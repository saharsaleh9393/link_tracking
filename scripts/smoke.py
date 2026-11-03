"""Exercise a running local instance without printing credentials or destination secrets."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from dotenv import load_dotenv


def main():
    load_dotenv()
    base = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    headers = {"Authorization": "Bearer " + os.environ["ADMIN_API_KEY"]}
    with httpx.Client(base_url=base, headers=headers, follow_redirects=False, timeout=10) as client:
        client.get("/health/ready").raise_for_status()
        response = client.post(
            "/api/v1/links",
            json={
                "slug": "smoke-" + uuid.uuid4().hex[:12],
                "destination_url": "https://example.com/?campaign=smoke",
            },
        )
        response.raise_for_status()
        link = response.json()
        try:
            redirect = client.get(
                f"/r/{link['slug']}", headers={"User-Agent": "MarketingTrackerSmoke/1.0"}
            )
            assert redirect.status_code == 302
            assert redirect.headers["location"] == "https://example.com/?campaign=smoke"
            now = datetime.now(UTC)
            response = client.get(
                "/api/v1/analytics/summary",
                params={
                    "start": (now - timedelta(minutes=5)).isoformat(),
                    "end": (now + timedelta(seconds=1)).isoformat(),
                    "link_id": link["id"],
                },
            )
            response.raise_for_status()
            assert response.json()["total_clicks"] == 1
        finally:
            client.delete(f"/api/v1/links/{link['id']}").raise_for_status()
    print(
        "PASS: readiness, authenticated link creation, preserved redirect, persisted click, analytics, soft deletion"
    )


if __name__ == "__main__":
    main()
