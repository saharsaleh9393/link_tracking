"use client";
import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useResource, queryString } from "@/lib/client";
import { initialRange, reportRange } from "@/lib/utils";
import type {
  Breakdown,
  Summary,
  Trend,
  ListPage,
  Link,
  Campaign,
  Counts,
} from "@/lib/types";
import { Heading, Loading, ErrorNotice, Empty, DataTable } from "../shared";
import { Card, CardContent } from "../ui/card";
import { Label } from "../ui/label";
import { Button } from "../ui/button";
import { ReportFilters, type ReportSelection } from "../report-filters";
import { Chart } from "../charts";
import { CsvDownload } from "../csv-download";
import { CountryNotice } from "../reporting-help";
function initial() {
  const range = initialRange();
  return {
    params: reportRange(range.from, range.to),
    links: [],
    campaigns: [],
  } as ReportSelection;
}
export function AnalyticsView() {
  const t = useTranslations(),
    locale = useLocale();
  const [selection, setSelection] = useState(initial),
    [interval, setInterval] = useState("day"),
    [dimension, setDimension] = useState("campaign"),
    [ids, setIds] = useState<string[]>([]),
    [offset, setOffset] = useState(0);
  const summary = useResource<Summary>("analytics/summary", selection.params),
    trend = useResource<Trend>("analytics/trends", {
      ...selection.params,
      granularity: interval,
      limit: 1000,
    });
  const breakdown = useResource<Breakdown>("analytics/breakdowns", {
    ...selection.params,
    dimension,
    limit: 20,
    offset,
  });
  const links = useResource<ListPage<Link>>("links", {
      limit: 500,
      include_total: true,
    }),
    campaigns = useResource<ListPage<Campaign>>("campaigns", {
      limit: 500,
      include_total: true,
    });
  const names = new Map([
    ...(links.data?.items || []).map((l) => [l.id, l.slug] as const),
    ...(campaigns.data?.items || []).map((c) => [c.id, c.name] as const),
    ...selection.links.map((l) => [l.id, l.slug] as const),
    ...selection.campaigns.map((c) => [c.id, c.name] as const),
  ]);
  const comparisons = useResource<{ items: (Counts & { link_id: string })[] }>(
    "analytics/link-comparison",
    {
      ...selection.params,
      link_id: null,
      link_ids: ids.length ? ids : ["00000000-0000-0000-0000-000000000000"],
    },
  );
  function label(value: string | null) {
    if (!value) return t("unknown");
    if (dimension === "campaign")
      return names.get(value) || t("campaignOutside");
    if (dimension === "device" && t.has(value)) return t(value);
    if (dimension === "country") {
      try {
        return (
          new Intl.DisplayNames([locale], { type: "region" }).of(value) || value
        );
      } catch {
        return value;
      }
    }
    return value;
  }
  const dimensions = [
    "campaign",
    "source",
    "medium",
    "device",
    "browser",
    "country",
    "os",
    "utm_campaign",
    "utm_content",
    "utm_term",
  ];
  function dimensionLabel(value: string) {
    return t(
      value === "campaign"
        ? "campaignPerformance"
        : value.startsWith("utm_")
          ? value + "_dimension"
          : value,
    );
  }
  return (
    <>
      <Heading
        title={t("analytics")}
        description={t("analyticsDescription")}
        action={
          <CsvDownload
            key={queryString({ ...selection.params, granularity: interval })}
            path="analytics/trends.csv"
            params={{ ...selection.params, granularity: interval }}
            label="exportTrends"
            filename="click-trends"
          />
        }
      />
      <ReportFilters
        onApply={(value) => {
          setSelection(value);
          setOffset(0);
        }}
      />
      <ErrorNotice code={summary.error || trend.error || breakdown.error} />
      {summary.loading ? (
        <Loading />
      ) : (
        summary.data && (
          <>
            <div className="mb-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {[
                "total_clicks",
                "human_clicks",
                "bot_clicks",
                "estimated_visitor_days",
              ].map((key, i) => (
                <Card key={key}>
                  <CardContent>
                    <p className="text-xs text-muted-foreground">
                      {t(
                        [
                          "totalClicks",
                          "humanClicks",
                          "botClicks",
                          "visitorDays",
                        ][i],
                      )}
                    </p>
                    <p className="mt-3 text-3xl font-semibold">
                      {new Intl.NumberFormat(locale).format(
                        summary.data![key as keyof Counts],
                      )}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
            <p className="mb-6 text-xs text-muted-foreground">
              {t("uniqueHint")}
            </p>
            {summary.data.partial_history && (
              <p
                role="status"
                className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
              >
                {t("partialHistory")}
              </p>
            )}
          </>
        )
      )}
      <div className="mb-4 flex justify-end gap-2">
        {["day", "hour"].map((value) => (
          <Button
            key={value}
            variant={interval === value ? "default" : "outline"}
            size="sm"
            onClick={() => setInterval(value)}
          >
            {t(value === "day" ? "daily" : "hourly")}
          </Button>
        ))}
      </div>
      <Chart
        title={t("clickTrend")}
        area
        points={
          trend.data?.items.map((row) => ({
            label: new Intl.DateTimeFormat(
              locale === "fa" ? "fa-IR-u-ca-gregory" : "en-GB",
              {
                month: "short",
                day: "numeric",
                ...(interval === "hour" ? { hour: "2-digit" as const } : {}),
                timeZone: "UTC",
              },
            ).format(new Date(row.bucket)),
            value: row.total_clicks,
          })) || []
        }
      />
      {trend.data?.next_offset !== null &&
        trend.data?.next_offset !== undefined && (
          <p className="mt-2 text-xs text-muted-foreground">
            {t("limitedChart", { count: 1000 })}
          </p>
        )}
      {dimension === "country" && <CountryNotice />}
      <div className="my-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">{t("exportScope")}</p>
        <CsvDownload
          key={queryString({ ...selection.params, dimension })}
          path="analytics/breakdowns.csv"
          params={{ ...selection.params, dimension }}
          label="exportBreakdown"
          filename="traffic-breakdown"
        />
      </div>
      <div className="mt-6 grid items-start gap-6 xl:grid-cols-[280px_1fr]">
        <Card>
          <CardContent>
            <Label htmlFor="dimension">{t("dimension")}</Label>
            <select
              id="dimension"
              className="w-full"
              value={dimension}
              onChange={(e) => {
                setDimension(e.target.value);
                setOffset(0);
              }}
            >
              {dimensions.map((d) => (
                <option key={d} value={d}>
                  {dimensionLabel(d)}
                </option>
              ))}
            </select>
            <p className="mt-4 text-xs text-muted-foreground">
              {t("limitedChart", { count: 20 })}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={offset === 0}
                onClick={() => setOffset((v) => v - 20)}
              >
                {t("previousChart")}
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={breakdown.data?.next_offset == null}
                onClick={() => setOffset((v) => v + 20)}
              >
                {t("nextChart")}
              </Button>
            </div>
          </CardContent>
        </Card>
        <Chart
          title={dimensionLabel(dimension)}
          points={
            breakdown.data?.items.map((row) => ({
              label: label(row.value),
              value: row.total_clicks,
            })) || []
          }
        />
      </div>
      <Card className="mt-6">
        <CardContent>
          <h2 className="font-semibold">{t("compare")}</h2>
          <p className="mt-2 text-xs text-muted-foreground">
            {t("compareHint")}
          </p>
          <div className="my-4 flex max-h-44 flex-wrap gap-3 overflow-auto">
            {links.data?.items.map((link) => (
              <label
                key={link.id}
                className="flex items-center gap-2 rounded-lg border px-3 py-2 text-xs"
              >
                <input
                  type="checkbox"
                  checked={ids.includes(link.id)}
                  disabled={!ids.includes(link.id) && ids.length >= 10}
                  onChange={(e) =>
                    setIds((values) =>
                      e.target.checked
                        ? [...values, link.id]
                        : values.filter((id) => id !== link.id),
                    )
                  }
                />
                {link.slug}
              </label>
            ))}
          </div>
          {ids.length ? (
            <>
              <ErrorNotice code={comparisons.error} />
              <Chart
                title={t("compare")}
                points={
                  comparisons.data?.items.map((row) => ({
                    label: names.get(row.link_id) || t("linkOutside"),
                    value: row.total_clicks,
                  })) || []
                }
              />
              <DataTable
                data={comparisons.data?.items || []}
                columns={[
                  {
                    accessorKey: "link_id",
                    header: t("links"),
                    cell: ({ row }) =>
                      names.get(row.original.link_id) || t("linkOutside"),
                  },
                  { accessorKey: "total_clicks", header: t("totalClicks") },
                  { accessorKey: "human_clicks", header: t("humanClicks") },
                  { accessorKey: "bot_clicks", header: t("botClicks") },
                ]}
              />
            </>
          ) : (
            <Empty hint={t("compareHint")} />
          )}
        </CardContent>
      </Card>
    </>
  );
}
