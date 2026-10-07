import {
  Component,
  ElementRef,
  HostListener,
  ViewChild,
  inject,
  signal,
} from "@angular/core";
import {
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
} from "@angular/router";
import { Api } from "./api";
import { UI } from "./ui";
@Component({
  selector: "app-root",
  standalone: true,
  imports: [...UI, RouterLink, RouterLinkActive, RouterOutlet],
  template: ` @if (loading()) {
      <main class="loading" role="status">{{ "loading" | t }}</main>
    } @else if (!api.user()) {
      <main class="login-layout">
        <section class="login-story">
          <div class="brand-mark">E<span>·</span></div>
          <p class="eyebrow">{{ "brand" | t }}</p>
          <h1>{{ "welcome" | t }}</h1>
          <p>{{ "intro" | t }}</p>
          <div class="story-lines"><span></span><span></span><span></span></div>
        </section>
        <section class="login-card">
          <h2>{{ "login" | t }}</h2>
          <p>{{ "loginHelp" | t }}</p>
          <form (ngSubmit)="login()">
            <mat-form-field
              ><mat-label>{{ "username" | t }}</mat-label>
              <input
                matInput
                name="username"
                [(ngModel)]="username"
                autocomplete="username"
                required
            /></mat-form-field>
            <mat-form-field
              ><mat-label>{{ "password" | t }}</mat-label
              ><input
                matInput
                name="password"
                [(ngModel)]="password"
                type="password"
                autocomplete="current-password"
                required
            /></mat-form-field>
            @if (loginError()) {
              <p class="error" role="alert">{{ "authError" | t }}</p>
            }
            <button mat-flat-button type="submit" [disabled]="busy()">
              {{ "login" | t }}
            </button>
          </form>
        </section>
      </main>
    } @else {
      <a class="skip-link" href="#main">{{ "skip" | t }}</a>
      <div class="app-shell">
        <aside
          id="app-navigation"
          [class.open]="navOpen()"
          aria-label="Navigation"
        >
          <button
            mat-button
            class="mobile-nav-close"
            id="navigation-close"
            (click)="closeNavigation()"
          >
            {{ "closeMenu" | t }}
          </button>
          <a class="brand" routerLink="/" (click)="navOpen.set(false)"
            ><span class="brand-mark small">E<span>·</span></span>
            <span
              ><strong>{{ "brand" | t }}</strong
              ><small>{{ "tagline" | t }}</small></span
            ></a
          >
          <nav>
            @for (entry of nav; track entry.key; let i = $index) {
              @if (entry.key !== "users" || api.isAdmin()) {
                <a
                  [routerLink]="entry.path"
                  routerLinkActive="selected"
                  [routerLinkActiveOptions]="{ exact: true }"
                  (click)="navOpen.set(false)"
                  ><span class="nav-number" aria-hidden="true"
                    >0{{ i + 1 }}</span
                  >{{ entry.key | t }}</a
                >
              }
            }
          </nav>
          <div class="account">
            <span class="avatar" aria-hidden="true">{{
              api.user()?.["username"]?.slice(0, 1)?.toUpperCase()
            }}</span>
            <span
              ><strong>{{ api.user()?.["username"] }}</strong
              ><small>{{ api.user()?.["role"] | t }}</small></span
            >
            <button mat-button (click)="logout()">{{ "logout" | t }}</button>
          </div>
        </aside>
        <div class="workspace">
          <header class="mobile-header">
            <button
              mat-button
              #navigationToggle
              (click)="openNavigation()"
              aria-controls="app-navigation"
              [attr.aria-expanded]="navOpen()"
            >
              {{ "menu" | t }}</button
            ><strong>{{ "brand" | t }}</strong>
          </header>
          @if (api.error()) {
            <div class="alert" role="alert">
              <span>{{ api.error() }}</span
              ><button mat-button (click)="api.error.set('')">
                {{ "close" | t }}
              </button>
            </div>
          }
          <main id="main" tabindex="-1"><router-outlet></router-outlet></main>
        </div>
      </div>
    }`,
})
export class App {
  @ViewChild("navigationToggle", { read: ElementRef })
  navigationToggle?: ElementRef<HTMLButtonElement>;
  api = inject(Api);
  router = inject(Router);
  loading = signal(true);
  busy = signal(false);
  loginError = signal(false);
  navOpen = signal(false);
  username = "";
  password = "";
  nav = [
    { key: "overview", path: "/" },
    ...[
      "services",
      "datasets",
      "criteria",
      "providers",
      "plans",
      "runs",
      "schedules",
      "users",
    ].map((key) => ({ key, path: "/" + key })),
  ];
  constructor() {
    this.api.restore().finally(() => this.loading.set(false));
  }
  openNavigation() {
    this.navOpen.set(true);
    requestAnimationFrame(() =>
      document.getElementById("navigation-close")?.focus(),
    );
  }
  @HostListener("document:keydown.escape")
  closeNavigation() {
    if (!this.navOpen()) return;
    this.navOpen.set(false);
    this.navigationToggle?.nativeElement.focus();
  }
  async login() {
    this.busy.set(true);
    this.loginError.set(false);
    try {
      this.api.accept(
        await this.api.request("/auth/login", "POST", {
          username: this.username,
          password: this.password,
        }),
      );
      this.password = "";
      await this.router.navigateByUrl("/");
    } catch {
      this.loginError.set(true);
    } finally {
      this.busy.set(false);
    }
  }
  async logout() {
    try {
      await this.api.request("/auth/logout", "POST");
      this.api.user.set(null);
      this.api.csrf = "";
      this.api.error.set("");
      this.navOpen.set(false);
    } catch (e) {
      this.api.fail(e);
    }
  }
}
