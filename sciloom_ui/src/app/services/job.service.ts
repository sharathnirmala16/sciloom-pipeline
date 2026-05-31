import { Injectable, signal, computed, effect } from '@angular/core';
import { Job, JobStage, Claim, JobLog } from '../types/job.types';

@Injectable({
  providedIn: 'root'
})
export class JobService {
  // Signals for application state
  private readonly _jobs = signal<Job[]>([]);
  private readonly _stages = signal<Record<string, JobStage[]>>({});
  private readonly _claims = signal<Record<string, Claim[]>>({});
  private readonly _logs = signal<Record<string, JobLog[]>>({});

  // Computed public read-only state
  public readonly jobs = computed(() => this._jobs());

  constructor() {
    this.loadFromLocalStorage();

    // Setup an effect to auto-save to localStorage whenever state changes
    effect(() => {
      localStorage.setItem('sciloom_jobs', JSON.stringify(this._jobs()));
      localStorage.setItem('sciloom_stages', JSON.stringify(this._stages()));
      localStorage.setItem('sciloom_claims', JSON.stringify(this._claims()));
      localStorage.setItem('sciloom_logs', JSON.stringify(this._logs()));
    });
  }

  private loadFromLocalStorage(): void {
    try {
      const storedJobs = localStorage.getItem('sciloom_jobs');
      const storedStages = localStorage.getItem('sciloom_stages');
      const storedClaims = localStorage.getItem('sciloom_claims');
      const storedLogs = localStorage.getItem('sciloom_logs');

      if (storedJobs) this._jobs.set(JSON.parse(storedJobs));
      if (storedStages) this._stages.set(JSON.parse(storedStages));
      if (storedClaims) this._claims.set(JSON.parse(storedClaims));
      if (storedLogs) this._logs.set(JSON.parse(storedLogs));
    } catch (e) {
      console.error('Error loading data from localStorage, resetting...', e);
      this.clearAll();
    }
  }

  public clearAll(): void {
    this._jobs.set([]);
    this._stages.set({});
    this._claims.set({});
    this._logs.set({});
    localStorage.clear();
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

  /**
   * Submits a new job and kicks off mock Stage 1 (Provisioning) execution.
   */
  public createJob(
    title: string,
    pdfFile: File | { name: string; size: number },
    repoSource: 'github' | 'zip',
    repoUrlOrFile: string | File | { name: string },
    dataSource: 'zip' | 'in_repo',
    dataFile?: File | { name: string },
    manualClaims: string[] = []
  ): string {
    const jobId = `job_${Date.now()}`;
    
    // Create new job item
    const newJob: Job = {
      id: jobId,
      title: title || `Job ${jobId.substring(4)}`,
      pdfPath: `jobs/${jobId}/${pdfFile.name}`,
      pdfName: pdfFile.name,
      repoSource,
      repoUrl: repoSource === 'github' ? (repoUrlOrFile as string) : undefined,
      repoFileName: repoSource === 'zip' ? (repoUrlOrFile as File).name : undefined,
      dataSource,
      dataFileName: dataSource === 'zip' && dataFile ? dataFile.name : undefined,
      status: 'CREATED',
      currentStage: 'PROVISIONING',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    // Create default stage configurations for the 5 pipeline stages
    const defaultStages: JobStage[] = [
      {
        id: `${jobId}_stage_1`,
        jobId,
        stageName: 'PROVISIONING',
        status: 'pending'
      },
      {
        id: `${jobId}_stage_2`,
        jobId,
        stageName: 'CLAIM_EXTRACTION',
        status: 'pending'
      },
      {
        id: `${jobId}_stage_3`,
        jobId,
        stageName: 'CODE_EXECUTION',
        status: 'pending'
      },
      {
        id: `${jobId}_stage_4`,
        jobId,
        stageName: 'CLAIM_REPLICATION',
        status: 'pending'
      },
      {
        id: `${jobId}_stage_5`,
        jobId,
        stageName: 'DTREG_GENERATION',
        status: 'pending'
      }
    ];

    // Add user provided claims if any
    const claimsList: Claim[] = manualClaims.map((claimText, idx) => ({
      id: `${jobId}_claim_${idx + 1}`,
      jobId,
      claimText,
      source: 'user',
      replicated: false,
      createdAt: new Date().toISOString()
    }));

    // Update state signals
    this._jobs.update(prev => [newJob, ...prev]);
    this._stages.update(prev => ({ ...prev, [jobId]: defaultStages }));
    this._claims.update(prev => ({ ...prev, [jobId]: claimsList }));
    this._logs.update(prev => ({ ...prev, [jobId]: [] }));

    // Start provisioning process
    this.runMockProvisioning(jobId);

    return jobId;
  }

  /**
   * Resets/retries Stage 1 for a failed job.
   */
  public retryJobStage1(jobId: string): void {
    const job = this.getJobById(jobId)();
    if (!job || job.status !== 'FAILED') return;

    // Reset status to CREATED
    this._jobs.update(prev =>
      prev.map(j => (j.id === jobId ? { ...j, status: 'CREATED', updatedAt: new Date().toISOString() } : j))
    );

    // Reset Stage 1 status
    this._stages.update(prev => {
      const stagesList = prev[jobId] || [];
      return {
        ...prev,
        [jobId]: stagesList.map(s => (s.stageName === 'PROVISIONING' ? { ...s, status: 'pending', errorLog: undefined, sandboxInfo: undefined } : s))
      };
    });

    // Clear logs
    this._logs.update(prev => ({ ...prev, [jobId]: [] }));

    // Run again
    this.runMockProvisioning(jobId);
  }

  /**
   * Transitions job to Stage 2: Claim Extraction (Mock advancement).
   */
  public advanceToStage2(jobId: string): void {
    this._jobs.update(prev =>
      prev.map(j =>
        j.id === jobId ? { ...j, status: 'CLAIM_EXTRACTION', currentStage: 'CLAIM_EXTRACTION', updatedAt: new Date().toISOString() } : j
      )
    );

    this._stages.update(prev => {
      const stagesList = prev[jobId] || [];
      return {
        ...prev,
        [jobId]: stagesList.map(s => {
          if (s.stageName === 'PROVISIONING') return { ...s, status: 'completed' as const };
          if (s.stageName === 'CLAIM_EXTRACTION') return { ...s, status: 'running' as const, startedAt: new Date().toISOString() };
          return s;
        })
      };
    });

    this.addLog(jobId, 'INFO', 'Successfully advanced pipeline to Stage 2: Claim Extraction');
    this.addLog(jobId, 'INFO', 'Initializing Claim Extraction Agent...');
  }

  /**
   * Deletes a job and its related data.
   */
  public deleteJob(jobId: string): void {
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
  }

  // --- Logger Helpers ---
  private addLog(jobId: string, level: 'INFO' | 'WARN' | 'ERROR', message: string): void {
    const newLog: JobLog = {
      timestamp: new Date().toLocaleTimeString(),
      level,
      message
    };
    this._logs.update(prev => ({
      ...prev,
      [jobId]: [...(prev[jobId] || []), newLog]
    }));
  }

  // --- Mock Provisioning Simulation ---
  private runMockProvisioning(jobId: string): void {
    const job = this._jobs().find(j => j.id === jobId);
    if (!job) return;

    // Determine if we should mock a failure (if title or URL has 'fail')
    const shouldFail =
      job.title.toLowerCase().includes('fail') ||
      (job.repoUrl && job.repoUrl.toLowerCase().includes('fail'));

    // Step-by-step logs and status transitions
    const logSteps = [
      { delay: 100, action: () => {
        // Mark job as PROVISIONING, stage 1 as running
        this.updateJobStatus(jobId, 'PROVISIONING');
        this.updateStageStatus(jobId, 'PROVISIONING', 'running');
        this.addLog(jobId, 'INFO', `Initializing provisioning for job ${jobId}...`);
      }},
      { delay: 1000, action: () => {
        this.addLog(jobId, 'INFO', `Creating workspace folder: jobs/${jobId}/`);
      }},
      { delay: 2000, action: () => {
        this.addLog(jobId, 'INFO', `Uploading research paper PDF: ${job.pdfName}...`);
      }},
      { delay: 3000, action: () => {
        if (job.repoSource === 'github') {
          this.addLog(jobId, 'INFO', `Cloning code repository from GitHub URL: ${job.repoUrl}...`);
        } else {
          this.addLog(jobId, 'INFO', `Extracting uploaded repository archive: ${job.repoFileName}...`);
        }
      }},
      { delay: 4500, action: () => {
        this.addLog(jobId, 'INFO', `Repository successfully setup at jobs/${jobId}/REPO/`);
        if (job.dataSource === 'zip') {
          this.addLog(jobId, 'INFO', `Extracting additional dataset archive: ${job.dataFileName}...`);
        } else {
          this.addLog(jobId, 'INFO', `Dataset marked as present in code repository workspace.`);
        }
      }},
      { delay: 6000, action: () => {
        this.addLog(jobId, 'INFO', `Starting Gemini Vision API OCR extraction on paper PDF...`);
        this.addLog(jobId, 'INFO', `Analyzing document formatting, images, tables and equations...`);
      }},
      { delay: 8000, action: () => {
        if (shouldFail) {
          this.addLog(jobId, 'ERROR', `FATAL ERROR: Gemini API call failed with quota limits / API key validation failure!`);
          this.updateJobStatus(jobId, 'FAILED');
          this.updateStageStatus(jobId, 'PROVISIONING', 'failed', 'Gemini Vision API quota exceeded. Please check configuration key.');
        } else {
          this.addLog(jobId, 'INFO', `Gemini Vision OCR successfully parsed all sections.`);
          this.addLog(jobId, 'INFO', `Saving parsed content to markdown file: RESEARCH_PAPER.md`);
        }
      }},
      { delay: 9500, action: () => {
        if (!shouldFail) {
          this.addLog(jobId, 'INFO', `Job setup completed. Directory structure finalized.`);
          this.addLog(jobId, 'INFO', `SQLite database updated: job status = PROVISIONED`);
          this.updateJobStatus(jobId, 'PROVISIONED');
          this.updateStageStatus(jobId, 'PROVISIONING', 'completed');

          // Generate simulated claims if the user hasn't added manual ones
          const claims = this._claims()[jobId] || [];
          if (claims.length === 0) {
            const autoClaims: Claim[] = [
              {
                id: `${jobId}_claim_1`,
                jobId,
                claimText: 'The proposed SciLoom model improves OCR extraction accuracy by 14% compared to traditional Tesseract pipelines.',
                source: 'agent',
                replicated: false,
                createdAt: new Date().toISOString()
              },
              {
                id: `${jobId}_claim_2`,
                jobId,
                claimText: 'The DTREG generation execution achieves fully valid JSON-LD outputs in 98.7% of replication jobs.',
                source: 'agent',
                replicated: false,
                createdAt: new Date().toISOString()
              }
            ];
            this._claims.update(prev => ({ ...prev, [jobId]: autoClaims }));
          }
        }
      }}
    ];

    // Execute steps sequentially with setTimeout
    logSteps.forEach(step => {
      setTimeout(() => {
        // Double check if the job still exists before executing action
        if (this._jobs().some(j => j.id === jobId)) {
          step.action();
        }
      }, step.delay);
    });
  }

  private updateJobStatus(jobId: string, status: Job['status']): void {
    this._jobs.update(prev =>
      prev.map(j => (j.id === jobId ? { ...j, status, updatedAt: new Date().toISOString() } : j))
    );
  }

  private updateStageStatus(
    jobId: string,
    stageName: JobStage['stageName'],
    status: JobStage['status'],
    errorLog?: string
  ): void {
    this._stages.update(prev => {
      const stagesList = prev[jobId] || [];
      return {
        ...prev,
        [jobId]: stagesList.map(s => {
          if (s.stageName === stageName) {
            const updated: JobStage = { ...s, status, errorLog, updatedAt: new Date().toISOString() };
            if (status === 'running') {
              updated.startedAt = new Date().toISOString();
            } else if (status === 'completed' || status === 'failed') {
              updated.completedAt = new Date().toISOString();
              if (status === 'failed') {
                updated.sandboxInfo = {
                  sandboxId: `sbx-${jobId}`,
                  connectionCommand: `sbx exec -j ${jobId} -- bash`
                };
              }
            }
            return updated;
          }
          return s;
        })
      };
    });
  }

  // --- Simulated Stage 1 Files Generator ---
  public getSimulatedOcrMarkdown(jobId: string): string {
    const job = this.getJobById(jobId)();
    const title = job ? job.title : 'SciLoom Research Paper';
    const pdfName = job ? job.pdfName : 'paper.pdf';

    return `# ${title}

## Abstract
This document presents the replication workspace of ${pdfName}. In this paper, we propose SciLoom, a deterministic finite state machine orchestration layer built with Pydantic Graph and Python. SciLoom automates the replication of quantitative scientific claims by using containerized code sandboxes and LLM-powered verification agents. Our experiments demonstrate high reliability in recovering statistical claims.

## 1. Introduction
Quantitative science relies heavily on reproducibility. However, setting up external repositories, installing matching environments, and verifying statistical equations manually takes significant human developer hours. We present a system architecture that solves this...

## 2. Experimental Setup
We evaluate the claim extraction capabilities on a test set of 120 research papers.
The results show two critical claims:
- **Claim 1**: The SciLoom model improves OCR extraction accuracy by 14% compared to traditional Tesseract pipelines.
- **Claim 2**: The DTREG generation execution achieves fully valid JSON-LD outputs in 98.7% of replication jobs.

## 3. Discussion
The sandboxing architecture prevents script execution side-effects, guaranteeing clean workspace state.
`;
  }

  public getSimulatedRepoFiles(jobId: string) {
    const job = this.getJobById(jobId)();
    const isGit = job?.repoSource === 'github';

    return [
      { name: 'README.md', isDir: false, size: 2140 },
      { name: 'requirements.txt', isDir: false, size: 342 },
      { name: 'setup.py', isDir: false, size: 1080 },
      {
        name: 'src',
        isDir: true,
        children: [
          { name: 'main.py', isDir: false, size: 4560 },
          { name: 'utils.py', isDir: false, size: 1820 },
          { name: 'model.py', isDir: false, size: 12400 },
          { name: '__init__.py', isDir: false, size: 55 }
        ]
      },
      {
        name: 'data',
        isDir: true,
        children: [
          { name: 'dataset.csv', isDir: false, size: 412950 },
          { name: 'config.json', isDir: false, size: 840 }
        ]
      },
      ...(isGit ? [{ name: '.gitignore', isDir: false, size: 120 }, { name: '.git', isDir: true, children: [] }] : [])
    ];
  }
}
