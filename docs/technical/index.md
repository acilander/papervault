# Technische Tiefe

Detaillierte Dokumentation für Entwickler und Power-User: Architektur, Logik, Mathematik und Algorithmik pro Feature.

## Kapitel

| Nr. | Thema | Beschreibung |
|-----|-------|--------------|
| 01 | [Pipeline und Import](01-pipeline-and-import.md) | Textextraktion, OCR, Hash, Duplikat-Check, LLM-Klassifikation, Archivierung |
| 02 | [Dokumente: Suche und Filter](02-documents-search-and-filter.md) | FTS5, Filter-Logik, Sortierung, Pagination, Bulk-Edit |
| 03 | [Ignore / Lock](03-ignore-lock.md) | Hash-Registry, Schutzmechanismen, API, Dateisystem-Auswirkungen |
| 04 | [Geringer-Wert-Regeln](04-low-value-rules.md) | Regel-Matching, SQL, Betragsprüfung, API |
| 05 | [Duplikate](05-duplicates.md) | SHA256-Hash-basierte Duplikat-Erkennung |
| 06 | [Absender](06-senders.md) | Sender-Registry, Kategorie-Pins, Merge, Audit |
| 07 | [Steuer-Modul](07-tax-module.md) | Steuerjahre, Positionen, Extraktion, Vergleich |
| 08 | [Sammlungen](08-collections.md) | Collections, Dokumenten-Zuordnung, ZIP-Export |
| 09 | [KI-Suche und Chat](09-chat-and-llm.md) | LLM-Integration, Prompting, Token-Management |
| 10 | [Monitor](10-monitor.md) | SSE-Stream, Live-Verarbeitung, Archiver |
| 11 | [Feedback](11-feedback.md) | Feedback-Erfassung und Migration |
| 12 | [Einstellungen](12-settings-and-config.md) | Konfiguration, Pfade, Umgebungsvariablen |
| 13 | [Inventar, Verträge, Ausgaben](13-inventory-contracts-services.md) | Entitäten-Module und Datenmodelle |
| 14 | [Two-Stage Klassifizierung & Bugfixes](14-two-stage-classification.md) | Pipeline-Optimierung und Behebung von fünf kritischen Bugs |
