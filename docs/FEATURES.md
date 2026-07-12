# PaperVault – Feature-Übersicht

Stand: 2026-07-12 (aus Code abgeleitet)

## Kern-Features

### PDF-Archivierungspipeline
- Überwacht den Inbox-Ordner auf neue PDFs.
- Extrahiert Text aus nativen und gescannten PDFs (OCR via Tesseract/Poppler).
- Klassifiziert Dokumente lokal mit einem GGUF-LLM (llama-cpp-python, keine Cloud).
- Ordnet Dokumente automatisch in eine hierarchische Ordnerstruktur ein (`Kategorie/Sender/Jahr/Monat/`).
- Speichert Metadaten in SQLite.

### Dokumentenverwaltung
- Listenansicht mit Suche, Filtern und Sortierung.
- Grid-Ansicht mit Thumbnails.
- Detailansicht zum Bearbeiten von Metadaten (Sender, Datum, Kategorie, Dokumententyp, Tags, Steuerjahr, Notizen, Ablaufdatum, …).
- Status-Workflow: `ok`, `review`, `pending`, `duplicate`, `missing`, `encrypted`, `corrupt`, `no_text`, `classification_failed`, `ignored`, `locked`.
- Bulk-Edit für mehrere Dokumente.
- Download und Wiederherstellung (Undo) für Bulk-Edits.

### Dokumentenschutz (Ignore / Lock)
- **Ignore**: Dokumente als irrelevant markieren, aus der Standardliste ausblenden, Hash in Registry speichern, Datei in `ignored/`-Ordner verschieben.
- **Lock**: Dokumente gegen Änderungen sperren; Duplikate desselben Hashes werden abgewiesen.
- Geschützt durch `protected_document_hashes` (SHA256-Hash-Präfix).

### Absender-Verwaltung
- Automatische Erkennung und Speicherung von Absendern.
- Zuordnung von Kategorie/Dokumententyp pro Absender.
- Anzeige unreviewter Absender im Sidebar-Badge.

### Duplikat-Erkennung
- Inhaltlicher Hash (SHA256) zur Erkennung von Duplikaten.
- Berücksichtigung von Ignore-/Lock-Hashes.
- Verschiebung von Duplikaten in einen separaten `duplicates/`-Ordner.

### Geringer-Wert-Regeln (Low Value Rules)
- Regelbasierte Markierung von Dokumenten als `low_value`.
- Filter nach Kategorie, Dokumententyp, Betrag (≤ max. Betrag aus items/services/contracts), Alter (Älter als X Tage).
- Vorschau-Funktion, bevor Regeln angewendet werden.

### Steuer-Modul (Tax)
- Steuerjahre anlegen und verwalten.
- Automatische/ manuelle Zuordnung von Dokumenten zu Steuerjahren.
- Steuerpositionen (Einnahmen / Ausgaben).
- Jahresvergleich, Entwicklungsübersicht, KI-Chat für Steuerfragen.

### Sammlungen (Collections)
- Dokumente in thematischen Sammlungen gruppieren.
- Detailansicht pro Sammlung.

### Inventar
- Verwaltung von Gegenständen/Geräten aus Dokumenten.

### Verträge
- Erfassung und Übersicht von Verträgen.

### Ausgaben (Services)
- Erfassung wiederkehrender / einmaliger Ausgaben.

### Validierung
- Validierungs-Workflow für Dokumente.

### Feedback
- Feedback-Mechanismus für einzelne Dokumente.

### KI-Suche (Chat)
- Chat-Interface mit lokalem LLM.
- Steuer-spezifischer Chat.

### Inbox-Monitor
- Live-Überwachung des Inbox-Ordners.
- SSE-Stream für Status-Updates.

### UI/UX
- React + Vite + Tailwind CSS.
- Dark Mode.
- Sidebar mit Schnellfiltern und Badges.

## Backend

- FastAPI mit SQLite.
- Repository-Pattern für DB-Zugriff.
- Automatische OpenAPI-Doku unter `/docs` (wenn Server läuft).
- CORS konfiguriert für den Vite-Dev-Server.

## Tests

- Python-Tests mit pytest.
- Abdeckung für API, Pipeline-Schritte, Repositories, Archiver und weitere Module.
