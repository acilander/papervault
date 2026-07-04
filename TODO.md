# PaperVault – Zukunftsplan

## Architektur-Refactoring

### JSON-Datenspeicher in SQLite migrieren

#### ✅ `hashes.json` → entfernt
- Legacy-Fallback aus `storage.py` entfernt, `HASHES_FILE` aus `config.py` entfernt
- DB `content_hash`-Spalte ist alleinige Quelle

#### ✅ `senders.json` → Tabelle `senders` (Repository-Pattern)
- `db/sender_repo.py` implementiert alle CRUD-Operationen gegen SQLite
- `storage.py` delegiert alle Schreibzugriffe an `sender_repo`
- Alle 7× `open(SENDERS_FILE, "w")` aus `senders.py` Routes entfernt
- Einmalige Migration von `senders.json` → DB beim ersten Start

#### `feedback.json` → neue Tabelle `feedback` (offen)
- Enthält: manuelle Korrekturen als Few-Shot-Beispiele für den LLM-Prompt
- **Vorteile DB:** Feedback per GUI durchsuchbar und löschbar, kein unbegrenztes JSON-Wachstum
- **Aufwand:** Mittel – `feedback.py` umschreiben, GUI-Seite für Feedback-Verwaltung ergänzen

---

## Code Smells

### ✅ Erledigt

- **Persistenz in HTTP-Routes** – alle `open(SENDERS_FILE)` durch `sender_repo`-Aufrufe ersetzt
- **Globaler mutabler Zustand (`sender_registry`)** – schreibt nur noch durch `sender_repo`, Cache via `_refresh_cache()`
- **`config.py` als God-Modul** – aufgeteilt in `config.py` (Pfade/Env), `categories.py` (Listen), `prompts.py` (System-Prompt)
- **God Function `process_pdf()`** – in 7 klar benannte Phasen aufgeteilt (`_register_doc`, `_extract_text`, `_build_user_hint`, `_stage_or_archive`)
- **`import` mitten in Funktionen** – alle Inline-Imports in `senders.py` entfernt

### 🟡 Offen (mittel)

**Zirkulärer Import als Workaround (`storage.py`)**
`import db as _db` innerhalb von `load_hashes()` ist ein Workaround für einen zirkulären Import. Fix: `db` per Dependency Injection übergeben.

### 🟢 Offen (niedrig)

**`vision._model` als globale Variable**
Funktioniert, aber eine `VisionService`-Klasse mit lazy-load wäre sauberer und testbarer.

**Kein einheitlicher Error-Boundary in der Pipeline**
Jeder Step in `core.py` hat seinen eigenen Fehler-Pfad. Ein zentraler Pipeline-Runner mit einheitlicher Fehlerbehandlung wäre wartbarer.

---

## Features

- [ ] Bulk-Reprocessing für Dokumente ohne Absender
- [ ] GUI-Seite für Feedback-Verwaltung (Few-Shot-Beispiele einsehen/löschen)
- [ ] Bulk-`low_value`-Markierung per Regel (Kategorie, Typ, Betragsschwelle)
