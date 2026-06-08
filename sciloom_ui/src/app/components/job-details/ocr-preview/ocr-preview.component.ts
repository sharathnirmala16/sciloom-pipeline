import { Component, input, output, signal, computed, inject, ChangeDetectionStrategy } from '@angular/core';
import { MarkdownComponent } from 'ngx-markdown';
import { FormsModule } from '@angular/forms';
import { DecimalPipe } from '@angular/common';
import { JobService } from '../../../services/job.service';

// PrimeNG
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { ConfirmationService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { TooltipModule } from 'primeng/tooltip';

@Component({
  selector: 'app-ocr-preview',
  imports: [MarkdownComponent, FormsModule, DecimalPipe, ConfirmDialogModule, ButtonModule, TooltipModule],
  providers: [ConfirmationService],
  template: `
    <!-- PrimeNG Confirm Dialog (scoped to this component) -->
    <p-confirmDialog key="ocrRetryDialog" />

    <div class="bg-white border border-slate-100 rounded-xl shadow-sm font-sans text-slate-800">

      <!-- ── Header toolbar ─────────────────────────────────────────────── -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
        <div class="flex items-center gap-2.5">
          <i class="pi pi-file-pdf text-rose-500 text-xl"></i>
          <div>
            <span class="font-semibold text-slate-700 text-sm">RESEARCH_PAPER.md</span>
            <span class="ml-2 text-[11px] text-slate-400 bg-slate-50 px-2 py-0.5 rounded-full border border-slate-100">Gemini 3.1 Flash Lite OCR</span>
          </div>
        </div>

        <!-- Action buttons -->
        <div class="flex items-center gap-2">
          @if (!isEditing()) {
            <!-- Copy button -->
            <button
              type="button"
              (click)="copyMarkdown()"
              pTooltip="Copy raw Markdown"
              tooltipPosition="top"
              class="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300 transition-all cursor-pointer"
            >
              <i [class]="copied() ? 'pi pi-check text-emerald-500' : 'pi pi-copy'"></i>
              {{ copied() ? 'Copied!' : 'Copy' }}
            </button>

            <!-- Edit button -->
            <button
              type="button"
              (click)="enableEdit()"
              pTooltip="Edit raw Markdown"
              tooltipPosition="top"
              class="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300 transition-all cursor-pointer"
            >
              <i class="pi pi-pencil"></i>
              Edit
            </button>

            <!-- Retry OCR button -->
            <button
              type="button"
              (click)="confirmRetryOcr()"
              pTooltip="Re-run Gemini OCR on all pages"
              tooltipPosition="top"
              class="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-amber-200 text-amber-700 bg-amber-50 hover:bg-amber-100 hover:border-amber-300 transition-all cursor-pointer"
            >
              <i class="pi pi-refresh"></i>
              Retry OCR
            </button>
          }

          @if (isEditing()) {
            <!-- Cancel button -->
            <button
              type="button"
              (click)="cancelEdit()"
              class="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-all cursor-pointer"
            >
              <i class="pi pi-times"></i>
              Cancel
            </button>

            <!-- Save button -->
            <button
              type="button"
              (click)="saveChanges()"
              class="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 transition-all cursor-pointer font-semibold"
            >
              <i class="pi pi-save"></i>
              Save Changes
            </button>
          }
        </div>
      </div>

      <!-- ── Page Density Grid ───────────────────────────────────────────── -->
      @if (charCounts().length > 0) {
        <div class="px-6 py-3 border-b border-slate-100 bg-slate-50/60">
          <div class="flex items-center gap-2 mb-2">
            <i class="pi pi-chart-bar text-slate-400 text-xs"></i>
            <span class="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">OCR Page Character Counts</span>
            @if (emptyPageCount() > 0) {
              <span class="ml-auto text-[10px] bg-rose-50 text-rose-600 border border-rose-200 px-2 py-0.5 rounded-full font-semibold">
                {{ emptyPageCount() }} page{{ emptyPageCount() === 1 ? '' : 's' }} with 0 chars — consider retrying OCR
              </span>
            }
          </div>
          <div class="flex flex-wrap gap-1.5">
            @for (count of charCounts(); track $index) {
              <div
                class="flex flex-col items-center gap-0.5 cursor-default"
                [title]="'Page ' + ($index + 1) + ': ' + count + ' chars'"
              >
                <div
                  class="w-7 h-7 rounded-md flex items-center justify-center text-[10px] font-bold border transition-colors"
                  [class]="count === 0
                    ? 'bg-rose-100 border-rose-300 text-rose-700'
                    : count < 200
                    ? 'bg-amber-50 border-amber-200 text-amber-700'
                    : 'bg-emerald-50 border-emerald-200 text-emerald-700'"
                >
                  {{ $index + 1 }}
                </div>
                <span class="text-[9px] text-slate-400">{{ count === 0 ? '0' : (count >= 1000 ? (count / 1000 | number:'1.1-1') + 'k' : count) }}</span>
              </div>
            }
          </div>
        </div>
      }

      <!-- ── Content area ───────────────────────────────────────────────── -->
      <div class="max-h-[580px] overflow-y-auto">

        @if (isEditing()) {
          <!-- Raw Markdown editor textarea -->
          <div class="p-4">
            <div class="text-[11px] text-slate-400 mb-2 flex items-center gap-1.5">
              <i class="pi pi-code"></i>
              Editing raw Markdown — changes will be saved to the backend
            </div>
            <textarea
              [(ngModel)]="editableContent"
              class="w-full min-h-[480px] font-mono text-sm text-slate-800 bg-slate-50 border border-slate-200 rounded-lg p-4 resize-y focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 leading-relaxed"
              spellcheck="false"
              placeholder="Paste or type your markdown here..."
            ></textarea>
          </div>
        } @else {
          <!-- Rendered Markdown preview -->
          <article class="prose max-w-none text-slate-700 p-6 md:p-8">
            <markdown [data]="processedMarkdown()" katex [katexOptions]="katexOptions"></markdown>
          </article>
        }

      </div>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class OCRPreviewComponent {
  // Inputs
  markdown = input.required<string>();
  jobId = input.required<string>();
  charCounts = input<number[]>([]);

  // Outputs
  ocrRetryStarted = output<void>();

  // State
  isEditing = signal(false);
  editableContent = signal('');
  copied = signal(false);

  private readonly jobService = inject(JobService);
  private readonly confirmationService = inject(ConfirmationService);

  // Computed: empty page count for warning badge
  emptyPageCount = computed(() => this.charCounts().filter(c => c === 0).length);

  // Computed: preprocessed markdown that doubles backslashes in math blocks
  processedMarkdown = computed(() => {
    const raw = this.markdown();
    if (!raw) return '';

    // Double backslashes inside LaTeX math delimiters to survive Marked parsing
    const mathRegex = /(\$\$[\s\S]*?\$\$)|(\$[^\$\n]+?\$)|(\\\[[\s\S]*?\\\])|(\\\([\s\S]*?\\\))/g;
    return raw.replace(mathRegex, (match) => match.replace(/\\/g, '\\\\'));
  });

  public katexOptions = {
    delimiters: [
      { left: '$$', right: '$$', display: true },
      { left: '$', right: '$', display: false },
      { left: '\\(', right: '\\)', display: false },
      { left: '\\[', right: '\\]', display: true }
    ],
    throwOnError: false
  };

  // ── Actions ──────────────────────────────────────────────────────────────

  copyMarkdown(): void {
    const content = this.markdown();
    if (!content) return;
    navigator.clipboard.writeText(content).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    });
  }

  enableEdit(): void {
    this.editableContent.set(this.markdown());
    this.isEditing.set(true);
  }

  cancelEdit(): void {
    this.isEditing.set(false);
  }

  saveChanges(): void {
    const content = this.editableContent();
    this.jobService.updateOcrMarkdown(this.jobId(), content);
    this.isEditing.set(false);
  }

  confirmRetryOcr(): void {
    this.confirmationService.confirm({
      key: 'ocrRetryDialog',
      header: 'Retry OCR Extraction?',
      message: 'This will re-run Gemini Vision OCR on all pages of the paper PDF, overwriting the current markdown. This may take several minutes. Continue?',
      icon: 'pi pi-refresh',
      acceptLabel: 'Yes, Retry OCR',
      rejectLabel: 'Cancel',
      acceptButtonStyleClass: 'p-button-warning',
      accept: () => {
        this.ocrRetryStarted.emit();
        this.jobService.retryOcr(this.jobId());
      }
    });
  }
}
