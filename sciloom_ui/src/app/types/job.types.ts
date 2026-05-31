export interface Job {
  id: string;
  title: string;
  pdfPath: string;
  pdfName: string;
  repoSource: 'github' | 'zip';
  repoUrl?: string;
  repoFileName?: string;
  dataSource: 'zip' | 'in_repo';
  dataFileName?: string;
  status: 'CREATED' | 'PROVISIONING' | 'PROVISIONED' | 'FAILED' | 'CLAIM_EXTRACTION' | 'RUNNING' | 'COMPLETED';
  currentStage: 'PROVISIONING' | 'CLAIM_EXTRACTION' | 'CODE_EXECUTION' | 'CLAIM_REPLICATION' | 'DTREG_GENERATION';
  sandboxId?: string;
  createdAt: string;
  updatedAt: string;
}

export interface JobStage {
  id: string;
  jobId: string;
  stageName: 'PROVISIONING' | 'CLAIM_EXTRACTION' | 'CODE_EXECUTION' | 'CLAIM_REPLICATION' | 'DTREG_GENERATION';
  status: 'pending' | 'running' | 'completed' | 'failed';
  errorLog?: string;
  sandboxInfo?: {
    sandboxId: string;
    connectionCommand: string;
  };
  startedAt?: string;
  completedAt?: string;
  updatedAt?: string;
  outputJson?: string;
}

export interface Claim {
  id: string;
  jobId: string;
  claimText: string;
  metrics?: string;
  evidence?: string;
  source: 'agent' | 'user';
  replicated: boolean;
  replicationError?: string;
  userInstructions?: string;
  userScreenshots?: string[];
  createdAt: string;
}

export interface JobLog {
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR';
  message: string;
}
