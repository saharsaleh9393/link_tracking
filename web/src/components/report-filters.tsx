"use client";
import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import type { Campaign, Link, ListPage } from "@/lib/types";
import { useResource, type Params } from "@/lib/client";
import { initialRange, reportRange } from "@/lib/utils";
import { Card, CardContent } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Button } from "./ui/button";
import { ErrorNotice } from "./shared";
export type ReportSelection = {
  params: Params;
  links: Link[];
  campaigns: Campaign[];
};
export function ReportFilters({
  onApply,
}: {
  onApply: (value: ReportSelection) => void;
}) {
  const t = useTranslations();
  const [range, setRange] = useState(initialRange),
    [campaign, setCampaign] = useState(""),
    [link, setLink] = useState(""),
    [q, setQ] = useState(""),
    [term, setTerm] = useState(""),
    [error, setError] = useState("");
  const campaigns = useResource<ListPage<Campaign>>("campaigns", {
      q: term,
      limit: 500,
      include_total: true,
    }),
    links = useResource<ListPage<Link>>("links", {
      q: term,
      limit: 500,
      include_total: true,
    });
  function apply(event: FormEvent) {
    event.preventDefault();
    try {
      const params = {
        ...reportRange(range.from, range.to),
        campaign_id: campaign || null,
        link_id: link || null,
      };
      onApply({
        params,
        links: links.data?.items || [],
        campaigns: campaigns.data?.items || [],
      });
      setError("");
    } catch {
      setError("invalidRange");
    }
  }
  return (
    <Card className="mb-6">
      <CardContent>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Input
            aria-label={t("catalogSearch")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("catalogSearch")}
            maxLength={200}
            className="max-w-xs"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                setTerm(q);
              }
            }}
          />
          <Button type="button" variant="outline" onClick={() => setTerm(q)}>
            {t("search")}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setQ("");
              setTerm("");
            }}
          >
            {t("clear")}
          </Button>
          <span className="text-xs text-muted-foreground">
            {t("catalogLimited")}
          </span>
        </div>
        <form onSubmit={apply} noValidate>
          <div className="grid items-end gap-4 sm:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr_1fr_auto]">
            <div>
              <Label htmlFor="startDate">{t("startDate")}</Label>
              <Input
                id="startDate"
                type="date"
                value={range.from}
                onChange={(e) => setRange({ ...range, from: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="endDate">{t("endDate")}</Label>
              <Input
                id="endDate"
                type="date"
                value={range.to}
                onChange={(e) => setRange({ ...range, to: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="reportCampaign">{t("campaign")}</Label>
              <select
                id="reportCampaign"
                className="w-full"
                value={campaign}
                onChange={(e) => setCampaign(e.target.value)}
              >
                <option value="">{t("allCampaigns")}</option>
                {campaign &&
                  !campaigns.data?.items.some((row) => row.id === campaign) && (
                    <option value={campaign}>{t("campaignOutside")}</option>
                  )}
                {campaigns.data?.items.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="reportLink">{t("links")}</Label>
              <select
                id="reportLink"
                className="w-full"
                value={link}
                onChange={(e) => setLink(e.target.value)}
              >
                <option value="">{t("allLinks")}</option>
                {link && !links.data?.items.some((row) => row.id === link) && (
                  <option value={link}>{t("linkOutside")}</option>
                )}
                {links.data?.items.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.slug}
                  </option>
                ))}
              </select>
            </div>
            <Button>{t("apply")}</Button>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">{t("dateHint")}</p>
          {error && (
            <p role="alert" className="mt-3 text-sm text-red-600">
              {t(error)}
            </p>
          )}
          <ErrorNotice code={campaigns.error || links.error} />
        </form>
      </CardContent>
    </Card>
  );
}
