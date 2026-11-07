"""Private dashboard state API. Never receives passwords, raw tokens or raw IPs."""

import math
from datetime import timedelta

from fastapi import APIRouter, Depends, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import session_dependency
from app.models import DashboardLoginBucket, DashboardSession
from app.security import require_admin

SESSION_SECONDS = 8 * 60 * 60
router = APIRouter(
    prefix="/api/v1/dashboard-auth", dependencies=[Depends(require_admin)], include_in_schema=False
)


class TokenHash(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class LoginAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    credentials_valid: bool = Field(strict=True)
    token_hash: str | None = Field(None, pattern=r"^[a-f0-9]{64}$")
    expires_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def complete_session(self):
        if self.credentials_valid and (self.token_hash is None or self.expires_at is None):
            raise ValueError("Successful login requires session metadata")
        return self


def cleanup_auth(session: Session):
    # Bounded indexed work; also run on login so storage does not depend on worker uptime.
    for model, column, key in (
        (DashboardSession, DashboardSession.expires_at, DashboardSession.token_hash),
        (DashboardLoginBucket, DashboardLoginBucket.resets_at, DashboardLoginBucket.key),
    ):
        session.execute(
            delete(model).where(key.in_(select(key).where(column <= func.now()).limit(2000)))
        )


@router.post("/login")
def login(body: LoginAttempt, response: Response, session: Session = Depends(session_dependency)):
    # All instances share this short transaction. No race between admission and issuance.
    session.execute(text("SELECT pg_advisory_xact_lock(1729048102)"))
    now = session.scalar(select(func.clock_timestamp()))
    cleanup_auth(session)
    settings = get_settings()
    keys = [
        ("client:" + body.client_key, settings.dashboard_login_client_limit),
        ("account", settings.dashboard_login_account_limit),
    ]
    buckets = []
    for key, limit in keys:
        bucket = session.get(DashboardLoginBucket, key)
        if bucket and bucket.resets_at <= now:
            bucket.attempts = 0
            bucket.resets_at = now + timedelta(seconds=settings.dashboard_login_window_seconds)
        if bucket and bucket.attempts >= limit:
            response.status_code = 429
            response.headers["Retry-After"] = str(
                max(1, math.ceil((bucket.resets_at - now).total_seconds()))
            )
            session.commit()
            return {"code": "RATE_LIMIT"}
        buckets.append((key, bucket))
    for key, bucket in buckets:
        if bucket is None:
            bucket = DashboardLoginBucket(
                key=key,
                attempts=0,
                resets_at=now + timedelta(seconds=settings.dashboard_login_window_seconds),
            )
            session.add(bucket)
        bucket.attempts += 1
    if not body.credentials_valid:
        session.commit()
        response.status_code = 401
        return {"code": "LOGIN"}
    expires_at = min(body.expires_at, now + timedelta(seconds=SESSION_SECONDS))
    if expires_at <= now:
        session.commit()
        response.status_code = 422
        return {"code": "VALIDATION"}
    session.add(DashboardSession(token_hash=body.token_hash, expires_at=expires_at))
    session.commit()
    return {"ok": True}


@router.post("/validate")
def validate(body: TokenHash, session: Session = Depends(session_dependency)):
    valid = session.scalar(
        select(DashboardSession.token_hash).where(
            DashboardSession.token_hash == body.token_hash,
            DashboardSession.expires_at > func.clock_timestamp(),
        )
    )
    return {"valid": valid is not None}


@router.post("/revoke")
def revoke(body: TokenHash, session: Session = Depends(session_dependency)):
    session.execute(delete(DashboardSession).where(DashboardSession.token_hash == body.token_hash))
    session.commit()
    return {"ok": True}
