import { NextResponse } from "next/server";
import { authenticated, sameOrigin } from "@/lib/auth";
import { allowedRoute, backend } from "@/lib/backend";
export const runtime = "nodejs";
type Context = { params: Promise<{ path: string[] }> };
async function handle(request: Request, context: Context) {
  if (!(await authenticated()))
    return NextResponse.json({ code: "AUTH" }, { status: 401 });
  if (request.method !== "GET" && !sameOrigin(request))
    return NextResponse.json({ code: "FORBIDDEN" }, { status: 403 });
  const path = (await context.params).path.join("/");
  if (!allowedRoute(path, request.method))
    return NextResponse.json({ code: "NOT_FOUND" }, { status: 404 });
  const query = new URL(request.url).searchParams;
  if (query.toString().length > 8192)
    return NextResponse.json({ code: "VALIDATION" }, { status: 422 });
  const body =
    request.method === "POST" || request.method === "PATCH"
      ? await request.text()
      : undefined;
  if (body && Buffer.byteLength(body) > 16384)
    return NextResponse.json({ code: "VALIDATION" }, { status: 422 });
  const result = await backend(path, request.method, query, body);
  const headers = { "Cache-Control": "no-store" };
  if (result.error)
    return NextResponse.json(
      { code: result.error },
      { status: result.status, headers },
    );
  if (result.status === 204)
    return new NextResponse(null, { status: 204, headers });
  if (result.csv)
    return new NextResponse(result.csv, {
      status: result.status,
      headers: { ...headers, ...result.csvHeaders },
    });
  return NextResponse.json(
    result.total !== null
      ? { items: result.data, total: Number(result.total) }
      : result.data,
    { status: result.status, headers },
  );
}
export { handle as GET, handle as POST, handle as PATCH, handle as DELETE };
