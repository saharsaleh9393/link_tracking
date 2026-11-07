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

## CSV, country lookup and reporting integrations — 2026-11-04

- **62 Python tests passed**, including CSV/JSON equivalence, UTF-8 Persian text, formula neutralization, cursor export continuity, read-only catalog access, real MMDB parsing, IPv4/IPv6-mapped lookups, private IP rejection, trusted-proxy/header precedence and safe database installation/update behavior.
- **8 frontend unit tests and 6 Chromium scenarios passed**. The report workflow downloaded 102 filtered click rows from three real CSV API pages, with one BOM/header and no visitor digest. Existing management, clipboard, language and authenticated-boundary scenarios also passed.
- Frontend lint, TypeScript, optimized build, Prettier and Python Ruff checks passed. No schema migration was needed.
- Country tests use the licensed synthetic MaxMind fixture under `tests/data`, not a production country database. Installation behavior is tested against compressed fixture bytes, including preservation of existing files and invalid replacements.
- The official DB-IP production database download returned a proxy HTTP 403 in this managed cloud. It was not bypassed or installed. Users must run the documented installer on their computer or supply an authorized compatible country MMDB, then restart the API. Local/private IPs and historical unknown events remain unknown by design.

See `docs/reporting-api.md` for read-only API examples, export limits, country setup and attribution.

## Link Settings — 2026-11-07

- **100 Python tests passed** on disposable PostgreSQL 17 `tracker_test`. New coverage includes legacy URL backfill without click changes, immutable per-link URLs, explicit/default selection, concurrent default changes and duplicate normalized configurations, database default uniqueness, activation/deletion rules, host/path matching, root approval and reserved routes, HEAD counting, read-only catalog URLs, generated root slugs and downgrade refusal for custom URLs.
- **15 frontend unit tests and 7 Chromium scenarios passed** against an optimized Next.js build and separate `tracker_ui_test`. The new browser workflow creates and edits a Linkspace, preserves its form across EN/FA and RTL/LTR changes, changes the default, overrides the selection, creates a tracked link, checks preserved destination parameters, verifies the old URL survives configuration edits and checks the unsafe-root validation message. Existing CSV, management, authentication and mobile workflows also passed.
- Frontend lint, TypeScript and Prettier passed. Optimized build passed using `npm run build -- --webpack`, the supported alternative used for this managed environment's Turbopack port restriction. Ruff lint/format and `alembic check` passed; no metadata drift was detected.
- The existing retention test assumed seven 31-day aggregation batches always covered an old month boundary. On November 7 this assumption failed; the test now computes the required batches from its date range. Worker behavior was not changed.
- No new dependencies, production database migration, DNS changes, HTTPS certificates, reverse-proxy changes or deployment were performed. Root `.env`, `web/.env.local` and database volumes were not committed or overwritten. Windows commands are documented but were not executed on Windows. Domain routing labels require the manual operator setup described in `docs/link-settings.md`; they are not automatic verification.

## Local Linkspace demo compatibility — 2026-11-07

- **115 Python tests passed**. Added coverage for HTTP `.localhost` normalization, a prefixless default shared across campaigns, tracking/HEAD behavior, exact host/port matching, reserved slugs, invalid/lookalike hostnames and disabling automatic demo approval when the backend public origin is not loopback HTTP on the same port.
- **18 frontend unit tests passed**, including field-specific Linkspace errors that do not echo submitted values. Frontend lint, TypeScript, Prettier, Ruff and an optimized Webpack build passed. No schema change or dependency change is needed.
- **All 8 Chromium scenarios passed.** The new scenario creates a local Linkspace through the UI, checks invalid base/prefix errors, previews and copies a prefixless URL, resolves a real special-use `.localhost` hostname to the local API and follows its 302 while preserving the destination query. The controlled external destination is fulfilled through Chromium CDP, with no external destination request. Playwright routing interception initially tried to tunnel local names through the cloud proxy; the test now keeps only special-use loopback names local and leaves public egress policy intact.
- The campaign browser test now scopes suggestions to their listbox and waits for the relevant response before keyboard selection, avoiding native `<option>` matches and a pending blur/debounce race; campaign application logic was not changed.
- See `docs/link-settings.md#local-demo-with-golocalhost` for Windows demo values and an optional hosts entry. DNS, server deployment, real environment files and operating-system hosts files were not modified. Production origins still require HTTPS and explicit root-routing approval.

## Production packaging and local simulation — 2026-11-07

- **121 Python tests passed**: original tracking/management/reporting plus deployment-only secret-file loading, production HTTPS/host/proxy checks, dashboard-root exclusion, physical-peer preservation, sanitized logging and non-overwriting initialization. **18 frontend unit tests and all 8 Chromium workflows passed** with the supported native optimized build; normal Windows development/start commands remain unchanged.
- Both final API and standalone Next.js Docker images built successfully from digest-pinned official bases with locked/hash-verified dependencies. Managed cloud CA trust was passed only through the optional BuildKit secret. Local `.env` files and runtime secret mounts were absent from the built images. No new dependencies or schema migration were added.
- A five-service HTTP simulation ran healthy on loopback port 8080. Its only host binding was Caddy; PostgreSQL, API, worker and web had no published ports. API connected as `linkspace_app`, with no schema CREATE privilege and with required management UPDATE privileges. Caddy's exact static peer address is outside the dynamic address pool. Internal upstream traffic honors an internal-only NO_PROXY extension, preserving public egress proxy policy.
- The public-proxy smoke script passed login/session flags, cross-origin and anonymous rejection, default link creation, redirect/query/Host preservation, HEAD exclusion from click counts, analytics/raw exports, custom prefixes, shared dashboard `/r`, dedicated root links, read-only API integration and private management blocking. Actual Chromium login and EN/FA management navigation also passed through the Docker proxy.
- A protected custom-format backup containing **1 synthetic campaign, 4 links and 4 clicks** was restored into a different fresh `restore_check` database/Compose project on port 8081. Counts matched before worker startup; the original database retained the same counts. Explicit migration/grants and the complete smoke script then passed on the restored stack. A second restore into that populated database was refused without changing it.
- Final app containers were recreated without migration or volume deletion: the existing four clicks remained, service health passed and the proxy smoke suite passed again. Initializer repeatability is covered by tests; root `.env`, `web/.env.local` and existing development database volumes were not overwritten.
- Both Compose variants validated. The actual production HTTPS Caddy config validated with **Docker networking disabled**, so no ACME certificate or remote server connection was attempted. GitHub Actions now includes an isolated deployment smoke job; a hosted CI run is separate from these local checks.
- Native Windows/Docker Desktop execution, real public DNS/TLS issuance, remote deployment, server reboot recovery, production load capacity, scheduled/encrypted off-host backups and external alert integration remain operator validation/setup steps. Windows CMD, Linux-after-discovery, Windows Server Linux-VM constraints, domain routing, secrets, backup/restore and compatible-image rollback commands are in `docs/deployment.md`.
