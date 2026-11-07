import { beforeEach, afterEach, describe, it, expect, vi } from "vitest";
const state = vi.hoisted(() => ({
  cookie: undefined as string | undefined,
  sessions: new Set<string>(),
  fail: false,
}));
vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: () => (state.cookie ? { value: state.cookie } : undefined),
  }),
}));
vi.mock("../src/lib/auth-store", () => ({
  authStore: vi.fn(
    async (
      action: string,
      body: { token_hash?: string; credentials_valid?: boolean },
    ) => {
      if (state.fail) throw Error("UNAVAILABLE");
      if (action === "login") {
        if (!body.credentials_valid)
          return { status: 401, data: { code: "LOGIN" } };
        state.sessions.add(body.token_hash!);
        return { status: 200, data: { ok: true } };
      }
      if (action === "revoke") {
        state.sessions.delete(body.token_hash!);
        return { status: 200, data: { ok: true } };
      }
      return {
        status: 200,
        data: { valid: state.sessions.has(body.token_hash!) },
      };
    },
  ),
}));
import { POST, DELETE } from "../src/app/api/auth/route";
import { authenticated } from "../src/lib/auth";
import { loginClientKey } from "../src/lib/login-client";
import { sessionHash, signSession, SESSION_SECONDS } from "../src/lib/session";
const secret = "unit-session-".repeat(4),
  password = "unit-dashboard-password-strong-and-private";
function request(body: string, origin = "http://localhost:3000") {
  return new Request("http://localhost:3000/api/auth", {
    method: "POST",
    headers: { origin, host: "localhost:3000" },
    body,
  });
}
beforeEach(() => {
  state.cookie = undefined;
  state.sessions.clear();
  state.fail = false;
  vi.stubEnv("APP_ENV", "development");
  vi.stubEnv("DASHBOARD_PROXY_SECRET", "");
  vi.stubEnv("DASHBOARD_ORIGIN", "");
  vi.stubEnv("DASHBOARD_SESSION_SECRET", secret);
  vi.stubEnv("DASHBOARD_PASSWORD", password);
  vi.stubEnv("DASHBOARD_SECURE_COOKIES", "true");
});
afterEach(() => vi.unstubAllEnvs());
describe("server backed dashboard authentication", () => {
  it("issues protected cookies and rejects a copied token immediately after logout", async () => {
    const response = await POST(request(JSON.stringify({ password })));
    expect(response.status).toBe(200);
    const cookie = response.cookies.get("linkspace_session")!;
    state.cookie = cookie.value;
    expect(cookie.httpOnly).toBe(true);
    expect(cookie.sameSite).toBe("strict");
    expect(cookie.secure).toBe(true);
    expect(cookie.maxAge).toBe(SESSION_SECONDS);
    expect(await authenticated()).toBe(true);
    expect((await DELETE(request(""))).status).toBe(200);
    expect(await authenticated()).toBe(false);
    expect(state.sessions.has(sessionHash(cookie.value))).toBe(false);
  });
  it("fails closed on database errors and does not report a failed revocation as successful", async () => {
    state.cookie = signSession(secret);
    state.sessions.add(sessionHash(state.cookie));
    state.fail = true;
    expect(await authenticated()).toBe(false);
    const response = await DELETE(request(""));
    expect(response.status).toBe(503);
    expect(response.cookies.get("linkspace_session")).toBeUndefined();
    expect((await POST(request(JSON.stringify({ password })))).status).toBe(
      503,
    );
  });
  it("rejects legacy, expired and tampered tokens even if their signatures used to be valid", async () => {
    const token = signSession(secret);
    state.cookie = token;
    expect(await authenticated()).toBe(false);
    state.sessions.add(sessionHash(token));
    state.cookie = token + "tampered";
    expect(await authenticated()).toBe(false);
    state.cookie = signSession(secret, Date.now() - SESSION_SECONDS * 1000 - 1);
    state.sessions.add(sessionHash(state.cookie));
    expect(await authenticated()).toBe(false);
  });
  it("rejects wrong passwords, malformed bodies and invalid origins", async () => {
    expect(
      (await POST(request(JSON.stringify({ password: "incorrect" })))).status,
    ).toBe(401);
    for (const body of [
      "{",
      "null",
      "[]",
      "{}",
      JSON.stringify({ password: 42 }),
      "x".repeat(2049),
    ])
      expect((await POST(request(body))).status).toBe(422);
    expect(
      (
        await POST(
          request(JSON.stringify({ password }), "https://evil.invalid"),
        )
      ).status,
    ).toBe(403);
    expect((await DELETE(request("", "https://evil.invalid"))).status).toBe(
      403,
    );
  });
});
describe("trusted login client identity", () => {
  it("ignores attacker supplied forwarding headers without proxy proof", () => {
    expect(
      loginClientKey(
        new Request("http://localhost", {
          headers: { "x-forwarded-for": "1.1.1.1" },
        }),
      ),
    ).toBe(
      loginClientKey(
        new Request("http://localhost", {
          headers: {
            "x-forwarded-for": "8.8.8.8",
            "x-linkspace-client-ip": "8.8.8.8",
          },
        }),
      ),
    );
  });
  it("requires ingress proof in production and hashes distinct real client IPs", () => {
    vi.stubEnv("APP_ENV", "production");
    const proxy = "unit-proxy-secret-".repeat(3);
    vi.stubEnv("DASHBOARD_PROXY_SECRET", proxy);
    expect(() =>
      loginClientKey(
        new Request("http://localhost", {
          headers: { "x-forwarded-for": "1.1.1.1" },
        }),
      ),
    ).toThrow();
    const client = (ip: string) =>
      loginClientKey(
        new Request("http://localhost", {
          headers: {
            "x-linkspace-proxy-token": proxy,
            "x-linkspace-client-ip": ip,
          },
        }),
      );
    expect(client("1.1.1.1")).not.toBe(client("8.8.8.8"));
    expect(client("1.1.1.1")).toMatch(/^[a-f0-9]{64}$/);
  });
});
