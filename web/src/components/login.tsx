"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowRight, Link2, Loader2, ShieldCheck } from "lucide-react";
import { LanguageSwitch } from "./language-switch";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { ErrorNotice } from "./shared";
export function Login() {
  const t = useTranslations(),
    router = useRouter();
  const [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!password) {
      setError("REQUIRED");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.code || "GENERIC");
        return;
      }
      setPassword("");
      router.push("/overview");
      router.refresh();
    } catch {
      setError("UNAVAILABLE");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <section className="relative hidden flex-col justify-between overflow-hidden bg-[#262047] p-14 text-white lg:flex">
        <div className="absolute -end-32 -bottom-40 size-[650px] rounded-full border border-white/10" />
        <div className="absolute -end-12 -bottom-20 size-[460px] rounded-full border border-white/10" />
        <div className="relative flex items-center gap-3 text-xl font-semibold">
          <span className="rounded-xl bg-white/15 p-2.5">
            <Link2 />
          </span>
          {t("brand")}
        </div>
        <div className="relative my-20">
          <p className="mb-6 text-xs tracking-[.2em] text-indigo-200">
            {t("signinBadge")}
          </p>
          <h1 className="whitespace-pre-line text-5xl leading-tight font-semibold tracking-tight">
            {t("signinHero")}
          </h1>
          <p className="mt-7 max-w-sm text-base leading-8 text-indigo-200">
            {t("signinHeroHint")}
          </p>
          <div className="mt-10 flex items-center gap-3 text-xs text-indigo-200">
            <ShieldCheck className="size-4" />
            {t("privacy")}
          </div>
        </div>
        <p className="text-xs text-indigo-300">{t("workspaceHint")}</p>
      </section>
      <section className="flex min-h-screen flex-col bg-white p-6 sm:p-12">
        <div className="flex justify-end">
          <LanguageSwitch />
        </div>
        <div className="m-auto w-full max-w-sm py-16">
          <span className="mb-8 inline-flex rounded-xl bg-primary/10 p-3 text-primary">
            <Link2 className="size-6" />
          </span>
          <h2 className="text-2xl font-semibold">{t("signinTitle")}</h2>
          <p className="mt-3 mb-8 text-sm leading-6 text-muted-foreground">
            {t("signinDescription")}
          </p>
          <form onSubmit={submit} noValidate>
            <Label htmlFor="password">{t("password")}</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              maxLength={1024}
            />
            <ErrorNotice code={error} />
            <Button className="mt-6 w-full" disabled={busy}>
              {busy ? (
                <Loader2 className="animate-spin" />
              ) : (
                <ArrowRight className="rtl:rotate-180" />
              )}
              {t("signin")}
            </Button>
          </form>
          <p className="mt-6 text-xs leading-6 text-muted-foreground">
            {t("signinHint")}
          </p>
        </div>
      </section>
    </div>
  );
}
