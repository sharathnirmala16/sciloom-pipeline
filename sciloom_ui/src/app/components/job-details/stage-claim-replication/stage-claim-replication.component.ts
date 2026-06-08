import { Component, inject, input, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { JobService } from '../../../services/job.service';
import { Job, JobStage } from '../../../types/job.types';

@Component({
  selector: 'app-stage-claim-replication',
  imports: [
    CommonModule,
    RouterLink
  ],
  template: `
    <!-- Stage Status: running -->
    @if (getStageStatus('CLAIM_REPLICATION') === 'running') {
      <div class="bg-white border border-slate-200 rounded-xl p-10 shadow-xs text-center space-y-4">
        <div class="w-14 h-14 rounded-full bg-amber-50 flex items-center justify-center text-amber-500 mx-auto border border-amber-100 shadow-xs">
          <i class="pi pi-spin pi-spinner text-xl"></i>
        </div>
        <div class="max-w-md mx-auto space-y-2">
          <h3 class="text-sm font-bold text-slate-900">Running 4. Claim Replication</h3>
          <p class="text-xs text-slate-500 leading-relaxed">
            Replication subagents are analyzing the research paper claims against the repository and executing verification scripts...
          </p>
          <div class="pt-4 flex justify-center gap-3">
            <button 
              type="button"
              (click)="onRetry()"
              class="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-xs transition-all cursor-pointer flex items-center gap-1.5"
            >
              <i class="pi pi-refresh text-[10px]"></i>
              Sync Sandbox State
            </button>
            <a 
              routerLink="/dashboard" 
              class="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 border border-slate-200 bg-white rounded-lg transition-all"
            >
              Return to Dashboard
            </a>
          </div>
        </div>
      </div>
    }

    <!-- Stage Status: completed -->
    @if (getStageStatus('CLAIM_REPLICATION') === 'completed') {
      <div class="bg-white border border-slate-200 rounded-xl p-10 shadow-xs text-center space-y-4">
        <div class="w-14 h-14 rounded-full bg-emerald-50 flex items-center justify-center text-emerald-500 mx-auto border border-emerald-100 shadow-xs">
          <i class="pi pi-check-circle text-2xl text-emerald-600"></i>
        </div>
        <div class="max-w-md mx-auto space-y-4">
          <div class="space-y-1">
            <h3 class="text-sm font-bold text-slate-900">4. Claim Replication Completed</h3>
            <p class="text-xs text-slate-500 leading-relaxed">
              Stage 4 Complete. All scientific claims have been verified and replicated against the linked source dataset.
            </p>
          </div>
          <div class="pt-2 flex justify-center">
            <button
              type="button"
              (click)="onAdvanceToStage5()"
              class="px-5 py-2.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm hover:shadow-md transition-all cursor-pointer flex items-center gap-2"
            >
              <i class="pi pi-arrow-right text-[10px]"></i>
              Advance to Stage 5: DTREG Gen
            </button>
          </div>
        </div>
      </div>
    }

    <!-- Stage Status: failed -->
    @if (getStageStatus('CLAIM_REPLICATION') === 'failed') {
      <div class="bg-white border border-slate-200 rounded-xl p-10 shadow-xs text-center space-y-4">
        <div class="w-14 h-14 rounded-full bg-rose-50 flex items-center justify-center text-rose-500 mx-auto border border-rose-100 shadow-xs">
          <i class="pi pi-exclamation-triangle text-xl"></i>
        </div>
        <div class="max-w-md mx-auto space-y-2">
          <h3 class="text-sm font-bold text-slate-900">4. Claim Replication Failed</h3>
          <p class="text-xs text-slate-500 leading-relaxed font-semibold text-rose-600">
            An error occurred during stage execution inside the sandbox runner.
          </p>
          @if (getErrorLog()) {
            <div class="bg-rose-50 border border-rose-200 rounded-lg p-3 text-xs font-mono text-rose-600 max-h-32 overflow-y-auto text-left">
              {{ getErrorLog() }}
            </div>
          }
          <div class="pt-2 flex justify-center">
            <button
              type="button"
              (click)="onRetry()"
              class="px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm hover:shadow-md transition-all cursor-pointer"
            >
              <i class="pi pi-refresh mr-1 text-[10px]"></i>
              Retry Replication
            </button>
          </div>
        </div>
      </div>
    }

    <!-- Stage Status: pending -->
    @if (getStageStatus('CLAIM_REPLICATION') === 'pending') {
      <div class="bg-white border border-slate-200 rounded-xl p-10 shadow-xs text-center space-y-4">
        <div class="w-14 h-14 rounded-full bg-slate-50 flex items-center justify-center text-slate-400 mx-auto border border-slate-100 shadow-xs">
          <i class="pi pi-clock text-xl"></i>
        </div>
        <div class="max-w-md mx-auto space-y-2">
          <h3 class="text-sm font-bold text-slate-900">4. Claim Replication Pending</h3>
          <p class="text-xs text-slate-500 leading-relaxed">
            This stage will begin automatically after the previous stages are completed successfully.
          </p>
        </div>
      </div>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class StageClaimReplicationComponent {
  private readonly jobService = inject(JobService);

  // Inputs
  jobId = input.required<string>();
  job = input<Job | null>(null);
  stages = input<JobStage[]>([]);

  getStageStatus(stageName: string): 'completed' | 'running' | 'failed' | 'pending' {
    const stage = this.stages().find(s => s.stageName === stageName);
    return stage ? (stage.status as any) : 'pending';
  }

  getErrorLog(): string | null {
    const stage = this.stages().find(s => s.stageName === 'CLAIM_REPLICATION');
    return stage?.errorLog ?? null;
  }

  onRetry(): void {
    this.jobService.retryPipelineStage(this.jobId(), 'CLAIM_REPLICATION');
  }

  onAdvanceToStage5(): void {
    this.jobService.advancePipeline(this.jobId(), 'DTREG_GENERATION');
  }
}
