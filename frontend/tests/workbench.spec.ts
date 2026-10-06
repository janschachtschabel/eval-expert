import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.beforeAll(async ({ request }) => {
  await expect
    .poll(
      async () => {
        try {
          return (await request.get("/api/health")).status();
        } catch {
          return 0;
        }
      },
      { timeout: 30000 },
    )
    .toBe(200);
});

test("schedule presets preview future dates and retain the configuration", async ({
  page,
}) => {
  const name = "Browserzeitplan " + Date.now();
  await page.goto("/");
  await page.getByLabel("Benutzername").fill("admin");
  await page
    .getByLabel("Passwort", { exact: true })
    .fill(process.env["EVAL_TEST_PASSWORD"] || "Test-password-for-browser!");
  await page.getByRole("button", { name: "Anmelden", exact: true }).click();
  await page.getByRole("button", { name: "Demo einrichten" }).click();
  await page.getByRole("link", { name: "Zeitpläne", exact: true }).click();
  await page.getByRole("button", { name: "Neu anlegen" }).click();
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByLabel("Prüfprofile", { exact: true }).click();
  await page
    .getByRole("option", { name: "Demo · Metadaten prüfen", exact: true })
    .click();
  await page.getByLabel("Häufigkeit", { exact: true }).click();
  await page
    .getByRole("option", { name: "Täglich um 08:00 Uhr", exact: true })
    .click();
  await expect(page.getByLabel("Cron-Zeitplan")).toHaveValue("0 8 * * *");
  await page
    .getByRole("button", { name: "Nächste Termine", exact: true })
    .click();
  await expect(page.locator(".editor li")).toHaveCount(5);
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  const card = page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name, exact: true }) });
  await expect(
    card.getByText("Nächste Ausführung:", { exact: false }),
  ).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await card.getByRole("button", { name: "Entfernen", exact: true }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toHaveCount(0);
});

test("local login, reference run, evidence, export and responsive navigation", async ({
  page,
}) => {
  const errors: string[] = [];
  const externalAssets: string[] = [];
  page.on("request", (request) => {
    if (
      ["font", "stylesheet", "script", "image"].includes(
        request.resourceType(),
      ) &&
      new URL(request.url()).origin !==
        new URL(process.env["EVAL_TEST_URL"] || "http://127.0.0.1:8117").origin
    )
      externalAssets.push(request.url());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      !message.location().url.endsWith("/api/auth/session")
    )
      errors.push(message.text());
  });
  await page.goto("/");
  await page.getByLabel("Benutzername").fill("admin");
  await page
    .getByLabel("Passwort", { exact: true })
    .fill(process.env["EVAL_TEST_PASSWORD"] || "Test-password-for-browser!");
  await page.getByRole("button", { name: "Anmelden", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Überblick", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Demo einrichten" }).click();
  await expect(
    page.getByRole("heading", { name: "Prüfprofile", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Prüfung starten", exact: true })
    .first()
    .click();
  await expect(
    page.getByText("Abgeschlossen", { exact: true }).first(),
  ).toBeVisible({ timeout: 30000 });
  await expect(
    page.getByRole("heading", { name: "Referenzvergleich" }),
  ).toBeVisible();
  await expect(
    page.getByText("subject", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Fall 1 ansehen", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Einzelfall 1" }),
  ).toBeVisible();
  await expect(
    page.getByText("Brüche verstehen", { exact: false }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Schließen", exact: true }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "CSV exportieren" }).click();
  expect((await download).suggestedFilename()).toMatch(/eval-.*\.csv/);
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.evaluate(() => window.scrollTo(0, 0));
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../artifacts/mobile-run.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 320, height: 812 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "../artifacts/desktop-run.png",
    fullPage: false,
  });
  expect(errors).toEqual([]);
  expect(externalAssets).toEqual([]);
});

test("criteria and dataset can be created with ordinary forms", async ({
  page,
}) => {
  const suffix = Date.now();
  await page.goto("/");
  await page.getByLabel("Benutzername").fill("admin");
  await page
    .getByLabel("Passwort", { exact: true })
    .fill(process.env["EVAL_TEST_PASSWORD"] || "Test-password-for-browser!");
  await page.getByRole("button", { name: "Anmelden", exact: true }).click();
  await page.getByRole("link", { name: "Kriterien", exact: true }).click();
  await page.getByRole("button", { name: "Neu anlegen" }).click();
  await page
    .getByLabel("Name", { exact: true })
    .fill("Browserprüfung Beschreibung " + suffix);
  await page
    .getByLabel("Prüfschritte")
    .fill("Prüfe, ob die Beschreibung sachlich und verständlich ist.");
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Browserprüfung Beschreibung " + suffix,
    }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Testdaten", exact: true }).click();
  await page.getByRole("button", { name: "Neu anlegen" }).click();
  await page
    .getByLabel("Name", { exact: true })
    .fill("Browserprüfung Daten " + suffix);
  await page
    .getByLabel("Datensatz")
    .fill(
      '{"id":"one","input":{"title":"Text"},"reference":{"subject":["german"]}}',
    );
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Browserprüfung Daten " + suffix }),
  ).toBeVisible();
});
