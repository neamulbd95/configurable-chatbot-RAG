import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AdminAuthService } from '../../../core/services/admin-auth.service';
import { CardComponent } from '../../../shared/ui/card/card.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { SourceDbStatusPanelComponent } from '../source-db-status-panel/source-db-status-panel.component';
import { IngestionPanelComponent } from '../ingestion-panel/ingestion-panel.component';
import { ResetPanelComponent } from '../reset-panel/reset-panel.component';

@Component({
  selector: 'app-admin-page',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    CardComponent,
    ButtonComponent,
    SourceDbStatusPanelComponent,
    IngestionPanelComponent,
    ResetPanelComponent,
  ],
  templateUrl: './admin-page.component.html',
  styleUrl: './admin-page.component.scss',
})
export class AdminPageComponent {
  keyInput = '';
  readonly editingKey = signal(false);

  constructor(readonly auth: AdminAuthService) {}

  saveKey(): void {
    this.auth.setApiKey(this.keyInput);
    this.keyInput = '';
    this.editingKey.set(false);
  }

  clearKey(): void {
    this.auth.clear();
  }
}
