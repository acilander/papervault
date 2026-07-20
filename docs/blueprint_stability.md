# PaperVault Stabilitäts-Megaplan

Dieser Plan stabilisiert parallele Konfigurationsspeicherung, Start/Stop-Verhalten, Ignore-Dateibewegung, Trace-Verständlichkeit, adaptive LLM-Retries und die Git-Hygiene, ohne automatische fachliche Entscheidungen einzuführen.

## Zielbild und festgelegte Produktregeln

- **Settings-Konflikte:** Ein veralteter Speichervorgang erhält `409 Conflict`; die Oberfläche lädt die aktuelle Konfiguration neu, statt Daten zu überschreiben.
- **Ignore:** Ignorierte Dateien werden physisch nach `S:\papervault\ignored` verschoben. Bei Wiederherstellung wandern sie zurück in die Dokumentprüfung (`review`), damit der Nutzer erneut entscheidet.
- **Altbestand:** Bereits ignorierte Dokumente werden nicht pauschal migriert. Erst eine zukünftige Wiederherstellung bewegt eine vorhandene Datei in den Review-Ordner.
- **Trace-Texte:** Nutzeransichten zeigen lesbare Phasennamen; technische Schlüssel bleiben nur in Detaildaten.
- **LLM:** Empfehlungen und Retry-Fallbacks bleiben Hinweise. Kein Retry und keine KI-Empfehlung darf `ignored`, `ok` oder `locked` automatisch setzen.
- **Kompatibilität:** Keine neuen externen Abhängigkeiten; Windows/PowerShell 5.1, FastAPI, SQLite und bestehendes React/Tailwind-Stack bleiben erhalten.

## 1. Settings: revisionssicher, atomar und prozessübergreifend aktuell

### Problem

`config_manager` verwendet einen pro Prozess gecachten Settings-Stand. Ein älterer Backend-/Archiver-Prozess kann dadurch eine aktualisierte `settings.json` mit seinem veralteten Zustand überschreiben. Der derzeitige vollständige `PUT /config/settings` kennt keine Revision und kann keine Konflikte erkennen.

### Änderungen

- **`backend/config_manager.py`**
  - `settings_revision` als integerbasiertes Top-Level-Feld in `DEFAULT_SETTINGS` einführen.
  - Eine private Lesehilfe einführen, die `settings.json` jedes Mal frisch vom Datenträger liest, Defaults ergänzt und niemals automatisch persistiert.
  - `get_settings()` für reine Lesezugriffe am Cache festhalten, aber einen `force=True`-Pfad bzw. eine dedizierte Fresh-Read-Funktion für Schreiboperationen anbieten.
  - `save_settings(new_settings, expected_revision)` so umbauen:
    1. Aktuelle Datei frisch lesen.
    2. `expected_revision` gegen die Datei prüfen.
    3. Bei Abweichung einen klar unterscheidbaren Konfliktfehler auslösen.
    4. Bestehende Merge- und Kategorieintegritätsprüfung ausführen.
    5. Revision erhöhen.
    6. Die bisherige Backup-Datei erzeugen.
    7. In eine temporäre Datei schreiben und mit `os.replace` atomar ersetzen.
    8. Erst danach Cache und in-memory `config.CATEGORIES`/`config.DOCUMENT_TYPES` aktualisieren.
  - Eine Runtime-Refresh-Funktion ergänzen, die eine geänderte Revision erkennt und die in-memory Konfigurationslisten aktualisiert.

- **`backend/config.py` und `backend/pipeline/core.py` / Archiver-Einstieg**
  - Vor der Verarbeitung eines Dokuments die Runtime-Revision prüfen und die Listen aktualisieren.
  - Pfadänderungen bleiben bewusst restartpflichtig; Kategorien und Dokumenttypen dürfen ohne Prozessneustart konsistent aktualisiert werden.

- **`backend/api/routes/config.py`**
  - `PUT /settings` verlangt bzw. verarbeitet `settings_revision` aus dem Client-Payload.
  - Konflikt aus `config_manager` in `HTTP 409` mit verständlicher Detailmeldung übersetzen.
  - `POST /settings/document-types` arbeitet mit derselben Fresh-Read-/Revision-Logik, damit Human-in-the-Loop-Typfreigaben nicht gegen offene Settings-Formulare verlieren.
  - Der `GET`-Pfad liefert die aktuelle Revision zuverlässig mit aus.

- **`frontend/src/api.ts`, `frontend/src/ConfigContext.tsx`, `frontend/src/pages/Settings.tsx`**
  - `AppConfig` um `settings_revision` ergänzen.
  - Bei erfolgreichem Speichern die neue Serverkonfiguration übernehmen.
  - Bei `409` die Konfiguration neu laden und eine klare Meldung anzeigen: lokale Änderungen wurden nicht gespeichert, weil Einstellungen inzwischen geändert wurden.
  - Die gezielte Dokumenttypfreigabe aktualisiert den Context über die Serverantwort bzw. `reloadConfig()`.

### Tests / Abnahme

- Zwei simulierte Settings-Snapshots derselben Revision: erster Save erfolgreich, zweiter Save liefert Konflikt und verändert die Datei nicht.
- Ein frischer Save erzeugt eine um eins erhöhte Revision und eine gültige Backup-Datei.
- Ein Prozess mit veraltetem Cache kann keine neueren Dokumenttypen mehr überschreiben.
- Kategorien bleiben nur speicherbar, wenn Ordner- und Routingdefinitionen vollständig sind.
- Laufende Dokumentverarbeitung sieht neu freigegebene Dokumenttypen ohne Backend-/Archiver-Neustart; Pfadänderungen bleiben explizit restartpflichtig.

## 2. `start_all.ps1`: robuste Prozessbereinigung und verlässlicher Start

### Problem

Mit `$ErrorActionPreference = "Stop"` kann ein nativer `taskkill`-Fehler die Startsequenz abbrechen, wenn ein Prozess zwischen Prüfung und Beendigung bereits endet.

### Änderungen

- **`start_all.ps1`**
  - `Stop-ProcessTree` so umbauen, dass `taskkill`-Exitcodes für bereits beendete Prozesse nicht als terminierender Fehler behandelt werden.
  - Native Befehlsausgabe gezielt auffangen; nur unerwartete Fehler protokollieren.
  - `Stop-ProcessOnPort` beibehalten, aber optional kurz warten und den Port erneut prüfen, bevor Frontend/API gestartet werden.
  - Im API-Timeout-Fall beide gestarteten Prozesse best-effort beenden, ohne dass die Bereinigung den ursprünglichen Timeout verdeckt.
  - Klare Statusmeldungen für "bereits beendet", "beendet" und "konnte nicht beendet werden" ausgeben.

### Tests / Abnahme

- Scriptstart mit keinem Prozess auf Port 5173/8000.
- Scriptstart mit laufendem Frontend/API.
- Simulierter stale PID/zwischenzeitlich beendeter Prozess: kein Abbruch durch `taskkill`.
- API-Timeout beendet gestartete Kindprozesse und meldet den eigentlichen Timeout.

## 3. Ignore-/Unignore-Dateibewegung an die beschlossene Semantik anpassen

### Problem

Die API setzt aktuell nur Status und Hash-Sperre. Die beschlossene Regel verlangt das Verschieben nach `IGNORED_DIR` und bei Wiederherstellung zurück in die Dokumentprüfung.

### Änderungen

- **`backend/api/routes/documents.py`**
  - Bei `POST /documents/{id}/ignore`:
    1. Dokument und Hash laden/ermitteln.
    2. Datei, sofern vorhanden, mit `unique_path` nach `IGNORED_DIR` verschieben.
    3. Erst nach erfolgreichem Dateiumzug DB-Pfad, Dateiname und Status `ignored` aktualisieren.
    4. Hash mit Typ `ignored` schützen.
    5. Einen Trace mit Quell- und Zielpfad schreiben.
    6. Bei Move-Fehler keinen halbfertigen Ignore-Status hinterlassen; verständlichen Fehler liefern.
  - Bei `POST /documents/{id}/unignore`:
    1. Hash-Sperre entfernen.
    2. Vorhandene Datei mit `unique_path` nach `REVIEW_DIR` verschieben.
    3. DB-Pfad/Dateiname aktualisieren und Status auf `review` setzen.
    4. Einen Wiederherstellungs-Trace schreiben.
    5. Bei altem Ignore-Bestand außerhalb von `IGNORED_DIR` die vorhandene Datei trotzdem nach `REVIEW_DIR` bewegen.
    6. Bei fehlender Datei den Status nicht stillschweigend auf einen scheinbar prüfbaren Zustand setzen; stattdessen einen nachvollziehbaren Fehler oder `missing`-Status liefern.

- **`tests/test_documents_api.py`**
  - Ignore testet Status, Hash-Schutz, physische Datei in `IGNORED_DIR`, DB-Pfad und Trace.
  - Unignore testet Hash-Entfernung, physische Datei in `REVIEW_DIR`, Status `review`, DB-Pfad und Trace.
  - Fehlender Quellpfad und Kollision im Zielordner werden explizit abgedeckt.

- **`docs/technical/03-ignore-lock.md`**
  - Bestehende Dokumentation auf die beschlossene Restore-Regel `ignored → review` und die tatsächlichen Fehlerfälle aktualisieren.

### Tests / Abnahme

- Kein ignorierter Beleg bleibt im aktiven Archiv- oder Reviewpfad.
- Wiederhergestellte Belege erscheinen erneut in `Dokumentprüfung offen`.
- Gleicher Dateiinhalt wird nach Ignore weiterhin automatisch blockiert.
- Altbestand wird nicht beim Deployment verschoben.

## 4. Einheitliche, lesbare Pipeline-Phasen in allen Nutzeransichten

### Problem

`DocumentDetail` übersetzt einige Trace-Schlüssel lokal; die Dokumentprüfung zeigt technische Namen roh. Neue Phasen wie `document_type_approval` und `approval` benötigen ebenfalls verständliche Texte.

### Änderungen

- **Neues Frontend-Modul, z. B. `frontend/src/lib/traceLabels.ts`**
  - Zentralen `TRACE_STEP_LABELS`-Katalog definieren.
  - Vorhandene und neue Phasen abdecken: `ingest`, `text_extraction`, `duplicate_check`, `pre_analysis`, `llm_classification`, `document_type_approval`, `approval`, `archiving`, `contract_extraction`, `tax_linker`, `items_extraction`, `services_extraction`.
  - Fallback auf den technischen Schlüssel nur für unbekannte künftige Phasen.

- **`frontend/src/pages/Inbox.tsx`**
  - Die aufklappbare Pipeline-Timeline mit Label statt `trace.step_name` rendern.
  - Technischen Schlüssel optional nur im aufklappbaren Detailbereich zeigen.

- **`frontend/src/pages/DocumentDetail.tsx`**
  - Lokales `STEP_LABELS` durch das gemeinsame Modul ersetzen.
  - Export/Kopieren nutzt dieselbe lesbare Bezeichnung.

### Tests / Abnahme

- Jede bekannte Pipelinephase hat in beiden Ansichten dieselbe deutsche Bezeichnung.
- Neue unbekannte Phasen bleiben sichtbar statt zu brechen.
- Detail-JSON bleibt unverändert für Diagnosezwecke erreichbar.

## 5. Adaptive Retry-Strategie mit echten Modell-Mocks beweisen

### Problem

Die adaptive Logik ist implementiert, bisher aber vor allem über Helper- und Pipeline-Tests abgesichert. Die entscheidende Steuerung des LLM-Aufrufs braucht deterministische Unit-/Integrationstests mit Antwortsequenzen.

### Änderungen

- **`tests/test_llm_classify.py`** (neu oder bestehende Klassifikations-Testdatei erweitern)
  - Einen Fake für `_llm.create_chat_completion` verwenden, der kontrollierte Stage-1-/Stage-2-Antworten liefert und Nachrichten sowie Temperatur protokolliert.
  - `load_model` und Lock-Umgebung mocken, damit kein echtes Modell geladen wird.
  - Testfälle:
    1. Erster Versuch nutzt `temperature=0.0`; zweiter `0.15` in beiden Stufen.
    2. Nach Sender-/Summary-Validierungsfehler enthält der nächste Auftrag die feldbezogene Korrekturanweisung in beiden Stufen.
    3. Wiederholte identische Validierungssignatur beendet nach dem zweiten Auftreten und liefert reviewbares Low-Confidence-Ergebnis statt weiterer Schleife.
    4. Ungültiges JSON erhält einen speziellen JSON-Korrekturauftrag.
    5. Context-Overflow kürzt den Inhalt und behält diesen spezialisierten Retrypfad bei.
    6. Nur unbekannter Dokumenttyp wird sofort als Human-in-the-Loop-Vorschlag zurückgegeben, ohne weitere Retry-Schleife.
  - Diagnostics je Test auf Versuch, Failure-Type und vorgeschlagene Felder prüfen.

- **`backend/llm/classify.py`**
  - Falls Tests versteckte, nicht deterministische Stellen zeigen, Retry-Entscheidung als kleine testbare Hilfsfunktion kapseln; Verhalten und öffentliche API bleiben unverändert.

### Tests / Abnahme

- Kein Test lädt ein GGUF-Modell oder benötigt GPU.
- Drei identische LLM-Aufrufe ohne Anpassung sind nicht mehr möglich.
- Jeder Retry hat beobachtbar entweder neue Guidance, neue Temperatur, gekürzten Kontext oder beendet die Schleife mit Diagnose.

## 6. PID-Laufzeitdatei aus Git entfernen

### Änderungen

- **`.gitignore`**
  - `backend/archiver.pid` bzw. `*.pid` im Runtime-Abschnitt ignorieren.
  - Bestehende Datei aus dem Arbeitsbaum nicht löschen; sie bleibt Laufzeitstatus für `archiver_service`.

### Tests / Abnahme

- `git status --short` zeigt `backend/archiver.pid` nicht mehr.
- `backend/services/archiver_service.py` kann die Datei weiterhin schreiben, prüfen und bereinigen.

## Reihenfolge der Umsetzung

1. Settings-Revision, Fresh-Read, atomarer Save und Conflict-Handling.
2. `start_all.ps1` robust machen, danach Backend/Archiver sauber neu starten.
3. Ignore-/Unignore-Dateibewegung plus API-Tests.
4. Gemeinsame Trace-Labels in Dokumentprüfung und Detailansicht.
5. Adaptive Retry-Mocks und Diagnosetests.
6. PID-Gitignore.
7. Gesamtlauf: relevante Pytest-Suites, Frontend-Build, manuelle Smoke-Checks für Settings-Konflikt, Ignore/Restore, Trace-Übersetzung und Startscript.

## Commit-Aufteilung nach Umsetzung

1. **`feat(classification): add adaptive review diagnostics`**
   - Adaptive Retry-Guidance, kontrollierte Retry-Varianz und Wiederholungsabbruch.
   - Persistierte Klassifikationsdiagnosen und Human-in-the-Loop-Dokumenttypfreigabe.
   - Backend- und Klassifikations-/API-Tests einschließlich stabiler Testkonfiguration.

2. **`feat(review): surface decision signals in document review`**
   - Entscheidungskarte mit KI-Vertrauen, geringem Archivwert, Merkmalen und Fehlerdiagnosen.
   - Aufklappbare Trace-Details und zugehörige Frontend-API-Typen.

## Nicht im Scope

- Keine automatische KI-Ignore-Aktion.
- Keine Massenmigration bestehender ignorierter Dateien.
- Keine neuen externen Python- oder Frontend-Abhängigkeiten.
- Keine Änderung bestehender Archivstruktur außerhalb von künftig ignorierten bzw. wiederhergestellten Dateien.
