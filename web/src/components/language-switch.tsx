"use client";
import { useTranslations } from "next-intl";
import { useAppLocale } from "./locale-provider";
import { cn } from "@/lib/utils";
export function LanguageSwitch() {
  const { locale, setLocale } = useAppLocale();
  const t = useTranslations();
  return (
    <div
      role="group"
      aria-label={t("language")}
      className="inline-flex rounded-lg border bg-muted/40 p-1"
      dir="ltr"
    >
      {(["en", "fa"] as const).map((value) => (
        <button
          type="button"
          key={value}
          aria-pressed={locale === value}
          onClick={() => setLocale(value)}
          className={cn(
            "rounded-md px-2.5 py-1.5 text-xs font-semibold transition",
            locale === value
              ? "bg-white text-primary shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {value.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
