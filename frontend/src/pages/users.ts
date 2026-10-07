import { NgForm } from "@angular/forms";
import { controlError } from "../validation";
import { Component, inject, signal } from "@angular/core";
import { Api, Item } from "../api";
import { UI } from "../ui";
@Component({
  standalone: true,
  imports: UI,
  template: ` <div class="page-heading">
      <div>
        <p class="eyebrow">{{ "brand" | t }}</p>
        <h1>{{ "users" | t }}</h1>
        <p>{{ "userHelp" | t }}</p>
      </div>
    </div>
    @if (!api.isAdmin()) {
      <p class="alert" role="alert">{{ "permission" | t }}</p>
    } @else {
      <section class="surface editor">
        <h2>{{ "addUser" | t }}</h2>
        <form #editorForm="ngForm" (ngSubmit)="save(editorForm)">
          <div class="form-grid">
            <mat-form-field
              ><mat-label>{{ "username" | t }}</mat-label
              ><input
                matInput
                name="username"
                [(ngModel)]="username"
                required
              /><mat-error>{{
                errorMessage(editorForm.controls["username"]) | t
              }}</mat-error></mat-form-field
            >
            <mat-form-field
              ><mat-label>{{ "password" | t }}</mat-label
              ><input
                matInput
                name="password"
                [(ngModel)]="password"
                type="password"
                autocomplete="new-password"
                minlength="12"
                required
              /><mat-error>{{
                errorMessage(editorForm.controls["password"]) | t
              }}</mat-error></mat-form-field
            >
            <mat-form-field
              ><mat-label>{{ "role" | t }}</mat-label
              ><mat-select name="role" [(ngModel)]="role">
                @for (r of ["admin", "editor", "reviewer", "viewer"]; track r) {
                  <mat-option [value]="r">{{ r | t }}</mat-option>
                }</mat-select
              ><mat-error>{{
                errorMessage(editorForm.controls["role"]) | t
              }}</mat-error></mat-form-field
            >
          </div>
          <button mat-flat-button type="submit" [disabled]="busy()">
            {{ "save" | t }}
          </button>
        </form>
      </section>
      <div class="catalog-grid">
        @for (user of users(); track user["id"]) {
          <article class="surface catalog-card">
            <h2>{{ user["username"] }}</h2>
            <p>
              {{ user["role"] | t }} ·
              {{ (user["active"] ? "active" : "inactive") | t }}
            </p>
            @if (user["active"] && user["id"] !== api.user()?.["id"]) {
              <button mat-button (click)="disable(user)">
                {{ "disable" | t }}
              </button>
            }
          </article>
        }
      </div>
    }`,
})
export class UsersPage {
  errorMessage = controlError;
  api = inject(Api);
  users = signal<Item[]>([]);
  busy = signal(false);
  username = "";
  password = "";
  role = "viewer";
  constructor() {
    this.load();
  }
  async load() {
    if (!this.api.isAdmin()) return;
    try {
      this.users.set(await this.api.request("/users"));
    } catch (e) {
      this.api.fail(e);
    }
  }
  async save(editorForm: NgForm) {
    editorForm.control.markAllAsTouched();
    if (editorForm.invalid || this.busy()) return;
    this.busy.set(true);
    try {
      await this.api.request("/users", "POST", {
        username: this.username,
        password: this.password,
        role: this.role,
      });
      editorForm.resetForm({ role: "viewer" });
      this.password = "";
      this.username = "";
      await this.load();
    } catch (e) {
      this.api.fail(e);
    } finally {
      this.busy.set(false);
    }
  }
  async disable(user: Item) {
    try {
      await this.api.request("/users/" + user["id"] + "/disable", "POST");
      await this.load();
    } catch (e) {
      this.api.fail(e);
    }
  }
}
