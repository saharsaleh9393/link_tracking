"use client";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
export default function NotFound() {
  const t = useTranslations();
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center gap-5 p-8 text-center">
      <h1 className="text-5xl font-semibold">404</h1>
      <p>{t("error_NOT_FOUND")}</p>
      <Button asChild>
        <Link href="/overview">{t("overview")}</Link>
      </Button>
    </main>
  );
}
