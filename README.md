# Document Archiver

Automatisches PDF-Archivierungssystem mit lokalem LLM (llama-cpp-python) und React Web-UI.  
Überwacht einen Inbox-Ordner, klassifiziert PDFs per LLM und legt sie in einer strukturierten Ordnerhierarchie ab. Alle Metadaten werden in einer SQLite-Datenbank gehalten und sind über eine FastAPI + React-Oberfläche verwaltbar.

---

## Voraussetzungen

- Python 3.10+
- Node.js 18+ (für das Frontend)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (optional, für gescannte PDFs)
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases/) im PATH (für OCR)
- GGUF-Modell (z.B. Qwen2.5 1.5B oder größer)

---

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

cd frontend
npm install
```

---

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
| `DB_PATH` | Pfad zur SQLite-Datenbank (Standard: `TARGET_BASE/archive.db`) |

---

## Starten

### Schnellstart (alles auf einmal)
```
start_all.bat
```

### Manuell
```bash
# Backend (Port 8000)
python -m uvicorn api.main:app --reload --port 8000

# Frontend (Port 5173)
cd frontend && npm run dev
```

→ Web-UI: **http://localhost:5173**  
→ API-Docs: **http://localhost:8000/docs**

---

## Archiver

Der Archiver kann direkt gestartet werden oder über die Web-UI (Monitor-Seite → Start-Button).

```bash
python archiver.py
```

Er überwacht `SOURCE_DIR` dauerhaft per Watchdog. Neue PDFs werden:
1. Text extrahiert (PyMuPDF, ggf. Tesseract OCR)
2. Per LLM klassifiziert (Absender, Datum, Kategorie, Typ, Zusammenfassung)
3. Validiert und ggf. automatisch korrigiert (Absender-Override, Few-Shot-Feedback)
4. In die SQLite-DB eingetragen
5. In den passenden Archiv-Ordner verschoben

---

## Web-UI – Seiten & Features

### Dashboard
- KPI-Karten: Gesamtzahl, OK, Verschlüsselt, Fehlgeschlagen, Duplikate
- Balkendiagramm nach Kategorie und Jahr
- **Ablauf-Widget**: Dokumente die in den nächsten 60 Tagen ablaufen
- **Steuer-Export**: ZIP-Download aller steuerrelevanten PDFs eines Jahres

### Dokumente
- Volltext-Suche + Filter: Kategorie, Jahr, Absender, Status
- Schnell-Toggle: 🧾 Steuerrelevant / ⏰ Läuft ab / Duplikate
- Klick auf Zeile → Dokument-Detail

### Dokument-Detail
- PDF-Vorschau direkt im Browser
- Metadaten-Editor: Absender, Datum, Typ, Kategorie, Zusammenfassung
- **Tags** (kommagetrennt, als farbige Pills dargestellt)
- **Steuer-Flag** + Steuerjahr
- **Ablaufdatum** (Datepicker)
- **Notizen** (Freitext)
- Datei umbenennen (ändert Dateiname auf Disk + DB)
- Im Explorer öffnen
- Aktionen für Problemdokumente: Neu klassifizieren, Löschen inkl. Datei

### Absender-Manager
- Tabelle aller bekannten Absender mit Kategorien
- **Bestätigen-Workflow**: Neue Absender sind als „unbestätigt" markiert (blauer Punkt), Zähler in der Sidebar
- **Filter „Nicht bestätigt"** – zeigt nur neue, noch nicht geprüfte Absender
- `pinned_category` per Dropdown setzen (überschreibt LLM dauerhaft)
- **Kategorie entfernen** – Modal mit 4 Optionen:
  - Dateien belassen (nur DB-Sperre, LLM wählt diese Kat nie wieder)
  - In Sonstiges verschieben
  - In andere Kategorie verschieben
  - Neu klassifizieren per LLM
- **Zusammenführen** – verschiebt alle PDFs des Quell-Absenders in den Zielordner und aktualisiert DB
- **Reorganisieren** – verschiebt alle PDFs eines Absenders in den korrekten Kategorie-Ordner
- Absender löschen

### Monitor
- Live-Log via Server-Sent Events (SSE), farbkodiert nach Schweregrad
- **Archiver Start / Stop** – startet `archiver.py` als Subprocess, Output fließt in den Live-Log
- **Inbox-Panel** (rechts): zeigt alle noch nicht verarbeiteten PDFs in `SOURCE_DIR` mit Größe und Datum, aktualisiert sich alle 5 Sekunden

### Sidebar (global)
- Badge bei „Absender": Anzahl unbestätigter Absender
- Badge bei „Monitor": Anzahl PDFs in der Inbox
- **Schnellfilter**: Duplikate / Fehlgeschlagen / Steuerrelevant / Läuft ab – direkter Sprung in gefilterte Dokumentenliste

---

## Lernfähigkeit / Feedback-Loop

Jede manuelle Korrektur in der GUI (Absender, Kategorie, Typ) wird als Few-Shot-Beispiel in `feedback.json` gespeichert. Der LLM bekommt beim nächsten Dokument die 15 zuletzt bestätigten Klassifizierungen als Kontext.

- `feedback.json` – max. 200 Einträge, Kategorie-Korrekturen bevorzugt
- `senders.json` – `excluded_categories` verhindert, dass der LLM entfernte Kategorien wieder wählt
- `pinned_category` – überschreibt LLM-Entscheidung vollständig für einen Absender

---

## Projektstruktur

| Datei / Ordner | Beschreibung |
|---|---|
| `archiver.py` | Entry-Point, Watchdog, Worker-Thread |
| `archive.py` | `process_pdf()`, Duplikat-Check, Datei verschieben |
| `config.py` | Konstanten, Kategorien, System-Prompt, Pfade |
| `db.py` | SQLite-Schema, CRUD, Suche, Migrationen |
| `llm.py` | Modell laden, klassifizieren, validieren, Few-Shot-Injection |
| `storage.py` | `senders.json`, `hashes.json`, Processing-Log |
| `feedback.py` | Few-Shot-Beispiele sammeln und in LLM-Prompt injizieren |
| `pdf_utils.py` | Text-Extraktion, OCR, Dateiname-Helpers |
| `api/` | FastAPI-Backend (routes: documents, senders, stats, monitor) |
| `frontend/` | React + Vite + TailwindCSS |
| `senders.json` | Absender-Registry mit Kategorien, pinned_category, excluded_categories |
| `hashes.json` | SHA256-Hashes für Duplikat-Erkennung |
| `feedback.json` | Gespeicherte Korrekturen als Few-Shot-Beispiele |
| `start_all.bat` | Startet Backend + Frontend gleichzeitig |

---

## Archivstruktur

```
TARGET_BASE/
├── 01 - Arbeit & Rente/
│   └── 2025/
│       └── Arbeitgeber GmbH/
│           └── 20250101_Entgeltnachweis.pdf
├── 02 - Bank & Finanzen/
│   └── ...
├── duplicates/     ← Duplikate (Shortcut zum Original)
├── failed/         ← nicht klassifizierbare PDFs
├── encrypted/      ← passwortgeschützte PDFs
└── archive.db      ← SQLite-Datenbank
```

---

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

---

## Tests

```bash
python -m pytest tests/ -v
```
