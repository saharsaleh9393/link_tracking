import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.config import get_settings


def attempt(client, admin, identity="a", valid=False, token="session"):
    body = {"client_key": hashlib.sha256(identity.encode()).hexdigest(), "credentials_valid": valid}
    if valid:
        body.update(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=(datetime.now(UTC) + timedelta(hours=8)).isoformat(),
        )
    return client.post("/api/v1/dashboard-auth/login", headers=admin, json=body)


def test_shared_session_creation_validation_revocation_expiry(client, admin, database):
    assert attempt(client, admin, valid=True).status_code == 200
    body = {"token_hash": hashlib.sha256(b"session").hexdigest()}
    assert client.post("/api/v1/dashboard-auth/validate", headers=admin, json=body).json() == {
        "valid": True
    }
    assert client.post("/api/v1/dashboard-auth/revoke", headers=admin, json=body).status_code == 200
    assert client.post("/api/v1/dashboard-auth/validate", headers=admin, json=body).json() == {
        "valid": False
    }
    assert attempt(client, admin, valid=True, token="expiring").status_code == 200
    with database.begin() as connection:
        connection.execute(
            text("UPDATE dashboard_sessions SET expires_at=now()-interval '1 second'")
        )
    assert client.post(
        "/api/v1/dashboard-auth/validate",
        headers=admin,
        json={"token_hash": hashlib.sha256(b"expiring").hexdigest()},
    ).json() == {"valid": False}


def test_shared_rate_limit_is_atomic_and_clients_are_isolated(client, admin, monkeypatch):
    monkeypatch.setenv("DASHBOARD_LOGIN_CLIENT_LIMIT", "3")
    get_settings.cache_clear()
    with ThreadPoolExecutor(max_workers=6) as pool:
        statuses = list(pool.map(lambda _: attempt(client, admin).status_code, range(8)))
    assert statuses.count(401) == 3 and statuses.count(429) == 5
    blocked = attempt(client, admin, valid=True)
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) >= 1
    assert attempt(client, admin, identity="different", valid=True).status_code == 200


def test_account_limit_applies_across_clients_without_creating_unbounded_buckets(
    client, admin, monkeypatch, database
):
    monkeypatch.setenv("DASHBOARD_LOGIN_ACCOUNT_LIMIT", "3")
    get_settings.cache_clear()
    for index in range(3):
        assert attempt(client, admin, identity=str(index)).status_code == 401
    for index in range(20):
        assert attempt(client, admin, identity="blocked-" + str(index)).status_code == 429
    with database.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM dashboard_login_buckets")) == 4


def test_expired_limit_state_is_reclaimed_without_resetting_active_sessions(
    client, admin, database
):
    assert attempt(client, admin, valid=True).status_code == 200
    with database.begin() as connection:
        connection.execute(
            text("UPDATE dashboard_login_buckets SET resets_at=now()-interval '1 second'")
        )
    assert attempt(client, admin, identity="new").status_code == 401
    with database.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM dashboard_login_buckets")) == 2
        assert connection.scalar(text("SELECT count(*) FROM dashboard_sessions")) == 1


def test_private_auth_store_rejects_missing_or_report_credentials_and_invalid_bodies(
    client, admin, report
):
    assert (
        client.post("/api/v1/dashboard-auth/validate", json={"token_hash": "a" * 64}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/dashboard-auth/validate", headers=report, json={"token_hash": "a" * 64}
        ).status_code
        == 401
    )
    for body in ({}, {"token_hash": "raw-cookie"}, {"token_hash": "a" * 64, "extra": "field"}):
        assert (
            client.post("/api/v1/dashboard-auth/validate", headers=admin, json=body).status_code
            == 422
        )
    assert (
        client.post(
            "/api/v1/dashboard-auth/login",
            headers=admin,
            json={"client_key": "b" * 64, "credentials_valid": True},
        ).status_code
        == 422
    )
