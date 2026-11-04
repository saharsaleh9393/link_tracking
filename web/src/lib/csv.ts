// CSV transport compatibility only. Filtering, attribution and counting stay in FastAPI.
const counters = [
  "total_clicks",
  "human_clicks",
  "bot_clicks",
  "unknown_clicks",
  "estimated_visitor_days",
];
const schemas: Record<string, string[]> = {
  "exports/clicks.csv": [
    "occurred_at",
    "click_id",
    "link_id",
    "campaign_id",
    "destination_id",
    "link_version",
    "device",
    "os",
    "browser",
    "classification",
    "bot_reason",
    "ruleset",
    "country",
    "referrer_origin",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
  ],
  "analytics/trends.csv": ["bucket", ...counters],
  "analytics/breakdowns.csv": ["value", ...counters],
};
export function jsonReportPath(path: string) {
  return Object.hasOwn(schemas, path) ? path.slice(0, -4) : null;
}
export function reportCsv(path: string, report: unknown) {
  const fields = schemas[path];
  if (
    !fields ||
    !report ||
    typeof report !== "object" ||
    !("items" in report) ||
    !Array.isArray(report.items)
  )
    throw Error("Invalid report");
  const items = report.items as Record<string, unknown>[];
  const cell = (value: unknown) => {
    let text = value === null || value === undefined ? "" : String(value);
    if (
      typeof value === "string" &&
      (/^[\s]*[=+\-@]/.test(text) || /^[\t\r\n]/.test(text))
    )
      text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  };
  const body =
    "\ufeff" +
    [
      fields.map(cell).join(","),
      ...items.map((row) => fields.map((key) => cell(row[key])).join(",")),
    ].join("\r\n") +
    "\r\n";
  const page = report as Record<string, unknown>;
  return {
    csv: new TextEncoder().encode(body).buffer,
    status: 200,
    csvHeaders: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": 'attachment; filename="report.csv"',
      "X-Export-Row-Count": String(items.length),
      "X-Partial-History": String(page.partial_history === true),
      ...(typeof page.next_cursor === "string" && page.next_cursor
        ? { "X-Next-Cursor": page.next_cursor }
        : {}),
      ...(typeof page.next_offset === "number"
        ? { "X-Next-Offset": String(page.next_offset) }
        : {}),
    },
  };
}
