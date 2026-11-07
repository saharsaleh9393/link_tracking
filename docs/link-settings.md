# Link Settings

Open **Settings → Link Settings** (`/settings/links`). EN/FA forms manage PostgreSQL-backed URL configurations: name, HTTP(S) origin, optional single path prefix, active status and default. Search and pagination are server-side; tables support sorting. A preview is not proof that the domain resolves.

The default is automatically used by `POST /api/v1/links` when `linkspace_id` is omitted/null. An explicit active `linkspace_id` overrides it. Create-link forms offer both choices and preview the selected URL. Management responses and `GET /api/v1/reporting/links` return the authoritative `tracking_url`; tables, details, destination pages and copy buttons use that value.

Each link stores its base URL and path prefix at creation. Changing a configuration or default affects **future links only**. Existing links keep their destination, UTM behavior, attribution and URL. Deactivating a Linkspace prevents new selection, without disabling its existing links. Only unused, non-default configurations may be deleted; even soft-deleted links retain their association. Choose a different default before disabling/removing the current default.

## Upgrade locally (Windows CMD)

Stop FastAPI, worker and Next.js, leaving PostgreSQL running. Back up any database containing data you want to retain. Before migration, verify the root `.env` has the **existing** public tracking origin in `PUBLIC_BASE_URL`; the migration uses it to freeze legacy `/r/{slug}` URLs. Do not change it to a new domain first.

If `web/.env.local` overrides `PUBLIC_BASE_URL`, copy that existing public value to the backend setting before migration so snapshots match the URLs previously displayed by Next.js. For new configurations, FastAPI/PostgreSQL is the source of truth.

From the repository root:

```bat
.venv\Scripts\alembic.exe upgrade head
```

Migration `0003` creates `linkspaces`, adds three indexed/FK/snapshot fields to `links`, seeds an active default named `Original links`, and backfills existing URLs. It does not change slugs, destinations, click events or aggregates. PostgreSQL runs it transactionally with a five-second lock acquisition limit. Retry during a quiet period if locks cannot be acquired. Snapshot fields are nullable for schema compatibility; all API-created and migrated links receive snapshots. Downgrade is refused when it would discard custom link URLs.

Restart in three CMD windows, each initially at the repository root:

```bat
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

```bat
.venv\Scripts\python.exe -m app.worker
```

```bat
cd web
npm run dev
```

For an optimized frontend, replace `npm run dev` with `npm run build` followed by `npm run start`. No new dependencies or credentials are needed for this feature. Settings and URLs are owned by FastAPI/PostgreSQL; the browser receives no API keys.

## Local demo with `go.localhost`

With FastAPI on port 8000 and backend `PUBLIC_BASE_URL=http://127.0.0.1:8000`, create:

| Field | Value |
|---|---|
| Name | Local demo |
| Base URL | `http://go.localhost:8000` (without `/slug`) |
| Path prefix | Empty |
| Active / Default | Enabled |

This creates URLs such as `http://go.localhost:8000/launch` for new links in **any campaign**. Use the actual API port, not the dashboard's port 3000. No migration or `LINKSPACE_ROOT_ORIGINS` change is needed for this dedicated local hostname. The local-demo label means development on this computer, not public DNS/TLS readiness.

Modern browsers resolve `.localhost` names to loopback. If your Windows resolver does not, add `127.0.0.1 go.localhost` to `C:\Windows\System32\drivers\etc\hosts` using an administrator editor. Keep FastAPI bound to `127.0.0.1`; don't edit DNS, expose it to the LAN or change real server settings for this demonstration. Anyone opening this URL on another computer targets **their own** localhost.

Automatic root approval is deliberately limited to valid HTTP `.localhost` subdomains on the same effective port as a loopback backend `PUBLIC_BASE_URL`. Bare localhost/IP roots, different ports, HTTPS localhost roots and public domains retain the explicit approval requirement. When moving to production, set `PUBLIC_BASE_URL` to the real public origin; automatic demo approval then stops. Test URLs are not rewritten into public URLs: create a production Linkspace and use it for new links. Domain/prefix validation errors are localized separately, without exposing submitted values.

## Manual domain and routing setup (no deployment performed)

Custom origins require **HTTPS**; HTTP is permitted for localhost, its subdomains and loopback development. Credentials, URL paths, queries, fragments, wildcards and invalid ports are rejected. Prefixes normalize to lowercase, without surrounding slashes. Use one segment such as `r`, `go` or `visit`. Application paths such as `api`, `health`, `docs`, `settings`, `login`, `_next` and dashboard navigation paths are reserved. Normalized `(base_url, path_prefix)` is unique in PostgreSQL. A partial unique index, active-default check and transaction locks protect concurrent default changes and link creation.

For each real domain, the server operator must separately:

1. Configure DNS to reach the appropriate server/load balancer and obtain a valid HTTPS certificate.
2. Configure the reverse proxy's hostname allowlist and route the selected prefix to FastAPI, preserving the entire redirect path, query string and original **Host** header. Keep dashboard/API/health/static routes explicit; don't blindly forward a shared site's root to the redirect catch-all.
3. Test the generated URL, destination query preservation, HEAD behavior and recorded clicks from outside the server. No application request probes DNS or external services.
4. Only after this setup is complete, add the exact origin to backend `LINKSPACE_ROUTED_ORIGINS` (comma-separated), then restart FastAPI. The UI labels this **Configured by server operator — not automatically verified**. Otherwise a custom domain remains **Pending DNS / HTTPS / proxy setup**. This is an operator attestation, not an automatic DNS/certificate check.

Except for the dedicated local-demo rule above, for prefixless links (`https://go.example.com/slug`), first confirm that the origin is dedicated to redirects and has no competing site/application routes. Then explicitly add it to backend `LINKSPACE_ROOT_ORIGINS` and restart FastAPI before creating a Linkspace with an empty prefix. Without that approval the API returns `LINKSPACE_ROOT_UNSAFE` and the UI explains the required action. `LINKSPACE_ROUTED_ORIGINS` additionally controls the production configuration label; root approval alone does not claim DNS/HTTPS is ready. For an isolated local API origin, an operator can approve e.g. `http://127.0.0.1:8000` for development.

The catch-all is registered after explicit FastAPI routes. It accepts only the link's snapshotted origin/path/slug and checks root approval on every root request, without an additional database query on cache hits. It does not trust `X-Forwarded-Host`. Unknown paths and mismatched hosts return 404. `/r/{slug}` remains an unconditional compatibility alias using the original tracking engine. Slugs remain globally unique across Linkspaces. Disabling a link still disables every alias.

Changing DNS or removing old proxy routes can break existing URLs even though database snapshots stay intact; retain routing for all previously issued origins/prefixes. Merely editing the URL configuration does not move existing links.

## Administrative API

- `GET /api/v1/linkspaces`: `q`, `offset`, `limit` (maximum 500), `active_only`, `include_total`; optional `X-Total-Count`.
- `POST /api/v1/linkspaces`: `{name, base_url, path_prefix, is_active, is_default}`.
- `PUT /api/v1/linkspaces/{id}`: complete editable configuration, same fields as POST.
- `DELETE /api/v1/linkspaces/{id}`: only unused and non-default; otherwise 409.

All require the existing admin bearer key. Reporting credentials cannot access or change settings. The Next.js session-authenticated bridge adds keys server-side and enforces same-origin writes. Existing link APIs remain compatible; their response fields `linkspace_id` and `tracking_url` are additive. No link-update endpoint can rewrite a link's stored URL configuration.
