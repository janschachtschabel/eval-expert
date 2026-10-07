import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { waitForApplication, signIn as login } from "./support";

test.beforeAll(async ({ request }) => {
  await waitForApplication(request);
});

test("service mappings survive saving, reopening and page reload", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("link", { name: "Dienste", exact: true }).click();
  await page.getByRole("button", { name: "Neu anlegen", exact: true }).click();
  const name = "URL mapping " + Date.now();
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page
    .getByLabel("Endpoint-URL", { exact: true })
    .fill("https://example.org/from-url");
  const initial = {
    url: { $input: "/source/url" },
    method: "simple",
    lang: "auto",
  };
  const updated = {
    ...initial,
    lang: "de",
    output_format: "txt",
    browser_location: null,
  };
  const mapping = page.getByLabel("Eingabezuordnung (JSON)", { exact: true });
  const card = page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name, exact: true }) });
  await mapping.fill(JSON.stringify(initial));
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  await card.getByRole("button", { name: "Bearbeiten", exact: true }).click();
  expect(JSON.parse(await mapping.inputValue())).toEqual(initial);
  await mapping.fill(JSON.stringify(updated));
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  await page.reload();
  await card.getByRole("button", { name: "Bearbeiten", exact: true }).click();
  expect(JSON.parse(await mapping.inputValue())).toEqual(updated);
});

test("service previews derive independent inputs from saved mappings", async ({
  page,
}) => {
  await login(page);
  const session = await (await page.request.get("/api/auth/session")).json();
  const headers = { "X-CSRF-Token": session.csrf_token };
  const services = [
    {
      name: "URL preview",
      mapping: { url: { $input: "/url" }, lang: "auto" },
      input: { url: "" },
    },
    {
      name: "Metadata preview",
      mapping: { text: { $input: "/metadata/description" } },
      input: { metadata: { description: "" } },
    },
  ];
  for (const service of services) {
    const response = await page.request.post("/api/catalog/services", {
      headers,
      data: {
        name: service.name,
        url: "https://example.org/from-url",
        mapping: service.mapping,
      },
    });
    expect(response.ok()).toBe(true);
  }
  let attempts = 0;
  await page.route("**/api/connections/preview", (route) =>
    ++attempts === 1
      ? route.fulfill({
          status: 422,
          json: { detail: "Temporary target failure" },
        })
      : route.fulfill({ json: { output: { text: "Extracted text" } } }),
  );
  await page.getByRole("link", { name: "Dienste", exact: true }).click();
  const cards = services.map((service) =>
    page.getByRole("article").filter({
      has: page.getByRole("heading", { name: service.name, exact: true }),
    }),
  );
  for (const [index, card] of cards.entries()) {
    await card.locator("summary").click();
    await expect(
      card.getByLabel("Testeingabe (JSON)", { exact: true }),
    ).toHaveValue(JSON.stringify(services[index].input, null, 2));
  }
  const input = cards[0].getByLabel("Testeingabe (JSON)", { exact: true });
  const value = { url: "https://www.wirlernenonline.de" };
  await input.fill(JSON.stringify(value));
  await cards[0].locator("summary").click();
  await cards[0].locator("summary").click();
  await expect(input).toHaveValue(JSON.stringify(value));
  await expect(
    cards[1].getByLabel("Testeingabe (JSON)", { exact: true }),
  ).toHaveValue(JSON.stringify(services[1].input, null, 2));
  const request = page.waitForRequest("**/api/connections/preview");
  await cards[0]
    .getByRole("button", { name: "Antwort testen", exact: true })
    .click();
  expect((await request).postDataJSON().input).toEqual(value);
  await expect(cards[0].getByRole("alert")).toContainText(
    "Temporary target failure",
  );
  await expect(input).toHaveValue(JSON.stringify(value));
  await cards[0]
    .getByRole("button", { name: "Antwort testen", exact: true })
    .click();
  await expect(cards[0]).toContainText("Extracted text");
  await expect(cards[1]).not.toContainText("Extracted text");
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
});
