# Technisch: Pipeline und Import

## 1. Ziel

PDFs, sowie Office-Dokumente (`.docx`, `.xlsx`) aus dem Inbox-Ordner automatisch klassifizieren, Metadaten extrahieren und strukturiert im Dateisystem ablegen.

## 2. Beteiligte Komponenten

| Datei | Rolle |
|-------|-------|
| `backend/pipeline/core.py` | Koordiniert die Verarbeitungsschritte inkl. Phase 8c (Tax Linking) |
| `backend/pipeline/steps.py` | Einzelne Schritte: Hash, Duplikat, Klassifikation, Archivierung |
| `backend/pdf_utils.py` | Textextraktion für PDF (PyMuPDF) und Office (`.docx`, `.xlsx`), VLM Fallback |
| `backend/vision.py` | Moondream2 VLM Engine für visuelles OCR |
| `backend/archiver.py` | Höherer Einstiegspunkt (Watchdog) für Batch-Verarbeitung |
| `backend/llm.py` | LLM-Abstraktion und Prompting |
| `backend/storage.py` | Dateisystem-Operationen, Pfadaufbau, Sender-Registry |

## 3. Ablauf

### 3.1 Datei erkennen

- **Automatisch**: `Monitor`-Seite startet SSE-Stream; Backend (`archiver.py`) prüft INBOX_DIR. Akzeptiert werden `.pdf`, `.docx`, `.xlsx`.
- **Manuell**: Nutzer startet Archiver über Monitor oder Prüfung-Seite.

### 3.2 Textextraktion & VLM OCR Fallback

```
Office (.docx/.xlsx) ──► zipfile + xml.etree.ElementTree ──► nativer Text
PDF ──► PyMuPDF ──► nativer Text
      └──► (bei < 50 Zeichen) ──► PyTesseract OCR ──► gescannter Text
           └──► (bei < 50 Zeichen) ──► Moondream2 (VLM) ──► perfektionierter VLM-Text
```

- **Office-Dokumente** werden ohne externe Bibliotheken (Zero-Dependency) nativ über Pythons integriertes `zipfile` und `xml.etree` geparst, was extrem schnell und ressourcenschonend ist.
- Für **PDFs** wird PyMuPDF verwendet.
- **VLM Fallback**: Liefert PyTesseract bei Scans oder Handy-Fotos schlechte Ergebnisse (< 50 Zeichen), schaltet die Pipeline auf das lokale VLM (Moondream2 auf der GPU) um, welches das Dokument visuell liest und als Rohtext ausgibt.

### 3.3 Hash-Berechnung

```python
content_hash = sha256(text.encode("utf-8")).hexdigest()[:16]
```

- 16 Zeichen reichen für die Duplikat-Erkennung und reduzieren Speicher.
- Der Hash basiert auf dem **extrahierten Text**, nicht auf der Datei.

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
  "confidence": "high",
  "vehicle_id": null,
  "child_name": null
}
```

Prompts integrieren nun auch Asset Tracking (`vehicle_id`, `child_name`).

### 3.6 Archivierung & MFH

Zielpfad wird aus Kategorie, Sender, Jahr, Monat gebaut. Ist ein Asset Tag vorhanden, wird oft ein spezieller Unterordner erzeugt.
**Wichtig:** Bei Office-Dateien (`.docx`, `.xlsx`) wird die Dateiendung immer beibehalten, der Ursprungsname wird nicht mutiert, um Makros/Referenzen nicht zu brechen.

### 3.7 Proactive Tax Linking (Phase 8c)

Am Ende von `core.py` (Phase 8c) greift das Proactive Tax Linking. Wenn die zugeordnete Kategorie eines neuen Dokuments steuer- oder nebenkostenrelevant ist (z. B. `Haus_Gemeinkosten`, `OG_Miete`, `DG_Miete`), wird automatisch in der `tax_documents` Tabelle ein verknüpfter Draft-Eintrag für das entsprechende Steuerjahr angelegt. Dies erspart die manuelle Zuordnung am Jahresende komplett.

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
| `missing` | Datei existiert nicht mehr |
| `encrypted` | Datei ist passwortgeschützt |
| `corrupt` | Datei kann nicht gelesen werden |
| `no_text` | Kein Text extrahierbar (auch nach VLM) |
| `classification_failed` | LLM-Klassifikation fehlgeschlagen |

## 5. Mathematik & Algorithmik

### 5.1 OCR-Entscheidung

```python
if len(extracted_text.strip()) < 50:
    text = use_ocr()
    if len(text.strip()) < 50:
        text = use_vlm() # Moondream2 GPU
```

### 5.2 Confidence-Score

Das LLM liefert kategorische Confidence (`low`, `medium`, `high`).

## 6. Fehlerbehandlung

- OCR/VLM-Fehler → `no_text` oder `corrupt`
- LLM-Fehler → `classification_failed`
- Duplikat → `duplicate`

## 7. Tests

- `tests/test_pipeline_steps.py`
- `tests/test_archiver.py`
- `tests/test_extra_concurrency_and_formats.py` (für Word/Excel)
- `tests/test_vision.py` (für VLM)
