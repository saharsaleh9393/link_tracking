import {
  createHash,
  createHmac,
  randomBytes,
  timingSafeEqual,
} from "node:crypto";
export const SESSION_COOKIE = "linkspace_session";
export const SESSION_SECONDS = 8 * 60 * 60;
export function configured(secret: string | undefined) {
  return !!secret && secret.length >= 32 && !secret.startsWith("replace-");
}
export function passwordMatches(
  candidate: string,
  expected: string | undefined,
) {
  if (
    !expected ||
    expected.length < 20 ||
    expected.startsWith("replace-") ||
    candidate.length > 1024
  )
    return false;
  return timingSafeEqual(
    createHash("sha256").update(candidate).digest(),
    createHash("sha256").update(expected).digest(),
  );
}
export function signSession(secret: string, now = Date.now()) {
  if (!configured(secret)) throw Error("CONFIG");
  const payload = Buffer.from(
    JSON.stringify({
      expires: now + SESSION_SECONDS * 1000,
      nonce: randomBytes(16).toString("hex"),
    }),
  ).toString("base64url");
  return (
    payload +
    "." +
    createHmac("sha256", secret).update(payload).digest("base64url")
  );
}
// Signature/expiry verification is necessary but never sufficient for authorization.
export function validSessionSignature(
  token: string | undefined,
  secret: string | undefined,
  now = Date.now(),
) {
  if (!token || token.length > 1024 || !configured(secret)) return false;
  try {
    const [payload, signature, ...rest] = token.split(".");
    if (rest.length || !payload || !signature) return false;
    const expected = createHmac("sha256", secret!).update(payload).digest();
    const actual = Buffer.from(signature, "base64url");
    if (actual.length !== expected.length || !timingSafeEqual(actual, expected))
      return false;
    const decoded = JSON.parse(Buffer.from(payload, "base64url").toString());
    return (
      typeof decoded.expires === "number" &&
      typeof decoded.nonce === "string" &&
      /^[a-f0-9]{32}$/.test(decoded.nonce) &&
      decoded.expires > now &&
      decoded.expires <= now + SESSION_SECONDS * 1000 + 30_000
    );
  } catch {
    return false;
  }
}
export function sessionHash(token: string) {
  return createHash("sha256").update(token).digest("hex");
}
