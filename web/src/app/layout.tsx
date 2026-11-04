import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import { LocaleProvider } from "@/components/locale-provider";
import type { Locale } from "@/lib/types";
import "./globals.css";
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations();
  return {
    title: `${t("brand")} — ${t("tagline")}`,
    description: t("signinDescription"),
  };
}
export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = (await getLocale()) as Locale;
  return (
    <html lang={locale} dir={locale === "fa" ? "rtl" : "ltr"}>
      <body>
        <LocaleProvider initialLocale={locale}>{children}</LocaleProvider>
      </body>
    </html>
  );
}
