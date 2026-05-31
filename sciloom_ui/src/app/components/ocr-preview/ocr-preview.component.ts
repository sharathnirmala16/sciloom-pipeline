import { Component, input, computed, ChangeDetectionStrategy } from '@angular/core';

interface ParsedBlock {
  type: 'h1' | 'h2' | 'h3' | 'list' | 'paragraph';
  text: string;
  items?: string[];
}

@Component({
  selector: 'app-ocr-preview',
  imports: [],
  template: `
    <div class="bg-white border border-slate-100 rounded-xl p-6 md:p-8 shadow-sm max-h-[600px] overflow-y-auto font-sans leading-relaxed text-slate-800">
      <div class="flex items-center justify-between pb-4 mb-6 border-b border-slate-100">
        <div class="flex items-center gap-2">
          <i class="pi pi-file-pdf text-rose-500 text-xl"></i>
          <span class="font-semibold text-slate-700 text-sm">RESEARCH_PAPER.md (OCR parsed)</span>
        </div>
        <span class="text-xs text-slate-400 bg-slate-50 px-2.5 py-1 rounded-full border border-slate-100 font-medium">Gemini 3.5 Flash OCR</span>
      </div>

      <article class="prose max-w-none space-y-4">
        @for (block of parsedBlocks(); track $index) {
          @switch (block.type) {
            @case ('h1') {
              <h1 class="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight pt-2 pb-1">{{ block.text }}</h1>
            }
            @case ('h2') {
              <h2 class="text-xl md:text-2xl font-semibold text-slate-800 tracking-tight pt-3 pb-1 border-b border-slate-50">{{ block.text }}</h2>
            }
            @case ('h3') {
              <h3 class="text-lg font-semibold text-slate-800 pt-2">{{ block.text }}</h3>
            }
            @case ('list') {
              <ul class="list-disc pl-5 space-y-1.5 text-slate-600 my-2">
                @for (item of block.items; track $index) {
                  <li class="text-sm md:text-base leading-relaxed">{{ item }}</li>
                }
              </ul>
            }
            @default {
              <p class="text-sm md:text-base text-slate-600 leading-relaxed font-normal">{{ block.text }}</p>
            }
          }
        }
      </article>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class OCRPreviewComponent {
  markdown = input.required<string>();

  // A simple computed parser that breaks the paper markdown into rendering blocks
  parsedBlocks = computed<ParsedBlock[]>(() => {
    const raw = this.markdown();
    if (!raw) return [];

    // Split text into paragraphs by double newlines
    const paragraphs = raw.split(/\r?\n\r?\n/);
    const blocks: ParsedBlock[] = [];

    for (let p of paragraphs) {
      p = p.trim();
      if (!p) continue;

      if (p.startsWith('# ')) {
        blocks.push({ type: 'h1', text: p.replace('# ', '') });
      } else if (p.startsWith('## ')) {
        blocks.push({ type: 'h2', text: p.replace('## ', '') });
      } else if (p.startsWith('### ')) {
        blocks.push({ type: 'h3', text: p.replace('### ', '') });
      } else if (p.startsWith('- ') || p.startsWith('* ')) {
        // Parse list items
        const items = p.split(/\r?\n[-*]\s*/).map(item => item.replace(/^[-*]\s*/, '').trim()).filter(Boolean);
        blocks.push({ type: 'list', text: '', items });
      } else {
        // Standard paragraph
        blocks.push({ type: 'paragraph', text: p });
      }
    }

    return blocks;
  });
}
