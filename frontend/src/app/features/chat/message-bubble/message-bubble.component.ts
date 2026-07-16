import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChatMessageView } from '../../../core/models/chat.models';
import { BadgeComponent } from '../../../shared/ui/badge/badge.component';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';

@Component({
  selector: 'app-message-bubble',
  standalone: true,
  imports: [CommonModule, BadgeComponent, SpinnerComponent],
  templateUrl: './message-bubble.component.html',
  styleUrl: './message-bubble.component.scss',
})
export class MessageBubbleComponent {
  @Input({ required: true }) message!: ChatMessageView;

  confidenceTone(confidence: number): 'success' | 'warning' | 'danger' {
    if (confidence >= 0.8) return 'success';
    if (confidence >= 0.65) return 'warning';
    return 'danger';
  }
}
