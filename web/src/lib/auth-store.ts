import "server-only";
import { configured } from "./session";

export class AuthStoreUnavailable extends Error {
  constructor() {
    super("UNAVAILABLE");
  }
}
export async function authStore(
  action: "login" | "validate" | "revoke",
  body: unknown,
) {
  const key = process.env.ADMIN_API_KEY;
  if (!configured(key)) throw new AuthStoreUnavailable();
  try {
    const base = new URL(
      process.env.TRACKER_API_URL || "http://127.0.0.1:8000",
    );
    if (
      !["http:", "https:"].includes(base.protocol) ||
      base.username ||
      base.password ||
      base.search ||
      base.hash
    )
      throw Error();
    const url = new URL(
      `${base.pathname.replace(/\/$/, "")}/api/v1/dashboard-auth/${action}`,
      base,
    );
    const response = await fetch(url, {
      method: "POST",
      body: JSON.stringify(body),
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
      },
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(3000),
    });
    const data = await response.json();
    if (response.ok)
      return { status: response.status, data, retryAfter: undefined };
    if (
      action === "login" &&
      ((response.status === 401 && data.code === "LOGIN") ||
        (response.status === 429 && data.code === "RATE_LIMIT"))
    ) {
      const seconds = Number(response.headers.get("Retry-After"));
      return {
        status: response.status,
        data,
        retryAfter: String(
          seconds >= 1 && seconds <= 3600 ? Math.ceil(seconds) : 60,
        ),
      };
    }
    throw Error();
  } catch {
    throw new AuthStoreUnavailable();
  }
}
