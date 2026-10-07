import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { signIn, waitForApplication } from "./support";

test.beforeAll(async ({ request }) => {
  await waitForApplication(request);
});

test("a judge profile renders dataset summaries and saves its selected configuration", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      !message.location().url.endsWith("/api/auth/session")
    )
      errors.push(message.text());
  });
  await signIn(page);
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
    name: "Profile URL extractor",
    url: "https://example.org/from-url",
    mapping: { url: { $input: "/url" } },
  });
  const dataset = await create("datasets", {
    name: "Profile URL cases",
    format: "json",
    content: JSON.stringify(
      Array.from({ length: 5 }, (_, i) => ({
        id: "url-" + i,
        input: { url: "https://example.org/page-" + i },
        reference: {},
      })),
    ),
  });
  const criterion = await create("criteria", {
    name: "Profile advertising criterion",
    steps: ["Prüfe Werbefreiheit."],
    output_path: "/text",
  });
  const provider = await create("providers", {
    name: "Profile judge connection",
    model: "fixture-model",
  });
  const summaries = await (
    await page.request.get("/api/catalog/datasets")
  ).json();
  const summary = summaries.find(
    (item: { id: string }) => item.id === dataset.id,
  );
  expect(summary.case_count).toBe(5);
  expect(summary.cases).toBeUndefined();

  await page.getByRole("link", { name: "Prüfprofile", exact: true }).click();
  await expect(page.locator("main [role='status']")).toHaveCount(0);
  await page.getByRole("button", { name: "Neu anlegen", exact: true }).click();
  await expect(
    page.getByLabel("Name", { exact: true }),
    errors.join("\n"),
  ).toBeVisible();
  const name = "Browser advertising profile";
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByLabel("Dienst", { exact: true }).click();
  await page.getByRole("option", { name: service.name, exact: true }).click();
  await page.getByLabel("Datensatz", { exact: true }).click();
  await page
    .getByRole("option", { name: dataset.name + " · 5 Fälle", exact: true })
    .click();
  await page.getByLabel("Messverfahren", { exact: true }).click();
  await page
    .getByRole("option", { name: "LLM-Bewertung", exact: true })
    .click();
  await page.getByLabel("LLM-Anbindung", { exact: true }).click();
  await page.getByRole("option", { name: provider.name, exact: true }).click();
  await page.getByLabel("Bewertungskriterien", { exact: true }).click();
  await page.getByRole("option", { name: criterion.name, exact: true }).click();
  await page.keyboard.press("Escape");
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  const card = page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name, exact: true }) });
  await expect(card).toContainText("5 Fälle");
  await card.getByRole("button", { name: "Bearbeiten", exact: true }).click();
  await expect(page.getByLabel("Dienst", { exact: true })).toContainText(
    service.name,
  );
  await expect(page.getByLabel("Datensatz", { exact: true })).toContainText(
    dataset.name + " · 5 Fälle",
  );
  await expect(page.getByLabel("Messverfahren", { exact: true })).toContainText(
    "LLM-Bewertung",
  );
  await expect(page.getByLabel("LLM-Anbindung", { exact: true })).toContainText(
    provider.name,
  );
  await expect(
    page.getByLabel("Bewertungskriterien", { exact: true }),
  ).toContainText(criterion.name);
  expect(errors).toEqual([]);
});
