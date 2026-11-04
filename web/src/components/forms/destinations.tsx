"use client";
import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { request, useResource, ApiError } from "@/lib/client";
import type { Destination, Link } from "@/lib/types";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { ErrorNotice, Loading, Toast } from "../shared";
export function Destinations({
  link,
  onChanged,
}: {
  link: Link;
  onChanged: (link: Link) => void;
}) {
  const t = useTranslations();
  const [version, setVersion] = useState(0),
    [error, setError] = useState(""),
    [success, setSuccess] = useState(false),
    [busy, setBusy] = useState(false),
    [url, setUrl] = useState("");
  const data = useResource<Destination[]>(
    "links/" + link.id + "/destinations",
    { limit: 500 },
    version,
  );
  async function add(event: FormEvent) {
    event.preventDefault();
    try {
      const parsed = new URL(url.trim());
      if (!["http:", "https:"].includes(parsed.protocol)) throw Error();
    } catch {
      setError("VALIDATION");
      return;
    }
    setError("");
    setSuccess(false);
    setBusy(true);
    try {
      await request("links/" + link.id + "/destinations", {
        method: "POST",
        body: { url: url.trim() },
      });
      setUrl("");
      setSuccess(true);
      setVersion((v) => v + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.code : "GENERIC");
    } finally {
      setBusy(false);
    }
  }
  async function activate(id: string) {
    setError("");
    setBusy(true);
    try {
      const saved = await request<Link>("links/" + link.id, {
        method: "PATCH",
        body: { active_destination_id: id, expected_version: link.version },
      });
      onChanged(saved);
      setSuccess(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.code : "GENERIC");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="mt-8 border-t pt-6">
      <h3 className="mb-4 font-semibold">{t("destinations")}</h3>
      <ErrorNotice code={error || data.error} />
      {success && (
        <Toast key={link.version + version} message={t("success")} />
      )}{" "}
      {data.loading ? (
        <Loading />
      ) : (
        <div className="space-y-3">
          {data.data?.map((row) => (
            <div key={row.id} className="rounded-lg border p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-medium">
                  {t("version", { version: row.version })}
                </p>
                {row.id === link.active_destination_id ? (
                  <span className="text-xs text-emerald-600">
                    {t("activeDestination")}
                  </span>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => activate(row.id)}
                  >
                    {t("activateDestination")}
                  </Button>
                )}
              </div>
              <p
                dir="ltr"
                className="mt-2 overflow-wrap-anywhere text-xs text-muted-foreground"
              >
                {row.url}
              </p>
            </div>
          ))}
        </div>
      )}
      {data.data?.length === 500 && (
        <p className="mt-3 text-xs text-muted-foreground">{t("catalogHint")}</p>
      )}
      <form onSubmit={add} noValidate className="mt-5 space-y-3">
        <Label htmlFor="new_destination">{t("addDestination")}</Label>
        <Input
          id="new_destination"
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
          maxLength={4096}
          placeholder="https://"
        />
        <Button variant="outline" disabled={busy || !url}>
          {t("addDestination")}
        </Button>
      </form>
    </section>
  );
}
