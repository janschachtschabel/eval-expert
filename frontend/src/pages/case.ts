import { Component, inject } from "@angular/core";
import { MAT_DIALOG_DATA, MatDialogModule } from "@angular/material/dialog";
import { UI, pretty, percent } from "../ui";
@Component({
  standalone: true,
  imports: [...UI, MatDialogModule],
  template: ` <h2 mat-dialog-title>
      {{ "caseTitle" | t }} {{ data["case_id"] }}
    </h2>
    <mat-dialog-content>
      <span class="badge" [class.amber]="data['status'] !== 'success'">{{
        data["status"] | t
      }}</span>
      @if (data["reused_response"]) {
        <p>{{ "savedResponses" | t }}</p>
      }
      @if (data["error"]) {
        <p class="error">{{ data["error"] }}</p>
      }
      @if (data["status"] === "field_error") {
        <h3>{{ "fieldErrors" | t }}</h3>
        <pre>{{ pretty(data["field_errors"]) }}</pre>
      }
      <div class="case-json-grid">
        @for (key of ["input", "output", "reference"]; track key) {
          <section>
            <h3>
              {{
                (key === "output"
                  ? "response"
                  : key === "reference"
                    ? "gold"
                    : key
                ) | t
              }}
            </h3>
            <pre>{{ pretty(data[key]) }}</pre>
          </section>
        }
      </div>
      <h3>{{ "verdicts" | t }}</h3>
      @if (!data["judges"]?.length) {
        <p>{{ "noJudges" | t }}</p>
      }
      @for (verdict of data["judges"]; track $index) {
        <article class="surface-subtle">
          <h4>{{ verdict["name"] }}</h4>
          @if (verdict["status"] === "success") {
            <p>
              <strong>{{ pct(verdict["score"]) }}</strong> ·
              {{ (verdict["passed"] ? "passed" : "notPassed") | t }}
            </p>
            <p>{{ verdict["reason"] }}</p>
            <details>
              <summary>{{ "snapshot" | t }}</summary>
              <pre>{{ pretty(verdict) }}</pre>
            </details>
            @if (!verdict["source_supplied"]) {
              <span class="badge amber">{{ "sourceMissing" | t }}</span>
            }
          } @else {
            <p class="error">{{ "judgeError" | t }} · {{ verdict["error"] }}</p>
          }
        </article>
      }</mat-dialog-content
    ><mat-dialog-actions align="end"
      ><button mat-button mat-dialog-close>
        {{ "close" | t }}
      </button></mat-dialog-actions
    >`,
})
export class CaseDialog {
  data = inject(MAT_DIALOG_DATA);
  pretty = pretty;
  pct = percent;
}
