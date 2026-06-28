# Scientific Claim Replication & Metadata Generation Pipeline

This workspace provides an automated, agent-driven pipeline for converting scientific code repositories and their associated research papers into standardized **JSON-LD Loom records**.

By utilizing specialized OpenCode agents and local OCR processing, the pipeline automates paper parsing, environment setup, quantitative claim extraction, statistical verification/replication, and final semantic metadata serialization.

---

## Prerequisites & Installation

Before running the pipeline, set up the base workspace environment to support the PDF-to-Markdown conversion script and OCR processing.

### 1. System Dependencies
The PDF conversion utility relies on `pdf2image`, which requires `poppler` (specifically `pdftoppm`) to be installed on your system.
* **Ubuntu/Debian:**
  ```bash
  sudo apt-get update && sudo apt-get install -y poppler-utils
  ```
* **macOS (via Homebrew):**
  ```bash
  brew install poppler
  ```

### 2. Python Virtual Environment
Initialize a virtual environment in the workspace root using `uv` and install the dependencies required for the OCR script:
```bash
# Create the virtual environment
uv venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
# If requirements.txt is not yet present, install manually:
uv pip install pdf2image httpx pillow
```

### 3. OCR Engine (LM Studio / Local LLM)
The default converter script is configured to use a local **LM Studio** server hosting a vision-capable LLM (such as `glm-ocr` or `minicpm-v`) to perform page-by-page OCR and markdown generation:
* Start LM Studio and load a vision model.
* Enable the local inference server (by default, running at `http://localhost:1234/v1`).
* **Alternative Backends:** While GLM OCR is used here as a local and lightweight option, any alternative model, API (e.g., OpenAI GPT-4o, Claude 3.5 Sonnet), or local OCR tool can be substituted by adjusting the endpoint and request format in the script.

---

## Step-by-Step Execution Guide

### Step 1: Place the Repository & Setup Branch
Clone or copy the target repository into this workspace (for example, placing it under a subdirectory like `REPO`). 
> [TIP]
> It is highly recommended to create a separate Git branch in the target repository for this verification work (e.g., `sciloom-replication`) to keep replication scripts and metadata records isolated from the upstream main branch.

### Step 2: Initialize the `.sciloom` Directory
Inside the target repository, create a directory named `.sciloom`. Place the PDF of the research paper in this directory, named exactly `PAPER.pdf`:
```bash
mkdir -p REPO/.sciloom
cp path/to/research-paper.pdf REPO/.sciloom/PAPER.pdf
```

### Step 3: Convert the PDF to Markdown
Run the conversion script [pdf-to-markdown.py](pdf-to-markdown.py) to convert the research paper PDF into formatted Markdown. Ensure your virtual environment is active:
```bash
python pdf-to-markdown.py REPO/.sciloom/PAPER.pdf REPO/.sciloom/PAPER.md
```
> [NOTE]
> The script processes each PDF page concurrently, cleaning up markdown code block wrappers automatically and outputting a single cohesive markdown document.

### Step 4: Extract Quantitative Claims
Run the OpenCode Claim Extraction Agent defined in [.opencode/agents/claim-extraction-agent.md](.opencode/agents/claim-extraction-agent.md).
* **Agent Role:** Read the generated `.sciloom/PAPER.md` (or the equivalent OCR output file) and identify only the *original quantitative findings* proven by the paper's own data.
* **Output:** The agent automatically writes a structured JSON list of findings to `.sciloom/CLAIMS.json` containing atomic claims, metrics, and source section headers:
  ```json
  [
    {
      "id": "CLAIM-001",
      "claimText": "Mean feather cort differed significantly among the samples...",
      "metrics": "F_{3,35} = 7.285, p < 0.001",
      "evidence": "Results"
    }
  ]
  ```

### Step 5: Configure Environment & Verify Execution
Run the OpenCode Code Execution Agent defined in [.opencode/agents/code-execution-agent.md](.opencode/agents/code-execution-agent.md).
* **Agent Role:** Explores the target repository (`REPO/`), detects package configuration files (such as `requirements.txt` or `pyproject.toml`), sets up a virtual environment (`.venv`), resolves packages via `uv` or `pip`, and executes the codebase's main replication entry point to confirm viability.
* **Output:** Creates a status summary at `.sciloom/CODE_EXECUTION_SUCCESS.json` or `.sciloom/CODE_EXECUTION_FAILED.json`.

### Step 6: Mathematically Replicate the Claims
Run the OpenCode Claim Replication Agent defined in [.opencode/agents/claim-replication-agent.md](.opencode/agents/claim-replication-agent.md).
* **Agent Role:** Spawns subagents for isolated verification tasks, writes standalone Python replication scripts under `REPO/replicate_CLAIM_*.py` for each claim in `CLAIMS.json`, processes datasets, runs statistical tests (e.g. ANOVA, regressions), and validates computed metrics against paper values.
* **Output:** Writes executable Python scripts and updates `.sciloom/CLAIMS.json` with `"replicated": true` (along with computed statistics like F-values, p-values) or `"replicated": false` (with traceback details on failure).

### Step 7: Serialize Standardized DTREG JSON-LD Records
Run the OpenCode DTREG Generation Agent defined in [.opencode/agents/dtreg-generation-agent.md](.opencode/agents/dtreg-generation-agent.md).
* **Agent Role:** Maps the replicated findings to metadata schemas (e.g. Group Comparison or Algorithm Evaluation templates). It writes a parameterized serialization script `REPO/generate_dtreg.py` using the `dtreg` library and runs it.
* **Output:** Dynamically queries executing packages, dependencies, and statistical outputs to generate individual ePIC DTREG JSON-LD Loom records for each verified claim (e.g., `REPO/dtreg_output_CLAIM-001.jsonld`).

---

## Example Run Reference

An example run of this pipeline is structured under [example_repo/](example_repo). You can examine this directory to see the expected input and output file structures:

* **Example Config & Inputs:** Check the [example_repo/.sciloom/](example_repo/.sciloom) folder containing the source paper [PAPER.pdf](example_repo/.sciloom/PAPER.pdf), OCR generated [PAPER.md](example_repo/.sciloom/PAPER.md), extracted [CLAIMS.json](example_repo/.sciloom/CLAIMS.json), and environment [CODE_EXECUTION_SUCCESS.json](example_repo/.sciloom/CODE_EXECUTION_SUCCESS.json).
* **Example Verification Scripts:** View [replicate_CLAIM_001.py](example_repo/REPO/replicate_CLAIM_001.py) in the cloned repository directory, which demonstrates the programmatic parsing, testing, and validation of statistical values.
* **Example Serialization Output:** View [generate_dtreg.py](example_repo/REPO/generate_dtreg.py) and the resulting Loom records (e.g., [dtreg_output_CLAIM-001.jsonld](example_repo/REPO/dtreg_output_CLAIM-001.jsonld)) to see how statistical graphs and dependencies are captured semantically.
