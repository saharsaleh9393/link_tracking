# Next.js dashboard contracts

## Architecture

`web/src/app` uses App Router route groups for authenticated screens. `components/ui` contains locally owned shadcn/ui source components built on Radix, CVA and Tailwind; `components/views` owns presentation, not analytics business rules. TanStack Table handles table interaction and Recharts renders backend counts.

Browser requests go to same-origin `/api/tracker/...`. A narrow route/method allowlist forwards requests to FastAPI with the existing server-side keys. Backend errors become localized error codes; keys, database URLs and backend error payloads are never sent to browsers. GETs use no-store, writes are not automatically retried, and abortable requests avoid stale filter results. A network failure after a write can be ambiguous: refresh before retrying.

The dashboard has a separate password login and HMAC-signed, eight-hour HttpOnly/SameSite=Strict session cookie. CSRF checks require matching Origin and the destination Host; retain Host at a trusted reverse proxy, or set a fixed `DASHBOARD_ORIGIN`. Login attempts have a process-local minute budget; Internet-facing deployment also requires ingress rate limits. No users/RBAC or multi-tenant ownership is claimed.

All public/private URL settings reject credentials; there are no `NEXT_PUBLIC_*` credential variables. `PUBLIC_BASE_URL` is deliberately public. Keep `.env` and `web/.env.local` private. Production needs HTTPS, `DASHBOARD_SECURE_COOKIES=true`, a configured public origin, protected service environment and appropriate supervision after inspecting the server. These are not deployment instructions for an uninspected server.

## Language and state

`next-intl` reads only an explicit `locale` cookie, falling back to English regardless of Accept-Language. The client provider changes messages and HTML lang/dir without navigation or a React subtree key change. The current route, applied filters, typed searches and unsaved modal fields survive language changes. The top-header switcher is mirrored inside accessible modal dialogs so it remains reachable while the background is inert. User data such as campaign names is never machine-translated.

Cookie preference lasts one year. Both catalogs have matching keys/interpolations. Persian date display explicitly uses the Gregorian calendar; reporting boundaries and server buckets remain UTC. Changing language does not change the time range or visitor estimation semantics.

## Campaign names and legacy data

Migration `0002` takes a bounded table lock, checks normalized legacy names, and creates a unique expression index on `lower(btrim(name, whitespace_characters))`. It does not rewrite names, IDs, campaign assignments or events. PostgreSQL lower-case comparison follows the database locale; this is case-insensitive equality, not fuzzy/accent-insensitive matching.

If duplicates or empty names exist, the transaction rolls back, including the migration revision. **No deletion, merge or automatic renaming occurs.** Preserve a backup, inspect the conflicting records, explicitly rename the intended campaigns through the previous management flow or a reviewed database change, then rerun. The error deliberately does not dump campaign names. Schema rollback removes the uniqueness index; it never removes campaign rows.

The API trims new names, rejects blanks and maps create/rename unique violations to HTTP 409, including concurrent requests. Campaign listing adds optional `with_link_count`, `sort_by`, `descending`; its existing list response and default order remain supported. Link count covers currently assigned, non-deleted links. Historical snapshots remain unchanged.

Autocomplete retrieves a bounded suggestion page with partial, case-insensitive matching. Typing and selecting a suggestion do not apply the table search; Search or Enter does. Clear explicitly resets it. The recent campaign table uses server-side sorting and 25-row pagination; column-header sorting affects only the current page. Selectors retrieve bounded catalogs (up to 500) with search refinement; breakdowns use bounded pages and trends cap at 1000 buckets.

## Verification

`npm test` covers translation parity, session signing/expiry/tampering, CSRF/origin behavior, API forwarding boundaries, key handling, sanitized errors and date bounds. Backend tests additionally prove trimming, duplicate rejection, concurrent creation, direct SQL uniqueness, link counts and migration rollback without data loss.

Real-browser tests use a separate disposable PostgreSQL database, **never the application database**. Create `tracker_ui_test`, then start a FastAPI process with the test-only credentials below. From the root in Windows CMD:

```bat
docker compose exec db createdb -U tracker tracker_ui_test
set DATABASE_URL=postgresql+psycopg://tracker:tracker_local_only@127.0.0.1:5432/tracker_ui_test
set ADMIN_API_KEY=e2e-admin-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
set REPORT_API_KEY=e2e-report-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
set VISITOR_HMAC_KEY=e2e-visitor-cccccccccccccccccccccccccccccccccccccccc
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8003 --no-access-log --no-proxy-headers
```

In another CMD, from `web`:

```bat
npm ci
npx playwright install chromium
npm run build
npm run test:e2e
```

Playwright launches Next.js on port 3100 with isolated test-only dashboard credentials and the API URL on port 8003. It checks first-visit English, preference persistence, RTL/LTR, form/filter preservation, navigation order, autocomplete, duplicates, links/destinations/redirects/reports and authenticated boundaries. The tests create synthetic records in that database and must not target live data. CI uses the same isolated settings. On the managed Linux machine, `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium` can select the provided browser instead of downloading one.

Windows commands are provided; native Windows execution is not claimed validated in this Linux environment. Streamlit history is retained on the previous branch.
