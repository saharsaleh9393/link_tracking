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
import { reportCsv, jsonReportPath } from "../src/lib/csv";
import { linkPreview } from "../src/lib/linkspaces";
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
    const space = "linkspaces/00000000-0000-0000-0000-000000000003";
    expect(allowedRoute("linkspaces", "GET")).toBe(true);
    expect(allowedRoute("linkspaces", "POST")).toBe(true);
    expect(allowedRoute(space, "PUT")).toBe(true);
    expect(allowedRoute(space, "DELETE")).toBe(true);
    expect(allowedRoute("linkspaces", "PUT")).toBe(false);
    expect(allowedRoute("linkspaces/../../health", "PUT")).toBe(false);
    expect(allowedRoute("exports/clicks.csv", "GET")).toBe(true);
    expect(allowedRoute("reporting/links", "GET")).toBe(true);
    expect(allowedRoute("exports/clicks.csv", "POST")).toBe(false);
    expect(allowedRoute("analytics/trends.csv", "GET")).toBe(true);
    expect(allowedRoute("analytics/breakdowns.csv", "GET")).toBe(true);
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
  it.each([
    "exports/clicks.csv",
    "analytics/trends.csv",
    "analytics/breakdowns.csv",
  ])(
    "exports %s through the JSON report when CSV returns 404",
    async (path) => {
      vi.stubEnv("REPORT_API_KEY", "test-report-key");
      vi.stubEnv("TRACKER_API_URL", "http://127.0.0.1:8000");
      const query = new URLSearchParams({
        start: "2026-11-01T00:00:00Z",
        end: "2026-11-05T00:00:00Z",
        limit: "50",
        cursor: "page-cursor",
      });
      const calls: { url: URL; key: string }[] = [];
      vi.stubGlobal(
        "fetch",
        vi.fn(async (url: URL, init: RequestInit) => {
          calls.push({
            url: new URL(url),
            key: new Headers(init.headers).get("Authorization") || "",
          });
          return url.pathname.endsWith(".csv")
            ? new Response("missing", { status: 404 })
            : Response.json({
                items: [
                  {
                    click_id: "click-1",
                    value: "instagram",
                    bucket: "2026-11-01",
                    total_clicks: 1,
                  },
                ],
                next_cursor: "next-page",
                partial_history: true,
              });
        }),
      );
      const result = await backend(path, "GET", query);
      expect(result.status).toBe(200);
      expect(result.csvHeaders?.["X-Next-Cursor"]).toBe("next-page");
      expect(result.csvHeaders?.["X-Partial-History"]).toBe("true");
      expect(calls.map((c) => c.url.pathname)).toEqual([
        "/api/v1/" + path,
        "/api/v1/" + path.slice(0, -4),
      ]);
      expect(
        calls.every(
          (c) =>
            c.url.search === "?" + query.toString() &&
            c.key === "Bearer test-report-key",
        ),
      ).toBe(true);
      expect(new TextDecoder().decode(result.csv)).not.toContain(
        "test-report-key",
      );
    },
  );
  it("does not retry rejected CSV credentials and explains missing reporting routes", async () => {
    vi.stubEnv("REPORT_API_KEY", "test-report-key");
    const fetcher = vi.fn(async () => new Response("", { status: 401 }));
    vi.stubGlobal("fetch", fetcher);
    expect(
      await backend("exports/clicks.csv", "GET", new URLSearchParams()),
    ).toEqual({ error: "AUTH", status: 401 });
    expect(fetcher).toHaveBeenCalledTimes(1);
    fetcher.mockImplementation(async () => new Response("", { status: 404 }));
    expect(
      await backend("exports/clicks.csv", "GET", new URLSearchParams()),
    ).toEqual({ error: "CSV_UNAVAILABLE", status: 503 });
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
  it("localizes only known Linkspace error codes and keeps configuration calls administrative", async () => {
    vi.stubEnv("ADMIN_API_KEY", "admin-secret");
    let key = "";
    const fetcher = vi.fn(async (_url: unknown, init?: RequestInit) => {
      key = new Headers(init?.headers).get("Authorization") || "";
      return Response.json(
        { detail: { code: "LINKSPACE_ROOT_UNSAFE", private: "PRIVATE" } },
        { status: 422 },
      );
    });
    vi.stubGlobal("fetch", fetcher);
    const result = await backend(
      "linkspaces",
      "POST",
      new URLSearchParams(),
      "{}",
    );
    expect(result).toEqual({ error: "LINKSPACE_ROOT_UNSAFE", status: 422 });
    expect(key).toBe("Bearer admin-secret");
    expect(JSON.stringify(result)).not.toContain("PRIVATE");
    fetcher.mockImplementation(async () =>
      Response.json({ detail: { code: "PRIVATE" } }, { status: 422 }),
    );
    expect(
      await backend("linkspaces", "POST", new URLSearchParams(), "{}"),
    ).toEqual({ error: "VALIDATION", status: 422 });
  });
  it.each([
    ["base_url", "LINKSPACE_URL"],
    ["path_prefix", "LINKSPACE_PREFIX"],
    ["name", "LINKSPACE_NAME"],
  ])(
    "explains Linkspace %s validation without leaking submitted input",
    async (field, code) => {
      vi.stubEnv("ADMIN_API_KEY", "admin-secret");
      vi.stubGlobal(
        "fetch",
        vi.fn(async () =>
          Response.json(
            {
              detail: [
                {
                  loc: ["body", field],
                  msg: "PRIVATE submitted input",
                  input: "PRIVATE",
                },
              ],
            },
            { status: 422 },
          ),
        ),
      );
      const result = await backend(
        "linkspaces",
        "POST",
        new URLSearchParams(),
        "{}",
      );
      expect(result).toEqual({ error: code, status: 422 });
      expect(JSON.stringify(result)).not.toContain("PRIVATE");
    },
  );
});
it("previews root and prefixed Linkspace URLs consistently", () => {
  expect(linkPreview("https://go.example.com/", "")).toBe(
    "https://go.example.com/slug",
  );
  expect(linkPreview("http://localhost:8000", "/GO/", "launch")).toBe(
    "http://localhost:8000/go/launch",
  );
});
it("serializes legacy JSON with Persian text, safe spreadsheet cells and no private columns", () => {
  const report = reportCsv("exports/clicks.csv", {
    items: [
      {
        click_id: "one",
        utm_source: "فارسی, منبع",
        utm_content: "=SUM(1,1)",
        visitor_digest: "PRIVATE-VISITOR",
        ip: "PRIVATE-IP",
      },
    ],
  });
  const bytes = new Uint8Array(report.csv);
  expect(Array.from(bytes.slice(0, 3))).toEqual([239, 187, 191]);
  const csv = new TextDecoder().decode(bytes);
  expect(csv).toContain('"فارسی, منبع"');
  expect(csv).toContain('"\'=SUM(1,1)"');
  expect(csv).not.toContain("PRIVATE");
  expect(jsonReportPath("__proto__")).toBeNull();
  expect(jsonReportPath("unlisted.csv")).toBeNull();
});
it("builds inclusive UTC date filters and rejects reversed ranges", () => {
  expect(reportRange("2026-11-04", "2026-11-04")).toEqual({
    start: "2026-11-04T00:00:00.000Z",
    end: "2026-11-05T00:00:00.000Z",
  });
  expect(() => reportRange("2026-11-05", "2026-11-04")).toThrow();
});
