import { Component, inject, signal, computed, effect, input, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { JobService } from '../../../services/job.service';
import { Job, JobStage, JobLog, Claim } from '../../../types/job.types';
import { OCRPreviewComponent } from '../ocr-preview/ocr-preview.component';
import { FileExplorerComponent } from '../file-explorer/file-explorer.component';

// PrimeNG
import { ButtonModule } from 'primeng/button';
import { ProgressBarModule } from 'primeng/progressbar';
import { TagModule } from 'primeng/tag';

@Component({
  selector: 'app-stage-provisioning',
  imports: [
    CommonModule,
    OCRPreviewComponent,
    FileExplorerComponent,
    ButtonModule,
    ProgressBarModule,
    TagModule
  ],
  template: `
    <!-- ================= CASE 1: PROVISIONING / Setup In Progress ================= -->
    @if (getStageStatus('PROVISIONING') === 'running' || getStageStatus('PROVISIONING') === 'pending' || isOcrRetrying()) {
      <div class="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-6">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <i [class]="isOcrRetrying() ? 'pi pi-spin pi-refresh text-amber-500 text-2xl' : 'pi pi-spin pi-spinner text-indigo-600 text-2xl'"></i>
            <div class="flex flex-col">
              @if (isOcrRetrying()) {
                <h3 class="text-sm font-bold text-slate-900">OCR Re-extraction in Progress</h3>
                <span class="text-xs text-slate-400 mt-0.5">Re-running Gemini Vision OCR on all pages of the paper PDF…</span>
              } @else {
                <h3 class="text-sm font-bold text-slate-900">Provisioning Workspace Environment</h3>
                <span class="text-xs text-slate-400 mt-0.5">{{ activeStepName() }}</span>
              }
            </div>
          </div>
          @if (!isOcrRetrying()) {
            <span class="text-xs font-bold text-indigo-600 bg-indigo-50 border border-indigo-100 px-2.5 py-1 rounded-full">
              {{ progressPercent() }}%
            </span>
          }
        </div>

        <!-- Progress Bar -->
        @if (!isOcrRetrying()) {
          <p-progressBar 
            [value]="progressPercent()" 
            [showValue]="false"
            styleClass="h-2 rounded-full overflow-hidden bg-slate-100"
          />
        }

        <!-- Simulated Terminal Log Stream -->
        <div class="space-y-2">
          <div class="flex items-center justify-between text-xs text-slate-500 font-semibold px-1">
            <span>Orchestrator Logs</span>
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
              <div class="text-slate-500 italic py-2">Waiting for logs to initialize...</div>
            }
          </div>
        </div>
      </div>
    }

    <!-- ================= CASE 2: PROVISIONED (Stage 1 Complete) ================= -->
    @if (getStageStatus('PROVISIONING') === 'completed' && !isOcrRetrying()) {
      <div class="space-y-6">
        
        <!-- Success banner -->
        <div class="bg-emerald-50/50 border border-emerald-100 rounded-xl p-4 flex items-center gap-3">
          <div class="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 shadow-xs">
            <i class="pi pi-check text-sm font-bold"></i>
          </div>
          <div class="flex flex-col">
            <h3 class="text-sm font-bold text-slate-900">Stage 1 Setup Complete</h3>
            <span class="text-xs text-slate-500 mt-0.5">Workspace cloned, dataset linked, and paper OCR markdown generated successfully.</span>
          </div>
        </div>

        <!-- Tab Selection Switcher -->
        <div class="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
          <div class="border-b border-slate-200 flex items-center px-4 bg-slate-50/20">
            <button 
              type="button"
              (click)="selectTab('ocr')"
              class="px-4 py-3.5 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center gap-2"
              [class.border-indigo-600]="activeTab() === 'ocr'"
              [class.text-indigo-600]="activeTab() === 'ocr'"
              [class.border-transparent]="activeTab() !== 'ocr'"
              [class.text-slate-500]="activeTab() !== 'ocr'"
            >
              <i class="pi pi-file-pdf"></i>
              OCR Markdown Paper
            </button>
            <button 
              type="button"
              (click)="selectTab('files')"
              class="px-4 py-3.5 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center gap-2"
              [class.border-indigo-600]="activeTab() === 'files'"
              [class.text-indigo-600]="activeTab() === 'files'"
              [class.border-transparent]="activeTab() !== 'files'"
              [class.text-slate-500]="activeTab() !== 'files'"
            >
              <i class="pi pi-folder"></i>
              Workspace Files (REPO/)
            </button>
            <button 
              type="button"
              (click)="selectTab('claims')"
              class="px-4 py-3.5 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center gap-2"
              [class.border-indigo-600]="activeTab() === 'claims'"
              [class.text-indigo-600]="activeTab() === 'claims'"
              [class.border-transparent]="activeTab() !== 'claims'"
              [class.text-slate-500]="activeTab() !== 'claims'"
            >
              <i class="pi pi-list"></i>
              Claims Registry
              <span class="ml-1 bg-slate-100 text-slate-500 text-[10px] px-1.5 py-0.5 rounded-full border border-slate-200">{{ claims().length }}</span>
            </button>
          </div>

          <!-- Tab Contents -->
          <div class="p-5">
            
            <!-- Tab 1: OCR Markdown -->
            @if (activeTab() === 'ocr') {
              <app-ocr-preview
                [jobId]="jobId()"
                [markdown]="ocrMarkdown()"
                [charCounts]="job()?.ocrPageCharCounts || []"
                (ocrRetryStarted)="onOcrRetryStarted()"
              />
            }

            <!-- Tab 2: File tree -->
            @if (activeTab() === 'files') {
              <div class="border border-slate-100 rounded-xl p-4 bg-slate-50/20 max-h-[500px] overflow-y-auto">
                <div class="flex items-center gap-2 text-xs font-semibold text-slate-500 pb-3 mb-3 border-b border-slate-100">
                  <i class="pi pi-box"></i>
                  <span>jobs/{{ jobId() }}/REPO/</span>
                </div>
                <app-file-explorer [nodes]="repoFiles()" />
              </div>
            }

            <!-- Tab 3: Claims -->
            @if (activeTab() === 'claims') {
              <div class="space-y-4">
                <div class="flex flex-col gap-1">
                  <h4 class="text-xs font-bold text-slate-700 uppercase tracking-wider">Extracted Quantitative Claims</h4>
                  <span class="text-xs text-slate-400">Scientific metrics extracted from the paper to be replicated in Stage 4.</span>
                </div>

                <div class="space-y-3">
                  @for (claim of claims(); track claim.id) {
                    <div class="bg-white border border-slate-100 hover:border-slate-200 rounded-xl p-4 shadow-2xs flex items-start justify-between gap-4 transition-all">
                      <div class="flex flex-col gap-1.5">
                        <span class="text-xs font-bold text-slate-400 uppercase tracking-wider font-mono">Claim ID: {{ claim.id.substring(claim.id.indexOf('claim_')) }}</span>
                        <p class="text-xs md:text-sm text-slate-700 leading-relaxed font-semibold">{{ claim.claimText }}</p>
                        
                        <div class="flex items-center gap-2 pt-1">
                          <span class="text-[10px] font-semibold text-slate-400 bg-slate-50 px-2 py-0.5 border border-slate-100 rounded-full">
                            Source: {{ claim.source === 'user' ? 'Manual Submit' : 'Gemini Extraction' }}
                          </span>
                          <span class="text-[10px] font-semibold text-amber-600 bg-amber-50 px-2 py-0.5 border border-amber-100 rounded-full">
                            Status: Pending Replication
                          </span>
                        </div>
                      </div>
                    </div>
                  }
                </div>
              </div>
            }

          </div>
        </div>

        <!-- Call to Action Box: Advance to Stage 2 -->
        @if (job()?.status === 'PROVISIONED') {
          <div class="bg-indigo-50 border border-indigo-100 rounded-xl p-5 shadow-2xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div class="flex flex-col gap-1 max-w-lg">
              <h4 class="text-sm font-bold text-slate-900">Proceed to Claim Extraction</h4>
              <p class="text-xs text-slate-500 leading-relaxed">
                Ready to proceed? The next step (Stage 2) launches the Claim Extraction Agent to double-check papers for any further statistical evidence.
              </p>
            </div>
            <button 
              type="button" 
              (click)="onAdvanceToStage2()"
              class="px-5 py-2.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm hover:shadow-md transition-all self-start sm:self-auto cursor-pointer"
            >
              Advance to Stage 2
            </button>
          </div>
        }

      </div>
    }

    <!-- ================= CASE 3: FAILED SETUP ================= -->
    @if (getStageStatus('PROVISIONING') === 'failed' && !isOcrRetrying()) {
      <div class="space-y-6">
        
        <!-- Error Banner -->
        <div class="bg-rose-50 border border-rose-100 rounded-xl p-5 shadow-2xs space-y-4">
          <div class="flex items-start gap-3">
            <div class="w-8 h-8 rounded-full bg-rose-100 flex items-center justify-center text-rose-500 shrink-0 shadow-xs">
              <i class="pi pi-exclamation-triangle text-sm font-bold"></i>
            </div>
            <div class="flex flex-col gap-1.5">
              <h3 class="text-sm font-bold text-slate-900">Provisioning Setup Failed</h3>
              <p class="text-xs text-slate-500 leading-relaxed">
                An error occurred during stage execution inside the sandbox runner. The container environment was left running to allow debugging.
              </p>
              @if (getStage('PROVISIONING')?.errorLog) {
                <div class="bg-white border border-rose-200 rounded-lg p-3 text-xs font-mono text-rose-600 max-h-32 overflow-y-auto">
                  {{ getStage('PROVISIONING')?.errorLog }}
                </div>
              }
            </div>
          </div>

          <!-- Sandbox Connection details block -->
          <div class="bg-slate-900 border border-slate-950 rounded-xl p-4 space-y-3 font-mono text-xs shadow-inner">
            <div class="flex items-center justify-between text-slate-400 border-b border-slate-800 pb-2 mb-1">
              <span>Sandbox Terminal Access</span>
              <span class="text-[10px] text-rose-400">Offline Debug Mode</span>
            </div>
            <div class="flex flex-col gap-2">
              <div class="flex items-center justify-between text-slate-300">
                <span>Sandbox Host ID:</span>
                <span class="text-indigo-400 font-semibold">{{ getStage('PROVISIONING')?.sandboxInfo?.sandboxId }}</span>
              </div>
              <div class="flex flex-col gap-1">
                <span class="text-slate-400">Run this command to SSH into sandbox:</span>
                <div class="flex items-center gap-2 bg-slate-950 border border-slate-800 px-3 py-2 rounded-lg text-emerald-400 select-all">
                  <span>{{ getStage('PROVISIONING')?.sandboxInfo?.connectionCommand }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="flex items-center justify-end gap-3 pt-2">
            <button 
              type="button" 
              (click)="onRetry()"
              class="px-4 py-2 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm hover:shadow-md transition-all cursor-pointer"
            >
              <i class="pi pi-refresh mr-1 text-[10px]"></i>
              Retry Setup
            </button>
          </div>
        </div>

        <!-- Terminal logs display below failed banner -->
        <div class="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-2">
          <span class="text-xs text-slate-500 font-semibold">Error Log Stream</span>
          <div class="bg-slate-900 border border-slate-950 rounded-xl p-4 h-[250px] overflow-y-auto font-mono text-[11px] leading-relaxed shadow-inner space-y-1.5">
            @for (log of logs(); track $index) {
              <div class="flex items-start gap-2">
                <span class="text-slate-500 shrink-0">[{{ log.timestamp }}]</span>
                <span 
                  class="shrink-0 font-bold uppercase"
                  [class.text-emerald-400]="log.level === 'INFO'"
                  [class.text-rose-400]="log.level === 'ERROR'"
                >
                  [{{ log.level }}]
                </span>
                <span class="text-slate-300">{{ log.message }}</span>
              </div>
            }
          </div>
        </div>

      </div>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class StageProvisioningComponent {
  private readonly jobService = inject(JobService);

  // Inputs
  jobId = input.required<string>();
  job = input<Job | null>(null);
  stages = input<JobStage[]>([]);
  logs = input<JobLog[]>([]);
  ocrMarkdown = input<string>('');
  repoFiles = input<any[]>([]);
  claims = input<Claim[]>([]);

  // State
  activeTab = signal<'ocr' | 'files' | 'claims'>('ocr');
  isOcrRetrying = signal(false);
  private _prevStatus = signal<string | undefined>(undefined);

  getStageStatus(stageName: string): 'completed' | 'running' | 'failed' | 'pending' {
    const stage = this.stages().find(s => s.stageName === stageName);
    return stage ? (stage.status as any) : 'pending';
  }

  getStage(stageName: string): JobStage | undefined {
    return this.stages().find(s => s.stageName === stageName);
  }

  progressPercent = computed(() => {
    const jobVal = this.job();
    if (!jobVal) return 0;
    if (jobVal.status === 'CREATED') return 5;
    if (jobVal.status === 'FAILED') return 100;
    if (jobVal.status === 'PROVISIONED' || jobVal.status === 'CLAIM_EXTRACTION' || jobVal.status === 'COMPLETED') return 100;
    
    const logsList = this.logs();
    return Math.min(Math.round((logsList.length / 9) * 100), 98);
  });

  activeStepName = computed(() => {
    const logsList = this.logs();
    if (logsList.length <= 2) return 'Step 1/3: Provisioning workspace directories...';
    if (logsList.length <= 5) return 'Step 2/3: Unzipping files and cloning repo...';
    return 'Step 3/3: Running Gemini Vision OCR to convert paper to markdown...';
  });

  constructor() {
    effect(() => {
      const currentStatus = this.job()?.status;
      const prev = this._prevStatus();
      if (this.isOcrRetrying() && prev === 'PROVISIONING' && currentStatus === 'PROVISIONED') {
        this.isOcrRetrying.set(false);
      }
      this._prevStatus.set(currentStatus);
    });
  }

  onRetry(): void {
    this.jobService.retryPipelineStage(this.jobId(), 'PROVISIONING');
  }

  onAdvanceToStage2(): void {
    this.jobService.advancePipeline(this.jobId(), 'CLAIM_EXTRACTION');
  }

  onOcrRetryStarted(): void {
    this.isOcrRetrying.set(true);
    this._prevStatus.set('PROVISIONING');
  }

  selectTab(tab: 'ocr' | 'files' | 'claims'): void {
    this.activeTab.set(tab);
  }
}
