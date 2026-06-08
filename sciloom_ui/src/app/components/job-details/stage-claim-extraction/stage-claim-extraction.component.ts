import { Component, inject, input, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { JobService } from '../../../services/job.service';
import { Job, JobStage, JobLog, Claim } from '../../../types/job.types';
import { ClaimsEditorComponent } from '../claims-editor/claims-editor.component';

@Component({
  selector: 'app-stage-claim-extraction',
  imports: [
    CommonModule,
    ClaimsEditorComponent
  ],
  template: `
    <!-- Stage 2: running -->
    @if (getStageStatus('CLAIM_EXTRACTION') === 'running') {
      <div class="space-y-6">
        <!-- Running header -->
        <div class="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
          <div class="flex items-center gap-3">
            <i class="pi pi-spin pi-spinner text-amber-500 text-2xl"></i>
            <div class="flex flex-col">
              <h3 class="text-sm font-bold text-slate-900">Running Claim Extraction</h3>
              <span class="text-xs text-slate-400 mt-0.5">The Claim Extraction Agent (OpenCode) is currently scanning your research document markdown for quantitative evidence matrices. This can take a few minutes...</span>
            </div>
          </div>
        </div>

        <!-- Log terminal -->
        <div class="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-2">
          <div class="flex items-center justify-between text-xs text-slate-500 font-semibold px-1">
            <span>Agent Log Stream</span>
            <span class="font-mono text-[10px]">sqlite-honker://sciloom.db</span>
          </div>
          <div class="bg-slate-900 border border-slate-950 rounded-xl p-4 h-[350px] overflow-y-auto font-mono text-[11px] leading-relaxed shadow-inner space-y-1.5 scrollbar-thin">
            @for (log of logs(); track $index) {
              <div class="flex items-start gap-2">
                <span class="text-slate-500 shrink-0 select-none">[{{ log.timestamp }}]</span>
                <span
                  class="shrink-0 font-bold uppercase select-none"
                  [class.text-emerald-400]="log.level === 'INFO'"
                  [class.text-amber-400]="log.level === 'WARN'"
                  [class.text-rose-400]="log.level === 'ERROR'"
                >
                  [{{ log.level }}]
                </span>
                <span class="text-slate-300 break-all">{{ log.message }}</span>
              </div>
            }
            @if (logs().length === 0) {
              <div class="text-slate-500 italic py-2">Waiting for agent logs...</div>
            }
          </div>
        </div>
      </div>
    }

    <!-- Stage 2: completed (human review/edit claims) -->
    @if (getStageStatus('CLAIM_EXTRACTION') === 'completed') {
      <div class="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
        <app-claims-editor
          [jobId]="jobId()"
          [claims]="claims()"
          (claimsSaved)="onClaimsSaved()"
          (advanceToStage3)="onAdvanceToStage3()"
        />
      </div>
    }

    <!-- Stage 2: failed -->
    @if (getStageStatus('CLAIM_EXTRACTION') === 'failed') {
      <div class="bg-white border border-slate-200 rounded-xl p-10 shadow-xs text-center space-y-4">
        <div class="w-14 h-14 rounded-full bg-rose-50 flex items-center justify-center text-rose-500 mx-auto border border-rose-100 shadow-xs">
          <i class="pi pi-exclamation-triangle text-xl"></i>
        </div>
        <div class="max-w-md mx-auto space-y-2">
          <h3 class="text-sm font-bold text-slate-900">Claim Extraction Failed</h3>
          <p class="text-xs text-rose-600 font-semibold leading-relaxed">
            The agent was unable to extract claims from the research paper.
          </p>
          @if (getErrorLog()) {
            <div class="bg-rose-50 border border-rose-200 rounded-lg p-3 text-xs font-mono text-rose-600 max-h-32 overflow-y-auto text-left">
              {{ getErrorLog() }}
            </div>
          }
          <div class="pt-2 flex justify-center gap-3">
            <button
              type="button"
              (click)="onRetry()"
              class="px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm hover:shadow-md transition-all cursor-pointer"
            >
              <i class="pi pi-refresh mr-1 text-[10px]"></i>
              Retry Extraction
            </button>
          </div>
        </div>
      </div>
    }

    <!-- Stage 2: pending -->
    @if (getStageStatus('CLAIM_EXTRACTION') === 'pending') {
      <div class="bg-white border border-slate-200 rounded-xl p-10 shadow-xs text-center space-y-4">
        <div class="w-14 h-14 rounded-full bg-slate-50 flex items-center justify-center text-slate-400 mx-auto border border-slate-100 shadow-xs">
          <i class="pi pi-clock text-xl"></i>
        </div>
        <div class="max-w-md mx-auto space-y-2">
          <h3 class="text-sm font-bold text-slate-900">Claim Extraction Pending</h3>
          <p class="text-xs text-slate-500 leading-relaxed">
            This stage will begin automatically after Stage 1 provisioning is completed successfully.
          </p>
        </div>
      </div>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class StageClaimExtractionComponent {
  private readonly jobService = inject(JobService);

  // Inputs
  jobId = input.required<string>();
  job = input<Job | null>(null);
  stages = input<JobStage[]>([]);
  logs = input<JobLog[]>([]);
  claims = input<Claim[]>([]);

  getStageStatus(stageName: string): 'completed' | 'running' | 'failed' | 'pending' {
    const stage = this.stages().find(s => s.stageName === stageName);
    return stage ? (stage.status as any) : 'pending';
  }

  getErrorLog(): string | null {
    const stage = this.stages().find(s => s.stageName === 'CLAIM_EXTRACTION');
    return stage?.errorLog ?? null;
  }

  onRetry(): void {
    // Retry Stage 2 claim extraction triggers the retry endpoint
    this.jobService.retryCurrentStage(this.jobId(), 'CLAIM_EXTRACTION');
  }

  onAdvanceToStage3(): void {
    this.jobService.advancePipeline(this.jobId(), 'CODE_EXECUTION');
  }

  onClaimsSaved(): void {
    this.jobService.refreshClaims(this.jobId());
  }
}
