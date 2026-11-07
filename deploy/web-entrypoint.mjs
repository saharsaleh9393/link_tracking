import { readFileSync } from "node:fs";

try {
  for (const key of ["ADMIN_API_KEY", "REPORT_API_KEY", "DASHBOARD_PASSWORD", "DASHBOARD_SESSION_SECRET"]) {
    if (process.env[key + "_FILE"]) {
      if (process.env[key]) throw Error("Ambiguous secret");
      process.env[key] = readFileSync(process.env[key + "_FILE"], "utf8").trim();
    }
    if (!process.env[key] || process.env[key].length < 32 || process.env[key].startsWith("replace-")) throw Error("Configure secrets");
  }
  const origin = new URL(process.env.DASHBOARD_ORIGIN);
  if (origin.origin !== process.env.DASHBOARD_ORIGIN || origin.username || origin.password) throw Error("Configure dashboard origin");
  if (process.env.APP_ENV === "production" && (origin.protocol !== "https:" || process.env.DASHBOARD_SECURE_COOKIES !== "true")) throw Error("HTTPS cookies required");
  await import("./server.js");
} catch {
  console.error(JSON.stringify({ event: "dashboard_startup_failed", message: "Check origin and mounted secrets" }));
  process.exit(1);
}
