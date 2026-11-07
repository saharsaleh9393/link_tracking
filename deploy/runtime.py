"""Container-only process setup; native Windows entry points remain unchanged."""

import json
import logging
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class SafeFormatter(logging.Formatter):
    def format(self, record):
        try:
            message = record.getMessage()
        except (TypeError, ValueError):
            message = "server_event"
        # Never emit exception bodies, request URLs, SQL parameters or bearer values.
        safe_events = {"maintenance_completed", "expired_partition_removed", "migration_completed"}
        safe_errors = {
            "click_recording_failed error_type=%s",
            "database_unavailable error_type=%s",
            "maintenance_failed error_type=%s",
        }
        event = (
            message
            if isinstance(record.msg, str)
            and (
                record.msg in safe_events
                or (
                    record.msg in safe_errors
                    and re.fullmatch(r"[a-z_]+ error_type=[A-Za-z]+", message)
                )
            )
            else "server_event"
        )
        return json.dumps(
            {
                "time": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "event": event,
                "error_type": record.exc_info[0].__name__
                if record.exc_info and isinstance(record.exc_info[0], type)
                else None,
            }
        )


def grant_runtime_access():
    from sqlalchemy import text

    from app.db import get_engine

    with get_engine().begin() as connection:
        connection.execute(text("GRANT USAGE ON SCHEMA public TO linkspace_app"))
        connection.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON dashboard_sessions, dashboard_login_buckets TO linkspace_app"
            )
        )
        connection.execute(
            text("GRANT SELECT, INSERT, UPDATE ON campaigns, links TO linkspace_app")
        )
        connection.execute(text("GRANT SELECT, INSERT ON link_destinations TO linkspace_app"))
        connection.execute(
            text("GRANT SELECT, INSERT, UPDATE, DELETE ON linkspaces TO linkspace_app")
        )
        connection.execute(
            text("REVOKE DELETE ON campaigns, links, link_destinations FROM linkspace_app")
        )
        connection.execute(text("REVOKE UPDATE ON link_destinations FROM linkspace_app"))
        connection.execute(
            text("GRANT SELECT, INSERT ON click_events, audit_events TO linkspace_app")
        )
        connection.execute(
            text(
                "GRANT SELECT ON daily_link_stats, daily_campaign_stats, aggregation_state, alembic_version TO linkspace_app"
            )
        )


def main():
    handler = logging.StreamHandler()
    handler.setFormatter(SafeFormatter())
    logging.basicConfig(handlers=[handler], level=logging.INFO, force=True)
    from app.config import get_settings

    settings = get_settings()
    action = sys.argv[1]
    if action in {"api", "worker"}:
        from sqlalchemy.orm import Session

        from app.db import get_engine
        from app.main import ready

        with Session(get_engine()) as session:
            ready(session)  # No automatic migration on normal service/reboot startup.
    if action == "api":
        import uvicorn

        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            access_log=False,
            proxy_headers=False,
            log_config=None,
            timeout_graceful_shutdown=25,
        )
    elif action == "worker":
        from app.worker import main as worker

        sys.argv = [sys.argv[0]]
        # worker basicConfig leaves this sanitized logging handler intact.
        worker()
    elif action == "migrate":
        from alembic import command
        from alembic.config import Config

        from app.worker import ensure_partitions

        command.upgrade(Config("alembic.ini"), "head")
        ensure_partitions()
        grant_runtime_access()
        logging.info("migration_completed")
    elif action == "worker-health":
        path = Path(os.environ["WORKER_HEARTBEAT_FILE"])
        if time.time() - path.stat().st_mtime > max(180, settings.worker_interval_seconds * 3):
            raise RuntimeError("Stale worker heartbeat")
    else:
        raise ValueError("Unknown runtime action")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            json.dumps({"event": "runtime_failed", "error_type": type(exc).__name__}),
            file=sys.stderr,
        )
        sys.exit(1)
