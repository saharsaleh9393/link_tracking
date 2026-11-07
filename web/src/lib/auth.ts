import "server-only";
import { cookies } from "next/headers";
import { SESSION_COOKIE, validSessionSignature, sessionHash } from "./session";
import { authStore } from "./auth-store";
export async function authenticated() {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!validSessionSignature(token, process.env.DASHBOARD_SESSION_SECRET))
    return false;
  try {
    const result = await authStore("validate", {
      token_hash: sessionHash(token!),
    });
    return result.data.valid === true;
  } catch {
    return false;
  } // Fail closed; never fall back to signature-only authorization.
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
