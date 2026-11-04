"use client";
import { useLocale, useTranslations } from "next-intl";
import {
  ArrowDownUp,
  ChevronLeft,
  ChevronRight,
  Copy,
  Inbox,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";
import { Badge } from "./ui/badge";
export function Heading({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-7 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight lg:text-[28px]">
          {title}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>
      </div>
      {action}
    </div>
  );
}
export function Empty({ hint }: { hint?: string }) {
  const t = useTranslations();
  return (
    <div className="flex min-h-52 flex-col items-center justify-center gap-3 p-8 text-center">
      <span className="rounded-2xl bg-primary/5 p-4 text-primary">
        <Inbox className="size-7" />
      </span>
      <h3 className="font-medium">{t("empty")}</h3>
      <p className="max-w-md text-sm text-muted-foreground">
        {hint || t("emptyHint")}
      </p>
    </div>
  );
}
export function Loading() {
  const t = useTranslations();
  return (
    <div role="status" className="min-h-48 p-6">
      <div className="mb-5 flex items-center gap-3 text-sm text-muted-foreground">
        <Loader2 className="size-5 animate-spin" />
        {t("loading")}
      </div>
      <div aria-hidden="true" className="space-y-3 animate-pulse">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-8 rounded-lg bg-slate-100" />
        ))}
      </div>
    </div>
  );
}
export function ErrorNotice({
  code,
  retry,
}: {
  code?: string;
  retry?: () => void;
}) {
  const t = useTranslations();
  if (!code) return null;
  const key = "error_" + code;
  return (
    <div
      role="alert"
      className="my-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
    >
      <p>{t.has(key) ? t(key) : t("error_GENERIC")}</p>
      {code === "AUTH" ? (
        <a href="/login" className="underline">
          {t("loginAgain")}
        </a>
      ) : (
        retry && (
          <Button variant="outline" size="sm" onClick={retry}>
            <RefreshCw />
            {t("retry")}
          </Button>
        )
      )}
    </div>
  );
}
export function Toast({ message }: { message: string }) {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const timer = setTimeout(() => setVisible(false), 6000);
    return () => clearTimeout(timer);
  }, []);
  if (!visible) return null;
  return (
    <div
      role="status"
      className="pointer-events-none fixed bottom-5 end-4 z-40 max-w-[calc(100vw-2rem)] sm:max-w-sm rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 shadow-lg sm:end-8"
    >
      {message}
    </div>
  );
}
export function Status({ value }: { value: string }) {
  const t = useTranslations();
  return (
    <Badge
      className={
        value === "active"
          ? "border-emerald-100 bg-emerald-50 text-emerald-700"
          : "border-slate-200 bg-slate-50 text-slate-500"
      }
    >
      <span className="size-1.5 rounded-full bg-current" />
      {t.has(value) ? t(value) : t("unknown")}
    </Badge>
  );
}
export function DataTable<T>({
  data,
  columns,
}: {
  data: T[];
  columns: ColumnDef<T, unknown>[];
}) {
  const t = useTranslations();
  const [sorting, setSorting] = useState<SortingState>([]);
  // React Compiler is not enabled. TanStack's imperative table API is intentionally not memoized.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });
  if (!data.length) return <Empty />;
  return (
    <Table>
      <TableHeader>
        {table.getHeaderGroups().map((group) => (
          <TableRow key={group.id}>
            {group.headers.map((header) => (
              <TableHead key={header.id}>
                {header.isPlaceholder ? null : header.column.getCanSort() ? (
                  <button
                    className="inline-flex items-center gap-2"
                    title={t("sorting")}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext(),
                    )}
                    <ArrowDownUp className="size-3" />
                  </button>
                ) : (
                  flexRender(
                    header.column.columnDef.header,
                    header.getContext(),
                  )
                )}
              </TableHead>
            ))}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {table.getRowModel().rows.map((row) => (
          <TableRow key={row.id}>
            {row.getVisibleCells().map((cell) => (
              <TableCell key={cell.id}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
export function Pager({
  page,
  total,
  pageSize = 25,
  onPage,
}: {
  page: number;
  total: number;
  pageSize?: number;
  onPage: (page: number) => void;
}) {
  const t = useTranslations(),
    locale = useLocale();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t px-5 py-4 text-sm text-muted-foreground">
      <span>
        {t("results", { count: new Intl.NumberFormat(locale).format(total) })} ·{" "}
        {t("page", { page: new Intl.NumberFormat(locale).format(page + 1) })}
      </span>
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={page === 0}
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeft className="rtl:rotate-180" />
          {t("previous")}
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={(page + 1) * pageSize >= total || page >= 4000}
          onClick={() => onPage(page + 1)}
        >
          {t("next")}
          <ChevronRight className="rtl:rotate-180" />
        </Button>
      </div>
    </div>
  );
}
export function CopyUrl({ value }: { value: string }) {
  const t = useTranslations();
  const [copied, setCopied] = useState(false),
    [failed, setFailed] = useState(false);
  return (
    <Card className="flex items-center gap-2 bg-muted/40 p-3">
      <code dir="ltr" className="min-w-0 flex-1 overflow-auto text-xs">
        {value}
      </code>
      <Button
        variant="ghost"
        size="icon"
        aria-label={t("copy")}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            setFailed(false);
          } catch {
            setFailed(true);
          }
        }}
      >
        <Copy />
      </Button>
      <span
        className={copied ? "text-xs text-emerald-700" : "sr-only"}
        role="status"
      >
        {copied ? t("copied") : failed ? t("copyFailed") : ""}
      </span>
      {failed && <p className="text-xs">{t("copyFailed")}</p>}
    </Card>
  );
}
export function useDateFormat() {
  const locale = useLocale();
  return (value: string) =>
    new Intl.DateTimeFormat(locale === "fa" ? "fa-IR-u-ca-gregory" : "en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "UTC",
    }).format(new Date(value));
}
