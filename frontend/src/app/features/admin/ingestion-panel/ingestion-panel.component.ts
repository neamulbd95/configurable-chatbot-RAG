import { Component, OnDestroy, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription, interval, switchMap, takeWhile } from 'rxjs';
import { AdminService } from '../../../core/services/admin.service';
import { IngestJobResponse } from '../../../core/models/admin.models';
import { CardComponent } from '../../../shared/ui/card/card.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { BadgeComponent, BadgeTone } from '../../../shared/ui/badge/badge.component';
import { AlertComponent } from '../../../shared/ui/alert/alert.component';

const POLL_INTERVAL_MS = 1500;
const ACTIVE_STATUSES = new Set(['pending', 'running']);

@Component({
  selector: 'app-ingestion-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, CardComponent, ButtonComponent, BadgeComponent, AlertComponent],
  templateUrl: './ingestion-panel.component.html',
  styleUrl: './ingestion-panel.component.scss',
})
export class IngestionPanelComponent implements OnDestroy {
  tablesInput = '';
  readonly job = signal<IngestJobResponse | null>(null);
  readonly starting = signal(false);
  readonly requestError = signal<string | null>(null);

  private pollSub: Subscription | null = null;

  constructor(private readonly adminService: AdminService) {}

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
  }

  statusTone(status: string): BadgeTone {
    switch (status) {
      case 'succeeded':
        return 'success';
      case 'failed':
        return 'danger';
      case 'running':
        return 'info';
      default:
        return 'neutral';
    }
  }

  start(): void {
    const tables = this.parseTables();
    this.starting.set(true);
    this.requestError.set(null);
    this.job.set(null);
    this.pollSub?.unsubscribe();

    this.adminService.startIngestion({ tables }).subscribe({
      next: (started) => {
        this.starting.set(false);
        this.pollJob(started.job_id);
      },
      error: (err) => {
        this.starting.set(false);
        this.requestError.set(err?.error?.detail ?? err?.message ?? 'Failed to start ingestion');
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

  private pollJob(jobId: string): void {
    this.pollSub = interval(POLL_INTERVAL_MS)
      .pipe(
        switchMap(() => this.adminService.getIngestionJob(jobId)),
        takeWhile((job) => ACTIVE_STATUSES.has(job.status), true),
      )
      .subscribe({
        next: (job) => this.job.set(job),
        error: (err) => this.requestError.set(err?.error?.detail ?? err?.message ?? 'Status check failed'),
      });
  }
}
