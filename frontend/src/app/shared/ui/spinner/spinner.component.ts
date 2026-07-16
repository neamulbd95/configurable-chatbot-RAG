import { Component, Input } from '@angular/core';

@Component({
  selector: 'mtf-spinner',
  standalone: true,
  template: `<span class="mtf-spinner" [style.width.px]="size" [style.height.px]="size" role="status" aria-label="Loading"></span>`,
  styleUrl: './spinner.component.scss',
})
export class SpinnerComponent {
  @Input() size = 20;
}
