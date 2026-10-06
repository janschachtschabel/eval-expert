import { Component, inject, signal } from "@angular/core";
import { RouterLink } from "@angular/router";
import { Api, Item } from "../api";
import { UI, percent } from "../ui";
@Component({
  standalone: true,
  imports: [...UI, RouterLink],
  template: `
    <div class="page-heading">
      <div>
        <p class="eyebrow">{{ "evidence" | t }}</p>
        <h1>{{ "runs" | t }}</h1>
        <p>{{ "historyHelp" | t }}</p>
      </div>
      <a mat-flat-button routerLink="/plans">{{ "start" | t }}</a>
    </div>
    @if (loading()) {
      <p role="status">{{ "loading" | t }}</p>
    } @else if (!runs().length) {
      <section class="empty-state">
        <h2>{{ "emptyRuns" | t }}</h2>
        <a mat-button routerLink="/plans">{{ "plans" | t }}</a>
      </section>
    } @else {
      <div class="run-list">
        @for (run of runs(); track run["id"]) {
          <a [routerLink]="'/runs/' + run['id']" class="run-card"
            ><div>
              <span
                class="badge"
                [class.success]="run['status'] === 'completed'"
                >{{ run["status"] | t }}</span
              >
              @if (run["demo"]) {
                <span class="badge amber">{{ "demo" | t }}</span>
              }
              <h2>{{ run["name"] }}</h2>
              <p>
                {{ run["created"] | date: "dd.MM.yyyy HH:mm" }} ·
                {{ run["progress"] }}/{{ run["total"] }} {{ "cases" | t }}
              </p>
            </div>
            <div class="run-score">
              <strong>{{
                pct(run["summary"]?.reference?.[0]?.micro?.f1)
              }}</strong
              ><span>{{ "f1" | t }}</span>
            </div>
            <div class="run-score">
              <strong>{{ pct(run["summary"]?.judge?.mean_score) }}</strong
              ><span>{{ "judge" | t }}</span>
            </div></a
          >
        }
      </div>
    }
  `,
})
export class RunsPage {
  api = inject(Api);
  runs = signal<Item[]>([]);
  loading = signal(true);
  pct = percent;
  constructor() {
    this.api
      .request<Item[]>("/runs")
      .then((r) => this.runs.set(r))
      .catch((e) => this.api.fail(e))
      .finally(() => this.loading.set(false));
  }
}
