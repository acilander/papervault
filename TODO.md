# PaperVault – Zukunftsplan & Roadmap

Dieses Dokument dokumentiert die historische Entwicklung, bereits gemeisterte Meilensteine sowie die aktuelle Roadmap für **PaperVault**.

---

## 📜 Historie & Architektur-Entwicklung (Erledigt)

Hier sind die Meilensteine dokumentiert, die im Rahmen des Architektur-Refactorings erfolgreich aus der Legacy-Version in das moderne Datenbank-System überführt wurden.

### 1. JSON-Datenspeicher in SQLite migrieren (Historisch)

*   **✅ `hashes.json` → vollständig entfernt**
    *   Die SQLite-Spalte `content_hash` ist nun die alleinige Quelle für Integrität und Duplikatsprüfung.
*   **✅ `senders.json` → Tabelle `senders` (Repository-Pattern)**
    *   `db/sender_repo.py` implementiert alle CRUD-Operationen gegen SQLite.
*   **✅ `feedback.json` → Tabelle `feedback` (erledigt)**
    *   Manuelle Belegkorrekturen werden als Few-Shot-Beispiele für den LLM-Prompt in der Tabelle `feedback` gespeichert.

### 2. Code Smells & Refactoring-Erfolge (Historisch)

*   **✅ Keine Persistenz in HTTP-Routes:** Alle direkten Datei-Interaktionen wurden durch standardisierte Repository-Aufrufe (`sender_repo`, `feedback_repo`) ersetzt.
*   **✅ Beseitigung globaler mutabler Zustände:** Die globale `sender_registry` schreibt nur noch über Repositories und nutzt einen Thread-sicheren Cache über `_refresh_cache()`.
*   **✅ Aufteilung des God-Moduls `config.py`:** Zuvor enthielt `config.py` Pfade, Listen und Prompts. Aufgeteilt in `config.py` (Pfade/Env), `categories.py` (Kategoriendefinitionen) und `prompts.py` (System-Prompt-Builder).
*   **✅ Entflechtung der God-Function `process_pdf()`:** Aufgeteilt in 7 klar benannte, testbare Phasen in `backend/pipeline/core.py`.
*   **✅ Inline-Imports entfernt:** Alle verspäteten Imports inmitten von Funktionen an den Dateianfang verlagert.
*   **✅ Lazy-Loading für Vision-Modelle:** `vision._model` von einer globalen Variable in ein Singleton-Pattern innerhalb der `VisionService`-Klasse umgewandelt.

### 3. Bugs & Architekturbereinigungen (Behoben - Juli 2026)

*   **✅ Bug #1: OCR File Lock Leak** (`backend/pdf_utils.py`)
    *   *Lösung:* Kapselung von `fitz.open` in einen robusten `try-finally`-Block innerhalb von `ocr_pdf()`, um Dateisperren unter Windows bei OCR-Fehlern auszuschließen.
*   **✅ Bug #2: GPU-Zwang blockiert CPU-only Modus** (`backend/api/main.py`, `backend/llm/driver.py`)
    *   *Lösung:* Anpassen von `assert_gpu_support()` zu einer weichen Assertion (Log-Warnung), wenn `N_GPU_LAYERS = 0` (CPU-only) gewählt ist.
*   **✅ Bug #3: Preload Thread-Safety Race Condition** (`backend/llm/driver.py`)
    *   *Lösung:* Double-Checked Locking in `load_model()` / `get_llm()` mittels `_llm_lock` implementiert.
*   **✅ Bug #4: Sender Overrides erzwingen Legacy-Kategorien** (`backend/storage.py`)
    *   *Lösung:* Ignorieren generischer Overrides wie `"Rechnung"`, wenn das LLM bereits spezifische Typen (`Warenrechnung`, `Dienstleistungsrechnung`) geliefert hat.
*   **✅ Bug #5: Toter/Verwaister Hashing-Code** (`backend/storage.py`, `tests/test_storage.py`)
    *   *Lösung:* Entfernung von `content_hashes` und `load_hashes()` im Backend sowie entsprechende Bereinigung in der Testsuite.
*   **✅ Monitor-Stopp-Typo im Controller** (`backend/api/routes/monitor.py`)
    *   *Lösung:* Behebung des Tippfehlers in der Route `@router.post("/router/stop")` -> `@router.post("/archiver/stop")`, wodurch der Stopp-Button im UI wieder einwandfrei funktioniert.
*   **✅ Separation of Concerns (LLM-Modul)** (`backend/llm/driver.py` vs. `backend/llm/classify.py`)
    *   *Lösung:* Abspaltung des High-Level-Klassifizierers und aller Normalisierungshelfer in ein eigenständiges Modul `classify.py`. `driver.py` ist nun ein reines Low-Level-Inferenzmodul.
*   **✅ Modularisierung von `pdf_utils.py`**
    *   *Lösung:* Auslagerung der PDF-Thumbnails in `pdf_thumbnails.py` und der SimHash-Klassen in `pdf_hashing.py` zur Steigerung der Kohäsion und Kapselung.

### 4. Features & Optimierungen (Behoben - Juli 2026)

*   **✅ Typ-Spalte im Frontend:** Spalte für den spezifischen Dokumenttyp in der Hauptdokumentenliste hinzugefügt.
*   **✅ Tabellensortierung im gesamten UI:** Sortierung nach Spalten für Dokumente, Verträge, Ausgaben, Inventar und Sammlungen vollständig implementiert.
*   **✅ Opt #1: SimHash-Bypass für periodische Dokumente** (`backend/pipeline/core.py`)
    *   *Lösung:* Überspringen des SimHash-Vergleichs für Gehaltsabrechnungen/Kontoauszüge mittels `is_periodic_document()`, wodurch Fehlalarme („Scan-Duplikat“) und das Zurücksetzen des Vertrauens auf `low` verhindert werden.
*   **✅ Opt #2: Multi-Prozess Pfad-Synchronisation** (`backend/api/routes/config.py`, Settings UI)
    *   *Lösung:* Einbau einer gut sichtbaren Warnbox in der Settings-UI sowie eines Hinweistextes im API-Response bei Pfad-Änderungen, dass ein Neustart der App (`start_all.bat`) zwingend erforderlich ist.

---

## 🔄 Geplante Optimierungen (Ausblick)

*   **[ ] Feingranulare Settings-UI** (`frontend/src/pages/Settings.tsx`)
    *   *Zustand:* Hochdynamische Kategorien-Mappings (`categories_config` und `category_folder_map`) sind in der `settings.json` vorhanden, lassen sich aber im UI noch nicht komfortabel konfigurieren.
    *   *Geplante Lösung:* Ausbau der Settings-UI zu einem vollwertigen Konfigurations-Dashboard.
*   **[ ] Modell-Kaskade (LLM Cascade scenarios)**
    *   *Zustand:* Die Klassifizierung läuft über einen allumfassenden JSON-Prompt, was Inferenzzeit kostet und fehleranfällig ist.
    *   *Geplante Lösung:* 1. Stufe extrahiert nur Metadaten (Typ, Absender) -> 2. Stufe leitet an spezialisierten Prompt weiter (z. B. getrennte Felder für Handwerkerrechnungen nach § 35a EStG).
*   **[ ] Schnellfilter-Verschiebung im UI**
    *   *Zustand:* Filter wie "Eilt" oder "Ausstehend" nehmen wertvollen Platz in der globalen linken Menüleiste ein.
    *   *Geplante Lösung:* Filter direkt in die jeweilige Tabellenansicht überführen, um das Seitenmenü sauber zu strukturieren.
