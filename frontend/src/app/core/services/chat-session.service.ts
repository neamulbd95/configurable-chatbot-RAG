import { Injectable, signal } from '@angular/core';

const STORAGE_KEY = 'ragchatbot.sessionId';

/** Persists the chat session_id returned by POST /chat so multi-turn
 * context (FR-6.11) survives a page reload. */
@Injectable({ providedIn: 'root' })
export class ChatSessionService {
  readonly sessionId = signal<string | null>(localStorage.getItem(STORAGE_KEY));

  setSessionId(id: string): void {
    localStorage.setItem(STORAGE_KEY, id);
    this.sessionId.set(id);
  }

  reset(): void {
    localStorage.removeItem(STORAGE_KEY);
    this.sessionId.set(null);
  }
}
