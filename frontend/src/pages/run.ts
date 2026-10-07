import { Component, DestroyRef, inject, signal } from "@angular/core";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { MatDialog } from "@angular/material/dialog";
import { Api, Item, Page } from "../api";
import { UI, percent, pretty } from "../ui";
import { CaseDialog } from "./case";
import { Pager } from "../pager";
@Component({
  standalone: true,
  imports: [...UI, RouterLink, Pager],
  templateUrl: "./run.html",
})
export class RunPage {
  api = inject(Api);
  route = inject(ActivatedRoute);
  router = inject(Router);
  dialog = inject(MatDialog);
  run = signal<Item | null>(null);
  history = signal<Item[]>([]);
  busy = signal(false);
  caseOffset = signal(0);
  caseBusy = signal(false);
  inspecting = signal(false);
  classPages = signal<Record<string, Page>>({});
  classBusy = signal<string | null>(null);
  private destroyed = false;
  pct = percent;
  pretty = pretty;
  id = "";
  selectedField = "";
  private loadGeneration = 0;
  private loadingRunId: string | null = null;
  constructor() {
    const interval = setInterval(() => {
      if (this.active()) this.load();
    }, 2000);
    inject(DestroyRef).onDestroy(() => {
      clearInterval(interval);
      this.loadGeneration++;
      this.destroyed = true;
    });
    this.route.params.subscribe((params) => {
      this.id = params["id"];
      this.selectedField = "";
      this.history.set([]);
      this.caseOffset.set(0);
      this.classPages.set({});
      this.run.set(null);
      this.load();
    });
  }
  async load() {
    const id = this.id;
    if (this.loadingRunId === id) return;
    const generation = ++this.loadGeneration;
    this.loadingRunId = id;
    const current = () => id === this.id && generation === this.loadGeneration;
    try {
      const old = this.run();
      const r = old
        ? { ...old, ...(await this.api.request("/runs/" + id + "/status")) }
        : await this.api.request("/runs/" + id);
      if (!current()) return;
      if (old) r["results"] = this.run()?.["results"] || r["results"];
      if (old && r["progress"] !== old["progress"] && !this.caseBusy()) {
        const offset = this.caseOffset();
        const page = await this.api.request<Page>(
          "/runs/" + id + "/cases?offset=" + offset,
        );
        if (!current()) return;
        if (offset === this.caseOffset() && !this.caseBusy())
          r["results"] = page.items;
        else r["results"] = this.run()?.["results"] || r["results"];
      }
      this.run.set(r);
      if (!this.selectedField)
        this.selectedField =
          this.run()?.["snapshot"]["plan"]["fields"][0]?.name || "__judge";
      if (!this.active()) {
        const all = await this.api.request<Page>(
          "/runs/page?limit=12&status=completed&comparison_key=" +
            encodeURIComponent(r["comparison_key"]),
        );
        if (!current()) return;
        this.history.set(all.items.reverse());
      }
    } catch (e) {
      if (current()) this.api.fail(e);
    } finally {
      if (current()) this.loadingRunId = null;
    }
  }
  active() {
    return ["queued", "running"].includes(this.run()?.["status"]);
  }
  async inspect(row: Item) {
    const id = this.id;
    this.inspecting.set(true);
    try {
      const data = await this.api.request(
        "/runs/" + id + "/cases/" + row["ordinal"],
      );
      if (this.destroyed || id !== this.id) return;
      this.dialog.open(CaseDialog, {
        data,
        width: "960px",
        maxWidth: "96vw",
        autoFocus: "first-tabbable",
        restoreFocus: true,
      });
    } catch (e) {
      this.api.fail(e);
    } finally {
      this.inspecting.set(false);
    }
  }
  async loadCases(offset: number) {
    const id = this.id;
    this.caseBusy.set(true);
    try {
      let page = await this.api.request<Page>(
        "/runs/" + id + "/cases?offset=" + offset,
      );
      if (this.destroyed || id !== this.id) return;
      // A terminal status may arrive while this page is pending. Refresh that stale page.
      while (page.total < this.run()?.["progress"]) {
        page = await this.api.request<Page>(
          "/runs/" + id + "/cases?offset=" + offset,
        );
        if (this.destroyed || id !== this.id) return;
      }
      this.caseOffset.set(page.offset);
      this.run.update((r) => (r ? { ...r, results: page.items } : r));
    } catch (e) {
      this.api.fail(e);
    } finally {
      this.caseBusy.set(false);
    }
  }
  toggleClasses(event: Event, name: string) {
    if ((event.target as HTMLDetailsElement).open && !this.classPages()[name])
      this.loadClasses(name);
  }
  async loadClasses(name: string, offset = 0) {
    const id = this.id;
    this.classBusy.set(name);
    try {
      const page = await this.api.request<Page>(
        "/runs/" +
          id +
          "/classes?field=" +
          encodeURIComponent(name) +
          "&offset=" +
          offset,
      );
      if (this.destroyed || id !== this.id) return;
      this.classPages.update((pages) => ({ ...pages, [name]: page }));
    } catch (e) {
      this.api.fail(e);
    } finally {
      this.classBusy.set(null);
    }
  }
  async stop() {
    try {
      await this.api.request("/runs/" + this.id + "/cancel", "POST");
      await this.load();
    } catch (e) {
      this.api.fail(e);
    }
  }
  async recompute() {
    this.busy.set(true);
    try {
      const r = await this.api.request(
        "/runs/" + this.id + "/recompute",
        "POST",
      );
      await this.router.navigateByUrl("/runs/" + r.id);
    } catch (e) {
      this.api.fail(e);
    } finally {
      this.busy.set(false);
    }
  }
  async rerun() {
    this.busy.set(true);
    try {
      const r = await this.api.request("/runs", "POST", {
        plan_id: this.run()?.["snapshot"]["plan"]["id"],
      });
      await this.router.navigateByUrl("/runs/" + r.id);
    } catch (e) {
      this.api.fail(e);
    } finally {
      this.busy.set(false);
    }
  }
  configuration() {
    const saved = structuredClone(this.run()?.["snapshot"] || {});
    if (saved["dataset"]) delete saved["dataset"]["cases"];
    return pretty(saved);
  }
  value(row: Item) {
    return this.selectedField === "__judge"
      ? row["summary"]?.judge?.mean_score
      : row["summary"]?.reference?.find(
          (f: Item) => f["name"] === this.selectedField,
        )?.micro?.f1;
  }
  points() {
    return this.history()
      .map((r, i) => {
        const value = this.value(r);
        return {
          x: 30 + (i * 540) / Math.max(1, this.history().length - 1),
          y: 155 - (value || 0) * 130,
          value,
          id: r["id"],
        };
      })
      .filter((p) => p.value !== null && p.value !== undefined);
  }
  line() {
    return this.points()
      .map((p) => p.x + "," + p.y)
      .join(" ");
  }
}
