# Technisch: Haus & Vermietung (MFH), Inventar, Verträge und Ausgaben

## 1. Übersicht

Diese Module extrahieren und verwalten spezifische Entitäten aus Dokumenten und bilden das Rückgrat der "Haus & Vermietung"-Architektur (MFH = Mehrfamilienhaus). Sie bieten eine Schicht über der reinen Dokumentenverwaltung.

## 2. Inventar (Assets)

### Zweck

- Verwaltung von Gegenständen und Geräten (Assets).
- **Neu:** Verknüpfung mit Wohneinheiten (`property_unit`).
- Verknüpfung mit Kaufbelegen.

### Typische Felder

- `name`
- `category`
- `purchase_date`
- `price`
- `warranty_until`
- `document_id`
- `property_unit` (EG, OG, DG, UG, Gesamthaus)

### Ablauf

1. LLM oder manuelle Erfassung erstellt Inventar-Eintrag.
2. Eintrag wird in dedizierter Tabelle gespeichert.
3. Frontend-Seite `Inventory.tsx` zeigt Übersicht pro Haus/Einheit.

## 3. Verträge & Contract Risk Auditor

### Zweck

- Erfassung laufender Verträge.
- Ablaufdaten und Kündigungsfristen im Blick behalten.
- **Contract Risk Auditor:** Automatische Identifikation von Risiken wie Indexmiete.

### Typische Felder

- `partner`
- `contract_type`
- `start_date`
- `end_date`
- `cancellation_period`
- `amount`
- `document_id`
- `property_unit`

### Ablauf & Auditor

1. Dokument wird als Vertrag klassifiziert.
2. LLM extrahiert Vertragsdaten.
3. **Auditor-Modul:** Die Pipeline durchsucht den Text parallel nach Mustern ("Indexmiete", "Staffelmiete", "Selbstbeteiligung").
4. Warnungen werden direkt in das `notes` Feld des Vertrages oder Dokuments geschrieben, um den Nutzer sofort bei der Prüfung darauf aufmerksam zu machen.
5. Seite `Contracts.tsx` listet Verträge inklusive ihrer Risikofaktoren.

## 4. Ausgaben (Services) & Predictive Forecasting

### Zweck

- Erfassung wiederkehrender oder einmaliger Ausgaben (Strom, Wasser, Handwerker).
- Grundlage für Auswertungen, Steuer-Positionen und Prognosen.

### Typische Felder

- `provider`
- `description`
- `amount`
- `date`
- `category`
- `document_id`
- `property_unit`

### Predictive Utility Forecasting (Monitor)

Die historischen Ausgabendaten (Services) der Kategorien Strom, Wasser, Heizung bilden die Datenbasis für das **Forecasting**.
- Der Endpunkt `/monitor/forecast` lädt Zeitreihen aus der Datenbank.
- Mittels `numpy.polyfit` (lineare Regression ersten Grades) wird ein Trend für das Folgejahr errechnet.
- Das System generiert daraus natürliche Sprach-Empfehlungen ("Die Nebenkosten steigen um 8%. Es wird empfohlen, die Vorauszahlungen der Mieter anzupassen.").

## 5. Gemeinsame Muster & MFH

- Jedes Modul hat ein Repository unter `backend/db/`.
- API-Router unter `backend/api/routes/`.
- Frontend-Seite unter `frontend/src/pages/`.
- Verknüpfung zum Quelldokument über `document_id`.
- **MFH-Zentrierung:** Alle drei Tabellen (`items`, `contracts`, `services`) besitzen die Spalte `property_unit`. Dies erlaubt eine schnelle Aggregation (z.B. "Wie viel kostet das EG?").

## 6. Integration mit Steuer-Modul

- `services.amount`, `contracts.amount` und `items.total_price` fließen in die Low-Value-Betragsprüfung ein.
- Steuer-Positionen können aus diesen Entitäten abgeleitet werden. (Siehe Proactive Tax Linking in Phase 8c).

## 7. Hinweis

Diese Module sind primär Datenerfassungs- und Übersichtsmodule. Die genaue Extraktionslogik pro Dokumententyp befindet sich in den jeweiligen Repositories und Prompts (`backend/prompts.py`).
