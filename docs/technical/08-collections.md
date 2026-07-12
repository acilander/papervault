# Technisch: Sammlungen (Collections)

## 1. Ziel

Dokumente thematisch gruppieren, unabhängig von ihrer Archivpfad-Struktur.

## 2. Datenmodell

### Tabelle `collections`

| Spalte | Typ | Beschreibung |
|--------|-----|--------------|
| `id` | INTEGER PK | Sammlungs-ID |
| `name` | TEXT | Name |
| `description` | TEXT | Beschreibung |
| `color` | TEXT | Hex-Farbe |
| `updated_at` | TEXT | ISO-Timestamp |

### Tabelle `collection_documents`

| Spalte | Typ | Beschreibung |
|--------|-----|--------------|
| `collection_id` | INTEGER FK | Sammlung |
| `document_id` | INTEGER FK | Dokument |
| `added_at` | TEXT | ISO-Timestamp |
| PRIMARY KEY | (`collection_id`, `document_id`) |

## 3. Ablauf

### 3.1 Sammlung erstellen

```python
POST /collections/ { "name": "Umbau 2024", "description": "...", "color": "#3b82f6" }
```

### 3.2 Dokument hinzufügen

```python
POST /collections/{id}/documents { "document_id": 123 }
```

### 3.3 Sammlung abrufen

```python
GET /collections/{id}
```

Liefert Sammlungsmetadaten plus Liste der zugeordneten Dokumente.

### 3.4 ZIP-Export

```python
collectionZipUrl(id)
```

Erzeugt ein ZIP-Archiv aller Dateien in der Sammlung.

## 4. Frontend

- Seite `Collections.tsx` zeigt Listen- und Detailansicht.
- Farbauswahl bei Erstellung.
- Bulk-Add in `Documents.tsx` ermöglicht Hinzufügen mehrerer Dokumente.

## 5. Tests

- `tests/test_collections.py`
