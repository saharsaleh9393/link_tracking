import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.linkspace_config import normalize_base

DEFAULT_ID = "00000000-0000-0000-0000-000000000003"


def create_space(client, admin, **overrides):
    response = client.post(
        "/api/v1/linkspaces",
        headers=admin,
        json={
            "name": "Local go",
            "base_url": "http://127.0.0.1:8000",
            "path_prefix": "go",
            **overrides,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def update_space(client, admin, space, **overrides):
    body = {
        key: space[key] for key in ("name", "base_url", "path_prefix", "is_active", "is_default")
    }
    return client.put(
        f"/api/v1/linkspaces/{space['id']}", headers=admin, json={**body, **overrides}
    )


def test_snapshots_preserve_urls_redirects_clicks_and_read_only_catalog(
    client, admin, report, new_link, database
):
    old = new_link(slug="legacy")
    assert old["tracking_url"] == "http://127.0.0.1:8000/r/legacy"
    space = create_space(client, admin, is_default=True)
    selected = new_link(slug="fresh", utm_source="instagram")
    assert selected["linkspace_id"] == space["id"]
    assert selected["tracking_url"] == "http://127.0.0.1:8000/go/fresh"
    assert update_space(client, admin, space, path_prefix="visit").status_code == 200
    assert new_link(slug="newer")["tracking_url"].endswith("/visit/newer")
    for link in (old, selected):
        row = client.get(f"/api/v1/links/{link['id']}", headers=admin).json()
        assert row["tracking_url"] == link["tracking_url"]
        assert client.get(link["tracking_url"]).status_code == 302
        assert client.head(link["tracking_url"]).status_code == 302
        assert client.get(f"/r/{link['slug']}").status_code == 302
    assert client.get("http://127.0.0.1:8000/visit/fresh").status_code == 404
    assert client.get("http://other.example/go/fresh").status_code == 404
    assert (
        client.get("/go/fresh", headers={"X-Forwarded-Host": "127.0.0.1:8000"}).status_code == 404
    )
    assert client.get("/api/v1/reporting/links", headers=report).json()["items"]
    catalog = client.get("/api/v1/reporting/links", headers=report).json()["items"]
    assert (
        next(row for row in catalog if row["id"] == selected["id"])["tracking_url"]
        == selected["tracking_url"]
    )
    with database.connect() as connection:
        # Only the two GETs per link count; HEADs, wrong hosts and wrong prefixes do not.
        assert connection.scalar(text("SELECT count(*) FROM click_events")) == 4


def test_explicit_selection_activation_and_deletion_rules(client, admin, new_link):
    space = create_space(client, admin)
    link = new_link(linkspace_id=space["id"])
    assert link["tracking_url"].split("/")[-2] == "go"
    assert client.delete(f"/api/v1/linkspaces/{space['id']}", headers=admin).status_code == 409
    assert update_space(client, admin, space, is_active=False).status_code == 200
    rejected = client.post(
        "/api/v1/links",
        headers=admin,
        json={"destination_url": "https://example.com", "linkspace_id": space["id"]},
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "LINKSPACE_UNAVAILABLE"
    assert client.get(link["tracking_url"]).status_code == 302
    assert client.delete(f"/api/v1/links/{link['id']}", headers=admin).status_code == 204
    assert client.delete(f"/api/v1/linkspaces/{space['id']}", headers=admin).status_code == 409
    unused = create_space(client, admin, path_prefix="unused")
    assert client.delete(f"/api/v1/linkspaces/{unused['id']}", headers=admin).status_code == 204
    assert client.delete(f"/api/v1/linkspaces/{DEFAULT_ID}", headers=admin).status_code == 409
    original = client.get("/api/v1/linkspaces", headers=admin).json()[0]
    assert update_space(client, admin, original, is_active=False).status_code == 422
    assert update_space(client, admin, original, is_default=False).status_code == 409


def test_duplicate_normalized_configuration_and_concurrent_defaults(client, admin, database):
    first = create_space(client, admin, base_url="https://GO.Example.com:443/", path_prefix="/GO/")
    assert first["base_url"] == "https://go.example.com" and first["path_prefix"] == "go"
    assert first["configuration_status"] == "pending_configuration"
    duplicate = client.post(
        "/api/v1/linkspaces",
        headers=admin,
        json={
            "name": "Another",
            "base_url": "https://go.example.com",
            "path_prefix": "go",
            "is_default": True,
        },
    )
    assert duplicate.status_code == 409
    assert (
        sum(row["is_default"] for row in client.get("/api/v1/linkspaces", headers=admin).json())
        == 1
    )
    second = create_space(client, admin, path_prefix="launch")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda space: update_space(client, admin, space, is_default=True).status_code,
                (first, second),
            )
        )
    assert results == [200, 200]
    with database.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM linkspaces WHERE is_default")) == 1
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO linkspaces(id,name,base_url,path_prefix,is_active,is_default) VALUES (:id,'DB constraint','https://another.example','go',true,true)"
            ),
            {"id": uuid.uuid4()},
        )


@pytest.mark.parametrize(
    "base",
    [
        "javascript:alert(1)",
        "//example.com",
        "https://user:pass@example.com",
        "https://example.com/path",
        "https://example.com?token=secret",
        "https://example.com#fragment",
        "https://*.example.com",
        "https://bad_domain.example",
        "https://example.com:65536",
        "https://example.com:0",
        "https://example.com:",
        "https://example.com\\evil",
        "https://example.com%2f.evil",
        "http://example.com",
        "https://example.com/../",
        "https://example.com.",
    ],
)
def test_invalid_origins_rejected(client, admin, base):
    response = client.post(
        "/api/v1/linkspaces", headers=admin, json={"name": "Invalid", "base_url": base}
    )
    assert response.status_code == 422
    assert "secret" not in response.text


@pytest.mark.parametrize(
    "prefix",
    ["api", "API", "settings", "login", "health", "docs", "_next", "go/next", "..", "%72", "r?x=1"],
)
def test_reserved_and_invalid_prefixes(client, admin, prefix):
    assert (
        client.post(
            "/api/v1/linkspaces",
            headers=admin,
            json={"name": "Invalid", "base_url": "https://example.com", "path_prefix": prefix},
        ).status_code
        == 422
    )


def test_root_requires_operator_approval_and_preserves_reserved_routes(
    client, admin, monkeypatch, new_link
):
    body = {"name": "Root links", "base_url": "https://short.example.com", "path_prefix": ""}
    denied = client.post("/api/v1/linkspaces", headers=admin, json=body)
    assert denied.status_code == 422 and denied.json()["detail"]["code"] == "LINKSPACE_ROOT_UNSAFE"
    monkeypatch.setenv("LINKSPACE_ROOT_ORIGINS", "https://short.example.com")
    get_settings.cache_clear()
    root = create_space(client, admin, **body)
    assert root["preview_url"] == "https://short.example.com/slug"
    assert root["configuration_status"] == "pending_configuration"
    link = new_link(slug="root-link", linkspace_id=root["id"])
    assert link["tracking_url"] == "https://short.example.com/root-link"
    assert client.get(link["tracking_url"]).status_code == 302
    assert client.get("/root-link").status_code == 404
    for slug in ("api", "login", "settings", "_next"):
        rejected = client.post(
            "/api/v1/links",
            headers=admin,
            json={
                "slug": slug,
                "destination_url": "https://example.com",
                "linkspace_id": root["id"],
            },
        )
        assert rejected.status_code == 422
    assert client.get("https://short.example.com/health/live").json() == {"status": "ok"}
    monkeypatch.setenv("LINKSPACE_ROUTED_ORIGINS", "https://short.example.com")
    get_settings.cache_clear()
    page = client.get("/api/v1/linkspaces", headers=admin).json()
    assert (
        next(row for row in page if row["id"] == root["id"])["configuration_status"]
        == "operator_configured"
    )
    monkeypatch.setenv("LINKSPACE_ROOT_ORIGINS", "")
    get_settings.cache_clear()
    assert client.get(link["tracking_url"]).status_code == 404
    assert client.get("/r/root-link").status_code == 302


def test_linkspace_permissions_and_pagination(client, admin, report):
    assert client.get("/api/v1/linkspaces").status_code == 401
    assert client.get("/api/v1/linkspaces", headers=report).status_code == 401
    create_space(client, admin)
    page = client.get(
        "/api/v1/linkspaces", headers=admin, params={"limit": 1, "include_total": True}
    )
    assert page.headers["X-Total-Count"] == "2"
    assert page.json()[0]["is_default"]
    assert (
        client.get("/api/v1/linkspaces", headers=admin, params={"q": "LOCAL"}).json()[0]["name"]
        == "Local go"
    )
    assert client.get("/api/v1/linkspaces", headers=admin, params={"q": "%"}).json() == []


def test_migration_backfills_legacy_urls_without_changing_clicks(client, admin, new_link, database):
    link = new_link(slug="migration-legacy")
    client.get("/r/migration-legacy")
    config = Config("alembic.ini")
    command.downgrade(config, "0002")
    try:
        command.upgrade(config, "head")
        with database.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT tracking_base_url,tracking_path_prefix,linkspace_id FROM links WHERE id=:id"
                ),
                {"id": link["id"]},
            ).one()
            assert (
                row.tracking_base_url == "http://127.0.0.1:8000" and row.tracking_path_prefix == "r"
            )
            assert row.linkspace_id is not None
            assert connection.scalar(text("SELECT count(*) FROM click_events")) == 1
            assert connection.scalar(text("SELECT count(*) FROM linkspaces WHERE is_default")) == 1
        assert (
            client.get(f"/api/v1/links/{link['id']}", headers=admin).json()["tracking_url"]
            == link["tracking_url"]
        )
        assert client.get("/r/migration-legacy").status_code == 302
    finally:
        command.upgrade(config, "head")


def test_origin_normalization_supports_idn_and_loopback():
    assert normalize_base("http://LOCALHOST:8000/") == "http://localhost:8000"
    assert normalize_base("http://[::1]:8000") == "http://[::1]:8000"
    assert normalize_base("https://مثال.ir") == "https://xn--mgbh0fb.ir"


def test_concurrent_duplicate_configurations_do_not_remove_default(client, admin):
    def create(base):
        return client.post(
            "/api/v1/linkspaces",
            headers=admin,
            json={
                "name": "Race",
                "base_url": base,
                "path_prefix": "go",
                "is_default": True,
            },
        ).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(
            pool.map(
                create,
                [
                    "https://go.example.com",
                    "https://GO.EXAMPLE.COM/",
                    "https://go.example.com:443",
                    "https://go.example.com",
                ],
            )
        )
    assert sorted(statuses) == [201, 409, 409, 409]
    assert (
        sum(space["is_default"] for space in client.get("/api/v1/linkspaces", headers=admin).json())
        == 1
    )


def test_root_auto_slugs_and_snapshot_survives_environment_change(
    client, admin, new_link, monkeypatch
):
    monkeypatch.setenv("LINKSPACE_ROOT_ORIGINS", "http://127.0.0.1:8000")
    get_settings.cache_clear()
    space = create_space(client, admin, path_prefix="", is_default=True)
    monkeypatch.setattr("app.links.secrets.token_urlsafe", lambda _: "_abcdefghijk")
    link = new_link()
    assert link["linkspace_id"] == space["id"]
    assert client.get(link["tracking_url"]).status_code == 302
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://new.example.com")
    get_settings.cache_clear()
    assert (
        client.get(f"/api/v1/links/{link['id']}", headers=admin).json()["tracking_url"]
        == link["tracking_url"]
    )


def test_downgrade_refuses_to_discard_custom_origins(client, admin, new_link, database):
    space = create_space(client, admin, base_url="https://custom.example.com", path_prefix="r")
    link = new_link(linkspace_id=space["id"])
    with pytest.raises(RuntimeError, match="discard custom URLs"):
        command.downgrade(Config("alembic.ini"), "0002")
    with database.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
    assert (
        client.get(f"/api/v1/links/{link['id']}", headers=admin).json()["tracking_url"]
        == link["tracking_url"]
    )


def test_migration_normalizes_seeded_configuration_for_uniqueness(client, admin, monkeypatch):
    config = Config("alembic.ini")
    command.downgrade(config, "0002")
    try:
        monkeypatch.setenv("PUBLIC_BASE_URL", "https://EXAMPLE.COM:443/")
        get_settings.cache_clear()
        command.upgrade(config, "head")
        original = client.get("/api/v1/linkspaces", headers=admin).json()[0]
        assert original["base_url"] == "https://example.com"
        duplicate = client.post(
            "/api/v1/linkspaces",
            headers=admin,
            json={
                "name": "Duplicate original",
                "base_url": "https://example.com",
                "path_prefix": "r",
            },
        )
        assert duplicate.status_code == 409
    finally:
        command.upgrade(config, "head")


def test_localhost_subdomain_demo_works_across_campaigns_without_root_env(
    client, admin, new_link, database
):
    space = create_space(
        client,
        admin,
        name="Local demo",
        base_url="http://go.localhost:8000",
        path_prefix="",
        is_default=True,
    )
    assert space["configuration_status"] == "local_development"
    assert space["preview_url"] == "http://go.localhost:8000/slug"
    for name in ("Campaign A", "Campaign B"):
        campaign = client.post("/api/v1/campaigns", headers=admin, json={"name": name}).json()
        link = new_link(campaign_id=campaign["id"])
        assert link["linkspace_id"] == space["id"]
        assert link["tracking_url"] == "http://go.localhost:8000/" + link["slug"]
        assert client.get(link["tracking_url"]).status_code == 302
        assert client.head(link["tracking_url"]).status_code == 302
        assert client.get("http://other.localhost:8000/" + link["slug"]).status_code == 404
        assert client.get("http://go.localhost:3000/" + link["slug"]).status_code == 404
    with database.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM click_events")) == 2
    assert client.get("http://go.localhost:8000/health/live").json() == {"status": "ok"}
    reserved = client.post(
        "/api/v1/links",
        headers=admin,
        json={"slug": "settings", "destination_url": "https://example.com"},
    )
    assert reserved.status_code == 422
    assert reserved.json()["detail"]["code"] == "LINKSPACE_RESERVED_SLUG"


@pytest.mark.parametrize(
    "base",
    [
        "http://go.localhost:3000",
        "https://go.localhost:8000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://go.example.com",
    ],
)
def test_demo_root_approval_does_not_extend_to_other_origins(client, admin, base):
    response = client.post(
        "/api/v1/linkspaces",
        headers=admin,
        json={"name": "Unsafe root", "base_url": base, "path_prefix": ""},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "LINKSPACE_ROOT_UNSAFE"


@pytest.mark.parametrize(
    "public_base", ["https://go.example.com", "http://127.0.0.1:8001", "http://192.168.1.5:8000"]
)
def test_local_demo_auto_approval_is_off_outside_local_api_origin(
    client, admin, monkeypatch, public_base
):
    monkeypatch.setenv("PUBLIC_BASE_URL", public_base)
    get_settings.cache_clear()
    response = client.post(
        "/api/v1/linkspaces",
        headers=admin,
        json={"name": "Local demo", "base_url": "http://go.localhost:8000", "path_prefix": ""},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "LINKSPACE_ROOT_UNSAFE"


@pytest.mark.parametrize(
    "base",
    [
        "http://go.localhost.evil.com:8000",
        "http://notlocalhost:8000",
        "http://bad_name.localhost:8000",
        "http://a..localhost:8000",
        "http://go.localhost:8000/slug",
    ],
)
def test_demo_hostname_validation_cannot_be_bypassed(client, admin, base):
    assert (
        client.post(
            "/api/v1/linkspaces",
            headers=admin,
            json={"name": "Invalid demo", "base_url": base, "path_prefix": "r"},
        ).status_code
        == 422
    )


def test_localhost_subdomain_normalization():
    assert normalize_base("HTTP://GO.LOCALHOST:8000/") == "http://go.localhost:8000"
