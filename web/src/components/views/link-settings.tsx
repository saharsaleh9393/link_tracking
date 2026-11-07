"use client";
import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { Plus, Pencil, Trash2, Loader2 } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import { request, ApiError, useResource } from "@/lib/client";
import type { ListPage } from "@/lib/types";
import { linkPreview, type Linkspace } from "@/lib/linkspaces";
import {
  Heading,
  DataTable,
  Loading,
  ErrorNotice,
  Pager,
  Status,
  Toast,
  useDateFormat,
} from "../shared";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "../ui/dialog";

type Configuration = Pick<
  Linkspace,
  "name" | "base_url" | "path_prefix" | "is_active" | "is_default"
>;
function values(space: Linkspace): Configuration {
  return {
    name: space.name,
    base_url: space.base_url,
    path_prefix: space.path_prefix,
    is_active: space.is_active,
    is_default: space.is_default,
  };
}
function ConfigurationForm({
  space,
  onSaved,
  onCancel,
}: {
  space?: Linkspace;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const t = useTranslations();
  const [form, setForm] = useState<Configuration>(
    space
      ? values(space)
      : {
          name: "",
          base_url: "",
          path_prefix: "r",
          is_active: true,
          is_default: false,
        },
  );
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (!form.name.trim()) {
      setError("LINKSPACE_NAME");
      return;
    }
    try {
      const url = new URL(form.base_url.trim());
      if (
        !["http:", "https:"].includes(url.protocol) ||
        url.username ||
        url.password ||
        !url.hostname ||
        url.search ||
        url.hash ||
        (url.pathname !== "/" && url.pathname !== "")
      )
        throw Error();
    } catch {
      setError("LINKSPACE_URL");
      return;
    }
    setBusy(true);
    try {
      await request(space ? "linkspaces/" + space.id : "linkspaces", {
        method: space ? "PUT" : "POST",
        body: {
          ...form,
          name: form.name.trim(),
          base_url: form.base_url.trim(),
        },
      });
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.code : "GENERIC");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="mt-5 space-y-5" noValidate>
      <div>
        <Label htmlFor="space-name">{t("linkspaceName")}</Label>
        <Input
          id="space-name"
          required
          maxLength={100}
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
      </div>
      <div>
        <Label htmlFor="space-base">{t("baseUrl")}</Label>
        <Input
          id="space-base"
          dir="ltr"
          type="url"
          required
          placeholder="https://go.example.com"
          maxLength={300}
          value={form.base_url}
          onChange={(e) => setForm({ ...form, base_url: e.target.value })}
        />
        <p className="mt-2 text-xs text-muted-foreground">{t("baseUrlHint")}</p>
      </div>
      <div>
        <Label htmlFor="space-prefix">{t("pathPrefix")}</Label>
        <Input
          id="space-prefix"
          dir="ltr"
          placeholder="r"
          maxLength={50}
          value={form.path_prefix}
          onChange={(e) => setForm({ ...form, path_prefix: e.target.value })}
        />
        <p className="mt-2 text-xs text-muted-foreground">
          {t("pathPrefixHint")}
        </p>
      </div>
      <div className="rounded-xl border bg-muted/30 p-4">
        <p className="mb-2 text-xs text-muted-foreground">{t("urlPreview")}</p>
        <code dir="ltr" className="block break-all text-sm">
          {form.base_url
            ? linkPreview(form.base_url, form.path_prefix)
            : "https://example.com/r/slug"}
        </code>
      </div>
      <label className="flex items-center gap-3 text-sm">
        <input
          type="checkbox"
          checked={form.is_active}
          onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
        />
        {t("active")}
      </label>
      <label className="flex items-center gap-3 text-sm">
        <input
          type="checkbox"
          checked={form.is_default}
          disabled={space?.is_default}
          onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
        />
        {t("defaultLinkspace")}
      </label>
      <p className="text-xs text-muted-foreground">
        {t("linkspaceSnapshotHint")}
      </p>
      <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-6 text-amber-900">
        {t("linkspaceDeploymentHint")}
      </p>
      <ErrorNotice code={error} />
      <div className="flex justify-end gap-2 border-t pt-4">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={busy}
        >
          {t("cancel")}
        </Button>
        <Button disabled={busy}>
          {busy && <Loader2 className="animate-spin" />}
          {t("save")}
        </Button>
      </div>
    </form>
  );
}

export function LinkSettingsView() {
  const t = useTranslations(),
    date = useDateFormat();
  const [version, setVersion] = useState(0),
    [page, setPage] = useState(0),
    [search, setSearch] = useState(""),
    [term, setTerm] = useState("");
  const [editing, setEditing] = useState<Linkspace | null>(null),
    [creating, setCreating] = useState(false),
    [deleting, setDeleting] = useState<Linkspace | null>(null);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [success, setSuccess] = useState(false);
  const data = useResource<ListPage<Linkspace>>(
    "linkspaces",
    { q: term, offset: page * 25, limit: 25, include_total: true },
    version,
  );
  function saved() {
    setEditing(null);
    setCreating(false);
    setDeleting(null);
    setVersion((v) => v + 1);
    setSuccess(true);
  }
  async function change(
    space: Linkspace,
    kind: "default" | "active" | "delete",
  ) {
    setBusy(true);
    setError("");
    try {
      await request(
        "linkspaces/" + space.id,
        kind === "delete"
          ? { method: "DELETE" }
          : {
              method: "PUT",
              body: {
                ...values(space),
                ...(kind === "default"
                  ? { is_default: true, is_active: true }
                  : { is_active: !space.is_active }),
              },
            },
      );
      saved();
    } catch (e) {
      setError(e instanceof ApiError ? e.code : "GENERIC");
    } finally {
      setBusy(false);
    }
  }
  const columns: ColumnDef<Linkspace, unknown>[] = [
    {
      accessorKey: "name",
      header: t("linkspaceName"),
      cell: ({ row }) => (
        <div>
          <p className="font-medium">{row.original.name}</p>
          {row.original.is_default && (
            <span className="text-xs text-primary">
              {t("defaultLinkspace")}
            </span>
          )}
          <p className="mt-1 text-xs text-muted-foreground">
            {date(row.original.created_at)}
          </p>
        </div>
      ),
    },
    {
      accessorKey: "preview_url",
      header: t("urlPreview"),
      cell: ({ row }) => (
        <code dir="ltr" className="block max-w-72 break-all text-xs">
          {row.original.preview_url}
        </code>
      ),
    },
    {
      accessorKey: "is_active",
      header: t("status"),
      cell: ({ row }) => (
        <Status value={row.original.is_active ? "active" : "disabled"} />
      ),
    },
    {
      accessorKey: "configuration_status",
      header: t("configurationStatus"),
      cell: ({ row }) => (
        <span
          className={
            row.original.configuration_status === "pending_configuration"
              ? "text-amber-800"
              : "text-muted-foreground"
          }
        >
          {t(row.original.configuration_status)}
        </span>
      ),
    },
    { accessorKey: "link_count", header: t("linkCount") },
    {
      id: "actions",
      header: t("actions"),
      enableSorting: false,
      cell: ({ row }) => (
        <div className="flex flex-wrap items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("edit") + " " + row.original.name}
            disabled={busy}
            onClick={() => {
              setError("");
              setEditing(row.original);
            }}
          >
            <Pencil />
          </Button>
          {!row.original.is_default && (
            <>
              <Button
                variant="outline"
                size="sm"
                disabled={busy || !row.original.is_active}
                onClick={() => change(row.original, "default")}
              >
                {t("setDefault")}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={() => change(row.original, "active")}
              >
                {t(
                  row.original.is_active
                    ? "deactivateLinkspace"
                    : "activateLinkspace",
                )}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label={t("delete") + " " + row.original.name}
                disabled={busy}
                onClick={() => {
                  setError("");
                  setDeleting(row.original);
                }}
              >
                <Trash2 className="text-red-400" />
              </Button>
            </>
          )}
        </div>
      ),
    },
  ];
  return (
    <>
      <p className="mb-2 text-xs text-muted-foreground">
        {t("settings")} / {t("linkSettings")}
      </p>
      <Heading
        title={t("linkSettings")}
        description={t("linkSettingsDescription")}
        action={
          <Button
            onClick={() => {
              setError("");
              setCreating(true);
            }}
          >
            <Plus />
            {t("newLinkspace")}
          </Button>
        }
      />
      {success && <Toast key={version} message={t("success")} />}
      <p className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
        {t("linkspaceDeploymentHint")}
      </p>
      <p className="mb-5 text-sm text-muted-foreground">
        {t("linkspaceSnapshotHint")}
      </p>
      <ErrorNotice
        code={data.error || error}
        retry={() => setVersion((v) => v + 1)}
      />
      <Card>
        <form
          className="flex max-w-xl gap-2 p-5"
          onSubmit={(event) => {
            event.preventDefault();
            setTerm(search);
            setPage(0);
          }}
        >
          <Input
            aria-label={t("search")}
            value={search}
            maxLength={100}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("search")}
          />
          <Button variant="outline">{t("search")}</Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setSearch("");
              setTerm("");
              setPage(0);
            }}
          >
            {t("clear")}
          </Button>
        </form>
        {data.loading ? (
          <Loading />
        ) : (
          <DataTable data={data.data?.items || []} columns={columns} />
        )}
        <Pager page={page} total={data.data?.total || 0} onPage={setPage} />
      </Card>
      <Dialog
        open={creating || !!editing}
        onOpenChange={(open) => {
          if (!open) {
            setCreating(false);
            setEditing(null);
          }
        }}
      >
        <DialogContent>
          <DialogTitle className="pe-6 text-xl font-semibold">
            {t(editing ? "editLinkspace" : "newLinkspace")}
          </DialogTitle>
          <ConfigurationForm
            key={editing?.id || "new"}
            space={editing || undefined}
            onSaved={saved}
            onCancel={() => {
              setCreating(false);
              setEditing(null);
            }}
          />
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!deleting}
        onOpenChange={(open) => {
          if (!open && !busy) setDeleting(null);
        }}
      >
        <DialogContent>
          <DialogTitle>{t("deleteLinkspace")}</DialogTitle>
          <DialogDescription className="my-4">
            {t("deleteLinkspaceHint")}
          </DialogDescription>
          <ErrorNotice code={error} />
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setDeleting(null)}
            >
              {t("cancel")}
            </Button>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={() => deleting && change(deleting, "delete")}
            >
              {t("delete")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
