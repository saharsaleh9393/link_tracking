import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { authStore, AuthStoreUnavailable } from "../src/lib/auth-store";
beforeEach(() => {
  vi.stubEnv("ADMIN_API_KEY", "private-admin-".repeat(4));
  vi.stubEnv("TRACKER_API_URL", "http://api:8000");
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
describe("private authentication store transport", () => {
  it("uses the fixed private endpoint and authenticated no-cache POST", async () => {
    const fetcher = vi.fn().mockResolvedValue(Response.json({ valid: true }));
    vi.stubGlobal("fetch", fetcher);
    expect(
      (await authStore("validate", { token_hash: "a".repeat(64) })).data.valid,
    ).toBe(true);
    const [url, options] = fetcher.mock.calls[0];
    expect(String(url)).toBe("http://api:8000/api/v1/dashboard-auth/validate");
    expect(options).toMatchObject({
      method: "POST",
      cache: "no-store",
      redirect: "error",
    });
    expect(options.headers.Authorization).toBe(
      `Bearer ${process.env.ADMIN_API_KEY}`,
    );
    expect(options.body).not.toContain("linkspace_session");
  });
  it("preserves rate limits with bounded Retry-After", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { code: "RATE_LIMIT" },
            { status: 429, headers: { "Retry-After": "3" } },
          ),
        ),
    );
    expect(await authStore("login", {})).toMatchObject({
      status: 429,
      retryAfter: "3",
    });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { code: "RATE_LIMIT" },
            { status: 429, headers: { "Retry-After": "invalid" } },
          ),
        ),
    );
    expect((await authStore("login", {})).retryAfter).toBe("60");
  });
  it("distinguishes invalid credentials from broken internal authentication", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(Response.json({ code: "LOGIN" }, { status: 401 })),
    );
    expect((await authStore("login", {})).status).toBe(401);
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json({ detail: "internal key rejected" }, { status: 401 }),
        ),
    );
    await expect(authStore("login", {})).rejects.toBeInstanceOf(
      AuthStoreUnavailable,
    );
  });
  it("fails closed and sanitizes database, invalid JSON and network errors", async () => {
    for (const response of [
      new Response("private database failure", { status: 500 }),
      new Response("not json", { status: 200 }),
    ]) {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
      await expect(authStore("validate", {})).rejects.toThrow("UNAVAILABLE");
    }
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(Error("private connection details")),
    );
    await expect(authStore("revoke", {})).rejects.toThrow("UNAVAILABLE");
  });
  it("rejects URLs containing credentials before fetching", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    vi.stubEnv("TRACKER_API_URL", "http://private:password@api:8000");
    await expect(authStore("login", {})).rejects.toThrow("UNAVAILABLE");
    expect(fetcher).not.toHaveBeenCalled();
  });
});
