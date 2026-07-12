# Technisch: Duplikat-Erkennung

## 1. Ziel

Erkennen und Abweisen von Dokumenten, die identischen Inhalt bereits archivierter Dokumente haben.

## 2. Hash-Basis

- Algorithmus: SHA256
- Eingabe: UTF-8-kodierter Text des PDFs
- Verwendung: 16 Zeichen Hex-Präfix (64 Bit)

```python
import hashlib
content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
```

## 3. Ablauf

### 3.1 Beim Import

1. Text extrahieren (siehe Pipeline).
2. Hash berechnen.
3. Prüfe `protected_document_hashes`:
   - `ignored` → Datei nach `IGNORED_DIR` verschieben, Status `ignored`
   - `locked` → Datei nach `DUPLICATES_DIR/<hash>/` verschieben, Status `duplicate`
4. Prüfe `documents` nach existierendem Hash mit Status `ok`, `review`, `processing` oder `locked`.
   - Treffer → Datei nach `DUPLICATES_DIR/<hash>/` verschieben, Status `duplicate`
5. Kein Treffer → normale Klassifikation und Archivierung.

### 3.2 Hash-Kollision

Wahrscheinlichkeit bei 1 Million Dokumenten mit 64-Bit-Hash:

```
P(Kollision) ≈ n² / (2 * 2^64) = 10^12 / (2 * 1.8 * 10^19) ≈ 2.7 * 10^-8
```

Für private Archive vernachlässigbar.

## 4. Dateisystem

### Duplikat-Ordner

```
DUPLICATES_DIR/
  <hash1>/
    original.pdf
    duplicate_1.pdf
  <hash2>/
    ...
```

### Unique-Path-Logik

Falls Dateiname bereits existiert:

```python
unique_path(path):
    if not exists(path): return path
    base, ext = splitext(path)
    i = 1
    while exists(f"{base}_{i}{ext}"):
        i += 1
    return f"{base}_{i}{ext}"
```

## 5. Frontend

- Seite `Duplicates.tsx` zeigt gefundene Duplikate an.
- Nutzer kann Duplikate löschen.
- Originaldokument bleibt unverändert.

## 6. API

- Duplikat-Count: `GET /monitor/duplicates/count`
- Duplikat-Liste: (Frontend nutzt Dokumentenfilter `status=duplicate`)

## 7. Tests

- `tests/test_pipeline_steps.py` – `test_check_duplicate_*`
- `tests/test_documents_api.py` – falls Duplikat-spezifische Tests vorhanden

## 8. Unterschiede zu Ignore/Lock

| Aspekt | Duplikat | Ignore | Lock |
|--------|----------|--------|------|
| Auslöser | Gleicher Hash | Nutzeraktion | Nutzeraktion |
| Zielordner | `DUPLICATES_DIR` | `IGNORED_DIR` | bleibt Archiv |
| Status | `duplicate` | `ignored` | `locked` |
| Re-Import | Wieder Duplikat | Wieder ignoriert | Wieder Duplikat |
