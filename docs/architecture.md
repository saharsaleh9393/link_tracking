# Architecture and data contracts

## Runtime

FastAPI synchronous handlers run in a thread pool. SQLAlchemy uses a bounded PostgreSQL connection pool per process. A separate worker maintains monthly partitions and daily link/campaign aggregates. No message broker is required.

The public route is `GET /r/{slug}`. Management and reporting routes require bearer credentials; reporting credentials cannot manage links. The initial deployment serves one organization. Multi-tenant ownership and per-user RBAC are outside this version.

## Redirect write path

1. Validate bounded slug and UTM input.
2. Resolve the link and its active immutable destination in one joined query, or use a bounded process-local TTL cache.
3. Reject inactive, deleted or expired links with 410; missing links return 404.
4. Generate a click UUID, UTC timestamp, effective UTM snapshot and request classifications.
5. Commit one event before returning 302. Database statement timeout is 250 ms for the write transaction, lock timeout 100 ms. These are statement bounds, **not a guarantee on total request latency**; connection acquisition, parsing and commit also take time.
6. Send `Cache-Control: no-store`. `HEAD` resolves the destination but does not count a click.

If event persistence fails, a resolved destination still redirects. Increment `tracker_redirects_total{outcome="unrecorded"}` and log only the exception type. If resolution fails with no cached configuration, return 503. There is no claim of lossless delivery during outages.

The cache TTL defaults to two seconds. Local edits invalidate the current process's cache; other instances can use stale configuration until expiry. Expiration timestamps are checked on every request, including cache hits. Set TTL to zero for database-backed status checks on every redirect. A shared invalidation mechanism is a future option if immediate revocation across instances becomes necessary.

The service does not fetch destinations or call remote geolocation APIs. URL validation is syntax/policy validation, not a reputation or DNS-rebinding defense for a future URL-fetching service. For organizations that need strict destination control, configure exact `DESTINATION_ALLOWED_HOSTS` and restrict management access.

## Tables and integrity

| Table | Purpose |
|---|---|
| campaigns | Editable name and archive flag |
| links | Unique reserved slug, campaign, UTM defaults, version and lifecycle |
| link_destinations | Immutable destination versions; one active destination per link |
| click_events | Time-partitioned historical event snapshots |
| daily_link_stats | UTC daily counters and non-bot estimated unique visitors per link |
| daily_campaign_stats | UTC daily campaign counters, deduplicated across links |
| aggregation_state | Historical processing cursor and last successful aggregation time |
| audit_events | Administrative actions; never records full destination URLs or credentials |

UUIDs are application-generated. `click_events` uses `(occurred_at, click_id)` as its primary key because PostgreSQL partitioned unique keys must include the partition key. Events have no foreign keys on their high-volume insert path. Links and destinations use a deferred composite foreign key so an active destination must belong to its link. Slugs remain reserved after soft deletion.

The zero UUID in **campaign aggregates only** means no campaign. Campaign IDs created by the application are random nonzero UUIDs. Historical campaign/UTM/destination snapshots remain unchanged after edits.

Link updates use `expected_version` plus row locking to reject lost updates. Adding a destination does not activate it; PATCH the link's `active_destination_id` explicitly.

## UTM policy

Tracking-request UTM values override link defaults for event attribution. Each value is bounded to 200 characters. Unknown query parameters are discarded. Forwarding is opt-in. Existing destination query bytes, including signatures and WhatsApp text, remain untouched; absent UTM keys may be appended. Destination-owned UTM keys win for the outgoing URL, while event attribution follows the tracking-request policy. Leave forwarding disabled for signed URLs.

## Privacy and traffic classification

- No raw IP, full User-Agent or full referrer is stored in event tables.
- A daily HMAC uses the transient normalized client IP, coarse browser/OS/device and UTC day. It detects repeat patterns, not people. NAT merges visitors and changing networks can split them.
- HMAC keys and IP-derived digests are sensitive. Rotating the deployment key during a UTC day changes estimates; rotate deliberately and document the boundary.
- Known User-Agent signatures identify many bots and social previews. Recognized browser UAs are classified as human heuristically; spoofing and sophisticated automation are not reliably detected. Unrecognized clients are unknown. Bot classification is versioned (`ua-v1`). Rate-based bot scoring is not implemented.
- Daily unique visitors exclude bots but include unknown clients. Multi-day reports return visitor-days; they do not claim cross-day unique people. Summing link-level uniques also overcounts across links; campaign aggregates deduplicate independently.
- Referrers are reduced to scheme, hostname and port; credentials, paths and queries are removed.
- Forwarding headers are ignored unless the socket peer belongs to configured trusted CIDRs. The server starts with Uvicorn proxy-header rewriting disabled so trust decisions use the actual peer. Walk X-Forwarded-For from the trusted edge towards the first untrusted address.
- Country headers are used only from a trusted edge that **overwrites** client-supplied country headers. Unknown or invalid ISO codes remain null. Country is network-derived and is not proof of residence.

Disable or sanitize reverse-proxy and hosting access logs too. This application starts with access logging disabled; infrastructure can otherwise retain raw IPs and URLs independently. UTM values and destination parameters can contain personal data supplied by administrators: organizational policy must forbid that usage.

GDPR compliance requires a lawful basis, notice, retention policy and data-subject procedures. Pseudonymization is not anonymization. No cookies or browser fingerprinting scripts are used.

## Aggregation and retention

The worker rebuilds complete UTC-day buckets under a PostgreSQL advisory lock and a repeatable-read snapshot. Replacement is atomic; retries do not increment counters twice. It refreshes today and yesterday every cycle and catches up up to 31 historical days per run. Ingestion uses server time; arbitrary historical imports require an explicit affected-day rebuild strategy.

Current and previous-day aggregates are provisional. Empty days are omitted. Hourly trends and dimension breakdowns are computed from raw events with time-bounded queries; persistent hourly/dimension cubes are deliberately deferred until measured need.

Raw retention drops whole monthly partitions only after the aggregation cursor covers them. `RAW_RETENTION_DAYS=90` is a minimum window: effective retention can extend by up to one calendar month, or longer if maintenance is failing. Aggregate and audit data currently have no automatic expiry; set an organizational policy before production. Backups have their own retention obligations. Do not lower retention casually.

Daily link and campaign performance exports survive raw retention. Detailed source/device/country/hourly reports are limited to retained raw history and expose `partial_history` conservatively. Daily link exports cannot retrospectively filter campaign ownership; use campaign aggregates for historical campaign reporting.

## Scaling and failure limits

Pool sizes multiply with API workers and worker processes. Leave headroom below PostgreSQL's connection limit. A bounded cache removes repeat lookup queries; each counted click still writes one row. Index only common filters to control write amplification.

Analytics and collection initially share PostgreSQL. Reporting statements have a default five-second timeout, exports cap page sizes, and date ranges cap at 366 days. These controls bound resource use but do not guarantee workload isolation. Separate reporting pools/replicas, shared caching, export jobs or durable buffering should follow measured bottlenecks.

At-least-once client retries are separate click requests and receive new IDs; this is intentional click counting, not per-person attribution. FastAPI background tasks are not used for event durability.
