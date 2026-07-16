import { Component, Input } from '@angular/core';

@Component({
  selector: 'mtf-card',
  standalone: true,
  template: `
    <div class="mtf-card" [class.mtf-card--flush]="flush">
      <ng-content></ng-content>
    </div>
  `,
  styleUrl: './card.component.scss',
})
export class CardComponent {
  @Input() flush = false;
}
