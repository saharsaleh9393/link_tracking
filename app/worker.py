"""Run with python -m app.worker [--once]. Only uses the primary PostgreSQL database."""

import argparse
import logging
import os
import signal
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

from sqlalchemy import text

from app.config import get_settings
from app.db import get_engine

logger = logging.getLogger("tracker.worker")
stop = Event()


def ensure_partitions():
    now = datetime.now(UTC)
    month_index = now.year * 12 + now.month - 1
    with get_engine().begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '1s'"))
        connection.execute(text("SELECT pg_advisory_xact_lock(827301)"))
        for offset in (-1, 0, 1, 2):
            year, month = divmod(month_index + offset, 12)
            next_year, next_month = divmod(month_index + offset + 1, 12)
            month += 1
            next_month += 1
            connection.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS click_events_{year}_{month:02d} PARTITION OF click_events "
                    f"FOR VALUES FROM ('{year}-{month:02d}-01') TO ('{next_year}-{next_month:02d}-01')"
                )
            )


def rebuild_day(connection, day):
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    params = {"day": day, "start": start, "end": start + timedelta(days=1)}
    connection.execute(text("DELETE FROM daily_link_stats WHERE day = :day"), params)
    connection.execute(
        text("""
        INSERT INTO daily_link_stats
        (day, link_id, total_clicks, human_clicks, bot_clicks, unknown_clicks,
         estimated_unique_visitors, refreshed_at)
        SELECT :day, link_id, count(*),
            count(*) FILTER (WHERE classification = 'human'),
            count(*) FILTER (WHERE classification = 'bot'),
            count(*) FILTER (WHERE classification = 'unknown'),
            count(DISTINCT visitor_digest) FILTER (WHERE classification != 'bot'), now()
        FROM click_events WHERE occurred_at >= :start AND occurred_at < :end
        GROUP BY link_id
    """),
        params,
    )
    connection.execute(text("DELETE FROM daily_campaign_stats WHERE day = :day"), params)
    connection.execute(
        text("""
        INSERT INTO daily_campaign_stats
        (day, campaign_id, total_clicks, human_clicks, bot_clicks, unknown_clicks,
         estimated_unique_visitors, refreshed_at)
        SELECT :day, coalesce(campaign_id, '00000000-0000-0000-0000-000000000000'::uuid), count(*),
            count(*) FILTER (WHERE classification = 'human'),
            count(*) FILTER (WHERE classification = 'bot'),
            count(*) FILTER (WHERE classification = 'unknown'),
            count(DISTINCT visitor_digest) FILTER (WHERE classification != 'bot'), now()
        FROM click_events WHERE occurred_at >= :start AND occurred_at < :end
        GROUP BY campaign_id
    """),
        params,
    )


def aggregate():
    today = datetime.now(UTC).date()
    # One snapshot and one worker: retries replace whole buckets rather than incrementing.
    with get_engine().connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.execute(text("SET LOCAL statement_timeout = '60s'"))
            if not connection.scalar(text("SELECT pg_try_advisory_xact_lock(827302)")):
                return
            next_day = connection.scalar(
                text("SELECT next_day FROM aggregation_state WHERE name='daily'")
            )
            if next_day is None:
                earliest = connection.scalar(text("SELECT min(occurred_at) FROM click_events"))
                next_day = earliest.date() if earliest else today
            # Advance through old data in bounded batches; always refresh recent buckets.
            days = {today, today - timedelta(days=1)}
            for _ in range(31):
                if next_day >= today:
                    break
                days.add(next_day)
                next_day += timedelta(days=1)
            for day in sorted(days):
                rebuild_day(connection, day)
            connection.execute(
                text("""
                INSERT INTO aggregation_state(name,next_day,refreshed_at) VALUES ('daily',:day,now())
                ON CONFLICT(name) DO UPDATE SET next_day=excluded.next_day,refreshed_at=excluded.refreshed_at
            """),
                {"day": next_day},
            )


def purge_expired():
    """Drop only whole expired monthly partitions after aggregates cover their data.

    Effective raw retention is configured minimum plus up to one calendar month.
    """
    cutoff = datetime.now(UTC).date() - timedelta(days=get_settings().raw_retention_days)
    with get_engine().begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '1s'"))
        connection.execute(text("SELECT pg_advisory_xact_lock(827302)"))
        covered = connection.scalar(
            text("SELECT next_day FROM aggregation_state WHERE name='daily'")
        )
        if covered is None:
            return
        import re

        names = connection.scalars(
            text("""
            SELECT c.relname FROM pg_inherits i JOIN pg_class c ON i.inhrelid=c.oid
            WHERE i.inhparent='click_events'::regclass
        """)
        ).all()
        for name in names:
            match = re.fullmatch(r"click_events_(\d{4})_(\d{2})", name)
            if not match:
                continue
            year, month = map(int, match.groups())
            end = datetime(year + (month == 12), month % 12 + 1, 1).date()
            if end <= cutoff and end <= covered:
                connection.execute(text(f'DROP TABLE "{name}"'))
                logger.info("expired_partition_removed")


def run_once():
    ensure_partitions()
    aggregate()
    purge_expired()
    from sqlalchemy.orm import Session

    from app.dashboard_auth import cleanup_auth

    with Session(get_engine()) as session:
        cleanup_auth(session)
        session.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if args.once:
        run_once()
        return
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    while not stop.is_set():
        try:
            run_once()
            if path := os.environ.get("WORKER_HEARTBEAT_FILE"):
                Path(path).touch()
            logger.info("maintenance_completed")
        except Exception as exc:
            # Never log exception payloads that may contain query parameters.
            logger.error("maintenance_failed error_type=%s", type(exc).__name__)
        stop.wait(get_settings().worker_interval_seconds)


if __name__ == "__main__":
    main()
