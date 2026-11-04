# Validation evidence

Validated in the managed development environment on 2026-11-03 with Python 3.12.14 and PostgreSQL 17, using the repository's pinned dependencies.

| Check | Observed outcome |
|---|---|
| Fresh Compose database and `alembic upgrade head` | Passed |
| `alembic check` | No model/schema drift; runtime partition children excluded from autogeneration |
| PostgreSQL integration suite | 37 passed; no skipped tests |
| Ruff lint and formatting | Passed |
| Repeated frozen dependency sync | Passed; existing local credentials preserved |
| Repeated worker maintenance | Passed; aggregates remain idempotent |
| Native API HTTP smoke | Passed: create link, redirect, persisted event, analytics, soft deletion |
| Docker image build | Passed with hash verification and TLS verification enabled |
| Non-root Docker API HTTP smoke | Passed after correcting copied-file ownership |
| Worker and migration check inside image | Passed |
| Local logical backup and isolated restore | Passed; event/link/audit/aggregate row counts and schema revision matched |

One bounded local load probe sent 500 requests with concurrency 10. All 500 returned 302, and the API confirmed 500 persisted events for that link. Observed throughput was approximately 194 requests/second, median response time 45 ms and p95 81 ms. These numbers describe this one short local run; they do not establish sustained production capacity or a latency SLA.

The native API and worker were started in managed execution sessions. A detached shell background process was cleaned up by the execution runner; saved startup instructions therefore use managed long-running sessions. Do not assume live processes survive environment publication or a new task.

Not executed: native Windows/Laragon startup, Power BI Desktop/Service refresh, GitHub-hosted CI, remote SSH discovery/deployment, production backup scheduling or production load tests. Their instructions/interfaces are provided, but those execution environments have not been inspected or validated.

`install_script` and `start_skill` were saved to the cloud configuration draft. Saving is separate from publishing and from validating restoration in a fresh task.

## Streamlit dashboard — 2026-11-04

Branch: `feat/streamlit-dashboard`. The complete suite now has **61 passing tests**, including all 37 original backend checks. Ruff lint and formatting pass using `uv sync --frozen --extra dashboard` dependencies. No database schema migration was added.

New checks exercise Persian Streamlit forms through the actual authenticated HTTP adapter into FastAPI and PostgreSQL: create/edit/delete links, activation state, destination switching, create/archive campaigns, UTM charts and link comparisons, raw-click pagination/filter resets, search, server-side counts, form failures and unavailable API handling. An unrelated edit preserves the original expiry timestamp, including seconds and microseconds.

Real Chromium checks exercised the running API/Streamlit pair on localhost, desktop and 390-pixel mobile layouts. API credentials were absent from the browser DOM and received WebSocket frames. Browser-test tools were isolated from the application's runtime dependency lock. Screenshots and generated state remain in ignored `.local/` files.

Windows commands are documented but native Windows execution was not available here. The existing API exports remain compatible; no new Power BI integration or remote deployment was performed.

## Bilingual Next.js dashboard — 2026-11-04

Branch: `feat/nextjs-admin-ui`, based on `feat/streamlit-dashboard` at `2d99b74`, not `main`. Streamlit runtime and its UI-specific tests were replaced; the previous implementation remains in that parent commit and branch.

- **46 Python tests passed**, including all original backend workflows, concurrent campaign-name uniqueness, direct database enforcement, newest-first campaign/link counts, and atomic migration refusal on legacy duplicates or empty names without data loss.
- **7 frontend unit tests passed** for matching EN/FA catalogs, session expiry/signature protection, same-origin checks, forwarding allowlists, server-only API credentials, sanitized error codes and date ranges.
- **6 real Chromium scenarios passed** against an optimized Next.js build and a separate `tracker_ui_test` database: first-visit English despite Persian browser preferences; persisted RTL/LTR choice; draft form and route preservation; explicit/keyboard campaign autocomplete and duplicate errors; destination and link workflows; authenticated boundaries; mobile filters; and 102-event cursor pagination.
- `npm run lint`, `npm run typecheck`, `npm run build`, Prettier, Ruff and `alembic check` passed. Tested with Node 24.22.1, Python 3.12.14 and PostgreSQL 17.
- Browser HTML/JSON/RSC/JavaScript responses were checked for the isolated API keys, session secret and database connection string; none were exposed. Desktop EN/FA and mobile screenshots were inspected and retained only under ignored `.local/`.
- Initializer repeatability was verified: existing `.env.local` was preserved. Root `.env`, database volumes and generated artifacts are excluded from Git.

Native Windows execution and remote production deployment remain unperformed. Exact Windows CMD setup/run commands are in README. CI has been updated with the same backend/frontend checks and browser workflows; a GitHub-hosted run is separate from this local evidence.
