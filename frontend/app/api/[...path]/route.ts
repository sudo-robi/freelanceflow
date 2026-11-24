import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, { params }: RouteContext): Promise<Response> {
  const backendUrl = process.env.API_BACKEND_URL;
  if (!backendUrl) {
    return Response.json({ detail: "API_BACKEND_URL is not configured" }, { status: 503 });
  }

  const { path } = await params;
  const target = new URL(
    `/api/${path.map((part) => encodeURIComponent(part)).join("/")}${request.nextUrl.search}`,
    backendUrl,
  );
  const headers = new Headers();
  for (const name of ["accept", "authorization", "content-type"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return Response.json({ detail: "Backend API is unavailable" }, { status: 502 });
  }

  const responseHeaders = new Headers();
  for (const name of ["content-type", "cache-control"]) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new Response(
    ["HEAD", "204", "304"].includes(request.method) || upstream.status === 204 || upstream.status === 304
      ? null
      : upstream.body,
    { status: upstream.status, headers: responseHeaders },
  );
}

export const GET = proxy;
export const HEAD = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
