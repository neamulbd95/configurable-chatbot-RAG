import { InjectionToken } from '@angular/core';

/** Base URL of the ragchatbot FastAPI service. Override via the provider
 * in app.config.ts if deploying against a non-default backend. */
export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL', {
  providedIn: 'root',
  factory: () => 'http://localhost:8000',
});
