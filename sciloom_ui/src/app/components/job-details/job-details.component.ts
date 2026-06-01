import { Component, inject, signal, computed, effect, OnInit, OnDestroy, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { JobService } from '../../services/job.service';
import { FileExplorerComponent } from '../file-explorer/file-explorer.component';
import { OCRPreviewComponent } from '../ocr-preview/ocr-preview.component';
import { ClaimsEditorComponent } from '../claims-editor/claims-editor.component';

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
    ClaimsEditorComponent,
    ButtonModule,
    TimelineModule,
    ProgressBarModule,
    TagModule,
    MessageModule
  ],
  templateUrl: './job-details.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class JobDetailsComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly jobService = inject(JobService);

  // Active Job ID
  jobId = signal<string>('');

  // Active tab selection in provisioned view
  activeTab = signal<'ocr' | 'files' | 'claims'>('ocr');

  // Currently selected stage in the horizontal timeline
  selectedStageName = signal<'PROVISIONING' | 'CLAIM_EXTRACTION' | 'CODE_EXECUTION' | 'CLAIM_REPLICATION' | 'DTREG_GENERATION'>('PROVISIONING');

  /**
   * Temporarily true after the user confirms an OCR retry, so the terminal
   * view is shown even though the job DB status is still PROVISIONED.
   * Clears automatically once the job's status returns to PROVISIONED
   * (i.e. the retry finished and the SSE stream ended).
   */
  isOcrRetrying = signal(false);

  // Track previous status to detect when retry finishes
  private _prevStatus = signal<string | undefined>(undefined);

  // Hardcoded timeline structure matching the 5 stages
  timelineStages: TimelineItem[] = [
    { name: 'PROVISIONING', label: '1. Provisioning', description: 'Setup sandbox & perform Gemini OCR' },
    { name: 'CLAIM_EXTRACTION', label: '2. Claim Extraction', description: 'Extract quantitative scientific claims' },
    { name: 'CODE_EXECUTION', label: '3. Code Execution', description: 'Configure running environment in Docker' },
    { name: 'CLAIM_REPLICATION', label: '4. Claim Replication', description: 'Replicate metric evidence via subagents' },
    { name: 'DTREG_GENERATION', label: '5. DTREG Gen', description: 'Generate JSON-LD artifact for Loom' }
  ];

  constructor() {
    // Effect: once OCR retry finishes (status flips back to PROVISIONED),
    // clear the retrying flag so the OCR preview re-appears with fresh data.
    effect(() => {
      const currentStatus = this.job()?.status;
      const prev = this._prevStatus();
      if (this.isOcrRetrying() && prev === 'PROVISIONING' && currentStatus === 'PROVISIONED') {
        this.isOcrRetrying.set(false);
      }
      this._prevStatus.set(currentStatus);

      // Auto-select active stage when status changes, if not already specified by query param
      const hasQueryParam = this.route.snapshot.queryParamMap.has('stage');
      if (currentStatus && !hasQueryParam && currentStatus !== prev) {
        const activeStage = this.mapStatusToStageName(currentStatus);
        if (activeStage) {
          this.selectedStageName.set(activeStage);
          this.router.navigate([], {
            relativeTo: this.route,
            queryParams: { stage: activeStage },
            queryParamsHandling: 'merge'
          });
        }
      }
    });
  }

  ngOnInit(): void {
    // Subscribe to route parameter changes
    this.route.paramMap.subscribe(params => {
      const id = params.get('id');
      if (id) {
        this.jobId.set(id);
        this.jobService.loadJobDetails(id);
      }
    });

    // Subscribe to query parameter changes to update active stage selection
    this.route.queryParamMap.subscribe(queryParams => {
      const stageParam = queryParams.get('stage');
      if (stageParam) {
        const validStages = ['PROVISIONING', 'CLAIM_EXTRACTION', 'CODE_EXECUTION', 'CLAIM_REPLICATION', 'DTREG_GENERATION'];
        if (validStages.includes(stageParam)) {
          this.selectedStageName.set(stageParam as any);
        }
      }
    });
  }

  ngOnDestroy(): void {
    this.jobService.disconnectLogsSse();
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

  onAdvanceToStage3(): void {
    this.jobService.advanceToStage3(this.jobId());
  }

  onClaimsSaved(): void {
    this.jobService.refreshClaims(this.jobId());
  }

  /** Called when the OCR preview confirms a retry — switch UI to terminal view. */
  onOcrRetryStarted(): void {
    this.isOcrRetrying.set(true);
    this._prevStatus.set('PROVISIONING');
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
      case 'CODE_EXECUTION':
      case 'CLAIM_REPLICATION':
      case 'DTREG_GENERATION':
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

  // Timeline selection action
  selectStage(stageName: 'PROVISIONING' | 'CLAIM_EXTRACTION' | 'CODE_EXECUTION' | 'CLAIM_REPLICATION' | 'DTREG_GENERATION'): void {
    this.selectedStageName.set(stageName);
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { stage: stageName },
      queryParamsHandling: 'merge'
    });
  }

  // Map job status string to a timeline stage name
  private mapStatusToStageName(status: string): 'PROVISIONING' | 'CLAIM_EXTRACTION' | 'CODE_EXECUTION' | 'CLAIM_REPLICATION' | 'DTREG_GENERATION' | null {
    switch (status) {
      case 'CREATED':
      case 'PROVISIONING':
      case 'PROVISIONED':
      case 'FAILED':
        return 'PROVISIONING';
      case 'CLAIM_EXTRACTION':
        return 'CLAIM_EXTRACTION';
      case 'CODE_EXECUTION':
        return 'CODE_EXECUTION';
      case 'CLAIM_REPLICATION':
        return 'CLAIM_REPLICATION';
      case 'DTREG_GENERATION':
      case 'COMPLETED':
        return 'DTREG_GENERATION';
      default:
        return null;
    }
  }

  getSelectedStageLabel(): string {
    const stage = this.timelineStages.find(s => s.name === this.selectedStageName());
    return stage ? stage.label : '';
  }

  getSelectedStageRunningDescription(): string {
    switch (this.selectedStageName()) {
      case 'CLAIM_EXTRACTION':
        return 'The Claim Extraction Agent (OpenCode) is currently scanning your research document markdown for quantitative evidence matrices. This can take a few minutes...';
      case 'CODE_EXECUTION':
        return 'The Code Execution Agent is configuring your docker isolation environment and installing project dependencies...';
      case 'CLAIM_REPLICATION':
        return 'Replication subagents are analyzing the research paper claims against the repository and executing verification scripts...';
      case 'DTREG_GENERATION':
        return 'Generating the final Loom DTREG JSON-LD metadata artifact with claim verification proofs...';
      default:
        return 'This stage execution is currently running inside the workspace sandbox.';
    }
  }

  getSelectedStageCompletedDescription(): string {
    switch (this.selectedStageName()) {
      case 'CLAIM_EXTRACTION':
        return 'Stage 2 Complete. Scientific quantitative claims have been extracted from the paper and linked to the sandbox environment.';
      case 'CODE_EXECUTION':
        return 'Stage 3 Complete. The repository execution environment was configured in Docker sandbox sbx-' + this.jobId() + ' successfully.';
      case 'CLAIM_REPLICATION':
        return 'Stage 4 Complete. All scientific claims have been verified and replicated against the linked source dataset.';
      case 'DTREG_GENERATION':
        return 'Stage 5 Complete. The Loom DTREG metadata artifact has been successfully generated and published.';
      default:
        return 'This stage has finished execution successfully.';
    }
  }
}

