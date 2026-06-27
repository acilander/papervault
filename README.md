# Document Archiver

Automatisches PDF-Archivierungssystem mit lokalem LLM (llama-cpp-python).  
Überwacht einen Inbox-Ordner, klassifiziert PDFs und legt sie in einer strukturierten Ordnerhierarchie ab.

## Voraussetzungen

- Python 3.10+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (optional, für gescannte PDFs)
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases/) im PATH (für OCR)
- GGUF-Modell (z.B. Qwen2.5 1.5B oder größer)

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Konfiguration

Kopiere `.env.example` zu `.env` und passe die Pfade an:

```bash
copy .env.example .env
```

| Variable | Beschreibung |
|---|---|
| `SOURCE_DIR` | Inbox-Ordner der überwacht wird |
| `TARGET_BASE` | Zielverzeichnis für das Archiv |
| `MODEL_PATH` | Pfad zur GGUF-Modelldatei |
| `MAX_RETRIES` | Maximale LLM-Versuche pro Dokument (Standard: 3) |
| `SENDER_SUBFOLDERS` | Unterordner pro Absender anlegen (true/false) |

## Verwendung

```bash
# Archiver starten (überwacht Inbox dauerhaft)
python archiver.py

# Alle PDFs im failed/-Ordner erneut verarbeiten
python archiver.py --retry-failed

# senders.json aus bestehenden JSON-Sidecar-Dateien neu aufbauen
python archiver.py --reindex

# Tests ausführen
python -m pytest tests/ -v
```

## Archivstruktur

```
C:/Archive/
├── 01 - Arbeit & Rente/
│   └── 2025/
│       └── Arbeitgeber GmbH/
│           └── Entgeltnachweis_2025.pdf
├── 02 - Bank & Finanzen/
│   └── 2025/
│       └── Sparkasse Karlsruhe/
│           └── Kontoauszug_2025-03.pdf
├── duplicates/          ← erkannte Duplikate mit Shortcut zum Original
├── failed/              ← nicht klassifizierbare PDFs
└── encrypted/           ← passwortgeschützte PDFs
```

## Dateien

| Datei | Beschreibung |
|---|---|
| `archiver.py` | Entry-Point, Watchdog, Worker-Thread |
| `config.py` | Konstanten, Kategorien, System-Prompt |
| `storage.py` | senders.json, hashes.json, processing_log |
| `pdf_utils.py` | Text-Extraktion, OCR, Dateiname-Helpers |
| `llm.py` | Modell laden, klassifizieren, validieren |
| `archive.py` | process_pdf, Duplikat-Check, Reindex |
| `senders.json` | Bekannte Absender mit optionaler Kategorie-Festlegung |

## senders.json anpassen

Um einen Absender dauerhaft einer Kategorie zuzuordnen, setze `pinned_category`:

```json
{
  "Sparkasse Karlsruhe": {
    "categories": ["Bank & Finanzen"],
    "pinned_category": "Bank & Finanzen"
  }
}
```

Nach Änderungen an `senders.json` können bestehende Dateien mit dem Reorganize-Script verschoben werden:

```bash
python reorganize_archive.py --dry-run
python reorganize_archive.py --run
```

## Kategorien

| # | Kategorie |
|---|---|
| 01 | Arbeit & Rente |
| 02 | Bank & Finanzen |
| 03 | Gesundheit |
| 04 | Versicherung |
| 05 | KFZ |
| 06 | Wohnen & Eigentum |
| 07 | Vermieter |
| 08 | Energie & Versorgung |
| 09 | Kommunikation |
| 10 | Einkauf & Bestellungen |
| 11 | Geraete & Garantie |
| 12 | Behoerde & Urkunden |
| 13 | Ausbildung & Verein |
| 14 | Sonstiges |
