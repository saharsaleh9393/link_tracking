import "server-only";
import { cookies } from "next/headers";
import { SESSION_COOKIE, validSession } from "./session";
export async function authenticated() {
  return validSession(
    (await cookies()).get(SESSION_COOKIE)?.value,
    process.env.DASHBOARD_SESSION_SECRET,
  );
}
export function sameOrigin(request: Request) {
  const url = new URL(request.url);
  // Next may normalize request.url to localhost. Host is browser-controlled only by the
  // actual destination, not by cross-origin JavaScript; preserve it at trusted ingress.
  const expected =
    process.env.DASHBOARD_ORIGIN ||
    `${url.protocol}//${request.headers.get("host") || url.host}`;
  return request.headers.get("origin") === expected;
}
