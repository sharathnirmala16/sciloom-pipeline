import { Component, inject, output, signal, ChangeDetectionStrategy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, FormArray, Validators, ReactiveFormsModule, AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';
import { JobService } from '../../services/job.service';
import { validateGitHubUrl } from '../../utils/job-validator';

// PrimeNG Imports
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { RadioButtonModule } from 'primeng/radiobutton';
import { TooltipModule } from 'primeng/tooltip';
import { MessageModule } from 'primeng/message';

// Custom validator for GitHub URLs
export function githubUrlValidator(): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const val = control.value;
    if (!val) return null; // let Validators.required handle empty checks
    return validateGitHubUrl(val) ? null : { invalidGithubUrl: true };
  };
}

@Component({
  selector: 'app-job-form',
  imports: [
    CommonModule,
    ReactiveFormsModule,
    ButtonModule,
    InputTextModule,
    RadioButtonModule,
    TooltipModule,
    MessageModule
  ],
  templateUrl: './job-form.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class JobFormComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly jobService = inject(JobService);

  // Outputs
  submitted = output<string>();
  cancel = output<void>();

  // State management
  jobForm!: FormGroup;
  
  // File trackers for mock handling
  selectedPdfFile = signal<{ name: string; size: number } | null>(null);
  selectedRepoFile = signal<{ name: string; size: number } | null>(null);
  selectedDataFile = signal<{ name: string; size: number } | null>(null);

  ngOnInit(): void {
    this.initForm();
  }

  private initForm(): void {
    this.jobForm = this.fb.group({
      title: ['', [Validators.required, Validators.minLength(3)]],
      pdfFile: [null, [Validators.required]],
      repoSource: ['github', [Validators.required]],
      repoUrl: ['', [Validators.required, githubUrlValidator()]],
      repoFile: [null, []],
      dataSource: ['in_repo', [Validators.required]],
      dataFile: [null, []],
      claims: this.fb.array([])
    });
  }

  // --- Claims Array Helpers ---
  get claims(): FormArray {
    return this.jobForm.get('claims') as FormArray;
  }

  addClaim(claimText = ''): void {
    this.claims.push(this.fb.control(claimText, [Validators.required, Validators.minLength(10)]));
  }

  removeClaim(index: number): void {
    this.claims.removeAt(index);
  }

  // --- Form Value Change Triggers ---
  onRepoSourceChange(source: 'github' | 'zip'): void {
    const repoUrlCtrl = this.jobForm.get('repoUrl');
    const repoFileCtrl = this.jobForm.get('repoFile');

    if (source === 'github') {
      repoUrlCtrl?.setValidators([Validators.required, githubUrlValidator()]);
      repoFileCtrl?.clearValidators();
      this.selectedRepoFile.set(null);
      this.jobForm.patchValue({ repoFile: null });
    } else {
      repoUrlCtrl?.clearValidators();
      repoFileCtrl?.setValidators([Validators.required]);
      this.jobForm.patchValue({ repoUrl: '' });
    }
    repoUrlCtrl?.updateValueAndValidity();
    repoFileCtrl?.updateValueAndValidity();
  }

  onDataSourceChange(source: 'zip' | 'in_repo'): void {
    const dataFileCtrl = this.jobForm.get('dataFile');

    if (source === 'zip') {
      dataFileCtrl?.setValidators([Validators.required]);
    } else {
      dataFileCtrl?.clearValidators();
      this.selectedDataFile.set(null);
      this.jobForm.patchValue({ dataFile: null });
    }
    dataFileCtrl?.updateValueAndValidity();
  }

  // --- Mock File Selection Handlers ---
  onPdfSelect(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      if (file.type !== 'application/pdf') {
        alert('Please upload a valid PDF file.');
        return;
      }
      this.selectedPdfFile.set({ name: file.name, size: file.size });
      this.jobForm.patchValue({ pdfFile: file });
      this.jobForm.get('pdfFile')?.markAsDirty();
    }
  }

  onRepoFileSelect(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      this.selectedRepoFile.set({ name: file.name, size: file.size });
      this.jobForm.patchValue({ repoFile: file });
      this.jobForm.get('repoFile')?.markAsDirty();
    }
  }

  onDataFileSelect(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      this.selectedDataFile.set({ name: file.name, size: file.size });
      this.jobForm.patchValue({ dataFile: file });
      this.jobForm.get('dataFile')?.markAsDirty();
    }
  }

  // --- Submission ---
  onSubmit(): void {
    if (this.jobForm.invalid) {
      Object.keys(this.jobForm.controls).forEach(key => {
        const control = this.jobForm.get(key);
        control?.markAsTouched();
      });
      return;
    }

    const val = this.jobForm.value;
    
    this.jobService.createJob(
      val.title,
      val.pdfFile,
      val.repoSource,
      val.repoSource === 'github' ? val.repoUrl : val.repoFile,
      val.dataSource,
      val.dataSource === 'zip' ? val.dataFile : undefined,
      val.claims
    ).subscribe({
      next: (job) => {
        this.submitted.emit(job.id);
      },
      error: (err) => {
        console.error('Submission failed:', err);
        alert('Failed to submit job: ' + (err.error?.detail || err.message));
      }
    });
  }
}
