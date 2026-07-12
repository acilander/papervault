# Technisch: Steuer-Modul

## 1. Ziel

Unterstützung bei der Steuererklärung durch lokale Analyse von Steuerprogramm-Exporten und Finanzamtsbescheiden.

> Detaillierte Planung: [`blueprint_tax_module.md`](../blueprint_tax_module.md)

## 2. Datenmodell

### Tabellen

| Tabelle | Zweck |
|---------|-------|
| `tax_years` | Steuerjahre mit Status (`draft`, `submitted`, `assessed`, `final`) |
| `tax_documents` | Verknüpfung zwischen `documents` und `tax_years` |
| `tax_positions` | Extrahierte Positionen (Kategorie, Betrag, Seite, Verifizierung) |

### Positionen

```json
{
  "category": "Werbungskosten",
  "subcategory": "Fahrtkosten",
  "label": "Fahrtkosten Büro",
  "amount": 1234.56,
  "amount_assessed": 1200.00,
  "page": 3,
  "source_text": "...",
  "verified": true
}
```

## 3. Ablauf

### 3.1 Steuerjahr anlegen

```python
POST /tax/years { "year": 2024 }
```

### 3.2 Dokument verknüpfen

```python
POST /tax/years/{id}/documents {
  "document_id": 123,
  "source_type": "tax_program_export"  # oder "assessment_notice"
}
```

### 3.3 Positionen extrahieren

```python
POST /tax/years/{id}/extract { "document_id": 123 }
```

- LLM liest `documents.full_text`.
- Prompt enthält Anweisung für JSON-Array.
- Ergebnis wird in `tax_positions` gespeichert.

### 3.4 Positionen verifizieren

```python
PATCH /tax/positions/{id} { "amount": 1300.00, "verified": true }
```

### 3.5 Vergleich Export vs. Bescheid

```python
GET /tax/years/{id}/comparison
```

- Gruppiert Positionen nach Kategorie.
- Vergleicht `amount` (Steuerprogramm) mit `amount_assessed` (Bescheid).
- Liefert Differenzen pro Kategorie.

## 4. Mathematik

### 4.1 Summen pro Kategorie

```python
sum_export = sum(p.amount for p in positions if p.source_type == "tax_program_export")
sum_assessed = sum(p.amount_assessed for p in positions if p.source_type == "assessment_notice")
diff = sum_export - sum_assessed
```

### 4.2 Zeitreihe

```python
GET /tax/development
```

Liefert für jede Kategorie die Summe pro Jahr.

## 5. Frontend

- `TaxYears.tsx`: Übersicht aller Jahre.
- `TaxYearDetail.tsx`: Detailansicht mit Dokumenten, Positionen, Vergleich.
- `TaxYearComparison.tsx`: Jahr-gegen-Jahr-Vergleich.
- `TaxDevelopment.tsx`: Entwicklungsdiagramm.
- `TaxChat.tsx`: Steuer-Chat.

## 6. Hinweis

Das Steuer-Modul ersetzt keine Steuerberatung. Alle vom LLM extrahierten Positionen müssen verifiziert werden.

## 7. Tests

- `tests/test_tax_api.py`
- `tests/test_tax_repos.py`
- `tests/test_tax_extraction.py`
