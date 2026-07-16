import { Component, EventEmitter, Input, Output } from '@angular/core';
import { ButtonComponent } from '../button/button.component';

@Component({
  selector: 'mtf-confirm-dialog',
  standalone: true,
  imports: [ButtonComponent],
  template: `
    <div class="mtf-confirm-backdrop" (click)="cancel.emit()">
      <div class="mtf-confirm" role="alertdialog" aria-modal="true" (click)="$event.stopPropagation()">
        <h3>{{ title }}</h3>
        <p>
          <ng-content></ng-content>
        </p>
        <div class="mtf-confirm__actions">
          <mtf-button variant="secondary" (click)="cancel.emit()">{{ cancelLabel }}</mtf-button>
          <mtf-button variant="danger" [loading]="loading" (click)="confirm.emit()">{{ confirmLabel }}</mtf-button>
        </div>
      </div>
    </div>
  `,
  styleUrl: './confirm-dialog.component.scss',
})
export class ConfirmDialogComponent {
  @Input() title = 'Are you sure?';
  @Input() confirmLabel = 'Confirm';
  @Input() cancelLabel = 'Cancel';
  @Input() loading = false;
  @Output() confirm = new EventEmitter<void>();
  @Output() cancel = new EventEmitter<void>();
}
