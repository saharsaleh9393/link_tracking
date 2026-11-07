import logging
import re
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from time import monotonic

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.csv_exports import router as csv_router
from app.db import get_engine, session_dependency
from app.links import resolve_link
from app.links import router as management_router
from app.linkspace_config import RESERVED, matches_route
from app.linkspaces import router as linkspace_router
from app.models import ClickEvent
from app.reporting import router as reporting_router
from app.reporting_access import router as reporting_access_router
from app.security import ConfiguredTrustedHosts, require_admin
from app.tracking import collect_metadata, effective_utms, redirect_url, trusted_peer

logger = logging.getLogger("tracker")
redirects = Counter("tracker_redirects_total", "Redirect outcomes", ["outcome"])
latency = Histogram("tracker_redirect_duration_seconds", "Redirect handler duration")


@asynccontextmanager
async def lifespan(app):
    get_settings()  # Fail closed before serving if credentials are missing or invalid.
    yield
    get_engine().dispose()


app = FastAPI(title="Marketing Link Tracking", version="0.1.0", lifespan=lifespan)
app.include_router(management_router)
app.include_router(linkspace_router)
app.include_router(reporting_router)
app.include_router(csv_router)
app.include_router(reporting_access_router)
app.add_middleware(ConfiguredTrustedHosts)


@app.middleware("http")
async def response_headers(request: Request, call_next):
    # Preserve the physical peer for trusted forwarding/country checks. Uvicorn's
    # proxy middleware would replace it, so accept only the scheme here.
    if trusted_peer(request):
        scheme = request.headers.get("x-forwarded-proto", "")
        if scheme in {"http", "https"}:
            request.scope["scheme"] = scheme
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Pydantic's default response echoes submitted input, potentially including URL tokens.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": list(item["loc"]), "type": item["type"], "msg": item["msg"]}
                for item in exc.errors()
            ]
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    logger.error("database_unavailable error_type=%s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})


@app.get("/health/live", tags=["Operations"])
def live():
    return {"status": "ok"}


@app.get("/health/ready", tags=["Operations"])
def ready(session: Session = Depends(session_dependency)):
    revision = session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
    if revision != "0003":
        raise HTTPException(503, "Database migration required")
    partition = session.scalar(
        text("SELECT to_regclass(:name)"), {"name": f"click_events_{datetime.now(UTC):%Y_%m}"}
    )
    if partition is None:
        raise HTTPException(503, "Current event partition missing; run maintenance")
    return {"status": "ready"}


@app.get("/metrics", dependencies=[Depends(require_admin)], include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.api_route("/r/{slug}", methods=["GET", "HEAD"], tags=["Redirect"])
def redirect(slug: str, request: Request):
    return perform_redirect(slug, request)


def perform_redirect(slug: str, request: Request, custom_path: str | None = None):
    started = monotonic()
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,80}", slug):
        raise HTTPException(404, "Link not found")
    if len(request.url.query) > 4096:
        raise HTTPException(414, "Query too long")
    with Session(get_engine()) as session:
        try:
            link = resolve_link(session, slug)
        except SQLAlchemyError:
            redirects.labels("resolution_failed").inc()
            raise
        finally:
            # End the read transaction before acquiring the event-write transaction.
            session.rollback()
        if link is None:
            raise HTTPException(404, "Link not found")
        if custom_path is not None and not matches_route(
            link, custom_path, request.headers.get("host", "")
        ):
            raise HTTPException(404, "Link not found")
        now = datetime.now(UTC)
        if link["status"] != "active" or (link["expires_at"] and link["expires_at"] <= now):
            raise HTTPException(410, "Link unavailable")
        utms = effective_utms(link, request)
        if any(
            value is not None and (len(value) > 200 or any(ord(c) < 32 for c in value))
            for value in utms.values()
        ):
            raise HTTPException(422, "UTM values must be at most 200 characters without controls")
        destination = redirect_url(link["url"], utms, link["forward_utm"])
        if request.method == "HEAD":
            return RedirectResponse(destination, status_code=302)
        click_id = uuid.uuid4()
        recorded = False
        try:
            session.execute(text("SET LOCAL statement_timeout = '250ms'"))
            session.execute(text("SET LOCAL lock_timeout = '100ms'"))
            session.add(
                ClickEvent(
                    occurred_at=now,
                    click_id=click_id,
                    link_id=link["id"],
                    campaign_id=link["campaign_id"],
                    destination_id=link["active_destination_id"],
                    link_version=link["version"],
                    **utms,
                    **collect_metadata(request, now),
                )
            )
            session.commit()
            recorded = True
        except SQLAlchemyError as exc:
            session.rollback()
            logger.error("click_recording_failed error_type=%s", type(exc).__name__)
        redirects.labels("recorded" if recorded else "unrecorded").inc()
        latency.observe(monotonic() - started)
        return RedirectResponse(destination, status_code=302)


@app.api_route("/{tracking_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
def configured_redirect(tracking_path: str, request: Request):
    parts = tracking_path.split("/")
    if (
        len(parts) not in {1, 2}
        or parts[0].lower() in RESERVED
        or parts[0].startswith("_")
        or (len(parts) == 2 and not re.fullmatch(r"[a-z0-9_-]{1,50}", parts[0]))
    ):
        raise HTTPException(404, "Link not found")
    return perform_redirect(parts[-1], request, custom_path=tracking_path)
