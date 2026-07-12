# PaperVault – Systemarchitektur

## 1. Übersicht

PaperVault ist eine lokale Dokumentenarchivierungslösung mit drei Hauptschichten:

1. **Frontend**: React + Vite + Tailwind CSS (läuft im Browser)
2. **Backend**: FastAPI (Python) mit SQLite-Datenbank
3. **Pipeline**: Lokale KI-Klassifikation und Dateiverarbeitung

```
┌─────────────────────────────────────┐
│  Browser (React SPA)                │
│  http://localhost:5173              │
└──────────────┬──────────────────────┘
               │ REST (axios)
┌──────────────▼──────────────────────┐
│  FastAPI Backend                    │
│  http://localhost:8000               │
│  - API-Routes                       │
│  - Repository-Schicht               │
│  - SQLite Datenbank                 │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Pipeline (llm, archiver, steps)    │
│  - OCR / Textextraktion             │
│  - LLM-Klassifikation               │
│  - Dateiarchivierung                │
└─────────────────────────────────────┘
```

## 2. Datenfluss beim Import

```
1. PDF landet im INBOX_DIR
2. Monitor erkennt Datei oder Nutzer startet Archiver manuell
3. Pipeline:
   a. PDF → Text (native) oder OCR (gescannt)
   b. Duplikat-Check via SHA256-Hash
   c. LLM extrahiert Metadaten (Sender, Datum, Kategorie, Typ, Betrag, ...)
   d. Datei wird nach TARGET_BASE/Kategorie/Sender/Jahr/Monat/ verschoben
   e. SQLite-Eintrag in `documents` wird erstellt
4. Frontend zeigt Dokument in Inbox / Dokumentenliste an
```

## 3. Verzeichnisstruktur

```
papervault/
├── backend/
│   ├── api/           # FastAPI Routes und Pydantic-Modelle
│   ├── db/            # SQLite-Schema, Repositories, Verbindung
│   ├── pipeline/      # Archiver, Verarbeitungsschritte
│   ├── tax/           # Steuer-Modul Extraktion / Prompts
│   ├── llm.py         # LLM-Abstraktion
│   ├── storage.py     # Dateisystem-Operationen, Sender-Registry
│   └── config.py      # Konfiguration und Pfade
├── frontend/
│   ├── src/
│   │   ├── pages/     # Seitenkomponenten
│   │   ├── components/# Wiederverwendbare Komponenten
│   │   ├── api.ts     # API-Client
│   │   └── ConfigContext.tsx
│   └── vite.config.ts # Dev-Proxy
├── tests/             # pytest-Suite
└── scripts/           # Hilfsskripte
```

## 4. Datenbank

SQLite-Datenbank mit folgenden Kern-Tabellen:

| Tabelle | Zweck |
|---------|-------|
| `documents` | Alle Dokumente mit Metadaten, Status, Text |
| `documents_fts` | FTS5-Volltextindex für schnelle Suche |
| `protected_document_hashes` | SHA256-Hashes für Ignore/Lock-Schutz |
| `low_value_rules` | Regeln für geringe Werte |
| `collections` / `collection_documents` | Sammlungen |
| `tax_years`, `tax_documents`, `tax_positions` | Steuer-Modul |
| `items`, `services`, `contracts` | Extrahierte Entitäten |
| `senders` | Sender-Registry (JSON-Datei, nicht SQLite) |

## 5. Frontend-Architektur

- **React Router** für Seitennavigation.
- **ConfigContext** liefert globale Konfiguration (Kategorien, Dokumententypen).
- **API-Client** (`api.ts`) kapselt alle Backend-Aufrufe.
- **Tailwind CSS** für Styling, Dark Mode über `dark`-Klasse.

## 6. Sicherheit & Datenschutz

- Alle Daten bleiben lokal.
- Kein Cloud-LLM; optional GPU-beschleunigtes lokales LLM.
- Passwortgeschützte Bereiche sind nicht implementiert – Tool für lokale Nutzung gedacht.

## 7. Erweiterbarkeit

Neue Features werden typischerweise so hinzugefügt:

1. DB-Schema in `backend/db/schema.py`
2. Repository in `backend/db/`
3. API-Router in `backend/api/routes/`
4. Router in `backend/api/main.py` registrieren
5. Frontend-Seite in `frontend/src/pages/`
6. Route in `frontend/src/App.tsx` hinzufügen
7. Vite-Proxy in `frontend/vite.config.ts` ergänzen
8. Tests in `tests/`

## 8. Wichtige Algorithmen (Überblick)

| Bereich | Algorithmus / Methode |
|---------|----------------------|
| Duplikat-Erkennung | SHA256-Hash des Dokumententextes |
| Volltextsuche | SQLite FTS5 über Trigger synchronisiert |
| Klassifikation | Lokales GGUF-LLM mit strukturiertem JSON-Prompt |
| Low-Value-Matching | SQL mit optionalem EXISTS-Subquery über `items/services/contracts` |
| Sender-Lernen | Häufigkeitsanalyse + manuelle Review-Pins |

## Siehe auch

- [`docs/USER_GUIDE.md`](USER_GUIDE.md) – Bedienungsanleitung
- [`docs/technical/`](technical/) – Detaillierte technische Kapitel
