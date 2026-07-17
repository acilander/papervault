# PaperVault – Feature-Übersicht

Stand: 2026-07-14 (RTX 3060 Power-Features & MFH Update)

## Kern-Features

### PDF & Office Archivierungspipeline
- Überwacht den Inbox-Ordner auf neue PDFs, `.docx` und `.xlsx` Dateien (Zero-Dependency Word/Excel Support). Originaldateinamen von Office-Dokumenten bleiben erhalten.
- Extrahiert Text aus nativen und gescannten PDFs (OCR via Tesseract/Poppler).
- **Lokales VLM OCR Fallback:** Nutzt Moondream2 (GPU) für perfektioniertes OCR, wenn PyTesseract bei Fotos oder schiefen Scans < 50 Zeichen liefert.
- Klassifiziert Dokumente lokal mit einem GGUF-LLM (llama-cpp-python, keine Cloud).
- Ordnet Dokumente automatisch in eine hierarchische Ordnerstruktur ein (`Kategorie/Sender/Jahr/Monat/`).

### Haus & Vermietung (MFH)
- **Mehrfamilienhaus-Architektur (MFH):** Zuordnung von Dokumenten, Verträgen und Inventar zu Wohneinheiten (EG, OG, DG, UG, Gesamthaus).
- **Vermieter-Rolleninversion:** Ausgehende Dokumente (z.B. an Mieter) werden in `00_Ausgehend_Vermieter` archiviert, wenn der Archivbesitzer der Sender ist.
- **Predictive Utility Forecasting:** `/monitor/forecast` berechnet mit Numpy Polyfit (lineare Regression) historische Nebenkosten (Strom, Wasser) und gibt natürliche Sprach-Empfehlungen für Mieter-Vorauszahlungen.
- **Contract Risk Auditor:** Die KI scannt Verträge auf Risiken ("Indexmiete", "Staffelmiete", "Selbstbeteiligung") und hinterlegt automatisch Warnungen in den Notizen.

### Asset & Family Tracking
- Automatische Erkennung und Tagging von `vehicle_id` (z.B. Golf, Tesla, Motorrad) und `child_name` (z.B. Lena, Felix).
- Ablage im Dateisystem in dedizierten Unterordnern für Fahrzeuge und Kinder.

### Dokumentenverwaltung
- Listenansicht mit Suche, Filtern und Sortierung.
- Grid-Ansicht mit Thumbnails.
- Detailansicht zum Bearbeiten von Metadaten (Sender, Datum, Kategorie, Dokumententyp, Tags, Steuerjahr, Wohneinheit, Notizen, Ablaufdatum, …).
- Status-Workflow: `ok`, `review`, `pending`, `duplicate`, `missing`, `encrypted`, `corrupt`, `no_text`, `classification_failed`, `ignored`, `locked`.
- Bulk-Edit für mehrere Dokumente.
- Download und Wiederherstellung (Undo) für Bulk-Edits.

### Dokumentenschutz & Human-in-the-Loop Daten-Locking
- **Ignore**: Dokumente als irrelevant markieren, aus der Standardliste ausblenden, Hash in Registry speichern, Datei in `ignored/`-Ordner verschieben.
- **Lock & Verifizieren**: Dokumente mit dem `verified`-Flag (`verified = 1`) dauerhaft sperren. Gesperrte/verifizierte Belege sind schreibgeschützt, blockieren Inferenzupdates des LLMs und verhindern schleichende KI-Datenkorruption ("AI-Drift").
- Geschützt durch `protected_document_hashes` (SHA256-Hash-Präfix) und die `verified` Spalte der SQLite-Datenbank.

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

### Steuer-Modul (Tax) & Proactive Linking
- Steuerjahre anlegen und verwalten.
- **Proactive Tax Linking (Phase 8c):** Dokumente der Kategorien `Haus_Gemeinkosten`, `OG_Miete` oder `DG_Miete` werden vollautomatisch als Entwurf mit dem passenden Steuerjahr verknüpft.
- Automatische/manuelle Zuordnung von Dokumenten zu Steuerjahren.
- Steuerpositionen (Einnahmen / Ausgaben).
- Jahresvergleich, Entwicklungsübersicht.

### Sammlungen (Collections)
- Dokumente in thematischen Sammlungen gruppieren.
- Detailansicht pro Sammlung.

### Inventar, Verträge & Ausgaben
- **Inventar:** Verwaltung von Gegenständen/Geräten aus Dokumenten, inkl. Wohneinheiten.
- **Verträge:** Erfassung und Übersicht von Verträgen, Risiko-Auditing (Staffelmiete etc.).
- **Ausgaben (Services):** Erfassung wiederkehrender / einmaliger Ausgaben.

### KI-Suche (Chat) & Hybrid RAG
- **Hybrid RAG:** Kombiniert semantische Vektorsuche (Embeddings in SQLite BLOBs, Cosine Similarity via Numpy im RAM) mit FTS5 Keywords.
- Chat-Interface mit lokalem LLM.
- Steuer-spezifischer Chat.

### Inbox-Monitor
- Live-Überwachung des Inbox-Ordners.
- SSE-Stream für Status-Updates.

### UI/UX
- Sidebar in 4 Bereiche gegliedert: "Eingang & Suche", "Haus & Vermietung", "Steuern & Qualität", "System".
- Die klassische "Inbox" Seite heißt jetzt "Prüfung".
- React + Vite + Tailwind CSS.
- Dark Mode.
- Sidebar mit Schnellfiltern und Badges.

## Backend

- FastAPI mit SQLite (FTS5 + BLOB).
- Repository-Pattern für DB-Zugriff.
- Automatische OpenAPI-Doku unter `/docs` (wenn Server läuft).
- CORS konfiguriert für den Vite-Dev-Server.

## Tests

- Python-Tests mit pytest.
- Abdeckung für API, Pipeline-Schritte, Repositories, Archiver und weitere Module.
