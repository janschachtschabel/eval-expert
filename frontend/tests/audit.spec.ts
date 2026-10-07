import { test, expect } from "@playwright/test";
import { waitForApplication, signIn } from "./support";

let auditUsername: string;
test.beforeAll(async ({ request }) => {
  await waitForApplication(request);
  const password =
    process.env["EVAL_TEST_PASSWORD"] || "Test-password-for-browser!";
  const login = await request.post("/api/auth/login", {
    data: { username: "admin", password },
  });
  expect(login.ok()).toBe(true);
  const session = await login.json();
  auditUsername = "audit-" + Date.now();
  const account = await request.post("/api/users", {
    headers: { "X-CSRF-Token": session.csrf_token },
    data: { username: auditUsername, password, role: "admin" },
  });
  expect(account.ok()).toBe(true);
});

async function login(page: import("@playwright/test").Page) {
  await signIn(page, auditUsername);
}

test("delayed demo completion preserves the page selected in the meantime", async ({
  page,
}) => {
  await login(page);
  let release!: () => void;
  let started!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  const requested = new Promise<void>((resolve) => {
    started = resolve;
  });
  await page.route("**/api/demo", async (route) => {
    const response = await route.fetch();
    started();
    await pending;
    await route.fulfill({ response });
  });
  await page.getByRole("button", { name: "Demo einrichten" }).click();
  await requested;
  await page.getByRole("link", { name: "Zeitpläne", exact: true }).click();
  const response = page.waitForResponse("**/api/demo");
  release();
  await (await response).finished();
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  await expect(page).toHaveURL(/\/schedules$/);
  await expect(
    page.getByRole("heading", { name: "Zeitpläne", exact: true }),
  ).toBeVisible();
});

test("mobile navigation closes by button and Escape and restores focus", async ({
  page,
}) => {
  await login(page);
  await page.setViewportSize({ width: 375, height: 812 });
  const opener = page.getByRole("button", {
    name: "Navigation öffnen",
    exact: true,
  });
  await opener.click();
  const closer = page.getByRole("button", {
    name: "Navigation schließen",
    exact: true,
  });
  await expect(closer).toBeVisible();
  await closer.click();
  await expect(opener).toHaveAttribute("aria-expanded", "false");
  await expect(opener).toBeFocused();
  await opener.click();
  await page.keyboard.press("Escape");
  await expect(opener).toHaveAttribute("aria-expanded", "false");
  await expect(opener).toBeFocused();
});

test("case pages load full evidence on demand and history shows its total", async ({
  page,
}) => {
  await login(page);
  const session = await (await page.request.get("/api/auth/session")).json();
  const headers = { "X-CSRF-Token": session.csrf_token };
  const demo = await (await page.request.post("/api/demo", { headers })).json();
  const source = await (
    await page.request.get("/api/catalog/plans/" + demo.plan_id)
  ).json();
  const cases = Array.from({ length: 60 }, (_, index) => ({
    id: String(index + 1),
    input: { title: "Beleg " + (index + 1) },
    reference: { subject: ["label" + (index + 1)] },
  }));
  const datasetResponse = await page.request.post("/api/catalog/datasets", {
    headers,
    data: {
      name: "Browserpagination " + Date.now(),
      format: "json",
      content: JSON.stringify(cases),
    },
  });
  expect(datasetResponse.ok()).toBe(true);
  const dataset = await datasetResponse.json();
  delete source.id;
  delete source.version;
  const planResponse = await page.request.post("/api/catalog/plans", {
    headers,
    data: { ...source, name: "Pagination", dataset_id: dataset.id },
  });
  expect(planResponse.ok()).toBe(true);
  const plan = await planResponse.json();
  const response = await page.request.post("/api/runs", {
    headers,
    data: { plan_id: plan.id },
  });
  const run = await response.json();
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get("/api/runs/" + run.id + "/status")
          ).json()
        ).status,
      { timeout: 30000 },
    )
    .toBe("completed");
  await page.goto("/runs/" + run.id);
  const evidence = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Einzelergebnisse", exact: true }),
  });
  await expect(
    evidence.getByRole("button", { name: /Fall .* ansehen/ }),
  ).toHaveCount(25);
  await evidence
    .getByRole("button", { name: "Nächste Seite", exact: true })
    .click();
  await evidence
    .getByRole("button", { name: "Nächste Seite", exact: true })
    .click();
  await expect(
    evidence.getByRole("button", { name: /Fall .* ansehen/ }),
  ).toHaveCount(10);
  await evidence
    .getByRole("button", { name: "Fall 60 ansehen", exact: true })
    .click();
  await expect(
    page.getByRole("dialog").getByText("Beleg 60", { exact: false }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Schließen", exact: true }).click();
  const classes = page
    .locator("details.class-details")
    .filter({ has: page.locator("summary").filter({ hasText: "subject" }) });
  await classes.locator("summary").click();
  await expect(classes.getByRole("row")).toHaveCount(51);
  await classes
    .getByRole("button", { name: "Nächste Seite", exact: true })
    .click();
  await expect(classes.getByRole("row")).toHaveCount(11);
  await page.getByRole("link", { name: "Prüfläufe", exact: true }).click();
  const total = (await (await page.request.get("/api/runs/page")).json()).total;
  await expect(
    page.getByText("Insgesamt " + total, { exact: true }),
  ).toBeVisible();
});

test("stale editor keeps entered data and explicitly reloads the current version", async ({
  page,
}) => {
  await login(page);
  const session = await (await page.request.get("/api/auth/session")).json();
  const headers = { "X-CSRF-Token": session.csrf_token };
  const response = await page.request.post("/api/catalog/criteria", {
    headers,
    data: {
      name: "Konflikttest " + Date.now(),
      steps: ["Prüfe die Beschreibung."],
    },
  });
  expect(response.ok()).toBe(true);
  const criterion = await response.json();
  await page.getByRole("link", { name: "Kriterien", exact: true }).click();
  await page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name: criterion.name }) })
    .getByRole("button", { name: "Bearbeiten", exact: true })
    .click();
  await page
    .getByLabel("Name", { exact: true })
    .fill("Mein nicht gespeicherter Text");
  const concurrent = await page.request.put(
    "/api/catalog/criteria/" + criterion.id,
    {
      headers,
      data: { ...criterion, name: "Aktuell gespeicherte Fassung" },
    },
  );
  expect(concurrent.ok()).toBe(true);
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue(
    "Mein nicht gespeicherter Text",
  );
  await page
    .getByRole("button", { name: "Aktuelle Fassung laden", exact: true })
    .click();
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue(
    "Aktuell gespeicherte Fassung",
  );
});

test("late save success preserves a newer unsaved editor", async ({ page }) => {
  let release!: () => void;
  let started!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  const requested = new Promise<void>((resolve) => {
    started = resolve;
  });
  await page.route("**/api/catalog/criteria", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: [] });
      return;
    }
    started();
    await pending;
    await route.fulfill({
      json: { id: "saved", version: 1, name: "First draft" },
    });
  });
  await login(page);
  await page.getByRole("link", { name: "Kriterien", exact: true }).click();
  await page.getByRole("button", { name: "Neu anlegen", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("First draft");
  await page.getByLabel("Prüfschritte").fill("Prüfe den Beschreibungstext.");
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  await requested;
  await page.getByRole("button", { name: "Abbrechen", exact: true }).click();
  await page.getByRole("button", { name: "Neu anlegen", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("Second unsaved draft");
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/catalog/criteria") &&
      r.request().method() === "POST",
  );
  release();
  await (await response).finished();
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue(
    "Second unsaved draft",
  );
});

test("late reload cannot reopen an editor the user cancelled", async ({
  page,
}) => {
  const criterion = {
    id: "mock-criterion",
    version: 1,
    name: "Reload criterion",
    steps: ["Prüfe."],
  };
  let release!: () => void;
  let started!: () => void;
  let hold = false;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  const requested = new Promise<void>((resolve) => {
    started = resolve;
  });
  await page.route("**/api/catalog/criteria", (route) =>
    route.fulfill({ json: [criterion] }),
  );
  await page.route("**/api/catalog/criteria/mock-criterion", async (route) => {
    if (route.request().method() === "PUT") {
      await route.fulfill({ status: 409, json: { detail: "Version changed" } });
      return;
    }
    if (hold) {
      started();
      await pending;
    }
    await route.fulfill({ json: criterion });
  });
  await login(page);
  await page.getByRole("link", { name: "Kriterien", exact: true }).click();
  await page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name: criterion.name }) })
    .getByRole("button", { name: "Bearbeiten", exact: true })
    .click();
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  hold = true;
  await page
    .getByRole("button", { name: "Aktuelle Fassung laden", exact: true })
    .click();
  await requested;
  await page.getByRole("button", { name: "Abbrechen", exact: true }).click();
  const response = page.waitForResponse(
    "**/api/catalog/criteria/mock-criterion",
  );
  release();
  await (await response).finished();
  await expect(page.getByLabel("Name", { exact: true })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Neu anlegen", exact: true }),
  ).toBeVisible();
});

test("a delayed last case page refreshes after terminal status arrives", async ({
  page,
}) => {
  let release!: () => void;
  let started!: () => void;
  let terminal = false;
  let delayed = 0;
  let progress = 51;
  let releaseSecond!: () => void;
  let startedSecond!: () => void;
  const pendingSecond = new Promise<void>((resolve) => {
    releaseSecond = resolve;
  });
  const requestedSecond = new Promise<void>((resolve) => {
    startedSecond = resolve;
  });
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  const requested = new Promise<void>((resolve) => {
    started = resolve;
  });
  const rows = (offset: number, count: number) =>
    Array.from({ length: count }, (_, i) => ({
      case_id: String(offset + i + 1),
      ordinal: offset + i,
      status: "success",
      judge_count: 0,
    }));
  const summary = { reference: [], judge: {} };
  await page.route("**/api/runs/mock-pagination", (route) =>
    route.fulfill({
      json: {
        id: "mock-pagination",
        name: "Pending pagination",
        status: "running",
        progress: 51,
        total: 60,
        comparison_key: "mock-comparison",
        created: "2026-10-07T08:00:00Z",
        summary,
        snapshot: {
          plan: { name: "Pending pagination", fields: [], version: 1 },
          dataset: {},
          criteria: [],
        },
        results: rows(0, 25),
      },
    }),
  );
  await page.route("**/api/runs/mock-pagination/status", (route) =>
    route.fulfill({
      json: {
        status: terminal ? "completed" : "running",
        progress,
        summary,
      },
    }),
  );
  await page.route("**/api/runs/mock-pagination/cases?**", async (route) => {
    const offset = Number(
      new URL(route.request().url()).searchParams.get("offset"),
    );
    if (offset === 50 && delayed < 2) {
      delayed++;
      if (delayed === 1) {
        progress = 52;
        started();
        await pending;
      } else {
        terminal = true;
        progress = 60;
        startedSecond();
        await pendingSecond;
      }
      await route.fulfill({
        json: {
          items: rows(50, delayed),
          offset: 50,
          limit: 25,
          total: 50 + delayed,
        },
      });
      return;
    }
    await route.fulfill({
      json: {
        items: rows(offset, Math.min(25, 60 - offset)),
        offset,
        limit: 25,
        total: terminal ? 60 : 51,
      },
    });
  });
  await login(page);
  await page.goto("/runs/mock-pagination");
  const evidence = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Einzelergebnisse", exact: true }),
  });
  await evidence
    .getByRole("button", { name: "Nächste Seite", exact: true })
    .click();
  await evidence
    .getByRole("button", { name: "Nächste Seite", exact: true })
    .click();
  await requested;
  await expect(page.locator(".progress-panel")).toContainText("52/60");
  release();
  await requestedSecond;
  await expect(
    page.locator(".page-heading").getByText("Abgeschlossen", { exact: true }),
  ).toBeVisible();
  releaseSecond();
  await expect(
    evidence.getByRole("button", { name: /Fall .* ansehen/ }),
  ).toHaveCount(10);
  await expect(
    evidence.getByRole("button", { name: "Fall 60 ansehen", exact: true }),
  ).toBeVisible();
});
