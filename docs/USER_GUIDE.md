# PaperVault – Bedienungsanleitung

> Aus dem Code abgeleitete Bedienungsanleitung für Endanwender.

---

## Inhalt

1. [Erste Schritte](#1-erste-schritte)
2. [Dashboard](#2-dashboard)
3. [Inbox – Dokumente prüfen](#3-inbox--dokumente-prüfen)
4. [Dokumente durchsuchen](#4-dokumente-durchsuchen)
5. [Dokument bearbeiten](#5-dokument-bearbeiten)
6. [Duplikate](#6-duplikate)
7. [Absender verwalten](#7-absender-verwalten)
8. [Geringer-Wert-Regeln](#8-geringer-wert-regeln)
9. [Ignorieren und Sperren](#9-ignorieren-und-sperren)
10. [Sammlungen](#10-sammlungen)
11. [Steuer-Modul](#11-steuer-modul)
12. [Inventar, Verträge, Ausgaben](#12-inventar-verträge-ausgaben)
13. [KI-Suche](#13-ki-suche)
14. [Monitor](#14-monitor)
15. [Feedback](#15-feedback)
16. [Einstellungen](#16-einstellungen)
17. [Fehlerbehebung](#17-fehlerbehebung)

---

## 1. Erste Schritte

### Starten der Anwendung

Auf Windows über PowerShell:

```powershell
.\start_all.ps1
```

Oder manuell:

```powershell
# Backend
.venv\Scripts\python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (neues Terminal)
cd frontend
npm run dev
```

Die Web-App ist dann unter `http://localhost:5173` erreichbar, das Backend unter `http://localhost:8000`.

### Dark Mode

- Über das Sonne/Mond-Icon oben links in der Sidebar umschalten.
- Der Modus folgt initial der Systemeinstellung.

### Erstkonfiguration

1. Unter **Einstellungen** das Archiv-Verzeichnis und das Quellverzeichnis prüfen.
2. Ein geeignetes LLM-Modell (GGUF) hinterlegen.
3. Optionale OCR-Tools (Tesseract, Poppler) im PATH prüfen.

---

## 2. Dashboard

Das Dashboard zeigt einen schnellen Überblick:

- Gesamtzahl der Dokumente
- Dokumente nach Kategorie, Jahr und Status
- Unreviewte Absender
- Kürzlich archivierte Dokumente
- KPI-Karten für fehlende Dateien, ablaufende Dokumente usw.

Klick auf eine Karte oder ein Diagramm führt oft direkt zur gefilterten Dokumentenliste.

---

## 3. Inbox – Dokumente prüfen

Die Inbox zeigt Dokumente, die noch nicht als endgültig klassifiziert sind.

### Reiter

- **Zu überprüfen** (`review`): Dokumente, bei denen die KI-Klassifikation geprüft werden soll.
- **In Verarbeitung** (`processing` / `pending`): Dokumente, die gerade verarbeitet werden.
- **Fehlgeschlagen** (`classification_failed`): Dokumente, die nicht automatisch klassifiziert werden konnten (z. B. verschlüsselte oder korrupte PDFs).

### Aktionen pro Dokument

- **Öffnen**: PDF ansehen.
- **Bearbeiten**: Sender, Datum, Kategorie, Dokumententyp, Zusammenfassung korrigieren.
- **Bestätigen**: Dokument als überprüft markieren (`status = ok`).
- **Neu verarbeiten**: KI-Klassifikation mit optionalem Hinweis wiederholen.
- **Löschen**: Dokument samt Datei entfernen.

### Massenbearbeitung

- Mehrere Dokumente über Checkboxen auswählen.
- Mit den Buttons oben alle ausgewählten Dokumente bestätigen oder neu verarbeiten.

---

## 4. Dokumente durchsuchen

Unter **Dokumente** befindet sich die zentrale Übersicht aller archivierten Dokumente.

### Ansichten

- **Listenansicht**: Tabellarische Darstellung mit Sortierung.
- **Grid-Ansicht**: Thumbnail-Vorschau der Dokumente.

### Filter

Oben in der Leiste stehen verschiedene Filter zur Verfügung:

- **Suche** (`q`): Volltextsuche über Dateiname, Sender, Zusammenfassung, Keywords.
- **Kategorie**: Nach Dokumentenkategorie filtern.
- **Jahr**: Archivierungsjahr.
- **Sender**: Nach Absender filtern.
- **Status**: z. B. `ok`, `review`, `locked`, `ignored`, `missing`.
- **Steuerrelevant**: Nur als steuerrelevant markierte Dokumente.
- **Geringer Wert**: Nur Dokumente mit `low_value = 1`.
- **Kein Absender**: Dokumente ohne erkannten Absender.
- **Confidence**: Nach Klassifikations-Confidence filtern (`low`, `medium`, `high`).
- **Tag**: Nach Tag filtern (sofern Tags vergeben sind).

### Schnellfilter in der Sidebar

- **Fehlgeschlagen**
- **Steuerrelevant**
- **Läuft ab** (nächste 60 Tage)
- **Datei fehlt**
- **Kein Absender**
- **Geringer Wert**

Klick auf einen Schnellfilter öffnet die Dokumentenliste mit dem passenden Filter.

### Sortierung

- Nach Dateiname, Sender, Datum, Kategorie, Status, Archivierungsdatum sortierbar.
- Auf- oder absteigend.

### Selektion und Bulk-Edit

- Checkboxen in der Liste ermöglichen die Mehrfachauswahl.
- Oben rechts „Bulk-Edit“: Feld wählen (z. B. Kategorie, Steuerjahr, Tags), Wert eingeben, auf alle ausgewählten Dokumente anwenden.
- Rückgängig machen über den gelben Undo-Banner, der nach einem Bulk-Edit erscheint.

---

## 5. Dokument bearbeiten

Klick auf einen Dateinamen öffnet die Detailansicht.

### Metadaten bearbeiten

Folgende Felder können geändert werden:

- Dateiname (optional umbenennen)
- Sender
- Datum
- Dokumententyp
- Kategorie
- Zusammenfassung
- Tags (kommasepariert)
- Steuerrelevant (Checkbox)
- Steuerjahr
- Läuft ab (Ablaufdatum)
- Notizen
- Status

### Wichtige Hinweise

- **Gesperrte Dokumente** (`locked`) können nicht bearbeitet werden. Entsperren vor einer Änderung.
- **Ignorierte Dokumente** (`ignored`) können ebenfalls nicht bearbeitet werden.
- Änderungen an Metadaten werden gespeichert, sobald der „Speichern“-Button geklickt wird.

### PDF ansehen

- Klick auf das PDF zeigt die Datei an (sofern vorhanden).
- Bei fehlender Datei wird der Status automatisch auf `missing` gesetzt.

### Aktionen

- **Neu verarbeiten**: LLM-Klassifikation wiederholen.
- **Bestätigen**: Status auf `ok` setzen.
- **Ignorieren / Wiederherstellen**
- **Sperren / Entsperren**
- **Löschen**: Dokument samt Datei entfernen.

---

## 6. Duplikate

Unter **Duplikate** werden Dokumente angezeigt, die denselben Inhaltshash haben.

### Ablauf

- Beim Import wird anhand des SHA256-Hashes geprüft, ob ein Dokument bereits existiert.
- Doppelte Dateien werden automatisch in den `duplicates/`-Ordner verschoben und mit Status `duplicate` markiert.
- Wenn der Original-Hash als `locked` geschützt ist, wird das Duplikat ebenfalls abgelehnt.

### Manueller Umgang

- Duplikate können eingesehen und gelöscht werden.
- Das Original-Dokument behält den Status `ok` oder `locked`.

---

## 7. Absender verwalten

Unter **Absender** werden alle erkannten Absender aufgelistet.

### Ansicht

- Name des Absenders
- Anzahl der zugeordneten Dokumente
- Zugeordnete Kategorien
- Festgepinnte Kategorie/Dokumententyp
- Review-Status

### Aktionen

- **Kategorie festlegen**: Feste Kategorie für alle zukünftigen Dokumente dieses Absenders setzen.
- **Dokumententyp festlegen**: Typ vorbelegen.
- **Reviewed**: Absender als geprüft markieren.
- **Zusammenführen**: Zwei Absender-Einträge vereinen.
- **Umbenennen**: Schreibweise korrigieren.
- **Neu laden**: `senders.json` ohne Backend-Neustart neu einlesen.
- **Neu aufbauen**: Sender-Registry aus allen Dokumenten neu generieren.
- **Audit**: Plausibilitätsprüfung für Absender starten (sofern implementiert).

### Tipps

- Unreviewte Absender werden im Sidebar-Badge angezeigt.
- Eine feste Kategorie beschleunigt die zukünftige Klassifikation.

---

## 8. Geringer-Wert-Regeln

Siehe auch: [`feature-low-value-rules.md`](feature-low-value-rules.md)

### Zweck

Dokumente automatisch als „geringer Wert“ markieren, um unwichtige Belege zu kennzeichnen.

### Regeln erstellen

1. Menü **Geringer Wert** in der Sidebar öffnen.
2. Name vergeben.
3. Bedingungen auswählen:
   - Kategorie
   - Dokumententyp
   - Maximalbetrag (wird gegen `items`, `services`, `contracts` geprüft)
   - Älter als X Tage
4. **Regel erstellen**.

### Regel testen und anwenden

- **Vorschau** zeigt alle passenden Dokumente, ohne sie zu verändern.
- **Anwenden** markiert alle passenden Dokumente mit `low_value = 1`.

### Filter in Dokumentenliste

- Über den Button **Geringer Wert** oder den Sidebar-Schnellfilter lassen sich als gering markierte Dokumente anzeigen.

---

## 9. Ignorieren und Sperren

Siehe auch: [`feature-ignore-lock.md`](feature-ignore-lock.md)

### Ignorieren

- In der Dokumenten-Detailansicht auf **Ignorieren** klicken.
- Das Dokument verschwindet aus der Standardliste.
- Der Inhaltshash wird gespeichert, damit das Dokument nicht erneut importiert wird.
- Ignorierte Dokumente werden in den `ignored/`-Ordner verschoben.

### Ignorieren rückgängig machen

1. In der Dokumentenliste den Status-Filter **Irrelevant** wählen.
2. Dokument öffnen.
3. **Wiederherstellen** klicken.

### Sperren

- In der Detailansicht auf **Sperren** klicken.
- Gesperrte Dokumente können nicht bearbeitet oder gelöscht werden.
- Duplikate eines gesperrten Hashes werden abgewiesen.

### Entsperren

- In der Detailansicht auf **Entsperren** klicken.
- Das Schloss-Icon in der Liste verschwindet.

---

## 10. Sammlungen

Unter **Sammlungen** können Dokumente thematisch gruppiert werden (z. B. „Umbau 2024“, „Versicherungen“).

### Sammlung erstellen

1. Auf **Sammlungen** klicken.
2. **Neue Sammlung** mit Name, Beschreibung und Farbe anlegen.

### Dokumente hinzufügen

- In der Dokumentenliste über Bulk-Edit „Zur Sammlung hinzufügen“ wählen.
- Oder in der Sammlungs-Detailansicht einzelne Dokumente hinzufügen.

### Export

- Sammlungen können als ZIP heruntergeladen werden.

---

## 11. Steuer-Modul

Detaillierte Architektur und Planung: [`blueprint_tax_module.md`](blueprint_tax_module.md)

### Steuerjahr anlegen

1. Menü **Steuer** → **Steuerjahre** öffnen.
2. Jahr eingeben und anlegen.

### Dokumente verknüpfen

- In der Steuerjahres-Detailansicht Dokumente hinzufügen.
- Mögliche Quellen:
  - `tax_program_export` (Export aus Steuersoftware)
  - `assessment_notice` (Finanzamtsbescheid)

### Positionen extrahieren

- Klick auf **Extrahieren** startet das lokale LLM.
- Das LLM liest `full_text` und erzeugt strukturierte Positionen (Kategorie, Unterkategorie, Betrag, Seite).
- Positionen müssen vom Benutzer verifiziert werden.

### Positionen korrigieren

- Betrag, Kategorie, Unterkategorie, Bezeichnung bearbeiten.
- **Verifiziert**-Checkbox setzen.
- Positionen löschen, falls falsch erkannt.

### Vergleich Export vs. Bescheid

- Wenn sowohl Steuerprogramm-Export als auch Bescheid vorliegen, zeigt das Modul Abweichungen (`amount` vs. `amount_assessed`).

### Weitere Ansichten

- **Entwicklung**: Zeitreihe der Beträge pro Kategorie über mehrere Jahre.
- **Vergleich**: Jahr gegen Jahr vergleichen.
- **Steuer-Assistent**: KI-Chat für Steuerfragen.

---

## 12. Inventar, Verträge, Ausgaben

Diese Module erfassen spezifische Informationen aus Dokumenten.

### Inventar

- Erfassung von Gegenständen/Geräten.
- Verknüpfung mit Quelldokumenten.

### Verträge

- Übersicht eingehender und laufender Verträge.
- Ablaufdaten und Kündigungsfristen verwalten.

### Ausgaben (Services)

- Erfassung wiederkehrender oder einmaliger Ausgaben.
- Verknüpfung mit Dokumenten.

> Hinweis: Diese Module sind primär Datenerfassungs- und Übersichtsmodule. Details finden sich in der jeweiligen Seite im Frontend.

---

## 13. KI-Suche

Unter **KI-Suche** kann ein lokales LLM befragt werden.

### Dokumentenbasierte Fragen

- Fragen über das Archiv stellen.
- Das LLM greift auf indexierte Dokumenteninhalte zu.

### Steuer-Assistent

- Spezieller Chat für Steuerfragen.
- Berücksichtigt verknüpfte Steuerjahre und Positionen.

> Wichtig: Die KI ersetzt keine Steuerberatung.

---

## 14. Monitor

Der **Monitor** zeigt den Live-Status der Inbox-Verarbeitung.

### Anzeigen

- Aktuell im Inbox-Ordner befindliche Dateien.
- Verarbeitungsstatus in Echtzeit per SSE-Stream.
- Duplikat-Anzahl.

### Aktionen

- Archiver manuell starten.
- Status der Verarbeitung beobachten.

---

## 15. Feedback

Unter **Feedback** können Feedback-Einträge zu Dokumenten oder der Anwendung erfasst werden.

- Kategorien wie Fehler, Wünsche, Bewertungen.
- Hilft bei der Weiterentwicklung des Systems.

---

## 16. Einstellungen

Unter **Einstellungen** werden globale Optionen konfiguriert.

### Typische Einstellungen

- Pfade für Inbox, Archiv, Ignored, Duplikate.
- LLM-Modellpfad.
- OCR-Optionen.
- Dark-Mode-Standard.
- Weitere Konfigurationen je nach Version.

---

## 17. Fehlerbehebung

### Seite bleibt leer oder schwarz

1. Browser-Konsole mit **F12** öffnen.
2. Roten Fehlertext lesen.
3. Häufige Ursachen:
   - Vite-Dev-Server hat die API-Route nicht gelernt → Frontend-Server neu starten.
   - Backend läuft nicht → `start_all.ps1` prüfen.
   - API liefert unerwartetes Format → Backend-Logs prüfen.

### Dokumente werden nicht verarbeitet

- Prüfen, ob Archiver läuft (Monitor-Seite).
- Prüfen, ob PDF lesbar ist (nicht verschlüsselt/korrupt).
- Prüfen, ob LLM geladen ist.

### OCR funktioniert nicht

- `tesseract --version` und `pdftoppm -v` im Terminal prüfen.
- Pfade in den Umgebungsvariablen/PATH hinterlegen.

### API-Fehler 500

- Backend-Log im Terminal lesen.
- Datenbank auf Fehler prüfen: `.venv\Scripts\python backend/db/connection.py` oder Tests laufen lassen.

### Tests ausführen

```powershell
.venv\Scripts\python -m pytest tests/ -q
```

---

## Siehe auch

- [`FEATURES.md`](FEATURES.md) – Übersicht aller Features
- [`feature-ignore-lock.md`](feature-ignore-lock.md) – Ignore / Lock
- [`feature-low-value-rules.md`](feature-low-value-rules.md) – Low-Value-Rules
- [`blueprint_tax_module.md`](blueprint_tax_module.md) – Steuer-Modul (detailliert)
- Backend läuft → OpenAPI-Doku unter `http://localhost:8000/docs`
