# Operations and deployment readiness

For the implemented Docker Compose deployment, local Windows simulation, exact environment settings, backup/restore drill and release rollback, see [Container deployment](deployment.md). `compose.yaml` below still refers to the original development database; `compose.production.yaml` is the separate production stack. Server discovery remains mandatory before any actual deployment.

## Production environment discovery comes first

No remote server was accessed or deployed by this implementation. Before selecting commands or overwriting configuration, inspect the authorized SSH host for OS/version, CPU, RAM, disk, architecture, Python/container support, current services, reverse proxy, TLS ownership, ports, PostgreSQL version and backup tooling. Inspect existing application/service definitions and preserve them. Windows and Linux need different service managers; do not assume either.

Choose native services or containers based on that inspection. Production needs persistent API and worker services, a separately managed PostgreSQL service, automatic reboot/restart behavior, TLS ingress, secrets management and monitoring. The included Compose file is a **local development database**, not a production stack.

## Application processes

- Run migrations once, before starting the new release, using a schema-owner/migration identity.
- Run the API with `uvicorn app.main:app --host <private-listen-address> --port <chosen-port> --no-access-log --no-proxy-headers`. Multiple workers are possible; pool sizes multiply and Prometheus handling needs adjustment (see below).
- Run `python -m app.worker` as a separate supervised process with DDL permission for partition maintenance. `--once` is appropriate for a scheduler if recurring execution is guaranteed.
- Use separate runtime and maintenance database roles for least privilege: runtime needs SELECT/INSERT/UPDATE on management tables, INSERT/SELECT on events and SELECT on aggregates. Maintenance needs ownership/DDL plus aggregate writes. Provision roles on the actual server after reviewing existing permissions. Migration and worker ownership must agree for partition creation/removal.
- Services need a working directory at the checkout/application root, the virtual environment interpreter, environment injection, restart-on-failure and graceful shutdown. Do not depend on an interactive SSH session remaining open.

Application credentials `ADMIN_API_KEY`, `REPORT_API_KEY` and `VISITOR_HMAC_KEY` must be independent random values of at least 32 characters. `.env` is a local convenience; production should inject protected environment values through the chosen service manager/secret store. The example keys are rejected. Never use proxy-substituted outbound API credentials as raw local signing/HMAC keys.

## Container artifact

The Dockerfile builds a non-root API image with hash-verified dependencies. Normal builds use `docker build -t marketing-tracker .`. In this managed cloud, supply the supported combined CA bundle as a BuildKit secret if network trust requires it; never disable TLS verification. No `.env` or test keys enter the image.

The same image can run migrations (`alembic upgrade head`) and the worker (`python -m app.worker`) using different credentials and commands. Supply environment variables securely and connect to an external PostgreSQL service. Running the image is not a complete production deployment; persistence and ingress belong to the inspected server's operating environment.

## Ingress controls

- Terminate TLS at a trusted proxy; bind the application port privately.
- Configure exact `TRUSTED_PROXY_CIDRS`; never trust all Internet addresses.
- Strip/overwrite incoming forwarding and country headers at the edge. Set `COUNTRY_HEADER` only if that edge supplies a reliable ISO country code.
- Configure request/header size limits and endpoint-specific rate limits at the ingress. Administrative routes should also have an IP allowlist/VPN where practical. Protect `/docs` and `/openapi.json` at ingress if schema exposure is unwanted.
- Keep URL/referrer/IP access logging disabled or sanitized. Never log bearer credentials. Error monitoring must scrub request URLs, headers and database payloads before export.
- Static bearer keys are suitable for a small single-organization backend; key rotation, distribution and revocation are operational responsibilities. Multi-user deployments should add an identity provider and roles before opening access broadly.

## Health, logs and alerting

`/health/live` checks process liveness. `/health/ready` verifies migration metadata and the current month's event partition. It does not prove every feature or the worker is healthy.

`/metrics` is admin-protected and includes redirect outcome counters and redirect latency. Current metrics are **process-local**; use one API process per container and scrape each instance, or configure Prometheus multiprocess mode separately before using multiple Uvicorn workers in one container. Do not aggregate process-local counters by randomly load-balancing scrape requests.

Alert on:

- Any sustained `unrecorded` or `resolution_failed` redirect outcomes.
- Rising p95/p99 latency and connection-pool exhaustion.
- API 5xx rates from ingress, database storage/WAL growth and backup age.
- Stale `aggregation_state.refreshed_at` (e.g. more than five worker intervals).
- Missing future partitions and repeated `maintenance_failed` logs.

Application errors log event names and error types without query parameter payloads. Configure log rotation/retention in the chosen service manager. External error-monitoring credentials and provider selection remain deployment configuration; no unconfigured third-party transmission is enabled.

## Backups and restore

Select a PostgreSQL-supported backup strategy based on recovery targets: scheduled `pg_dump` custom-format backups for a small deployment; physical backups plus WAL archiving for tighter recovery-point objectives. Backups must be encrypted, access-controlled, copied off-host and retained on a documented schedule. Monitor exit codes and backup age.

Use PostgreSQL client tools compatible with the server. Load credentials through a protected password file or secret injection, never a password argument. A logical backup operation is `pg_dump --format=custom --file=<protected-backup-path> --dbname=<database-name>` with connection settings supplied securely. This command is a template: paths, scheduling, identity and OS must be established on the server first.

Restore into an isolated empty database using `pg_restore`, apply any pending migration, start an isolated application, run the smoke test and compare expected historical counts. A successful backup command alone does not prove recoverability. Avoid `--clean` against an existing database without explicit approval. Docker volume persistence is not a backup.

No remote scheduled backup or restore test is claimed complete in this repository.

## Release and rollback

Record application revision, lockfile, migration revision and image digest. Test migrations on a recent restored copy before rollout; take a verified backup. Keep the previous artifact. Roll back application code only when compatible with the live schema. Migration downgrade is destructive and is not an automatic release rollback strategy.

Retain visitor HMAC keys securely for the lifetime needed to interpret the chosen privacy window; never include secrets in build layers or repository history. Backups and monitoring data remain subject to the privacy/retention policy.
