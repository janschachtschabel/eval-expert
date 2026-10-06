import { Component, DestroyRef, inject, signal } from "@angular/core";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { MatDialog } from "@angular/material/dialog";
import { Api, Item } from "../api";
import { UI, percent, pretty } from "../ui";
import { CaseDialog } from "./case";
@Component({
  standalone: true,
  imports: [...UI, RouterLink],
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
    });
    this.route.params.subscribe((params) => {
      this.id = params["id"];
      this.selectedField = "";
      this.history.set([]);
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
      const r = await this.api.request("/runs/" + id);
      if (!current()) return;
      this.run.set(r);
      if (!this.selectedField)
        this.selectedField =
          this.run()?.["snapshot"]["plan"]["fields"][0]?.name || "__judge";
      if (!this.active()) {
        const all = await this.api.request<Item[]>("/runs");
        if (!current()) return;
        this.history.set(
          all
            .filter(
              (x) =>
                x["status"] === "completed" &&
                x["comparison_key"] === r["comparison_key"],
            )
            .slice(0, 12)
            .reverse(),
        );
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
  inspect(row: Item) {
    this.dialog.open(CaseDialog, {
      data: row,
      width: "960px",
      maxWidth: "96vw",
      autoFocus: "first-tabbable",
      restoreFocus: true,
    });
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
