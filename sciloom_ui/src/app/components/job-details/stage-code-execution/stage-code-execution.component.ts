import { 
  Component, 
  inject, 
  input, 
  signal, 
  effect, 
  ChangeDetectionStrategy, 
  ViewChild, 
  ElementRef, 
  AfterViewChecked 
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ConfirmationService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { MessageModule } from 'primeng/message';
import { Job, JobLog, SandboxInfo } from '../../../types/job.types';
import { JobService } from '../../../services/job.service';

@Component({
  selector: 'app-stage-code-execution',
  imports: [
    CommonModule,
    ButtonModule,
    ConfirmDialogModule,
    MessageModule
  ],
  providers: [ConfirmationService],
  template: `
    <p-confirmDialog key="deleteSandboxDialog" />

    <div class="space-y-6">
      <!-- Header -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-4">
        <div class="flex flex-col gap-1">
          <h3 class="text-base font-bold text-slate-900 flex items-center gap-2">
            <i class="pi pi-code text-indigo-600"></i>
            Stage 3: Code Execution
          </h3>
          <span class="text-xs text-slate-500">
            Run agent to execute code, verify claims in the isolated Docker sandbox, and interact via OpenCode.
          </span>
        </div>
        
        <!-- Stage Status Badge -->
        <div>
          @switch (stageStatus()) {
            @case ('pending') {
              <span class="text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                Pending
              </span>
            }
            @case ('running') {
              <span class="text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200 flex items-center gap-1.5">
                <span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-ping"></span>
                Running
              </span>
            }
            @case ('completed') {
              <span class="text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                <i class="pi pi-check text-[9px] font-bold"></i>
                Completed
              </span>
            }
            @case ('failed') {
              <span class="text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-full bg-rose-50 text-rose-700 border border-rose-200 flex items-center gap-1">
                <i class="pi pi-times text-[9px] font-bold"></i>
                Failed
              </span>
            }
          }
        </div>
      </div>

      <!-- STATE 1: PENDING -->
      @if (stageStatus() === 'pending') {
        <div class="bg-slate-50/50 border border-slate-200 rounded-2xl p-10 text-center space-y-4">
          <div class="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mx-auto shadow-xs border border-slate-200">
            <i class="pi pi-clock text-lg"></i>
          </div>
          <div class="max-w-md mx-auto space-y-1.5">
            <h4 class="text-sm font-bold text-slate-900">Waiting for Stage 2 Completion</h4>
            <p class="text-xs text-slate-500 leading-relaxed">
              The Code Execution stage will become available once claims extraction is complete and the claims are verified and saved.
            </p>
          </div>
        </div>
      }

      <!-- STATE 2: RUNNING -->
      @if (stageStatus() === 'running') {
        <div class="space-y-6">
          <!-- Loading banner -->
          <div class="bg-indigo-50/40 border border-indigo-100 rounded-2xl p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div class="flex items-start gap-4">
              <div class="w-10 h-10 rounded-full bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shrink-0 shadow-xs">
                <i class="pi pi-spin pi-spinner text-sm"></i>
              </div>
              <div class="space-y-1">
                <h4 class="text-xs font-bold text-slate-950">Executing Code & Verifying Claims...</h4>
                <p class="text-[11px] text-slate-500 max-w-xl">
                  An autonomous agent has been spawned inside the Docker container to set up dependencies, install the codebase, and verify claim metrics.
                </p>
              </div>
            </div>

            <!-- OpenCode Session Deep Link button (Running stage) -->
            @if (job().opencodeSessionId && job().opencodeServerUrl) {
              <a
                [href]="getOpenCodeUrl()"
                target="_blank"
                class="px-4 py-2 text-xs font-bold text-indigo-600 bg-white border border-indigo-200 rounded-lg shadow-xs hover:shadow-sm hover:bg-indigo-50 transition-all flex items-center gap-1.5 shrink-0 cursor-pointer"
              >
                <i class="pi pi-external-link text-[10px]"></i>
                Open Live Workspace
              </a>
            }
          </div>

          <!-- Live Terminal Console -->
          <div class="space-y-2">
            <div class="flex items-center justify-between text-xs text-slate-500 font-semibold px-1">
              <span class="flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-indigo-500 animate-ping"></span>
                Execution Logs (Live SSE)
              </span>
              <span class="font-mono text-[10px] text-slate-400">sandbox-runner://stream</span>
            </div>
            
            <div 
              #terminalContainer
              class="bg-slate-950 border border-slate-900 rounded-2xl p-4 h-[350px] overflow-y-auto font-mono text-[11px] leading-relaxed shadow-inner space-y-1.5 scrollbar-thin"
            >
              @for (log of logs(); track $index) {
                <div class="flex items-start gap-2">
                  <span class="text-slate-500 shrink-0 select-none">[{{ log.timestamp }}]</span>
                  <span 
                    class="shrink-0 font-bold uppercase select-none"
                    [class.text-indigo-400]="log.level === 'INFO'"
                    [class.text-amber-400]="log.level === 'WARN'"
                    [class.text-rose-400]="log.level === 'ERROR'"
                  >
                    [{{ log.level }}]
                  </span>
                  <span class="text-slate-300 break-all">{{ log.message }}</span>
                </div>
              }
              @if (logs().length === 0) {
                <div class="text-slate-600 italic py-2">Waiting for agent to output logs...</div>
              }
            </div>
          </div>
        </div>
      }

      <!-- STATE 3: COMPLETED -->
      @if (stageStatus() === 'completed') {
        <div class="space-y-6">
          <!-- Success banner -->
          <div class="bg-emerald-50/40 border border-emerald-100 rounded-2xl p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div class="flex items-start gap-4">
              <div class="w-10 h-10 rounded-full bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 shrink-0 shadow-xs">
                <i class="pi pi-check text-sm font-bold"></i>
              </div>
              <div class="space-y-1">
                <h4 class="text-xs font-bold text-slate-950">Code Execution Successful</h4>
                <p class="text-[11px] text-slate-500 max-w-xl">
                  All claims have been run and verified inside the Docker sandbox. Environment status and output logs have been recorded.
                </p>
              </div>
            </div>

            @if (job().opencodeSessionId && job().opencodeServerUrl) {
              <a
                [href]="getOpenCodeUrl()"
                target="_blank"
                class="px-4 py-2 text-xs font-bold text-emerald-700 bg-white border border-emerald-200 rounded-lg shadow-xs hover:shadow-sm hover:bg-emerald-50 transition-all flex items-center gap-1.5 shrink-0 cursor-pointer"
              >
                <i class="pi pi-external-link text-[10px]"></i>
                Open Live Workspace
              </a>
            }
          </div>

          <!-- Sandbox Info & Next Action Panel -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
            <!-- Sandbox Status Card -->
            <div class="bg-slate-50/50 border border-slate-200 rounded-2xl p-5 space-y-3">
              <div class="flex items-center justify-between border-b border-slate-100 pb-2">
                <h4 class="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                  <i class="pi pi-server text-indigo-600 text-[11px]"></i>
                  Sandbox Summary
                </h4>
                <button
                  type="button"
                  (click)="confirmDeleteSandbox($event)"
                  [disabled]="isDeletingSandbox()"
                  class="px-2 py-0.5 text-[9px] font-bold text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-200 rounded transition-colors cursor-pointer"
                >
                  Delete Sandbox
                </button>
              </div>
              
              @if (isLoadingSandboxInfo()) {
                <div class="py-4 text-center text-xs text-slate-400">
                  <i class="pi pi-spin pi-spinner mr-1"></i> Loading details...
                </div>
              } @else if (sandboxInfo()) {
                <div class="space-y-2 text-xs">
                  <div class="flex justify-between">
                    <span class="text-slate-500">Container Name:</span>
                    <span class="font-mono text-slate-800 font-semibold">{{ sandboxInfo()?.sandboxName }}</span>
                  </div>
                  <div class="flex justify-between">
                    <span class="text-slate-500">Status:</span>
                    <span class="font-bold text-emerald-600 flex items-center gap-1">
                      <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                      Active
                    </span>
                  </div>
                  <div class="flex justify-between">
                    <span class="text-slate-500">Docker ID:</span>
                    <span class="font-mono text-slate-400 select-all">{{ sandboxInfo()?.sandboxId | slice:0:12 }}</span>
                  </div>
                </div>
              } @else {
                <div class="text-[11px] text-slate-500 italic">No details loaded.</div>
              }
            </div>

            <!-- Next Action Card -->
            <div class="bg-indigo-50/30 border border-indigo-100 rounded-2xl p-5 flex flex-col justify-between gap-4">
              <div class="space-y-1">
                <h4 class="text-xs font-bold text-indigo-950">Advance Pipeline</h4>
                <p class="text-[11px] text-slate-500 leading-relaxed">
                  Move to Stage 4: Claim Replication to start verifying replication results across multiple environments.
                </p>
              </div>
              <div class="flex flex-wrap items-center gap-3 self-start">
                <button
                  type="button"
                  (click)="onAdvance()"
                  class="px-4 py-2.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm hover:shadow-md transition-all cursor-pointer flex items-center justify-center gap-2"
                >
                  <i class="pi pi-arrow-right text-[10px]"></i>
                  Advance to Stage 4
                </button>
                <button
                  type="button"
                  (click)="onRetry()"
                  class="px-4 py-2.5 text-xs font-bold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg shadow-sm hover:shadow-md transition-all cursor-pointer flex items-center justify-center gap-2"
                >
                  <i class="pi pi-refresh text-[10px]"></i>
                  Retry Code Execution
                </button>
              </div>
            </div>
          </div>
        </div>
      }

      <!-- STATE 4: FAILED -->
      @if (stageStatus() === 'failed') {
        <div class="space-y-6">
          <!-- Error banner -->
          <div class="bg-rose-50/40 border border-rose-100 rounded-2xl p-6 flex items-start gap-4">
            <div class="w-10 h-10 rounded-full bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600 shrink-0 shadow-xs">
              <i class="pi pi-exclamation-triangle text-sm"></i>
            </div>
            <div class="space-y-1.5 flex-1">
              <h4 class="text-xs font-bold text-slate-950">Code Execution Failed</h4>
              <p class="text-[11px] text-slate-500 leading-relaxed">
                An error occurred while compiling code, building dependencies, or running validation. Inspect the logs below to diagnose.
              </p>
            </div>
          </div>

          <!-- Scrollable Error Logs -->
          @if (errorLog()) {
            <div class="space-y-2">
              <h4 class="text-xs font-bold text-slate-700 px-1">Error Logs</h4>
              <div class="bg-slate-950 border border-slate-900 rounded-2xl p-4 max-h-[250px] overflow-y-auto font-mono text-[11px] text-rose-200 whitespace-pre-wrap leading-relaxed shadow-inner">
                {{ errorLog() }}
              </div>
            </div>
          }

          <!-- Sandbox Debug Panel -->
          <div class="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
            <div class="flex items-center justify-between border-b border-slate-100 pb-2.5">
              <h4 class="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                <i class="pi pi-wrench text-indigo-600 text-[11px]"></i>
                Sandbox Debug Details
              </h4>
              <div class="flex gap-2">
                <!-- Delete container -->
                <button
                  type="button"
                  (click)="confirmDeleteSandbox($event)"
                  [disabled]="isDeletingSandbox()"
                  class="px-2.5 py-1 text-[10px] font-bold text-rose-600 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-md transition-colors cursor-pointer disabled:opacity-50"
                >
                  @if (isDeletingSandbox()) {
                    <i class="pi pi-spin pi-spinner mr-1"></i> Deleting...
                  } @else {
                    <i class="pi pi-trash mr-1"></i> Delete Sandbox
                  }
                </button>
              </div>
            </div>

            @if (isLoadingSandboxInfo()) {
              <div class="py-4 text-center text-xs text-slate-400">
                <i class="pi pi-spin pi-spinner mr-1"></i> Loading connection details...
              </div>
            } @else if (sandboxInfo()) {
              <div class="space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div class="flex justify-between border-b border-slate-50 pb-2">
                    <span class="text-slate-500">Container ID:</span>
                    <span class="font-mono text-slate-800 select-all">{{ sandboxInfo()?.sandboxId }}</span>
                  </div>
                  <div class="flex justify-between border-b border-slate-50 pb-2">
                    <span class="text-slate-500">Container Name:</span>
                    <span class="font-mono text-slate-800 font-semibold">{{ sandboxInfo()?.sandboxName }}</span>
                  </div>
                  <div class="flex justify-between border-b border-slate-50 pb-2">
                    <span class="text-slate-500">Status:</span>
                    <span class="font-bold text-rose-600 uppercase">{{ sandboxInfo()?.status }}</span>
                  </div>
                  @if (sandboxInfo()?.opencodeSessionId && sandboxInfo()?.opencodeServerUrl) {
                    <div class="flex justify-between border-b border-slate-50 pb-2">
                      <span class="text-slate-500">OpenCode Live Session:</span>
                      <a
                        [href]="getOpenCodeUrl()"
                        target="_blank"
                        class="text-indigo-600 font-semibold hover:underline"
                      >
                        Open Session
                      </a>
                    </div>
                  }
                </div>

                <!-- Connection command bubble with copy -->
                @if (sandboxInfo()?.connectionCommand) {
                  <div class="space-y-2">
                    <div class="flex items-center justify-between text-[11px] text-slate-500 px-1">
                      <span class="font-semibold">Connect to Sandbox via CLI:</span>
                      @if (copied()) {
                        <span class="text-emerald-600 font-bold flex items-center gap-1">
                          <i class="pi pi-check text-[10px]"></i> Copied!
                        </span>
                      } @else {
                        <span class="text-slate-400 font-mono">ssh / docker exec</span>
                      }
                    </div>
                    
                    <div class="bg-slate-900 border border-slate-950 rounded-xl p-3 flex items-center justify-between gap-4 font-mono text-[10px] text-slate-200">
                      <span class="break-all select-all font-mono leading-relaxed">{{ sandboxInfo()?.connectionCommand }}</span>
                      <button
                        type="button"
                        (click)="copyConnectionCommand(sandboxInfo()?.connectionCommand ?? '')"
                        class="p-1.5 hover:bg-slate-800 rounded-md border border-slate-800 hover:border-slate-700 text-slate-400 hover:text-white transition-all cursor-pointer shrink-0"
                        title="Copy to clipboard"
                      >
                        <i class="pi pi-copy text-xs"></i>
                      </button>
                    </div>
                  </div>
                }
              </div>
            } @else {
              <div class="text-[11px] text-slate-500 italic">No details loaded.</div>
            }
          </div>

          <!-- Action Footer -->
          <div class="flex items-center gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              (click)="onRetry()"
              class="px-5 py-2.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm hover:shadow-md transition-all cursor-pointer flex items-center gap-2"
            >
              <i class="pi pi-refresh text-[10px]"></i>
              Retry Code Execution
            </button>
          </div>
        </div>
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class StageCodeExecutionComponent implements AfterViewChecked {
  private readonly jobService = inject(JobService);
  private readonly confirmationService = inject(ConfirmationService);

  jobId = input.required<string>();
  job = input.required<Job>();
  stageStatus = input.required<'pending' | 'running' | 'completed' | 'failed'>();
  errorLog = input<string | null>(null);
  logs = input<JobLog[]>([]);

  sandboxInfo = signal<SandboxInfo | null>(null);
  isLoadingSandboxInfo = signal(false);
  sandboxInfoError = signal<string | null>(null);
  isDeletingSandbox = signal(false);
  copied = signal(false);

  @ViewChild('terminalContainer') private terminalContainer!: ElementRef;

  constructor() {
    effect(() => {
      const status = this.stageStatus();
      // Fetch sandbox info on completion or failure
      if (status === 'completed' || status === 'failed') {
        this.fetchSandboxInfo();
      } else {
        this.sandboxInfo.set(null);
      }
    });
  }

  ngAfterViewChecked() {
    this.scrollToBottom();
  }

  private scrollToBottom(): void {
    if (this.terminalContainer) {
      try {
        const el = this.terminalContainer.nativeElement;
        el.scrollTop = el.scrollHeight;
      } catch (err) {
        // Ignore
      }
    }
  }

  fetchSandboxInfo() {
    this.isLoadingSandboxInfo.set(true);
    this.sandboxInfoError.set(null);
    this.jobService.getSandboxInfo(this.jobId()).subscribe({
      next: (info) => {
        this.sandboxInfo.set(info);
        this.isLoadingSandboxInfo.set(false);
      },
      error: (err) => {
        console.error('Failed to fetch sandbox info:', err);
        this.sandboxInfoError.set('Could not load sandbox debug details.');
        this.isLoadingSandboxInfo.set(false);
      }
    });
  }

  getOpenCodeUrl(): string {
    const serverUrl = this.job().opencodeServerUrl ?? '';
    const sessionId = this.job().opencodeSessionId ?? '';
    if (!serverUrl || !sessionId) return '#';
    // Format: {opencodeServerUrl}/?session={opencodeSessionId}
    const cleanUrl = serverUrl.endsWith('/') ? serverUrl : `${serverUrl}/`;
    return `${cleanUrl}?session=${encodeURIComponent(sessionId)}`;
  }

  confirmDeleteSandbox(event: Event): void {
    this.confirmationService.confirm({
      key: 'deleteSandboxDialog',
      target: event.target as EventTarget,
      message: 'Are you sure you want to delete this Docker sandbox? This will terminate the container and lose any unsaved runtime state.',
      header: 'Delete Sandbox',
      icon: 'pi pi-exclamation-triangle',
      rejectButtonProps: {
        label: 'Cancel',
        severity: 'secondary',
        outlined: true,
        size: 'small'
      },
      acceptButtonProps: {
        label: 'Delete Container',
        severity: 'danger',
        size: 'small'
      },
      accept: () => {
        this.deleteSandbox();
      }
    });
  }

  deleteSandbox(): void {
    this.isDeletingSandbox.set(true);
    this.jobService.deleteSandbox(this.jobId()).subscribe({
      next: () => {
        this.isDeletingSandbox.set(false);
        this.jobService.loadJobDetails(this.jobId());
      },
      error: (err) => {
        console.error('Failed to delete sandbox:', err);
        this.isDeletingSandbox.set(false);
      }
    });
  }

  copyConnectionCommand(cmd: string): void {
    navigator.clipboard.writeText(cmd).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    });
  }

  onAdvance(): void {
    this.jobService.advancePipeline(this.jobId(), 'CLAIM_REPLICATION');
  }

  onRetry(): void {
    this.jobService.retryPipelineStage(this.jobId(), 'CODE_EXECUTION');
  }
}
