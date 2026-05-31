import { Component, inject, signal, computed, OnInit, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { JobService } from '../../services/job.service';
import { FileExplorerComponent } from '../file-explorer/file-explorer.component';
import { OCRPreviewComponent } from '../ocr-preview/ocr-preview.component';

// PrimeNG Imports
import { ButtonModule } from 'primeng/button';
import { TimelineModule } from 'primeng/timeline';
import { ProgressBarModule } from 'primeng/progressbar';
import { TagModule } from 'primeng/tag';
import { MessageModule } from 'primeng/message';

interface TimelineItem {
  name: 'PROVISIONING' | 'CLAIM_EXTRACTION' | 'CODE_EXECUTION' | 'CLAIM_REPLICATION' | 'DTREG_GENERATION';
  label: string;
  description: string;
}

@Component({
  selector: 'app-job-details',
  imports: [
    CommonModule,
    RouterLink,
    FileExplorerComponent,
    OCRPreviewComponent,
    ButtonModule,
    TimelineModule,
    ProgressBarModule,
    TagModule,
    MessageModule
  ],
  templateUrl: './job-details.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class JobDetailsComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly jobService = inject(JobService);

  // Active Job ID
  jobId = signal<string>('');

  // Active tab selection in provisioned view
  activeTab = signal<'ocr' | 'files' | 'claims'>('ocr');

  // Hardcoded timeline structure matching the 5 stages
  timelineStages: TimelineItem[] = [
    { name: 'PROVISIONING', label: '1. Provisioning', description: 'Setup sandbox & perform Gemini OCR' },
    { name: 'CLAIM_EXTRACTION', label: '2. Claim Extraction', description: 'Extract quantitative scientific claims' },
    { name: 'CODE_EXECUTION', label: '3. Code Execution', description: 'Configure running environment in Docker' },
    { name: 'CLAIM_REPLICATION', label: '4. Claim Replication', description: 'Replicate metric evidence via subagents' },
    { name: 'DTREG_GENERATION', label: '5. DTREG Gen', description: 'Generate JSON-LD artifact for Loom' }
  ];

  ngOnInit(): void {
    // Subscribe to route parameter changes
    this.route.paramMap.subscribe(params => {
      const id = params.get('id');
      if (id) {
        this.jobId.set(id);
      }
    });
  }

  // Computed properties tied to JobService
  job = computed(() => this.jobService.getJobById(this.jobId())());
  stages = computed(() => this.jobService.getStagesForJob(this.jobId())());
  claims = computed(() => this.jobService.getClaimsForJob(this.jobId())());
  logs = computed(() => this.jobService.getLogsForJob(this.jobId())());
  ocrMarkdown = computed(() => this.jobService.getSimulatedOcrMarkdown(this.jobId()));
  repoFiles = computed(() => this.jobService.getSimulatedRepoFiles(this.jobId()));

  // Simulated Stage 1 progress metrics
  progressPercent = computed(() => {
    const jobVal = this.job();
    if (!jobVal) return 0;
    if (jobVal.status === 'CREATED') return 5;
    if (jobVal.status === 'FAILED') return 100;
    if (jobVal.status === 'PROVISIONED' || jobVal.status === 'CLAIM_EXTRACTION' || jobVal.status === 'COMPLETED') return 100;
    
    // Increment based on the number of logs received in the mock stream
    const logsList = this.logs();
    return Math.min(Math.round((logsList.length / 9) * 100), 98);
  });

  activeStepName = computed(() => {
    const logsList = this.logs();
    if (logsList.length <= 2) return 'Step 1/3: Provisioning workspace directories...';
    if (logsList.length <= 5) return 'Step 2/3: Unzipping files and cloning repo...';
    return 'Step 3/3: Running Gemini Vision OCR to convert paper to markdown...';
  });

  // Action methods
  onRetry(): void {
    this.jobService.retryJobStage1(this.jobId());
  }

  onAdvanceToStage2(): void {
    this.jobService.advanceToStage2(this.jobId());
  }

  selectTab(tab: 'ocr' | 'files' | 'claims'): void {
    this.activeTab.set(tab);
  }

  // --- Helper state builders for timeline stages ---
  getStageStatus(stageName: string): 'completed' | 'running' | 'failed' | 'pending' {
    const stage = this.stages().find(s => s.stageName === stageName);
    return stage ? (stage.status as any) : 'pending';
  }

  getStageIcon(stageName: string): string {
    const status = this.getStageStatus(stageName);
    switch (status) {
      case 'completed':
        return 'pi pi-check-circle text-emerald-600';
      case 'running':
        return 'pi pi-spin pi-spinner text-indigo-600';
      case 'failed':
        return 'pi pi-exclamation-triangle text-rose-500';
      default:
        return 'pi pi-circle text-slate-300';
    }
  }

  getStatusClass(stageName: string): string {
    const status = this.getStageStatus(stageName);
    switch (status) {
      case 'completed':
        return 'text-slate-800 font-semibold';
      case 'running':
        return 'text-indigo-600 font-semibold';
      case 'failed':
        return 'text-rose-600 font-semibold';
      default:
        return 'text-slate-400 font-normal';
    }
  }

  getStatusBadgeSeverity(status?: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' {
    switch (status) {
      case 'PROVISIONED':
      case 'COMPLETED':
        return 'success';
      case 'PROVISIONING':
      case 'CREATED':
        return 'info';
      case 'CLAIM_EXTRACTION':
      case 'RUNNING':
        return 'warn';
      case 'FAILED':
        return 'danger';
      default:
        return 'secondary';
    }
  }

  formatDate(dateString?: string): string {
    if (!dateString) return '';
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }
}
