"use client";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Link2,
  MousePointer2,
  Megaphone,
  Users,
  Plus,
  RefreshCw,
  Activity,
} from "lucide-react";
import { useResource } from "@/lib/client";
import { initialRange, reportRange } from "@/lib/utils";
import type { Overview, Summary, Trend } from "@/lib/types";
import { Heading, Loading, ErrorNotice, Empty, useDateFormat } from "../shared";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../ui/card";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { Chart } from "../charts";
export function OverviewView() {
  const t = useTranslations(),
    locale = useLocale(),
    date = useDateFormat();
  const [version, setVersion] = useState(0),
    [range] = useState(initialRange);
  const params = reportRange(range.from, range.to);
  const overview = useResource<Overview>("management/overview", {}, version),
    stats = useResource<Summary>("analytics/summary", params, version),
    trend = useResource<Trend>(
      "analytics/trends",
      { ...params, granularity: "day" },
      version,
    );
  const error = overview.error || stats.error || trend.error;
  const points =
    trend.data?.items.map((row) => ({
      label: new Intl.DateTimeFormat(
        locale === "fa" ? "fa-IR-u-ca-gregory" : "en",
        { month: "short", day: "numeric", timeZone: "UTC" },
      ).format(new Date(row.bucket)),
      value: row.total_clicks,
    })) || [];
  return (
    <>
      <Heading
        title={t("overview")}
        description={t("overviewDescription")}
        action={
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="icon"
              aria-label={t("refresh")}
              onClick={() => setVersion((v) => v + 1)}
            >
              <RefreshCw />
            </Button>
            <Button asChild>
              <Link href="/links?create=1">
                <Plus />
                {t("newLink")}
              </Link>
            </Button>
          </div>
        }
      />
      <div className="relative mb-7 overflow-hidden rounded-2xl bg-gradient-to-r from-[#38305f] to-[#6552a2] px-7 py-7 text-white">
        <div className="absolute -top-24 -end-12 size-72 rounded-full border border-white/10" />
        <div className="absolute -top-12 end-6 size-52 rounded-full border border-white/10" />
        <Badge className="mb-3 border-white/15 bg-white/10 text-[10px] tracking-wider text-indigo-100">
          {t("workspaceName")}
        </Badge>
        <h2 className="relative text-xl font-semibold">{t("welcome")}</h2>
        <p className="relative mt-2 text-sm text-indigo-200">
          {t("welcomeHint")}
        </p>
      </div>
      <ErrorNotice code={error} retry={() => setVersion((v) => v + 1)} />
      {(overview.loading || stats.loading) && <Loading />}
      {overview.data && stats.data && (
        <div className="mb-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            {
              label: "totalLinks",
              value: overview.data.total_links,
              Icon: Link2,
              color: "bg-indigo-50 text-indigo-600",
              hint: t("workspace"),
            },
            {
              label: "totalClicks",
              value: stats.data.total_clicks,
              Icon: MousePointer2,
              color: "bg-sky-50 text-sky-600",
              hint: t("last7"),
            },
            {
              label: "activeCampaigns",
              value: overview.data.active_campaigns,
              Icon: Megaphone,
              color: "bg-amber-50 text-amber-600",
              hint: t("workspace"),
            },
            {
              label: "humanClicks",
              value: stats.data.human_clicks,
              Icon: Users,
              color: "bg-emerald-50 text-emerald-600",
              hint: t("last7"),
            },
          ].map(({ label, value, Icon, color, hint }) => (
            <Card key={label}>
              <CardContent>
                <div className="flex items-center justify-between">
                  <p className="text-xs font-medium text-muted-foreground">
                    {t(label)}
                  </p>
                  <span className={"rounded-lg p-2 " + color}>
                    <Icon className="size-4" />
                  </span>
                </div>
                <p className="mt-3 text-[30px] font-semibold tracking-tight">
                  {new Intl.NumberFormat(locale).format(value)}
                </p>
                <p className="mt-2 text-[11px] text-muted-foreground">{hint}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <Chart title={t("clickTrend")} points={points} area />
        <Card>
          <CardHeader>
            <CardTitle>{t("recentActivity")}</CardTitle>
            <CardDescription>{t("activityHint")}</CardDescription>
          </CardHeader>
          <CardContent className="max-h-[325px] overflow-auto">
            {overview.data?.recent_activity.length ? (
              overview.data.recent_activity.map((row, index) => (
                <div
                  key={row.resource_id + index}
                  className="flex gap-3 border-b py-3 first:pt-0 last:border-0"
                >
                  <span className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/5 text-primary">
                    <Activity className="size-3" />
                  </span>
                  <div>
                    <p className="text-xs font-medium">
                      {t.has("activity_" + row.action.replaceAll(".", "_"))
                        ? t("activity_" + row.action.replaceAll(".", "_"))
                        : t("updated")}
                    </p>
                    <p className="mt-1 text-[10px] text-muted-foreground">
                      {date(row.occurred_at)}
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <Empty />
            )}
          </CardContent>
        </Card>
      </div>
      <Card className="mt-6">
        <CardContent className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <span className="hidden rounded-xl bg-primary/5 p-3 text-primary sm:block">
              <ArrowUpRight />
            </span>
            <div>
              <p className="text-sm font-semibold">{t("quickStart")}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {t("quickStartHint")}
              </p>
            </div>
          </div>
          <Button variant="outline" asChild>
            <Link href="/links?create=1">
              {t("newLink")}
              <ArrowRight className="rtl:rotate-180" />
            </Link>
          </Button>
        </CardContent>
      </Card>
    </>
  );
}
