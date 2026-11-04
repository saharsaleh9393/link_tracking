import json
import os
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

import dashboard.app
from dashboard.api import ApiClient, ApiError, DashboardSettings

ROOT = Path(__file__).resolve().parents[1]
HUMAN = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"
}


@pytest.fixture
def ui(client, monkeypatch):
    def handle(request):
        response = client.request(
            request.method,
            request.url.path,
            params=request.url.params.multi_items(),
            headers=dict(request.headers),
            json=json.loads(request.content) if request.content else None,
        )
        return httpx.Response(
            response.status_code, headers=response.headers, content=response.content
        )

    api = ApiClient(
        DashboardSettings(
            admin_api_key=os.environ["ADMIN_API_KEY"], report_api_key=os.environ["REPORT_API_KEY"]
        ),
        transport=httpx.MockTransport(handle),
    )
    monkeypatch.setattr(dashboard.app, "get_client", lambda: api)
    yield AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=20)
    api.close()


def find(elements, label):
    return next(element for element in elements if element.label == label)


def navigate(ui, page):
    ui.sidebar.radio[0].set_value(page).run()
    assert not ui.exception


def test_overview_empty_and_secret_safety(ui):
    ui.run()
    assert not ui.exception
    assert [metric.value for metric in ui.metric] == ["0", "0", "0", "0"]
    rendered = str(ui)
    assert os.environ["ADMIN_API_KEY"] not in rendered
    assert os.environ["REPORT_API_KEY"] not in rendered
    assert ui.info


def test_link_create_edit_destinations_and_delete(ui, client, admin):
    ui.run()
    navigate(ui, "لینک‌ها")
    ui.text_input(key="new_destination").set_value("https://wa.me/989123456789?text=hello%20there")
    ui.text_input(key="new_slug").set_value("persian-launch")
    find(ui.button, "ساخت لینک").click().run()
    assert not ui.exception and not ui.error
    assert any("persian-launch" in block.value for block in ui.code)
    link = client.get("/api/v1/links", headers=admin).json()[0]
    assert link["slug"] == "persian-launch"
    find(ui.checkbox, "لینک فعال باشد").uncheck()
    find(ui.button, "ذخیره تغییرات").click().run()
    assert not ui.exception and not ui.error
    assert client.get("/r/persian-launch").status_code == 410
    find(ui.text_input, "آدرس مقصد جدید").set_value("https://t.me/newchannel")
    find(ui.button, "افزودن مقصد").click().run()
    assert not ui.exception and not ui.error
    destinations = client.get(f"/api/v1/links/{link['id']}/destinations", headers=admin).json()
    find(ui.selectbox, "انتخاب مقصد فعال").select(destinations[-1]["id"])
    find(ui.button, "فعال‌کردن مقصد انتخاب‌شده").click().run()
    assert not ui.exception and not ui.error
    assert (
        client.get(f"/api/v1/links/{link['id']}", headers=admin).json()["active_destination_id"]
        == destinations[-1]["id"]
    )
    find(ui.checkbox, "حذف لینک را تأیید می‌کنم؛ آمار قبلی حفظ می‌شود.").check().run()
    find(ui.button, "حذف لینک").click().run()
    assert not ui.exception and not ui.error
    assert client.get(f"/api/v1/links/{link['id']}", headers=admin).json()["status"] == "deleted"


def test_campaign_create_edit_and_archive(ui, client, admin):
    ui.run()
    navigate(ui, "کمپین‌ها")
    find(ui.text_input, "نام کمپین جدید").set_value("کمپین پاییز")
    find(ui.button, "ساخت کمپین").click().run()
    assert not ui.exception and not ui.error
    find(ui.text_input, "نام کمپین").set_value("کمپین زمستان")
    find(ui.checkbox, "کمپین بایگانی شود").check()
    find(ui.button, "ذخیره کمپین").click().run()
    assert not ui.exception and not ui.error
    campaign = client.get("/api/v1/campaigns", headers=admin).json()[0]
    assert campaign["name"] == "کمپین زمستان" and campaign["archived"]


def test_analytics_and_click_reports(ui, client, new_link):
    link = new_link(utm_source="instagram", utm_content="story", utm_term="autumn")
    client.get(f"/r/{link['slug']}", headers=HUMAN)
    ui.run()
    navigate(ui, "تحلیل ترافیک")
    assert not ui.error
    assert ui.metric[0].value == "1"
    assert len(ui.get("plotly_chart")) == 10
    find(ui.multiselect, "لینک‌های مقایسه (حداکثر ۱۰ مورد)").select(link["id"]).run()
    assert not ui.exception and not ui.error
    assert len(ui.get("plotly_chart")) == 11
    navigate(ui, "گزارش کلیک‌ها")
    assert not ui.error and len(ui.dataframe[0].value) == 1
    assert ui.dataframe[0].value.iloc[0]["منبع"] == "instagram"
    assert find(ui.button, "صفحه بعد").disabled


def test_dashboard_unavailable_api_is_graceful(monkeypatch):
    class Offline:
        def get(self, *args, **kwargs):
            raise ApiError("ارتباط با سرویس برقرار نشد.")

    monkeypatch.setattr(dashboard.app, "get_client", lambda: Offline())
    ui = AppTest.from_file(str(ROOT / "streamlit_app.py")).run()
    assert not ui.exception
    assert len(ui.error) == 1


def test_expiration_is_preserved_on_unrelated_edit(ui, new_link, client, admin):
    original = "2027-01-02T12:34:56.123456+00:00"
    link = new_link(expires_at=original)
    ui.run()
    navigate(ui, "لینک‌ها")
    find(ui.button, "ذخیره تغییرات").click().run()
    assert not ui.exception and not ui.error
    saved = client.get(f"/api/v1/links/{link['id']}", headers=admin).json()
    assert datetime.fromisoformat(saved["expires_at"]) == datetime.fromisoformat(original)


def test_click_report_paging_and_filter_reset(ui, new_link, client):
    link = new_link(slug="paged-clicks")
    for _ in range(101):
        client.get(f"/r/{link['slug']}", headers=HUMAN)
    ui.run()
    navigate(ui, "گزارش کلیک‌ها")
    assert len(ui.dataframe[0].value) == 100
    find(ui.button, "صفحه بعد").click().run()
    assert not ui.exception and not ui.error
    assert len(ui.dataframe[0].value) == 1
    find(ui.button, "صفحه قبل").click().run()
    assert len(ui.dataframe[0].value) == 100
    find(ui.selectbox, "لینک گزارش").select(link["id"]).run()
    assert not ui.exception and not ui.error
    assert find(ui.button, "صفحه قبل").disabled


def test_link_search_and_validation_are_visible(ui, new_link):
    new_link(slug="alpha-campaign")
    new_link(slug="beta-campaign")
    ui.run()
    navigate(ui, "لینک‌ها")
    ui.text_input(key="links_search").set_value("beta").run()
    assert not ui.exception and not ui.error
    assert len(ui.dataframe[0].value) == 1
    ui.text_input(key="new_destination").set_value("javascript:alert(1)")
    find(ui.button, "ساخت لینک").click().run()
    assert not ui.exception and ui.error
