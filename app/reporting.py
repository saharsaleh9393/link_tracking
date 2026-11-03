import base64
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func, select, tuple_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import session_dependency
from app.models import ClickEvent as E
from app.models import DailyCampaignStat, DailyStat
from app.schemas import UTM_FIELDS
from app.security import require_reporting

router = APIRouter(prefix="/api/v1", tags=["Reporting"], dependencies=[Depends(require_reporting)])


@dataclass
class Filters:
    start: datetime
    end: datetime
    link_id: uuid.UUID | None
    campaign_id: uuid.UUID | None


def filters(
    start: datetime,
    end: datetime,
    link_id: uuid.UUID | None = None,
    campaign_id: uuid.UUID | None = None,
) -> Filters:
    if start.utcoffset() is None or end.utcoffset() is None:
        raise HTTPException(422, "Dates must include a timezone")
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    if not start < end or end - start > timedelta(days=366):
        raise HTTPException(422, "Date range must be positive and no longer than 366 days")
    return Filters(start, end, link_id, campaign_id)


def event_conditions(f: Filters):
    result = [E.occurred_at >= f.start, E.occurred_at < f.end]
    if f.link_id:
        result.append(E.link_id == f.link_id)
    if f.campaign_id:
        result.append(E.campaign_id == f.campaign_id)
    return result


def counters():
    # Daily rotating digests support visitor-days across a range, not cross-day people.
    return [
        func.count().label("total_clicks"),
        func.count().filter(E.classification == "human").label("human_clicks"),
        func.count().filter(E.classification == "bot").label("bot_clicks"),
        func.count().filter(E.classification == "unknown").label("unknown_clicks"),
        func.count(distinct(E.visitor_digest))
        .filter(
            E.classification != "bot",
        )
        .label("estimated_visitor_days"),
    ]


def metadata(f: Filters):
    return {
        "start": f.start,
        "end": f.end,
        "timezone": "UTC",
        "unique_method": "daily rotating HMAC; non-bot visitor-days, not cross-day unique people",
        "raw_retention_days": get_settings().raw_retention_days,
        "partial_history": f.start
        < datetime.now(UTC) - timedelta(days=get_settings().raw_retention_days),
    }


@router.get("/analytics/summary")
def summary(f: Filters = Depends(filters), session: Session = Depends(session_dependency)):
    values = dict(session.execute(select(*counters()).where(*event_conditions(f))).mappings().one())
    single_day = f.start.date() == (f.end - timedelta(microseconds=1)).date()
    values["estimated_unique_visitors"] = values["estimated_visitor_days"] if single_day else None
    return {**metadata(f), **values}


DIMENSIONS = {
    "campaign": E.campaign_id,
    "link": E.link_id,
    "source": E.utm_source,
    "medium": E.utm_medium,
    "device": E.device,
    "country": E.country,
    "browser": E.browser,
    "os": E.os,
    "classification": E.classification,
}


@router.get("/analytics/breakdowns")
def breakdown(
    dimension: Literal[
        "campaign",
        "link",
        "source",
        "medium",
        "device",
        "country",
        "browser",
        "os",
        "classification",
    ],
    f: Filters = Depends(filters),
    offset: int = Query(0, ge=0, le=100000),
    limit: int = Query(100, ge=1, le=1000),
    session: Session = Depends(session_dependency),
):
    column = DIMENSIONS[dimension]
    query = select(column.label("value"), *counters()).where(*event_conditions(f)).group_by(column)
    rows = (
        session.execute(
            query.order_by(func.count().desc(), column.asc().nulls_last())
            .offset(offset)
            .limit(limit + 1)
        )
        .mappings()
        .all()
    )
    return {
        **metadata(f),
        "items": [dict(row) for row in rows[:limit]],
        "next_offset": offset + limit if len(rows) > limit else None,
    }


@router.get("/analytics/trends")
def trends(
    granularity: Literal["day", "hour"] = "day",
    f: Filters = Depends(filters),
    offset: int = Query(0, ge=0, le=100000),
    limit: int = Query(1000, ge=1, le=1000),
    session: Session = Depends(session_dependency),
):
    bucket = func.date_trunc(granularity, E.occurred_at)
    query = (
        select(bucket.label("bucket"), *counters())
        .where(*event_conditions(f))
        .group_by(bucket)
        .order_by(bucket)
    )
    rows = session.execute(query.offset(offset).limit(limit + 1)).mappings().all()
    return {
        **metadata(f),
        "items": [dict(row) for row in rows[:limit]],
        "next_offset": offset + limit if len(rows) > limit else None,
    }


@router.get("/analytics/link-comparison")
def comparison(
    link_ids: list[uuid.UUID] = Query(min_length=1, max_length=50),
    f: Filters = Depends(filters),
    session: Session = Depends(session_dependency),
):
    rows = (
        session.execute(
            select(E.link_id, *counters())
            .where(
                *event_conditions(f),
                E.link_id.in_(link_ids),
            )
            .group_by(E.link_id)
            .order_by(E.link_id)
        )
        .mappings()
        .all()
    )
    found = {row["link_id"]: dict(row) for row in rows}
    empty = {
        "total_clicks": 0,
        "human_clicks": 0,
        "bot_clicks": 0,
        "unknown_clicks": 0,
        "estimated_visitor_days": 0,
    }
    return {
        **metadata(f),
        "items": [found.get(key, {"link_id": key, **empty}) for key in dict.fromkeys(link_ids)],
    }


def encode_cursor(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def decode_cursor(value: str) -> dict:
    try:
        if len(value) > 4096:
            raise ValueError
        result = json.loads(base64.b64decode(value, altchars=b"-_", validate=True))
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (ValueError, TypeError):
        raise HTTPException(422, "Invalid cursor") from None


def cursor_scope(f: Filters):
    return [f.start.isoformat(), f.end.isoformat(), str(f.link_id), str(f.campaign_id)]


@router.get("/exports/clicks")
def raw_export(
    f: Filters = Depends(filters),
    cursor: str | None = Query(None, max_length=4096),
    limit: int = Query(1000, ge=1, le=5000),
    session: Session = Depends(session_dependency),
):
    cutoff = min(datetime.now(UTC), f.end)
    conditions = event_conditions(f)
    if cursor:
        data = decode_cursor(cursor)
        try:
            if data["scope"] != cursor_scope(f):
                raise ValueError
            cutoff = datetime.fromisoformat(data["cutoff"])
            last_time = datetime.fromisoformat(data["time"])
            if cutoff.utcoffset() is None or last_time.utcoffset() is None:
                raise ValueError
            conditions.append(
                tuple_(E.occurred_at, E.click_id) > tuple_(last_time, uuid.UUID(data["id"]))
            )
        except (KeyError, ValueError, TypeError):
            raise HTTPException(422, "Cursor does not match export") from None
    columns = [
        E.occurred_at,
        E.click_id,
        E.link_id,
        E.campaign_id,
        E.destination_id,
        E.link_version,
        E.device,
        E.os,
        E.browser,
        E.classification,
        E.bot_reason,
        E.ruleset,
        E.country,
        E.referrer_origin,
        *(getattr(E, key) for key in UTM_FIELDS),
    ]
    rows = (
        session.execute(
            select(*columns)
            .where(*conditions, E.occurred_at < cutoff)
            .order_by(
                E.occurred_at,
                E.click_id,
            )
            .limit(limit + 1)
        )
        .mappings()
        .all()
    )
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(
            {
                "scope": cursor_scope(f),
                "cutoff": cutoff.isoformat(),
                "time": last["occurred_at"].isoformat(),
                "id": str(last["click_id"]),
            }
        )
    return {
        **metadata(f),
        "cutoff": cutoff,
        "items": [dict(row) for row in rows[:limit]],
        "next_cursor": next_cursor,
    }


@router.get("/exports/daily")
def daily_export(
    f: Filters = Depends(filters),
    cursor: str | None = Query(None, max_length=4096),
    limit: int = Query(1000, ge=1, le=5000),
    session: Session = Depends(session_dependency),
):
    if f.campaign_id:
        raise HTTPException(
            422,
            "Daily link aggregates do not retain campaign snapshots; use campaign performance export",
        )
    if f.start.time().isoformat() != "00:00:00" or f.end.time().isoformat() != "00:00:00":
        raise HTTPException(422, "Daily export requires UTC midnight boundaries")
    conditions = [DailyStat.day >= f.start.date(), DailyStat.day < f.end.date()]
    if f.link_id:
        conditions.append(DailyStat.link_id == f.link_id)
    if cursor:
        data = decode_cursor(cursor)
        try:
            if data["scope"] != cursor_scope(f):
                raise ValueError
            day = datetime.fromisoformat(data["day"]).date()
            conditions.append(
                tuple_(DailyStat.day, DailyStat.link_id) > tuple_(day, uuid.UUID(data["id"]))
            )
        except (KeyError, ValueError, TypeError):
            raise HTTPException(422, "Cursor does not match export") from None
    rows = session.scalars(
        select(DailyStat)
        .where(*conditions)
        .order_by(DailyStat.day, DailyStat.link_id)
        .limit(limit + 1)
    ).all()
    items = [
        {column.name: getattr(row, column.name) for column in DailyStat.__table__.columns}
        for row in rows[:limit]
    ]
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(
            {"scope": cursor_scope(f), "day": last.day.isoformat(), "id": str(last.link_id)}
        )
    return {
        **metadata(f),
        "items": items,
        "next_cursor": next_cursor,
        "consistency": "live aggregates; current and previous UTC day may refresh during paging",
    }


@router.get("/exports/campaigns")
def campaign_export(
    f: Filters = Depends(filters),
    offset: int = Query(0, ge=0, le=100000),
    limit: int = Query(100, ge=1, le=1000),
    session: Session = Depends(session_dependency),
):
    if f.link_id:
        raise HTTPException(422, "Campaign aggregates cannot be filtered by link")
    return performance_export(DailyCampaignStat, "campaign_id", f, offset, limit, session)


@router.get("/exports/links")
def link_export(
    f: Filters = Depends(filters),
    offset: int = Query(0, ge=0, le=100000),
    limit: int = Query(100, ge=1, le=1000),
    session: Session = Depends(session_dependency),
):
    if f.campaign_id:
        raise HTTPException(
            422, "Link aggregates cannot be filtered by historical campaign; use campaign export"
        )
    return performance_export(DailyStat, "link_id", f, offset, limit, session)


def performance_export(model, key, f, offset, limit, session):
    if f.start.time().isoformat() != "00:00:00" or f.end.time().isoformat() != "00:00:00":
        raise HTTPException(422, "Performance exports require UTC midnight boundaries")
    column = getattr(model, key)
    conditions = [model.day >= f.start.date(), model.day < f.end.date()]
    selected = f.link_id if key == "link_id" else f.campaign_id
    if selected:
        conditions.append(column == selected)
    query = (
        select(
            column.label(key),
            *(
                func.sum(getattr(model, name)).label(name)
                for name in (
                    "total_clicks",
                    "human_clicks",
                    "bot_clicks",
                    "unknown_clicks",
                )
            ),
            func.sum(model.estimated_unique_visitors).label("estimated_visitor_days"),
            func.min(model.refreshed_at).label("oldest_refresh"),
        )
        .where(*conditions)
        .group_by(column)
        .order_by(column)
    )
    rows = session.execute(query.offset(offset).limit(limit + 1)).mappings().all()
    return {
        **metadata(f),
        "items": [dict(row) for row in rows[:limit]],
        "next_offset": offset + limit if len(rows) > limit else None,
        "source": "daily aggregates; survives raw-event retention",
        "partial_history": False,
    }
