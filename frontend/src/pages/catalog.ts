import { DRAFTS } from "./drafts";
import { Component, DestroyRef, inject, signal } from "@angular/core";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { Api, ApiError, Item } from "../api";
import { UI, pretty } from "../ui";
import { tr } from "../i18n";

@Component({
  standalone: true,
  imports: [...UI, RouterLink],
  templateUrl: "./catalog.html",
})
export class CatalogPage {
  api = inject(Api);
  route = inject(ActivatedRoute);
  router = inject(Router);
  kind = signal("services");
  items = signal<Item[]>([]);
  editing = signal<Item | null>(null);
  lookups = signal<Record<string, Item[]>>({});
  loading = signal(true);
  busy = signal(false);
  conflict = signal(false);
  private editorGeneration = 0;
  private listGeneration = 0;
  private destroyed = false;
  operations = signal<Item[]>([]);
  extra = signal("");
  openapiUrl = "";
  operation = -1;
  mapping = "";
  schema = "";
  content = "";
  format = "jsonl";
  steps = "";
  aliases: string[] = [];
  previewInput = '{"title":"Beispiel"}';
  frequency = "weekly";
  scheduleDates = signal<string[]>([]);
  help: Record<string, string> = {
    services: "serviceHelp",
    datasets: "datasetHelp",
    criteria: "criteriaHelp",
    providers: "providerHelp",
    plans: "planHelp",
    schedules: "scheduleHelp",
  };
  constructor() {
    inject(DestroyRef).onDestroy(() => {
      this.destroyed = true;
      this.editorGeneration++;
      this.listGeneration++;
    });
    this.route.data.subscribe((data) => {
      this.cancelEditor();
      this.kind.set(data["kind"]);
      this.extra.set("");
      this.load();
    });
  }
  async load() {
    const kind = this.kind();
    const generation = ++this.listGeneration;
    const current = () =>
      !this.destroyed &&
      generation === this.listGeneration &&
      kind === this.kind();
    this.loading.set(true);
    try {
      const items = await this.api.request("/catalog/" + kind);
      if (!current()) return;
      this.items.set(items);
      const keys = ["services", "datasets", "criteria", "providers", "plans"];
      const lookups = Object.fromEntries(
        await Promise.all(
          keys.map(async (key) => [
            key,
            await this.api.request("/catalog/" + key),
          ]),
        ),
      );
      if (current()) this.lookups.set(lookups);
    } catch (e) {
      if (current()) this.api.fail(e);
    } finally {
      if (current()) this.loading.set(false);
    }
  }
  cancelEditor() {
    this.editorGeneration++;
    this.editing.set(null);
    this.conflict.set(false);
    this.busy.set(false);
  }
  permitted() {
    return ["services", "providers"].includes(this.kind())
      ? this.api.isAdmin()
      : this.api.canEdit();
  }
  async open(item?: Item) {
    const kind = this.kind();
    const generation = ++this.editorGeneration;
    this.busy.set(true);
    try {
      const value = item
        ? await this.api.request<Item>("/catalog/" + kind + "/" + item["id"])
        : { name: "", description: "", ...structuredClone(DRAFTS[kind]) };
      if (this.destroyed || generation !== this.editorGeneration) return;
      this.applyEditor(value);
      this.conflict.set(false);
    } catch (e) {
      this.api.fail(e);
    } finally {
      if (generation === this.editorGeneration) this.busy.set(false);
    }
  }
  applyEditor(value: Item) {
    this.mapping = pretty(value["mapping"] || { $input: "" });
    this.schema = value["response_schema"]
      ? pretty(value["response_schema"])
      : "";
    this.content = value["cases"]
      ? value["cases"].map((r: Item) => JSON.stringify(r)).join("\n")
      : "";
    this.format = "jsonl";
    this.steps = (value["steps"] || []).join("\n");
    this.aliases = (value["fields"] || []).map((f: Item) =>
      pretty(f["aliases"] || {}),
    );
    this.editing.set(value);
    this.extra.set("");
    this.operations.set([]);
    this.operation = -1;
    this.scheduleDates.set([]);
    this.frequency =
      value["cron"] === "0 8 * * 1"
        ? "weekly"
        : value["cron"] === "0 8 * * *"
          ? "daily"
          : value["cron"] === "0 * * * *"
            ? "hourly"
            : "custom";
    setTimeout(() => document.getElementById("editor-title")?.focus());
  }
  async save() {
    const form = this.editing();
    if (!form) return;
    const generation = this.editorGeneration;
    const current = () =>
      !this.destroyed && generation === this.editorGeneration;
    this.busy.set(true);
    try {
      const value = structuredClone(form);
      delete value["has_secret"];
      switch (this.kind()) {
        case "services":
          value["mapping"] = JSON.parse(this.mapping);
          value["response_schema"] = this.schema.trim()
            ? JSON.parse(this.schema)
            : null;
          break;
        case "datasets":
          value["content"] = this.content;
          value["format"] = this.format;
          delete value["cases"];
          break;
        case "criteria":
          value["steps"] = this.steps
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean);
          break;
        case "plans":
          value["fields"] = value["fields"].map((f: Item, i: number) => ({
            ...f,
            aliases: JSON.parse(this.aliases[i] || "{}"),
          }));
          break;
      }
      const path =
        "/catalog/" + this.kind() + (value["id"] ? "/" + value["id"] : "");
      await this.api.request(path, value["id"] ? "PUT" : "POST", value);
      if (!current()) return;
      this.editing.set(null);
      await this.load();
    } catch (e) {
      if (!current()) return;
      if (e instanceof ApiError && e.status === 409) this.conflict.set(true);
      else this.api.fail(e);
    } finally {
      if (current()) this.busy.set(false);
    }
  }
  addField() {
    this.editing()?.["fields"].push({
      name: "",
      output_path: "/",
      reference_path: "/",
      aliases: {},
    });
    this.aliases.push("{}");
  }
  removeField(index: number) {
    this.editing()?.["fields"].splice(index, 1);
    this.aliases.splice(index, 1);
  }
  async importFile(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    if (file.size > 5_000_000) {
      this.api.fail(new Error("5 MB"));
      return;
    }
    this.content = await file.text();
    this.format = file.name.endsWith(".csv")
      ? "csv"
      : file.name.endsWith(".json")
        ? "json"
        : "jsonl";
  }
  async start(item: Item) {
    this.busy.set(true);
    try {
      const run = await this.api.request("/runs", "POST", {
        plan_id: item["id"],
      });
      await this.router.navigateByUrl("/runs/" + run.id);
    } catch (e) {
      this.api.fail(e);
    } finally {
      this.busy.set(false);
    }
  }
  async loadOpenapi() {
    this.busy.set(true);
    try {
      const result = await this.api.request("/connections/openapi", "POST", {
        url: this.openapiUrl,
      });
      this.operations.set(result.operations);
      this.operation = -1;
      this.extra.set(pretty(result.schemas));
    } catch (e) {
      this.api.fail(e);
    } finally {
      this.busy.set(false);
    }
  }
  selectOperation() {
    const op = this.operations()[this.operation];
    const form = this.editing();
    if (!op || !form) return;
    form["url"] = op["url"];
    form["method"] = op["method"];
    if (!form["name"]) form["name"] = op["name"];
    this.extra.set(pretty(op["input_schema"] || op["parameters"]));
  }
  async preview(item: Item) {
    this.busy.set(true);
    try {
      const result = await this.api.request("/connections/preview", "POST", {
        service_id: item["id"],
        input: JSON.parse(this.previewInput),
      });
      this.extra.set(pretty(result));
    } catch (e) {
      this.api.fail(e);
    } finally {
      this.busy.set(false);
    }
  }
  async models(item: Item) {
    this.busy.set(true);
    try {
      this.extra.set(
        pretty(
          await this.api.request("/connections/models", "POST", {
            provider_id: item["id"],
          }),
        ),
      );
    } catch (e) {
      this.api.fail(e);
    } finally {
      this.busy.set(false);
    }
  }
  async versions(item: Item) {
    try {
      this.extra.set(
        pretty(
          await this.api.request(
            "/catalog/" + this.kind() + "/" + item["id"] + "/versions",
          ),
        ),
      );
    } catch (e) {
      this.api.fail(e);
    }
  }
  chooseFrequency() {
    const presets: Record<string, string> = {
      daily: "0 8 * * *",
      weekly: "0 8 * * 1",
      hourly: "0 * * * *",
    };
    const form = this.editing();
    if (form && presets[this.frequency]) form["cron"] = presets[this.frequency];
    this.scheduleDates.set([]);
  }
  async previewSchedule() {
    try {
      const result = await this.api.request(
        "/connections/schedule-preview",
        "POST",
        this.editing(),
      );
      this.scheduleDates.set(result.dates);
    } catch (e) {
      this.api.fail(e);
    }
  }
  localDate(value: string, zone: string) {
    return new Intl.DateTimeFormat("de-DE", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: zone,
    }).format(new Date(value));
  }
  async remove(item: Item) {
    if (!confirm(tr("deleteConfirm"))) return;
    try {
      await this.api.request(
        "/catalog/" + this.kind() + "/" + item["id"],
        "DELETE",
      );
      await this.load();
    } catch (e) {
      this.api.fail(e);
    }
  }
  providerKind() {
    const f = this.editing();
    if (f)
      f["base_url"] =
        f["kind"] === "openai"
          ? "https://api.openai.com/v1"
          : "https://b-api.prod.openeduhub.net";
  }
  count(item: Item) {
    return (
      this.lookups()["datasets"]?.find((d) => d["id"] === item["dataset_id"])?.[
        "case_count"
      ] || 0
    );
  }
}
