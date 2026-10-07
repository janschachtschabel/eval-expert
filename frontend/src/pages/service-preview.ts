import { Component, DestroyRef, inject, input, signal } from "@angular/core";
import { Api, Item } from "../api";
import { UI, pretty } from "../ui";
import { inputExample } from "./input-example";

@Component({
  selector: "app-service-preview",
  standalone: true,
  imports: UI,
  template: `
    <details (toggle)="toggle($event)">
      <summary>{{ "preview" | t }}</summary>
      @if (loading()) {
        <p role="status">{{ "loading" | t }}</p>
      } @else if (ready()) {
        <p class="hint">{{ "previewHelp" | t }}</p>
        <mat-form-field>
          <mat-label>{{ "previewInput" | t }}</mat-label>
          <textarea
            matInput
            [(ngModel)]="value"
            class="code"
            rows="5"
            [disabled]="busy()"
          ></textarea>
        </mat-form-field>
        <button mat-button (click)="preview()" [disabled]="busy()">
          {{ (busy() ? "loading" : "preview") | t }}
        </button>
      } @else {
        <button mat-button (click)="load()">{{ "retry" | t }}</button>
      }
      @if (error()) {
        <p role="alert" class="error">{{ "error" | t }}: {{ error() }}</p>
      }
      @if (result()) {
        <h3>{{ "response" | t }}</h3>
        <pre>{{ result() }}</pre>
      }
    </details>
  `,
})
export class ServicePreview {
  service = input.required<Item>();
  private api = inject(Api);
  private destroyed = false;
  loading = signal(false);
  ready = signal(false);
  busy = signal(false);
  error = signal("");
  result = signal("");
  value = "";

  constructor() {
    inject(DestroyRef).onDestroy(() => (this.destroyed = true));
  }
  toggle(event: Event) {
    if ((event.target as HTMLDetailsElement).open && !this.ready()) this.load();
  }
  async load() {
    if (this.loading()) return;
    this.loading.set(true);
    this.error.set("");
    try {
      const service = await this.api.request<Item>(
        "/catalog/services/" + this.service()["id"],
      );
      if (this.destroyed) return;
      this.value = pretty(
        service["kind"] === "demo"
          ? { title: "Beispiel" }
          : inputExample(service["mapping"]),
      );
      this.ready.set(true);
    } catch (e) {
      if (!this.destroyed)
        this.error.set(e instanceof Error ? e.message : String(e));
    } finally {
      if (!this.destroyed) this.loading.set(false);
    }
  }
  async preview() {
    this.busy.set(true);
    this.error.set("");
    this.result.set("");
    try {
      const result = await this.api.request("/connections/preview", "POST", {
        service_id: this.service()["id"],
        input: JSON.parse(this.value),
      });
      if (!this.destroyed) this.result.set(pretty(result));
    } catch (e) {
      if (!this.destroyed)
        this.error.set(e instanceof Error ? e.message : String(e));
    } finally {
      if (!this.destroyed) this.busy.set(false);
    }
  }
}
