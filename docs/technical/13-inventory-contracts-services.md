# Technisch: Inventar, Verträge und Ausgaben

## 1. Übersicht

Diese Module extrahieren und verwalten spezifische Entitäten aus Dokumenten. Sie bilden eine zusätzliche Schicht über der reinen Dokumentenverwaltung.

## 2. Inventar

### Zweck

- Verwaltung von Gegenständen und Geräten.
- Verknüpfung mit Kaufbelegen.

### Typische Felder

- `name`
- `category`
- `purchase_date`
- `price`
- `warranty_until`
- `document_id`

### Ablauf

1. LLM oder manuelle Erfassung erstellt Inventar-Eintrag.
2. Eintrag wird in dedizierter Tabelle gespeichert.
3. Frontend-Seite `Inventory.tsx` zeigt Übersicht.

## 3. Verträge

### Zweck

- Erfassung laufender Verträge.
- Ablaufdaten und Kündigungsfristen im Blick behalten.

### Typische Felder

- `partner`
- `contract_type`
- `start_date`
- `end_date`
- `cancellation_period`
- `amount`
- `document_id`

### Ablauf

1. Dokument wird als Vertrag klassifiziert.
2. LLM extrahiert Vertragsdaten oder Nutzer erfasst manuell.
3. Seite `Contracts.tsx` listet Verträge.

## 4. Ausgaben (Services)

### Zweck

- Erfassung wiederkehrender oder einmaliger Ausgaben.
- Grundlage für Auswertungen und Steuer-Positionen.

### Typische Felder

- `provider`
- `description`
- `amount`
- `date`
- `category`
- `document_id`

### Ablauf

1. Rechnung oder Beleg wird importiert.
2. `services`-Eintrag wird aus dem Dokument extrahiert.
3. Seite `Services.tsx` zeigt Ausgabenübersicht.

## 5. Gemeinsame Muster

- Jedes Modul hat ein Repository unter `backend/db/`.
- API-Router unter `backend/api/routes/`.
- Frontend-Seite unter `frontend/src/pages/`.
- Verknüpfung zum Quelldokument über `document_id`.

## 6. Integration mit Steuer-Modul

- `services.amount`, `contracts.amount` und `items.total_price` fließen in die Low-Value-Betragsprüfung ein.
- Steuer-Positionen können aus diesen Entitäten abgeleitet werden.

## 7. Hinweis

Diese Module sind primär Datenerfassungs- und Übersichtsmodule. Die genaue Extraktionslogik pro Dokumententyp befindet sich in den jeweiligen Repositories und Prompts.
