# PaperVault - Developer & Agent Instructions

This file serves as the definitive instructional context and architectural map for anyone (including AI assistants) working on the **PaperVault** codebase.

---

## 1. Project Overview

**PaperVault** is a fully offline, local PDF archiving and metadata-management system. It monitors a target inbox directory, extracts text, utilizes a local LLM to classify and summarize documents, and organizes files into a clean category-based folder hierarchy on the local filesystem.

### Key Technologies
*   **Backend:** FastAPI (Python 3.10+), SQLite (FTS5 full-text search), PyMuPDF (text extraction), pytesseract (OCR fallback), watchdog (file monitoring), llama-cpp-python (local GGUF-based inference).
*   **Frontend:** React 19, TypeScript, Vite 8, Tailwind CSS v4, Lucide React, Recharts.
*   **Database:** SQLite in WAL (Write-Ahead Logging) mode, leveraging virtual tables (`documents_fts`) and automated triggers to keep indexing synchronized.

---

## 2. Directory Structure & Key Components

```text
papervault/
├── backend/                  # Python Core
│   ├── config.py             # Central configurations, system prompts, paths
│   ├── archiver.py           # Background Watchdog watcher and thread-safe process queue
│   ├── feedback.py           # Accumulates manual edits as few-shot JSON templates
│   ├── storage.py            # Thread-safe file management (hashes, senders)
│   ├── pdf_utils.py          # Smart Chunking, OCR and text extraction facade
│   ├── pdf_thumbnails.py     # Render PNG/JPEG PDF thumbnails and header images
│   ├── pdf_hashing.py        # SimHash fingerprinting and Hamming distance calculations
│   ├── utils.py              # Shared string normalization, date parsing, logging
│   ├── api/                  # FastAPI App
│   │   ├── main.py           # App entry point, CORS settings
│   │   ├── models.py         # Pydantic schemas
│   │   └── routes/           # API endpoint modules
│   ├── db/                   # SQLite Repository
│   │   ├── connection.py     # SQLite setup & WAL manager
│   │   ├── schema.py         # Table structures & migrations
│   │   ├── documents_repo.py # CRUD & FTS Search
│   │   └── stats_repo.py     # Analytics & counts
│   ├── llm/                  # Local Inference & LLM Workflows
│   │   ├── driver.py         # Low-level model loading and completion driver
│   │   ├── classify.py       # High-level document classification logic
│   │   └── specialized/      # Specialized contracts/items/services extraction
│   └── pipeline/             # PDF Ingest Pipeline
│       ├── core.py           # Orchestrator (process_pdf)
│       └── steps.py          # Standalone processing steps (duplicates, shortcuts)
├── frontend/                 # React Web-UI
│   ├── package.json          # Vite + React 19 dependencies, oxlint
│   ├── src/                  # React source code (pages, components, ConfigContext.tsx)
│   └── vite.config.ts        # Vite build configuration with Tailwind v4
├── tests/                    # Backend Pytest suite (requires backend/ in PYTHONPATH)
├── requirements.txt          # Python virtual env dependencies
├── start_all.bat             # Orchestrated startup batch script
└── stop_all.bat              # PowerShell-based robust process termination
```

---

## 3. Critical Setup & Operational Commands

### Environment Configuration (`.env`)
Create a `.env` file in the project root matching `.env.example` with these main variables:
```bash
SOURCE_DIR="C:/Archive/Inbox"       # Monitored directory
TARGET_BASE="C:/Archive"            # Archived document storage
MODEL_PATH="C:/..."                 # Path to local GGUF model file
DB_PATH="C:/Archive/archive.db"     # SQLite database path
MAX_RETRIES="3"                     # LLM inference attempts
SENDER_SUBFOLDERS="true"            # Use TARGET_BASE/{Category}/{Year}/{Sender}/ structure
```

### Build & Run Commands

*   **Automated Model & Env Setup (Any PC):**
    ```bash
    python scripts/download_model.py
    ```

*   **Unified Startup:**
    ```bash
    start_all.bat
    ```
*   **Backend Startup (Manual):**
    ```bash
    cd backend
    python -m uvicorn api.main:app --port 8000
    ```
*   **Frontend Startup (Manual):**
    ```bash
    cd frontend
    npm install
    npm run dev
    ```
*   **Running Tests:**
    ```bash
    pytest
    ```

---

## 4. Architectural & Development Conventions

### A. Local Inference Mandate & Hardware Modes
*   **Rule:** Even if the selected GGUF model resides inside the `.ollama` cache directory, **Ollama must NOT be run as a server.**
*   **Rationale:** Ollama 0.30.x on Windows is known to crash with HTTP 500 / "exit status 1" on AMD Ryzen Zen-2 CPUs (e.g., Ryzen 5 3600) due to incompatible instruction sets.
*   **Implementation:** Always load GGUF models directly from the filesystem using `llama-cpp-python` via `llm.py`.
*   **CUDA GPU Acceleration:** To prevent CUDA memory segmentation faults when running on GPUs like the **NVIDIA RTX 3060 12GB**, a global thread synchronization lock (`_llm_lock = threading.Lock()`) must serialize all `_llm.create_chat_completion` calls.
*   **CPU-only Support & Lifespan Startup:** `assert_gpu_support()` must not block server startup if the user explicitly chooses CPU-only execution (e.g., setting `N_GPU_LAYERS = 0`). Only log a warning in that case.
*   **Preload Thread-Safety:** During model preloading (background daemon thread `llm-preload`), all checks and instantiations of the global `_llm` instance must reside under double-checked locking inside `_llm_lock` to avoid double-loading or CUDA OOM if API requests arrive concurrently.

### B. Database Schema & Migration Pattern
*   All DB connections must go through `db.get_conn()`, a context manager that enforces WAL (`PRAGMA journal_mode=WAL`), foreign keys, and relies on a **Thread-Local Connection Pool** (`threading.local()`) inside `connection.py` to reuse connections and eliminate connection overhead.
*   **Full-Text Search (FTS5):** A virtual table `documents_fts` tracks `filename, sender, summary, keywords`. Triggers on the main `documents` table (`documents_ai`, `documents_au`, `documents_ad`) automatically maintain the FTS index on INSERT, UPDATE, and DELETE.
*   **Database-Grounded Duplicates:** The file `hashes.json` is deprecated. Duplicate matches are performed directly against SQLite using high-performance indexed queries (`get_document_by_hash`).
*   **Migrations:** Incremental columns are appended via the `MIGRATIONS` array in `schema.py`. To remain safe and idempotent across database initializations, migration SQL strings are executed sequentially within `try-except` blocks to ignore duplicate-column errors.

### C. Processing Pipeline & Ingest Sequence
1.  **Ingestion:** Watchdog spots a new `.pdf` in `SOURCE_DIR`. It polls via `wait_for_file()` until the file lock is released.
    *   **Self-Healing Worker:** An automated monitoring loop in `archiver.py` checks every 2 seconds if the file-processing background worker thread has died (`worker_thread.is_alive() == False`) and automatically restarts it.
    *   **Multi-Process Path Synchronization:** Updates to `SOURCE_DIR` or `TARGET_BASE` via the settings API write to `.env` but only update the memory of the FastAPI backend. Since `archiver.py` runs as a separate OS process, it does **not** dynamically reload these variables. Changing paths requires a manual service restart to avoid UI/worker path divergence.
2.  **Duplicate Check:** 
    *   **Dual-Mode Hashing:** If the extracted text is $\ge$ 100 characters, it uses content-based text hashing. If the text is shorter (e.g. OCR failed or blank PDF) or identified as a recurring periodic document (e.g. payslips, bank statements), it automatically falls back to binary file-level hashing to prevent false duplicate collisions on generic strings.
    *   If an exact duplicate is found, it is moved to `duplicates/` and logged in the DB as `status='duplicate'`.
    *   **Near-Duplicate SimHash Filtering:** Near-duplicate check detects $\ge$ 90% text similarity. To prevent monatliche Gehaltsabrechnungen or other recurring periodic documents from always triggering SimHash duplicate flags (which overrides confidence to `LOW` and forces manual review), the SimHash duplicate check must be bypassed when `is_periodic_document()` is true.
3.  **OCR Text Extraction & File Lock Safety:**
    *   If embedded text is missing or garbled (Dictionary-Density score < 15% and Alnum ratio < 75%), OCR is triggered (`ocr_pdf()`).
    *   **PyMuPDF File Lock Safety:** Every method opening PDF files (`extract_text()`, `ocr_pdf()`, etc.) **must** encapsulate PyMuPDF documents in `try-finally` blocks to guarantee `doc.close()` executes and releases Windows file locks on exceptions.
4.  **Prompt Builder:**
    *   System Prompt is generated utilizing strict schemas.
    *   **Few-Shot Integration:** Up to 15 manual GUI correction records are extracted from `feedback.json` (preferring category corrections) and formatted as few-shot examples inside the context prompt.
    *   **Similar-Doc Context:** The 3 most recent entries for the matching sender are queried from SQLite and injected to ensure classification consistency.
    *   **Smart Chunking:** For documents with $\ge$ 3 pages, only Page 1 (sender, date metadata) and the Last Page (totals, signature metadata) are extracted and concatenated to stay within the 2000 character limit without losing context.
    *   **Königsweg Briefkopf Isolation:** The top 30% of page 1 is isolated and provided to the LLM as a dedicated `--- DOKUMENT-BRIEFKOPF ---` section. Disambiguation rules instruct the model to resolve `sender` strictly from this section, resolving the "Netto" (net tax value) token confusion.
5.  **LLM Execution:** JSON schema extraction parses `sender`, `date`, `document_type`, `category`, `summary`, and `keywords`.
    *   **Confidence Score & Ampel-Notizen:** Calculates a confidence rating (`HIGH`, `MEDIUM`, `LOW`) and a logical reason (e.g. Rule Match vs Semantic Text Verification vs Hallucination Alarm) and records it directly in the `notes` column in SQLite, making it instantly visible in the UI detail panel.
6.  **Validation & Post-Processing:**
    *   Dates in the future or invalid formats are rejected.
    *   **Hallucinations Filtering:** Keywords are cross-verified against the original extracted PDF text. If a keyword does not appear literally, it is stripped.
    *   **Sender Registry Matching:** Fuzzy matching and canonical alias resolution maps the sender name using definitions inside `senders.json`.
7.  **Archiving / Auto-Archiving:**
    *   **Auto-Archiving (Weg 3):** If confidence is `HIGH` (Stufe 0 Rule Match and valid date), the document automatically bypasses the review inbox, is moved directly to the final archive folder, and marked `status="ok"`.
    *   Otherwise, the PDF is relocated to the `review/` inbox folder.
    *   **Transactional Safety & Rollback:** File movements and DB writes are wrapped in `try-except` blocks. If database writes fail, the PDF is automatically moved back to its original path (filesystem rollback), fully protecting against dangling untracked files.

### D. Frontend Standards
*   **Tailwind CSS v4:** Vite relies on `@tailwindcss/vite` plugin configuration. Avoid using deprecated `@apply` structures where vanilla utilities or custom CSS files are preferred.
*   **Linter:** `oxlint` is configured and used as the default fast linter in `package.json` under `npm run lint`. Ensure all frontend modifications compile cleanly and satisfy oxlint rules.
*   **Filtering & Routing:** Page states (active filters, document lists) should reflect in the React Router URL state to maintain bookmarkable, back-button-friendly navigations.

### E. Single Source of Truth (SSOT) Rule
*   **Definition:** Core system definitions, classifications (e.g., categories, allowed document types), and configuration constants must be defined in exactly one place (the backend configuration, e.g. `config.py`) and dynamically exposed via APIs (e.g. `/stats/categories` and `/stats/document-types`).
*   **Rule:** Redundant lists or hardcoded arrays of categories or document types must not be duplicated in frontend assets. The frontend must fetch and use these settings dynamically through runtime API endpoints (managed by the `ConfigProvider` React Context) to ensure backend configurations and frontend UI states remain fully synchronized at all times.

---

## 5. Testing Principles
*   Backend tests live in `tests/`.
*   All database tests must use the `in_memory_db` autouse fixture defined in `tests/test_db.py` to redirect sqlite interactions to a temporary sqlite path (`tmp_path / "test.db"`) avoiding production database contamination.
*   *Note on local preferences:* Do not automatically run the entire test suite on every minor change. Only invoke pytest when testing specific modules or when requested by the developer.

## 6. AI Assistant Behavior & Output Rules

When interacting with this codebase or answering user queries, the AI assistant MUST strictly adhere to the following output formatting rules to preserve context window and reduce reading overhead:

*   **Zero Fluff:** Provide pure, actionable output. Do NOT include pleasantries, conversational filler, or introductory/concluding remarks (e.g., "Here is the code you requested", "Let me know if you need more help", "Certainly!").
*   **Code-First & Live-Code Verification:** If modifying or generating code, output ONLY the necessary code blocks. Do not explain the code unless explicitly asked to do so. Start immediately with the solution. **Crucially, the assistant must always verify any reported bugs, design flaws, or current status against the actual live-code (using grep_search/read_file) before making any claims or listing active issues, rather than relying on historical blueprints or design-plan files.**
*   **Concise Reasoning:** If a task is complex and requires step-by-step logical deduction (Chain of Thought) to avoid errors, keep the analysis extremely brief, use bullet points, and place it directly before the final code block. 
*   **Precision:** Answer questions directly. If asked a yes/no question, start with Yes or No.