import "server-only";
import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { isIP } from "node:net";
import { configured } from "./session";

export class UntrustedLoginClient extends Error {}
export function loginClientKey(request: Request) {
  const proof = request.headers.get("x-linkspace-proxy-token") || "";
  const proxySecret = process.env.DASHBOARD_PROXY_SECRET;
  let client = "unverified-development-client";
  if (configured(proxySecret)) {
    if (
      proof.length > 256 ||
      !timingSafeEqual(
        createHash("sha256").update(proof).digest(),
        createHash("sha256").update(proxySecret!).digest(),
      )
    )
      throw new UntrustedLoginClient();
    client = request.headers.get("x-linkspace-client-ip") || "";
    if (!isIP(client)) throw new UntrustedLoginClient();
  } else if (["production", "simulation"].includes(process.env.APP_ENV || "")) {
    throw new UntrustedLoginClient();
  }
  // Raw IPs never reach the database. Unverified headers cannot create new buckets.
  return createHmac("sha256", process.env.DASHBOARD_SESSION_SECRET!)
    .update("login-client:" + client)
    .digest("hex");
}
