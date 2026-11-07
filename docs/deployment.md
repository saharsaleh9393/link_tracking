# Container deployment and Windows production simulation

This is a single-server Docker Compose deployment. It reuses FastAPI, Next.js, PostgreSQL 17, the worker and migration `0003`. No server was accessed, DNS changed, existing development environment overwritten or real HTTPS certificate issued while preparing it. Inspect the target OS, architecture, RAM/disk, existing services, occupied ports, Docker support, firewall, DNS and backup ownership **before choosing server commands**. Review existing proxy/service configuration before installation; never replace it blindly.

## Layout and boundaries

- `compose.yaml` remains the original local database workflow for native Windows development. Its data volume and port 5432 are separate.
- `compose.production.yaml` provides database, one API process, worker, standalone Next.js, Caddy, and explicit `ops` migration/backup/restore jobs. API/web run as non-root, with read-only roots, writable temporary directories, dropped capabilities and graceful shutdown. Caddy has only the bind-port capability. Base images are pinned by digest; Python hashes and `npm ci` lock dependencies.
- Only Caddy publishes ports. Database network is internal; web cannot reach it. API/web share a private edge network. Caddy additionally has a public network for ACME. Static proxy IP `.2` is outside the upper-half dynamic pool; the API trusts **only that IP /32**. Choose a different private /24 and its upper /25 if it conflicts with an existing network/VPN.
- PostgreSQL bootstrap creates separate non-superuser schema-owner and runtime roles. API uses `linkspace_app`; migration and worker use `linkspace_owner` for partition DDL. API has campaign/link SELECT/INSERT/UPDATE, destination SELECT/INSERT, Linkspace CRUD, event/audit INSERT/SELECT, aggregate/version SELECT, and no schema DDL or hard deletion of links/campaigns/destinations. Bootstrap superuser credentials are mounted only to PostgreSQL. Role bootstrap runs only on a new database volume. Existing separately managed databases need a reviewed role/grant setup; do not run bootstrap against existing databases blindly.
- Persistent volumes hold PostgreSQL and Caddy certificate/config state. `down` retains volumes. **Never use `down -v`, volume pruning or initdb as an update/rollback step.** Docker secrets are read-only file mounts, not encrypted vault storage. Protect their host directories and all backups. No real secrets are in either image or example env file. Review image security advisories and refresh pinned digests through tested releases before deployment and on a patch schedule.

## Windows CMD: isolated HTTP simulation

Requires Docker Desktop using **Linux containers**, Docker Compose **2.24.4+**, and Python 3.12+. Use the repository root. Existing PostgreSQL/Laragon and native development can stay running; the simulation uses a separate project, database volume and port **8080**, with no database port publishing.

Generate `.env.simulation` and independent keys/passwords under `.local/deployment/linkspace-sim/secrets`. The helper refuses to overwrite existing inputs, including `.env`. It never prints secrets. Read `dashboard_password` privately to sign in. On Windows, restrict that directory's ACL to your account and administrators; POSIX chmod does not replace Windows ACLs.

```bat
py -3.12 deploy\init_deployment.py --mode simulation
```

If 8080 or the subnet is occupied, choose both before initialization with `--port 8088 --subnet 172.30.60.0/24`. Re-running the initializer is deliberately not a password-reset mechanism. Do not delete secret files for an existing database: PostgreSQL will not reset role passwords on restart. Existing secret rotation requires coordinated database password changes and service restarts.

Validate and build immutable-input images. No credentials are needed at build time:

```bat
docker compose --env-file .env.simulation -f compose.production.yaml -f compose.simulation.yaml config --quiet
docker compose --env-file .env.simulation -f compose.production.yaml -f compose.simulation.yaml build api web
```

Start the empty database, run migrations once explicitly, then start services. A normal reboot/restart does not run migrations. The API checks schema/partition readiness before serving; proxy/web wait for API health. The worker starts after API readiness and reports a heartbeat after successful maintenance.

```bat
docker compose --env-file .env.simulation -f compose.production.yaml -f compose.simulation.yaml up -d --wait db
docker compose --env-file .env.simulation -f compose.production.yaml -f compose.simulation.yaml --profile ops run --rm migrate
docker compose --env-file .env.simulation -f compose.production.yaml -f compose.simulation.yaml up -d --wait
```

Open **http://panel.localhost:8080**. Links use **http://go.localhost:8080**. Chromium resolves special-use `.localhost` names to loopback; if your Windows resolver does not, add `127.0.0.1 panel.localhost go.localhost` to `C:\Windows\System32\drivers\etc\hosts` using an administrator editor. These URLs work on this computer only. Simulation overrides bind only `127.0.0.1`, publish HTTP only, disable ACME/TLS and use non-Secure HttpOnly/SameSite=Strict session cookies. Never use the simulation override for a real public deployment.

Run smoke checks. `--write` explicitly authorizes labeled synthetic campaigns, settings, links and retained clicks; created links are soft-deleted and the campaign archived afterward. No historical data is deleted. The connection override avoids Windows resolver differences while preserving public Host/Origin headers. Requests do not follow external destinations.

```bat
py -3.12 deploy\smoke.py --env-file .env.simulation --connect-url http://127.0.0.1:8080 --write
docker compose --env-file .env.simulation -f compose.production.yaml -f compose.simulation.yaml ps
docker compose --env-file .env.simulation -f compose.production.yaml -f compose.simulation.yaml logs --tail 100 api worker web proxy
```

Smoke checks cover login/session flags, unauthenticated and cross-origin rejection, default link creation, tracking and HEAD counts, analytics/raw reports, custom prefixes, shared dashboard `/r`, dedicated root links, query preservation and public reporting/private management boundaries. Prefixless production checks run only after explicit root approval.

Stop and resume without removing data:

```bat
docker compose --env-file .env.simulation -f compose.production.yaml -f compose.simulation.yaml down
docker compose --env-file .env.simulation -f compose.production.yaml -f compose.simulation.yaml up -d --wait
```

Native Windows development (`compose.yaml`, Python virtualenv, `npm run dev`) remains supported. It does not load `.env.simulation` or production secrets. The existing native optimized frontend commands remain in README; the container build alone enables `LINKSPACE_STANDALONE=true` and uses standalone `server.js`; normal native builds keep `npm run start` supported without standalone warnings.

## Environment and secrets

`.env.production.example` contains **no credentials**. Run `python3 deploy/init_deployment.py --mode production` to create private `.env.production` and secret files, then edit only the new deployment env file for the real server. Example production domains are rejected by application startup until replaced.

| Setting | Meaning |
|---|---|
| `APP_ENV` | `production` for HTTPS, exact trusted hosts and Secure cookies; `simulation` only for the local HTTP override |
| `RELEASE_TAG` | Exact Git SHA/release identifier for both app images; retain previous images and record image digests |
| `DASHBOARD_ORIGIN` | Exact external browser origin for CSRF/same-origin checks, including nonstandard port if used |
| `PUBLIC_BASE_URL` | External tracking origin, used to seed/freeze legacy URLs during migration; preserve the previous public value when upgrading an existing database |
| `DASHBOARD_SITE`, `TRACKING_SITES` | Caddy listen site addresses; comma-separated tracking sites. Real deployment uses HTTPS domains on 443. Simulation sites omit external :8080 because Caddy listens internally on 80 |
| `DASHBOARD_TRACKING_PATHS` | Only shared dashboard paths sent to FastAPI, default `/r/* /go/*`; add explicitly configured custom prefixes here |
| `HTTP_ALLOWED_HOSTS` | Exact hostname list, no schemes/ports/wildcards; include API/health internal hosts plus every configured ingress hostname |
| `DASHBOARD_SECURE_COOKIES` | Must be `true` in production; false only in HTTP simulation |
| `ACME_EMAIL` | Real operator contact for certificate issuance |
| `LINKSPACE_ROUTED_ORIGINS` | Exact origins after DNS/TLS/proxy checks; operator attestation, not automatic verification |
| `LINKSPACE_ROOT_ORIGINS` | Explicit dedicated redirect origins allowed at root; **dashboard root is always blocked** |
| `EDGE_SUBNET`, `EDGE_DYNAMIC_RANGE`, `PROXY_IP` | Non-conflicting private /24, upper /25 allocation range, fixed proxy IP outside that pool. Compose derives trusted /32 automatically |
| `BIND_ADDRESS`, `HTTP_PORT`, `HTTPS_PORT` | Server ingress binding; production typically 0.0.0.0:80/443. Simulation override always binds loopback and publishes HTTP only |
| `SECRETS_DIRECTORY` | Protected generated directory; never commit/copy into images |
| `POSTGRES_DB` | Database initialized on a new volume; must agree with the mounted database URL secrets |
| `BACKUP_DIRECTORY`, `BACKUP_UID/GID` | Protected host backup directory and writing identity; helper chooses current Linux UID/GID or Windows Docker defaults |
| `RAW_RETENTION_DAYS`, `WORKER_INTERVAL_SECONDS`, `DB_POOL_SIZE/MAX_OVERFLOW` | Existing retention/maintenance/pool settings; size them after measuring server capacity and click load |
| `GEOIP_DIRECTORY` | Optional host directory containing `country.mmdb`, mounted read-only. No IP lookup network calls; missing database remains Unknown |

The helper writes `postgres_password`, `owner_password`, `app_password`, `app_database_url`, `owner_database_url`, `admin_api_key`, `report_api_key`, `visitor_hmac_key`, `dashboard_password`, `dashboard_session_secret`. Secrets are independent random tokens. Their parent project/secrets directories are owner-only on POSIX; files are 0644 *inside those protected directories* so different non-root container UIDs can read selected read-only mounts. Verify Windows ACLs and server ownership. Only selected secrets reach each service. Do not print `docker compose config` or `docker inspect` environment dumps when adding your own inline secret overrides; use `config --quiet`.

Backend `_FILE` settings are additive: native development can keep its existing env values. Using an explicit inline env value and `_FILE` for the same secret is rejected. Database role password rotation must update PostgreSQL and both relevant mounted secret/DSN files together. Rotating session secrets logs everyone out. Keep visitor HMAC key handling consistent with the privacy window.

## Domains, routes, forwarding and authentication

Use a dashboard hostname and one or more dedicated tracking hostnames. Caddy preserves the **original Host, including external port**, full path and query. It overwrites incoming X-Forwarded-For/Proto/Host from the actual socket/request, removes `Forwarded` and untrusted country headers, and never uses caller-supplied forwarding chains. Keep Uvicorn `--no-proxy-headers`; custom tracking needs the physical proxy peer. The application accepts forwarded scheme only from the exact proxy IP and retains the physical peer for address/country checks. If another load balancer/CDN is added later, explicitly review both trust boundaries; don't widen trusted ranges to all addresses or trust incoming country headers blindly.

On dedicated tracking sites, all valid prefixes and root slugs go to the existing FastAPI redirect engine. `/r/{slug}` stays a compatibility alias. Direct `/api/v1/analytics/*`, `/exports/*`, `/reporting/*` allow authenticated read-only integration requests; raw administrative API, docs, metrics and health paths are blocked at this ingress. Dashboard API calls use the session-authenticated Next.js bridge, server-side bearer keys and exact `DASHBOARD_ORIGIN` for writes. There is no permissive CORS middleware; cross-origin browser API calls are not enabled.

For a main domain shared with the dashboard, select a configured prefix and add its wildcard path to `DASHBOARD_TRACKING_PATHS`. Dashboard root redirects are rejected even if mistakenly put in the root allowlist. Prefer a dedicated subdomain for prefixless links. Additional custom domains require DNS, HTTPS certificate reachability, `TRACKING_SITES`, `HTTP_ALLOWED_HOSTS`, a deliberate `up -d --force-recreate proxy` (admin reload API is disabled), and then the appropriate Linkspace/routing attestation. Recreating the single proxy causes a brief ingress interruption; choose a maintenance window. Saving a Linkspace alone does not configure a domain. Keep **all historical** origins/prefixes routed when changing defaults; snapshots never rewrite old links.

Restrict dashboard access with a VPN/firewall/IP policy if appropriate. The existing shared-password dashboard and static API keys are single-organization authentication, not multi-user RBAC/SSO. Login has the existing process-level limiter; don't run multiple dashboard replicas or expose high-risk admin access without reviewing ingress/distributed rate limiting and identity requirements. No new external monitoring or credential transmission is enabled automatically.

## Linux server deployment (only after environment inspection)

Confirm a supported Linux host with Docker Engine/Compose, adequate measured capacity, synchronized time, protected SSH, working outbound ACME HTTPS, and inbound ports 80/443. Configure Docker to start after reboot (`systemctl enable docker` only on a confirmed systemd installation). Existing firewall/proxy rules must be reviewed before changes. If another service owns 80/443, integrate deliberately or assign separate host/IP; do not stop it blindly.

1. Check out the reviewed feature/release SHA. Initialize production inputs, set real domains/email and `RELEASE_TAG` to that SHA. Protect secret/backup directory ownership. Configure real DNS A/AAAA records correctly, including IPv6 reachability; remove broken AAAA records through your normal DNS process.
2. Validate config, build `api web`, and record image IDs/digests. For prebuilt images, load/pull those exact artifacts and use `--no-build`. Do not use mutable `latest` for a release.
3. Start `db`, explicitly run `migrate`, then start all services using the commands below. For existing data, first take and verify a backup and test migration on a restored copy. Existing external PostgreSQL data is not automatically imported or remounted.
4. Verify real TLS, cookie flags, trusted host rejection, all public paths and external smoke checks. Mark routed/root origins only after successful verification; restart API/worker after changing their environment.

```sh
python3 deploy/init_deployment.py --mode production
# Edit .env.production and review protected files before continuing.
docker compose --env-file .env.production -f compose.production.yaml config --quiet
docker compose --env-file .env.production -f compose.production.yaml build api web
docker compose --env-file .env.production -f compose.production.yaml up -d --wait db
docker compose --env-file .env.production -f compose.production.yaml --profile ops run --rm migrate
docker compose --env-file .env.production -f compose.production.yaml up -d --wait --no-build
python3 deploy/smoke.py --env-file .env.production --write
```

No simulation connection override is permitted in production smoke checks: normal DNS and certificate verification must work. Caddy obtains/renews certificates and retains ACME state in its data volume. Automatic HTTPS and HSTS apply only to production config. Test expiration/renewal alerts and off-host persistence of certificate state according to your recovery plan. Do not enable wildcard/on-demand certificate issuance for arbitrary UI-entered domains.

For **Windows Server**, first identify the available virtualization/container platform. These are Linux images; Windows containers cannot run this stack. Docker Desktop is suitable for laptop simulation, not an unattended Windows Server production service. Use an approved Linux VM with Docker Engine (then follow the Linux recipe) or a separately reviewed supported Linux-container platform. Ensure its VM/container service starts at reboot and its persistent disks/backups survive host maintenance. Native Windows development remains unchanged; no Windows host services are replaced by this repository.

## Backups, restore drill and rollback

Backup job connects over the private network as schema owner, writes an atomic custom-format PostgreSQL dump to the protected backup directory, and never puts passwords on the command line. Schedule it with the confirmed server's scheduler (systemd timer/cron or Windows Task Scheduler on the approved host platform), monitor failures/backup age, encrypt copies and send them off-host. A Docker volume is not a backup. Logical dumps provide point-in-time contents at dump start, not continuous WAL recovery; add a measured WAL/PITR solution if recovery objectives require it.

```sh
docker compose --env-file .env.production -f compose.production.yaml --profile ops run --rm backup
```

For Windows simulation, add `-f compose.simulation.yaml` and use `.env.simulation` in that command. Filenames are printed, never credentials. Keep the backup's release SHA, migration version and protected matching settings/keys in the recovery inventory; the database dump does not include application secrets.

Restore **only into a separate, empty** `restore_*` database/project. The restore job refuses normal database names and destinations containing public tables. It never uses `--clean`, overwrites an existing database or changes the original volume. Example Windows CMD drill (replace the backup basename with an actual file; original simulation can keep running):

```bat
py -3.12 deploy\init_deployment.py --mode simulation --env-file .env.restore --project linkspace-restore --port 8081 --subnet 172.30.51.0/24 --database restore_check
docker compose --env-file .env.restore -f compose.production.yaml -f compose.simulation.yaml up -d --wait db
docker compose --env-file .env.restore -f compose.production.yaml -f compose.simulation.yaml --profile ops run --rm -e BACKUP_FILE=YOUR_BACKUP.dump restore
docker compose --env-file .env.restore -f compose.production.yaml -f compose.simulation.yaml --profile ops run --rm migrate
docker compose --env-file .env.restore -f compose.production.yaml -f compose.simulation.yaml up -d --wait --no-build
py -3.12 deploy\smoke.py --env-file .env.restore --connect-url http://127.0.0.1:8081 --prepare-simulation-default --write
```

Compare historical counts/checksums **before starting the worker**, because normal configured retention/aggregation then resumes. Restored Linkspace snapshots retain original URLs; do not rewrite them to test ports. The explicit simulation-only flag selects a test default for the restored copy without rewriting historical URLs; it is refused in production. Normal smoke checks fail if the actual default tracking URL points to a different origin. Record restore duration and successful application reads, not just `pg_restore` exit status. For Linux use `python3` and the same Compose commands. Real recovery/failover is a separate approved maintenance operation after the drill.

Before updates: record current image IDs, Git/migration SHA, env/config versions, encrypted secrets and backup; stop write-facing services during the migration window if required. Build the new SHA-tagged images first, take a backup, stop `proxy web api worker` (keep db), run the new image's `migrate`, then `up -d --wait --no-build`. Migration lock timeouts fail rather than dropping data. Review future migrations for compatibility and grant additions in `deploy/runtime.py`.

Rollback application images only if the prior code supports the live schema: set `RELEASE_TAG` to the retained prior tag and `up -d --wait --no-build`. Don't rebuild an old tag from a new checkout. There is **no automatic schema downgrade**; `0003` already refuses downgrade that would discard custom URLs. If the schema is incompatible, plan a controlled restore/cutover from a verified backup and account for clicks written after it. Never restore over live data or assume an application rollback undoes a database migration.

## Logs, health and monitoring

Container JSON logs rotate at 10 MB × 5 per service. API/worker container logs retain only fixed event names and exception types, not traceback payloads/URLs/SQL parameters. Uvicorn access logging stays off. Caddy access/request-error logging is disabled to avoid logging full queries/referrers/IPs; use safe app metrics and status monitoring rather than enabling raw request logs. PostgreSQL statement/parameter logging is disabled and errors use terse output. Next.js bridge sanitizes upstream errors and does not log keys or login bodies.

Readiness covers schema/current partition; worker heartbeat fails when maintenance stops succeeding. Health status alone does not restart an unhealthy process: restart policies restart exited processes, while monitoring/operators handle persistent unhealthy states. Alert on unhealthy services, worker lag, disk/WAL growth, backup age, certificate expiry, `click_recording_failed` and redirect counters. `/metrics` stays admin-protected and private: scrape through a reviewed private-network/VPN path, without publishing the API port. One API process per container preserves existing process-local metric semantics. External error monitoring must scrub URLs, headers, credentials and database values before export; provider configuration is a manual step.

Managed cloud builds may need a combined CA passed as BuildKit secret `proxy_ca`; Dockerfiles support it without disabling TLS or baking it into runtime images. This is a testing-environment requirement, not a credential or mandatory setting for ordinary Windows/Linux Docker builds.

Optional GeoIP files are non-secret but must be readable by the API UID (10001): make the mounted directory traversable and country.mmdb readable. Keep secret directories owner-only; do not apply GeoIP permissions to secrets.

For an upgrade from a pre-0003 database whose issued URLs used HTTP, preserve that original origin during the one-time snapshot migration. An explicitly reviewed migration invocation can override `APP_ENV=development` and `PUBLIC_BASE_URL` to the original HTTP value for that one-off owner job; do not relax the normal production services. Then use HTTPS production settings and select a new HTTPS Linkspace default. Keep legacy origins/proxy routes available, and test the process on a restored copy first.
