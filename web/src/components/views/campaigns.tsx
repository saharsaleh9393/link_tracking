"use client";
import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { Plus, Pencil, Megaphone, RefreshCw } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import type { Campaign, ListPage } from "@/lib/types";
import { useResource, request, ApiError } from "@/lib/client";
import {
  Heading,
  DataTable,
  Pager,
  ErrorNotice,
  Loading,
  Toast,
  useDateFormat,
  Status,
} from "../shared";
import { Card } from "../ui/card";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Dialog, DialogContent, DialogTitle } from "../ui/dialog";
import { CampaignSearch } from "../campaign-search";
export function CampaignsView() {
  const t = useTranslations(),
    date = useDateFormat();
  const [version, setVersion] = useState(0),
    [page, setPage] = useState(0),
    [term, setTerm] = useState(""),
    [status, setStatus] = useState(""),
    [sort, setSort] = useState("created_at");
  const [editor, setEditor] = useState<Campaign | "new" | null>(null),
    [error, setError] = useState(""),
    [success, setSuccess] = useState(false),
    [busy, setBusy] = useState(false),
    [validation, setValidation] = useState(false);
  const data = useResource<ListPage<Campaign>>(
    "campaigns",
    {
      q: term,
      archived: status ? status === "archived" : null,
      offset: page * 25,
      limit: 25,
      include_total: true,
      with_link_count: true,
      sort_by: sort,
      descending: sort !== "name",
    },
    version,
  );
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor) return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") || "").trim();
    if (!name || name.length > 200) {
      setValidation(true);
      return;
    }
    setValidation(false);
    setBusy(true);
    setError("");
    try {
      await request(editor === "new" ? "campaigns" : "campaigns/" + editor.id, {
        method: editor === "new" ? "POST" : "PATCH",
        body:
          editor === "new"
            ? { name }
            : { name, archived: form.get("archived") === "on" },
      });
      setEditor(null);
      setVersion((v) => v + 1);
      setSuccess(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.code : "GENERIC");
    } finally {
      setBusy(false);
    }
  }
  const columns: ColumnDef<Campaign, unknown>[] = [
    {
      accessorKey: "name",
      header: t("name"),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <span className="rounded-lg bg-amber-50 p-2 text-amber-600">
            <Megaphone className="size-4" />
          </span>
          <span className="font-medium">{row.original.name}</span>
        </div>
      ),
    },
    {
      accessorKey: "archived",
      header: t("status"),
      cell: ({ row }) => (
        <Status value={row.original.archived ? "archived" : "active"} />
      ),
    },
    {
      accessorKey: "link_count",
      header: t("linkCount"),
      cell: ({ row }) => row.original.link_count ?? 0,
    },
    {
      accessorKey: "created_at",
      header: t("created"),
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">
          {date(row.original.created_at)}
        </span>
      ),
    },
    {
      id: "actions",
      header: t("actions"),
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="icon"
          aria-label={t("edit") + " " + row.original.name}
          onClick={() => {
            setEditor(row.original);
            setError("");
          }}
        >
          <Pencil />
        </Button>
      ),
    },
  ];
  return (
    <>
      <Heading
        title={t("campaigns")}
        description={t("campaignsDescription")}
        action={
          <Button
            onClick={() => {
              setEditor("new");
              setError("");
              setValidation(false);
            }}
          >
            <Plus />
            {t("newCampaign")}
          </Button>
        }
      />
      {success && <Toast key={version} message={t("success")} />}
      <ErrorNotice code={data.error} retry={() => setVersion((v) => v + 1)} />
      <Card>
        <div className="border-b px-5 py-4 text-sm font-semibold">
          {t("recentCampaigns")}
        </div>
        <div className="flex flex-wrap gap-3 border-b p-5">
          <CampaignSearch
            onSearch={(value) => {
              setTerm(value);
              setPage(0);
            }}
          />
          <select
            aria-label={t("status")}
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(0);
            }}
          >
            <option value="">{t("all")}</option>
            <option value="active">{t("active")}</option>
            <option value="archived">{t("archived")}</option>
          </select>
          <select
            aria-label={t("sort")}
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setPage(0);
            }}
          >
            {["created_at", "name", "link_count"].map((value, index) => (
              <option key={value} value={value}>
                {t(["sortNewest", "sortName", "sortLinks"][index])}
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
      <Dialog
        open={!!editor}
        onOpenChange={(open) => {
          if (!open) setEditor(null);
        }}
      >
        <DialogContent>
          <DialogTitle className="text-xl font-semibold">
            {t(editor === "new" ? "newCampaign" : "edit")}
          </DialogTitle>
          {editor && (
            <form
              key={typeof editor === "string" ? editor : editor.id}
              onSubmit={save}
              noValidate
              className="mt-6 space-y-5"
            >
              <div>
                <Label htmlFor="campaignName">{t("campaignName")}</Label>
                <Input
                  id="campaignName"
                  name="name"
                  defaultValue={editor === "new" ? "" : editor.name}
                  required
                  maxLength={200}
                />
              </div>
              {editor !== "new" && (
                <div>
                  <label className="flex items-center gap-3 text-sm">
                    <input
                      name="archived"
                      type="checkbox"
                      defaultChecked={editor.archived}
                    />
                    {t("archive")}
                  </label>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {t("archiveHint")}
                  </p>
                </div>
              )}
              {validation && (
                <p role="alert" className="text-sm text-red-600">
                  {t("campaignRequired")}
                </p>
              )}
              <ErrorNotice code={error} />
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setEditor(null)}
                >
                  {t("cancel")}
                </Button>
                <Button disabled={busy}>
                  {t(editor === "new" ? "create" : "save")}
                </Button>
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
