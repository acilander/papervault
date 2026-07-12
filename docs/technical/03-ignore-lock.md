# Technisch: Ignore / Lock

## 1. Ziel

Dokumente dauerhaft als irrelevant markieren oder gegen Änderungen schützen. Beides wird über einen Hash-Registry realisiert, sodass geschützte Dokumente auch beim Re-Import erkannt werden.

## 2. Datenmodell

### Tabelle `protected_document_hashes`

| Spalte | Typ | Beschreibung |
|--------|-----|--------------|
| `hash` | TEXT PK | SHA256-Präfix (16 Hex-Zeichen) |
| `type` | TEXT | `ignored` oder `locked` |
| `document_id` | INTEGER | Verweis auf das Originaldokument |
| `filename` | TEXT | Original-Dateiname |
| `created_at` | TEXT | ISO-Timestamp |

### Index

```sql
CREATE INDEX IF NOT EXISTS idx_protected_hash_type ON protected_document_hashes(hash, type);
```

## 3. Abläufe

### 3.1 Ignorieren

**API:** `POST /documents/{id}/ignore`

```python
1. doc = get_document(id)
2. content_hash = doc["content_hash"] (oder neu berechnen)
3. update_document(id, status="ignored")
4. protect_document_hash(hash, "ignored", document_id=id, filename=doc["filename"])
5. Zielpfad = unique_path(IGNORED_DIR / basename(doc.file_path))
6. shutil.move(doc.file_path, Zielpfad)
7. update_document(id, file_path=Zielpfad)
```

### 3.2 Wiederherstellen

**API:** `POST /documents/{id}/unignore`

```python
1. doc = get_document(id)
2. delete_protected_hash(doc["content_hash"])
3. update_document(id, status="ok")
```

> Hinweis: Die Datei verbleibt im `ignored/`-Ordner; es erfolgt keine Rückführung in das Archiv.

### 3.3 Sperren

**API:** `POST /documents/{id}/lock`

```python
1. doc = get_document(id)
2. update_document(id, status="locked")
3. protect_document_hash(hash, "locked", document_id=id, filename=doc["filename"])
```

### 3.4 Entsperren

**API:** `POST /documents/{id}/unlock`

```python
1. doc = get_document(id)
2. delete_protected_hash(doc["content_hash"])
3. update_document(id, status="ok")
```

## 4. Schutzmechanismen

### 4.1 Bearbeiten blockieren

`PATCH /documents/{id}` prüft:

```python
if doc["status"] in ("locked", "ignored"):
    raise HTTPException(409, "Dokument ist gesperrt oder ignoriert")
```

### 4.2 Bulk-Update ausschließen

`PATCH /documents/bulk` filtert IDs:

```python
valid_ids = [id for id in ids if get_document(id)["status"] not in ("locked", "ignored")]
```

### 4.3 Reprocess / Confirm blockieren

`POST /documents/{id}/reprocess` und `POST /documents/{id}/confirm` werfen 409 bei `locked`/`ignored`.

## 5. Duplikat-Handling

`pipeline/steps.check_duplicate()` prüft zuerst die Registry:

```python
protected = get_protected_hash(content_hash)
if protected:
    if protected["type"] == "ignored":
        move_to_ignored(file_path)
        update_document(doc_id, status="ignored", file_path=new_path)
        return True
    if protected["type"] == "locked":
        move_to_duplicates(file_path)
        update_document(doc_id, status="duplicate", file_path=new_path)
        return True
```

## 6. Sicherheitsbetrachtung

- Der Hash basiert auf dem Inhalt, nicht auf dem Dateinamen.
- Selbst wenn der Nutzer die Datei umbenennt oder kopiert, wird der Schutz erkannt.
- 64-Bit-Hash-Präfix bietet ausreichenden Schutz gegen Kollisionen bei typischen Privatanwendungen.

## 7. Frontend

- `DocumentDetail.tsx`: Buttons für Ignore/Lock mit Bestätigungsdialog.
- Read-only-Modus: Eingabefelder deaktiviert, wenn `status` = `locked` oder `ignored`.
- `Documents.tsx`: Lock-Icon neben Dateiname; Status-Filter `ignored` und `locked` verfügbar.

## 8. Tests

- `tests/test_documents_api.py`:
  - `test_ignore_and_unignore_document`
  - `test_lock_and_unlock_document`
  - `test_locked_document_cannot_be_edited`
  - `test_ignored_hidden_from_default_list`
- `tests/test_pipeline_steps.py`:
  - `test_check_duplicate_ignored_hash`
  - `test_check_duplicate_locked_hash`

## 9. Dateisystem-Auswirkungen

| Aktion | Quellpfad | Zielpfad |
|--------|-----------|----------|
| Ignore | Archiv | `IGNORED_DIR/<filename>` |
| Unignore | `IGNORED_DIR` | bleibt dort |
| Lock | Archiv | bleibt im Archiv |
| Locked-Duplikat importieren | Inbox | `DUPLICATES_DIR/<hash>/<filename>` |
| Ignored-Duplikat importieren | Inbox | `IGNORED_DIR/<filename>` |
