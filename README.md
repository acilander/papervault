# PaperVault

Automatisches PDF-Archivierungssystem mit **lokalem LLM** (llama-cpp-python, keine Cloud) und **React Web-UI**.  
Überwacht einen Inbox-Ordner, klassifiziert PDFs vollautomatisch und legt sie strukturiert im Dateisystem ab.  
Metadaten in SQLite, vollständig verwaltbar über FastAPI + React.

---

## Voraussetzungen

- Python 3.10+
- Node.js 18+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) – optional, für gescannte PDFs
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases/) – im PATH, für OCR
- GGUF-Modell (z.B. Qwen2.5 1.5B Instruct oder größer)

---

## Installation

### 1. Voraussetzungen installieren (Windows)

#### Tesseract OCR (für gescannte PDFs)
1. Installer herunterladen: https://github.com/UB-Mannheim/tesseract/wiki
2. Bei Installation **"German"** Sprache auswählen
3. Installationspfad zum PATH hinzufügen (z.B. `C:\Program Files\Tesseract-OCR`)
4. Prüfen: `tesseract --version`

#### Poppler (für pdf2image / OCR)
1. Download: https://github.com/oschwartz10612/poppler-windows/releases/
2. Entpacken, z.B. nach `C:\poppler`
3. `C:\poppler\Library\bin` zum PATH hinzufügen
4. Prüfen: `pdftoppm -v`

### 2. Python-Umgebung

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. PyTorch installieren

> **Wichtig:** PyTorch muss **vor** `requirements.txt` installiert werden, da pip sonst ggf. eine falsche Version zieht.

```bash
# CPU-only (Standard, reicht für Vision/Logo-Erkennung):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# CUDA (optional, nur wenn torch selbst GPU nutzen soll):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu132
```

CUDA-Version prüfen: `nvidia-smi` → Spalte "CUDA Version"

### 4. llama-cpp-python mit CUDA installieren

> **Wichtig:** Standard `pip install llama-cpp-python` löst einen Compile-Vorgang aus (erfordert MSVC + CUDA Toolkit, dauert sehr lang).
> Stattdessen das **fertige CUDA-Wheel** verwenden — kein Build nötig.
>
> Voraussetzungen: **Python 3.10–3.12** (kein 3.13/3.14!) und das **venv aktiviert**.

```bash
# CUDA 13.x (RTX-Karten, Treiber 610+):
pip install llama-cpp-python==0.3.32 --force-reinstall --no-cache-dir --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu132

# CUDA 12.x:
pip install llama-cpp-python==0.3.32 --force-reinstall --no-cache-dir --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121

# CPU-only (kein CUDA):
pip install llama-cpp-python==0.3.32 --force-reinstall --no-cache-dir --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

Verfügbare CUDA-Versionen: `cu118`, `cu121`–`cu125`, `cu130`, `cu132`  
Welche passt: `nvcc --version` oder `nvidia-smi` → Treiber ≥ 520 → cu121, Treiber ≥ 610 → cu132

### 5. Restliche Abhängigkeiten

```bash
pip install -r requirements.txt
```

> **Bekannte Versionsbeschränkungen:**
> - `transformers==4.51.3` – Version 5.x ist **inkompatibel** mit dem moondream2 Vision-Modell
> - `Pillow==10.4.0` – Version 11+ ist inkompatibel mit dem moondream-Paket
> - `pyvips` benötigt zusätzlich `pyvips-binary` für Windows (enthält die native DLL):
>   ```bash
>   pip install pyvips pyvips-binary
>   ```

### 6. Frontend

```bash
cd frontend
npm install
```

### 7. LLM-Modell herunterladen

Empfohlen: **Qwen2.5-14B-Instruct-Q4_K_M.gguf**

Download z.B. über [HuggingFace](https://huggingface.co/Qwen/Qwen2.5-14B-Instruct-GGUF) oder LM Studio.

Pfad in `.env` eintragen:
```
MODEL_PATH=C:/Pfad/zum/Modell/Qwen2.5-14B-Instruct-Q4_K_M.gguf
```

---

## Konfiguration

```bash
copy .env.example .env   # dann .env anpassen
```

| Variable | Beschreibung | Standard |
|---|---|---|
| `SOURCE_DIR` | Inbox-Ordner, der überwacht wird | – |
| `TARGET_BASE` | Zielverzeichnis für das Archiv | – |
| `MODEL_PATH` | Pfad zur GGUF-Modelldatei | – |
| `MAX_RETRIES` | LLM-Versuche pro Dokument | `3` |
| `N_GPU_LAYERS` | GPU-Layer für LLM (`-1` = alle auf GPU, `0` = CPU-only) | `-1` |
| `SENDER_SUBFOLDERS` | Unterordner pro Absender | `true` |
| `DB_PATH` | SQLite-Datenbank | `TARGET_BASE/archive.db` |

---

## Starten

```bash
start_all.bat          # Backend + Frontend gleichzeitig (Port-Guard enthalten)
```

oder manuell:

```bash
python -m uvicorn api.main:app --port 8000            # Backend
cd frontend && npm run dev                             # Frontend (Port 5173)
```

→ Web-UI: **http://localhost:5173**  
→ API-Docs (Swagger): **http://localhost:8000/docs**

---

## Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                        React Frontend                        │
│  Dashboard │ Dokumente │ Absender │ Monitor │ Dokument-Detail│
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────────────┐
│                     FastAPI Backend                          │
│  /documents  /senders  /stats  /monitor  /tax               │
└──────┬──────────────────────────────────────┬───────────────┘
       │                                      │
┌──────▼──────┐                    ┌──────────▼──────────┐
│  SQLite DB  │                    │   archiver.py        │
│  (FTS5)     │◄───────────────────│   Watchdog + Worker  │
└─────────────┘                    └──────────┬──────────┘
                                              │
                              ┌───────────────▼──────────────┐
                              │         archive.py            │
                              │  extract → LLM → validate    │
                              │  → DB → Filesystem           │
                              └───────────────┬──────────────┘
                                              │
                              ┌───────────────▼──────────────┐
                              │           llm.py              │
                              │  llama-cpp (lokal, kein API) │
                              │  Similar-Doc-Hint             │
                              │  Few-Shot-Injection           │
                              │  Keyword-Filter               │
                              └──────────────────────────────┘
```

### Verarbeitungs-Pipeline (pro PDF)

```
PDF eingelegt in SOURCE_DIR
  │
  ├─► Text extrahieren (PyMuPDF)
  │     └─► kein Text → Tesseract OCR
  │
  ├─► Duplikat-Check (SHA256 gegen hashes.json)
  │     └─► Duplikat → duplicates/ → DB status=duplicate
  │
  ├─► LLM-Prompt aufbauen:
  │     ├── System-Prompt (Kategorien, Regeln, JSON-Schema)
  │     ├── Few-Shot-Beispiele (aus feedback.json, max. 15)
  │     ├── Similar-Doc-Hint (letzte 3 Docs desselben Absenders aus DB)
  │     └── PDF-Text (erste 3000 Zeichen)
  │
  ├─► LLM klassifiziert → JSON:
  │     sender, date, document_type, category, summary, keywords
  │
  ├─► Validierung + Normalisierung:
  │     ├── Datum plausibel? (kein Zukunftsdatum)
  │     ├── Absender normalisiert (Alias-Matching, Fuzzy)
  │     ├── Absender-Override (pinned_category / excluded_categories)
  │     └── Keywords gegen Originaltext validiert (Halluzinationen entfernt)
  │
  ├─► DB: upsert_document → keywords update
  │
  └─► Datei → TARGET_BASE/{Kategorie}/{Jahr}/{Absender}/
```

---

## Features im Detail

### Automatische Klassifizierung
- **Absender** – Firma/Organisation, nie der Empfänger (Alexander/Sonja Staiger)
- **Datum** – aus dem Dokument, nicht das Archivierungsdatum; Zukunftsdaten werden zurückgewiesen
- **Dokumenttyp** – Rechnung, Vertrag, Bescheid, Kontoauszug u.a. (10 Typen)
- **Kategorie** – 14 Kategorien (Arbeit, Bank, Versicherung, KFZ, Wohnen …)
- **Zusammenfassung** – ein Satz auf Deutsch
- **Keywords** – 5–15 spezifische Begriffe (Beträge, Vertragsnummern, Produktnamen) für FTS5-Suche

### Lernfähigkeit (3 Ebenen)

**1. Few-Shot-Feedback** – jede manuelle Korrektur in der GUI wird in `feedback.json` gespeichert. Beim nächsten PDF bekommt der LLM die 15 aktuellsten Korrekturen als Kontext. Kategorie-Korrekturen werden priorisiert (max. 200 Einträge gesamt).

**2. Similar-Doc-Hint** – vor jeder Klassifizierung sucht das System in der DB nach den letzten 3 Dokumenten desselben Absenders und injiziert sie als Prompt-Kontext. Dadurch klassifiziert es wiederkehrende Rechnungen konsistent. Fallback: keyword-basiertes Kategorie-Matching (z.B. „kWh, Abrechnung" → Energie & Versorgung).

**3. Absender-Overrides** (`senders.json`):
- `pinned_category` – überschreibt LLM-Entscheidung dauerhaft
- `excluded_categories` – verhindert, dass der LLM eine entfernte Kategorie erneut wählt
- `aliases` – alte Absendernamen nach Umbenennung, LLM erkennt sie weiterhin (4-stufiges Matching: exact → alias → fuzzy canonical → fuzzy alias)

### Halluzinations-Filter
Der LLM neigt dazu, generische Begriffe wie „IBAN" oder „Vertragsnummer" als Keywords zu liefern statt der tatsächlichen Werte. `filter_keywords_against_text()` in `llm.py` prüft jedes Keyword gegen den Originaltext (normalisiert: Umlauts, Groß-/Kleinschreibung) und entfernt alles was nicht wörtlich vorkommt oder auf einer Blocklist steht.

### Absender-Verwaltung
- **Umbenennen** – alter Name wird als Alias gespeichert, alle DB-Einträge umgeschrieben, LLM erkennt weiterhin
- **Zusammenführen** – PDFs von Absender A → Ordner von Absender B, DB-Einträge aktualisiert
- **Reorganisieren** – alle PDFs eines Absenders in den korrekten Kategorie-Ordner verschieben
- **Kategorie entfernen** – mit Auswahl: belassen / nach Sonstiges / in andere Kategorie / Neu klassifizieren
- **Bestätigen-Workflow** – neue Absender als „unbestätigt" markiert, Badge in Sidebar, Filteransicht

### Dateisystem-Konsistenz
- **Scan-Missing** (`POST /monitor/scan-missing`) – prüft alle `ok`-Einträge gegen das Filesystem, markiert fehlende Dateien mit `status='missing'`
- **Bulk-Delete-Missing** (`DELETE /monitor/missing`) – löscht alle `missing`-Einträge auf einmal; umbenannte Dateien können danach neu eingelesen werden
- **Orphan-Scan** – findet PDFs im Archivordner ohne DB-Eintrag, ermöglicht Re-Import als `pending`
- Sidebar-Badge „Datei fehlt" aktualisiert sich alle 15 Sekunden

---

## Web-UI – Seiten

### Dashboard
- KPI-Karten: Gesamt / OK / Verschlüsselt / Fehlgeschlagen / Duplikate
- Balkendiagramm nach Kategorie und Jahr
- **Ablauf-Widget** – Dokumente die in ≤ 60 Tagen ablaufen
- **Steuer-Export** – ZIP-Download aller steuerrelevanten PDFs eines Jahres

### Dokumente
- Volltext-FTS5-Suche (durchsucht Inhalt, Zusammenfassung, Keywords)
- Filter: Kategorie / Jahr / Absender / Status
- **Aktive Filter-Pills** – zeigen aktive Filter, einzeln oder per „Alle löschen" aufhebbar
- Status-Dropdown: OK / Fehlgeschlagen / Verschlüsselt / Korrupt / Duplikat / **Datei fehlt**
- Schnell-Toggles: 🧾 Steuer / ⏰ Läuft ab
- Filter-Links sind URL-basiert (bookmarkbar, Zurück-Button funktioniert)

### Dokument-Detail
- PDF-Vorschau direkt im Browser
- Metadaten-Editor: Absender, Datum, Typ, Kategorie, Zusammenfassung
- **Tags** (kommagetrennt, als farbige Pills)
- **Steuer-Flag** + Steuerjahr
- **Ablaufdatum** (Datepicker)
- **Notizen** (Freitext)
- Datei umbenennen (Disk + DB synchron)
- Im Explorer öffnen
- Aktionen: Neu klassifizieren / Löschen inkl. Datei

### Absender-Manager
- Tabelle mit Absender-Name, **Dokument-Anzahl (Badge, klickbar → gefilterte Liste)**, Kategorien, feste Kategorie
- **Umbenennen** – Pencil-Icon, Modal mit Erklärung dass alter Name als Alias gespeichert wird
- **Alias-Pills** – alte Namen werden unter dem aktuellen Namen angezeigt
- **Kategorie entfernen** – Modal mit 4 Optionen für betroffene Dokumente
- Zusammenführen, Reorganisieren, Löschen
- Bestätigen-Workflow (blauer Punkt, Filter, Sidebar-Badge)

### Monitor
- **Live-Log** via SSE, farbkodiert (grün/gelb/rot nach Schweregrad)
- **Archiver Start/Stop** – Subprocess-Management, Output direkt im Log
- **Inbox-Panel** – PDFs in `SOURCE_DIR`, aktualisiert alle 5 Sekunden
- **Orphan-Panel** – PDFs im Archiv ohne DB-Eintrag, Checkbox-Auswahl, Bulk-Import
- **Fehlende-Dateien-Panel** – Scan-Button + Liste der `missing`-Einträge + „Alle löschen"-Button

### Sidebar (global)
- Badge „Absender": unbestätigte Absender
- Badge „Monitor": Anzahl PDFs in Inbox
- **Schnellfilter**: Duplikate / Fehlgeschlagen / Steuerrelevant / Läuft ab / **Datei fehlt**
- Alle Schnellfilter sind URL-basiert und landen direkt in der gefilterten Dokumentenliste

---

## Projektstruktur

```
document_processor/
├── archiver.py          Entry-Point: Watchdog-Loop + Worker-Thread
├── archive.py           process_pdf(): Text → LLM → DB → Filesystem
├── llm.py               Modell laden, klassifizieren, normalisieren
│                          build_similar_docs_hint()
│                          normalize_sender()  (4-stufig inkl. Aliases)
│                          filter_keywords_against_text()
├── config.py            Konstanten, Kategorien, System-Prompt (JSON-Schema)
├── db.py                SQLite CRUD, FTS5, Migrationen, Schema
├── storage.py           senders.json, hashes.json, Processing-Log
├── feedback.py          Few-Shot: sammeln, priorisieren, in Prompt injizieren
├── pdf_utils.py         Text-Extraktion (PyMuPDF), OCR (Tesseract), Dateinamen
├── scripts/
│   ├── extract_keywords.py  Batch-Nachextraktion für bestehende Dokumente
│   └── migrate_to_db.py     Einmalige Migration: Filesystem → SQLite
│
├── api/
│   ├── main.py          FastAPI-App, Router-Registrierung, CORS
│   ├── models.py        Pydantic-Modelle (Document, SenderEntry, …)
│   └── routes/
│       ├── documents.py  CRUD, Suche, Reprocess, Tax-Export, Delete-with-File
│       ├── senders.py    List, PATCH, Rename, Merge, Reorganize, Remove-Cat, Delete
│       ├── stats.py      KPI-Aggregation, by_category, by_year, by_status
│       ├── monitor.py    SSE-Log, Archiver-Control, Inbox, Scan-Missing,
│       │                  Delete-Missing, Orphan-Scan, Orphan-Import
│       └── tax.py        ZIP-Export steuerrelevanter PDFs
│
├── frontend/
│   └── src/
│       ├── App.tsx          Router, Sidebar, Sidebar-Badges (alle 15s)
│       ├── api.ts           Axios-Wrapper für alle API-Calls
│       └── pages/
│           ├── Dashboard.tsx
│           ├── Documents.tsx     (URL-basierte Filter)
│           ├── DocumentDetail.tsx
│           ├── Senders.tsx       (Rename-Modal, Doc-Count-Badge)
│           └── Monitor.tsx       (SSE, Orphan-Panel, Missing-Panel)
│
├── tests/
│   ├── test_db.py               Basis-CRUD, Suche, Stats
│   ├── test_db_extended.py      Expiring, Tax, FTS, Keywords
│   ├── test_storage.py          Sender-Registry, Hash-Registry
│   ├── test_storage_extended.py Reviewed-Flag, Excluded-Categories
│   ├── test_feedback.py         Few-Shot Sammlung + Priorisierung
│   ├── test_llm_utils.py        filter_keywords_against_text
│   ├── test_pdf_utils.py        Text-Extraktion, Dateinamen
│   ├── test_config.py           System-Prompt, Kategorien
│   └── test_validate.py         Klassifizierungs-Validierung
│
├── senders.json         Absender-Registry (categories, pinned, excluded, aliases)
├── hashes.json          SHA256-Hashes für Duplikat-Erkennung (In-Memory)
├── feedback.json        Gespeicherte Korrekturen für Few-Shot
├── .env                 Konfiguration (nicht im Repo)
├── .env.example         Vorlage
├── requirements.txt     Python-Abhängigkeiten
└── start_all.bat        Startet Backend + Frontend (mit Port-Guard)
```

---

## Datenbank-Schema (SQLite)

```sql
CREATE TABLE documents (
    id            INTEGER PRIMARY KEY,
    file_path     TEXT UNIQUE NOT NULL,
    filename      TEXT,
    sender        TEXT,
    date          TEXT,              -- YYYY-MM-DD oder YYYY
    document_type TEXT,
    category      TEXT,
    summary       TEXT,
    keywords      TEXT,              -- kommagetrennt, FTS5-indexiert
    content_hash  TEXT,
    status        TEXT DEFAULT 'ok', -- ok | duplicate | classification_failed |
                                     -- encrypted | corrupt | pending | missing
    archived_at   TEXT,
    tags          TEXT,
    tax_relevant  INTEGER DEFAULT 0,
    tax_year      TEXT,
    expires_at    TEXT,
    notes         TEXT
);

-- FTS5 Volltext-Index (sender, filename, summary, category, keywords)
CREATE VIRTUAL TABLE documents_fts USING fts5(...);
```

### Status-Werte

| Status | Bedeutung |
|---|---|
| `ok` | Erfolgreich klassifiziert und archiviert |
| `pending` | Wartet auf (Re-)Klassifizierung |
| `duplicate` | Inhaltlich identisch mit bestehendem Dokument |
| `classification_failed` | LLM-Klassifizierung fehlgeschlagen (max. Retries) |
| `encrypted` | PDF ist passwortgeschützt |
| `corrupt` | PDF nicht lesbar |
| `missing` | DB-Eintrag vorhanden, Datei nicht mehr im Filesystem |

---

## Kategorien

| # | Kategorie |
|---|---|
| 01 | Arbeit & Rente |
| 02 | Bank & Finanzen |
| 03 | Gesundheit |
| 04 | Versicherung |
| 05 | KFZ |
| 06 | Wohnen & Eigentum |
| 07 | Vermieter |
| 08 | Energie & Versorgung |
| 09 | Kommunikation |
| 10 | Einkauf & Bestellungen |
| 11 | Geräte & Garantie |
| 12 | Behörde & Urkunden |
| 13 | Ausbildung & Verein |
| 14 | Sonstiges |

---

## Archivstruktur

```
TARGET_BASE/
├── 01 - Arbeit & Rente/
│   └── 2025/
│       └── Arbeitgeber GmbH/
│           └── 20250101_Entgeltnachweis.pdf
├── 02 - Bank & Finanzen/
│   └── 2025/
│       └── Sparkasse/
│           └── 20250301_Kontoauszug.pdf
├── duplicates/          ← Duplikate mit Hash-Unterordner
├── failed/              ← Klassifizierung fehlgeschlagen
├── encrypted/           ← passwortgeschützte PDFs
└── archive.db           ← SQLite-Datenbank
```

---

## Tests

```bash
python -m pytest tests/ -v
# 92 Tests in 9 Dateien
```

| Testdatei | Abgedeckte Bereiche |
|---|---|
| `test_db.py` | Basis-CRUD, Suche, Stats |
| `test_db_extended.py` | Expiring, Tax-Docs, FTS-Keywords, Few-Shot-Prio |
| `test_storage.py` | Sender-Registry, Hash-Registry |
| `test_storage_extended.py` | `reviewed`-Flag, `excluded_categories` |
| `test_feedback.py` | Few-Shot sammeln, Kategorie-Priorisierung |
| `test_llm_utils.py` | `filter_keywords_against_text` (Blocklist, Umlauts, Fuzzy) |
| `test_pdf_utils.py` | Text-Extraktion, Dateinamen-Generierung |
| `test_config.py` | System-Prompt, Kategorienliste |
| `test_validate.py` | Datum-Validierung, Kategorie-Check |

---

## Hilfsskripte

```bash
# Keywords nachträglich für bestehende Dokumente extrahieren
python scripts/extract_keywords.py              # alle ohne Keywords
python scripts/extract_keywords.py --limit 10  # nur 10 (zum Testen)
python scripts/extract_keywords.py --force     # auch vorhandene überschreiben
python scripts/extract_keywords.py --dry-run   # zeigt was gemacht würde

# Einmalige Migration: Filesystem-Struktur → SQLite
python scripts/migrate_to_db.py
```

---

## Changelog

### 2026-06-28
- **fix**: `scan-missing` prüft jetzt alle DB-Einträge (nicht nur `status=ok`)
- **fix**: `GET /documents/expiring` und `/tax-export` kollidierten mit `/{doc_id}` → `422`-Fehler behoben (Reihenfolge der Routes korrigiert)
- **fix**: `stop_all.bat` verwendete `Stop-Process` statt `taskkill /F /T` → uvicorn-Reloader-Subprocess blieb am Leben
- **fix**: `POST /senders/reload` kollidierten mit `PATCH /{name}` → Route auf `POST /senders/~reload` verschoben
- **fix**: `senders.json` war in Git getrackt (persönliche Daten) → aus Tracking entfernt
- **feat**: Archiver startet automatisch beim Öffnen der Monitor-Seite
- **feat**: SSE-Verbindung reconnectet automatisch alle 3 Sekunden bei Abbruch
- **feat**: Dashboard zeigt eigene KPI-Karte „Datei fehlt" (`missing`-Status), nicht mehr in „Fehlgeschlagen" gezählt
- **feat**: `Neu laden`-Button im Absender-Manager lädt `senders.json` ohne Backend-Neustart
- **feat**: `stop_all.bat` – beendet Backend + Frontend zuverlässig
- **chore**: App umbenannt zu **PaperVault**
- **chore**: Root aufgeräumt, Hilfsskripte nach `scripts/` verschoben
