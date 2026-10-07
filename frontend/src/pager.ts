import { Component, input, output } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { TranslatePipe } from "./i18n";

@Component({
  selector: "app-pager",
  standalone: true,
  imports: [MatButtonModule, TranslatePipe],
  template: `<div class="pagination">
    <span role="status">{{ "totalCount" | t }} {{ total() }}</span>
    <span>{{ total() ? offset() + 1 : 0 }}–{{ end() }} / {{ total() }}</span>
    <button
      mat-button
      type="button"
      (click)="change.emit(offset() - limit())"
      [disabled]="disabled() || offset() === 0"
    >
      {{ "previousPage" | t }}
    </button>
    <button
      mat-button
      type="button"
      (click)="change.emit(offset() + limit())"
      [disabled]="disabled() || end() >= total()"
    >
      {{ "nextPage" | t }}
    </button>
  </div>`,
})
export class Pager {
  total = input.required<number>();
  offset = input.required<number>();
  limit = input(25);
  disabled = input(false);
  change = output<number>();
  end() {
    return Math.min(this.offset() + this.limit(), this.total());
  }
}
