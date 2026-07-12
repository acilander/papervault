# Blueprint: Steuer-Modul für PaperVault

## Ziel

Ein lokales, datensicheres Steuer-Hilfsprogramm innerhalb von PaperVault. Es lernt aus vergangenen Steuererklärungen (Steuerprogramm-Exporte + Finanzamtsbescheide), strukturiert Positionen pro Jahr und unterstützt die Vorbereitung zukünftiger Erklärungen.

## Grundsatz

- Keine Steuerberatung durch das LLM.
- Positionen müssen vom Benutzer verifiziert werden.
- Alle Daten bleiben lokal.

## Module

### 1. Datenbank-Schema

#### `tax_years`

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | INTEGER PK | |
| `year` | INTEGER | Steuerjahr |
| `status` | TEXT | `draft`, `submitted`, `assessed`, `final` |
| `notes` | TEXT | optionale Notizen |
| `created_at` | TEXT | ISO-Timestamp |
| `updated_at` | TEXT | ISO-Timestamp |

#### `tax_documents`

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | INTEGER PK | |
| `tax_year_id` | INTEGER FK | |
| `document_id` | INTEGER FK | referenziert `documents` |
| `source_type` | TEXT | `tax_program_export` oder `assessment_notice` |
| `parsed_at` | TEXT | ISO-Timestamp |
| `verified` | INTEGER | 0/1, ob der Benutzer die Extraktion geprüft hat |

#### `tax_positions`

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | INTEGER PK | |
| `tax_year_id` | INTEGER FK | |
| `tax_document_id` | INTEGER FK | Quelle |
| `category` | TEXT | z. B. `Einkünfte`, `Werbungskosten`, `Sonderausgaben`, `Außergewöhnliche Belastungen` |
| `subcategory` | TEXT | z. B. `Lohn`, `Riester`, `Krankenkosten` |
| `label` | TEXT | Lesbare Bezeichnung |
| `amount` | REAL | Betrag in EUR |
| `amount_assessed` | REAL | Betrag lt. Bescheid (falls abweichend) |
| `page` | INTEGER | Seite im PDF (optional) |
| `verified` | INTEGER | 0/1 |
| `source_text` | TEXT | Originaltext-Ausschnitt |
| `created_at` | TEXT | ISO-Timestamp |

### 2. Backend

#### Repositories

- `backend/db/tax_years_repo.py`: CRUD für Steuerjahre.
- `backend/db/tax_documents_repo.py`: Verknüpfung zwischen `documents` und Steuerjahr.
- `backend/db/tax_positions_repo.py`: CRUD für Positionen, Filter, Vergleich.

#### LLM-Extraktion

- `backend/tax/extraction.py`: Funktion `extract_tax_positions(document_id, source_type)`.
  - Lädt Text aus `documents.full_text`.
  - Sendet strukturierten Prompt ans LLM.
  - Erwartet JSON-Array mit `{category, subcategory, label, amount, page, source_text}`.
  - Speichert Ergebnisse in `tax_positions`.
- `backend/tax/prompts.py`: Prompts für Steuerprogramm-Export und Bescheid.

#### Vergleichs-Logik

- `backend/tax/comparison.py`: `compare_year(tax_year_id)`.
  - Vergleicht Positionen aus `tax_program_export` mit `assessment_notice`.
  - Markiert Abweichungen (`amount` vs. `amount_assessed`).
  - Liefert Summen pro Kategorie und Jahr.

#### API-Routes

- `backend/api/routes/tax.py` mit Prefix `/tax`:
  - `GET /tax/years` – Liste aller Jahre
  - `POST /tax/years` – Jahr anlegen
  - `GET /tax/years/{id}` – Jahr inkl. Positionen
  - `PATCH /tax/years/{id}` – Status/Notizen aktualisieren
  - `POST /tax/years/{id}/documents` – Dokument verknüpfen
  - `POST /tax/years/{id}/extract` – LLM-Extraktion starten
  - `GET /tax/years/{id}/comparison` – Vergleich Export vs. Bescheid
  - `GET /tax/years/{id}/documents` – Verknüpfte Dokumente
  - `PATCH /tax/positions/{id}` – Position korrigieren/verifizieren
  - `DELETE /tax/positions/{id}` – Position löschen
  - `GET /tax/development` – Zeitreihe pro Kategorie

### 3. Frontend

#### Neue Seiten unter `frontend/src/pages/tax/`

- `TaxYears.tsx` – Übersicht aller Steuerjahre mit Status.
- `TaxYearDetail.tsx` – Detailansicht eines Jahres:
  - Verknüpfte Dokumente
  - Positionen pro Kategorie
  - Button „Extraktion starten“
  - Button „Vergleich anzeigen“
- `TaxImport.tsx` – Upload / Verknüpfung von Dokumenten:
  - Auswahl aus bestehenden Dokumenten
  - Typ: Steuerprogramm-Export oder Bescheid
- `TaxReview.tsx` – Review-UI für extrahierte Positionen:
  - Tabelle mit editierbaren Feldern
  - Verifizieren-Checkbox
  - Kategorie/Subcategory auswählbar
- `TaxComparison.tsx` – Vergleich Export vs. Bescheid:
  - Abweichungen rot markiert
  - Summen pro Kategorie
- `TaxDevelopment.tsx` – Entwicklung über die Jahre:
  - Liniendiagramm pro Kategorie
  - Tabelle mit Jahresvergleich
- `TaxChat.tsx` – Steuer-Assistent:
  - Chat mit Kontext: Steuerjahre, Positionen, verknüpfte Dokumente
  - Fragen wie: „Was hat sich 2025 gegenüber 2024 geändert?“

#### Navigation

- Neuer Hauptnavigationspunkt „Steuer“.
- Innerhalb der Steuer-Seite Tabs: Jahre, Entwicklung, Assistent.

### 4. LLM-Prompts

#### Steuerprogramm-Export

```text
Du erhältst den Text eines Steuerprogramm-Exports.
Extrahiere alle steuerrelevanten Positionen in ein JSON-Array.
Felder pro Objekt:
- category: Eine von [Einkünfte, Werbungskosten, Sonderausgaben, Außergewöhnliche Belastungen, Steuerliche Ergebnisse]
- subcategory: konkrete Untergruppe
- label: lesbare Bezeichnung
- amount: Betrag als Zahl (positiv, EUR)
- page: Seitenzahl im PDF (optional, null wenn unbekannt)
- source_text: Originaltext-Ausschnitt
Ignoriere Kopfzeilen, Fußzeilen und Seitenzahlen.
```

#### Finanzamtsbescheid

```text
Du erhältst den Text eines Finanzamtsbescheids.
Extrahiere:
- Festgesetzte Einkommensteuer
- Soli
- ggf. Kirchensteuer
- Erstattung / Nachzahlung
- Abweichungen gegenüber der Erklärung (wenn im Text erwähnt)
Gib ein JSON-Array mit gleichen Feldern wie beim Steuerprogramm-Export zurück.
```

### 5. Workflows

#### Workflow A: Steuerjahr anlegen und dokumentieren

1. Benutzer legt Steuerjahr an (z. B. 2024).
2. Benutzer verknüpft Steuerprogramm-Export-PDF aus der Dokumenten-DB.
3. Backend extrahiert Positionen mit LLM.
4. Benutzer prüft Positionen in Review-UI und korrigiert falls nötig.
5. Benutzer verknüpft Finanzamtsbescheid.
6. Backend extrahiert Bescheidspositionen.
7. Benutzer vergleicht Export vs. Bescheid.

#### Workflow B: Vorbereitung neues Jahr

1. Benutzer legt neues Jahr an (z. B. 2025).
2. System schlägt wiederkehrende Positionen aus Vorjahren vor.
3. Benutzer verknüpft neue Dokumente.
4. System zeigt fehlende Positionen im Vergleich zum Vorjahr.

#### Workflow C: Analyse über die Jahre

1. Benutzer öffnet „Entwicklung“.
2. Wählt Kategorie(n) aus.
3. Sieht Diagramm und Tabelle mit Beträgen pro Jahr.

### 6. Abhängigkeiten / Erweiterungen bestehende Komponenten

- `documents.full_text` wird für LLM-Extraktion verwendet.
- `categories.py` und `prompts.py` werden um Steuerkategorien erweitert.
- Chat-Modul bekommt einen Steuer-Kontext.
- `documents.low_value` kann Steuer-relevante Dokumente ausschließen.

### 7. Nicht im Scope

- Automatisches Ausfüllen von Steuerformularen.
- Rechtsverbindliche Steuerberatung.
- ELSTER-Integration.
- Cloud-Export.

## Implementierungs-Reihenfolge

1. Datenbank-Schema + Repositories
2. Backend-API für Steuerjahre und Dokumentenverknüpfung
3. LLM-Extraktion für Steuerprogramm-Exporte
4. Review-UI für Positionen
5. Finanzamtsbescheid-Extraktion + Vergleich
6. Entwicklungsdiagramm
7. Steuer-Chat-Assistent

## Erfolgskriterien

- Ein Steuerprogramm-PDF kann importiert und in Positionen aufgeteilt werden.
- Positionen sind korrigierbar und verifizierbar.
- Vergleich zwischen Export und Bescheid zeigt Abweichungen.
- Entwicklung pro Kategorie ist über mindestens 2 Jahre visualisierbar.
- Steuer-Chat kann gezielt Fragen zu einem Steuerjahr beantworten.
