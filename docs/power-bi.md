# API and Power BI

All reporting endpoints require `Authorization: Bearer <REPORT_API_KEY>`. Use a dedicated report key, HTTPS and an approved gateway/custom connector or other secure credential mechanism. Do not paste credentials into a shareable workbook, source-controlled M file or query-string parameter. A report key can read all organization reporting data in this single-organization version.

## Contracts

| Endpoint | Data source | Pagination |
|---|---|---|
| `/api/v1/analytics/summary` | Raw events, bounded dates | One summary |
| `/api/v1/analytics/breakdowns?dimension=device` | Raw events | `offset`, `limit`, `next_offset` |
| `/api/v1/analytics/trends?granularity=hour` | Raw events | `offset`, `limit`, `next_offset` |
| `/api/v1/analytics/link-comparison?link_ids=UUID&link_ids=UUID` | Raw events | At most 50 selected IDs |
| `/api/v1/exports/clicks` | Raw events without visitor digest | `cursor`, `limit`, `next_cursor` |
| `/api/v1/exports/daily` | Daily link aggregates | `cursor`, `limit`, `next_cursor` |
| `/api/v1/exports/campaigns` | Daily campaign aggregates | `offset`, `limit`, `next_offset` |
| `/api/v1/exports/links` | Daily link aggregates | `offset`, `limit`, `next_offset` |

Every endpoint requires `start` and `end`: timezone-aware ISO timestamps, inclusive start and exclusive end. They are normalized to UTC. For example, `start=2026-11-01T00:00:00Z&end=2026-11-02T00:00:00Z`. Requests span at most 366 days. A plus sign in a positive timezone offset must be URL-encoded; prefer a client parameter encoder or UTC `Z`.

Optional `link_id` and `campaign_id` filters apply to raw reporting. Aggregate endpoints reject filters that cannot be answered from their grain. Aggregate exports require UTC midnight boundaries. Maximum raw/daily page size is 5000; aggregate performance/breakdown page size is 1000. Responses include `items` and continuation metadata.

`/exports/clicks` fixes an upper event-time cutoff on its first page and uses `(occurred_at, click_id)` keyset pagination. Keep the original filters unchanged when following `next_cursor`. A cursor is opaque continuation state, not authorization. Ingestion can commit concurrently; this is not a database-wide snapshot. For finalized historical exports, use closed windows and re-fetch a small overlap with deduplication by `(occurred_at, click_id)`.

Daily aggregates are live and current/yesterday rows may change during paging. Use closed historical UTC days for stable large reports, or re-read recent days. Link/campaign performance sums daily aggregates and returns `oldest_refresh`; an empty response can mean no clicks or aggregation has not run. Inspect worker freshness operationally before treating missing data as final.

## Incremental refresh

1. Define Power BI `RangeStart` and `RangeEnd` parameters in UTC.
2. Map them to the API's `start`/`end` **on the server request**, rather than downloading all history and filtering locally.
3. Fetch all pages for each refresh window.
4. Expand `items` into records and give UUIDs text type, timestamps DateTimeZone and counts Int64.
5. Refresh the current and previous UTC day to capture provisional aggregates. Use daily exports for long-lived summary datasets and raw exports only within retention.
6. Deduplicate raw data using the composite event key when windows overlap.

Power Query does not automatically fold arbitrary REST pagination. Use a fixed `Web.Contents` base URL plus `RelativePath` and `Query` options so gateway configuration remains stable. The following example is for a **non-secret data-fetching function**; `TrackerFetchJson` must be provided by your approved authenticated connector/gateway. It is not a built-in Power Query function:

```powerquery
let
    StartUtc = DateTimeZone.ToText(DateTime.AddZone(RangeStart, 0), "yyyy-MM-ddTHH:mm:ssZ"),
    EndUtc = DateTimeZone.ToText(DateTime.AddZone(RangeEnd, 0), "yyyy-MM-ddTHH:mm:ssZ"),
    FetchPage = (cursor as nullable text) as record =>
        TrackerFetchJson("api/v1/exports/clicks",
            Record.Combine({[start=StartUtc, end=EndUtc, limit="5000"],
                if cursor = null then [] else [cursor=cursor]})),
    Pages = List.Generate(
        () => [Page=FetchPage(null), Continue=true],
        each [Continue],
        each if [Page][next_cursor] = null
            then [Page=[items={}, next_cursor=null], Continue=false]
            else [Page=FetchPage([Page][next_cursor]), Continue=true],
        each [Page][items]),
    Result = Table.FromRecords(List.Combine(Pages))
in
    Result
```

This repository implements the REST interface. A signed Power BI connector and validation inside Power BI Desktop/Service are separate client integration work; they have not been executed in this cloud machine.

## Metric interpretation

- `total_clicks` includes bots and unknown clients; `HEAD` is excluded.
- `human_clicks` means browser-UA heuristic, not proof of a person.
- Daily `estimated_unique_visitors` excludes bots and includes unknown clients with an available digest.
- Multi-day `estimated_visitor_days` counts daily visitors across days. It is not a period-wide distinct-person metric. Summary `estimated_unique_visitors` is null for multi-day windows.
- Zero-campaign UUID in campaign aggregates means unassigned. No destination query credentials or visitor digest appear in standard raw exports.
- Trends omit empty buckets; fill zeros in the BI date/time dimension.
- Detailed reports older than retention can be incomplete and carry `partial_history`. Daily aggregates persist independently.
