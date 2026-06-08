import { Component, inject, signal, computed, effect, OnInit, OnDestroy, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { JobService } from '../../services/job.service';

// Child Stage Components
import { StageProvisioningComponent } from './stage-provisioning/stage-provisioning.component';
import { StageClaimExtractionComponent } from './stage-claim-extraction/stage-claim-extraction.component';
import { StageCodeExecutionComponent } from './stage-code-execution/stage-code-execution.component';
import { StageClaimReplicationComponent } from './stage-claim-replication/stage-claim-replication.component';
import { StageDtregGenerationComponent } from './stage-dtreg-generation/stage-dtreg-generation.component';

// PrimeNG Imports
import { TagModule } from 'primeng/tag';

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
    StageProvisioningComponent,
    StageClaimExtractionComponent,
    StageCodeExecutionComponent,
    StageClaimReplicationComponent,
    StageDtregGenerationComponent,
    TagModule
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

  // Currently selected stage in the horizontal timeline
  selectedStageName = signal<'PROVISIONING' | 'CLAIM_EXTRACTION' | 'CODE_EXECUTION' | 'CLAIM_REPLICATION' | 'DTREG_GENERATION'>('PROVISIONING');

  // Track previous status to detect when status changes
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
    effect(() => {
      const currentStatus = this.job()?.status;
      const prev = this._prevStatus();
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
  codeExecutionStage = computed(() => this.stages().find(s => s.stageName === 'CODE_EXECUTION') || null);

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
        return 'PROVISIONING';
      case 'FAILED':
        return this.job()?.currentStage || 'PROVISIONING';
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
}

