# SciLoom Pipeline Project Progress & Handover Note

## Stage 1, 2, 3, 4 & 5 Backend & UI Progress 🚀

All five stages of the SciLoom Pipeline are now represented in the UI:
*   **Stage 1 (Provisioning, OCR Extraction & Job Setup)**: Fully completed (Hierarchical UI Component + Backend).
*   **Stage 2 (Claim Extraction)**: Fully completed (Hierarchical UI Component + Backend).
*   **Stage 3 (Code Execution)**: Fully completed (Hierarchical UI Component + Backend).
*   **Stage 4 (Claim Replication)**: UI Component implemented & integrated.
*   **Stage 5 (DTREG Gen)**: UI Component implemented & integrated.

---

## 🎨 Frontend UI Components & Hierarchical Refactoring (Implemented)

All components are located in the [src/app/components](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components) directory, structured hierarchically:
- **`AppHeaderComponent`**: The shared top navigation bar and branding logo. See [app-header.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/app-header/app-header.component.ts).
- **`DashboardComponent`**: Displays registered jobs with PrimeNG Tables, custom pagination, search filters, and statistics summaries. See [dashboard.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/dashboard/dashboard.component.ts) and [dashboard.component.html](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/dashboard/dashboard.component.html).
- **`JobFormComponent`**: A Reactive form within a Modal Dialog for creating a new job. Handles validation of required inputs and file uploads. See [job-form.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/job-form/job-form.component.ts).
- **`JobDetailsComponent`**: High-level parent coordinator dashboard displaying the 5-stage timeline and rendering the corresponding child stage component. See [job-details.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/job-details/job-details.component.ts) and [job-details.component.html](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/job-details/job-details.component.html).

### Stage-Specific Child Components
Nested directly under the `job-details/` folder structure:
- **`StageProvisioningComponent`** (Stage 1): Renders workspace setup progress metrics, simulated orchestrator log stream, and contains nested workspace tabs for paper OCR markdown preview, file explorer, and claims list. See [stage-provisioning.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/job-details/stage-provisioning/stage-provisioning.component.ts).
- **`StageClaimExtractionComponent`** (Stage 2): Manages claim extraction agent log stream and embeds the claims editor component upon successful completion. See [stage-claim-extraction.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/job-details/stage-claim-extraction/stage-claim-extraction.component.ts).
- **`StageCodeExecutionComponent`** (Stage 3): dedicated UI for Stage 3 Code Execution. Features a 4-state visual layout (pending, running with auto-scrolling logs terminal, completed with live workspace link, and failed with connection command copy controls and delete sandbox actions). See [stage-code-execution.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/job-details/stage-code-execution/stage-code-execution.component.ts).
- **`StageClaimReplicationComponent`** (Stage 4): Handles claim replication status, retries, and progression triggers. See [stage-claim-replication.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/job-details/stage-claim-replication/stage-claim-replication.component.ts).
- **`StageDtregGenerationComponent`** (Stage 5): Renders Loom DTREG metadata json-ld generation state. See [stage-dtreg-generation.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/job-details/stage-dtreg-generation/stage-dtreg-generation.component.ts).

### Inner Utility Components
Nested directly under `job-details/` alongside their host components:
- **`OCRPreviewComponent`**: Markdown viewer and editor for research papers. Includes page character counts density grid, raw markdown text area, and OCR re-extraction confirmation controls. See [ocr-preview.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/job-details/ocr-preview/ocr-preview.component.ts).
- **`FileExplorerComponent`**: Recursive file explorer for repository trees. See [file-explorer.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/job-details/file-explorer/file-explorer.component.ts).
- **`ClaimsEditorComponent`**: Full-featured claims management UI for Stage 2 human-in-the-loop review. Features inline editing, claims additions/removals, and backend syncing. See [claims-editor.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/job-details/claims-editor/claims-editor.component.ts).

---

## 🎯 Stage 2: Claims Editor Integration

### Component Hierarchy
```
JobDetailsComponent (parent)
  └── StageClaimExtractionComponent (child)
        └── ClaimsEditorComponent (inner child, embedded in completed view)
```

### Stage 2 Views in `stage-claim-extraction.component.ts`
The `CLAIM_EXTRACTION` stage has dedicated views for all four pipeline states:
- **Running**: Live SSE terminal with spinner, agent log stream, and "Return to Dashboard" link.
- **Completed**: `<app-claims-editor>` with full edit/add/remove/save/advance capabilities.
- **Failed**: Error banner with claim extraction error log, retry button.
- **Pending**: Placeholder waiting for Stage 1 completion.

---

## ⚡ Stage 3: Code Execution Integration (Fully Implemented)

### Component Hierarchy
```
JobDetailsComponent (parent)
  └── StageCodeExecutionComponent (child)
```

### How Stage 3 Works
1. When Stage 2 (Claim Extraction) is approved, advancing enqueues a `code_execution` task.
2. The background worker spins up an isolated Docker container named `sbx-{job_id}` (using `sbx create opencode`).
3. The worker copies `RESEARCH_PAPER.md` to the sandbox and launches the OpenCode execution agent.
4. The agent sets up a Python virtual environment using `uv`, installs package dependencies, runs verification tests/entry points, and reports status.
5. If configuration succeeds: Stage status becomes `completed`, and the database stores the OpenCode live `opencode_session_id`.
6. If configuration fails: Stage status becomes `failed`, and connection command/sandbox details are stored in `sandbox_info` to allow the user to debug manually.

### Frontend UI Implementation
- **API Schema Additions**: Added `opencodeSessionId` and `opencodeServerUrl` to the `Job` interface, and declared `SandboxInfo` in `job.types.ts`.
- **Live OpenCode Session Link**: Renders a deep link to `{opencodeServerUrl}/?session={opencodeSessionId}` when the container environment is running or completed.
- **Auto-Scrolling Live Logs**: Terminal-style box automatically scrolls to the bottom during active logs streaming.
- **Copy Connection CLI Command**: Displays copyable `connectionCommand` on failure using clipboard API.
- **Sandbox Container Management**: Added PrimeNG ConfirmDialog wrapper around `DELETE /api/jobs/{job_id}/sandbox` to clean up containers.

---

## 🛠 Backend Architecture & API Specifications

The Python backend is located in the [sciloom_pipeline](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_pipeline) directory.

### Database System
- **SQLite Engine**: Configured to run in WAL mode with foreign keys enabled.
- **SQLAlchemy 2.0 ORM Models**:
  - `Job`: Includes `sandbox_id`, `opencode_session_id` (String(512)), and `opencode_server_url` (String(2048)).
  - `OcrLog`: Stores character counts per page.
  - `Stage`: Track timeline states (`pending`, `running`, `completed`, `failed`) and save sandbox connections command sequences (`sandbox_info`).
  - `Claim`: Tracks extraction variables, verification metrics, and execution evidence.
  - `Log`: Stores chronological logs written by workers.
- **Alembic migrations**: Managed database migrations dynamically, filtering out internal `_honker_*` job queue tables automatically.

### Background Workers & Job Queue
- Orchestrated with **Honker** (a thread-safe SQLite-backed queue utilizing `NOTIFY` and `LISTEN` actions).
- **Stage 1 (Provisioning)**: Consumes the `provision` task to download git repos/ZIPs, run Gemini OCR, and log page character counts.
- **Stage 2 (Claim Extraction)**: Consumes the `claim_extraction` task to run the claim extraction agent in a secure subprocess.
- **Stage 3 (Code Execution)**: Consumes the `code_execution` task to create the Docker sandbox, execute the environment configuration agent, and track session details.

---

## 📡 API Endpoints List

Base URL: `http://localhost:8000/api`

### 1. Jobs Management
* **`GET /api/jobs`**: Returns all replication jobs.
* **`GET /api/jobs/{job_id}`**: Returns details of a specific job (including sandbox fields).
* **`POST /api/jobs`** (`multipart/form-data`): Creates job and enqueues the `provision` task.
* **`DELETE /api/jobs/{job_id}`**: Deletes the database record, cascaded tables, and disk workspace.

### 2. Files & OCR Results
* **`GET /api/jobs/{job_id}/ocr`**: Returns the extracted Markdown text.
* **`PUT /api/jobs/{job_id}/ocr`**: Overwrites the markdown file on disk and automatically updates page character counts.
* **`POST /api/jobs/{job_id}/ocr/retry`**: Triggers a partial re-extraction task specifically for the PDF OCR.
* **`GET /api/jobs/{job_id}/files`**: Returns a recursive JSON structure representing the `REPO` folder directory tree.

### 3. Claims Syncing
* **`GET /api/jobs/{job_id}/claims`**: Returns claims for the job.
* **`PUT /api/jobs/{job_id}/claims`**: Synchronizes claims (adds, updates, deletes).

### 4. Sandbox Info & Management
* **`GET /api/jobs/{job_id}/sandbox`**: Returns connection commands and status of the job's sandbox container.
* **`DELETE /api/jobs/{job_id}/sandbox`**: Deletes the Docker sandbox container and nullifies sandbox-related job fields.

### 5. Stage & Process Controls
* **`POST /api/jobs/{job_id}/advance`**: Advances the pipeline to the next stage.
  - Advancing from `PROVISIONING` -> `CLAIM_EXTRACTION`: Enqueues `claim_extraction` task (unless user claims exist, in which case it advances straight to `CODE_EXECUTION`).
  - Advancing from `CLAIM_EXTRACTION` -> `CODE_EXECUTION`: Enqueues the `code_execution` task.
* **`POST /api/jobs/{job_id}/retry`**: Resets the current stage status and re-queues it (maps the active stage to worker task types).

### 6. Real-time Log Streaming
* **`GET /api/jobs/{job_id}/logs`**: Server-Sent Events (SSE) stream. Broadcasts historical logs followed by live log updates pushed by the Honker worker.

---

## 🔬 Scientific Markdown & LaTeX Math Rendering

- **Delimiters & Formula Rendering**: Registered `ngx-markdown` with KaTeX integration. Handles inline delimiters (`$`, `\(`) and block delimiters (`$$`, `\[`) dynamically.
- **Marked Parser Escape Fix**: Added computed preprocessing to double backslashes in math blocks (e.g. `\left\{` is translated to `\\left\\{` prior to Marked parsing). This prevents character stripping and renders complex LaTeX notations cleanly without red compile errors.
- **Premium Table & Math CSS Styling**: Defined styles in [styles.css](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/styles.css) with bordered responsive tables, alternate shading, and horizontal scrolls for wide equations.

---

## 🐞 Troubleshooting: SQLite Disk I/O Error in SSE Stream

- **The Issue**: During active task workloads (such as provisioning or retrying OCR), the backend logs would throw a repeated `RuntimeError: disk I/O error` (SQLITE_IOERR) when `/api/jobs/{job_id}/logs` was requested. On the frontend, this caused the EventSource connection to abort with `net::ERR_INCOMPLETE_CHUNKED_ENCODING`, which triggered an infinite loop of reconnect attempts in the browser console.
- **The Root Cause**: Honker's `listen()` implementation starts a background C/Rust thread to poll the SQLite database `data_version` Monotonic Commit Counter every 1ms. When uvicorn spawned individual `honker.open` connections inside the async `StreamingResponse` log generator, it conflicted with active SQLAlchemy sessions and background worker transactions, corrupting file index/WAL handles.
- **The Solution**: 
  - Refactored the logging stream to use a **Pure-Python In-Memory asyncio broker**.
  - Added a connection registry (`_log_listeners` dictionary of `asyncio.Queue` objects) to `QueueService`.
  - The worker broadcasts log events directly to the memory queue in RAM, bypassing SQLite file queries or locking.
  - The SSE endpoint registers an `asyncio.Queue` and yields events in real-time. If the client disconnects, the queue is automatically unregistered.
  - This completely eliminated the `disk I/O error` and browser reconnect loop, making log streaming fast and reliable.

- **OpenCode Agent Sandbox Configuration & Execution Fixes**:
  - **Missing Agent definitions**: The sandbox runs in an isolated VM that only has access to the workspace directory. Because `.opencode` was at the project root rather than inside the job workspace, the agent failed to boot because it could not find its `code-execution-agent.md` configuration. This was resolved by copying the `.opencode/agents` folder to the job `REPO/.opencode/agents` folder during the Stage 1 provisioning phase.
  - **Subcommand Parsing Crash**: The backend previously executed `sbx run <sandbox_name> -- --agent ...` which omitted the `run` subcommand. This caused `opencode` inside the container to fall back to the root server command, which rejected `--format json` and positional arguments, printing CLI help and exiting with code 1. Adding `run` immediately after the `--` separator resolved the parser error.
  - **Subprocess Environment Keys**: Mapped the backend's `settings.gemini_api_key` to `GOOGLE_API_KEY` inside the custom environment variables when calling any agent process (`opencode run` and `sbx run`), resolving LLM authentication failures inside the sandbox.

---

## 💻 Troubleshooting: WSL 2 Docker Sandbox Workspace Mount Issue

- **The Issue**: When running the pipeline from WSL 2 (Windows Subsystem for Linux), the sandbox container workspace `/home/agent/workspace` appears empty even though the container has successfully started. Commands or dependencies run by the agent inside the sandbox fail with file-not-found or permission errors.
- **The Root Cause**: 
  - The backend calls the `sbx` CLI. Because `/usr/local/bin/sbx` is a symlink pointing to the Windows executable `sbx.exe` on the host, WSL automatically translates Linux file paths (e.g. `/home/sharath/.../REPO`) to Windows UNC network paths (e.g. `\\wsl.localhost\Ubuntu-22.04\home\sharath\...`).
  - When `sbx.exe` mounts this path inside the container, Docker Desktop mounts it under a literal Linux path matching the UNC name (e.g., `/wsl.localhost/Ubuntu-22.04/.../REPO`) instead of `/home/agent/workspace`. Because it is a mounted network share, standard tools inside the container cannot perform symlinking, dependency compilation, or socket connections without permission blocks.
- **The Manual Workaround (WSL-only)**:
  1. Bash into the running sandbox VM:
     ```bash
     sbx exec -it sbx-job-<job_id> bash
     ```
  2. Copy the files from the network mount to the native container workspace:
     ```bash
     cp -r /wsl.localhost/Ubuntu-22.04/home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/jobs/job_<job_id>/REPO/. /home/agent/workspace
     ```
  3. Navigate to `/home/agent/workspace` and run build/run commands normally:
     ```bash
     cd /home/agent/workspace
     ```
