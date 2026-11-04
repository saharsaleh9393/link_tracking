"use client";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { BookOpen, Globe } from "lucide-react";
import { useResource, queryString, type Params } from "@/lib/client";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogTitle } from "./ui/dialog";
import { ErrorNotice } from "./shared";
type ReportingStatus = {
  country: {
    local_database_available: boolean;
    trusted_header_enabled: boolean;
    private_ips_remain_unknown: boolean;
  };
};
export function CountryNotice() {
  const t = useTranslations();
  const status = useResource<ReportingStatus>("reporting/status");
  const ready =
    status.data?.country.local_database_available ||
    status.data?.country.trusted_header_enabled;
  return (
    <div className="my-5 rounded-xl border bg-card p-4 text-sm">
      <div className="flex items-start gap-3">
        <Globe className="mt-1 size-4 shrink-0 text-primary" />
        <div>
          {status.data && (
            <p className="font-medium">
              {t(ready ? "countryReady" : "countryNotConfigured")}
            </p>
          )}
          <p className="mt-1 text-xs leading-6 text-muted-foreground">
            {t("countryPrivate")}
          </p>
          {status.data && !ready && (
            <p className="mt-1 text-xs text-muted-foreground">
              {t("countrySetup")}
            </p>
          )}
          <p className="mt-1 text-xs text-muted-foreground">
            {t("countryFuture")}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            {t("countryAttribution")}{" "}
            <a
              href="https://db-ip.com"
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              DB-IP
            </a>{" "}
            · CC BY 4.0
          </p>
        </div>
      </div>
      <ErrorNotice code={status.error} />
    </div>
  );
}
export function ApiGuide({ params }: { params: Params }) {
  const t = useTranslations();
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        <BookOpen />
        {t("apiGuide")}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogTitle className="text-xl font-semibold">
            {t("apiGuide")}
          </DialogTitle>
          <p className="my-4 text-sm leading-7 text-muted-foreground">
            {t("apiGuideHint")}
          </p>
          <pre
            dir="ltr"
            className="overflow-x-auto rounded-lg bg-muted p-4 text-xs leading-6"
          >
            {"GET /api/v1/exports/clicks?" +
              queryString({ ...params, limit: 1000 }) +
              "\nAuthorization: Bearer <REPORT_API_KEY>"}
          </pre>
          <p className="mt-4 text-sm text-muted-foreground">
            {t("apiPagination")}
          </p>
          <ul className="my-4 space-y-2 text-xs" dir="ltr">
            {[
              "/api/v1/analytics/summary",
              "/api/v1/analytics/breakdowns",
              "/api/v1/analytics/trends",
              "/api/v1/exports/clicks",
              "/api/v1/exports/clicks.csv",
              "/api/v1/exports/daily",
              "/api/v1/exports/campaigns",
              "/api/v1/exports/links",
              "/api/v1/reporting/links",
              "/api/v1/reporting/campaigns",
            ].map((path) => (
              <li key={path}>
                <code>{path}</code>
              </li>
            ))}
          </ul>
          <p className="text-xs leading-6 text-muted-foreground">
            {t("apiReadOnly")}
          </p>
        </DialogContent>
      </Dialog>
    </>
  );
}
