"""Bounded, authenticated CSV pages sharing the JSON reporting queries."""

import csv
import io
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import session_dependency
from app.reporting import DIMENSIONS, Filters, breakdown, filters, raw_export, trends
from app.schemas import UTM_FIELDS
from app.security import require_reporting

router = APIRouter(prefix="/api/v1", tags=["Reporting"], dependencies=[Depends(require_reporting)])
COUNTERS = (
    "total_clicks",
    "human_clicks",
    "bot_clicks",
    "unknown_clicks",
    "estimated_visitor_days",
)
CLICK_FIELDS = (
    "occurred_at",
    "click_id",
    "link_id",
    "campaign_id",
    "destination_id",
    "link_version",
    "device",
    "os",
    "browser",
    "classification",
    "bot_reason",
    "ruleset",
    "country",
    "referrer_origin",
    *UTM_FIELDS,
)


def csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    if isinstance(value, str) and value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return str(value)


def csv_response(report: dict, fields: tuple[str, ...], filename: str):
    output = io.StringIO(newline="")
    output.write("\ufeff")  # UTF-8 BOM for Persian text in Windows Excel.
    writer = csv.writer(output)
    writer.writerow(fields)
    writer.writerows([csv_cell(row.get(key)) for key in fields] for row in report["items"])
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}.csv"',
        "Cache-Control": "no-store",
        "X-Export-Row-Count": str(len(report["items"])),
        "X-Partial-History": str(report.get("partial_history", False)).lower(),
    }
    if report.get("next_cursor"):
        headers["X-Next-Cursor"] = report["next_cursor"]
    if report.get("next_offset") is not None:
        headers["X-Next-Offset"] = str(report["next_offset"])
    return Response(
        output.getvalue().encode("utf-8"), media_type="text/csv; charset=utf-8", headers=headers
    )


@router.get("/exports/clicks.csv", response_class=Response)
def clicks_csv(
    f: Filters = Depends(filters),
    cursor: str | None = Query(None, max_length=4096),
    limit: int = Query(5000, ge=1, le=5000),
    session: Session = Depends(session_dependency),
):
    return csv_response(raw_export(f, cursor, limit, session), CLICK_FIELDS, "click-events")


@router.get("/analytics/breakdowns.csv", response_class=Response)
def breakdown_csv(
    dimension: str,
    f: Filters = Depends(filters),
    offset: int = Query(0, ge=0, le=100000),
    limit: int = Query(1000, ge=1, le=1000),
    session: Session = Depends(session_dependency),
):
    from fastapi import HTTPException

    if dimension not in DIMENSIONS:
        raise HTTPException(422, "Invalid breakdown dimension")
    return csv_response(
        breakdown(dimension, f, offset, limit, session), ("value", *COUNTERS), "traffic-breakdown"
    )


@router.get("/analytics/trends.csv", response_class=Response)
def trends_csv(
    granularity: str = "day",
    f: Filters = Depends(filters),
    offset: int = Query(0, ge=0, le=100000),
    limit: int = Query(1000, ge=1, le=1000),
    session: Session = Depends(session_dependency),
):
    from fastapi import HTTPException

    if granularity not in {"day", "hour"}:
        raise HTTPException(422, "Invalid granularity")
    return csv_response(
        trends(granularity, f, offset, limit, session), ("bucket", *COUNTERS), "click-trends"
    )
