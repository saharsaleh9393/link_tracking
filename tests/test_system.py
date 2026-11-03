import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.links import resolve_link
from app.models import ClickEvent, DailyCampaignStat, DailyStat
from app.security import validate_destination
from app.worker import aggregate, ensure_partitions

HUMAN = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
}


def window():
    now = datetime.now(UTC)
    return {
        "start": (now - timedelta(days=1)).isoformat(),
        "end": (now + timedelta(days=1)).isoformat(),
    }


def day_window():
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return {"start": start.isoformat(), "end": (start + timedelta(days=1)).isoformat()}


@pytest.mark.parametrize(
    "value",
    [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "http://localhost/a",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://[::1]",
        "http://169.254.169.254/latest",
        "https://user:pass@example.com",
        "https://example.com/\r\nLocation:x",
        "https://example.com/%0d%0a",
        "https://example.com:99999",
        "https://example.com\\@127.0.0.1",
        "http://2130706433",
        "http://0x7f.0.0.1",
        "http://service.internal",
        "https://example.com:22/",
    ],
)
def test_destination_rejects_abuse(value):
    with pytest.raises(ValueError):
        validate_destination(value)


@pytest.mark.parametrize(
    "value",
    [
        "https://www.instagram.com/example/?igsh=abc",
        "https://wa.me/989123456789?text=hello%20there",
        "https://t.me/channel",
        "https://example.com/path?signature=a%2Fb%3D#section",
    ],
)
def test_destination_preserved(value):
    assert validate_destination(value) == value


def test_auth_and_readonly_scope(client, admin, report):
    assert client.get("/api/v1/links").status_code == 401
    assert client.get("/api/v1/links", headers=report).status_code == 401
    assert client.get("/api/v1/links", headers=admin).status_code == 200
    assert (
        client.get("/api/v1/analytics/summary", headers=report, params=window()).status_code == 200
    )
    assert client.get("/metrics").status_code == 401


def test_campaign_and_link_lifecycle(client, admin, new_link):
    campaign = client.post("/api/v1/campaigns", headers=admin, json={"name": "Launch"}).json()
    link = new_link(campaign_id=campaign["id"], slug="launch")
    assert client.get("/api/v1/campaigns", headers=admin).json()[0]["name"] == "Launch"
    assert (
        client.get("/api/v1/links", headers=admin, params={"campaign_id": campaign["id"]}).json()[
            0
        ]["id"]
        == link["id"]
    )
    assert client.get("/r/launch").status_code == 302
    changed = client.patch(
        f"/api/v1/links/{link['id']}",
        headers=admin,
        json={"status": "disabled", "expected_version": 1},
    )
    assert changed.status_code == 200
    assert client.get("/r/launch").status_code == 410
    assert (
        client.patch(
            f"/api/v1/links/{link['id']}",
            headers=admin,
            json={"status": "active", "expected_version": 1},
        ).status_code
        == 409
    )
    assert client.delete(f"/api/v1/links/{link['id']}", headers=admin).status_code == 204
    assert client.get("/r/launch").status_code == 410
    assert (
        client.post(
            "/api/v1/links",
            headers=admin,
            json={"slug": "launch", "destination_url": "https://example.com"},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/links/{link['id']}",
            headers=admin,
            json={"status": "active", "expected_version": 3},
        ).status_code
        == 410
    )


def test_redirect_capture_privacy_and_utm(client, admin, new_link, database):
    link = new_link(utm_source="default", utm_medium="social")
    url = f"/r/{link['slug']}?utm_source=instagram&target=https://evil.example"
    response = client.get(
        url,
        headers={
            **HUMAN,
            "Referer": "https://referrer.example/path?email=private",
            "X-Forwarded-For": "1.1.1.1",
            "CF-IPCountry": "US",
        },
    )
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/path?a=1%2F2#part"
    assert response.headers["cache-control"] == "no-store"
    client.get(url, headers=HUMAN)
    with Session(database) as session:
        events = session.scalars(select(ClickEvent)).all()
        assert len(events) == 2
        assert events[0].click_id != events[1].click_id
        assert events[0].visitor_digest == events[1].visitor_digest
        assert events[0].referrer_origin == "https://referrer.example"
        assert events[0].country is None
        assert events[0].utm_source == "instagram"
        assert events[0].utm_medium == "social"
        assert events[0].classification == "human"
        assert events[0].device == "desktop"
    raw = client.get("/api/v1/exports/clicks", headers=admin, params=window()).json()
    assert "visitor_digest" not in raw["items"][0]
    assert "private" not in str(raw)
    summary = client.get("/api/v1/analytics/summary", headers=admin, params=window()).json()
    assert summary["total_clicks"] == 2
    assert summary["estimated_visitor_days"] == 1
    assert summary["estimated_unique_visitors"] is None


def test_head_bot_unknown_and_trends(client, admin, new_link):
    link = new_link()
    url = f"/r/{link['slug']}"
    assert client.head(url).status_code == 302
    client.get(url, headers={"User-Agent": "TelegramBot (like TwitterBot)"})
    client.get(url, headers={"User-Agent": ""})
    client.get(url, headers=HUMAN)
    summary = client.get("/api/v1/analytics/summary", headers=admin, params=day_window()).json()
    assert summary["total_clicks"] == 3
    assert summary["bot_clicks"] == 1
    assert summary["human_clicks"] == 1
    assert summary["unknown_clicks"] == 1
    assert summary["estimated_unique_visitors"] == 2
    for dimension in (
        "source",
        "medium",
        "campaign",
        "device",
        "country",
        "browser",
        "os",
        "classification",
    ):
        response = client.get(
            "/api/v1/analytics/breakdowns",
            headers=admin,
            params={**window(), "dimension": dimension},
        )
        assert response.status_code == 200, response.text
        assert sum(item["total_clicks"] for item in response.json()["items"]) == 3
    for granularity in ("day", "hour"):
        response = client.get(
            "/api/v1/analytics/trends",
            headers=admin,
            params={**window(), "granularity": granularity},
        )
        assert response.status_code == 200, response.text
        assert sum(item["total_clicks"] for item in response.json()["items"]) == 3


def test_destinations_and_history(client, admin, new_link, database):
    link = new_link(utm_campaign="original")
    client.get(f"/r/{link['slug']}", headers=HUMAN)
    added = client.post(
        f"/api/v1/links/{link['id']}/destinations",
        headers=admin,
        json={"url": "https://wa.me/989123456789?text=hi%20there"},
    )
    assert added.status_code == 201
    dest = added.json()
    changed = client.patch(
        f"/api/v1/links/{link['id']}",
        headers=admin,
        json={"active_destination_id": dest["id"], "utm_campaign": "new", "expected_version": 1},
    )
    assert changed.status_code == 200
    response = client.get(f"/r/{link['slug']}", headers=HUMAN)
    assert response.headers["location"] == dest["url"]
    with Session(database) as session:
        events = session.scalars(select(ClickEvent).order_by(ClickEvent.occurred_at)).all()
        assert events[0].utm_campaign == "original"
        assert events[0].destination_id != events[1].destination_id
    other = new_link()
    assert (
        client.patch(
            f"/api/v1/links/{other['id']}",
            headers=admin,
            json={"active_destination_id": dest["id"], "expected_version": 1},
        ).status_code
        == 422
    )


def test_forward_utm_preserves_existing_query(client, new_link):
    link = new_link(
        destination_url="https://example.com/?sig=a%2Fb&text=a+b&utm_source=owned#frag",
        forward_utm=True,
        utm_medium="social",
    )
    response = client.get(f"/r/{link['slug']}?utm_source=new&utm_content=hi%20there")
    assert (
        response.headers["location"]
        == "https://example.com/?sig=a%2Fb&text=a+b&utm_source=owned&utm_medium=social&utm_content=hi+there#frag"
    )


def test_export_keyset_and_filters(client, admin, new_link):
    link = new_link()
    for _ in range(5):
        client.get(f"/r/{link['slug']}", headers=HUMAN)
    params = {**window(), "limit": 2}
    items = []
    while True:
        response = client.get("/api/v1/exports/clicks", headers=admin, params=params)
        assert response.status_code == 200, response.text
        data = response.json()
        items.extend(data["items"])
        if not data["next_cursor"]:
            break
        params["cursor"] = data["next_cursor"]
    assert len(items) == len({item["click_id"] for item in items}) == 5
    assert (
        client.get(
            "/api/v1/exports/clicks", headers=admin, params={**window(), "cursor": "bad!"}
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/analytics/summary",
            headers=admin,
            params={"start": "2026-01-01", "end": "2026-01-02"},
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/analytics/summary",
            headers=admin,
            params={"start": "2020-01-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"},
        ).status_code
        == 422
    )


def test_aggregation_repeatability_and_exports(client, admin, new_link, database):
    campaign = client.post("/api/v1/campaigns", headers=admin, json={"name": "Campaign"}).json()
    first = new_link(campaign_id=campaign["id"])
    second = new_link(campaign_id=campaign["id"])
    for link in (first, first, second):
        client.get(f"/r/{link['slug']}", headers=HUMAN)
    client.get(f"/r/{first['slug']}", headers={"User-Agent": "Googlebot"})
    aggregate()
    aggregate()
    ensure_partitions()
    ensure_partitions()
    with Session(database) as session:
        rows = session.scalars(select(DailyStat)).all()
        assert sum(row.total_clicks for row in rows) == 4
        campaign_stat = session.scalar(select(DailyCampaignStat))
        assert campaign_stat.total_clicks == 4
        assert campaign_stat.estimated_unique_visitors == 1
    params = day_window()
    daily = client.get("/api/v1/exports/daily", headers=admin, params={**params, "limit": 1}).json()
    assert len(daily["items"]) == 1
    assert daily["next_cursor"]
    next_page = client.get(
        "/api/v1/exports/daily",
        headers=admin,
        params={**params, "limit": 1, "cursor": daily["next_cursor"]},
    ).json()
    assert next_page["items"][0]["link_id"] != daily["items"][0]["link_id"]
    for path in ("campaigns", "links"):
        response = client.get(f"/api/v1/exports/{path}", headers=admin, params=params)
        assert response.status_code == 200, response.text
        assert sum(row["total_clicks"] for row in response.json()["items"]) == 4
    comparison = client.get(
        "/api/v1/analytics/link-comparison",
        headers=admin,
        params={**window(), "link_ids": [first["id"], second["id"], str(uuid.uuid4())]},
    )
    assert [row["total_clicks"] for row in comparison.json()["items"]] == [3, 1, 0]


def test_tracking_failure_still_redirects(client, new_link, monkeypatch):
    link = new_link()
    original = Session.commit

    def failure(session):
        raise OperationalError("insert", {}, Exception("offline"))

    monkeypatch.setattr(Session, "commit", failure)
    assert client.get(f"/r/{link['slug']}", headers=HUMAN).status_code == 302
    monkeypatch.setattr(Session, "commit", original)


def test_concurrent_clicks(client, admin, new_link):
    link = new_link()
    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(
            executor.map(
                lambda _: client.get(f"/r/{link['slug']}", headers=HUMAN).status_code, range(40)
            )
        )
    assert statuses == [302] * 40
    summary = client.get("/api/v1/analytics/summary", headers=admin, params=window()).json()
    assert summary["total_clicks"] == 40
    assert summary["estimated_visitor_days"] == 1


def test_expired_missing_and_validation(client, admin, new_link):
    link = new_link(expires_at=(datetime.now(UTC) - timedelta(days=1)).isoformat())
    assert client.get(f"/r/{link['slug']}").status_code == 410
    assert client.get("/r/missing").status_code == 404
    assert client.get("/r/x").status_code == 404
    response = client.post(
        "/api/v1/links", headers=admin, json={"destination_url": "https://user:secret@example.com"}
    )
    assert response.status_code == 422
    assert "secret" not in response.text
    assert client.get("/health/ready").status_code == 200


def test_trusted_proxy_country_and_rotation(client, admin, new_link, monkeypatch, database):
    from starlette.requests import Request

    from app.tracking import collect_metadata

    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "203.0.113.0/24")
    monkeypatch.setenv("COUNTRY_HEADER", "cf-ipcountry")
    get_settings.cache_clear()
    link = new_link()
    client.get(
        f"/r/{link['slug']}", headers={**HUMAN, "CF-IPCountry": "IR", "X-Forwarded-For": "1.1.1.1"}
    )
    with Session(database) as session:
        event = session.scalar(select(ClickEvent))
        assert event.country == "IR"
    request = Request(
        {
            "type": "http",
            "client": ("1.1.1.1", 10),
            "headers": [(b"user-agent", HUMAN["User-Agent"].encode())],
        }
    )
    now = datetime.now(UTC)
    assert (
        collect_metadata(request, now)["visitor_digest"]
        != collect_metadata(request, now + timedelta(days=1))["visitor_digest"]
    )


def test_cache_hit_avoids_select(client, new_link, database):
    link = new_link()
    with Session(database) as session:
        assert resolve_link(session, link["slug"])

    class NoQueries:
        def execute(self, *args):
            pytest.fail("A cache hit should not query the database")

    assert resolve_link(NoQueries(), link["slug"])["id"] == uuid.UUID(link["id"])


def test_database_owns_destination_constraint(client, new_link, database):
    link = new_link()
    other = new_link()
    with database.connect() as connection:
        transaction = connection.begin()
        connection.execute(
            text("UPDATE links SET active_destination_id=:destination WHERE id=:link"),
            {"destination": other["active_destination_id"], "link": link["id"]},
        )
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            transaction.commit()


def test_archive_and_nullable_update_validation(client, admin, new_link):
    campaign = client.post("/api/v1/campaigns", headers=admin, json={"name": "Archive"}).json()
    response = client.patch(
        f"/api/v1/campaigns/{campaign['id']}", headers=admin, json={"archived": True}
    )
    assert response.status_code == 200
    response = client.post(
        "/api/v1/links",
        headers=admin,
        json={"destination_url": "https://example.com", "campaign_id": campaign["id"]},
    )
    assert response.status_code == 422
    link = new_link()
    for field in ("status", "forward_utm", "active_destination_id"):
        assert (
            client.patch(
                f"/api/v1/links/{link['id']}",
                headers=admin,
                json={field: None, "expected_version": 1},
            ).status_code
            == 422
        )


def test_source_and_campaign_history_after_edit(client, admin, new_link, database):
    campaign = client.post("/api/v1/campaigns", headers=admin, json={"name": "Before"}).json()
    link = new_link(campaign_id=campaign["id"], utm_source="before")
    client.get(f"/r/{link['slug']}", headers=HUMAN)
    client.patch(
        f"/api/v1/links/{link['id']}",
        headers=admin,
        json={"campaign_id": None, "utm_source": "after", "expected_version": 1},
    ).raise_for_status()
    client.get(f"/r/{link['slug']}", headers=HUMAN)
    aggregate()
    response = client.get(
        "/api/v1/analytics/summary",
        headers=admin,
        params={**window(), "campaign_id": campaign["id"]},
    ).json()
    assert response["total_clicks"] == 1
    exported = client.get("/api/v1/exports/campaigns", headers=admin, params=day_window()).json()[
        "items"
    ]
    assert len(exported) == 2
    assert sum(item["total_clicks"] for item in exported) == 2


def test_retention_preserves_aggregates(client, database):
    from app.models import AggregationState
    from app.worker import purge_expired

    today = datetime.now(UTC).date()
    old_month = (today - timedelta(days=200)).replace(day=1)
    next_month = (old_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    name = f"click_events_{old_month:%Y_%m}"
    with database.begin() as connection:
        connection.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF click_events FOR VALUES FROM ('{old_month}') TO ('{next_month}')"
            )
        )
    link_id = uuid.uuid4()
    with Session(database) as session:
        session.add(
            ClickEvent(
                occurred_at=datetime.combine(old_month, datetime.min.time(), tzinfo=UTC),
                click_id=uuid.uuid4(),
                link_id=link_id,
                destination_id=uuid.uuid4(),
                link_version=1,
                device="desktop",
                os="Other",
                browser="Other",
                classification="unknown",
                visitor_digest="old",
            )
        )
        session.commit()
    # No processing cursor means no deletion, even if the partition is old.
    purge_expired()
    with database.connect() as connection:
        assert connection.scalar(text("SELECT to_regclass(:name)"), {"name": name})
    for _ in range(7):
        aggregate()
    with Session(database) as session:
        assert session.get(AggregationState, "daily").next_day == today
        assert session.get(DailyStat, (old_month, link_id)).total_clicks == 1
    purge_expired()
    with database.connect() as connection:
        assert connection.scalar(text("SELECT to_regclass(:name)"), {"name": name}) is None
    aggregate()
    with Session(database) as session:
        assert session.get(DailyStat, (old_month, link_id)).total_clicks == 1
