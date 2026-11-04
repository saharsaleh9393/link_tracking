import { NextResponse } from "next/server";
import { sameOrigin } from "@/lib/auth";
import {
  configured,
  passwordMatches,
  signSession,
  SESSION_COOKIE,
  SESSION_SECONDS,
} from "@/lib/session";
export const runtime = "nodejs";
let attempts = 0;
let reset = 0;
export async function POST(request: Request) {
  if (!sameOrigin(request))
    return NextResponse.json({ code: "FORBIDDEN" }, { status: 403 });
  if (
    !configured(process.env.DASHBOARD_SESSION_SECRET) ||
    !process.env.DASHBOARD_PASSWORD ||
    process.env.DASHBOARD_PASSWORD.length < 20 ||
    process.env.DASHBOARD_PASSWORD.startsWith("replace-")
  )
    return NextResponse.json({ code: "CONFIG" }, { status: 503 });
  if (Date.now() > reset) {
    attempts = 0;
    reset = Date.now() + 60000;
  }
  if (++attempts > 10)
    return NextResponse.json(
      { code: "RATE_LIMIT" },
      { status: 429, headers: { "Retry-After": "60" } },
    );
  let input;
  try {
    const text = await request.text();
    if (text.length > 2048) throw Error();
    input = JSON.parse(text);
  } catch {
    return NextResponse.json({ code: "VALIDATION" }, { status: 422 });
  }
  if (
    !input ||
    typeof input !== "object" ||
    typeof input.password !== "string" ||
    !passwordMatches(input.password, process.env.DASHBOARD_PASSWORD)
  )
    return NextResponse.json({ code: "LOGIN" }, { status: 401 });
  const response = NextResponse.json({ ok: true });
  response.cookies.set(
    SESSION_COOKIE,
    signSession(process.env.DASHBOARD_SESSION_SECRET!),
    {
      httpOnly: true,
      secure: process.env.DASHBOARD_SECURE_COOKIES === "true",
      sameSite: "strict",
      path: "/",
      maxAge: SESSION_SECONDS,
    },
  );
  response.headers.set("Cache-Control", "no-store");
  return response;
}
export async function DELETE(request: Request) {
  if (!sameOrigin(request))
    return NextResponse.json({ code: "FORBIDDEN" }, { status: 403 });
  const response = NextResponse.json({ ok: true });
  response.cookies.delete(SESSION_COOKIE);
  return response;
}
