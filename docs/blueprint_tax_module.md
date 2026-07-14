# Blueprint: Steuer-Modul für PaperVault

## Ziel

Ein lokales, datensicheres Steuer-Hilfsprogramm innerhalb von PaperVault. Es lernt aus vergangenen Steuererklärungen (Steuerprogramm-Exporte + Finanzamtsbescheide), strukturiert Positionen pro Jahr und unterstützt die Vorbereitung zukünftiger Erklärungen.

## Grundsatz

- Keine Steuerberatung durch das LLM.
- Positionen müssen vom Benutzer verifiziert werden.
- Alle Daten bleiben lokal.

## Aktueller Implementierungsstand (Stand: 12.07.2026)

### Bereits implementiert

1. **Datenbank-Schema + Repositories**
   - Tabellen: `tax_years`, `tax_documents`, `tax_positions`
   - Dateien: `backend/db/tax_years_repo.py`, `backend/db/tax_documents_repo.py`, `backend/db/tax_positions_repo.py`

2. **Backend-API**
   - Datei: `backend/api/routes/tax.py` mit Prefix `/tax`
   - Endpunkte für Steuerjahre, Dokumentenverknüpfung, Positionen, Extraktion, Vergleich, Entwicklung und Chat

3. **LLM-Extraktion**
   - Datei: `backend/tax/extraction.py`
   - Prompts: `backend/tax/prompts.py`
   - Generische LLM-Hilfsfunktionen: `backend/llm.py` (`llm_json_completion`, `llm_completion`)

4. **Frontend-Seiten**
   - `frontend/src/pages/tax/TaxYears.tsx` – Übersicht aller Steuerjahre
   - `frontend/src/pages/tax/TaxYearDetail.tsx` – Detailansicht mit Dokumenten und Positionen
   - `frontend/src/pages/tax/TaxYearComparison.tsx` – Vergleich Export vs. Bescheid
   - `frontend/src/pages/tax/TaxDevelopment.tsx` – Entwicklungsdiagramm mit Recharts
   - `frontend/src/pages/tax/TaxChat.tsx` – Steuer-Assistent (neu, noch ungetestet)

5. **API-Helpers**
   - Datei: `frontend/src/api.ts` mit allen Tax-Endpunkten inklusive `askTaxQuestion`

6. **Routing und Navigation**
   - Routes in `frontend/src/App.tsx`
   - Navigationseintrag „Steuer“ mit Links zu Jahren, Entwicklung und Assistent

### Noch offen / zu prüfen

- TypeScript-Check und Build der Frontend-Änderungen müssen manuell im `frontend/`-Verzeichnis durchgeführt werden.
- Steuer-Chat-Assistent wurde gerade hinzugefügt, aber noch nicht laufend getestet.

### Start einer neuen Session

Branch: `feature/tax-module`

Aktuelle offene Änderungen (letzter Git-Status):

```
 M backend/api/routes/tax.py
 M backend/llm.py
 M frontend/src/App.tsx
 M frontend/src/api.ts
 M frontend/src/pages/tax/TaxYears.tsx
?? backend/tax/chat.py
?? blueprint_tax_module.md
?? frontend/src/pages/tax/TaxChat.tsx
?? frontend/src/pages/tax/TaxDevelopment.tsx
```

Empfohlene ersten Schritte beim Wiederaufnehmen:
1. Im `frontend/`-Ordner `npx tsc --noEmit` ausführen.
2. Backend-Import prüfen: `python -m py_compile backend/llm.py backend/tax/chat.py backend/api/routes/tax.py`.
3. Falls alles sauber: `git add` und Commit für das Entwicklungsdiagramm + Chat-Assistent.
4. Optional: Backend-Server starten und Chat-Endpunkt `POST /tax/chat` testen.

Wichtige Dateipfade:
- Backend-API: `backend/api/routes/tax.py`
- LLM-Hilfsfunktionen: `backend/llm.py`
- Steuer-Chat-Logik: `backend/tax/chat.py`
- LLM-Prompts: `backend/tax/prompts.py`
- Extraktion: `backend/tax/extraction.py`
- Frontend-API-Helpers: `frontend/src/api.ts`
- Frontend-Routing: `frontend/src/App.tsx`
- Frontend-Steuerjahre: `frontend/src/pages/tax/TaxYears.tsx`
- Frontend-Detail: `frontend/src/pages/tax/TaxYearDetail.tsx`
- Frontend-Vergleich: `frontend/src/pages/tax/TaxYearComparison.tsx`
- Frontend-Entwicklung: `frontend/src/pages/tax/TaxDevelopment.tsx`
- Frontend-Chat: `frontend/src/pages/tax/TaxChat.tsx`

## Zwischenfall: Falsch installierte Abhängigkeit

Während der Implementierung des Entwicklungsdiagramms wurde `recharts` korrekt in `frontend/package.json` installiert. Ein versehentlicher `npx tsc --noEmit`-Aufruf im Projekt-Root (statt im `frontend/`-Ordner) führte dazu, dass `npx` das fremde, veraltete Paket `tsc@2.0.4` zur Installation anbot. Dieses Paket ist nicht Microsofts TypeScript-Compiler.

### Bereinigung

- Root-`node_modules/`, `package.json` und `package-lock.json` wurden gelöscht.
- `frontend/package.json` und `frontend/package-lock.json` enthalten weiterhin korrekt `recharts`.
- Es befinden sich aktuell keine ungewollten Dateien im Repository.

### Korrekte Vorgehensweise für zukünftige Checks

```powershell
cd "C:\Users\Alexander\Documents\Python Apps\papervault\frontend"
npx tsc --noEmit
```

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
- `backend/tax/chat.py`: Steuer-Chat-Assistent, sammelt Kontext und beantwortet Fragen per LLM.

#### Vergleichs-Logik

- Vergleich erfolgt in `backend/api/routes/tax.py` Endpunkt `GET /tax/years/{id}/comparison`.
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
  - `POST /tax/documents/{tax_document_id}/extract` – LLM-Extraktion starten
  - `GET /tax/years/{id}/comparison` – Vergleich Export vs. Bescheid
  - `GET /tax/years/{id}/documents` – Verknüpfte Dokumente
  - `PATCH /tax/positions/{id}` – Position korrigieren/verifizieren
  - `DELETE /tax/positions/{id}` – Position löschen
  - `GET /tax/development` – Zeitreihe pro Kategorie
  - `POST /tax/chat` – Steuer-Chat-Assistent

### 3. Frontend

#### Neue Seiten unter `frontend/src/pages/tax/`

- `TaxYears.tsx` – Übersicht aller Steuerjahre mit Status.
- `TaxYearDetail.tsx` – Detailansicht eines Jahres:
  - Verknüpfte Dokumente
  - Positionen pro Kategorie
  - Button „Extraktion starten“
  - Button „Vergleich anzeigen“
- `TaxYearComparison.tsx` – Vergleich Export vs. Bescheid:
  - Abweichungen rot markiert
  - Summen pro Kategorie
- `TaxDevelopment.tsx` – Entwicklung über die Jahre:
  - Liniendiagramm pro Kategorie
  - Kategorie-Filter
- `TaxChat.tsx` – Steuer-Assistent:
  - Chat-UI mit Nutzer- und Assistent-Nachrichten
  - Sendet Frage an `POST /tax/chat`

#### Navigation

- Neuer Hauptnavigationspunkt „Steuer“.
- Innerhalb der Steuer-Seite: Links zu „Assistent“, „Entwicklung“ und der Jahresliste.

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
2. Wählt Kategorie aus.
3. Sieht Diagramm und Beträge pro Jahr.

## Abhängigkeiten / Erweiterungen bestehende Komponenten

- `documents.full_text` wird für LLM-Extraktion verwendet.
- `categories.py` und `prompts.py` werden um Steuerkategorien erweitert.
- Chat-Modul bekommt einen Steuer-Kontext.
- `documents.low_value` kann Steuer-relevante Dokumente ausschließen.

## Nicht im Scope

- Automatisches Ausfüllen von Steuerformularen.
- Rechtsverbindliche Steuerberatung.
- ELSTER-Integration.
- Cloud-Export.

## Implementierungs-Reihenfolge

1. ✅ Datenbank-Schema + Repositories
2. ✅ Backend-API für Steuerjahre und Dokumentenverknüpfung
3. ✅ LLM-Extraktion für Steuerprogramm-Exporte
4. ✅ Review-UI für Positionen
5. ✅ Finanzamtsbescheid-Extraktion + Vergleich
6. ✅ Entwicklungsdiagramm
7. ✅ Steuer-Chat-Assistent (hinzugefügt, Build/Check ausstehend)

## Erfolgskriterien

- Ein Steuerprogramm-PDF kann importiert und in Positionen aufgeteilt werden.
- Positionen sind korrigierbar und verifizierbar.
- Vergleich zwischen Export und Bescheid zeigt Abweichungen.
- Entwicklung pro Kategorie ist über mindestens 2 Jahre visualisierbar.
- Steuer-Chat kann gezielt Fragen zu einem Steuerjahr beantworten.
