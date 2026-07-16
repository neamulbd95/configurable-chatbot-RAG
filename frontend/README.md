# RAG Chatbot Frontend

Angular 18 (standalone components) frontend for the [ragchatbot](../README.md) API — a chat interface plus an admin panel for ingestion/reset/connectivity.

## Design system

There is no public Angular package for EY's Motif design system (only React-oriented/internal references were found — see the root README's build notes). Instead, `src/styles/_tokens.scss` defines an independent set of design tokens (color, type, spacing, shape) approximating Motif's visual language — EY-brand yellow/near-black, clean sans-serif, card-based layout — and `src/app/shared/ui/` implements a small component set (`mtf-button`, `mtf-card`, `mtf-badge`, `mtf-alert`, `mtf-spinner`, `mtf-confirm-dialog`) styled from those tokens. If you get access to an official Motif Angular library later, these are the components to swap.

## Prerequisites

- Node.js 20+ (this was built/tested against Node 20.0.0 with Angular CLI 18.2.21 — the Angular CLI's `latest` tag requires Node 22.22+/24.15+/26+, so pin `@angular/cli@18` if your Node is older)
- The backend running and reachable — see the root [README](../README.md)

## Configure the backend URL

`src/app/core/config/api-config.ts` defaults to `http://localhost:8000`. Change the factory value there if your backend runs elsewhere.

## Run

```bash
npm install
npx ng serve
```

Open `http://localhost:4200`. By default the backend only allows this origin via CORS (`CORS_ALLOWED_ORIGINS` in the backend's `.env`) — add your deployed frontend's origin there if you build for production and host it elsewhere.

- **Chat** (`/chat`): send messages, see grounded answers with citations/confidence, multi-turn session persisted in `localStorage`.
- **Admin** (`/admin`): source-DB connectivity check, trigger/poll ingestion jobs, reset the vector store (with a confirm dialog). If the backend has `ADMIN_API_KEY` set, enter it once in the Admin page — it's stored in `localStorage` and attached automatically to `/admin/*` requests only (see `core/interceptors/admin-key.interceptor.ts`).

## Build

```bash
npx ng build              # production build -> dist/frontend
npx ng build --configuration development
```

Both verified building cleanly as of this writing (production bundle ~84 kB transferred, well under budget).

## Known gaps

- No automated tests were written for the new feature/admin components (only the default `app.component.spec.ts` was kept in sync). Manual/API-level verification was done instead — see the root README's implementation status notes.
- Not visually verified in an actual rendered browser in this environment (no headless-browser tooling was available here) — verified instead at the network level: production and dev builds succeed, the dev server serves the correct app shell, and real CORS preflight + `/chat` + `/admin/*` requests against the live backend succeed with the expected response shapes. Open it in a real browser to confirm the visual/interaction layer before considering this done.
