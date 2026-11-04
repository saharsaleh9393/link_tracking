from datetime import UTC, datetime, timedelta


def test_management_search_counts_sort_and_permissions(client, admin, report, new_link):
    campaign = client.post("/api/v1/campaigns", headers=admin, json={"name": "کمپین یک"}).json()
    first = new_link(slug="alpha", campaign_id=campaign["id"])
    new_link(slug="beta")
    new_link(slug="literal_under_score")
    page = client.get(
        "/api/v1/links",
        headers=admin,
        params={"include_total": True, "limit": 1, "sort_by": "slug", "descending": True},
    )
    assert page.headers["X-Total-Count"] == "3"
    assert page.json()[0]["slug"] == "literal_under_score"
    assert len(client.get("/api/v1/links", headers=admin, params={"q": "_"}).json()) == 1
    assert client.get("/api/v1/links", headers=admin, params={"q": "%"}).json() == []
    assert (
        client.get("/api/v1/links", headers=admin, params={"sort_by": "invalid"}).status_code == 422
    )
    assert client.get("/api/v1/management/overview", headers=report).status_code == 401
    overview = client.get("/api/v1/management/overview", headers=admin).json()
    assert overview["total_links"] == 3 and overview["active_campaigns"] == 1
    assert overview["recent_activity"]
    client.delete(f"/api/v1/links/{first['id']}", headers=admin)
    assert client.get("/api/v1/management/overview", headers=admin).json()["total_links"] == 2
    campaigns = client.get(
        "/api/v1/campaigns",
        headers=admin,
        params={"q": "یک", "archived": False, "include_total": True},
    )
    assert campaigns.headers["X-Total-Count"] == "1"


def test_added_utm_dimensions_use_existing_counters(client, admin, new_link):
    link = new_link(utm_campaign="autumn", utm_content="story", utm_term="offer")
    client.get(f"/r/{link['slug']}")
    now = datetime.now(UTC)
    params = {
        "start": (now - timedelta(days=1)).isoformat(),
        "end": (now + timedelta(days=1)).isoformat(),
    }
    for dimension, value in (
        ("utm_campaign", "autumn"),
        ("utm_content", "story"),
        ("utm_term", "offer"),
    ):
        response = client.get(
            "/api/v1/analytics/breakdowns", headers=admin, params={**params, "dimension": dimension}
        )
        assert response.status_code == 200
        assert response.json()["items"][0]["value"] == value
        assert response.json()["items"][0]["total_clicks"] == 1
