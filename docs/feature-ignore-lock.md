# Feature: Dokumente ignorieren und sperren (Ignore / Lock)

## Überblick

Mit diesem Feature können Dokumente entweder als **irrelevant markiert** oder **gegen Änderungen gesperrt** werden. Beide Aktionen werden über einen SHA256-Hash des Dokumenteninhalts in der Tabelle `protected_document_hashes` gesichert, sodass geschützte Dokumente nicht versehentlich re-importiert oder verändert werden.

## Status

- `ignored` – Dokument ist irrelevant, wird standardmäßig ausgeblendet.
- `locked` – Dokument ist gesperrt, Änderungen sind blockiert.

## Abläufe

### Ignorieren eines Dokuments

1. Nutzer klickt in der Detailansicht auf **„Ignorieren“**.
2. Backend:
   - Status auf `ignored` setzen.
   - SHA256-Hash-Präfix in `protected_document_hashes` mit `type = 'ignored'` speichern.
   - Datei in den konfigurierten `IGNORED_DIR` verschieben.
3. Frontend:
   - Zurück zur Dokumentenliste navigieren.
   - Dokument erscheint nicht mehr in der Standardansicht.

### Wiederherstellen eines ignorierten Dokuments

1. Nutzer wählt Status-Filter **„Irrelevant“** in der Dokumentenliste.
2. In der Detailansicht auf **„Wiederherstellen“** klicken.
3. Backend:
   - Status auf `ok` setzen.
   - Hash aus `protected_document_hashes` entfernen.

### Sperren eines Dokuments

1. Nutzer klickt in der Detailansicht auf **„Sperren“**.
2. Backend:
   - Status auf `locked` setzen.
   - Hash in `protected_document_hashes` mit `type = 'locked'` speichern.
   - Datei bleibt im Archiv.

### Entsperren

1. Nutzer klickt auf **„Entsperren“**.
2. Backend:
   - Status auf `ok` setzen.
   - Hash aus `protected_document_hashes` entfernen.

## Auswirkungen auf andere Features

### Standard-Dokumentenliste

- `search_documents()` und `count_documents()` schließen Dokumente mit `status = 'ignored'` standardmäßig aus.
- Mit dem Status-Filter `ignored` lassen sie sich gezielt anzeigen.

### Duplikat-Check

`pipeline/steps.check_duplicate()` prüft zuerst `protected_document_hashes`:

- Hash ist `ignored` → Eingehende Datei wird verworfen, Status `ignored`, Datei nach `ignored/` verschoben.
- Hash ist `locked` → Eingehende Datei wird als Duplikat abgelehnt, Status `duplicate`, Datei nach `duplicates/` verschoben.

### Bearbeiten

- `PATCH /documents/{id}` und Bulk-Update blockieren Änderungen an `locked` oder `ignored` Dokumenten (HTTP 409).
- `POST /documents/{id}/reprocess` und `POST /documents/{id}/confirm` sind ebenfalls blockiert.

## API-Endpunkte

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| POST | `/documents/{id}/ignore` | Dokument ignorieren |
| POST | `/documents/{id}/unignore` | Ignorieren aufheben |
| POST | `/documents/{id}/lock` | Dokument sperren |
| POST | `/documents/{id}/unlock` | Sperre aufheben |

## Frontend

- In `DocumentDetail.tsx` werden Eingabefelder für `locked`/`ignored` Dokumente deaktiviert (read-only).
- Sperren-/Ignorieren-Buttons mit Bestätigungsdialog.
- Status-Badges und `Lock`-Icon in der Dokumentenliste.

## Datenbank

**Tabelle `protected_document_hashes`:**

| Spalte | Typ | Bedeutung |
|--------|-----|-----------|
| hash | TEXT PK | SHA256-Präfix des Dokumenteninhalts |
| type | TEXT | `ignored` oder `locked` |
| document_id | INTEGER | Verknüpfung zum Originaldokument |
| filename | TEXT | Ursprünglicher Dateiname |
| created_at | TEXT | Zeitstempel |

## Tests

Siehe:
- `tests/test_documents_api.py` – API-Tests für ignore/unignore, lock/unlock, Edit-Blocking, Standard-Ausblendung.
- `tests/test_pipeline_steps.py` – Duplikat-Handling für ignored/locked Hashes.
