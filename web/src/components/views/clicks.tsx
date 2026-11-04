"use client";
import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useResource } from "@/lib/client";
import { initialRange, reportRange } from "@/lib/utils";
import type { Click, ClickPage, ListPage, Link } from "@/lib/types";
import {
  Heading,
  Loading,
  ErrorNotice,
  DataTable,
  useDateFormat,
} from "../shared";
import { Card } from "../ui/card";
import { Button } from "../ui/button";
import { ReportFilters, type ReportSelection } from "../report-filters";
export function ClicksView() {
  const t = useTranslations(),
    date = useDateFormat(),
    locale = useLocale();
  const [selection, setSelection] = useState<ReportSelection>(() => {
    const range = initialRange();
    return {
      params: reportRange(range.from, range.to),
      links: [],
      campaigns: [],
    };
  });
  const [cursors, setCursors] = useState<(string | null)[]>([null]),
    [index, setIndex] = useState(0);
  const data = useResource<ClickPage>("exports/clicks", {
    ...selection.params,
    cursor: cursors[index],
    limit: 100,
  });
  const links = useResource<ListPage<Link>>("links", {
    limit: 500,
    include_total: true,
  });
  const names = new Map([
    ...(links.data?.items || []).map((row) => [row.id, row.slug] as const),
    ...selection.links.map((row) => [row.id, row.slug] as const),
  ]);
  const translated = (value: string) => (t.has(value) ? t(value) : value);
  return (
    <>
      <Heading title={t("clicks")} description={t("clicksDescription")} />
      <ReportFilters
        onApply={(value) => {
          setSelection(value);
          setCursors([null]);
          setIndex(0);
        }}
      />
      <ErrorNotice code={data.error} />
      {data.data?.partial_history && (
        <p className="mb-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
          {t("partialHistory")}
        </p>
      )}
      <Card>
        {data.loading ? (
          <Loading />
        ) : (
          <DataTable<Click>
            data={data.data?.items || []}
            columns={[
              {
                accessorKey: "occurred_at",
                header: t("clickTime"),
                cell: ({ row }) => (
                  <span className="whitespace-nowrap text-xs">
                    {date(row.original.occurred_at)}
                  </span>
                ),
              },
              {
                accessorKey: "link_id",
                header: t("links"),
                cell: ({ row }) =>
                  names.get(row.original.link_id) || t("linkOutside"),
              },
              {
                accessorKey: "classification",
                header: t("classification"),
                cell: ({ row }) => translated(row.original.classification),
              },
              {
                accessorKey: "device",
                header: t("device"),
                cell: ({ row }) => translated(row.original.device),
              },
              { accessorKey: "browser", header: t("browser") },
              {
                accessorKey: "country",
                header: t("country"),
                cell: ({ row }) =>
                  row.original.country
                    ? new Intl.DisplayNames([locale], { type: "region" }).of(
                        row.original.country,
                      ) || row.original.country
                    : t("unknown"),
              },
              ...(
                [
                  "utm_source",
                  "utm_medium",
                  "utm_campaign",
                  "utm_content",
                  "utm_term",
                ] as const
              ).map((key) => ({
                accessorKey: key,
                header: t(key),
                cell: ({ row }: { row: { original: Click } }) =>
                  row.original[key] || "—",
              })),
            ]}
          />
        )}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t p-4">
          <p className="text-xs text-muted-foreground">{t("eventsPerPage")}</p>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={index === 0}
              onClick={() => setIndex((v) => v - 1)}
            >
              {t("previous")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!data.data?.next_cursor}
              onClick={() => {
                setCursors((values) => [
                  ...values.slice(0, index + 1),
                  data.data!.next_cursor,
                ]);
                setIndex((v) => v + 1);
              }}
            >
              {t("next")}
            </Button>
          </div>
        </div>
      </Card>
    </>
  );
}
