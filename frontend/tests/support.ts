import { expect, APIRequestContext, Page } from "@playwright/test";

export async function waitForApplication(request: APIRequestContext) {
  await expect
    .poll(
      async () => {
        try {
          return (await request.get("/api/health", { timeout: 3000 })).status();
        } catch {
          return 0;
        }
      },
      { timeout: 30000 },
    )
    .toBe(200);
}

export async function signIn(page: Page, username = "admin") {
  await page.goto("/");
  await page.getByLabel("Benutzername").fill(username);
  await page
    .getByLabel("Passwort", { exact: true })
    .fill(process.env["EVAL_TEST_PASSWORD"] || "Test-password-for-browser!");
  await page.getByRole("button", { name: "Anmelden", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Überblick", exact: true }),
  ).toBeVisible();
}
