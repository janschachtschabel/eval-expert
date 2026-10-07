import { expect, APIRequestContext } from "@playwright/test";

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
