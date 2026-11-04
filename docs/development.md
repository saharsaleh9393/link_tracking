# Development and verification

Run commands from the repository root. Use the existing checkout; cloud tasks already have isolation and do not need another Git worktree.

## Dependencies

`uv.lock` is the cross-platform source lock. The hash-pinned pip exports support Python installations without uv. Python 3.12 is the tested runtime.

After an intentional dependency update:

```bash
uv lock
uv sync --frozen --extra dashboard
uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file requirements.lock
uv export --frozen --extra dashboard --no-dev --no-emit-project --format requirements-txt --output-file requirements-dashboard.lock
uv export --frozen --extra dashboard --no-emit-project --format requirements-txt --output-file requirements-dev.lock
```

## Tests

Create a **disposable** PostgreSQL database named `tracker_test`, owned by a role with schema creation privileges. Tests migrate and truncate that database. Never use a production database. No SQLite substitution is used because partitioning, constraints and SQL reporting need PostgreSQL.

For the local Compose database, this creates the test database once:

```bash
docker compose exec db createdb -U tracker tracker_test
```

Bash test environment:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://tracker:tracker_local_only@127.0.0.1:5432/tracker_test'
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

PowerShell equivalent:

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://tracker:tracker_local_only@127.0.0.1:5432/tracker_test'
.\.venv\Scripts\pytest -q
.\.venv\Scripts\ruff check .
.\.venv\Scripts\ruff format --check .
```

Tests fail rather than silently skipping integration checks if `TEST_DATABASE_URL` is absent. Test database names must contain `test`; additionally verify the hostname and user yourself. Tests must run serially against one database. The suite uses its own test-only keys and never prints application keys.

Existing coverage exercises destination abuse, permissions, link lifecycle and version conflicts, snapshot attribution, concurrent clicks, missing/expired links, bot classification, trusted headers, daily HMAC rotation, keyset paging, aggregate repeatability and destination ownership constraints.

Install `requirements-dev.lock` or use `uv sync --frozen --extra dashboard` for the complete suite. Streamlit's AppTest drives the real Persian forms through an HTTP adapter into the FastAPI test client and disposable PostgreSQL database. Tests cover dashboard creation/edit/deletion, destinations, campaigns, charts, expiry preservation, sanitized errors and server-only authorization. See [dashboard](dashboard.md).

CI runs the same checks against PostgreSQL 17. It has not been executed on GitHub until a workflow run occurs.

## Migrations

Run `alembic upgrade head` before startup, once per deployment, using migration credentials. Run `alembic check` after model changes to check for drift. Never let API startup auto-create or silently migrate production tables.

## Load probe

Create a disposable staging link and record its baseline count, then run:

```bash
.venv/bin/python scripts/load_test.py http://127.0.0.1:8000/r/YOUR-SLUG --requests 500 --concurrency 10
```

This creates real events. Compare analytics after the run: successful 302 responses alone do not demonstrate event durability under the availability-first policy. Watch `tracker_redirects_total{outcome="unrecorded"}`. The probe is a bounded local check, not evidence of production capacity.
