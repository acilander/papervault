# Technisch: Pipeline und Import

## 1. Ziel

PDFs aus dem Inbox-Ordner automatisch klassifizieren, Metadaten extrahieren und strukturiert im Dateisystem ablegen.

## 2. Beteiligte Komponenten

| Datei | Rolle |
|-------|-------|
| `backend/pipeline/core.py` | Koordiniert die Verarbeitungsschritte |
| `backend/pipeline/steps.py` | Einzelne Schritte: Hash, OCR, Duplikat, Klassifikation, Archivierung |
| `backend/archiver.py` | Höherer Einstiegspunkt für Batch-Verarbeitung |
| `backend/llm.py` | LLM-Abstraktion und Prompting |
| `backend/storage.py` | Dateisystem-Operationen, Pfadaufbau, Sender-Registry |

## 3. Ablauf

### 3.1 Datei erkennen

- **Automatisch**: `Monitor`-Seite startet SSE-Stream; Backend prüft INBOX_DIR.
- **Manuell**: Nutzer startet Archiver über Monitor oder Inbox.
- **Skript**: `python -m archiver` oder ähnlich.

### 3.2 Textextraktion

```
PDF ──► pdfplumber / PyPDF2 ──► nativer Text
      └──► pdf2image ──► Tesseract OCR ──► gescannter Text
```

- Zuerst wird versucht, nativen Text zu extrahieren.
- Falls wenig oder kein Text → OCR mit Tesseract.
- Ergebnis: `full_text` wird in der Datenbank gespeichert.

### 3.3 Hash-Berechnung

```python
content_hash = sha256(text.encode("utf-8")).hexdigest()[:16]
```

- 16 Zeichen reichen für die Duplikat-Erkennung und reduzieren Speicher.
- Der Hash basiert auf dem **extrahierten Text**, nicht auf der Datei (damit identische Inhalte trotz unterschiedlicher Dateien erkannt werden).

### 3.4 Duplikat-Check

```
1. Prüfe protected_document_hashes:
   - ignored  → Datei nach ignored/ verschieben, status = ignored
   - locked   → Datei nach duplicates/ verschieben, status = duplicate
2. Prüfe documents-Tabelle auf existierenden Hash:
   → Datei nach duplicates/ verschieben, status = duplicate
3. Kein Duplikat → weiter zur Klassifikation
```

### 3.5 LLM-Klassifikation

Der Text wird an ein lokales GGUF-Modell geschickt. Das Modell liefert JSON:

```json
{
  "sender": "Musterfirma GmbH",
  "date": "2024-03-15",
  "document_type": "Rechnung",
  "category": "Sonstiges",
  "summary": "Rechnung für Büromaterial",
  "amount": 123.45,
  "tax_relevant": false,
  "confidence": "high"
}
```

Prompts sind typischerweise in `backend/prompts.py` oder modulspezifisch (z. B. `backend/tax/prompts.py`).

### 3.6 Archivierung

Zielpfad wird aus Kategorie, Sender, Jahr und Monat gebaut:

```
TARGET_BASE/<category>/<sender>/<year>/<month>/<filename>
```

- Sonderzeichen werden bereinigt.
- Kollisionsvermeidung durch eindeutige Dateinamen.
- `archived_at` wird auf aktuellen Zeitstempel gesetzt.

## 4. Zustände (Status)

| Status | Bedeutung |
|--------|-----------|
| `pending` | Warte auf Verarbeitung |
| `processing` | Wird gerade verarbeitet |
| `ok` | Erfolgreich archiviert und geprüft |
| `review` | Bitte manuell prüfen |
| `duplicate` | Duplikat erkannt |
| `ignored` | Vom Nutzer ignoriert |
| `locked` | Vom Nutzer gesperrt |
| `missing` | Datei existiert nicht mehr auf dem Datenträger |
| `encrypted` | PDF ist passwortgeschützt |
| `corrupt` | PDF kann nicht gelesen werden |
| `no_text` | Kein Text extrahierbar |
| `classification_failed` | LLM-Klassifikation fehlgeschlagen |

## 5. Mathematik & Algorithmik

### 5.1 Hash-Kollisionswahrscheinlichkeit

- SHA256 liefert 256 Bit.
- Verwendung von 16 Hex-Zeichen = 64 Bit.
- Kollisionswahrscheinlichkeit bei 1 Million Dokumenten: ca. \(10^{-10}\) (vernachlässigbar für diesen Anwendungsfall).

### 5.2 OCR-Entscheidung

Typische Heuristik:

```python
if len(extracted_text.strip()) < MIN_TEXT_LENGTH:
    use_ocr()
```

`MIN_TEXT_LENGTH` liegt oft bei 50–100 Zeichen.

### 5.3 Confidence-Score

Das LLM liefert kategorische Confidence (`low`, `medium`, `high`).
Diese wird später für Filter und Review-Priorisierung genutzt.

## 6. Fehlerbehandlung

Fehler in einem Schritt setzen den Status:

- OCR-Fehler → `no_text` oder `corrupt`
- LLM-Fehler → `classification_failed`
- Duplikat → `duplicate`
- Geschützter Hash → `ignored` oder `duplicate`

## 7. Tests

- `tests/test_pipeline_steps.py`
- `tests/test_archiver.py`

## 8. Konfiguration

Wichtige Pfade in `backend/config.py`:

- `SOURCE_DIR` / `INBOX_DIR`: Eingangsordner
- `TARGET_BASE`: Archiv-Ordner
- `DUPLICATES_DIR`: Duplikat-Ordner
- `IGNORED_DIR`: Ignorierte Dateien
- `DB_PATH`: SQLite-Datenbank
