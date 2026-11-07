"""Run tests only in new databases on the isolated security-test PostgreSQL cluster."""

import argparse
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Running as a script must resolve the repository packages without requiring installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.models import Campaign, ClickEvent, Destination, Link  # noqa: E402
from deploy.smoke import read_env  # noqa: E402


def main(env_path, database_host="127.0.0.1", database_port=55439, container=False, test_root=None):
    config = read_env(env_path)
    project = config["COMPOSE_PROJECT_NAME"]
    if not project.startswith("linkspace-security") or not config["POSTGRES_DB"].startswith(
        "security_test"
    ):
        raise ValueError("Refusing a non-security project")
    directory = env_path.parent / config["SECRETS_DIRECTORY"]
    owner = (
        (directory / "owner_database_url")
        .read_text()
        .strip()
        .rsplit("/", 1)[0]
        .replace("@db:5432", f"@{database_host}:{database_port}")
    )
    command = [
        "docker",
        "compose",
        "-p",
        project,
        "--env-file",
        str(env_path),
        "-f",
        "compose.production.yaml",
        "-f",
        "compose.simulation.yaml",
        "-f",
        "compose.security-test.yaml",
    ]
    environment = {key: value for key, value in os.environ.items() if key not in config}

    def new_database(label):
        name = "security_test_" + label + "_" + uuid.uuid4().hex[:12]
        subprocess.run(
            [
                *command,
                "exec",
                "-T",
                "db",
                "createdb",
                "-U",
                "postgres",
                "-O",
                "linkspace_owner",
                name,
            ],
            check=True,
            env=environment,
        )
        return name

    def env_for(name):
        result = {
            **environment,
            "APP_ENV": "development",
            "DATABASE_URL": owner + "/" + name,
            "PUBLIC_BASE_URL": "http://127.0.0.1:8000",
        }
        result.pop("DATABASE_URL_FILE", None)
        for key in ("ADMIN_API_KEY", "REPORT_API_KEY", "VISITOR_HMAC_KEY"):
            result.pop(key, None)
            result[key + "_FILE"] = str(directory / key.lower())
        return result

    upgrade = new_database("upgrade")
    unit = new_database("unit")
    if container:
        subprocess.run(
            [
                *command,
                "--profile",
                "ops",
                "run",
                "--rm",
                "--no-deps",
                "--user",
                "0:0",
                "-v",
                f"{test_root or Path.cwd()}:/tests:ro",
                "-e",
                "PYTHONPATH=/tests/.venv/lib/python3.12/site-packages",
                "-w",
                "/tests",
                "--entrypoint",
                "python",
                "migrate",
                "tests/security/run_backend.py",
                "--inside-container",
                upgrade,
                unit,
            ],
            check=True,
            env=environment,
        )
        return
    run_databases(owner, upgrade, unit, env_for)


def run_databases(owner, upgrade, unit, env_for):
    upgrade_env = env_for(upgrade)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0003"], check=True, env=upgrade_env
    )
    engine = create_engine(owner + "/" + upgrade, hide_parameters=True)
    link_id, dest_id, campaign_id, click_id = [uuid.uuid4() for _ in range(4)]
    with Session(engine) as session:
        session.add(Campaign(id=campaign_id, name="Isolated security upgrade fixture"))
        session.flush()
        session.add(
            Link(
                id=link_id,
                slug="security-upgrade-fixture",
                campaign_id=campaign_id,
                status="active",
                active_destination_id=dest_id,
                tracking_base_url="http://go.localhost:8090",
                tracking_path_prefix="r",
            )
        )
        session.flush()
        session.add(
            Destination(
                id=dest_id,
                link_id=link_id,
                url="https://example.com/fixture?signature=a%2Fb",
                version=1,
            )
        )
        session.add(
            ClickEvent(
                occurred_at=datetime.now(UTC),
                click_id=click_id,
                link_id=link_id,
                campaign_id=campaign_id,
                destination_id=dest_id,
                link_version=1,
                device="desktop",
                os="Test",
                browser="Test",
                classification="human",
            )
        )
        session.commit()

    def snapshots():
        with engine.connect() as connection:
            return {
                table: connection.scalars(text(f"SELECT row_to_json(t)::text FROM {table} t")).all()
                for table in ("campaigns", "links", "link_destinations", "click_events")
            }

    before = snapshots()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=upgrade_env
    )
    if snapshots() != before:
        raise RuntimeError("Additive migration changed fixture records")
    print("PASS additive_upgrade_preserves_synthetic_campaign_link_destination_click", flush=True)
    engine.dispose()
    unit_env = env_for(unit)
    for key in ("ADMIN_API_KEY", "REPORT_API_KEY", "VISITOR_HMAC_KEY"):
        unit_env.pop(key + "_FILE", None)
    unit_env["TEST_DATABASE_URL"] = owner + "/" + unit
    unit_env["HTTP_ALLOWED_HOSTS"] = ""
    unit_env["DASHBOARD_ORIGIN"] = ""
    unit_env["ALLOW_LOCALHOST_LINKSPACE_DEMO"] = "true"
    # Existing downgrade exercises intentionally excluded: no destructive migrations are run.
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-k",
            "not migration and not downgrade",
            "-p",
            "no:cacheprovider",
        ],
        check=True,
        env=unit_env,
    )
    print("PASS backend_tests_used_only_new_security_databases", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--container", action="store_true")
    parser.add_argument("--test-root", type=Path)
    parser.add_argument("--inside-container", nargs=2)
    parser.add_argument("--database-host", default="127.0.0.1")
    parser.add_argument("--database-port", type=int, default=55439)
    args = parser.parse_args()
    try:
        if args.inside_container:
            if not all(name.startswith("security_test_") for name in args.inside_container):
                raise ValueError("Unsafe test database")
            owner = Path(os.environ["DATABASE_URL_FILE"]).read_text().strip().rsplit("/", 1)[0]

            def container_env(name):
                result = dict(os.environ, APP_ENV="development", DATABASE_URL=owner + "/" + name)
                result.pop("DATABASE_URL_FILE", None)
                return result

            run_databases(owner, *args.inside_container, container_env)
        else:
            main(
                args.env_file.resolve(),
                args.database_host,
                args.database_port,
                args.container,
                args.test_root,
            )
    except Exception as exc:
        parser.exit(
            1,
            f"Isolated backend test failed ({type(exc).__name__}); no credential values printed.\n",
        )
