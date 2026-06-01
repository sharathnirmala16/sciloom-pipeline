import { Component, inject, input, output, signal, computed, effect, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ConfirmationService } from 'primeng/api';
import { Claim } from '../../types/job.types';

import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { TextareaModule } from 'primeng/textarea';
import { TagModule } from 'primeng/tag';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { MessageModule } from 'primeng/message';

@Component({
  selector: 'app-claims-editor',
  imports: [
    CommonModule,
    FormsModule,
    ButtonModule,
    InputTextModule,
    TextareaModule,
    TagModule,
    ConfirmDialogModule,
    MessageModule
  ],
  providers: [ConfirmationService],
  template: `
    <p-confirmDialog key="deleteClaimDialog" />

    <div class="space-y-6">
      <!-- Header -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div class="flex flex-col gap-1">
          <h3 class="text-sm font-bold text-slate-900">Claims Editor</h3>
          <span class="text-xs text-slate-400">
            Review, edit, add, or remove claims before advancing to Stage 3.
          </span>
        </div>
        <p-tag
          [value]="editableClaims().length + ' claim' + (editableClaims().length !== 1 ? 's' : '')"
          severity="info"
          styleClass="text-[9px] font-extrabold tracking-wider px-2 py-0.5 rounded-full"
        />
      </div>

      <!-- No claims state -->
      @if (editableClaims().length === 0) {
        <div class="bg-slate-50 border border-slate-200 rounded-xl p-8 text-center">
          <div class="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
            <i class="pi pi-inbox text-slate-400 text-lg"></i>
          </div>
          <p class="text-xs text-slate-500 mb-4">No claims have been extracted or added yet.</p>
          <button
            type="button"
            (click)="addNewClaim()"
            class="px-4 py-2 text-xs font-semibold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg transition-colors cursor-pointer"
          >
            <i class="pi pi-plus mr-1.5 text-[10px]"></i>
            Add Your First Claim
          </button>
        </div>
      }

      <!-- Claims list -->
      @for (claim of editableClaims(); track claim._localId) {
        <div
          class="bg-white border rounded-xl p-5 shadow-2xs transition-all group"
          [class.border-slate-200]="!claim._isNew && !claim._isModified"
          [class.border-indigo-200]="claim._isNew"
          [class.border-amber-200]="claim._isModified && !claim._isNew"
          [class.bg-indigo-50/20]="claim._isNew"
        >
          <div class="flex items-start gap-4">
            <div class="flex-1 space-y-3">
              <!-- Source badge & actions row -->
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  @if (claim.source === 'agent') {
                    <span class="text-[10px] font-bold text-slate-500 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-full flex items-center gap-1">
                      <i class="pi pi-android text-[9px]"></i>
                      Agent Extracted
                    </span>
                  } @else {
                    <span class="text-[10px] font-bold text-indigo-600 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded-full flex items-center gap-1">
                      <i class="pi pi-user text-[9px]"></i>
                      User Added
                    </span>
                  }
                  @if (claim._isModified && !claim._isNew) {
                    <span class="text-[9px] font-semibold text-amber-600 bg-amber-50 border border-amber-100 px-1.5 py-0.5 rounded-full">
                      Modified
                    </span>
                  }
                  @if (claim._isNew) {
                    <span class="text-[9px] font-semibold text-indigo-600 bg-indigo-100 border border-indigo-200 px-1.5 py-0.5 rounded-full">
                      New
                    </span>
                  }
                </div>
                <button
                  type="button"
                  (click)="confirmDeleteClaim(claim._localId, $event)"
                  class="w-7 h-7 rounded-lg flex items-center justify-center text-slate-300 hover:text-rose-500 hover:bg-rose-50 border border-transparent hover:border-rose-200 transition-all opacity-0 group-hover:opacity-100 cursor-pointer"
                  title="Remove claim"
                >
                  <i class="pi pi-trash text-xs"></i>
                </button>
              </div>

              <!-- Claim text textarea -->
              <textarea
                [ngModel]="claim.claimText"
                (ngModelChange)="updateClaimText(claim._localId, $event)"
                rows="2"
                class="w-full text-xs border border-slate-200 rounded-lg p-3 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 transition-all placeholder:text-slate-300"
                [class.border-indigo-300]="claim._isNew"
                placeholder="Enter claim text..."
              ></textarea>

              <!-- Metrics / Evidence read-only display if present -->
              @if (claim.metrics) {
                <div class="flex items-start gap-2 text-[10px] text-slate-500 bg-slate-50 border border-slate-100 rounded-lg px-3 py-2">
                  <span class="font-bold text-slate-400 shrink-0 mt-0.5">Metrics:</span>
                  <span class="font-mono">{{ claim.metrics }}</span>
                </div>
              }
              @if (claim.evidence) {
                <div class="flex items-start gap-2 text-[10px] text-slate-500 bg-slate-50 border border-slate-100 rounded-lg px-3 py-2">
                  <span class="font-bold text-slate-400 shrink-0 mt-0.5">Evidence:</span>
                  <span class="font-mono break-all">{{ claim.evidence }}</span>
                </div>
              }
            </div>
          </div>
        </div>
      }

      <!-- Add claim button -->
      @if (editableClaims().length > 0) {
        <button
          type="button"
          (click)="addNewClaim()"
          class="w-full py-3 text-xs font-semibold text-slate-500 hover:text-indigo-600 border border-dashed border-slate-200 hover:border-indigo-300 rounded-xl bg-slate-50/50 hover:bg-indigo-50/30 transition-all cursor-pointer flex items-center justify-center gap-2"
        >
          <i class="pi pi-plus text-[10px]"></i>
          Add New Claim
        </button>
      }

      <!-- Error message -->
      @if (saveError()) {
        <p-message severity="error" styleClass="text-xs w-full">
          <ng-template pTemplate>
            <span class="text-xs">{{ saveError() }}</span>
          </ng-template>
        </p-message>
      }

      <!-- Action bar -->
      <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 pt-4 border-t border-slate-100">
        <div class="flex items-center gap-2">
          <button
            type="button"
            (click)="saveClaims()"
            [disabled]="isSaving() || !hasUnsavedChanges()"
            class="px-5 py-2.5 text-xs font-bold text-white rounded-lg shadow-sm transition-all cursor-pointer disabled:cursor-not-allowed flex items-center gap-2"
            [class.bg-indigo-600]="hasUnsavedChanges()"
            [class.hover:bg-indigo-700]="hasUnsavedChanges()"
            [class.bg-slate-300]="!hasUnsavedChanges()"
            [class.text-slate-500]="!hasUnsavedChanges()"
          >
            @if (isSaving()) {
              <i class="pi pi-spin pi-spinner text-[10px]"></i>
              Saving...
            } @else {
              <i class="pi pi-check text-[10px]"></i>
              Save Claims
            }
          </button>
          @if (hasUnsavedChanges()) {
            <span class="text-[10px] text-amber-600 font-semibold">You have unsaved changes</span>
          }
        </div>

        <button
          type="button"
          (click)="onAdvanceClick()"
          class="px-6 py-2.5 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm hover:shadow-md transition-all cursor-pointer flex items-center gap-2 self-start sm:self-auto"
          title="Proceed to Stage 3: Code Execution"
        >
          <i class="pi pi-arrow-right text-[10px]"></i>
          Advance to Stage 3
        </button>
      </div>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ClaimsEditorComponent {
  private readonly http = inject(HttpClient);
  private readonly confirmationService = inject(ConfirmationService);
  private readonly apiUrl = 'http://localhost:8000/api';

  claims = input.required<Claim[]>();
  jobId = input.required<string>();

  claimsSaved = output<void>();
  advanceToStage3 = output<void>();

  isSaving = signal(false);
  saveError = signal<string | null>(null);
  private _nextLocalId = signal(0);

  editableClaims = signal<EditableClaim[]>([]);

  hasUnsavedChanges = computed(() => {
    const original = this.claims();
    const edited = this.editableClaims();
    if (original.length !== edited.filter(c => !c._isDeleted).length) return true;
    return edited.some(e => e._isNew || e._isModified);
  });

  constructor() {
    effect(() => {
      const _claims = this.claims();
      this._syncFromClaims();
    });
  }

  private _syncFromClaims(): void {
    const incoming = this.claims();
    const existing = this.editableClaims();

    const incomingIds = new Set(incoming.map(c => c.id));
    const existingIds = new Set(existing.filter(c => !c._isNew && !c._isDeleted).map(c => c.id));

    const needsSync = incomingIds.size !== existingIds.size
      || ![...incomingIds].every(id => existingIds.has(id));

    if (!needsSync && existing.length === 0 && incoming.length === 0) return;

    if (!needsSync) return;

    let nextId = this._nextLocalId();
    const result: EditableClaim[] = [];

    for (const claim of incoming) {
      const existingEdit = existing.find(e => e.id === claim.id && !e._isDeleted);
      if (existingEdit && !existingEdit._isNew) {
        result.push(existingEdit);
      } else {
        result.push({
          ...claim,
          _localId: `existing_${claim.id}`,
          _isNew: false,
          _isModified: false,
          _isDeleted: false
        });
      }
    }

    for (const edit of existing) {
      if (edit._isNew && !edit._isDeleted) {
        result.push(edit);
      }
    }

    this._nextLocalId.set(nextId);
    this.editableClaims.set(result);
  }

  updateClaimText(localId: string, text: string): void {
    this.editableClaims.update(claims =>
      claims.map(c =>
        c._localId === localId
          ? { ...c, claimText: text, _isModified: !c._isNew }
          : c
      )
    );
    this.saveError.set(null);
  }

  addNewClaim(): void {
    const nextId = this._nextLocalId();
    const localId = `new_${nextId}`;
    this._nextLocalId.set(nextId + 1);

    const newClaim: EditableClaim = {
      id: localId,
      jobId: this.jobId(),
      claimText: '',
      source: 'user',
      replicated: false,
      createdAt: new Date().toISOString(),
      _localId: localId,
      _isNew: true,
      _isModified: false,
      _isDeleted: false
    };

    this.editableClaims.update(claims => [...claims, newClaim]);
    this.saveError.set(null);
  }

  confirmDeleteClaim(localId: string, event: Event): void {
    this.confirmationService.confirm({
      key: 'deleteClaimDialog',
      target: event.target as EventTarget,
      message: 'Are you sure you want to remove this claim?',
      header: 'Delete Claim',
      icon: 'pi pi-exclamation-triangle',
      rejectButtonProps: {
        label: 'Cancel',
        severity: 'secondary',
        outlined: true,
        size: 'small'
      },
      acceptButtonProps: {
        label: 'Delete',
        severity: 'danger',
        size: 'small'
      },
      accept: () => {
        this.deleteClaim(localId);
      }
    });
  }

  deleteClaim(localId: string): void {
    this.editableClaims.update(claims => {
      const claim = claims.find(c => c._localId === localId);
      if (!claim || claim._isNew) {
        return claims.filter(c => c._localId !== localId);
      }
      return claims.map(c =>
        c._localId === localId ? { ...c, _isDeleted: true } : c
      );
    });
    this.saveError.set(null);
  }

  saveClaims(): void {
    if (this.isSaving()) return;

    const claims = this.editableClaims();
    const payload = claims
      .filter(c => !c._isDeleted)
      .map(c => ({
        id: c._isNew ? undefined : c.id,
        claimText: c.claimText.trim(),
        source: c.source ?? 'user'
      }))
      .filter(c => c.claimText.length > 0);

    this.isSaving.set(true);
    this.saveError.set(null);

    this.http.put<Claim[]>(`${this.apiUrl}/jobs/${this.jobId()}/claims`, { claims: payload }).subscribe({
      next: (savedClaims) => {
        const result: EditableClaim[] = savedClaims.map(c => ({
          ...c,
          _localId: `existing_${c.id}`,
          _isNew: false,
          _isModified: false,
          _isDeleted: false
        }));
        this.editableClaims.set(result);
        this.isSaving.set(false);
        this.claimsSaved.emit();
      },
      error: (err) => {
        console.error('Failed to save claims:', err);
        this.saveError.set(err.error?.detail || 'Failed to save claims. Please try again.');
        this.isSaving.set(false);
      }
    });
  }

  onAdvanceClick(): void {
    if (this.hasUnsavedChanges()) {
      this.saveError.set('Please save your changes before advancing to Stage 3.');
      return;
    }
    this.advanceToStage3.emit();
  }
}

interface EditableClaim extends Claim {
  _localId: string;
  _isNew: boolean;
  _isModified: boolean;
  _isDeleted: boolean;
}