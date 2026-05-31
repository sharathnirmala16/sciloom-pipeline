# SciLoom Pipeline

## Goal

The goal of this project is to take any research paper and replicate the results of the paper with the help of AI Agents. It will aid a human in verifying the results of a paper through replication. Once the claims are replicated and verified, a dtreg script will be generated to automatically generate a JSON-LD file which will be compatible with TIB Loom. Since each job can take a long time and an agent can fail, or get stuck in between, the entire process is made up of stages and can be resumed from where it left off. This ensures reliability and efficiency. A human can pause the process and resume it later. Each stage can be run independently.

---

## Techstack

| Layer | Technology | Role |
|-------|-----------|------|
| **Frontend** | Angular 21, PrimeNG | Dashboard UI — job submission, monitoring, human review |
| **Backend** | Python, FastAPI | REST API, pipeline orchestration |
| **Agent Orchestration** | PydanticAI, Pydantic Graph | Deterministic process graph (FSM) for stage transitions; PydanticAI agents at each graph node |
| **Agent Execution** | OpenCode | LLM-powered agents invoked at each Pydantic Graph node |
| **Database** | SQLite | Persistent storage for jobs, claims, stage state, errors |
| **Notifications** | Honker | SQLite NOTIFY/LISTEN for cross-process orchestration and real-time notifications without external brokers |
| **Sandboxing** | Docker (sbx CLI) | Isolated execution environments per job |
| **OCR** | Gemini Vision API | PDF → Markdown conversion |

---

## Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Angular 21 + PrimeNG UI                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │  Submit  │ │  Claims  │ │ Sandbox  │ │ Replicat │ │ Download │ │
│  │  Paper   │ │  Editor  │ │  Logs    │ │ Results  │ │ Outputs  │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │
└───────┼────────────┼────────────┼────────────┼────────────┼────────┘
        │            │            │            │            │
        ▼            ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                                │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Pydantic Graph (FSM Orchestrator)               │   │
│  │                                                              │   │
│  │  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐     │   │
│  │  │ Provisn │──▶│ Claims  │──▶│ Code    │──▶│ Claim   │──┐  │   │
│  │  │         │   │ Extract │   │ Exec    │   │ Replic  │  │  │   │
│  │  └─────────┘   └─────────┘   └─────────┘   └─────────┘  │  │   │
│  │                                                          │  │   │
│  │                               ┌─────────┐                │  │   │
│  │                               │ DTREG   │◀───────────────┘  │   │
│  │                               │ Gen     │                   │   │
│  │                               └─────────┘                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐           │
│  │  SQLite DB    │  │   Honker      │  │ Sandbox Mgr   │           │
│  │  (Jobs,Claims │  │  (NOTIFY /    │  │ (Docker sbx)  │           │
│  │   Stages)     │  │   LISTEN)     │  │               │           │
│  └───────────────┘  └───────────────┘  └───────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
        │                                        │
        ▼                                        ▼
┌───────────────┐                    ┌───────────────────────┐
│  jobs/job_N/  │                    │  Docker Sandbox       │
│  (PDF, MD,    │                    │  (venv, repo, scripts │
│   REPO/)      │                    │   sciloom_output/)    │
└───────────────┘                    └───────────────────────┘
```

### Orchestration Model

**Pydantic Graph** provides the deterministic finite state machine (FSM) that governs stage transitions. Each node in the graph represents a pipeline stage. At each node, an **OpenCode agent** (powered by PydanticAI) is invoked to perform the actual work. The graph ensures:

- Stages execute in a deterministic, defined order
- Transitions are type-safe (edges defined by return type hints)
- State is explicitly passed between nodes via a shared state object
- Failed stages can be resumed without re-running completed stages

**Honker** provides SQLite-native NOTIFY/LISTEN semantics for:

- Notifying the UI when a stage completes or fails (without polling)
- Coordinating multiple concurrent job processes
- Triggering stage transitions across processes atomically within the same DB transaction

---

## Pipeline Flow

The UI is the primary interface through which a user interacts with the system. Each job progresses through 5 stages, with human intervention points between stages.

### Stage 1: Provisioning (Job Setup)

**Trigger:** User submits a new job via the UI.

**User Input:**
- Research paper PDF (required)
- Claims (optional — can be provided or auto-extracted in Stage 2)
- Code repository: GitHub URL **or** uploaded ZIP file
- Data: ZIP file upload **or** flag indicating data is in the repo

**Backend Actions:**
1. Create `jobs/job_{id}/` directory
2. Store the PDF in the job folder
3. Clone the repo (if GitHub URL) or extract the ZIP into `jobs/job_{id}/REPO/`
4. Convert the PDF to markdown using OCR (Gemini Vision) → `RESEARCH_PAPER.md`
5. Store the markdown file in the job folder
6. Initialize the job record in SQLite with status `PROVISIONED`

**Output:** `jobs/job_{id}/` containing `paper.pdf`, `RESEARCH_PAPER.md`, `REPO/`

---

### Stage 2: Claim Extraction

**Branching Logic:**

- **If the user provided claims:** Store them directly in the SQLite DB under the job ID. Skip agent invocation. Mark stage as `COMPLETE`.
- **If the user did not provide claims:** Invoke the **Claim Extraction Agent** using the markdown version of the paper. The user can start the job and leave — the agent runs asynchronously. Once claims are generated, they are stored in the SQLite DB under the job ID.

**Human-in-the-Loop:** Before proceeding to Stage 3, the user **can review, edit, add, or remove claims** through the UI. The stage does not auto-advance — the user explicitly confirms the claims and triggers the next stage.

**Agent:** `claim-extraction-agent` (OpenCode) — reads `RESEARCH_PAPER.md`, outputs structured claims.

**Output:** Claims stored in SQLite (claim_id, claim_text, metrics, evidence, job_id).

---

### Stage 3: Code Execution (Repo Setup)

**Purpose:** Get the research paper's code repository running inside an isolated sandbox.

**Process:**
1. Spin up a Docker sandbox tagged with the job ID via `sbx start`
2. Copy the code repo from `jobs/job_{id}/REPO/` into the sandbox
3. Install all required libraries inside the sandbox (venv creation, dependency installation)
4. The agent attempts to get the repo running (resolve import errors, missing dependencies, environment issues)

**Success Path:** If the agent gets the repo running successfully → mark stage as `COMPLETE` → user can proceed to Stage 4.

**Failure Path:** If the agent fails:
- Store the error details in SQLite
- Store instructions on how to access the sandbox (sandbox ID, connection command)
- Display the error and sandbox access info in the UI
- The user can SSH/exec into the sandbox manually, make fixes, and retry

**Agent:** Code Execution Agent (OpenCode) — environment setup specialist.

**Sandbox Lifecycle:** The sandbox is created here and **persists through Stages 3–5**. It is only deleted with the user's explicit permission from the UI after Stage 5 is complete.

**Output:** Running sandbox with functional repo environment.

---

### Stage 4: Claim Replication

**Purpose:** Replicate each quantitative claim from Stage 2 using the running repo from Stage 3.

**User Input (per claim):** From the UI, the user can attach:
- Written instructions for how to replicate the claim
- Screenshots showing expected output/behavior
- Any additional context the agent should know

**Process:**
1. The Claim Replication Agent receives:
   - The claims (from SQLite)
   - The running repo (inside the sandbox from Stage 3)
   - User-attached instructions and screenshots (per claim)
2. For each claim, the agent writes and executes a replication script
3. Compares computed results against the claim's expected metrics

**Success Path:** All claims replicated successfully → mark stage as `COMPLETE` → proceed to Stage 5.

**Failure Path:** If any claim fails:
- Store the error, traceback, and metric mismatch details in SQLite
- Display in the UI for the user to review
- User can access the sandbox to debug, attach updated instructions, and retry
- Sandbox remains alive

**Agent:** `claim-replication-agent` (OpenCode) — spawns subagents per claim with 260K token context budgets.

**Output:** Replication scripts and results inside the sandbox.

---

### Stage 5: DTREG Script Generation

**Purpose:** Generate the dtreg script that organises replicated claims and supporting evidence in the format TIB Loom requires, and produce the JSON-LD output.

**Process:**
1. The DTREG Generator Agent reads:
   - Replicated claims and their results (from Stages 2 & 4)
   - The repo contents and replication artifacts (from the sandbox)
2. Generates a dtreg Python script that:
   - Loads appropriate DTR schemas (ePIC or ORKG) via `dtreg.load_datatype()`
   - Populates schema instances with claim data and replication evidence
   - Serializes to JSON-LD via `dtreg.to_jsonld()`
3. Executes the script inside the sandbox
4. Creates a `sciloom_output/` folder inside the repo in the sandbox containing:
   - The dtreg script
   - The generated JSON-LD file
   - A summary report of the entire job

**Finalisation:**
1. The entire repo (now containing `sciloom_output/`) is copied back from the sandbox to `jobs/job_{id}/` on the host
2. The user can:
   - Access `jobs/job_{id}/` directly on the filesystem to get the repo with `sciloom_output/`
   - Download the entire output as a ZIP from the UI
3. **Only after this step**, with the user's explicit permission from the UI, the sandbox is deleted

**Agent:** DTREG Script Generator Agent (OpenCode) — uses all dtreg skills (dtr_interface, load_datatype, to_jsonld, extract_epic/orkg).

**Output:** `sciloom_output/` (dtreg script, JSON-LD, summary) inside the repo, synced to host.

---

## Concurrency

Multiple jobs can run concurrently. Each job has its own:
- Job directory (`jobs/job_{id}/`)
- Docker sandbox (tagged with job ID)
- Independent pipeline state in SQLite

**SQLite Locking:** WAL (Write-Ahead Logging) mode is used to allow concurrent reads while writes are serialized. Honker's transactional notifications ensure stage transitions and state updates are atomic — no data corruption across concurrent job processes.

---

## Data Model (SQLite)

```sql
-- Jobs table
CREATE TABLE jobs (
    id            TEXT PRIMARY KEY,
    title         TEXT,
    pdf_path      TEXT NOT NULL,
    repo_source   TEXT,              -- 'github' | 'zip'
    repo_url      TEXT,              -- GitHub URL (if applicable)
    data_source   TEXT,              -- 'zip' | 'in_repo'
    status        TEXT DEFAULT 'CREATED',
    current_stage TEXT DEFAULT 'PROVISIONING',
    sandbox_id    TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Stage tracking
CREATE TABLE stages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id        TEXT REFERENCES jobs(id),
    stage_name    TEXT NOT NULL,
    status        TEXT DEFAULT 'pending',
    error_log     TEXT,
    sandbox_info  TEXT,              -- JSON: how to access sandbox on failure
    started_at    DATETIME,
    completed_at  DATETIME,
    output_json   TEXT
);

-- Claims
CREATE TABLE claims (
    id            TEXT PRIMARY KEY,
    job_id        TEXT REFERENCES jobs(id),
    claim_text    TEXT NOT NULL,
    metrics       TEXT,
    evidence      TEXT,
    source        TEXT DEFAULT 'agent',  -- 'agent' | 'user'
    replicated    BOOLEAN DEFAULT FALSE,
    replication_error TEXT,
    user_instructions TEXT,          -- User-provided instructions for replication
    user_screenshots  TEXT,          -- JSON array of screenshot file paths
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## Job Directory Structure

```
jobs/job_{id}/
├── paper.pdf                         # Original uploaded PDF
├── RESEARCH_PAPER.md                 # OCR-extracted markdown
├── REPO/                             # Code repository (cloned or extracted)
│   ├── ...                           # Original repo contents
│   └── sciloom_output/               # (Synced back from sandbox after Stage 5)
│       ├── generate_loom.py          # Generated dtreg script
│       ├── record.jsonld             # JSON-LD for TIB Loom
│       └── SUMMARY.md               # Job summary report
└── user_attachments/                 # User-uploaded instructions & screenshots
    ├── CLAIM-001/
    │   ├── instructions.md
    │   └── screenshot_1.png
    └── CLAIM-002/
        └── instructions.md
```

---

## Agents

| Agent | Invoked At | Model | Key Skills |
|-------|-----------|-------|------------|
| **PDF Extractor** | Stage 1 | Gemini 3.5 Flash | Multimodal OCR |
| **Claim Extraction Agent** | Stage 2 | Gemini 3.5 Flash | Paper analysis, quantitative claim identification |
| **Code Execution Agent** | Stage 3 | Gemini 3.5 Flash | Environment setup, dependency resolution |
| **Claim Replication Agent** | Stage 4 | Gemini 3.5 Flash | Statistical replication, subagent orchestration |
| **DTREG Script Generator** | Stage 5 | Gemini 3.5 Flash | dtr_interface, load_datatype, to_jsonld, extract_epic, extract_orkg |

---

## Backend Structure

```
sciloom_pipeline/
├── __init__.py
├── main.py                          # FastAPI app entry point
├── config.py                        # Settings (pydantic-settings)
├── models/
│   ├── job.py                       # Job, JobCreate, JobStatus
│   ├── claim.py                     # Claim, ClaimUpdate
│   └── stage.py                     # Stage, StageStatus
├── services/
│   ├── job_service.py               # Job CRUD, directory management
│   ├── pipeline_service.py          # Pydantic Graph FSM, stage transitions
│   ├── sandbox_service.py           # Docker sandbox lifecycle (sbx wrapper)
│   └── agent_service.py             # OpenCode agent invocation
├── graph/
│   ├── __init__.py
│   ├── nodes.py                     # Pydantic Graph BaseNode per stage
│   ├── state.py                     # Shared pipeline state dataclass
│   └── edges.py                     # Stage transition definitions
├── routes/
│   ├── jobs.py                      # POST /jobs, GET /jobs/{id}
│   ├── claims.py                    # GET/PUT /jobs/{id}/claims
│   ├── pipeline.py                  # POST /jobs/{id}/advance, /retry
│   └── downloads.py                 # GET /jobs/{id}/download
├── document_processing/
│   └── pdf_extractor.py             # (existing) Gemini Vision OCR
├── db/
│   ├── database.py                  # SQLite + WAL mode + Honker setup
│   └── migrations/
└── notifications/
    └── honker.py                    # Honker NOTIFY/LISTEN wrappers
```