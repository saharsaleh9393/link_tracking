from datetime import date

import httpx
import pytest

from dashboard.api import ApiClient, ApiError, DashboardSettings
from dashboard.presentation import chart, date_params


def settings():
    return DashboardSettings(
        admin_api_key="dashboard-admin-" + "x" * 40, report_api_key="dashboard-report-" + "y" * 40
    )


def test_client_keeps_credentials_in_authorization_only():
    seen = []

    def handle(request):
        seen.append(request)
        if request.url.path == "/api/v1/links":
            return httpx.Response(200, json=[{"id": "link"}], headers={"X-Total-Count": "42"})
        return httpx.Response(200, json={"total_clicks": 2})

    api = ApiClient(settings(), transport=httpx.MockTransport(handle))
    page = api.page("links", q="کمپین", campaign_id=None)
    assert page.total == 42 and page.items == [{"id": "link"}]
    api.get("/api/v1/analytics/summary", start="2026-11-01T00:00:00Z")
    assert (
        seen[0].headers["authorization"] == "Bearer " + settings().admin_api_key.get_secret_value()
    )
    assert (
        seen[1].headers["authorization"] == "Bearer " + settings().report_api_key.get_secret_value()
    )
    for request in seen:
        assert "dashboard-admin" not in str(request.url)
        assert "dashboard-report" not in str(request.url)
        assert "authorization" not in request.url.params
    assert api.tracking_url("campaign-1") == "http://127.0.0.1:8000/r/campaign-1"
    api.close()


@pytest.mark.parametrize("status", [301, 401, 403, 404, 409, 410, 422, 429, 500, 503])
def test_client_sanitizes_backend_errors(status):
    secret = "NEVER-RENDER-THIS-TOKEN"
    api = ApiClient(
        settings(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                status, json={"detail": secret}, headers={"Location": "https://evil.example/"}
            )
        ),
    )
    with pytest.raises(ApiError) as exc:
        api.get("/api/v1/links")
    assert secret not in str(exc.value)
    assert "Bearer" not in str(exc.value)
    api.close()


def test_client_handles_network_and_invalid_json():
    def offline(request):
        raise httpx.ConnectError("secret-token-in-network-error", request=request)

    api = ApiClient(settings(), transport=httpx.MockTransport(offline))
    with pytest.raises(ApiError) as exc:
        api.get("/api/v1/links")
    assert "secret-token" not in str(exc.value)
    api.close()
    api = ApiClient(
        settings(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, text="<html>not the API</html>")
        ),
    )
    with pytest.raises(ApiError):
        api.get("/api/v1/links")
    api.close()


def test_tehran_inclusive_dates_and_chart():
    assert date_params(date(2026, 11, 4), date(2026, 11, 4)) == {
        "start": "2026-11-03T20:30:00+00:00",
        "end": "2026-11-04T20:30:00+00:00",
    }
    with pytest.raises(ValueError):
        date_params(date(2026, 11, 4), date(2026, 1, 1))
    figure = chart([{"value": "instagram", "total_clicks": 17}])
    assert list(figure.data[0].y) == [17]
    assert list(figure.data[0].x) == ["instagram"]


def test_dashboard_settings_reject_url_credentials():
    with pytest.raises(ValueError):
        DashboardSettings(admin_api_key="key", dashboard_api_url="https://user:token@example.com")
