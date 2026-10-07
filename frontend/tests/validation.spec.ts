import { test, expect } from "@playwright/test";
import { signIn, waitForApplication } from "./support";

let username: string;
test.beforeAll(async ({ request }) => {
  await waitForApplication(request);
  const password =
    process.env["EVAL_TEST_PASSWORD"] || "Test-password-for-browser!";
  const session = await (
    await request.post("/api/auth/login", {
      data: { username: "admin", password },
    })
  ).json();
  username = "validation-" + Date.now();
  const response = await request.post("/api/users", {
    headers: { "X-CSRF-Token": session.csrf_token },
    data: { username, password, role: "admin" },
  });
  expect(response.ok()).toBe(true);
});

test("catalog, team and login forms reject incomplete submissions before HTTP and keep inputs", async ({
  page,
}) => {
  await signIn(page, username);
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      /\/api\/(catalog|users|auth\/login)/.test(request.url())
    )
      mutations.push(request.url());
  });
  for (const title of [
    "Dienste",
    "Testdaten",
    "Kriterien",
    "LLM-Anbindung",
    "Prüfprofile",
    "Zeitpläne",
  ]) {
    await test.step(title, async () => {
      await page.getByRole("link", { name: title, exact: true }).click();
      await expect(page.locator("main [role='status']")).toHaveCount(0);
      await page
        .getByRole("button", { name: "Neu anlegen", exact: true })
        .click();
      await page.getByLabel("Name", { exact: true }).fill("Eingaben erhalten");
      await page
        .getByRole("button", { name: "Speichern", exact: true })
        .click();
      await expect(page.locator("mat-error").first()).toContainText(
        "Pflichtfeld",
      );
      await expect(page.getByLabel("Name", { exact: true })).toHaveValue(
        "Eingaben erhalten",
      );
    });
  }
  await page.getByRole("link", { name: "Team", exact: true }).click();
  await page.getByLabel("Benutzername", { exact: true }).fill("new-person");
  await page.getByLabel("Passwort", { exact: true }).fill("short");
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(page.locator("mat-error").first()).toContainText("12");
  await page.getByRole("button", { name: "Abmelden", exact: true }).click();
  await page.getByRole("button", { name: "Anmelden", exact: true }).click();
  await expect(page.locator("mat-error").first()).toContainText("Pflichtfeld");
  expect(mutations).toEqual([]);
});

test("a judge profile requires a provider in the editor and a missing run offers recovery", async ({
  page,
}) => {
  await signIn(page, username);
  const session = await (await page.request.get("/api/auth/session")).json();
  const headers = { "X-CSRF-Token": session.csrf_token };
  const create = async (kind: string, data: unknown) => {
    const response = await page.request.post("/api/catalog/" + kind, {
      headers,
      data,
    });
    expect(response.ok()).toBe(true);
    return response.json();
  };
  const service = await create("services", {
    name: "Missing-provider service",
    kind: "demo",
  });
  const dataset = await create("datasets", {
    name: "Missing-provider cases",
    cases: [
      { id: "url", input: { url: "https://example.org/" }, reference: {} },
    ],
  });
  const criterion = await create("criteria", {
    name: "Missing-provider criterion",
    steps: ["Check advertising."],
  });
  await page.getByRole("link", { name: "Prüfprofile", exact: true }).click();
  await expect(page.locator("main [role='status']")).toHaveCount(0);
  await page.getByRole("button", { name: "Neu anlegen", exact: true }).click();
  await page
    .getByLabel("Name", { exact: true })
    .fill("Incomplete judge profile");
  for (const [label, option] of [
    ["Dienst", service.name],
    ["Datensatz", dataset.name + " · 1 Fälle"],
    ["Messverfahren", "LLM-Bewertung"],
    ["Bewertungskriterien", criterion.name],
  ]) {
    await page.getByLabel(label, { exact: true }).click();
    await page.getByRole("option", { name: option, exact: true }).click();
    if (label === "Bewertungskriterien") await page.keyboard.press("Escape");
  }
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(page.locator("mat-error")).toContainText("Pflichtfeld");
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue(
    "Incomplete judge profile",
  );
  await page.route("**/api/catalog/plans", async (route) => {
    const response = await route.fetch();
    const items = await response.json();
    await route.fulfill({
      response,
      json: [
        ...items,
        {
          id: "legacy-incomplete",
          version: 1,
          name: "Legacy incomplete profile",
          mode: "judge",
          service_id: service.id,
          dataset_id: dataset.id,
          provider_id: null,
          criterion_ids: [criterion.id],
          field_count: 0,
        },
      ],
    });
  });
  await page.goto("/plans");
  const legacy = page.getByRole("article").filter({
    has: page.getByRole("heading", {
      name: "Legacy incomplete profile",
      exact: true,
    }),
  });
  await expect(legacy).toContainText("Wähle eine LLM-Anbindung im Prüfprofil");
  await expect(
    legacy.getByRole("button", { name: "Prüfung starten", exact: true }),
  ).toBeDisabled();
  await page.goto("/runs/nonexistent");
  await expect(
    page.getByRole("button", { name: "Erneut laden", exact: true }),
  ).toBeVisible();
  await expect(page.locator("main [role='status']")).toHaveCount(0);
  await expect(page.locator("main")).toContainText(
    "Prüflauf wurde nicht gefunden",
  );
});
