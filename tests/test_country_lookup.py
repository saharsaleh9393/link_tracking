from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.config import get_settings
from app.country import country_lookup
from app.models import ClickEvent
from app.tracking import collect_metadata

FIXTURE = Path(__file__).parent / "data" / "GeoIP2-Country-Test.mmdb"


@pytest.fixture
def geoip(monkeypatch):
    monkeypatch.setenv("GEOIP_DATABASE_PATH", str(FIXTURE))
    get_settings.cache_clear()
    country_lookup.close()
    yield
    country_lookup.close()
    get_settings.cache_clear()


def test_real_mmdb_country_lookup_and_private_addresses(geoip):
    assert country_lookup.available()
    assert country_lookup.lookup("81.2.69.160") == "GB"
    assert country_lookup.lookup("89.160.20.128") == "SE"
    assert country_lookup.lookup("::ffff:81.2.69.160") == "GB"
    for address in (
        None,
        "invalid",
        "127.0.0.1",
        "10.0.0.1",
        "192.168.1.1",
        "::1",
        "203.0.113.10",
        "224.0.0.1",
    ):
        assert country_lookup.lookup(address) is None


def test_country_is_recorded_only_from_real_or_trusted_client_ip(
    client, new_link, geoip, monkeypatch, database
):
    link = new_link()
    client.get(f"/r/{link['slug']}", headers={"X-Forwarded-For": "81.2.69.160"})
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "203.0.113.0/24")
    get_settings.cache_clear()
    client.get(f"/r/{link['slug']}", headers={"X-Forwarded-For": "81.2.69.160"})
    with Session(database) as session:
        countries = session.scalars(
            select(ClickEvent.country).order_by(ClickEvent.occurred_at)
        ).all()
        assert countries == [None, "GB"]


def test_trusted_header_precedence_and_fallback(geoip, monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "127.0.0.1/32")
    monkeypatch.setenv("COUNTRY_HEADER", "cf-ipcountry")
    get_settings.cache_clear()

    def request(code):
        return Request(
            {
                "type": "http",
                "client": ("127.0.0.1", 1),
                "headers": [(b"x-forwarded-for", b"81.2.69.160"), (b"cf-ipcountry", code.encode())],
            }
        )

    assert collect_metadata(request("IR"), datetime.now(UTC))["country"] == "IR"
    assert collect_metadata(request("XX"), datetime.now(UTC))["country"] == "GB"


def test_missing_or_invalid_mmdb_never_breaks_tracking(geoip, monkeypatch, tmp_path):
    bad = tmp_path / "bad.mmdb"
    for present in (False, True):
        if present:
            bad.write_bytes(b"not an MMDB")
        monkeypatch.setenv("GEOIP_DATABASE_PATH", str(bad))
        get_settings.cache_clear()
        country_lookup.close()
        assert not country_lookup.available()
        assert country_lookup.lookup("81.2.69.160") is None
