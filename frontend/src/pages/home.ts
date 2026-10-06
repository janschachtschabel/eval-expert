import { Component, inject, signal } from "@angular/core";
import { Router, RouterLink } from "@angular/router";
import { Api, Item } from "../api";
import { UI, percent } from "../ui";
@Component({
  standalone: true,
  imports: [...UI, RouterLink],
  template: `
    <div class="page-heading">
      <div>
        <p class="eyebrow">{{ "brand" | t }}</p>
        <h1>{{ "overview" | t }}</h1>
        <p>{{ "intro" | t }}</p>
      </div>
      <a mat-flat-button routerLink="/plans">{{ "setup" | t }}</a>
    </div>
    <section class="steps" [attr.aria-label]="'setup' | t">
      @for (step of steps; track step.title; let i = $index) {
        <a class="step-card" [routerLink]="step.path"
          ><span class="step-index">{{ i + 1 }}</span
          ><strong>{{ step.title | t }}</strong>
          <p>{{ step.help | t }}</p></a
        >
      }
    </section>
    <div class="metric-grid">
      @for (key of ["services", "datasets", "plans"]; track key) {
        <a class="metric-card" [routerLink]="'/' + key">
          <p>{{ key | t }}</p>
          <strong>{{ counts()[key] || 0 }}</strong
          ><span>{{ "setupCount" | t }}</span></a
        >
      }
      <a class="metric-card accent" routerLink="/runs"
        ><p>{{ "runs" | t }}</p>
        <strong>{{ runs().length }}</strong
        ><span>{{ "evidence" | t }}</span></a
      >
    </div>
    <div class="section-heading">
      <h2>{{ "latest" | t }}</h2>
      <a mat-button routerLink="/runs">{{ "allRuns" | t }}</a>
    </div>
    @if (loading()) {
      <p role="status">{{ "loading" | t }}</p>
    } @else if (!runs().length) {
      <section class="empty-state">
        <h3>{{ "emptyRuns" | t }}</h3>
        <p>{{ "demoHelp" | t }}</p>
      </section>
    } @else {
      <div class="run-list">
        @for (run of runs().slice(0, 5); track run["id"]) {
          <a [routerLink]="'/runs/' + run['id']" class="run-card">
            <div>
              <span
                class="badge"
                [class.success]="run['status'] === 'completed'"
                >{{ run["status"] | t }}</span
              >
              <h3>{{ run["name"] }}</h3>
              <p>{{ run["created"] | date: "dd.MM.yyyy HH:mm" }}</p>
            </div>
            <div class="run-score">
              <strong>{{
                pct(run["summary"]?.reference?.[0]?.micro?.f1)
              }}</strong
              ><span>{{ "f1" | t }}</span>
            </div>
          </a>
        }
      </div>
    }
    @if (api.isAdmin()) {
      <section class="surface demo-panel">
        <div>
          <h2>{{ "demo" | t }}</h2>
          <p>{{ "demoHelp" | t }}</p>
        </div>
        <button mat-stroked-button (click)="demo()" [disabled]="busy()">
          {{ "demoSetup" | t }}
        </button>
      </section>
    }
  `,
})
export class Home {
  api = inject(Api);
  router = inject(Router);
  counts = signal<Item>({});
  runs = signal<Item[]>([]);
  loading = signal(true);
  busy = signal(false);
  pct = percent;
  steps = [
    { title: "stepService", help: "stepServiceHelp", path: "/services" },
    { title: "stepData", help: "stepDataHelp", path: "/datasets" },
    { title: "stepPlan", help: "stepPlanHelp", path: "/plans" },
    { title: "stepRun", help: "stepRunHelp", path: "/runs" },
  ];
  constructor() {
    Promise.all(
      ["services", "datasets", "plans"].map(async (key) => [
        key,
        (await this.api.request<Item[]>("/catalog/" + key)).length,
      ]),
    )
      .then((values) => this.counts.set(Object.fromEntries(values)))
      .catch((e) => this.api.fail(e));
    this.api
      .request<Item[]>("/runs")
      .then((r) => this.runs.set(r))
      .catch((e) => this.api.fail(e))
      .finally(() => this.loading.set(false));
  }
  async demo() {
    this.busy.set(true);
    try {
      await this.api.request("/demo", "POST");
      await this.router.navigateByUrl("/plans");
    } catch (e) {
      this.api.fail(e);
    } finally {
      this.busy.set(false);
    }
  }
}
