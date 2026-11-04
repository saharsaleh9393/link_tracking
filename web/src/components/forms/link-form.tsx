"use client";
import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";
import type { Campaign, Link } from "@/lib/types";
import { utmKeys } from "@/lib/types";
import { request, ApiError } from "@/lib/client";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { ErrorNotice } from "../shared";
export function LinkForm({
  link,
  campaigns,
  onSaved,
  onCancel,
}: {
  link?: Link;
  campaigns: Campaign[];
  onSaved: (link: Link) => void;
  onCancel: () => void;
}) {
  const t = useTranslations();
  const [error, setError] = useState(""),
    [validation, setValidation] = useState(""),
    [busy, setBusy] = useState(false);
  const originalExpiry = link?.expires_at || "";
  const initialExpiry = originalExpiry
    ? new Date(originalExpiry).toISOString().slice(0, 16)
    : "";
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError("");
    setValidation("");
    const slug = String(form.get("slug") || "").trim(),
      destination = String(form.get("destination_url") || "").trim();
    if (!link) {
      try {
        const url = new URL(destination);
        if (!["http:", "https:"].includes(url.protocol)) throw Error();
      } catch {
        setValidation("invalidUrl");
        return;
      }
      if (slug && !/^[A-Za-z0-9_-]{3,80}$/.test(slug)) {
        setValidation("invalidSlug");
        return;
      }
    }
    const expiry = String(form.get("expires_at") || "");
    const body: Record<string, unknown> = {
      campaign_id: form.get("campaign_id") || null,
      forward_utm: form.get("forward_utm") === "on",
      expires_at:
        expiry === initialExpiry
          ? originalExpiry || null
          : expiry
            ? new Date(expiry + "Z").toISOString()
            : null,
    };
    utmKeys.forEach(
      (key) => (body[key] = String(form.get(key) || "").trim() || null),
    );
    if (link) {
      body.expected_version = link.version;
      body.status = form.get("active") === "on" ? "active" : "disabled";
      if (body.campaign_id === link.campaign_id) delete body.campaign_id;
    } else {
      body.destination_url = destination;
      body.slug = slug || null;
    }
    setBusy(true);
    try {
      const saved = await request<Link>(link ? "links/" + link.id : "links", {
        method: link ? "PATCH" : "POST",
        body,
      });
      onSaved(saved);
    } catch (e) {
      setError(e instanceof ApiError ? e.code : "GENERIC");
    } finally {
      setBusy(false);
    }
  }
  const candidates = campaigns.filter(
    (c) => !c.archived || c.id === link?.campaign_id,
  );
  return (
    <form onSubmit={submit} className="mt-6 space-y-5" noValidate>
      {!link && (
        <>
          <div>
            <Label htmlFor="destination_url">{t("destination")}</Label>
            <Input
              id="destination_url"
              name="destination_url"
              type="url"
              maxLength={4096}
              placeholder="https://www.instagram.com/your-brand/"
              required
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              {t("destinationHint")}
            </p>
          </div>
          <div>
            <Label htmlFor="slug">{t("slug")}</Label>
            <Input id="slug" name="slug" dir="ltr" maxLength={80} />
            <p className="mt-1.5 text-xs text-muted-foreground">
              {t("slugHint")}
            </p>
          </div>
        </>
      )}
      <div>
        <Label htmlFor="campaign_id">{t("campaign")}</Label>
        <select
          id="campaign_id"
          name="campaign_id"
          className="w-full"
          defaultValue={link?.campaign_id || ""}
        >
          <option value="">{t("none")}</option>
          {link?.campaign_id &&
            !candidates.some((c) => c.id === link.campaign_id) && (
              <option value={link.campaign_id}>{t("campaignOutside")}</option>
            )}
          {candidates.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
              {c.archived ? " · " + t("archived") : ""}
            </option>
          ))}
        </select>
      </div>
      {link && (
        <label className="flex items-center gap-3 text-sm">
          <input
            type="checkbox"
            name="active"
            defaultChecked={link.status === "active"}
          />
          {t("active")}
        </label>
      )}
      <div className="rounded-xl border bg-muted/25 p-4">
        <h3 className="mb-4 text-sm font-semibold">{t("utmTitle")}</h3>
        <div className="grid gap-4 sm:grid-cols-2">
          {utmKeys.map((key) => (
            <div key={key}>
              <Label htmlFor={key}>{t(key)}</Label>
              <Input
                id={key}
                name={key}
                defaultValue={link?.[key] || ""}
                maxLength={200}
              />
            </div>
          ))}
        </div>
      </div>
      <div>
        <Label htmlFor="expires_at">{t("expires")}</Label>
        <Input
          id="expires_at"
          name="expires_at"
          type="datetime-local"
          defaultValue={initialExpiry}
        />
        <p className="mt-1.5 text-xs text-muted-foreground">
          {t("expiresHint")}
        </p>
      </div>
      <div>
        <label className="flex items-center gap-3 text-sm">
          <input
            name="forward_utm"
            type="checkbox"
            defaultChecked={link?.forward_utm || false}
          />
          {t("forwardUtm")}
        </label>
        <p className="mt-2 text-xs text-muted-foreground">{t("utmHint")}</p>
      </div>
      {validation && (
        <p role="alert" className="text-sm text-red-600">
          {t(validation)}
        </p>
      )}
      <ErrorNotice code={error} />
      <div className="flex justify-end gap-2 border-t pt-5">
        <Button type="button" variant="outline" onClick={onCancel}>
          {t("cancel")}
        </Button>
        <Button disabled={busy}>
          {busy && <Loader2 className="animate-spin" />}
          {t(link ? "save" : "newLink")}
        </Button>
      </div>
    </form>
  );
}
