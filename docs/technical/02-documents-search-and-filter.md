# Technisch: Dokumentenliste, Suche und Filter

## 1. Ziel

Schnelles Durchsuchen, Filtern, Sortieren und Massenbearbeiten aller archivierten Dokumente.

## 2. Datenquelle

- Backend: `GET /documents/`
- Repo: `backend/db/documents_repo.py`
- Tabelle: `documents`
- Volltextindex: `documents_fts` (FTS5)

## 3. API-Parameter

| Parameter | Typ | Bedeutung |
|-----------|-----|-----------|
| `q` | string | Volltextsuche |
| `category` | string | Kategorie exakt |
| `year` | string | Archivierungsjahr (YYYY) |
| `sender` | string | Sender exakt |
| `status` | string | Dokumentenstatus |
| `tax_relevant` | 0/1 | Steuerrelevanz |
| `no_sender` | 0/1 | Dokumente ohne Sender |
| `low_value` | 0/1 | Geringer-Wert-Markierung |
| `confidence` | string | `low`, `medium`, `high` |
| `tag` | string | Tag enthält |
| `sort_by` | string | Sortierspalte |
| `sort_dir` | string | `asc` / `desc` |
| `limit` | int | Seitengröße |
| `offset` | int | Offset |

## 4. SQL-Query-Logik

### 4.1 Volltextsuche

```sql
SELECT d.* FROM documents d
WHERE d.id IN (
  SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?
)
ORDER BY d.archived_at DESC
LIMIT ? OFFSET ?
```

### 4.2 Kombinierte Filter

Filter werden als `AND`-Bedingungen an den WHERE-Clause angehängt:

```sql
SELECT d.* FROM documents d
WHERE d.id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?)
  AND d.category = ?
  AND d.sender = ?
  AND d.status = ?
  AND d.low_value = ?
ORDER BY d.archived_at DESC
LIMIT ? OFFSET ?
```

### 4.3 Standard-Filter für ignorierte Dokumente

Wenn kein `status`-Filter gesetzt ist, werden `ignored`-Dokumente ausgeschlossen:

```sql
AND d.status != 'ignored'
```

## 5. FTS5-Index

Der FTS5-Index synchronisiert sich automatisch über Trigger:

```sql
CREATE TRIGGER documents_ai AFTER INSERT ON documents BEGIN
  INSERT INTO documents_fts(rowid, filename, sender, summary, keywords, full_text)
  VALUES (new.id, new.filename, new.sender, new.summary, new.keywords, new.full_text);
END;
```

Äquivalente Trigger existieren für UPDATE und DELETE.

## 6. Sortierung

Mögliche Sortierspalten:

- `archived_at` (Standard, absteigend)
- `filename`
- `sender`
- `date`
- `category`
- `status`

## 7. Pagination

- Frontend: `PAGE_SIZE = 50`
- Backend liefert `X-Total-Count` Header.
- Berechnung der Seitenanzahl: `ceil(total / PAGE_SIZE)`.

## 8. Bulk-Edit

### Ablauf

1. Nutzer wählt Dokumente über Checkboxen.
2. Wählt Feld und neuen Wert.
3. Frontend sendet `PATCH /documents/bulk` mit `{ ids, field, value }`.
4. Backend aktualisiert alle Dokumente in einer Transaktion.
5. Frontend speichert vorherigen Zustand für Undo.

### Undo-Mechanismus

- Vor dem Bulk-Edit werden die aktuellen Werte der betroffenen Dokumente gelesen.
- Nach erfolgreichem Edit erscheint ein Undo-Button.
- Klick auf Undo sendet einen neuen Bulk-Update mit den ursprünglichen Werten.

## 9. Frontend-State

- `useSearchParams()` hält den Filterzustand in der URL.
- Dadurch sind Filter bookmarkbar und über Sidebar-Quicklinks setzbar.
- `useCallback` für `buildFilterParams` verhindert unnötige Re-Renders.

## 10. Mathematik & Algorithmik

### 10.1 Pagination

```
totalPages = ceil(total / pageSize)
offset = (page - 1) * pageSize
```

### 10.2 Filterlogik

Alle Filter sind **konjunktiv** (AND). Es gibt keine OR-Filterung.

### 10.3 Suchrelevanz

FTS5 liefert Ergebnisse ohne explizite Relevanzsortierung; Sortierung erfolgt nach `archived_at` oder anderer gewählter Spalte.

## 11. Performance

- SQLite-Indizes auf häufig gefilterten Spalten (`category`, `sender`, `status`, `archived_at`).
- FTS5 ermöglicht schnelle Volltextsuche über große Dokumentenmengen.
- `COUNT` und `SELECT` laufen in getrennten Queries, um `X-Total-Count` zu liefern.

## 12. Tests

- `tests/test_documents_api.py`
- `tests/test_documents_repo.py` (falls vorhanden)
