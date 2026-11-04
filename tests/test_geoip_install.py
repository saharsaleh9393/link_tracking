import gzip
import io
from pathlib import Path

import maxminddb
import pytest

from scripts.install_geoip import install


def test_installer_validates_country_database_and_preserves_existing_files(monkeypatch, tmp_path):
    fixture = Path(__file__).parent / "data" / "GeoIP2-Country-Test.mmdb"
    compressed = gzip.compress(fixture.read_bytes())
    calls = []

    def download(url, timeout):
        calls.append(url)
        response = io.BytesIO(compressed)
        response.url = url
        return response

    monkeypatch.setattr("scripts.install_geoip.urlopen", download)
    target = tmp_path / "country.mmdb"
    install("2026-11", target)
    with maxminddb.open_database(str(target)) as reader:
        assert reader.get("81.2.69.160")["country"]["iso_code"] == "GB"
    assert target.with_suffix(".source.json").exists()
    install("2026-11", target)
    assert len(calls) == 1
    original = target.read_bytes()
    compressed = gzip.compress(b"invalid database")
    with pytest.raises(maxminddb.InvalidDatabaseError):
        install("2026-11", target, update=True)
    assert target.read_bytes() == original


def test_installer_rejects_invalid_release(tmp_path):
    with pytest.raises(ValueError):
        install("../../other-host", tmp_path / "country.mmdb")
