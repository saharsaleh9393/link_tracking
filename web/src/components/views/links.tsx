"use client";
import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Plus,
  Search,
  Pencil,
  Trash2,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import type { Campaign, Link, ListPage } from "@/lib/types";
import { useResource, request, ApiError } from "@/lib/client";
import {
  Heading,
  ErrorNotice,
  Loading,
  DataTable,
  Pager,
  Status,
  Toast,
  CopyUrl,
  useDateFormat,
} from "../shared";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Card } from "../ui/card";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "../ui/dialog";
import { LinkForm } from "../forms/link-form";
import { Destinations } from "../forms/destinations";
export function LinksView() {
  const t = useTranslations(),
    date = useDateFormat(),
    query = useSearchParams();
  const [version, setVersion] = useState(0),
    [page, setPage] = useState(0),
    [search, setSearch] = useState(""),
    [term, setTerm] = useState(""),
    [status, setStatus] = useState(""),
    [campaign, setCampaign] = useState(""),
    [sort, setSort] = useState("created_at");
  const [creating, setCreating] = useState(query.get("create") === "1"),
    [editing, setEditing] = useState<Link | null>(null),
    [deleting, setDeleting] = useState<Link | null>(null),
    [created, setCreated] = useState<Link | null>(null),
    [success, setSuccess] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const data = useResource<ListPage<Link>>(
    "links",
    {
      q: term,
      status: status || null,
      campaign_id: campaign || null,
      offset: page * 25,
      limit: 25,
      include_total: true,
      sort_by: sort,
      descending: true,
    },
    version,
  );
  const catalogs = useResource<ListPage<Campaign>>(
    "campaigns",
    { limit: 500, include_total: true },
    version,
  );
  const names = new Map(catalogs.data?.items.map((c) => [c.id, c.name]));
  function saved(link: Link) {
    setEditing(null);
    setCreating(false);
    setCreated(link);
    setVersion((v) => v + 1);
    setSuccess(true);
  }
  async function remove() {
    if (!deleting) return;
    setBusy(true);
    setError("");
    try {
      await request("links/" + deleting.id, { method: "DELETE" });
      setDeleting(null);
      setVersion((v) => v + 1);
      setSuccess(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.code : "GENERIC");
    } finally {
      setBusy(false);
    }
  }
  const columns: ColumnDef<Link, unknown>[] = [
    {
      accessorKey: "slug",
      header: t("linkName"),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <span className="hidden rounded-lg bg-primary/5 p-2 text-primary sm:block">
            <ExternalLink className="size-4" />
          </span>
          <div>
            <p className="font-medium">{row.original.slug}</p>
            <CopyUrl compact value={row.original.tracking_url} />
          </div>
        </div>
      ),
    },
    {
      accessorKey: "status",
      header: t("status"),
      cell: ({ row }) => (
        <Status
          value={
            row.original.status === "active" &&
            row.original.expires_at &&
            new Date(row.original.expires_at) < new Date()
              ? "expired"
              : row.original.status
          }
        />
      ),
    },
    {
      accessorKey: "campaign_id",
      header: t("campaign"),
      cell: ({ row }) =>
        names.get(row.original.campaign_id || "") ||
        (row.original.campaign_id ? t("campaignOutside") : t("none")),
    },
    {
      accessorKey: "created_at",
      header: t("created"),
      cell: ({ row }) => (
        <span className="whitespace-nowrap text-xs text-muted-foreground">
          {date(row.original.created_at)}
        </span>
      ),
    },
    {
      id: "actions",
      header: t("actions"),
      enableSorting: false,
      cell: ({ row }) => (
        <div className="flex gap-1">
          <Button
            size="icon"
            variant="ghost"
            aria-label={t("edit") + " " + row.original.slug}
            disabled={row.original.status === "deleted"}
            onClick={() => setEditing(row.original)}
          >
            <Pencil />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            aria-label={t("delete") + " " + row.original.slug}
            disabled={row.original.status === "deleted"}
            onClick={() => setDeleting(row.original)}
          >
            <Trash2 className="text-red-400" />
          </Button>
        </div>
      ),
    },
  ];
  return (
    <>
      <Heading
        title={t("links")}
        description={t("linksDescription")}
        action={
          <Button
            onClick={() => {
              setCreating(true);
              setSuccess(false);
            }}
          >
            <Plus />
            {t("newLink")}
          </Button>
        }
      />
      {success && <Toast key={version} message={t("success")} />}{" "}
      {created && (
        <div className="mb-5">
          <CopyUrl value={created.tracking_url} />
        </div>
      )}
      <ErrorNotice
        code={data.error || catalogs.error}
        retry={() => setVersion((v) => v + 1)}
      />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b p-5">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setTerm(search);
              setPage(0);
            }}
            className="flex min-w-48 flex-1 gap-2"
          >
            <div className="relative flex-1">
              <Search className="absolute top-3 start-3 size-4 text-slate-400" />
              <Input
                aria-label={t("search")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="ps-9"
                placeholder={t("search") + "…"}
                maxLength={200}
              />
            </div>
            <Button variant="outline" type="submit">
              {t("search")}
            </Button>
          </form>
          <select
            aria-label={t("status")}
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(0);
            }}
          >
            <option value="">{t("all")}</option>
            {["active", "disabled", "deleted"].map((s) => (
              <option key={s} value={s}>
                {t(s)}
              </option>
            ))}
          </select>
          <select
            aria-label={t("campaign")}
            value={campaign}
            onChange={(e) => {
              setCampaign(e.target.value);
              setPage(0);
            }}
          >
            <option value="">{t("allCampaigns")}</option>
            {catalogs.data?.items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            aria-label={t("sort")}
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setPage(0);
            }}
          >
            {["created_at", "updated_at", "slug", "status"].map((s, i) => (
              <option key={s} value={s}>
                {t(["created", "updated", "linkName", "status"][i])}
              </option>
            ))}
          </select>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("refresh")}
            onClick={() => setVersion((v) => v + 1)}
          >
            <RefreshCw />
          </Button>
        </div>
        {data.loading ? (
          <Loading />
        ) : (
          <DataTable data={data.data?.items || []} columns={columns} />
        )}
        <Pager page={page} total={data.data?.total || 0} onPage={setPage} />
      </Card>
      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent>
          <DialogTitle className="pe-6 text-xl font-semibold">
            {t("newLink")}
          </DialogTitle>
          <LinkForm
            campaigns={catalogs.data?.items || []}
            onSaved={saved}
            onCancel={() => setCreating(false)}
          />
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!editing}
        onOpenChange={(open) => {
          if (!open) setEditing(null);
        }}
      >
        <DialogContent>
          {editing && (
            <>
              <DialogTitle className="pe-6 text-xl font-semibold">
                {t("linkDetails")}
              </DialogTitle>
              <div className="mt-5">
                <CopyUrl value={editing.tracking_url} />
              </div>
              <LinkForm
                key={editing.id + ":" + editing.version}
                link={editing}
                campaigns={catalogs.data?.items || []}
                onSaved={saved}
                onCancel={() => setEditing(null)}
              />
              <Destinations
                link={editing}
                onChanged={(link) => {
                  setEditing(link);
                  setVersion((v) => v + 1);
                }}
              />
            </>
          )}
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!deleting}
        onOpenChange={(open) => {
          if (!open && !busy) setDeleting(null);
        }}
      >
        <DialogContent>
          <DialogTitle className="pe-6 text-lg font-semibold">
            {t("confirmDelete")}
          </DialogTitle>
          <DialogDescription className="my-4 text-sm text-muted-foreground">
            {t("deleteHint")}
          </DialogDescription>
          <ErrorNotice code={error} />
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => setDeleting(null)}
              disabled={busy}
            >
              {t("cancel")}
            </Button>
            <Button variant="destructive" onClick={remove} disabled={busy}>
              {t("delete")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
