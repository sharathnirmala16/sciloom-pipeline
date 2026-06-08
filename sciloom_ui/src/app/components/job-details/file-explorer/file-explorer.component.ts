import { Component, input, ChangeDetectionStrategy } from '@angular/core';

@Component({
  selector: 'app-file-explorer',
  imports: [FileExplorerComponent],
  template: `
    <ul class="list-none pl-4 space-y-1">
      @for (node of nodes(); track node.name) {
        <li class="py-0.5">
          <div class="flex items-center gap-2.5 hover:bg-slate-50 px-2 py-1.5 rounded-lg transition-colors cursor-default select-none group">
            @if (node.isDir) {
              <i class="pi pi-folder-open text-amber-500 text-base"></i>
              <span class="font-medium text-slate-700 text-sm">{{ node.name }}</span>
            } @else {
              <i class="pi pi-file text-slate-400 text-base"></i>
              <span class="text-slate-600 text-sm group-hover:text-slate-900">{{ node.name }}</span>
              <span class="text-[11px] text-slate-400 font-mono ml-auto">{{ formatSize(node.size) }}</span>
            }
          </div>
          @if (node.isDir && node.children && node.children.length > 0) {
            <div class="border-l border-slate-100 ml-3 pl-1">
              <app-file-explorer [nodes]="node.children" />
            </div>
          }
        </li>
      }
    </ul>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class FileExplorerComponent {
  nodes = input.required<any[]>();

  protected formatSize(bytes?: number): string {
    if (bytes === undefined) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }
}
