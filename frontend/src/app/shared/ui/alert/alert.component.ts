import { Component, Input } from '@angular/core';

export type AlertTone = 'info' | 'success' | 'danger' | 'warning';

@Component({
  selector: 'mtf-alert',
  standalone: true,
  template: `
    <div class="mtf-alert" [class]="'mtf-alert--' + tone" role="alert">
      <ng-content></ng-content>
    </div>
  `,
  styleUrl: './alert.component.scss',
})
export class AlertComponent {
  @Input() tone: AlertTone = 'info';
}
