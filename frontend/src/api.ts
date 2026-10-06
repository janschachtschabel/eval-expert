import { Injectable, signal } from "@angular/core";
export type Item = Record<string, any>;
@Injectable({ providedIn: "root" })
export class Api {
  user = signal<Item | null>(null);
  error = signal("");
  csrf = "";
  async request<T = any>(
    path: string,
    method = "GET",
    body?: unknown,
  ): Promise<T> {
    const response = await fetch("/api" + path, {
      method,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(this.csrf ? { "X-CSRF-Token": this.csrf } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (!response.ok) {
      const value = await response.json().catch(() => ({}));
      if (response.status === 401 && path !== "/auth/login")
        this.user.set(null);
      throw new Error(
        typeof value.detail === "string"
          ? value.detail
          : "HTTP " + response.status,
      );
    }
    return response.status === 204 ? (undefined as T) : response.json();
  }
  async restore() {
    try {
      this.accept(await this.request("/auth/session"));
    } catch {
      this.user.set(null);
    }
  }
  accept(session: Item) {
    this.csrf = session["csrf_token"];
    this.user.set(session["user"]);
  }
  canEdit() {
    return ["admin", "editor"].includes(this.user()?.["role"]);
  }
  isAdmin() {
    return this.user()?.["role"] === "admin";
  }
  fail(error: unknown) {
    this.error.set(error instanceof Error ? error.message : String(error));
  }
}
