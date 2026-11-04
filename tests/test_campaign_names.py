import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def test_campaign_names_trim_and_reject_duplicates(client, admin):
    created = client.post("/api/v1/campaigns", headers=admin, json={"name": "  Launch  "})
    assert created.status_code == 201
    assert created.json()["name"] == "Launch"
    for name in ("launch", " LAUNCH ", "\tlaunch\n", "\u00a0Launch\u00a0"):
        response = client.post("/api/v1/campaigns", headers=admin, json={"name": name})
        assert response.status_code == 409
    assert len(client.get("/api/v1/campaigns", headers=admin).json()) == 1
    for name in ("", " ", "\t\n", "\u00a0"):
        assert (
            client.post("/api/v1/campaigns", headers=admin, json={"name": name}).status_code == 422
        )


def test_concurrent_campaign_creation_is_unique(client, admin):
    names = [" Autumn ", "autumn", "AUTUMN", "Autumn"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(
            pool.map(
                lambda name: (
                    client.post("/api/v1/campaigns", headers=admin, json={"name": name}).status_code
                ),
                names,
            )
        )
    assert sorted(statuses) == [201, 409, 409, 409]


def test_campaign_rename_conflict_preserves_original(client, admin):
    first = client.post("/api/v1/campaigns", headers=admin, json={"name": "First"}).json()
    second = client.post("/api/v1/campaigns", headers=admin, json={"name": "Second"}).json()
    assert (
        client.patch(
            f"/api/v1/campaigns/{second['id']}", headers=admin, json={"name": " first "}
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/campaigns/{first['id']}", headers=admin, json={"name": " FIRST "}
        ).status_code
        == 200
    )
    names = [row["name"] for row in client.get("/api/v1/campaigns", headers=admin).json()]
    assert "Second" in names
    assert (
        client.patch(
            f"/api/v1/campaigns/{first['id']}", headers=admin, json={"name": " "}
        ).status_code
        == 422
    )


def test_database_enforces_campaign_name_index(client, database):
    with database.begin() as connection:
        connection.execute(
            text("INSERT INTO campaigns(id,name,archived) VALUES (:id,'Campaign',false)"),
            {"id": uuid.uuid4()},
        )
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(
            text("INSERT INTO campaigns(id,name,archived) VALUES (:id,:name,false)"),
            {"id": uuid.uuid4(), "name": "\u00a0 CAMPAIGN \t"},
        )


def test_recent_campaigns_search_sort_and_link_counts(client, admin, new_link):
    first = client.post("/api/v1/campaigns", headers=admin, json={"name": "First autumn"}).json()
    second = client.post("/api/v1/campaigns", headers=admin, json={"name": "Second autumn"}).json()
    new_link(campaign_id=first["id"])
    deleted = new_link(campaign_id=first["id"])
    client.delete(f"/api/v1/links/{deleted['id']}", headers=admin)
    page = client.get(
        "/api/v1/campaigns",
        headers=admin,
        params={
            "q": "AUTUM",
            "descending": True,
            "include_total": True,
            "with_link_count": True,
            "limit": 1,
        },
    )
    assert page.headers["X-Total-Count"] == "2"
    assert page.json()[0]["id"] == second["id"]
    assert page.json()[0]["link_count"] == 0
    sorted_page = client.get(
        "/api/v1/campaigns",
        headers=admin,
        params={"sort_by": "link_count", "descending": True, "with_link_count": True},
    ).json()
    assert sorted_page[0]["id"] == first["id"] and sorted_page[0]["link_count"] == 1


@pytest.mark.parametrize("names", [(" Legacy ", "legacy"), (" \t",)])
def test_migration_stops_on_existing_duplicates_without_data_loss(client, database, names):
    config = Config("alembic.ini")
    command.downgrade(config, "0001")
    try:
        with database.begin() as connection:
            for name in names:
                connection.execute(
                    text("INSERT INTO campaigns(id,name,archived) VALUES (:id,:name,false)"),
                    {"id": uuid.uuid4(), "name": name},
                )
        with pytest.raises(RuntimeError, match="No data was changed"):
            command.upgrade(config, "head")
        with database.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM campaigns")) == len(names)
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001"
    finally:
        with database.begin() as connection:
            connection.execute(text("DELETE FROM campaigns"))
        command.upgrade(config, "head")
