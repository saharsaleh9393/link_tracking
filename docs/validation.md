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
