import { Injectable, signal } from "@angular/core";
import { apiMessage } from "./validation";
import { tr } from "./i18n";
export type Item = Record<string, any>;
export interface Page<T = Item> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
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
      throw new ApiError(
        response.status,
        apiMessage(value.detail, response.status, tr),
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
    this.error.set(
      error instanceof SyntaxError
        ? tr("invalidJson")
        : error instanceof Error
          ? error.message
          : String(error),
    );
  }
}
