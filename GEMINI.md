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
├── config.py                 # Central configurations, system prompts, category mappings
├── db.py                     # SQLite connection manager, schema definitions, and migration handler
├── archiver.py               # Background Watchdog watcher and thread-safe process queue
├── archive.py                # Main orchestration pipeline for processing a single PDF
├── llm.py                    # Local inference loader via llama-cpp-python and prompt constructor
├── feedback.py               # Accumulates manual edits as few-shot JSON templates
├── storage.py                # Handles file management, hash registers, and sender metadata
├── pdf_utils.py              # File-lock detection and PyMuPDF text/OCR extractors
├── api/                      # FastAPI Backend
│   ├── main.py               # App entry point, CORS settings, and startup hooks
│   ├── models.py             # Pydantic schemas for request/response payloads
│   └── routes/               # API endpoint modules (documents, senders, stats, monitor)
├── frontend/                 # React Web-UI
│   ├── package.json          # Vite + React 19 dependencies, oxlint for linting
│   ├── src/                  # React source code (pages, components, api.ts)
│   └── vite.config.ts        # Vite build configuration with Tailwind v4
├── tests/                    # Backend Pytest suite
│   └── test_*.py             # Database, validation, storage, and feedback unit tests
├── requirements.txt          # Python virtual env dependencies
└── start_all.bat             # Orchestrated startup batch script (Backend + Frontend)
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

### A. Local Inference Mandate (NO Ollama Server Calls)
*   **Rule:** Even if the selected GGUF model resides inside the `.ollama` cache directory, **Ollama must NOT be run as a server.**
*   **Rationale:** Ollama 0.30.x on Windows is known to crash with HTTP 500 / "exit status 1" on AMD Ryzen Zen-2 CPUs (e.g., Ryzen 5 3600) due to incompatible instruction sets.
*   **Implementation:** Always load GGUF models directly from the filesystem using `llama-cpp-python` via `llm.py`.

### B. Database Schema & Migration Pattern
*   All DB connections must go through `db.get_conn()`, a context manager that enforces WAL (`PRAGMA journal_mode=WAL`) and foreign keys.
*   **Full-Text Search (FTS5):** A virtual table `documents_fts` tracks `filename, sender, summary, keywords`. Triggers on the main `documents` table (`documents_ai`, `documents_au`, `documents_ad`) automatically maintain the FTS index on INSERT, UPDATE, and DELETE.
*   **Migrations:** Incremental columns are appended via the `MIGRATIONS` array in `db.py`. To remain safe and idempotent across database initializations, migration SQL strings are executed sequentially within `try-except` blocks to ignore duplicate-column errors.

### C. Processing Pipeline & Ingest Sequence
1.  **Ingestion:** Watchdog spots a new `.pdf` in `SOURCE_DIR`. It polls via `wait_for_file()` until the file lock is released.
2.  **Duplicate Check:** SHA256 of the document is generated and compared against `hashes.json`. If a duplicate is found, it is moved to `duplicates/` and logged in the DB as `status='duplicate'`.
3.  **Prompt Builder:**
    *   System Prompt is generated utilizing strict schemas.
    *   **Few-Shot Integration:** Up to 15 manual GUI correction records are extracted from `feedback.json` (preferring category corrections) and formatted as few-shot examples inside the context prompt.
    *   **Similar-Doc Context:** The 3 most recent entries for the matching sender are queried from SQLite and injected to ensure classification consistency.
4.  **LLM Execution:** JSON schema extraction parses `sender`, `date`, `document_type`, `category`, `summary`, and `keywords`.
5.  **Validation & Post-Processing:**
    *   Dates in the future or invalid formats are rejected.
    *   **Hallucinations Filtering:** Keywords are cross-verified against the original extracted PDF text. If a keyword does not appear literally, it is stripped.
    *   **Sender Registry Matching:** Fuzzy matching and canonical alias resolution maps the sender name using definitions inside `senders.json`.
6.  **Archiving:** The PDF is renamed and relocated to `TARGET_BASE/{Category_Folder}/{Year}/{Normalized_Sender}/{Filename}`. DB and FTS5 indexes are updated synchronously.

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
