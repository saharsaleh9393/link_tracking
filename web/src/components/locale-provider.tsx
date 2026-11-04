"use client";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { NextIntlClientProvider } from "next-intl";
import en from "@/messages/en.json";
import fa from "@/messages/fa.json";
import type { Locale } from "@/lib/types";
const Context = createContext<{
  locale: Locale;
  setLocale: (value: Locale) => void;
}>({ locale: "en", setLocale: () => {} });
export function LocaleProvider({
  initialLocale,
  children,
}: {
  initialLocale: Locale;
  children: ReactNode;
}) {
  const [locale, update] = useState(initialLocale);
  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = locale === "fa" ? "rtl" : "ltr";
    const messages = locale === "fa" ? fa : en;
    document.title = `${messages.brand} — ${messages.tagline}`;
  }, [locale]);
  const setLocale = (next: Locale) => {
    document.cookie = `locale=${next}; Path=/; Max-Age=31536000; SameSite=Lax`;
    update(next);
  };
  return (
    <Context.Provider value={{ locale, setLocale }}>
      <NextIntlClientProvider
        locale={locale}
        messages={locale === "fa" ? fa : en}
        timeZone="UTC"
      >
        {children}
      </NextIntlClientProvider>
    </Context.Provider>
  );
}
export function useAppLocale() {
  return useContext(Context);
}
