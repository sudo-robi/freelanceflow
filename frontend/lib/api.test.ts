import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest, clearToken, getToken, setToken } from "./api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiRequest", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("adds a bearer token to authenticated requests", async () => {
    setToken("test-token");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ ok: true }));

    await apiRequest("/api/me");

    const [, init] = fetchMock.mock.calls[0];
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer test-token");
  });

  it("does not send credentials after logout", async () => {
    setToken("test-token");
    clearToken();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ ok: true }));

    await apiRequest("/api/health");

    const [, init] = fetchMock.mock.calls[0];
    expect(new Headers(init?.headers).get("Authorization")).toBeNull();
  });

  it("keeps tokens in session storage only", () => {
    expect(getToken()).toBeNull();
    setToken("session-token");
    expect(getToken()).toBe("session-token");
    clearToken();
    expect(getToken()).toBeNull();
  });

  it("sends JSON content type and merges caller headers", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ ok: true }));

    await apiRequest("/api/projects", {
      method: "POST",
      body: '{"title":"Test"}',
      headers: { "X-Request-Id": "abc" },
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/projects");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe('{"title":"Test"}');
    const headers = new Headers(init?.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("X-Request-Id")).toBe("abc");
  });

  it("returns the parsed response body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ id: "123", title: "Project" }));

    await expect(apiRequest<{ id: string }>("/api/projects/123")).resolves.toEqual({
      id: "123",
      title: "Project",
    });
  });

  it("throws the API detail message for failed requests", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ detail: "Invalid credentials" }, 401));

    await expect(apiRequest("/api/login")).rejects.toThrow("Invalid credentials");
  });

  it("falls back to a generic message when the error body has no detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ message: "nope" }, 400));

    await expect(apiRequest("/api/login")).rejects.toThrow("Request failed");
  });

  it("falls back to a generic message for a non-JSON error body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("<html>bad gateway</html>", { status: 502 }),
    );

    await expect(apiRequest("/api/health")).rejects.toThrow("Request failed");
  });
});

describe("API_URL", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("uses the same origin outside development", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");

    const { API_URL } = await import("./api");

    expect(API_URL).toBe("");
  });

  it("targets the local API in development by default", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");

    const { API_URL } = await import("./api");

    expect(API_URL).toBe("http://localhost:8000");
  });

  it("prefers an explicit public API URL", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.com");

    const { API_URL } = await import("./api");

    expect(API_URL).toBe("https://api.example.com");
  });

  it("prefixes requests with a configured API URL", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.com");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ ok: true }));

    const { apiRequest } = await import("./api");
    await apiRequest("/api/health");

    expect(fetchMock.mock.calls[0][0]).toBe("https://api.example.com/api/health");
  });
});
