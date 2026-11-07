import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

# Tests never fall back to the application's database or keys.
TEST_URL = os.environ.get("TEST_DATABASE_URL")
os.environ["ADMIN_API_KEY"] = "test-admin-" + "a" * 40
os.environ["REPORT_API_KEY"] = "test-report-" + "b" * 40
os.environ["VISITOR_HMAC_KEY"] = "test-visitor-" + "c" * 40
os.environ["TRUSTED_PROXY_CIDRS"] = ""
os.environ["COUNTRY_HEADER"] = ""
os.environ["DESTINATION_ALLOWED_HOSTS"] = ""
os.environ["PUBLIC_BASE_URL"] = "http://127.0.0.1:8000"
os.environ["LINKSPACE_ROUTED_ORIGINS"] = ""
os.environ["LINKSPACE_ROOT_ORIGINS"] = ""
if TEST_URL:
    os.environ["DATABASE_URL"] = TEST_URL

from app.config import get_settings  # noqa: E402
from app.db import get_engine  # noqa: E402
from app.links import link_cache  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def database():
    if not TEST_URL:
        pytest.fail(
            "Set TEST_DATABASE_URL to a disposable PostgreSQL database; tests truncate its tables"
        )
    if "test" not in TEST_URL.rsplit("/", 1)[-1]:
        pytest.fail("Test database name must contain 'test'")
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(TEST_URL)
    yield engine
    engine.dispose()
    get_engine().dispose()


@pytest.fixture
def client(database):
    with database.begin() as connection:
        connection.execute(
            text("""TRUNCATE campaigns, links, link_destinations, click_events,
            daily_link_stats, daily_campaign_stats, audit_events, aggregation_state, linkspaces CASCADE""")
        )
        connection.execute(
            text("""INSERT INTO linkspaces
            (id, name, base_url, path_prefix, is_active, is_default)
            VALUES ('00000000-0000-0000-0000-000000000003', 'Original links',
            'http://127.0.0.1:8000', 'r', true, true)""")
        )
    with link_cache.lock:
        link_cache.data.clear()
    with TestClient(app, client=("203.0.113.10", 50000), follow_redirects=False) as value:
        yield value
    get_settings.cache_clear()


@pytest.fixture
def admin():
    return {"Authorization": "Bearer " + os.environ["ADMIN_API_KEY"]}


@pytest.fixture
def report():
    return {"Authorization": "Bearer " + os.environ["REPORT_API_KEY"]}


@pytest.fixture
def new_link(client, admin):
    def create(**overrides):
        response = client.post(
            "/api/v1/links",
            headers=admin,
            json={"destination_url": "https://example.com/path?a=1%2F2#part", **overrides},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return create
