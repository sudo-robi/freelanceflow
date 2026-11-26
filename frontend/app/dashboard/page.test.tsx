import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "./page";

const api = vi.hoisted(() => ({ apiRequest: vi.fn() }));
vi.mock("@/lib/api", () => api);

afterEach(cleanup);

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const dashboard = {
      user: { id: "1", full_name: "Ada", role: "freelancer", email: "ada@example.com", stellar_address: null },
      projects: {
        total: 2,
        by_status: { active: 1, awaiting_agreement: 1 },
        recent: [
          { id: "p1", title: "Website", status: "active", budget: 100, asset: "XLM", deadline: null, updated_at: null },
        ],
      },
      payments: {
        verified_count: 1,
        verified_amount: 100,
        asset: "XLM",
        recent: [
          { id: "pay1", transaction_hash: "a".repeat(64), amount: 100, status: "confirmed", confirmed_at: "2026-11-24T00:00:00" },
        ],
      },
      pending_reviews: 0,
      open_disputes: 1,
      unread_notifications: 2,
      activity: [{ action: "confirmed", entity_type: "payment", entity_id: "pay1", details: "hash", created_at: "2026-11-24T00:00:00" }],
      generated_at: "2026-11-24T00:00:00",
    };
    const report = { by_month: { "2026-11": 100 }, verified_payments: 1, total_amount: 100 };
    api.apiRequest.mockImplementation((path: string) =>
      path === "/api/dashboard" ? Promise.resolve(dashboard) : Promise.resolve(report),
    );
  });

  it("renders verified earnings instead of hardcoded placeholders", async () => {
    render(<DashboardPage />);

    await waitFor(() => expect(screen.getByText("Verified earnings")).toBeDefined());
    expect(api.apiRequest).toHaveBeenCalledWith("/api/dashboard");
    expect(screen.getAllByText("100 XLM").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1").length).toBeGreaterThan(0);
    expect(screen.getByText("Website")).toBeDefined();
    expect(screen.getByText("a".repeat(64))).toBeDefined();
  });

  it("shows API errors without inventing dashboard data", async () => {
    api.apiRequest.mockRejectedValue(new Error("Session expired"));
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("Session expired"));
    expect(screen.queryByText("Verified earnings")).toBeNull();
  });
});
