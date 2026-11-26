import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

interface Session { token: string; role: string }

async function register(request: APIRequestContext, role: "client" | "freelancer", name: string): Promise<Session> {
  const response = await request.post("/api/auth/register", {
    data: {
      email: `${name}@${role}.example.com`,
      password: "secure-pass-123",
      full_name: name,
      role,
    },
  });
  expect(response.status()).toBe(200);
  return response.json() as Promise<Session>;
}

function headers(session: Session) {
  return { Authorization: `Bearer ${session.token}` };
}

async function authenticate(page: Page, session: Session) {
  await page.addInitScript((token) => {
    sessionStorage.setItem("freelanceflow_session", token);
  }, session.token);
}

test("a client creates a real project and sees it in the dashboard", async ({ page, request }) => {
  const client = await register(request, "client", "e2e-client");
  await authenticate(page, client);

  await page.goto("/projects");
  await page.getByLabel("Project title").fill("E2E website project");
  await page.getByLabel("Description").fill("A complete project description for testing.");
  await page.getByLabel("Budget (XLM)").fill("120");
  await page.getByRole("button", { name: "Create project" }).click();

  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+/);
  await expect(page.getByRole("heading", { name: "E2E website project" })).toBeVisible();

  await page.goto("/dashboard");
  await expect(page.getByText("E2E website project")).toBeVisible();
  await expect(page.getByText("Verified earnings")).not.toBeVisible();
});

test("freelancer directory shows real profile data and portfolio", async ({ page, request }) => {
  const freelancer = await register(request, "freelancer", "e2e-freelancer");
  const me = await request.get("/api/me", { headers: headers(freelancer) });
  const { id } = await me.json() as { id: string };
  expect((await request.put("/api/me", {
    headers: headers(freelancer),
    data: { title: "Accessibility specialist", skills: "React, WCAG", description: "Inclusive interfaces." },
  })).status()).toBe(200);
  expect((await request.post("/api/me/portfolio", {
    headers: headers(freelancer),
    data: { title: "Public case study", url: "https://example.com/case-study", description: "Real portfolio entry" },
  })).status()).toBe(201);

  const client = await register(request, "client", "e2e-observer");
  await authenticate(page, client);
  await page.goto("/directory?skill=WCAG");
  await expect(page.getByRole("link", { name: "e2e-freelancer" })).toBeVisible();

  await page.getByRole("link", { name: "e2e-freelancer" }).click();
  await expect(page.getByText("React, WCAG")).toBeVisible();
  await expect(page.getByText("Public case study")).toBeVisible();
  await expect(page.getByText(id.slice(0, 8))).toHaveCount(0);
});

test("all workspace routes render without console errors or horizontal overflow", async ({ page, request }) => {
  const observer = await register(request, "client", "e2e-route-observer");
  await authenticate(page, observer);
  const consoleErrors: string[] = [];
  const failedResponses: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("404")) consoleErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.status() >= 400) failedResponses.push(`${response.status()} ${response.url()}`);
  });

  for (const path of [
    "/dashboard", "/projects", "/directory", "/wallet",
    "/payments", "/disputes", "/notifications", "/profile",
  ]) {
    await page.goto(path);
    await expect(page.locator("main")).toBeVisible();
    const overflow = await page.evaluate(() =>
      document.documentElement.scrollWidth > window.innerWidth + 1,
    );
    expect(overflow, `${path} overflows horizontally`).toBe(false);
  }
  // The browser's automatic /favicon.ico request is cosmetic and has no product impact.
  expect(failedResponses.filter((entry) => !entry.includes("/favicon.ico"))).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test("opening a dispute through the UI freezes the workflow", async ({ page, request }) => {
  const client = await register(request, "client", "e2e-dispute-client");
  const freelancer = await register(request, "freelancer", "e2e-dispute-free");
  const freelancerId = ((await (await request.get("/api/me", { headers: headers(freelancer) })).json()) as { id: string }).id;

  const project = await (await request.post("/api/projects", {
    headers: headers(client),
    data: { title: "Dispute project", description: "A project used for an end-to-end dispute test.", budget: 50 },
  })).json() as { id: string };
  const invitation = await (await request.post(`/api/projects/${project.id}/invitations`, {
    headers: headers(client),
    data: { freelancer_id: freelancerId },
  })).json() as { id: string };
  await request.post(`/api/invitations/${invitation.id}/accept`, { headers: headers(freelancer) });
  await request.post(`/api/projects/${project.id}/agreements`, {
    headers: headers(client),
    data: {
      freelancer_id: freelancerId,
      amount: 50,
      asset: "XLM",
      description: "Build and deliver the agreed milestone.",
      milestones: [{ title: "Delivery", amount: 50 }],
    },
  });

  await authenticate(page, client);
  await page.goto(`/projects/${project.id}`);
  await page.getByLabel("Reason for dispute").fill("The delivered work does not match the agreed scope.");
  await page.getByRole("button", { name: "Open dispute" }).click();

  await expect(page.getByText("An open dispute blocks approvals and payments.")).toBeVisible();
  await expect(page.getByText("open", { exact: true })).toBeVisible();
});
