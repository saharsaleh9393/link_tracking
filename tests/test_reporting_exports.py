import csv
import io
from datetime import UTC, datetime, timedelta

import pytest

from app.csv_exports import csv_cell


def window():
    now = datetime.now(UTC)
    return {
        "start": (now - timedelta(days=1)).isoformat(),
        "end": (now + timedelta(days=1)).isoformat(),
    }


def test_csv_click_export_paging_and_excel_safety(client, report, new_link):
    link = new_link(
        utm_content='=HYPERLINK("https://example.com","کمپین")', utm_source="فارسی, منبع"
    )
    for _ in range(3):
        client.get(f"/r/{link['slug']}")
    params = {**window(), "limit": 2, "link_id": link["id"]}
    first = client.get("/api/v1/exports/clicks.csv", headers=report, params=params)
    assert first.status_code == 200
    assert first.content.startswith(b"\xef\xbb\xbf")
    assert "attachment" in first.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(first.text.lstrip("\ufeff"))))
    assert len(rows) == 2
    assert rows[0]["utm_source"] == "فارسی, منبع"
    assert rows[0]["utm_content"].startswith("'=HYPERLINK")
    assert "visitor_digest" not in rows[0] and "ip" not in rows[0]
    cursor = first.headers["x-next-cursor"]
    second = client.get(
        "/api/v1/exports/clicks.csv", headers=report, params={**params, "cursor": cursor}
    )
    more = list(csv.DictReader(io.StringIO(second.text.lstrip("\ufeff"))))
    assert len(more) == 1
    assert len({row["click_id"] for row in [*rows, *more]}) == 3
    assert "x-next-cursor" not in second.headers
    assert client.get("/api/v1/exports/clicks.csv", params=window()).status_code == 401
    assert (
        client.post("/api/v1/campaigns", headers=report, json={"name": "Forbidden"}).status_code
        == 401
    )


@pytest.mark.parametrize(
    "value", ["=SUM(1,1)", "+SUM(1,1)", "-SUM(1,1)", "@SUM(1,1)", " \t=1", "\rnew", "\tnew"]
)
def test_csv_formula_values_are_neutralized(value):
    assert csv_cell(value) == "'" + value


def test_csv_aggregate_queries_match_json(client, report, new_link):
    link = new_link(utm_source="instagram")
    client.get(f"/r/{link['slug']}")
    for resource, extra in (
        ("breakdowns", {"dimension": "source"}),
        ("trends", {"granularity": "hour"}),
    ):
        params = {**window(), **extra}
        response = client.get(f"/api/v1/analytics/{resource}.csv", headers=report, params=params)
        rows = list(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))
        reference = client.get(
            f"/api/v1/analytics/{resource}", headers=report, params=params
        ).json()
        assert (
            sum(int(row["total_clicks"]) for row in rows)
            == sum(row["total_clicks"] for row in reference["items"])
            == 1
        )
    assert (
        client.get(
            "/api/v1/analytics/breakdowns.csv",
            headers=report,
            params={**window(), "dimension": "invalid"},
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/analytics/trends.csv",
            headers=report,
            params={**window(), "granularity": "invalid"},
        ).status_code
        == 422
    )


def test_read_only_catalogs_and_status_do_not_expose_secrets(client, admin, report, new_link):
    campaign = client.post("/api/v1/campaigns", headers=admin, json={"name": "API campaign"}).json()
    for _ in range(3):
        new_link(campaign_id=campaign["id"])
    first = client.get("/api/v1/reporting/links", headers=report, params={"limit": 2}).json()
    second = client.get(
        "/api/v1/reporting/links", headers=report, params={"limit": 2, "after": first["next_after"]}
    ).json()
    assert len({row["id"] for row in [*first["items"], *second["items"]]}) == 3
    assert "destination_url" not in str(first)
    assert (
        client.get("/api/v1/reporting/campaigns", headers=report).json()["items"][0]["name"]
        == "API campaign"
    )
    status = client.get("/api/v1/reporting/status", headers=report).json()
    assert status["api_version"] == "v1"
    assert "database_url" not in str(status) and "geoip_database_path" not in str(status)
    assert client.get("/api/v1/reporting/status").status_code == 401
