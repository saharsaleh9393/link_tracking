import { describe, it, expect, vi, afterEach } from "vitest";
import en from "../src/messages/en.json";
import fa from "../src/messages/fa.json";
import {
  passwordMatches,
  signSession,
  validSession,
  SESSION_SECONDS,
} from "../src/lib/session";
import { allowedRoute, backend } from "../src/lib/backend";
import { reportRange } from "../src/lib/utils";
import { sameOrigin } from "../src/lib/auth";
describe("bilingual messages", () => {
  it("has the same translated keys and interpolation variables", () => {
    expect(Object.keys(fa).sort()).toEqual(Object.keys(en).sort());
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      expect(fa[key].trim()).not.toBe("");
      expect(fa[key].match(/\{\w+\}/g) || []).toEqual(
        en[key].match(/\{\w+\}/g) || [],
      );
    }
  });
});
describe("sessions", () => {
  const secret = "test-session-secret-".repeat(3);
  it("signs, expires and rejects tampering", () => {
    const now = 1000000;
    const token = signSession(secret, now);
    expect(validSession(token, secret, now + 1)).toBe(true);
    expect(validSession(token, secret, now + SESSION_SECONDS * 1000)).toBe(
      false,
    );
    expect(validSession(token + "x", secret, now)).toBe(false);
    expect(validSession(token, "different".repeat(8), now)).toBe(false);
    expect(validSession("invalid", secret, now)).toBe(false);
  });
  it("checks configured passwords without accepting placeholders", () => {
    expect(passwordMatches("a".repeat(24), "a".repeat(24))).toBe(true);
    expect(passwordMatches("b", "a".repeat(24))).toBe(false);
    expect(passwordMatches("replace-password", "replace-password")).toBe(false);
  });
});
describe("API boundary", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });
  it("restricts forwarding to explicit backend routes", () => {
    expect(allowedRoute("exports/clicks.csv", "GET")).toBe(true);
    expect(allowedRoute("reporting/links", "GET")).toBe(true);
    expect(allowedRoute("exports/clicks.csv", "POST")).toBe(false);
    expect(allowedRoute("links", "POST")).toBe(true);
    expect(allowedRoute("analytics/summary", "GET")).toBe(true);
    for (const path of [
      "../health",
      "https://evil.example",
      "health/ready",
      "links/../../campaigns",
      "admin",
      "links%2F..",
    ])
      expect(allowedRoute(path, "GET")).toBe(false);
    expect(allowedRoute("analytics/summary", "DELETE")).toBe(false);
  });
  it("forwards CSV continuation metadata using the read-only key", async () => {
    vi.stubEnv("REPORT_API_KEY", "test-report-key");
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response("\ufeffclick_id\r\n123\r\n", {
            headers: {
              "Content-Type": "text/csv",
              "X-Export-Row-Count": "1",
              "X-Next-Cursor": "opaque-cursor",
            },
          }),
      ),
    );
    const response = await backend(
      "exports/clicks.csv",
      "GET",
      new URLSearchParams(),
    );
    expect(new TextDecoder().decode(response.csv)).toContain("click_id");
    expect(response.csvHeaders?.["X-Next-Cursor"]).toBe("opaque-cursor");
    expect(response.csvHeaders?.["X-Export-Row-Count"]).toBe("1");
  });
  it("requires exact same-origin writes", () => {
    expect(
      sameOrigin(
        new Request("http://localhost:3100/api/auth", {
          headers: { host: "127.0.0.1:3100", origin: "http://127.0.0.1:3100" },
        }),
      ),
    ).toBe(true);
    expect(
      sameOrigin(
        new Request("http://localhost:3000/api/auth", {
          headers: { origin: "http://localhost:3000" },
        }),
      ),
    ).toBe(true);
    expect(
      sameOrigin(
        new Request("http://localhost:3000/api/auth", {
          headers: { origin: "http://evil.example" },
        }),
      ),
    ).toBe(false);
  });
  it("sends keys only upstream and sanitizes error bodies", async () => {
    vi.stubEnv("ADMIN_API_KEY", "test-admin-key");
    vi.stubEnv("REPORT_API_KEY", "test-report-key");
    let authorization = "";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: unknown, init?: RequestInit) => {
        authorization = new Headers(init?.headers).get("Authorization") || "";
        return new Response(JSON.stringify({ detail: "NEVER EXPOSE THIS" }), {
          status: 409,
        });
      }),
    );
    const result = await backend(
      "campaigns",
      "POST",
      new URLSearchParams(),
      "{}",
    );
    expect(authorization).toBe("Bearer test-admin-key");
    expect(result).toEqual({ error: "DUPLICATE", status: 409 });
    expect(JSON.stringify(result)).not.toContain("NEVER");
    await backend("analytics/summary", "GET", new URLSearchParams());
    expect(authorization).toBe("Bearer test-report-key");
  });
});
it("builds inclusive UTC date filters and rejects reversed ranges", () => {
  expect(reportRange("2026-11-04", "2026-11-04")).toEqual({
    start: "2026-11-04T00:00:00.000Z",
    end: "2026-11-05T00:00:00.000Z",
  });
  expect(() => reportRange("2026-11-05", "2026-11-04")).toThrow();
});
