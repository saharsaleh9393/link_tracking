"use client";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Download, Loader2 } from "lucide-react";
import { queryString, ApiError, type Params } from "@/lib/client";
import { Button } from "./ui/button";
import { ErrorNotice } from "./shared";

const MAX_ROWS = 50000;
export function CsvDownload({
  path,
  params,
  label = "exportCsv",
  filename = "report",
}: {
  path: string;
  params: Params;
  label?: string;
  filename?: string;
}) {
  const t = useTranslations();
  const [busy, setBusy] = useState(false),
    [count, setCount] = useState(0),
    [error, setError] = useState(""),
    [partial, setPartial] = useState(false);
  const current = useRef<AbortController | null>(null);
  useEffect(() => () => current.current?.abort(), []);
  async function download() {
    const controller = new AbortController();
    current.current = controller;
    setBusy(true);
    setCount(0);
    setError("");
    setPartial(false);
    const parts: BlobPart[] = [];
    let rows = 0;
    let continuation: Params = {};
    try {
      while (true) {
        const query = queryString({
          ...params,
          limit: path.startsWith("exports/") ? 5000 : 1000,
          ...continuation,
        });
        const response = await fetch("/api/tracker/" + path + "?" + query, {
          signal: controller.signal,
          cache: "no-store",
        });
        if (!response.ok) {
          const data = await response.json().catch(() => ({ code: "GENERIC" }));
          throw new ApiError(data.code || "GENERIC");
        }
        const pageCount = Number(response.headers.get("X-Export-Row-Count"));
        if (!Number.isInteger(pageCount) || pageCount < 0)
          throw new ApiError("GENERIC");
        if (rows + pageCount > MAX_ROWS) throw new ApiError("EXPORT_LIMIT");
        const text = (await response.text()).replace(/^\ufeff/, "");
        if (controller.signal.aborted) return;
        if (response.headers.get("X-Partial-History") === "true")
          setPartial(true);
        parts.push(
          parts.length ? text.slice(text.indexOf("\r\n") + 2) : "\ufeff" + text,
        );
        rows += pageCount;
        setCount(rows);
        const cursor = response.headers.get("X-Next-Cursor"),
          offset = response.headers.get("X-Next-Offset");
        if (!cursor && offset === null) break;
        if (rows >= MAX_ROWS || pageCount === 0)
          throw new ApiError("EXPORT_LIMIT");
        continuation = cursor ? { cursor } : { offset: Number(offset) };
      }
      if (controller.signal.aborted) return;
      const url = URL.createObjectURL(
        new Blob(parts, { type: "text/csv;charset=utf-8" }),
      );
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename + ".csv";
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      if (!controller.signal.aborted)
        setError(e instanceof ApiError ? e.code : "UNAVAILABLE");
    } finally {
      if (current.current === controller) {
        setBusy(false);
        current.current = null;
      }
    }
  }
  return (
    <div className="max-w-xl">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" onClick={download} disabled={busy}>
          {busy ? <Loader2 className="animate-spin" /> : <Download />}
          {busy ? t("exportProgress", { count }) : t(label)}
        </Button>
        {busy && (
          <Button variant="ghost" onClick={() => current.current?.abort()}>
            {t("cancel")}
          </Button>
        )}
      </div>
      <ErrorNotice code={error} />
      {partial && (
        <p className="mt-2 text-xs text-amber-700">{t("partialHistory")}</p>
      )}
    </div>
  );
}
