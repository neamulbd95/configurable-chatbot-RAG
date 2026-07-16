import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'chat', pathMatch: 'full' },
  {
    path: 'chat',
    loadComponent: () =>
      import('./features/chat/chat-page/chat-page.component').then((m) => m.ChatPageComponent),
  },
  {
    path: 'admin',
    loadComponent: () =>
      import('./features/admin/admin-page/admin-page.component').then((m) => m.AdminPageComponent),
  },
  { path: '**', redirectTo: 'chat' },
];
