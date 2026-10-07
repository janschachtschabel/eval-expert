import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { TranslatePipe } from "./i18n";
export const UI = [
  CommonModule,
  FormsModule,
  MatButtonModule,
  MatFormFieldModule,
  MatInputModule,
  MatSelectModule,
  MatCheckboxModule,
  MatProgressBarModule,
  TranslatePipe,
];
export function pretty(value: unknown) {
  return JSON.stringify(value, null, 2);
}
export function percent(value: number | null | undefined) {
  return value === null || value === undefined
    ? "—"
    : new Intl.NumberFormat("de-DE", {
        style: "percent",
        maximumFractionDigits: 1,
      }).format(value);
}
