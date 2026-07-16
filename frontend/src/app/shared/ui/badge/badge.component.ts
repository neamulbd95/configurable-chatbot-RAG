import { Component, Input } from '@angular/core';

export type BadgeTone = 'neutral' | 'success' | 'danger' | 'warning' | 'info' | 'brand';

@Component({
  selector: 'mtf-badge',
  standalone: true,
  template: `
    <span class="mtf-badge" [class]="'mtf-badge--' + tone">
      <ng-content></ng-content>
    </span>
  `,
  styleUrl: './badge.component.scss',
})
export class BadgeComponent {
  @Input() tone: BadgeTone = 'neutral';
}
