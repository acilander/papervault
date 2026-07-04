# PaperVault – Zukunftsplan

## Architektur-Refactoring

### JSON-Datenspeicher in SQLite migrieren

Aktuell werden drei JSON-Dateien als Datenspeicher verwendet. Langfristig sollten diese in die SQLite-DB überführt werden.

#### `hashes.json` → obsolet (jetzt sofort)
- Die DB ist bereits die Primärquelle (`content_hash`-Spalte in `documents`)
- `hashes.json` ist nur noch Legacy-Fallback in `storage.load_hashes()`
- **Aktion:** Fallback-Code aus `storage.py` entfernen, Datei aus Repo entfernen

#### `senders.json` → neue Tabelle `senders`
- Enthält: `pinned_category`, `excluded_categories`, `aliases`, `reviewed`-Flag
- **Vorteile DB:** Atomare Transaktionen, kein Dateizugriffs-Konflikt bei parallelen Schreibvorgängen, SQL-Queries statt JSON-Iteration
- Aktuell alles per GUI verwaltbar (Absender-Manager)

**Architektur-Problem (Root Cause):** `storage.py` mischt Datenzugriff, Business-Logik und Persistenz. Routes greifen direkt auf `storage.sender_registry` (globales Dict) zu und mutieren es. Das macht die Implementierung schwer austauschbar.

**Lösung – Repository-Pattern:**
```
SenderRepository (Interface/Abstract)
  ├── JsonSenderRepository   ← aktuelle Implementierung
  └── SqliteSenderRepository ← Ziel-Implementierung
```
Alle Routes sprechen nur gegen das Interface. Migration JSON → SQLite = Tausch der Implementierung, keine Route muss angefasst werden. Gleiches Prinzip für `FeedbackRepository`.

#### `feedback.json` → neue Tabelle `feedback`
- Enthält: manuelle Korrekturen als Few-Shot-Beispiele für den LLM-Prompt
- **Vorteile DB:** Feedback per GUI durchsuchbar und löschbar, kein unbegrenztes JSON-Wachstum, Priorisierung per SQL statt in-memory Sort
- **Aufwand:** Mittel – `feedback.py` umschreiben, GUI-Seite für Feedback-Verwaltung ergänzen

---

## Code Smells (priorisiert)

### 🔴 Hoch

**Persistenz-Logik in HTTP-Routes (`senders.py`)**
`open(SENDERS_FILE, "w")` steht 7× direkt in Route-Handlern. Persistenz gehört ins Repository, nicht in HTTP-Handler.

**Globaler mutabler Zustand (`storage.py`)**
`sender_registry` und `content_hashes` sind globale Dicts, direkt von Routes, `llm.py` und `pipeline/core.py` mutiert. Wird durch Repository-Pattern gelöst.

### 🟡 Mittel

**God Function `process_pdf()` (`pipeline/core.py`)**
292 Zeilen, macht alles: Extraktion, OCR, Duplikat-Check, LLM, Datei-Verschiebung, DB, Logging. Kaum als Einheit testbar. Aufteilen in klar benannte Pipeline-Steps mit definierten Ein-/Ausgaben.

**Zirkulärer Import als Workaround (`storage.py` Z.55)**
`import db as _db` innerhalb von `load_hashes()` ist ein Workaround für einen zirkulären Import. Fix: `db` per Dependency Injection übergeben statt globalen Import.

**`import` mitten in Funktionen (`senders.py` Z.63-64)**
`import json` und `from config import SENDERS_FILE` stehen innerhalb von Route-Funktionen obwohl sie oben bereits importiert sind. Bereinigen.

**`config.py` als God-Modul**
Enthält Pfade, Konstanten, Kategorien, Dokumenttypen, Owner-Namen und den kompletten LLM-System-Prompt (133 Zeilen). Aufteilen: `config.py` (Pfade/Env), `prompts.py` (System-Prompt), `categories.py` (Listen).

### 🟢 Niedrig

**`vision._model` als globale Variable**
Funktioniert, aber eine `VisionService`-Klasse mit `__init__` und lazy-load wäre sauberer und testbarer.

**Kein einheitlicher Error-Boundary in der Pipeline**
Jeder Step in `core.py` hat seinen eigenen Fehler-Pfad mit individuellem `return`. Ein zentraler Pipeline-Runner mit einheitlicher Fehlerbehandlung wäre wartbarer.

---

## Features

- [ ] Bulk-Reprocessing für Dokumente ohne Absender
- [ ] GUI-Seite für Feedback-Verwaltung (Few-Shot-Beispiele einsehen/löschen)
- [ ] Bulk-`low_value`-Markierung per Regel (Kategorie, Typ, Betragsschwelle)
