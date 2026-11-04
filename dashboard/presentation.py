"""Formatting and chart helpers only; counting and classification remain in the API."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import plotly.graph_objects as go

TEHRAN = ZoneInfo("Asia/Tehran")
UTMS = {
    "utm_source": "منبع",
    "utm_medium": "رسانه",
    "utm_campaign": "کمپین UTM",
    "utm_content": "محتوا",
    "utm_term": "عبارت",
}
STATUS = {"active": "فعال", "disabled": "غیرفعال", "deleted": "حذف‌شده"}
CLASSIFICATION = {"human": "انسان (تخمینی)", "bot": "ربات", "unknown": "نامشخص"}
DEVICE = {"desktop": "رایانه", "mobile": "موبایل", "tablet": "تبلت", "other": "سایر"}


def date_params(start: date, end: date):
    """User selects inclusive Tehran calendar days; backend receives exclusive UTC end."""
    if start > end or (end - start).days >= 366:
        raise ValueError("بازه باید معتبر و حداکثر ۳۶۶ روز باشد.")
    return {
        "start": datetime.combine(start, datetime.min.time(), TEHRAN).astimezone(UTC).isoformat(),
        "end": datetime.combine(end + timedelta(days=1), datetime.min.time(), TEHRAN)
        .astimezone(UTC)
        .isoformat(),
    }


def display_time(value):
    if not value:
        return "—"
    try:
        return (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            .astimezone(TEHRAN)
            .strftime("%Y/%m/%d · %H:%M")
        )
    except (TypeError, ValueError):
        return "—"


def effective_status(link):
    if link["status"] == "active" and link.get("expires_at"):
        if datetime.fromisoformat(link["expires_at"].replace("Z", "+00:00")) <= datetime.now(UTC):
            return "منقضی"
    return STATUS.get(link["status"], "نامشخص")


def chart(items, *, trend=False, labels=None, title=""):
    labels = labels or {}
    x = [
        display_time(row["bucket"])
        if trend
        else labels.get(row.get("value"), row.get("value") or "نامشخص")
        for row in items
    ]
    y = [row["total_clicks"] for row in items]
    if trend:
        trace = go.Scatter(
            x=x, y=y, mode="lines+markers", fill="tozeroy", line={"color": "#6755df", "width": 3}
        )
    else:
        trace = go.Bar(x=x, y=y, marker_color="#6755df", marker_line_width=0)
    figure = go.Figure(trace)
    figure.update_layout(
        title=title,
        font={"family": "Tahoma, sans-serif", "color": "#334155"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 45, "b": 30},
        height=330,
        xaxis_title=None,
        yaxis_title="تعداد کلیک",
        hovermode="x unified",
    )
    figure.update_yaxes(rangemode="tozero", gridcolor="#edf0f5", separatethousands=True)
    return figure
