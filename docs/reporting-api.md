# CSV, reporting API and country lookup

## CSV in the dashboard

Click Reports exports **all matching pages**, not only the 100 visible rows. Traffic Analytics can export the trend or selected breakdown. Exports use the applied date/campaign/link filters; breakdown exports also use the selected dimension, and trends use the selected interval.

Files use UTF-8 with BOM for Persian text in Windows Excel, stable English field names, ISO timestamps and ISO country codes. Spreadsheet formula-like text is prefixed with an apostrophe; JSON retains original values. No raw client IP or visitor digest is exported.

Browser downloads are bounded to **50,000 rows per file**, support cancellation and combine server pages without repeated headers. Exceeding the bound produces an explicit message and no partial file. Narrow the filters or use the paginated API for larger datasets. The retention warning also applies to exports.

After pulling updates, restart FastAPI and Next.js (rebuild Next.js if using `npm run start`). For compatibility with older running APIs, the dashboard retries a missing CSV endpoint through its existing JSON reporting endpoint and serializes the same filtered page server-side. Pagination, reporting authentication and spreadsheet escaping are preserved. Authentication failures never trigger a retry. If both endpoints are missing, a localized error directs you to check `TRACKER_API_URL` and restart the services.

## Read-only API access

The existing `REPORT_API_KEY` in the backend environment authorizes reporting only; it cannot create/edit links or campaigns. Keep its **value** in the reporting tool's secure environment or credential store. Do not put it in a URL, browser JavaScript, screenshots or Git. The dashboard's API Guide contains placeholders only. Direct integrations use FastAPI, not the dashboard's private session-cookie bridge.

Base URL locally: `http://127.0.0.1:8000`. Production base URL and HTTPS will be determined during server deployment.

| Endpoint | Purpose / continuation |
|---|---|
| `GET /api/v1/analytics/summary` | Total, human/bot/unknown clicks and visitor-day estimates |
| `GET /api/v1/analytics/trends` | `granularity=day` or `hour`; `offset`, `limit`, `next_offset` |
| `GET /api/v1/analytics/breakdowns` | Campaign/source/medium/device/browser/country/OS/UTM groups; offset pagination |
| `GET /api/v1/analytics/link-comparison` | Repeated `link_ids` parameters |
| `GET /api/v1/exports/clicks` | Raw events; `cursor`, `limit` up to 5000, `next_cursor` |
| `GET /api/v1/exports/daily` | Daily link aggregates; UTC-midnight dates; cursor pagination |
| `GET /api/v1/exports/campaigns` | Campaign performance from daily aggregates |
| `GET /api/v1/exports/links` | Link performance from daily aggregates |
| `GET /api/v1/reporting/links` | ID/slug/campaign/status mapping; `after`, `limit` up to 500, `next_after` |
| `GET /api/v1/reporting/campaigns` | ID/name/archive mapping; same keyset pagination |
| `GET /api/v1/reporting/status` | Safe country-source/configuration and export capabilities; no keys or paths |
| `GET /api/v1/exports/clicks.csv` | CSV event page; up to 5000 rows |
| `GET /api/v1/analytics/trends.csv` | CSV trend page; up to 1000 buckets |
| `GET /api/v1/analytics/breakdowns.csv` | CSV breakdown page; up to 1000 groups |

All analytics/event exports require timezone-aware `start` and `end`, inclusive start and exclusive end, at most 366 days. Example: `start=2026-11-01T00:00:00Z&end=2026-11-05T00:00:00Z`. Optional `campaign_id` and `link_id` filter historical event snapshots. Metadata catalogs do not require dates and show current names; refresh mappings periodically. Some aggregate filters are intentionally rejected when their grain cannot answer them.

CSV pages return `X-Export-Row-Count`, `X-Partial-History` and, if more data exists, `X-Next-Cursor` or `X-Next-Offset`. Repeat the request with that cursor/offset and the **same filters**. Preserve only the first page's BOM/header if combining files. JSON cursors fix an event-time upper cutoff, not a transaction-wide database snapshot. Re-read a small overlap and deduplicate by `(occurred_at, click_id)` for scheduled incremental refresh.

CMD example, assuming the reporting key is already loaded securely into the process environment:

```bat
curl --fail -H "Authorization: Bearer %REPORT_API_KEY%" "http://127.0.0.1:8000/api/v1/exports/clicks?start=2026-11-01T00:00:00Z&end=2026-11-05T00:00:00Z&limit=1000"
```

Python example for a separate reporting service (standard library; credentials come from its environment):

```python
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

base = os.environ.get("TRACKER_API_URL", "http://127.0.0.1:8000").rstrip("/")
params = {"start": "2026-11-01T00:00:00Z", "end": "2026-11-05T00:00:00Z", "limit": 1000}
while True:
    request = Request(
        base + "/api/v1/exports/clicks?" + urlencode(params),
        headers={"Authorization": "Bearer " + os.environ["REPORT_API_KEY"]},
    )
    with urlopen(request, timeout=30) as response:
        page = json.load(response)
    for click in page["items"]:
        # Replace this with incremental writes to your reporting store.
        print(json.dumps(click, ensure_ascii=False))
    if not page["next_cursor"]:
        break
    params["cursor"] = page["next_cursor"]
```

The example prints one JSON event per line without accumulating the dataset. Summary visitor-days are **not distinct people across multiple days**. Daily aggregate exports survive raw retention; detailed country/device/source/hourly reports require retained events.

## Country lookup

Previously, country was recorded only when a configured trusted edge supplied a valid country header. There is now an offline MMDB fallback (DB-IP Country Lite or a compatible MaxMind Country database). It uses the actual client address or a forwarding chain from explicitly trusted proxies. No per-click network lookup occurs, and raw IPs are still not retained.

From the repository root in Windows CMD, install dependencies and the official free country database:

```bat
.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
.venv\Scripts\python.exe scripts\install_geoip.py
```

Restart FastAPI afterward. The default path is `.local/geoip/country.mmdb`, which is ignored by Git. Set `GEOIP_DATABASE_PATH` only when using another local file. The installer preserves an existing file unless `--update` is explicit, verifies HTTPS/gzip/MMDB format, caps download sizes and replaces the database only after validation. It records the release/source and SHA-256. It does not invent or disable verification checks.

For monthly updates, stop the API first on Windows (an open memory-mapped file may prevent replacement), then run and restart:

```bat
.venv\Scripts\python.exe scripts\install_geoip.py --update
```

If the current month's release is not yet available, select an available release, for example `--month 2026-10`. Downloads require outbound HTTPS to `download.db-ip.com`. That domain is blocked by the current managed-cloud policy; **the real production database was not downloaded here**. Installation/decompression/preservation behavior is tested with a licensed synthetic MMDB fixture, which must never be used as a production database.

The free DB-IP Lite data is CC BY 4.0: credit **IP Geolocation by DB-IP (https://db-ip.com)** in uses and downstream reports, and comply with https://creativecommons.org/licenses/by/4.0/. The dashboard includes the attribution alongside country setup information. Database quality/freshness affects results; VPNs reflect the exit IP, not necessarily the person's physical location.

Alternative: configure a trusted edge country header with `COUNTRY_HEADER` and exact `TRUSTED_PROXY_CIDRS`. That edge must overwrite incoming forwarding/country headers. Never trust all Internet addresses. A valid trusted country header takes precedence; otherwise the local database is used. Missing/invalid/unmatched data remains unknown and does not break redirection.

**Localhost, private/reserved IPs and historical unknowns:** `127.0.0.1`, private LAN addresses and similar ranges have no reliable country. Tests on your own computer can therefore still show Unknown after installation. New clicks from real public visitor IPs can be classified. Old unknown records cannot be backfilled because the raw IP was deliberately not stored; no historical values are fabricated or rewritten.
