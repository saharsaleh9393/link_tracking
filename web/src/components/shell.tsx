"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState, type ReactNode } from "react";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  ChevronDown,
  LayoutDashboard,
  Link2,
  LogOut,
  Menu,
  Megaphone,
  MousePointerClick,
  ShieldCheck,
  X,
} from "lucide-react";
import { Button } from "./ui/button";
import { LanguageSwitch } from "./language-switch";
import { cn } from "@/lib/utils";
const nav = [
  ["overview", LayoutDashboard],
  ["campaigns", Megaphone],
  ["links", Link2],
  ["destinations", ArrowUpRight],
  ["analytics", BarChart3],
  ["clicks", MousePointerClick],
] as const;
export function Shell({ children }: { children: ReactNode }) {
  const t = useTranslations(),
    path = usePathname(),
    router = useRouter();
  const [open, setOpen] = useState(false);
  const current =
    nav.find(([key]) => path.startsWith("/" + key))?.[0] || "overview";
  return (
    <div className="min-h-screen">
      <div
        className={cn(
          "fixed inset-0 z-40 bg-slate-950/30 lg:hidden",
          !open && "hidden",
        )}
        onClick={() => setOpen(false)}
      />
      <aside
        id="workspace-sidebar"
        className={cn(
          "fixed inset-y-0 start-0 z-40 flex w-64 flex-col border-e bg-card transition-transform lg:translate-x-0",
          !open &&
            "invisible -translate-x-full rtl:translate-x-full lg:visible lg:rtl:translate-x-0",
        )}
      >
        <div className="flex h-20 items-center justify-between px-7">
          <Link
            href="/overview"
            className="flex items-center gap-2.5 text-xl font-bold tracking-tight"
          >
            <span className="rounded-xl bg-primary p-2 text-white">
              <Link2 className="size-5" />
            </span>
            {t("brand")}
          </Link>
          <button
            onClick={() => setOpen(false)}
            aria-label={t("close")}
            className="lg:hidden"
          >
            <X className="size-5" />
          </button>
        </div>
        <div className="mx-5 mt-4 flex items-center gap-3 rounded-xl border bg-muted/30 p-3">
          <span className="flex size-9 items-center justify-center rounded-lg bg-indigo-100 text-sm font-semibold text-indigo-700">
            M
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold">
              {t("workspaceName")}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {t("local")}
            </p>
          </div>
          <ChevronDown className="size-3 text-muted-foreground" />
        </div>
        <p className="px-7 pt-8 pb-3 text-[10px] font-semibold tracking-widest text-slate-400 uppercase">
          {t("workspace")}
        </p>
        <nav className="space-y-1 px-4">
          {nav.map(([key, Icon]) => (
            <Link
              key={key}
              href={"/" + key}
              onClick={() => setOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-3 text-[13px] font-medium transition",
                current === key
                  ? "bg-primary/8 text-primary"
                  : "text-slate-500 hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="size-[18px]" />
              {t(key)}
              {current === key && (
                <span className="ms-auto size-1.5 rounded-full bg-primary" />
              )}
            </Link>
          ))}
        </nav>
        <div className="mx-5 mt-auto mb-6 rounded-xl border border-primary/10 bg-gradient-to-br from-indigo-50 to-white p-4">
          <ShieldCheck className="mb-3 size-5 text-primary" />
          <p className="text-xs font-semibold">{t("privacy")}</p>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            {t("sidebarFoot")}
          </p>
        </div>
      </aside>
      <div className="lg:ms-64">
        <header className="sticky top-0 z-30 flex h-20 items-center justify-between gap-3 border-b bg-card/95 px-4 backdrop-blur sm:px-8">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              aria-label={t("menu")}
              aria-expanded={open}
              aria-controls="workspace-sidebar"
              onClick={() => setOpen(true)}
            >
              <Menu />
            </Button>
            <span className="hidden text-xs text-muted-foreground sm:inline">
              {t("workspace")}
            </span>
            <span className="hidden text-slate-300 sm:inline">/</span>
            <span className="text-sm font-medium">{t(current)}</span>
          </div>
          <div className="flex items-center gap-3">
            <LanguageSwitch />
            <span className="hidden h-6 border-s sm:block" />
            <button
              title={t("signOut")}
              aria-label={t("signOut")}
              onClick={async () => {
                await fetch("/api/auth", { method: "DELETE" });
                router.replace("/login");
                router.refresh();
              }}
              className="flex items-center gap-2 rounded-lg p-2 text-muted-foreground hover:bg-muted"
            >
              <span className="hidden size-8 items-center justify-center rounded-full bg-amber-100 text-xs font-semibold text-amber-800 sm:flex">
                M
              </span>
              <LogOut className="size-4" />
            </button>
          </div>
        </header>
        <main className="mx-auto max-w-[1600px] p-4 sm:p-8 lg:p-9">
          {children}
        </main>
        <footer className="flex items-center justify-between px-8 pb-6 text-[11px] text-slate-400">
          <span>
            © {new Date().getFullYear()} {t("brand")}
          </span>
          <span className="flex items-center gap-1">
            <Activity className="size-3" />
            {t("tagline")}
            <ArrowUpRight className="size-3 rtl:-scale-x-100" />
          </span>
        </footer>
      </div>
    </div>
  );
}
