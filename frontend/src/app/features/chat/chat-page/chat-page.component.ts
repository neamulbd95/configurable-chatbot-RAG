import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChatService } from '../../../core/services/chat.service';
import { ChatSessionService } from '../../../core/services/chat-session.service';
import { ChatMessageView } from '../../../core/models/chat.models';
import { CardComponent } from '../../../shared/ui/card/card.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { MessageBubbleComponent } from '../message-bubble/message-bubble.component';
import { ChatInputComponent } from '../chat-input/chat-input.component';

@Component({
  selector: 'app-chat-page',
  standalone: true,
  imports: [CommonModule, CardComponent, ButtonComponent, MessageBubbleComponent, ChatInputComponent],
  templateUrl: './chat-page.component.html',
  styleUrl: './chat-page.component.scss',
})
export class ChatPageComponent {
  readonly messages = signal<ChatMessageView[]>([]);
  readonly sending = signal(false);

  constructor(
    private readonly chatService: ChatService,
    readonly session: ChatSessionService,
  ) {}

  onSend(text: string): void {
    const userMessage: ChatMessageView = { role: 'user', content: text };
    const pendingMessage: ChatMessageView = { role: 'assistant', content: '', pending: true };
    this.messages.update((current) => [...current, userMessage, pendingMessage]);
    this.sending.set(true);

    this.chatService
      .send({ message: text, session_id: this.session.sessionId() })
      .subscribe({
        next: (response) => {
          if (response.session_id) {
            this.session.setSessionId(response.session_id);
          }
          this.replacePending({
            role: 'assistant',
            content: response.answer,
            citations: response.citations,
            confidence: response.confidence,
            grounded: response.grounded,
          });
          this.sending.set(false);
        },
        error: (err) => {
          this.replacePending({
            role: 'assistant',
            content: 'Something went wrong.',
            error: err?.error?.detail ?? err?.message ?? 'Unknown error',
          });
          this.sending.set(false);
        },
      });
  }

  newSession(): void {
    this.session.reset();
    this.messages.set([]);
  }

  private replacePending(message: ChatMessageView): void {
    this.messages.update((current) => {
      const next = [...current];
      const idx = next.findIndex((m) => m.pending);
      if (idx >= 0) {
        next[idx] = message;
      } else {
        next.push(message);
      }
      return next;
    });
  }
}
