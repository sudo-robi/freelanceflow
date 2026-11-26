import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup } from "@testing-library/react";
import AppShell from "./AppShell";

afterEach(cleanup);

describe("AppShell", () => {
  it("renders the workspace navigation and page content", () => {
    render(<AppShell title="Projects" subtitle="Testnet"><h1>Project list</h1></AppShell>);

    expect(screen.getByRole("heading", { name: "Project list" })).toBeDefined();
    expect(screen.getAllByRole("link", { name: "Projects" }).length).toBeGreaterThan(0);
    for (const label of ["Overview", "Projects", "Discover", "Payments", "Disputes", "Wallet", "Notifications", "Profile"]) {
      expect(screen.getAllByRole("link", { name: label }).length).toBeGreaterThan(0);
    }
  });
});
