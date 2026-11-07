import "server-only";
import { jsonReportPath, reportCsv } from "./csv";
const uuid = "[0-9a-fA-F-]{36}";
const resources = new RegExp(
  `^(links|campaigns|linkspaces|linkspaces/${uuid}|links/${uuid}|campaigns/${uuid}|links/${uuid}/destinations|management/overview|reporting/(status|links|campaigns)|analytics/(summary|trends|breakdowns|link-comparison|trends\\.csv|breakdowns\\.csv)|exports/clicks(?:\\.csv)?)$`,
);
export function allowedRoute(path: string, method: string) {
  if (!resources.test(path)) return false;
  if (method === "GET") return true;
  if (method === "POST")
    return (
      /^(links|campaigns|linkspaces)$/.test(path) ||
      new RegExp(`^links/${uuid}/destinations$`).test(path)
    );
  if (method === "PATCH")
    return new RegExp(`^(links|campaigns)/${uuid}$`).test(path);
  if (method === "PUT") return new RegExp(`^linkspaces/${uuid}$`).test(path);
  return (
    method === "DELETE" && new RegExp(`^(links|linkspaces)/${uuid}$`).test(path)
  );
}
export function statusCode(status: number) {
  return (
    (
      {
        401: "AUTH",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        410: "GONE",
        422: "VALIDATION",
        429: "RATE_LIMIT",
      } as Record<number, string>
    )[status] || "UNAVAILABLE"
  );
}
export async function backend(
  path: string,
  method: string,
  query: URLSearchParams,
  body?: string,
): Promise<{
  status: number;
  error?: string;
  data?: unknown;
  total?: string | null;
  csv?: ArrayBuffer;
  csvHeaders?: Record<string, string>;
}> {
  const key =
    path.startsWith("analytics/") ||
    path.startsWith("exports/") ||
    path.startsWith("reporting/")
      ? process.env.REPORT_API_KEY
      : process.env.ADMIN_API_KEY;
  if (!key || key.startsWith("replace-"))
    return { error: "CONFIG", status: 503 };
  let base: URL;
  try {
    base = new URL(process.env.TRACKER_API_URL || "http://127.0.0.1:8000");
  } catch {
    return { error: "CONFIG", status: 503 };
  }
  if (
    !["http:", "https:"].includes(base.protocol) ||
    base.username ||
    base.password ||
    base.search ||
    base.hash
  )
    return { error: "CONFIG", status: 503 };
  const url = new URL(
    `${base.pathname.replace(/\/$/, "")}/api/v1/${path}`,
    base,
  );
  url.search = query.toString();
  try {
    const response = await fetch(url, {
      method,
      body,
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
      },
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(10000),
    });
    // Older/running FastAPI instances can serve JSON reports but not the new CSV routes.
    // Retry only a missing CSV read, with the same reporting key, filters and page cursor.
    const compatiblePath = jsonReportPath(path);
    if (response.status === 404 && method === "GET" && compatiblePath) {
      const jsonUrl = new URL(url);
      jsonUrl.pathname = jsonUrl.pathname.slice(0, -4);
      const jsonResponse = await fetch(jsonUrl, {
        method: "GET",
        headers: { Authorization: `Bearer ${key}` },
        cache: "no-store",
        redirect: "error",
        signal: AbortSignal.timeout(10000),
      });
      if (!jsonResponse.ok)
        return {
          error:
            jsonResponse.status === 404
              ? "CSV_UNAVAILABLE"
              : statusCode(jsonResponse.status),
          status: jsonResponse.status === 404 ? 503 : jsonResponse.status,
        };
      return reportCsv(path, await jsonResponse.json());
    }
    if (!response.ok) {
      if (
        path === "linkspaces" ||
        path.startsWith("linkspaces/") ||
        path === "links"
      ) {
        const detail = await response.json().catch(() => null);
        if (
          response.status === 422 &&
          (path === "linkspaces" || path.startsWith("linkspaces/")) &&
          Array.isArray(detail?.detail)
        ) {
          const fields: Record<string, string> = {
            name: "LINKSPACE_NAME",
            base_url: "LINKSPACE_URL",
            path_prefix: "LINKSPACE_PREFIX",
          };
          const field = detail.detail.find(
            (item: { loc?: unknown[] }) =>
              Array.isArray(item?.loc) &&
              item.loc[0] === "body" &&
              typeof item.loc[1] === "string" &&
              Object.hasOwn(fields, item.loc[1]),
          )?.loc[1];
          if (field) return { error: fields[field], status: 422 };
        }
        const code = detail?.detail?.code;
        if (
          [
            "LINKSPACE_ROOT_UNSAFE",
            "LINKSPACE_RESERVED_SLUG",
            "LINKSPACE_UNAVAILABLE",
            "LINKSPACE_DUPLICATE",
            "LINKSPACE_DEFAULT_ACTIVE",
            "LINKSPACE_SELECT_DEFAULT",
            "LINKSPACE_IN_USE",
          ].includes(code)
        )
          return { error: code, status: response.status };
      }
      return {
        error:
          response.status === 409 && path.startsWith("campaigns")
            ? "DUPLICATE"
            : statusCode(response.status),
        status: response.status,
      };
    }
    if (path.endsWith(".csv"))
      return {
        csv: await response.arrayBuffer(),
        status: response.status,
        csvHeaders: {
          "Content-Type": "text/csv; charset=utf-8",
          "Content-Disposition": 'attachment; filename="report.csv"',
          "X-Export-Row-Count":
            response.headers.get("X-Export-Row-Count") || "0",
          "X-Partial-History":
            response.headers.get("X-Partial-History") || "false",
          ...(response.headers.get("X-Next-Cursor")
            ? { "X-Next-Cursor": response.headers.get("X-Next-Cursor")! }
            : {}),
          ...(response.headers.get("X-Next-Offset")
            ? { "X-Next-Offset": response.headers.get("X-Next-Offset")! }
            : {}),
        },
      };
    const data = response.status === 204 ? null : await response.json();
    return {
      data,
      total: response.headers.get("X-Total-Count"),
      status: response.status,
    };
  } catch {
    return { error: "UNAVAILABLE", status: 503 };
  }
}
