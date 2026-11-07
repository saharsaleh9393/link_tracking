# Dashboard authentication update (migration 0004)

Sessions and login admission now live in PostgreSQL, shared by every web/API instance. The browser still receives an eight-hour signed, HttpOnly, SameSite=Strict cookie (Secure in production). Only SHA-256 token hashes and expiry timestamps are persisted. Every protected dashboard request checks the live store; successful logout deletes that session before clearing the cookie. Old stateless cookies require login again after the update. No campaign, link, destination or click record is migrated.

Database/network failures fail closed: protected requests are denied, login returns 503, and unsuccessful logout returns 503 without claiming success or clearing the cookie. An already authorized, in-flight request may finish after logout. There is no authorization cache.

Caddy replaces client-IP/proxy-proof headers for web upstream requests. A new independent `dashboard_proxy_secret`, mounted only to Caddy and Next.js, authenticates those headers. Next.js HMACs the verified IP before sending it to the private, admin-key-protected FastAPI state endpoints. Raw IPs, passwords and raw cookies are never sent to this store. Keep API/web ports private; the proof supplements network isolation. Upstream CDN/load-balancer client-IP trust is **not** enabled: adding one requires a reviewed Caddy trust configuration. Otherwise all clients behind it share that proxy's bucket.

Defaults: 10 admitted attempts per client and 100 per workspace account per 60 seconds. Both successful and failed attempts count, preventing unlimited session creation. The current dashboard has one shared password, so the account budget is workspace-wide. Admission is atomic across instances using a short PostgreSQL transaction lock. Blocked client requests do not consume the account budget. Responses remain generic (no account enumeration), with 429 and Retry-After. Configure `DASHBOARD_LOGIN_CLIENT_LIMIT`, `DASHBOARD_LOGIN_ACCOUNT_LIMIT`, `DASHBOARD_LOGIN_WINDOW_SECONDS` in the deployment env if needed. Expired rows are cleaned on login and by the worker, in bounded batches of 2,000 per table. Active rows are bounded by admission rate and eight-hour expiry. Global credential attacks can still temporarily exhaust the shared account budget; clients behind NAT share a client budget.

Native Windows development without a configured proxy secret ignores IP headers and uses one development bucket. Production/simulation require the authenticated Caddy headers. Keep clocks synchronized. Secret rotation, password changes and authorization/RBAC beyond the existing shared dashboard are separate operational work; this update does not rotate existing credentials.

## Safe existing-installation update (Windows CMD)

Review the diff, preserve your current image IDs/release tag, and keep a verified backup before the maintenance window. Run these commands **only on the intended installation**, from the repository root. They are instructions, not authorization for a remote deployment. No Git push is needed for the commands below once the reviewed code is present locally.

```cmd
cd /d C:\Users\a\projects\link_tracking
.venv\Scripts\python.exe deploy\prepare_auth.py --env-file .env.production
set "LS_COMPOSE=docker compose --env-file .env.production -f compose.production.yaml"
%LS_COMPOSE% config --quiet
%LS_COMPOSE% build api web
%LS_COMPOSE% --profile ops run --rm backup
%LS_COMPOSE% stop proxy web api worker
%LS_COMPOSE% --profile ops run --rm migrate
%LS_COMPOSE% up -d --wait --no-build
%LS_COMPOSE% ps
```

Set a **new, unused** `RELEASE_TAG` in the deployment env before building; retain the old images. The helper adds only a missing ingress secret, refuses to replace existing credentials, and does not edit the env file. Restrict `.local/deployment/.../secrets` with Windows ACLs. Migration `0004_dashboard_auth.py` only adds `dashboard_sessions` and `dashboard_login_buckets` plus expiry indexes; the migrate job also grants the existing runtime role access to these tables. If migration fails, keep write-facing services stopped and inspect sanitized logs; do not reset the DB.

For your existing local simulation, substitute these two commands above and keep the remaining steps unchanged:

```cmd
.venv\Scripts\python.exe deploy\prepare_auth.py --env-file .env.simulation
set "LS_COMPOSE=docker compose --env-file .env.simulation -f compose.production.yaml -f compose.simulation.yaml"
```

Linux operators use `python3 deploy/prepare_auth.py --env-file .env.production` and replace `%LS_COMPOSE%` with `docker compose --env-file .env.production -f compose.production.yaml` (or a shell function). No host OS/service configuration is changed by the helper. Keep the existing DNS, HTTPS and backup setup described in [deployment.md](deployment.md).

Rollback must retain migration 0004 and use an application version that enforces server-side sessions. Rolling back to stateless authentication reintroduces the vulnerability. No schema downgrade is part of deployment/rollback. Downgrade is defined but deliberately refuses to discard nonempty authentication tables. Never clear data to force it. Never use `down -v`, truncate, reset or restore over a live database.

After update, sign in again, verify a protected request succeeds, logout, then replay the previously copied cookie against `/api/tracker/management/overview`: it must return 401. A protected page must redirect to `/login`. Never paste the cookie into logs, tickets or command history. Verify HTTPS production cookies remain Secure. Availability of PostgreSQL/FastAPI is now required for dashboard authentication; monitor it.

## Isolated automated security checks

Use a **new** project, env file, database and port. Never use the production/simulation env in these scripts. The overlay exposes PostgreSQL only on `127.0.0.1:55439` for host tests and is never a production configuration. It adds a second web instance and two real source-IP clients; the test-only 4-second/4-attempt client budget is not a production default. Docker Compose 2.24.4+ and installed Python dev dependencies are required.

```cmd
.venv\Scripts\python.exe deploy\init_deployment.py --mode simulation --env-file .env.security --project linkspace-security --port 8090 --subnet 172.30.53.0/24 --database security_test
set "LS_SECURITY=docker compose --env-file .env.security -f compose.production.yaml -f compose.simulation.yaml -f compose.security-test.yaml"
%LS_SECURITY% config --quiet
%LS_SECURITY% build api web
%LS_SECURITY% up -d --wait db
%LS_SECURITY% --profile ops run --rm migrate
%LS_SECURITY% up -d --wait --no-build
.venv\Scripts\python.exe tests\security\run_backend.py --env-file .env.security
.venv\Scripts\python.exe tests\security\check_auth.py --env-file .env.security
%LS_SECURITY% stop
```

Run the scripts sequentially: HTTP checks intentionally stop/restart **only this new test database** to check fail-closed behavior. The backend runner creates new unique test databases each time, checks a forward-only 0003→0004 upgrade preserves synthetic business rows, and runs regression tests only there. Legacy destructive downgrade/migration tests are excluded. New test databases/volumes are retained for inspection. The HTTP runner checks all protected pages, copied-cookie rejection across instances, expiry/tampering, malformed bodies/origins, client isolation, spoofed headers, web restart persistence and database-outage handling. It never prints cookie/password values.

Managed Docker environments without host port publishing can use `--container` to run through the private Compose network (requires the host Python dev dependencies in `.venv/lib/python3.12/site-packages`). `--test-root` can point to a read-only staging copy of public source and dependencies if bind-mount permissions require it; never stage env or secret files. The optional private address flags `--database-host ADDRESS --database-port 5432` are available when direct container networking is supported. None of these options is necessary on ordinary Docker Desktop. Existing deployment smoke tests still cover redirects/tracking/analytics; do not run their `--write` mode against customer data.

## Verification performed for this update

- Backend: **122 passed**, **5 deselected** (legacy destructive migration/downgrade tests); one pre-existing Starlette/httpx deprecation warning. Executed inside the isolated Docker network with fresh unique test databases.
- Forward-only upgrade: 0003→0004 preserved all synthetic campaign/link/destination/click rows byte-for-byte.
- Frontend: **29 Vitest tests passed**; ESLint, TypeScript and Prettier checks passed.
- Production API and Next.js Docker builds passed, including optimized Next.js compilation, TypeScript and page generation. Native cloud-host `npm run build -- --webpack` failed parsing TypeScript `--showConfig` output; the same production build completed successfully inside the pinned Docker image. No native Windows build was executed.
- Actual Caddy + two Next.js instances + PostgreSQL checks passed: login, all protected pages, logout across instances, copied-cookie replay (401), expired/tampered cookies, malformed bodies/origins, per-client isolation, spoofed IP headers, shared limits after web restart, and fail-closed DB outage/recovery. Services recovered healthy.
- Production and security-overlay Compose validation passed; Caddy configuration validation passed with existing redundant-header/format warnings. A value-free check confirmed the ingress secret is absent from Caddy's saved JSON.
- Initial test-harness runs failed due to managed Docker networking/mount permissions and inherited simulation host settings; the final isolated runs above passed after correcting the harness. Production/simulation data was not used.
- No real HTTPS/server deployment, Git push, schema downgrade or existing-database reset was performed. Browser Playwright workflows were not rerun; protected-route HTTP and backend workflow regression tests were executed.

## Changed files

- `.env.production.example`
- `README.md`
- `app/config.py`
- `app/main.py`
- `app/models.py`
- `app/worker.py`
- `compose.production.yaml`
- `deploy/Caddyfile`
- `deploy/Caddyfile.local`
- `deploy/init_deployment.py`
- `deploy/routes.caddy`
- `deploy/runtime.py`
- `deploy/web-entrypoint.mjs`
- `docs/deployment.md`
- `tests/conftest.py`
- `tests/test_linkspaces.py`
- `web/src/app/api/auth/route.ts`
- `web/src/app/api/tracker/[...path]/route.ts`
- `web/src/components/shell.tsx`
- `web/src/lib/auth.ts`
- `web/src/lib/session.ts`
- `web/tests/core.test.ts`
- `app/dashboard_auth.py`
- `compose.security-test.yaml`
- `deploy/prepare_auth.py`
- `deploy/proxy-entrypoint.sh`
- `docs/security-auth.md`
- `migrations/versions/0004_dashboard_auth.py`
- `tests/security/Caddyfile`
- `tests/security/check_auth.py`
- `tests/security/run_backend.py`
- `tests/test_dashboard_auth.py`
- `tests/test_prepare_auth.py`
- `web/src/lib/auth-store.ts`
- `web/src/lib/login-client.ts`
- `web/tests/auth-store.test.ts`
- `web/tests/auth.test.ts`
