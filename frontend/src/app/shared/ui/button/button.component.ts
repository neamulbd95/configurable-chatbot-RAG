import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';

@Component({
  selector: 'mtf-button',
  standalone: true,
  imports: [CommonModule],
  template: `
    <button
      class="mtf-button"
      [class]="'mtf-button--' + variant"
      [type]="type"
      [disabled]="disabled || loading"
    >
      <span class="mtf-button__spinner" *ngIf="loading" aria-hidden="true"></span>
      <ng-content></ng-content>
    </button>
  `,
  styleUrl: './button.component.scss',
})
export class ButtonComponent {
  @Input() variant: ButtonVariant = 'primary';
  @Input() type: 'button' | 'submit' = 'button';
  @Input() disabled = false;
  @Input() loading = false;
}
