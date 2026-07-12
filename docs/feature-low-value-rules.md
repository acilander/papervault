# Feature: Geringer-Wert-Regeln (Low Value Rules)

## Überblick

Mit Geringer-Wert-Regeln lassen sich Dokumente automatisch als `low_value = 1` markieren, wenn sie bestimmte Kriterien erfüllen. Das hilft, unwichtige Belege (z. B. kleine Rechnungen, alte Tankquittungen) von wichtigen Dokumenten zu trennen.

## Regel-Kriterien

Eine Regel kann aus beliebiger Kombination dieser Bedingungen bestehen:

| Feld | Bedeutung |
|------|-----------|
| `name` | Anzeigename der Regel |
| `category` | Dokument muss dieser Kategorie zugeordnet sein |
| `document_type` | Dokument muss diesem Dokumententyp entsprechen |
| `max_amount` | Maximaler Betrag in EUR; geprüft gegen `items.total_price`, `services.amount` und `contracts.amount` |
| `older_than_days` | Dokument muss älter als X Tage sein (basierend auf `archived_at`) |
| `active` | Regel ist aktiv/inaktiv |

## Betragsprüfung

Wenn `max_amount` gesetzt ist, sucht die Regel in den verknüpften Tabellen `items`, `services` und `contracts` nach einem Betrag, der kleiner oder gleich dem angegebenen Limit ist:

```sql
EXISTS (
  SELECT 1 FROM (
    SELECT total_price AS amount FROM items WHERE document_id = d.id AND total_price IS NOT NULL
    UNION ALL
    SELECT amount FROM services WHERE document_id = d.id AND amount IS NOT NULL
    UNION ALL
    SELECT amount FROM contracts WHERE document_id = d.id AND amount IS NOT NULL
  ) WHERE amount <= :max_amount
)
```

## Vorgehen

### Regel erstellen

1. Menü **„Geringer Wert“** in der Sidebar öffnen.
2. Name und gewünschte Bedingungen eintragen.
3. **„Regel erstellen“** klicken.

### Regel testen

- **Vorschau**-Icon (Auge) klicken.
- Zeigt alle Dokumente an, die zur Regel passen würden, ohne sie zu verändern.

### Regel anwenden

- **Anwenden**-Icon (Play) klicken.
- Passende Dokumente werden auf `low_value = 1` gesetzt.
- Ergebnis: Anzahl der Treffer und tatsächlich aktualisierten Dokumente.

### Regel aktivieren/deaktivieren

- Toggle-Schalter in der Liste verwenden.
- Inaktive Regeln werden beim Anwenden übersprungen.

### Regel löschen

- Mülleimer-Icon klicken, Bestätigung erteilen.

## API-Endpunkte

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| GET | `/low-value-rules/` | Alle Regeln auflisten |
| POST | `/low-value-rules/` | Neue Regel erstellen |
| GET | `/low-value-rules/{id}` | Einzelne Regel abrufen |
| PATCH | `/low-value-rules/{id}` | Regel bearbeiten |
| DELETE | `/low-value-rules/{id}` | Regel löschen |
| POST | `/low-value-rules/{id}/preview` | Vorschau der Treffer |
| POST | `/low-value-rules/{id}/apply` | Regel anwenden |

## Datenbank

**Tabelle `low_value_rules`:**

| Spalte | Typ | Bedeutung |
|--------|-----|-----------|
| id | INTEGER PK | Regel-ID |
| name | TEXT | Name |
| category | TEXT | Optional: Kategorie |
| document_type | TEXT | Optional: Dokumententyp |
| max_amount | REAL | Optional: Maximalbetrag |
| older_than_days | INTEGER | Optional: Alter in Tagen |
| active | INTEGER | 1 = aktiv, 0 = inaktiv |
| created_at | TEXT | Zeitstempel |

## Anzeige im Frontend

- In der Sidebar wird die Anzahl der `low_value`-Dokumente angezeigt.
- In der Dokumentenliste kann über den Button **„Geringer Wert“** gefiltert werden.

## Bekannte Einschränkungen

- Der Betrag wird nur aus `items`, `services` und `contracts` gelesen, nicht aus dem reinen Dokumententext.
- Eine Regel prüft Beträge nur auf `<= max_amount`, nicht auf `>= 0`.

## Tests

Siehe `tests/test_low_value_rules.py`:

- Auflisten und Erstellen
- Aktivieren/Deaktivieren
- Löschen
- Vorschau und Anwenden
- Prüfung, dass `/low-value-rules/` immer ein Array zurückgibt
