import "server-only";
export function publicBase() {
  try {
    const url = new URL(process.env.PUBLIC_BASE_URL || "http://127.0.0.1:8000");
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash
    )
      throw Error();
    return url.toString().replace(/\/$/, "");
  } catch {
    throw Error("CONFIG");
  }
}
