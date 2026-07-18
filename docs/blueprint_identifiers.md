# Blueprint: Deterministic Identifiers & Entity Resolution (IDs, IBANs, Zählernummern)

This document designs and specifies the implementation of a structured "Identifiers" registry in PaperVault. It transitions the existing unstructured text `aliases` array into a high-performance, relational database-backed Entity Resolution system.

---

## 1. Architectural & Database Design

### A. SQLite Schema Expansion
We introduce two new tables in `backend/db/schema.py`:

1.  `sender_identifiers`: Stores confirmed, verifiably matched IDs associated with a specific canonical sender.
2.  `unassigned_identifiers`: Holds a temporary pool of newly detected identifiers found during PDF ingestion, awaiting manual confirmation and routing in the UI.

```sql
CREATE TABLE IF NOT EXISTS sender_identifiers (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_name         TEXT NOT NULL,
    identifier_type     TEXT NOT NULL CHECK(identifier_type IN ('IBAN', 'CUSTOMER_NO', 'PERSONAL_NO', 'METER_ID', 'POLICY_NO')),
    identifier_value    TEXT NOT NULL UNIQUE,
    label               TEXT,
    target_category     TEXT,
    target_unit         TEXT,
    created_at          TEXT NOT NULL,
    FOREIGN KEY (sender_name) REFERENCES senders(name) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_identifiers_value ON sender_identifiers(identifier_value);

CREATE TABLE IF NOT EXISTS unassigned_identifiers (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id         INTEGER NOT NULL,
    identifier_type     TEXT NOT NULL,
    identifier_value    TEXT NOT NULL,
    context_text        TEXT,
    detected_at         TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    UNIQUE(identifier_type, identifier_value)
);
```

### B. Whitelist Configuration
To prevent the user's own IBANs from polluting the unassigned identifier inbox, we introduce an `own_ibans` array inside the user's settings (persisted via `config_manager.py`).

---

## 2. Ingestion Pipeline Integration

Before a document is sent to the local LLM for full classification, the pipeline will perform a high-performance deterministic check (Stage 0):

```text
Incoming PDF 
   │
   ▼
Extract Text (PyMuPDF / OCR)
   │
   ▼
Scan text with Regexes for IBAN, Meter IDs, Customer IDs, etc.
   │
   ├── Matches existing confirmed identifier?
   │      ├── YES ──► Bypass LLM, assign Sender & Category directly (Confidence: HIGH)
   │      └── NO  ──► Send to LLM
   │
   ▼
LLM Classification
   │
   ▼
Record any non-matching, novel identifiers into `unassigned_identifiers`
```

### Regular Expressions for Detection
*   **IBAN:** `\bDE\d{20}\b` (with contextual filters: must not be in `own_ibans`, must be on the receiver side).
*   **Zählernummer (Meter ID):** `(?:Zähler-?Nr|Meter-?No|Zählerstand)[^\d]{0,10}(\d{5,12})` (case-insensitive).
*   **Kundennummer (Customer No):** `(?:Kunden-?nummer|Kd-?Nr|Customer-?No)[^\d]{0,10}([A-Z0-9-]{5,15})` (case-insensitive).

---

## 3. API Routes Design (`backend/api/routes/identifiers.py`)

*   `GET /api/identifiers`: Lists all confirmed identifiers.
*   `POST /api/identifiers`: Manually registers a new identifier.
*   `DELETE /api/identifiers/{id}`: Deletes a confirmed identifier.
*   `GET /api/identifiers/unassigned`: Retrieves all currently unassigned identifiers awaiting review.
*   `POST /api/identifiers/assign`: Assigns an unassigned identifier to a sender, migrating it to `sender_identifiers`.
*   `DELETE /api/identifiers/unassigned/{id}`: Ignores/dismisses an unassigned identifier proposal.

---

## 4. Frontend UI Design

We will add a new primary navigation tab **"IDs & Verträge"** (or similar, or integrate it elegantly with existing settings/senders) containing:
1.  A **Registered Identifiers Table** displaying all active rules, their types, associated senders, and routing targets (Wohnung, Category).
2.  A **Vorschlags-Inbox (Unassigned Proposals)** sidebar or secondary panel showing newly found unassigned identifiers with a quick `[ Zuweisen ]` or `[ Ignorieren ]` button.
