# Technisch: Geringer-Wert-Regeln (Low Value Rules)

## 1. Ziel

Automatische Markierung von Dokumenten als `low_value = 1`, wenn sie vordefinierte Kriterien erfüllen.

## 2. Datenmodell

### Tabelle `low_value_rules`

| Spalte | Typ | Beschreibung |
|--------|-----|--------------|
| `id` | INTEGER PK | Regel-ID |
| `name` | TEXT | Name |
| `category` | TEXT | Optional: geforderte Kategorie |
| `document_type` | TEXT | Optional: geforderter Dokumententyp |
| `max_amount` | REAL | Optional: Maximalbetrag |
| `older_than_days` | INTEGER | Optional: Mindestalter in Tagen |
| `active` | INTEGER | 1 = aktiv, 0 = inaktiv |
| `created_at` | TEXT | ISO-Timestamp |

## 3. Regel-Matching

`backend/db/low_value_rules_repo.py::find_matching_docs(rule)`

### Basisbedingungen

```sql
low_value = 0
status IN ('ok', 'review')
```

Nur diese Dokumente können überhaupt als gering markiert werden.

### Optionale Bedingungen

| Feld | SQL-Fragment |
|------|--------------|
| `category` | `AND category = ?` |
| `document_type` | `AND document_type = ?` |
| `older_than_days` | `AND archived_at < datetime('now', '-{days} days')` |

### Betragsbedingung

Wenn `max_amount` gesetzt:

```sql
AND EXISTS (
  SELECT 1 FROM (
    SELECT total_price AS amount FROM items WHERE document_id = d.id AND total_price IS NOT NULL
    UNION ALL
    SELECT amount FROM services WHERE document_id = d.id AND amount IS NOT NULL
    UNION ALL
    SELECT amount FROM contracts WHERE document_id = d.id AND amount IS NOT NULL
  ) WHERE amount <= :max_amount
)
```

## 4. Algorithmus

### 4.1 Regel anwenden

```python
def apply_rule(rule_id):
    rule = get(rule_id)
    if not rule["active"]:
        return {"matched": 0, "updated": 0}
    matches = find_matching_docs(rule, limit=100000)
    updated = 0
    for doc in matches:
        if doc["status"] in ("ok", "review") and doc["low_value"] == 0:
            update_document(doc["id"], low_value=1)
            updated += 1
    return {"matched": len(matches), "updated": updated}
```

### 4.2 Vorschau

Gleiche Query wie `apply_rule`, aber ohne `UPDATE`. Liefert nur die Trefferliste.

## 5. Mathematik

### 5.1 Altersberechnung

SQLite-Funktion:

```sql
archived_at < datetime('now', '-{days} days')
```

Vergleicht ISO-Timestamps. Dokumente älter als `days` Tage werden erfasst.

### 5.2 Betragsprüfung

```
amount <= max_amount
```

Für ein Dokument reicht es, wenn **ein** Betrag aus `items`, `services` oder `contracts` unter dem Limit liegt.

### 5.3 Unendlich vs. fehlender Betrag

- `max_amount = NULL`: Bedingung wird ignoriert.
- Betrag `NULL` in der UNION-Abfrage wird durch `IS NOT NULL` ausgeschlossen.
- Ein Dokument ohne jeglichen Betrag erfüllt die `max_amount`-Bedingung **nicht**, wenn `max_amount` gesetzt ist.

## 6. API-Endpunkte

| Methode | Pfad | Logik |
|---------|------|-------|
| GET | `/low-value-rules/` | `repo.get_all()` |
| POST | `/low-value-rules/` | `repo.insert()` + `repo.get()` |
| GET | `/low-value-rules/{id}` | `repo.get(id)` |
| PATCH | `/low-value-rules/{id}` | `repo.update(id, **fields)` |
| DELETE | `/low-value-rules/{id}` | `repo.delete(id)` |
| POST | `/low-value-rules/{id}/preview` | `find_matching_docs(rule, limit=200)` |
| POST | `/low-value-rules/{id}/apply` | `apply_rule(id)` |

## 7. Frontend

- Seite `LowValueRules.tsx` listet Regeln als Tabelle.
- Formular zum Erstellen neuer Regeln.
- Aktionen: Toggle aktiv/inaktiv, Vorschau, Anwenden, Löschen.
- Validierung der API-Antwort: `Array.isArray(data)`.

## 8. Integration mit Dokumentenliste

- Filter `low_value=1` in `GET /documents/`.
- Sidebar-Badge zeigt Anzahl der `low_value`-Dokumente an.
- Status-Button in der Dokumentenliste.

## 9. Tests

- `tests/test_low_value_rules.py`:
  - Liste ist Array
  - Erstellen, Aktivieren, Löschen
  - Vorschau und Anwenden

## 10. Bekannte Einschränkungen

- Beträge müssen zuvor in `items`, `services` oder `contracts` extrahiert worden sein.
- Keine komplexen logischen Verknüpfungen (nur AND).
- Keine Negation (z. B. „nicht Kategorie X“).
