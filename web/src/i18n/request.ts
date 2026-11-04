import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import en from "@/messages/en.json";
import fa from "@/messages/fa.json";
export default getRequestConfig(async () => {
  // Explicit preference only: never auto-detect Accept-Language on first visit.
  const locale = (await cookies()).get("locale")?.value === "fa" ? "fa" : "en";
  return { locale, messages: locale === "fa" ? fa : en, timeZone: "UTC" };
});
