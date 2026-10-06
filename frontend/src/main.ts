import { bootstrapApplication } from "@angular/platform-browser";
import { provideRouter, withComponentInputBinding } from "@angular/router";
import { provideZonelessChangeDetection } from "@angular/core";
import { App } from "./app";
import { Home } from "./pages/home";
import { CatalogPage } from "./pages/catalog";
import { RunsPage } from "./pages/runs";
import { RunPage } from "./pages/run";
import { UsersPage } from "./pages/users";
bootstrapApplication(App, {
  providers: [
    provideZonelessChangeDetection(),
    provideRouter(
      [
        { path: "", component: Home },
        { path: "runs", component: RunsPage },
        { path: "runs/:id", component: RunPage },
        { path: "users", component: UsersPage },
        ...[
          "services",
          "datasets",
          "criteria",
          "providers",
          "plans",
          "schedules",
        ].map((path) => ({
          path,
          component: CatalogPage,
          data: { kind: path },
        })),
        { path: "**", redirectTo: "" },
      ],
      withComponentInputBinding(),
    ),
  ],
}).catch(console.error);
