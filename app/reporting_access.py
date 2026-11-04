"""Read-only integration metadata. No destination secrets or administration privileges."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.country import country_lookup
from app.db import session_dependency
from app.models import Campaign, Link
from app.security import require_reporting

router = APIRouter(
    prefix="/api/v1/reporting", tags=["Reporting"], dependencies=[Depends(require_reporting)]
)


@router.get("/status")
def reporting_status():
    settings = get_settings()
    return {
        "country": {
            "local_database_available": country_lookup.available(),
            "trusted_header_enabled": bool(
                settings.country_header and settings.trusted_proxy_cidrs.strip()
            ),
            "private_ips_remain_unknown": True,
            "historical_unknowns_recoverable": False,
        },
        "csv": {"click_page_size": 5000, "aggregate_page_size": 1000, "encoding": "utf-8-sig"},
        "api_version": "v1",
        "read_only_credential": "REPORT_API_KEY",
    }


def catalog_page(session, model, columns, after, limit):
    query = select(*columns).order_by(model.id).limit(limit + 1)
    if after:
        query = query.where(model.id > after)
    rows = session.execute(query).mappings().all()
    return {
        "items": [dict(row) for row in rows[:limit]],
        "next_after": str(rows[limit - 1]["id"]) if len(rows) > limit else None,
    }


@router.get("/links")
def link_catalog(
    after: uuid.UUID | None = None,
    limit: int = Query(500, ge=1, le=500),
    session: Session = Depends(session_dependency),
):
    return catalog_page(
        session,
        Link,
        (Link.id, Link.slug, Link.campaign_id, Link.status, Link.created_at),
        after,
        limit,
    )


@router.get("/campaigns")
def campaign_catalog(
    after: uuid.UUID | None = None,
    limit: int = Query(500, ge=1, le=500),
    session: Session = Depends(session_dependency),
):
    return catalog_page(
        session,
        Campaign,
        (Campaign.id, Campaign.name, Campaign.archived, Campaign.created_at),
        after,
        limit,
    )
