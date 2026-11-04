# Linkspace · Marketing Link Tracking

A bilingual marketing management dashboard: **Next.js App Router, React, TypeScript, Tailwind CSS, shadcn/ui components, next-intl, TanStack Table and Recharts**, backed by FastAPI and PostgreSQL.

رابط انگلیسی/فارسی برای مدیریت کمپین، لینک و مقصدها و تحلیل کلیک‌ها. زبان اولین بازدید همیشه انگلیسی است؛ EN / FA زبان را ذخیره می‌کند و بدون از دست‌رفتن صفحه، فرم یا فیلتر بین LTR و RTL جابه‌جا می‌شود. نیازی به Swagger یا Power BI برای استفاده روزمره نیست.

Navigation: **Overview → Campaigns → Links → Destinations → Traffic Analytics → Click Reports**.

## Windows setup — CMD

Run these commands in **Command Prompt (CMD)** from the checkout root. Requirements: Python 3.12, Node.js 24 LTS with npm, and PostgreSQL 17 (native or Docker Desktop). Laragon's MySQL is not used. This version is for local development; no SSH server deployment has been performed.

Get this branch without changing `main`:

```bat
git fetch origin
git switch feat/nextjs-admin-ui
```

Install Python dependencies and create local settings. The initializer preserves an existing `.env`:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
.venv\Scripts\python.exe scripts\init_env.py
```

For a Docker development database:

```bat
docker compose up -d db
```

Alternatively, create a native PostgreSQL database `tracker` owned by a login role, then set `DATABASE_URL` in `.env` to its connection URL. Encode special characters in URL passwords. Do not run Docker on a port already occupied by native PostgreSQL.

Apply schema migrations and run maintenance once:

```bat
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m app.worker --once
```

**Existing campaigns:** migration `0002` enforces names that are unique ignoring case and surrounding whitespace. If existing duplicate/empty names are found, it stops atomically and preserves all data. Review and explicitly rename the conflicting records, then rerun. It never deletes or silently merges campaigns. Back up an existing database before migrations. Details: [web dashboard and migration notes](docs/web-dashboard.md).

Install the frontend and create a separate dashboard login:

```bat
cd web
npm ci
npm run init-env
cd ..
```

Read `DASHBOARD_PASSWORD` privately in `web\.env.local` to sign in. This is the dashboard login password, **not** an API key. The helper does not print credentials or overwrite existing settings. Next.js reads FastAPI keys server-side from the root `.env`.

## Run locally — three CMD windows

**Window 1 — FastAPI**, from the repository root:

```bat
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

**Window 2 — worker**, from the repository root:

```bat
.venv\Scripts\python.exe -m app.worker
```

**Window 3 — Next.js**, from the repository root:

```bat
cd web
npm run dev
```

On **your own computer**, open `http://127.0.0.1:3000` and sign in. The development server binds only to localhost. Links copied with `PUBLIC_BASE_URL=http://127.0.0.1:8000` work on that same computer; a publicly reachable hostname is a later deployment decision.

To verify/run the optimized frontend instead of development mode (inside `web`):

```bat
npm run build
npm run start
```

If FastAPI uses another port, set `TRACKER_API_URL` in `web\.env.local`; `PUBLIC_BASE_URL` is the separate public address shown in tracking links. Restart Next.js after environment changes.

## Included workflows

- Overview KPIs, 7-day click activity and recent management activity.
- Campaign autocomplete with keyboard support, explicit Search/Enter, Clear, case-insensitive matching, newest-first records, status, link counts, sorting and pagination.
- Trimmed campaign names with database-enforced uniqueness, including concurrent requests; create/edit/archive/restore without touching historical clicks.
- Link creation/editing, UTM attribution, campaign assignment, expiry, activation/deactivation, confirmed soft deletion and tracking URL copy.
- Destination versions, addition and explicit active-destination selection, including a dedicated Destinations page.
- Interactive traffic trends and campaign/source/medium/device/browser/country/OS/UTM breakdowns, date/campaign/link filters and link comparisons.
- Cursor-paginated raw-click reports without raw IP or visitor digest exposure.
- English/Persian navigation, forms, errors, chart/table labels, notifications, accessible dialogs and responsive mobile navigation.

Historical tracking events, analytics semantics, redirects, partitions and worker remain intact. Country is unknown unless a trusted source supplies it; human/bot classification is heuristic. Visitor-days are daily estimates, **not distinct people across a multi-day range**. Dates use the Gregorian calendar and UTC reporting boundaries.

The previous Streamlit implementation is preserved on `feat/streamlit-dashboard` and in Git history (commit `2d99b74`); it is no longer the primary runtime on this branch. Existing export APIs remain compatible, with no new Power BI integration.

## Verification

Python tests require a **disposable** database named `tracker_test`; they truncate its contents:

```bat
.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
docker compose exec db createdb -U tracker tracker_test
set TEST_DATABASE_URL=postgresql+psycopg://tracker:tracker_local_only@127.0.0.1:5432/tracker_test
.venv\Scripts\pytest.exe -q
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
```

Inside `web`:

```bat
npm run lint
npm run typecheck
npm test
npm run build
```

[Browser-test instructions and security contracts](docs/web-dashboard.md) · [Backend architecture](docs/architecture.md) · [Operations](docs/operations.md) · [Validation evidence](docs/validation.md).
