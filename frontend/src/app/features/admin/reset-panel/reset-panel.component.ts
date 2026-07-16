import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AdminService } from '../../../core/services/admin.service';
import { ResetResponse } from '../../../core/models/admin.models';
import { CardComponent } from '../../../shared/ui/card/card.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { AlertComponent } from '../../../shared/ui/alert/alert.component';
import { ConfirmDialogComponent } from '../../../shared/ui/confirm-dialog/confirm-dialog.component';

@Component({
  selector: 'app-reset-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, CardComponent, ButtonComponent, AlertComponent, ConfirmDialogComponent],
  templateUrl: './reset-panel.component.html',
  styleUrl: './reset-panel.component.scss',
})
export class ResetPanelComponent {
  tablesInput = '';
  readonly confirmOpen = signal(false);
  readonly resetting = signal(false);
  readonly requestError = signal<string | null>(null);
  readonly result = signal<ResetResponse | null>(null);

  constructor(private readonly adminService: AdminService) {}

  openConfirm(): void {
    this.requestError.set(null);
    this.result.set(null);
    this.confirmOpen.set(true);
  }

  cancelConfirm(): void {
    this.confirmOpen.set(false);
  }

  confirmReset(): void {
    const tables = this.parseTables();
    this.resetting.set(true);

    this.adminService.resetVectorStore({ tables, confirm: true }).subscribe({
      next: (result) => {
        this.result.set(result);
        this.resetting.set(false);
        this.confirmOpen.set(false);
      },
      error: (err) => {
        this.requestError.set(err?.error?.detail ?? err?.message ?? 'Reset failed');
        this.resetting.set(false);
        this.confirmOpen.set(false);
      },
    });
  }

  private parseTables(): string[] | null {
    const names = this.tablesInput
      .split(',')
      .map((name) => name.trim())
      .filter(Boolean);
    return names.length ? names : null;
  }
}
