import { test, expect } from "@playwright/test";
import { signIn, waitForApplication } from "./support";
import {
  names,
  cases,
  card,
  choose,
  view,
  create,
  save,
  inspectLayout,
  completed,
  start,
  providers,
} from "./journey-support";
test.use({ actionTimeout: 15000 });

test("all nine views support a complete URL evaluation, evidence, repeat runs, schedules and local team access", async ({
  page,
  context,
}) => {
  test.setTimeout(180000);
  await waitForApplication(page.request);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await signIn(page);
  await inspectLayout(page);
  await test.step("service OpenAPI, persistence and real preview", async () => {
    await create(page, "Dienste", names.service);
    await page
      .getByLabel("OpenAPI-URL", { exact: true })
      .fill("https://metadata.example.org/empty-openapi.json");
    await page
      .getByRole("button", { name: "Operationen laden", exact: true })
      .click();
    await expect(page.locator(".editor")).toContainText(
      "Keine unterstützten Operationen",
    );
    await page
      .getByLabel("OpenAPI-URL", { exact: true })
      .fill("https://metadata.example.org/openapi.json");
    await page
      .getByRole("button", { name: "Operationen laden", exact: true })
      .click();
    await choose(page, "API-Operation", "POST · Extract URL");
    await expect(page.getByLabel("Endpoint-URL", { exact: true })).toHaveValue(
      "https://metadata.example.org/from-url",
    );
    await page
      .getByLabel("Eingabezuordnung (JSON)", { exact: true })
      .fill("{broken");
    await page.getByRole("button", { name: "Speichern", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("JSON-Eingabe prüfen");
    await expect(
      page.getByLabel("Eingabezuordnung (JSON)", { exact: true }),
    ).toHaveValue("{broken");
    await page
      .getByLabel("Eingabezuordnung (JSON)", { exact: true })
      .fill(JSON.stringify({ url: { $input: "/url" } }));
    await save(page, names.service);
    await card(page, names.service)
      .getByRole("button", { name: "Bearbeiten", exact: true })
      .click();
    expect(
      JSON.parse(
        await page
          .getByLabel("Eingabezuordnung (JSON)", { exact: true })
          .inputValue(),
      ),
    ).toEqual({ url: { $input: "/url" } });
    await save(page, names.service);
    await card(page, names.service).locator("summary").click();
    await card(page, names.service)
      .getByLabel("Testeingabe (JSON)")
      .fill(JSON.stringify(cases[0].input));
    await card(page, names.service)
      .getByRole("button", { name: "Antwort testen", exact: true })
      .click();
    await expect(card(page, names.service)).toContainText(
      "Bruchrechnung ohne Werbung",
    );
    await inspectLayout(page);
  });
  await test.step("dataset import and editing", async () => {
    await create(page, "Testdaten", names.dataset);
    await page.locator("#dataset-file").setInputFiles({
      name: "five-urls.jsonl",
      mimeType: "application/jsonl",
      buffer: Buffer.from(cases.map((row) => JSON.stringify(row)).join("\n")),
    });
    await save(page, names.dataset);
    await expect(card(page, names.dataset)).toContainText("5 Fälle");
    await card(page, names.dataset)
      .getByRole("button", { name: "Bearbeiten", exact: true })
      .click();
    expect(
      (await page.getByLabel("Datensatz", { exact: true }).inputValue())
        .split("\n")
        .map((line) => JSON.parse(line)),
    ).toEqual(cases);
    await save(page, names.dataset);
    await inspectLayout(page);
  });
  await test.step("criterion with source and score", async () => {
    await create(page, "Kriterien", names.criterion);
    await page
      .getByLabel("Prüfschritte", { exact: true })
      .fill("Bewerte Werbefreiheit anhand des extrahierten Lerntexts.");
    await page
      .getByLabel("Antwortfeld (JSON Pointer)", { exact: true })
      .fill("/text");
    await page
      .getByLabel("Quellfeld (JSON Pointer)", { exact: true })
      .fill("/text");
    await choose(page, "Quelle aus", "Antwort");
    await page.getByLabel("Quellbeleg erforderlich").check();
    await page.getByLabel("Bestehensgrenze (0–1)", { exact: true }).fill("0.8");
    await save(page, names.criterion);
    await card(page, names.criterion)
      .getByRole("button", { name: "Versionsverlauf" })
      .click();
    await expect(page.locator(".evidence-panel")).toContainText(
      '"context_source": "output"',
    );
    await page
      .locator(".evidence-panel")
      .getByRole("button", { name: "Schließen" })
      .click();
    await inspectLayout(page);
  });
  await test.step("all provider adapters and preserved credentials", () =>
    providers(page));
  let original: any;
  await test.step("judge profile starts real worker and DeepEval", async () => {
    await create(page, "Prüfprofile", names.plan);
    await choose(page, "Dienst", names.service);
    await choose(page, "Datensatz", names.dataset + " · 5 Fälle");
    await choose(page, "Messverfahren", "LLM-Bewertung");
    await choose(page, "LLM-Anbindung", names.provider);
    await choose(page, "Bewertungskriterien", names.criterion, true);
    await save(page, names.plan);
    await card(page, names.plan)
      .getByRole("button", { name: "Bearbeiten", exact: true })
      .click();
    await expect(
      page.getByLabel("LLM-Anbindung", { exact: true }),
    ).toContainText(names.provider);
    await save(page, names.plan);
    await inspectLayout(page);
    original = await start(page);
    expect(original.summary.target_success_rate).toBe(0.8);
    expect(original.summary.judge.mean_score).toBeCloseTo(0.9);
    expect(original.summary.judge.valid).toBe(4);
    expect(original.summary.judge.expected).toBe(5);
    await expect(
      page.locator('.table-scroll[aria-label="Einzelergebnisse"]'),
    ).toContainText(cases[0].input.url);
    await inspectLayout(page);
  });
  await test.step("case evidence, CSV, JSON and protocol", async () => {
    await page
      .getByRole("button", { name: "Fall url-0 ansehen", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toContainText(
      "Sachlicher Lerntext ohne Werbeaufforderung",
    );
    await page.getByRole("button", { name: "Schließen", exact: true }).click();
    for (const label of ["CSV exportieren", "JSON exportieren"]) {
      const pending = page.waitForEvent("download");
      await page.getByRole("link", { name: label, exact: true }).click();
      const download = await pending;
      const stream = await download.createReadStream();
      let data = "";
      for await (const chunk of stream!) data += chunk.toString();
      expect(data).toContain(cases[0].input.url);
      expect(data).not.toContain("disposable-browser-key");
      if (label.startsWith("JSON"))
        expect(JSON.parse(data).results).toHaveLength(5);
    }
    const popup = page.waitForEvent("popup");
    await page
      .getByRole("link", { name: "Prüfprotokoll öffnen", exact: true })
      .click();
    const report = await popup;
    await expect(report.locator("body")).toContainText(names.plan);
    await expect(report.locator("body")).toContainText(
      "Sachlicher Lerntext ohne Werbeaufforderung",
    );
    await report.close();
  });
  await test.step("recomputation, rerun and history", async () => {
    await page
      .getByRole("button", {
        name: "Gespeicherte Antworten neu bewerten",
        exact: true,
      })
      .click();
    const recomputed = await completed(page, original.id);
    expect(recomputed.parent_id).toBe(original.id);
    expect(recomputed.results.every((row: any) => row.reused_response)).toBe(
      true,
    );
    await expect(page.locator(".history-chart circle")).toHaveCount(2);
    await page
      .getByRole("button", { name: "Dienst erneut aufrufen", exact: true })
      .click();
    expect((await completed(page, recomputed.id)).summary.judge.valid).toBe(4);
    await view(page, "Prüfläufe");
    await expect(page.locator("main")).toContainText(names.plan);
    await inspectLayout(page);
  });
  await test.step("both b-api adapters use their real request paths", async () => {
    for (const adapter of ["b-api · OpenAI", "b-api · AcademicCloud"]) {
      await view(page, "LLM-Anbindung");
      await card(page, names.provider)
        .getByRole("button", { name: "Bearbeiten", exact: true })
        .click();
      await choose(page, "Anbindung", adapter);
      await save(page, names.provider);
      expect((await start(page)).summary.judge.valid).toBe(4);
    }
  });
  await test.step("combined and reference modes", async () => {
    await view(page, "Prüfprofile");
    await card(page, names.plan)
      .getByRole("button", { name: "Bearbeiten", exact: true })
      .click();
    await choose(page, "Messverfahren", "Beide Verfahren");
    await page.getByRole("button", { name: "Feld hinzufügen" }).click();
    await page.getByLabel("Feldname", { exact: true }).fill("subject");
    await page
      .getByLabel("Antwortfeld (JSON Pointer)", { exact: true })
      .fill("");
    await page
      .getByLabel("Referenzfeld (JSON Pointer)", { exact: true })
      .fill("/subject");
    await save(page, names.plan);
    await card(page, names.plan)
      .getByRole("button", { name: "Bearbeiten", exact: true })
      .click();
    await expect(
      page.getByLabel("Antwortfeld (JSON Pointer)", { exact: true }),
    ).toHaveValue("");
    await page
      .getByLabel("Antwortfeld (JSON Pointer)", { exact: true })
      .fill("/subject");
    await page
      .getByLabel("Referenzfeld (JSON Pointer)", { exact: true })
      .fill("/subject");
    await save(page, names.plan);
    const combined = await start(page);
    expect(combined.summary.reference[0].micro.f1).toBeCloseTo(8 / 9);
    expect(combined.summary.judge.valid).toBe(4);
    await view(page, "Prüfprofile");
    await card(page, names.plan)
      .getByRole("button", { name: "Bearbeiten", exact: true })
      .click();
    await choose(page, "Messverfahren", "Referenzvergleich");
    await save(page, names.plan);
    const reference = await start(page);
    expect(reference.summary.reference[0].micro.f1).toBeCloseTo(8 / 9);
    expect(reference.summary.judge.expected).toBe(0);
  });
  await test.step("a running request can be cancelled", async () => {
    await view(page, "Testdaten");
    await card(page, names.dataset)
      .getByRole("button", { name: "Bearbeiten", exact: true })
      .click();
    await page.getByLabel("Datensatz", { exact: true }).fill(
      cases
        .map((row) =>
          JSON.stringify({
            ...row,
            input: { url: "https://example.org/slow/" + row.id },
          }),
        )
        .join("\n"),
    );
    await save(page, names.dataset);
    await view(page, "Prüfprofile");
    await card(page, names.plan)
      .getByRole("button", { name: "Prüfung starten", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Lauf abbrechen", exact: true })
      .click();
    await expect(page.locator(".page-heading .badge").first()).toHaveText(
      "Abgebrochen",
      { timeout: 15000 },
    );
    const run = await (
      await page.request.get("/api/runs/" + page.url().split("/").at(-1))
    ).json();
    expect(run.progress).toBeLessThan(5);
  });
  await test.step("future schedule, preview, edit, disable and remove", async () => {
    await create(page, "Zeitpläne", names.schedule);
    await choose(page, "Prüfprofile", names.plan);
    await page.getByRole("button", { name: "Nächste Termine" }).click();
    await expect(page.locator(".editor li")).toHaveCount(5);
    await save(page, names.schedule);
    await view(page, "Prüfprofile");
    page.once("dialog", (dialog) => dialog.accept());
    await card(page, names.plan)
      .getByRole("button", { name: "Entfernen", exact: true })
      .click();
    await expect(page.getByRole("alert")).toContainText(
      "Dieser Eintrag wird noch verwendet",
    );
    await expect(card(page, names.plan)).toBeVisible();
    await page
      .getByRole("alert")
      .getByRole("button", { name: "Schließen", exact: true })
      .click();
    await view(page, "Zeitpläne");
    await card(page, names.schedule)
      .getByRole("button", { name: "Bearbeiten", exact: true })
      .click();
    await page.getByLabel("Aktiv", { exact: true }).uncheck();
    await save(page, names.schedule);
    await expect(card(page, names.schedule)).toContainText("Inaktiv");
    await inspectLayout(page);
    page.once("dialog", (dialog) => dialog.accept());
    await card(page, names.schedule)
      .getByRole("button", { name: "Entfernen", exact: true })
      .click();
    await expect(card(page, names.schedule)).toHaveCount(0);
  });
  await test.step("team creation, viewer access and session revocation", async () => {
    await view(page, "Team");
    const username = "functional-viewer-" + Date.now();
    await page.getByLabel("Benutzername", { exact: true }).fill(username);
    await page
      .getByLabel("Passwort", { exact: true })
      .fill("Test-password-for-browser!");
    await page.getByRole("button", { name: "Speichern", exact: true }).click();
    await expect(card(page, username)).toContainText("Lesen");
    await inspectLayout(page);
    const viewerContext = await context
      .browser()!
      .newContext({ baseURL: new URL(page.url()).origin });
    const viewer = await viewerContext.newPage();
    await signIn(viewer, username);
    await expect(
      viewer.locator("aside").getByRole("link", { name: "Team", exact: true }),
    ).toHaveCount(0);
    await viewer.goto("/users");
    await expect(viewer.locator("main")).toContainText("Berechtigungen");
    await expect(viewer.locator("main form")).toHaveCount(0);
    await card(page, username)
      .getByRole("button", { name: "Zugang sperren" })
      .click();
    await expect(card(page, username)).toContainText("Gesperrt");
    expect((await viewer.request.get("/api/auth/session")).status()).toBe(401);
    await viewerContext.close();
    await page.getByRole("button", { name: "Abmelden", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Anmelden", exact: true }),
    ).toBeVisible();
  });
  expect(errors).toEqual([]);
});
