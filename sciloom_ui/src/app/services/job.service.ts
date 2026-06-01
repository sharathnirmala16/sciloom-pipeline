import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { Job, JobStage, Claim, JobLog } from '../types/job.types';

@Injectable({
  providedIn: 'root'
})
export class JobService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = 'http://localhost:8000/api';

  // Signals for application state
  private readonly _jobs = signal<Job[]>([]);
  private readonly _stages = signal<Record<string, JobStage[]>>({});
  private readonly _claims = signal<Record<string, Claim[]>>({});
  private readonly _logs = signal<Record<string, JobLog[]>>({});
  private readonly _ocrMarkdown = signal<Record<string, string>>({});
  private readonly _repoFiles = signal<Record<string, any[]>>({});

  // Computed public read-only state
  public readonly jobs = computed(() => this._jobs());

  private activeEventSource: EventSource | null = null;

  constructor() {
    this.loadJobs();
  }

  /**
   * Fetches all jobs from backend.
   */
  public loadJobs(): void {
    this.http.get<Job[]>(`${this.apiUrl}/jobs`).subscribe({
      next: jobs => {
        this._jobs.set(jobs);
      },
      error: err => console.error('Failed to load jobs:', err)
    });
  }

  // Getters for specific jobs, stages, claims, and logs
  public getJobById(id: string) {
    return computed(() => this._jobs().find(job => job.id === id) || null);
  }

  public getStagesForJob(jobId: string) {
    return computed(() => this._stages()[jobId] || []);
  }

  public getClaimsForJob(jobId: string) {
    return computed(() => this._claims()[jobId] || []);
  }

  public getLogsForJob(jobId: string) {
    return computed(() => this._logs()[jobId] || []);
  }

  public getSimulatedOcrMarkdown(jobId: string): string {
    return this._ocrMarkdown()[jobId] || '';
  }

  public getSimulatedRepoFiles(jobId: string): any[] {
    return this._repoFiles()[jobId] || [];
  }

  /**
   * Submits a new job to the backend using FormData.
   */
  public createJob(
    title: string,
    pdfFile: File,
    repoSource: 'github' | 'zip',
    repoUrlOrFile: string | File,
    dataSource: 'zip' | 'in_repo',
    dataFile?: File,
    manualClaims: string[] = []
  ): Observable<Job> {
    const formData = new FormData();
    formData.append('title', title);
    formData.append('repoSource', repoSource);
    formData.append('dataSource', dataSource);
    
    if (repoSource === 'github') {
      formData.append('repoUrl', repoUrlOrFile as string);
    } else if (repoUrlOrFile instanceof File) {
      formData.append('repoFile', repoUrlOrFile);
    }

    if (dataSource === 'zip' && dataFile) {
      formData.append('dataFile', dataFile);
    }

    if (pdfFile) {
      formData.append('pdfFile', pdfFile);
    }

    if (manualClaims && manualClaims.length > 0) {
      formData.append('manualClaims', JSON.stringify(manualClaims));
    }

    return this.http.post<Job>(`${this.apiUrl}/jobs`, formData).pipe(
      tap(newJob => {
        this._jobs.update(prev => [newJob, ...prev]);
      })
    );
  }

  /**
   * Resets/retries Stage 1 for a failed job.
   */
  public retryJobStage1(jobId: string): void {
    // Reset local state first to feel responsive
    this._jobs.update(prev =>
      prev.map(j => (j.id === jobId ? { ...j, status: 'PROVISIONING', updatedAt: new Date().toISOString() } : j))
    );
    this._stages.update(prev => {
      const stagesList = prev[jobId] || [];
      return {
        ...prev,
        [jobId]: stagesList.map(s => (s.stageName === 'PROVISIONING' ? { ...s, status: 'running' } : s))
      };
    });
    this._logs.update(prev => ({ ...prev, [jobId]: [] }));

    this.http.post(`${this.apiUrl}/jobs/${jobId}/retry`, {}).subscribe({
      next: () => {
        this.connectLogsSse(jobId);
      },
      error: err => {
        console.error('Failed to retry job stage 1:', err);
        // Refresh statuses to sync with actual backend state on failure
        this.refreshJobStatusAndStages(jobId);
      }
    });
  }

  /**
   * Saves user-edited OCR markdown content to the backend.
   */
  public updateOcrMarkdown(jobId: string, markdown: string): void {
    this.http.put(`${this.apiUrl}/jobs/${jobId}/ocr`, { markdown }).subscribe({
      next: () => {
        this._ocrMarkdown.update(prev => ({ ...prev, [jobId]: markdown }));
        // Refresh job to get updated ocrPageCharCounts
        this.http.get<Job>(`${this.apiUrl}/jobs/${jobId}`).subscribe({
          next: job => this._jobs.update(prev => prev.map(j => j.id === jobId ? job : j))
        });
      },
      error: err => console.error('Failed to update OCR markdown:', err)
    });
  }

  /**
   * Enqueues an OCR-only retry for an already-provisioned job.
   */
  public retryOcr(jobId: string): void {
    // Update local state temporarily to feel fast and toggle terminal view instantly
    this._jobs.update(prev =>
      prev.map(j =>
        j.id === jobId ? { ...j, status: 'PROVISIONING', updatedAt: new Date().toISOString() } : j
      )
    );
    this.http.post(`${this.apiUrl}/jobs/${jobId}/ocr/retry`, {}).subscribe({
      next: () => {
        this.connectLogsSse(jobId);
      },
      error: err => console.error('Failed to queue OCR retry:', err)
    });
  }

  /**
   * Transitions job to Stage 2: Claim Extraction.
   */
  public advanceToStage2(jobId: string): void {
    // Update local state temporarily to feel fast
    this._jobs.update(prev =>
      prev.map(j =>
        j.id === jobId ? { ...j, status: 'CLAIM_EXTRACTION', currentStage: 'CLAIM_EXTRACTION', updatedAt: new Date().toISOString() } : j
      )
    );

    this.http.post(`${this.apiUrl}/jobs/${jobId}/advance`, {}).subscribe({
      next: () => {
        this.refreshJobStatusAndStages(jobId);
      },
      error: err => {
        console.error('Failed to advance job to stage 2:', err);
        this.refreshJobStatusAndStages(jobId);
      }
    });
  }

  /**
   * Deletes a job from the backend.
   */
  public deleteJob(jobId: string): void {
    this.http.delete(`${this.apiUrl}/jobs/${jobId}`).subscribe({
      next: () => {
        this._jobs.update(prev => prev.filter(j => j.id !== jobId));
        this._stages.update(prev => {
          const next = { ...prev };
          delete next[jobId];
          return next;
        });
        this._claims.update(prev => {
          const next = { ...prev };
          delete next[jobId];
          return next;
        });
        this._logs.update(prev => {
          const next = { ...prev };
          delete next[jobId];
          return next;
        });
      },
      error: err => console.error('Failed to delete job:', err)
    });
  }

  /**
   * Loads all details for a job: stages, claims, OCR markdown, files list, and logs.
   */
  public loadJobDetails(jobId: string): void {
    // 1. Fetch current job info to ensure _jobs has it
    this.http.get<Job>(`${this.apiUrl}/jobs/${jobId}`).subscribe({
      next: job => {
        this._jobs.update(prev => {
          const index = prev.findIndex(j => j.id === jobId);
          if (index > -1) {
            const nextJobs = [...prev];
            nextJobs[index] = job;
            return nextJobs;
          } else {
            return [job, ...prev];
          }
        });
      }
    });

    // 2. Fetch stages
    this.http.get<JobStage[]>(`${this.apiUrl}/jobs/${jobId}/stages`).subscribe({
      next: stages => {
        this._stages.update(prev => ({ ...prev, [jobId]: stages }));
      }
    });

    // 3. Fetch claims
    this.http.get<Claim[]>(`${this.apiUrl}/jobs/${jobId}/claims`).subscribe({
      next: claims => {
        this._claims.update(prev => ({ ...prev, [jobId]: claims }));
      }
    });

    // 4. Fetch OCR markdown
    this.http.get<{ markdown: string }>(`${this.apiUrl}/jobs/${jobId}/ocr`).subscribe({
      next: res => {
        this._ocrMarkdown.update(prev => ({ ...prev, [jobId]: res.markdown }));
      },
      error: () => {
        this._ocrMarkdown.update(prev => ({ ...prev, [jobId]: '' }));
      }
    });

    // 5. Fetch Files
    this.http.get<any[]>(`${this.apiUrl}/jobs/${jobId}/files`).subscribe({
      next: files => {
        this._repoFiles.update(prev => ({ ...prev, [jobId]: files }));
      },
      error: () => {
        this._repoFiles.update(prev => ({ ...prev, [jobId]: [] }));
      }
    });

    // 6. Connect SSE logs
    this.connectLogsSse(jobId);
  }

  /**
   * Connects to EventSource (SSE) log stream from FastAPI.
   */
  public connectLogsSse(jobId: string): void {
    if (this.activeEventSource) {
      this.activeEventSource.close();
      this.activeEventSource = null;
    }

    // Reset logs array
    this._logs.update(prev => ({ ...prev, [jobId]: [] }));

    const eventSource = new EventSource(`${this.apiUrl}/jobs/${jobId}/logs`);
    this.activeEventSource = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const logData = JSON.parse(event.data);
        const newLog: JobLog = {
          timestamp: logData.timestamp,
          level: logData.level,
          message: logData.message
        };
        this._logs.update(prev => {
          const currentLogs = prev[jobId] || [];
          return {
            ...prev,
            [jobId]: [...currentLogs, newLog]
          };
        });

        // Whenever state transition occurs, reload job status/stages/files/ocr
        if (logData.message.includes('Advanced pipeline stage') || 
            logData.message.includes('completed') || 
            logData.message.includes('failed') ||
            logData.message.includes('status =') ||
            logData.message.includes('successfully parsed') ||
            logData.message.includes('cloned successfully') ||
            logData.message.includes('extracted successfully') ||
            logData.message.includes('setup completed') ||
            logData.message.includes('database updated')) {
          this.refreshJobStatusAndStages(jobId);
        }
      } catch (e) {
        console.error('Error parsing SSE log:', e);
      }
    };

    eventSource.onerror = (err) => {
      console.error('SSE EventSource error:', err);
    };
  }

  /**
   * Disconnects active SSE log stream.
   */
  public disconnectLogsSse(): void {
    if (this.activeEventSource) {
      this.activeEventSource.close();
      this.activeEventSource = null;
    }
  }

  private refreshJobStatusAndStages(jobId: string): void {
    this.http.get<Job>(`${this.apiUrl}/jobs/${jobId}`).subscribe({
      next: job => {
        this._jobs.update(prev => prev.map(j => j.id === jobId ? job : j));
      }
    });
    this.http.get<JobStage[]>(`${this.apiUrl}/jobs/${jobId}/stages`).subscribe({
      next: stages => {
        this._stages.update(prev => ({ ...prev, [jobId]: stages }));
      }
    });
    this.http.get<Claim[]>(`${this.apiUrl}/jobs/${jobId}/claims`).subscribe({
      next: claims => {
        this._claims.update(prev => ({ ...prev, [jobId]: claims }));
      }
    });
    this.http.get<any[]>(`${this.apiUrl}/jobs/${jobId}/files`).subscribe({
      next: files => {
        this._repoFiles.update(prev => ({ ...prev, [jobId]: files }));
      }
    });
    this.http.get<{ markdown: string }>(`${this.apiUrl}/jobs/${jobId}/ocr`).subscribe({
      next: res => {
        this._ocrMarkdown.update(prev => ({ ...prev, [jobId]: res.markdown }));
      }
    });
  }
}
