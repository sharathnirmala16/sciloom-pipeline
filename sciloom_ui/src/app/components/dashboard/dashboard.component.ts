import { Component, inject, signal, computed, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { JobService } from '../../services/job.service';
import { JobFormComponent } from '../job-form/job-form.component';
import { AppHeaderComponent } from '../app-header/app-header.component';

// PrimeNG Imports
import { TableModule } from 'primeng/table';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { DialogModule } from 'primeng/dialog';
import { TagModule } from 'primeng/tag';

@Component({
  selector: 'app-dashboard',
  imports: [
    CommonModule,
    RouterLink,
    AppHeaderComponent,
    JobFormComponent,
    TableModule,
    ButtonModule,
    InputTextModule,
    DialogModule,
    TagModule
  ],
  templateUrl: './dashboard.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DashboardComponent {
  private readonly jobService = inject(JobService);
  private readonly router = inject(Router);

  // Modal visibility
  showSubmitDialog = signal(false);

  // Search filter
  searchText = signal('');

  // Statistics summaries (derived using computed signals)
  totalJobs = computed(() => this.jobService.jobs().length);
  
  runningSetups = computed(() => 
    this.jobService.jobs().filter(j => j.status === 'PROVISIONING' || j.status === 'CREATED').length
  );
  
  readyJobs = computed(() => 
    this.jobService.jobs().filter(j => j.status === 'PROVISIONED').length
  );
  
  failedJobs = computed(() => 
    this.jobService.jobs().filter(j => j.status === 'FAILED').length
  );

  // Filtered jobs array based on search input
  filteredJobs = computed(() => {
    const query = this.searchText().toLowerCase().trim();
    const list = this.jobService.jobs();
    if (!query) return list;
    return list.filter(j => 
      j.title.toLowerCase().includes(query) || 
      j.id.toLowerCase().includes(query)
    );
  });

  // Action methods
  openSubmitDialog(): void {
    this.showSubmitDialog.set(true);
  }

  closeSubmitDialog(): void {
    this.showSubmitDialog.set(false);
  }

  onJobCreated(jobId: string): void {
    this.closeSubmitDialog();
    this.router.navigate(['/job', jobId]);
  }

  onDelete(jobId: string, event: Event): void {
    event.stopPropagation(); // stop row selection click
    if (confirm('Are you sure you want to delete this job? All logs, claims, and files will be permanently erased.')) {
      this.jobService.deleteJob(jobId);
    }
  }

  onSearchChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.searchText.set(input.value);
  }

  // --- Badge styling maps ---
  getStatusSeverity(status: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' {
    switch (status) {
      case 'PROVISIONED':
        return 'success';
      case 'PROVISIONING':
      case 'CREATED':
        return 'info';
      case 'CLAIM_EXTRACTION':
      case 'RUNNING':
        return 'warn';
      case 'FAILED':
        return 'danger';
      case 'COMPLETED':
        return 'success';
      default:
        return 'secondary';
    }
  }

  formatDate(dateString: string): string {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }
}
