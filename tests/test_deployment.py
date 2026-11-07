import json
import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from deploy.init_deployment import initialize
from deploy.runtime import SafeFormatter


def production(**overrides):
    return Settings(
        _env_file=None,
        app_env="production",
        public_base_url="https://go.company.org",
        dashboard_origin="https://panel.company.org",
        http_allowed_hosts="api,go.company.org,panel.company.org",
        trusted_proxy_cidrs="172.30.50.2/32",
        database_url="postgresql+psycopg://app:configured-test-password@db/linkspace",
        **overrides,
    )


def test_production_settings_require_https_exact_hosts_and_bounded_proxy_trust():
    assert production().app_env == "production"
    for values in (
        {"public_base_url": "http://go.company.org"},
        {"http_allowed_hosts": "*"},
        {"http_allowed_hosts": ""},
        {"trusted_proxy_cidrs": "0.0.0.0/0"},
        {"dashboard_origin": "https://panel.company.org/path"},
        {"public_base_url": "https://go.example.com"},
    ):
        defaults = {
            "database_url": "postgresql+psycopg://app:configured-test-password@db/linkspace",
            "public_base_url": "https://go.company.org",
            "dashboard_origin": "https://panel.company.org",
            "http_allowed_hosts": "api,go.company.org,panel.company.org",
        }
        defaults.update(values)
        with pytest.raises(ValidationError):
            Settings(_env_file=None, app_env="production", **defaults)


def test_secret_files_load_without_embedding_values_in_validation_errors(tmp_path, monkeypatch):
    path = tmp_path / "key"
    key = "file-only-secret-" + "x" * 40
    path.write_text(key)
    monkeypatch.delenv("ADMIN_API_KEY")
    monkeypatch.setenv("ADMIN_API_KEY_FILE", str(path))
    assert Settings(_env_file=None).admin_api_key.get_secret_value() == key
    monkeypatch.setenv("ADMIN_API_KEY", "ambiguous-inline-secret")
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)
    assert key not in str(error.value) and "ambiguous-inline-secret" not in str(error.value)


def test_trusted_host_and_scheme_forwarding_preserve_physical_peer(client, monkeypatch, new_link):
    from app.tracking import collect_metadata

    seen = []

    def capture(request, now):
        seen.append((request.url.scheme, request.client.host))
        return collect_metadata(request, now)

    monkeypatch.setattr("app.main.collect_metadata", capture)
    monkeypatch.setenv("HTTP_ALLOWED_HOSTS", "testserver,api")
    get_settings.cache_clear()
    assert client.get("/health/live").status_code == 200
    assert (
        client.get(
            "/health/live", headers={"Host": "evil.invalid", "X-Forwarded-Host": "testserver"}
        ).status_code
        == 400
    )
    link = new_link()
    assert (
        client.get("/r/" + link["slug"], headers={"X-Forwarded-Proto": "https"}).status_code == 302
    )
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "203.0.113.10/32")
    get_settings.cache_clear()
    assert (
        client.get("/r/" + link["slug"], headers={"X-Forwarded-Proto": "https"}).status_code == 302
    )
    assert seen == [("http", "203.0.113.10"), ("https", "203.0.113.10")]


def test_dashboard_origin_cannot_be_approved_for_root_redirects(client, admin, monkeypatch):
    monkeypatch.setenv("DASHBOARD_ORIGIN", "http://panel.localhost:8000")
    monkeypatch.setenv("LINKSPACE_ROOT_ORIGINS", "http://panel.localhost:8000")
    get_settings.cache_clear()
    response = client.post(
        "/api/v1/linkspaces",
        headers=admin,
        json={
            "name": "Unsafe shared root",
            "base_url": "http://panel.localhost:8000",
            "path_prefix": "",
        },
    )
    assert response.status_code == 422


def test_sanitized_logging_omits_exception_messages_and_unrecognized_payloads():
    record = logging.LogRecord(
        "uvicorn.error",
        logging.ERROR,
        "",
        0,
        "SECRET bearer and query data",
        (),
        (ValueError, ValueError("PRIVATE"), None),
    )
    rendered = SafeFormatter().format(record)
    assert "SECRET" not in rendered and "PRIVATE" not in rendered
    assert json.loads(rendered)["error_type"] == "ValueError"
    for payload in ({"password": "SECRET"}, "invalid format %s %s"):
        record.msg = payload
        record.args = ("PRIVATE",) if isinstance(payload, str) else ()
        record.exc_info = (None, None, None)
        rendered = SafeFormatter().format(record)
        assert "SECRET" not in rendered and "PRIVATE" not in rendered


def test_initializer_preserves_env_and_secret_files(tmp_path):
    original = tmp_path / ".env"
    original.write_text("PRIVATE_EXISTING_CONFIGURATION")
    output = initialize(
        tmp_path,
        mode="simulation",
        env_name=".env.simulation",
        project="test-sim",
        port=8088,
        subnet="172.30.60.0/24",
        database="linkspace",
    )
    assert original.read_text() == "PRIVATE_EXISTING_CONFIGURATION"
    directory = tmp_path / ".local/deployment/test-sim/secrets"
    values = {p.name: p.read_text() for p in directory.iterdir()}
    assert len(set(values.values())) == len(values)
    assert "PRIVATE_EXISTING" not in output.read_text()
    assert all(value.strip() not in output.read_text() for value in values.values())
    with pytest.raises(FileExistsError):
        initialize(
            tmp_path,
            mode="simulation",
            env_name=".env.simulation",
            project="test-sim",
            port=8088,
            subnet="172.30.60.0/24",
            database="linkspace",
        )
    assert values == {p.name: p.read_text() for p in directory.iterdir()}
    assert Path(output).is_file()
