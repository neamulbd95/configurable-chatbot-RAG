import { Injectable, signal } from '@angular/core';

const STORAGE_KEY = 'ragchatbot.adminApiKey';

/** Holds the admin API key entered by the user for this browser, so it can
 * be attached to /admin/* requests (see AdminKeyInterceptor). Never sent
 * anywhere except this app's own backend calls; persisted only in
 * localStorage on the user's own machine. */
@Injectable({ providedIn: 'root' })
export class AdminAuthService {
  readonly apiKey = signal<string | null>(localStorage.getItem(STORAGE_KEY));

  setApiKey(key: string): void {
    const trimmed = key.trim();
    if (trimmed) {
      localStorage.setItem(STORAGE_KEY, trimmed);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
    this.apiKey.set(trimmed || null);
  }

  clear(): void {
    localStorage.removeItem(STORAGE_KEY);
    this.apiKey.set(null);
  }
}
