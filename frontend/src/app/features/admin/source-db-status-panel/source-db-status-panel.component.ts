import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AdminService } from '../../../core/services/admin.service';
import { SourceDbStatusResponse } from '../../../core/models/admin.models';
import { CardComponent } from '../../../shared/ui/card/card.component';
import { BadgeComponent } from '../../../shared/ui/badge/badge.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { AlertComponent } from '../../../shared/ui/alert/alert.component';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';

@Component({
  selector: 'app-source-db-status-panel',
  standalone: true,
  imports: [CommonModule, CardComponent, BadgeComponent, ButtonComponent, AlertComponent, SpinnerComponent],
  templateUrl: './source-db-status-panel.component.html',
  styleUrl: './source-db-status-panel.component.scss',
})
export class SourceDbStatusPanelComponent implements OnInit {
  readonly status = signal<SourceDbStatusResponse | null>(null);
  readonly loading = signal(false);
  readonly requestError = signal<string | null>(null);

  constructor(private readonly adminService: AdminService) {}

  ngOnInit(): void {
    this.refresh();
  }

  refresh(): void {
    this.loading.set(true);
    this.requestError.set(null);
    this.adminService.sourceDbStatus().subscribe({
      next: (status) => {
        this.status.set(status);
        this.loading.set(false);
      },
      error: (err) => {
        this.requestError.set(err?.error?.detail ?? err?.message ?? 'Request failed');
        this.loading.set(false);
      },
    });
  }
}
