import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AdminAuthService } from '../services/admin-auth.service';

/** Attaches X-Admin-Api-Key to requests targeting /admin/* only — the
 * chat endpoint doesn't need it and shouldn't leak the key unnecessarily. */
export const adminKeyInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.includes('/admin/')) {
    return next(req);
  }

  const apiKey = inject(AdminAuthService).apiKey();
  if (!apiKey) {
    return next(req);
  }

  return next(req.clone({ setHeaders: { 'X-Admin-Api-Key': apiKey } }));
};
