import { expect, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const suffix = " " + Date.now();
export const names = {
  service: "Functional URL service" + suffix,
  dataset: "Functional five URLs" + suffix,
  criterion: "Functional Werbefreiheit" + suffix,
  provider: "Functional OpenAI" + suffix,
  plan: "Functional Volltext" + suffix,
  schedule: "Functional weekly schedule" + suffix,
};
export const cases = Array.from({ length: 5 }, (_, i) => ({
  id: "url-" + i,
  input: { url: "https://example.org/" + (i === 4 ? "failure" : "page-" + i) },
  reference: { subject: ["math"] },
}));
export const card = (page: Page, name: string) =>
  page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name, exact: true }) });
export async function choose(
  page: Page,
  label: string,
  option: string,
  multiple = false,
) {
  await page.getByRole("combobox", { name: label, exact: true }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
  if (multiple) await page.keyboard.press("Escape");
  await expect(page.getByRole("listbox")).toHaveCount(0);
}
export async function view(page: Page, title: string) {
  await page
    .locator("aside")
    .getByRole("link", { name: title, exact: true })
    .click();
  await expect(page.getByText("Wird geladen …", { exact: true })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
}
export async function create(page: Page, title: string, name: string) {
  await view(page, title);
  await page.getByRole("button", { name: "Neu anlegen", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill(name);
}
export async function save(page: Page, name: string) {
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(card(page, name)).toBeVisible();
  await expect(page.locator(".editor")).toHaveCount(0);
}
export async function inspectLayout(page: Page) {
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.setViewportSize({ width: 320, height: 812 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 375, height: 812 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1000 });
}
export async function completed(page: Page, previousId = "") {
  if (previousId)
    await expect(page).not.toHaveURL(new RegExp("/runs/" + previousId + "$"));
  await expect(page).toHaveURL(/\/runs\/[^/]+$/);
  await expect(page.locator(".page-heading .badge").first()).toHaveText(
    "Abgeschlossen",
    { timeout: 45000 },
  );
  await expect(page.locator(".progress-panel")).toHaveCount(0);
  const id = page.url().split("/").at(-1);
  return (await page.request.get("/api/runs/" + id)).json();
}
export async function start(page: Page) {
  await view(page, "Prüfprofile");
  await card(page, names.plan)
    .getByRole("button", { name: "Prüfung starten", exact: true })
    .click();
  return completed(page);
}
export async function providers(page: Page) {
  await create(page, "LLM-Anbindung", names.provider);
  for (const type of ["b-api · OpenAI", "b-api · AcademicCloud", "OpenAI"]) {
    await choose(page, "Anbindung", type);
    await expect(page.getByLabel("Basis-URL", { exact: true })).toHaveValue(
      type === "OpenAI"
        ? "https://api.openai.com/v1"
        : "https://b-api.prod.openeduhub.net",
    );
  }
  await page
    .getByLabel("Modell-ID", { exact: true })
    .fill("browser-judge-model");
  await page
    .getByLabel("API-Schlüssel / Zugangsdaten", { exact: true })
    .fill("disposable-browser-key");
  await save(page, names.provider);
  await card(page, names.provider)
    .getByRole("button", { name: "Verfügbare Modelle abrufen" })
    .click();
  await expect(page.locator(".evidence-panel")).toContainText(
    "browser-judge-model",
  );
  await page
    .locator(".evidence-panel")
    .getByRole("button", { name: "Schließen" })
    .click();
  await card(page, names.provider)
    .getByRole("button", { name: "Bearbeiten", exact: true })
    .click();
  await expect(
    page.getByLabel("API-Schlüssel / Zugangsdaten", { exact: true }),
  ).toBeEmpty();
  await save(page, names.provider);
  await expect(card(page, names.provider)).toContainText(
    "Zugangsdaten hinterlegt",
  );
  await inspectLayout(page);
}
