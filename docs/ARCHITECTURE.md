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

## 2. Verzeichnisstruktur

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

## 3. Datenbank (Kern-Tabellen)

| Tabelle | Zweck |
|---------|-------|
| `documents` | Alle Dokumente mit Metadaten, Status, Text |
| `documents_fts` | FTS5-Volltextindex für schnelle Suche |
| `protected_document_hashes` | SHA256-Hashes für Ignore/Lock-Schutz |
| `low_value_rules` | Regeln für geringe Werte |
| `collections` / `collection_documents` | Sammlungen |
| `tax_years`, `tax_documents`, `tax_positions` | Steuer-Modul |
| `items`, `services`, `contracts` | Extrahierte Entitäten |

## 4. Sicherheit & Datenschutz

- Alle Daten bleiben lokal.
- Kein Cloud-LLM; optional GPU-beschleunigtes lokales LLM.

## 5. Erweiterbarkeit

Standard-Workflow für neue Features:

1. DB-Schema in `backend/db/schema.py`
2. Repository in `backend/db/`
3. API-Router in `backend/api/routes/`
4. Router in `backend/api/main.py` registrieren
5. Frontend-Seite in `frontend/src/pages/`
6. Route in `frontend/src/App.tsx` hinzufügen
7. Vite-Proxy in `frontend/vite.config.ts` ergänzen
8. Tests in `tests/`

## Detaillierte technische Kapitel

| Thema | Kapitel |
|-------|---------|
| Pipeline & Import | [`technical/01-pipeline-and-import.md`](technical/01-pipeline-and-import.md) |
| Suche & Filter | [`technical/02-documents-search-and-filter.md`](technical/02-documents-search-and-filter.md) |
| Ignore / Lock | [`technical/03-ignore-lock.md`](technical/03-ignore-lock.md) |
| Low-Value-Rules | [`technical/04-low-value-rules.md`](technical/04-low-value-rules.md) |
| Duplikate | [`technical/05-duplicates.md`](technical/05-duplicates.md) |
| Absender | [`technical/06-senders.md`](technical/06-senders.md) |
| Steuer-Modul | [`technical/07-tax-module.md`](technical/07-tax-module.md) |

## Siehe auch

- [`USER_GUIDE.md`](USER_GUIDE.md) – Bedienungsanleitung
- [`UI_REFERENCE.md`](UI_REFERENCE.md) – UI-Elemente
