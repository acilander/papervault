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

#### ✅ `feedback.json` → neue Tabelle `feedback` (erledigt)
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

### ✅ Erledigt

**Zirkulärer Import als Workaround (`storage.py`)**
`import db as _db` innerhalb von `load_sender_registry()` entfernt; Modul-Import `import db` wird bereits am Dateianfang verwendet.

**`vision._model` als globale Variable**
In `VisionService`-Klasse mit lazy-load umgewandelt; `analyze_logo()` delegiert an Singleton-Instanz.

### 🟢 Offen (niedrig)

**Kein einheitlicher Error-Boundary in der Pipeline**
Jeder Step in `core.py` hat seinen eigenen Fehler-Pfad. Ein zentraler Pipeline-Runner mit einheitlicher Fehlerbehandlung wäre wartbarer.

---

## Features

- [x] Bulk-Reprocessing für Dokumente ohne Absender
- [x] GUI-Seite für Feedback-Verwaltung (Few-Shot-Beispiele einsehen/löschen)
- [x] Bulk-`low_value`-Markierung per Regel (Kategorie, Typ, Betragsschwelle)

## Meine Anmerkungen
- [x] neue Dokumente werden noch immer alls REchnung klassifiziert, obwohl wir neue Typen definiert haben
- [x] in Dokumente Liste feht die Typ Spalte
- [x] die Dokumente Liste lässt sich nicht nach den Spalten sortieren
- [x] wenn in der absender liste dokumente als review sind, die aber eine falsche Kategorie haben, wie kann ich alle auf die richtige Kategorie setzen?
- [x] alle tabellen sollen sich nach spalten sortieren lassen (Dokumente, Inventar, Ausgaben, Verträge, Sammlungen)
- [x] analysiere die Python vorverarbeitung auf verbesserungspotential
- [x] analysiere die beschreibungen der Dokumente in der sql datenbank und überprüfe ob die Kategorien und ordnerstruktur ausreichend ist
- [x] die menüstruktur an der linken seite ist historisch ewachsen aber nicht wirklich durchdacht. Schlage eine logischere umsetzung vor
- [x] wie ist deine einschätzung der funktion des Tax moduls, das mir bei der Steuer helfen soll?
- [x] Es werden dokumente als 100% duplikat erkannt, dabei sind es ähnlich strukturierte dokumente mit anderm datum z.B. Entgeltabrechnung. Wie kann man das verbessern.
- [x] warum kann ich in den settings nicht den pfad der dokumenten ablage definieren, wie ausgemacht?
- [x] wurde die KI-Suche mittlerweile verbessert und auf die ganze datenbank erweitert?
- [x] warum sind nicht alle settings aus dem json in der UI konfigurierbar? Das war doch der plan?
- [x] in den md datein haben wir eine neue individualle ordenerstruktur definiert. Findest du das?
- [x] Die promtgröße muss an das genutze modell angepasst werden.
- [x] ist die intelligente LLM kaskadae eingebaut? Ein grober prompt der dann an spezialisierte prompts weitergegebn wird?
- [x] brauche ich die schnellfilter noch im Hauptmenü oder können wir die besser in die ansicht verschieben in der sie auch relevant ist?