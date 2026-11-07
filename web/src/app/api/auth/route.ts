import { NextResponse } from "next/server";
import { sameOrigin } from "@/lib/auth";
import { cookies } from "next/headers";
import { authStore } from "@/lib/auth-store";
import { loginClientKey, UntrustedLoginClient } from "@/lib/login-client";
import {
  configured,
  passwordMatches,
  signSession,
  SESSION_COOKIE,
  SESSION_SECONDS,
  sessionHash,
} from "@/lib/session";
export const runtime = "nodejs";
function failure(code: string, status: number, retryAfter?: string) {
  return NextResponse.json(
    { code },
    {
      status,
      headers: {
        "Cache-Control": "no-store",
        ...(retryAfter ? { "Retry-After": retryAfter } : {}),
      },
    },
  );
}
export async function POST(request: Request) {
  if (!sameOrigin(request)) return failure("FORBIDDEN", 403);
  if (
    !configured(process.env.DASHBOARD_SESSION_SECRET) ||
    !process.env.DASHBOARD_PASSWORD ||
    process.env.DASHBOARD_PASSWORD.length < 20 ||
    process.env.DASHBOARD_PASSWORD.startsWith("replace-")
  )
    return failure("CONFIG", 503);
  let clientKey;
  try {
    clientKey = loginClientKey(request);
  } catch (error) {
    return failure(
      error instanceof UntrustedLoginClient ? "FORBIDDEN" : "CONFIG",
      error instanceof UntrustedLoginClient ? 403 : 503,
    );
  }
  let input;
  try {
    const text = await request.text();
    if (text.length > 2048) throw Error();
    input = JSON.parse(text);
  } catch {
    input = null;
  }
  const wellFormed =
    input &&
    typeof input === "object" &&
    !Array.isArray(input) &&
    typeof input.password === "string" &&
    input.password.length <= 1024 &&
    Object.keys(input).every((key) => key === "password");
  const valid =
    !!wellFormed &&
    passwordMatches(input.password, process.env.DASHBOARD_PASSWORD);
  const now = Date.now();
  const token = valid
    ? signSession(process.env.DASHBOARD_SESSION_SECRET!, now)
    : undefined;
  try {
    const result = await authStore("login", {
      client_key: clientKey,
      credentials_valid: valid,
      ...(token
        ? {
            token_hash: sessionHash(token),
            expires_at: new Date(now + SESSION_SECONDS * 1000).toISOString(),
          }
        : {}),
    });
    if (result.status === 429)
      return failure("RATE_LIMIT", 429, result.retryAfter);
    if (!wellFormed) return failure("VALIDATION", 422);
    if (!valid) return failure("LOGIN", 401);
    if (result.data.ok !== true) return failure("UNAVAILABLE", 503);
  } catch {
    return failure("UNAVAILABLE", 503);
  }
  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE, token!, {
    httpOnly: true,
    secure: process.env.DASHBOARD_SECURE_COOKIES === "true",
    sameSite: "strict",
    path: "/",
    maxAge: SESSION_SECONDS,
  });
  response.headers.set("Cache-Control", "no-store");
  return response;
}
export async function DELETE(request: Request) {
  if (!sameOrigin(request)) return failure("FORBIDDEN", 403);
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (token && token.length <= 1024) {
    try {
      const result = await authStore("revoke", {
        token_hash: sessionHash(token),
      });
      if (result.data.ok !== true) return failure("UNAVAILABLE", 503);
    } catch {
      return failure("UNAVAILABLE", 503);
    }
  }
  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE, "", {
    httpOnly: true,
    secure: process.env.DASHBOARD_SECURE_COOKIES === "true",
    sameSite: "strict",
    path: "/",
    maxAge: 0,
    expires: new Date(0),
  });
  response.headers.set("Cache-Control", "no-store");
  return response;
}
