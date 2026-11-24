import type { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DELETE, GET, HEAD, PATCH, POST, PUT, dynamic } from "../app/api/[...path]/route";

const BACKEND = "http://api.railway.internal:8000";

type RequestOptions = {
  method?: string;
  url?: string;
  headers?: Record<string, string>;
  body?: ArrayBuffer;
};

function makeRequest({ method = "GET", url = "http://localhost/api/me", headers = {}, body }: RequestOptions = {}) {
  return {
    method,
    nextUrl: new URL(url),
    headers: new Headers(headers),
    arrayBuffer: vi.fn(async () => body ?? new ArrayBuffer(0)),
  } as unknown as NextRequest;
}

function makeContext(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

function upstream(body: BodyInit | null = null, init: ResponseInit = {}) {
  return new Response(body, init);
}

describe("API proxy route", () => {
  let fetchMock: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.stubEnv("API_BACKEND_URL", BACKEND);
    fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      upstream(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("is a dynamic route handler", () => {
    expect(dynamic).toBe("force-dynamic");
  });

  it("returns 503 when the backend URL is not configured", async () => {
    vi.stubEnv("API_BACKEND_URL", "");

    const response = await GET(makeRequest(), makeContext(["me"]));

    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ detail: "API_BACKEND_URL is not configured" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("encodes every path segment and preserves the query string", async () => {
    const request = makeRequest({ url: "http://localhost/api/me?tab=history&page=2" });

    await GET(request, makeContext(["stellar", "account", "G ABC/123"]));

    expect(String(fetchMock.mock.calls[0][0])).toBe(
      `${BACKEND}/api/stellar/account/G%20ABC%2F123?tab=history&page=2`,
    );
  });

  it("forwards only accept, authorization and content-type request headers", async () => {
    const request = makeRequest({
      headers: {
        accept: "application/json",
        authorization: "Bearer token",
        "content-type": "application/json",
        cookie: "secret=1",
        "x-trace": "trace-123",
      },
    });

    await GET(request, makeContext(["me"]));

    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers as HeadersInit);
    expect(headers.get("accept")).toBe("application/json");
    expect(headers.get("authorization")).toBe("Bearer token");
    expect(headers.get("content-type")).toBe("application/json");
    expect(headers.has("cookie")).toBe(false);
    expect(headers.has("x-trace")).toBe(false);
  });

  it("omits headers that are not present on the incoming request", async () => {
    const response = await GET(makeRequest(), makeContext(["health"]));

    expect(response.status).toBe(200);
    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers as HeadersInit);
    expect([...headers.keys()]).toEqual([]);
  });

  it("does not send a body for GET and HEAD requests", async () => {
    await GET(makeRequest(), makeContext(["me"]));
    await HEAD(makeRequest({ method: "HEAD" }), makeContext(["me"]));

    for (const [, init] of fetchMock.mock.calls) {
      expect(init?.body).toBeUndefined();
      expect(init?.cache).toBe("no-store");
      expect(init?.redirect).toBe("manual");
    }
  });

  it("streams the request body for methods that can carry one", async () => {
    const payload = new TextEncoder().encode('{"title":"New"}').buffer;
    const request = makeRequest({ method: "POST", body: payload });

    await POST(request, makeContext(["projects"]));

    const [, init] = fetchMock.mock.calls[0];
    expect(init?.method).toBe("POST");
    expect(await new Response(init?.body as BodyInit).text()).toBe('{"title":"New"}');
    expect(request.arrayBuffer).toHaveBeenCalledOnce();
  });

  it("returns 502 when the backend request fails", async () => {
    fetchMock.mockRejectedValueOnce(new Error("network down"));

    const response = await GET(makeRequest(), makeContext(["me"]));

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ detail: "Backend API is unavailable" });
  });

  it("relays the upstream status, body and only safe response headers", async () => {
    fetchMock.mockResolvedValueOnce(
      upstream('{"id":"1"}', {
        status: 201,
        headers: {
          "content-type": "application/json",
          "cache-control": "no-store",
          "set-cookie": "session=secret",
        },
      }),
    );

    const response = await GET(makeRequest(), makeContext(["projects"]));

    expect(response.status).toBe(201);
    expect(await response.text()).toBe('{"id":"1"}');
    expect(response.headers.get("content-type")).toBe("application/json");
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.has("set-cookie")).toBe(false);
  });

  it.each([
    ["HEAD", 200],
    ["GET", 204],
    ["GET", 304],
  ])("returns no body for %s with upstream status %s", async (method, status) => {
    fetchMock.mockResolvedValueOnce(upstream(null, { status }));

    const response = await (method === "HEAD" ? HEAD : GET)(makeRequest({ method }), makeContext(["me"]));

    expect(response.status).toBe(status);
    expect(await response.text()).toBe("");
  });

  it.each([
    ["GET", GET],
    ["HEAD", HEAD],
    ["POST", POST],
    ["PUT", PUT],
    ["PATCH", PATCH],
    ["DELETE", DELETE],
  ])("exposes the %s handler", async (method, handler) => {
    await handler(makeRequest({ method }), makeContext(["me"]));

    expect(fetchMock.mock.calls[0][1]?.method).toBe(method);
  });
});
