import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup } from "@testing-library/react";
import AppShell from "./AppShell";

afterEach(cleanup);

describe("AppShell", () => {
  it("renders the workspace navigation and page content", () => {
    render(<AppShell title="Projects" subtitle="Testnet"><h1>Project list</h1></AppShell>);

    expect(screen.getByRole("heading", { name: "Project list" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Projects" })).toBeDefined();
    for (const label of ["Overview", "Projects", "Freelancers", "Payments", "Disputes", "Stellar wallet", "Notifications", "Profile"]) {
      expect(screen.getByRole("link", { name: label })).toBeDefined();
    }
  });
});
