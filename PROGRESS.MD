# SciLoom Pipeline Project Progress & Handover Note

## Stage 1 & 2 UI & Backend Completed 🚀
**Stage 1 (Provisioning, OCR Extraction & Job Setup)** and **Stage 2 (Claim Extraction)** have been fully completed!
- **Frontend**: Stage 1 & 2 UI finished in Angular 21 with PrimeNG v21 and Tailwind CSS layouts. Integrates native LaTeX math rendering, Markdown parsing, and a full claims editor with edit/add/remove/save functionality.
- **Backend**: Stage 1 & 2 fully implemented using FastAPI, SQLAlchemy 2.0 ORM, Alembic 1.18 migrations, Honker (async SQLite NOTIFY/LISTEN queue worker orchestration), and OpenCode LLM Claim Extraction agent subprocess pipeline.

---

## 🎨 Implemented UI Components

All components are located in the [src/app/components](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components) directory:
- **`AppHeaderComponent`**: The shared top navigation bar and branding logo. See [app-header.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/app-header/app-header.component.ts).
- **`DashboardComponent`**: Displays registered jobs with PrimeNG Tables, custom pagination, search filters, and statistics summaries. See [dashboard.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/dashboard/dashboard.component.ts) and [dashboard.component.html](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/dashboard/dashboard.component.html).
- **`JobFormComponent`**: A Reactive form within a Modal Dialog for creating a new job. Handles validation of required inputs and file uploads. See [job-form.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/job-form/job-form.component.ts).
- **`JobDetailsComponent`**: Main details dashboard displaying the 5-stage timeline, live log streaming feeds, and a tabbed details layout. Integrates an `isOcrRetrying` signal that seamlessly switches the view back to the streaming log terminal during a retry, hiding the initial progress bar. See [job-details.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/job-details/job-details.component.ts).
- **`OCRPreviewComponent`**: Markdown viewer and editor for research papers. Includes:
  - **Page Density Grid**: Renders individual page boxes color-coded by character counts (green for high density, amber for low density, and rose for empty pages) with interactive tooltip summaries.
  - **Raw Markdown Editor**: Switchable `<textarea>` panel allowing users to edit and save corrected text directly to the SQLite database.
  - **OCR Re-extraction controls**: Integrated with a PrimeNG confirm dialog to safely trigger backend OCR retries.
  - See [ocr-preview.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/ocr-preview/ocr-preview.component.ts).
- **`FileExplorerComponent`**: Recursive file explorer for repository trees. See [file-explorer.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/file-explorer/file-explorer.component.ts).
- **`ClaimsEditorComponent`**: Full-featured claims management UI for Stage 2 human-in-the-loop review. Features:
  - **Inline editing**: Textarea-based claim text editing with modification tracking (amber "Modified" badge).
  - **Add/Remove claims**: Add new user-source claims (indigo "New" badge), delete with PrimeNG confirm dialog.
  - **Save to backend**: PUT `ClaimsSyncRequest` payload wrapping `{ claims: [...] }` to `PUT /api/jobs/{id}/claims`.
  - **Advance to Stage 3**: Button with unsaved-changes guard — blocks advancement until claims are saved.
  - **Optimistic state**: Local `EditableClaim` signal array with `_isNew`, `_isModified`, `_isDeleted` flags for safe partial sync.
  - See [claims-editor.component.ts](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_ui/src/app/components/claims-editor/claims-editor.component.ts).

---

## 🎯 Stage 2 UI: Claims Editor Integration

### Component Hierarchy
```
JobDetailsComponent (parent)
  └── ClaimsEditorComponent (child, embedded in CLAIM_EXTRACTION completed view)
```

### Stage 2 Views in `job-details.component.html`
The `CLAIM_EXTRACTION` stage now has dedicated views for all four pipeline states:
- **Running**: Live SSE terminal with spinner, agent log stream, and "Return to Dashboard" link.
- **Completed**: `<app-claims-editor>` with full edit/add/remove/save/advance capabilities.
- **Failed**: Error banner with claim extraction error log, retry button.
- **Pending**: Placeholder waiting for Stage 1 completion.

### JobService Methods Added
- **`advanceToStage3(jobId)`**: Optimistic status update to `CODE_EXECUTION`, POST `/jobs/{id}/advance`, refresh + SSE reconnect.
- **`refreshClaims(jobId)`**: Reloads claims from backend after editor saves.
- **`advanceToStage2(jobId)`**: Now reconnects SSE logs after advancing to capture agent output.

### Type Updates
- **`Job.status`** expanded to include `CODE_EXECUTION`, `CLAIM_REPLICATION`, `DTREG_GENERATION` — matching the 5-stage pipeline lifecycle.
- **`getStatusSeverity()`** and **`getStatusBadgeSeverity()`** updated in both Dashboard and JobDetails to handle new status values.

### Backend Fixes
- **`agent_service.py`**: Changed `-f RESEARCH_PAPER.md` (relative) to `-f str(paper_path)` (absolute) to fix OpenCode's subprocess path resolution — OpenCode resolves `-f` relative to its own context, not the subprocess `cwd`.
- **`job_service.py`**: Added explicit `RESEARCH_PAPER.md` existence check before invoking the agent, providing a clear `FileNotFoundError` if provisioning is incomplete.

### Claims Sync API Contract
The `PUT /api/jobs/{id}/claims` endpoint expects a `ClaimsSyncRequest` body:
```json
{
  "claims": [
    { "id": "claim_1", "claimText": "...", "source": "agent", "metrics": "...", "evidence": "..." }
  ]
}
```
The frontend wraps the payload accordingly. New claims omit `id` (backend generates one). Deleted claims are omitted from the array (backend removes them).

---

## 🛠 Backend Architecture & API Specifications

The Python backend is located in the [sciloom_pipeline](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_pipeline) directory.

### Database System
- **SQLite Engine**: Configured to run in WAL mode with foreign keys enabled.
- **SQLAlchemy 2.0 ORM Models**:
  - `Job`: Primary job details, status tracking, relationships, and metadata.
  - `OcrLog`: Stores character counts per page to allow the frontend to detect empty or partial extraction anomalies.
  - `Stage`: Track timeline states (`pending`, `running`, `completed`, `failed`) and save sandbox connections command sequences.
  - `Claim`: Tracks extraction variables, verification metrics, and execution evidence.
  - `Log`: Stores chronological logs written by workers.
- **Alembic migrations**: Managed database migrations dynamically, filtering out internal `_honker_*` job queue tables automatically.

### Background Workers & Job Queue
- Orchestrated with **Honker** (a thread-safe SQLite-backed queue utilizing `NOTIFY` and `LISTEN` actions).
- **Stage 1 (Provisioning)**: When a job is created, the backend enqueues the `provision` task. The background worker consumes it, downloads git repos or extracts ZIP packages, performs security sandboxing checks, runs Gemini OCR on the PDF, logs details, and saves counts.
- **Stage 2 (Claim Extraction)**: When a job transitions into the `CLAIM_EXTRACTION` stage and no user claims are present, the worker consumes the `claim_extraction` task. It spawns the `claim-extraction-agent` via a secure OpenCode subprocess in the job workspace, streams real-time agent output to the log broker, and parses the generated `CLAIMS.json` to insert extracted quantitative findings directly into the SQLite database.

### 📄 PDF Document Processing & Smart OCR
- **PDFExtractor Class**: Located in [pdf_extractor.py](file:///home/sharath/Documents/LUH/sem_1/labor_ai_ready/sciloom-pipeline/sciloom_pipeline/document_processing/pdf_extractor.py).
- **High-DPI Rasterisation**: Increased resolution default from `300` to `500` DPI to significantly improve formula layout and OCR output.
- **OCR Engine model**: Switched to `"gemini-3.1-flash-lite"`.
- **Soft Failure Retry**: Built an internal retry loop. If a page generates an empty (`0` character) result, it waits and retries the request up to 3 times before accepting it.

---

## 📡 API Endpoints List

Base URL: `http://localhost:8000/api`

### 1. Jobs Management
* **`GET /api/jobs`**: Returns all replication jobs.
* **`GET /api/jobs/{job_id}`**: Returns details of a specific job.
* **`POST /api/jobs`** (`multipart/form-data`):
  - Form Fields: `title`, `repoSource` (`"github"`/`"zip"`), `repoUrl`, `dataSource` (`"zip"`/`"in_repo"`), `manualClaims` (JSON array), `pdfFile` (upload), `repoFile` (upload), `dataFile` (upload).
  - Automatically enqueues the `provision` task.
* **`DELETE /api/jobs/{job_id}`**: Deletes the database record, cascaded tables, and disk workspace.

### 2. Files & OCR Results
* **`GET /api/jobs/{job_id}/ocr`**: Returns the extracted Markdown text.
* **`PUT /api/jobs/{job_id}/ocr`**: Overwrites the markdown file on disk and automatically updates page character counts in the DB.
* **`POST /api/jobs/{job_id}/ocr/retry`**: Triggers a partial re-extraction task specifically for the PDF OCR, leaving workspace files intact.
* **`GET /api/jobs/{job_id}/files`**: Returns a recursive JSON structure representing the `REPO` folder directory tree.

### 3. Claims Syncing
* **`GET /api/jobs/{job_id}/claims`**: Returns claims for the job.
* **`PUT /api/jobs/{job_id}/claims`**: Synchronizes claims (adds, updates, deletes).

### 4. Stage & Process Controls
* **`POST /api/jobs/{job_id}/advance`**: Advances the pipeline to the next stage.
  - If advancing from `PROVISIONING` to `CLAIM_EXTRACTION`, it checks if manual claims were supplied. If yes, it skips straight to `CODE_EXECUTION`. If no, it enqueues the automated `claim_extraction` task.
* **`POST /api/jobs/{job_id}/retry`**: Resets the current stage status and re-queues it.
  - Automatically maps the active stage (e.g., `CLAIM_EXTRACTION`) to re-queue the task (`claim_extraction`) for the worker.

### 5. Real-time Log Streaming
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


