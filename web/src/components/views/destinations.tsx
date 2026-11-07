"use client";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { useResource } from "@/lib/client";
import type { Link, ListPage } from "@/lib/types";
import { Heading, Loading, ErrorNotice, Empty, CopyUrl } from "../shared";
import { Card, CardContent } from "../ui/card";
import { Label } from "../ui/label";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { Destinations } from "../forms/destinations";
export function DestinationsView() {
  const t = useTranslations();
  const [q, setQ] = useState(""),
    [term, setTerm] = useState(""),
    [id, setId] = useState(""),
    [changed, setChanged] = useState<Link | null>(null);
  const links = useResource<ListPage<Link>>("links", {
    q: term,
    limit: 500,
    include_total: true,
    status: "active",
  });
  const disabled = useResource<ListPage<Link>>("links", {
    q: term,
    limit: 500,
    include_total: true,
    status: "disabled",
  });
  const options = [
    ...(links.data?.items || []),
    ...(disabled.data?.items || []),
  ];
  const selected =
    changed?.id === id ? changed : options.find((link) => link.id === id);
  return (
    <>
      <Heading
        title={t("destinations")}
        description={t("destinationsDescription")}
      />
      <Card>
        <CardContent>
          <form
            className="mb-4 flex max-w-lg gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setTerm(q);
            }}
          >
            <Input
              aria-label={t("search")}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              maxLength={200}
              placeholder={t("search")}
            />
            <Button variant="outline">{t("search")}</Button>
          </form>
          <Label htmlFor="destinationLink">{t("selectLink")}</Label>
          <select
            id="destinationLink"
            value={id}
            className="mb-2 w-full max-w-lg"
            onChange={(e) => {
              setId(e.target.value);
              setChanged(null);
            }}
          >
            <option value="">—</option>
            {options.map((link) => (
              <option key={link.id} value={link.id}>
                {link.slug}
              </option>
            ))}
          </select>
          <ErrorNotice code={links.error || disabled.error} />
          {links.loading || disabled.loading ? (
            <Loading />
          ) : selected ? (
            <>
              <CopyUrl value={selected.tracking_url} />
              <Destinations
                key={selected.id}
                link={selected}
                onChanged={setChanged}
              />
            </>
          ) : (
            <Empty hint={t("selectLink")} />
          )}
          <p className="mt-4 text-xs text-muted-foreground">
            {t("catalogLimited")}
          </p>
        </CardContent>
      </Card>
    </>
  );
}
