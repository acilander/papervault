# PaperVault – UI-Referenz

> Pixelgenaue Beschreibung aller Bedienelemente pro Seite.

---

## Inhalt

1. [Dashboard](#1-dashboard)
2. [Sidebar](#2-sidebar)
3. [Dokumente](#3-dokumente)
4. [Dokumenten-Detail](#4-dokumenten-detail)
5. [Inbox](#5-inbox)
6. [Absender](#6-absender)
7. [Geringer-Wert-Regeln](#7-geringer-wert-regeln)
8. [Sammlungen](#8-sammlungen)
9. [Duplikate](#9-duplikate)
10. [Steuer](#10-steuer)
11. [KI-Suche](#11-ki-suche)
12. [Monitor](#12-monitor)
13. [Inventar, Verträge, Ausgaben](#13-inventar-vertraege-ausgaben)
14. [Einstellungen](#14-einstellungen)

---

## 1. Dashboard

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| KPI-Karten | Kacheln | Schnellübersicht: Gesamtdokumente, unreviewte Absender, fehlende Dateien, ablaufende Dokumente, fehlgeschlagene Klassifikationen |
| Diagramme | Charts | Dokumente nach Kategorie / Jahr / Status |
| Kürzlich archiviert | Liste | Letzte Dokumente mit Link zur Detailansicht |

---

## 2. Sidebar

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| PaperVault-Logo | Überschrift | Link zur Startseite |
| Dark-Mode-Toggle | Button | Sonne/Mond-Icon |
| Hauptnavigation | NavLinks | Dashboard, Inbox, Dokumente, Absender, KI-Suche, Sammlungen, Duplikate, Inventar, Verträge, Ausgaben, Validierung, Monitor, Feedback, Geringer Wert, Steuer, Einstellungen |
| Badges | Zähler | Unreviewte Absender, Review-Dokumente, Duplikate, Inbox-Dateien |
| Schnellfilter | Buttons | Fehlgeschlagen, Steuerrelevant, Läuft ab, Datei fehlt, Kein Absender, Geringer Wert |

---

## 3. Dokumente

### 3.1 Filterleiste

| Element | Typ | Beschreibung | Aktion |
|---------|-----|--------------|--------|
| Volltext suchen | Textfeld | `Search`-Icon, Placeholder „Volltext suchen…" | Suche über Dateiname, Sender, Summary, Keywords, Volltext; Enter startet Suche |
| Kategorie | Dropdown | Optionen: „Alle Kategorien" + alle konfigurierten Kategorien | Filter nach Kategorie |
| Jahr | Dropdown | „Alle Jahre" + verfügbare Archivierungsjahre | Filter nach Jahr |
| Absender | Textfeld | Eingabe des Absendernamens | Filter nach Absender |
| Status | Dropdown | Alle Status, OK, Review, Gesperrt, Irrelevant, Fehlgeschlagen, Verschlüsselt, Korrupt, Duplikat, Datei fehlt | Filter nach Status |
| Steuer | Toggle-Button | 🧾 Steuerrelevant | Filter `tax=1` umschalten |
| Läuft ab | Toggle-Button | ⏰ Läuft ab | Filter `expires=1` umschalten |
| Kein Absender | Toggle-Button | 👤 Kein Absender | Filter `no_sender=1` umschalten |
| Geringer Wert | Toggle-Button | ⚠️ Geringer Wert | Filter `low_value=1` umschalten |
| Confidence | Dropdown | Alle Confidence, Low, Medium, High | Filter nach Klassifikations-Confidence |
| Suchen | Button | Blauer Button | Lädt Dokumente mit aktiven Filtern |
| Zurücksetzen | Button | erscheint bei aktiven Filtern | Setzt alle Filter zurück |

### 3.2 Tag-Chips

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Tags | Chips | Liste aller im aktuellen Filter verfügbaren Tags; Klick filtert auf Tag, erneuter Klick entfernt Filter |

### 3.3 Aktive Filter-Pills

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Aktive Filter | Badges | Zeigt gesetzte Filter an; jedes Pill hat ein ✕ zum Entfernen; „Alle löschen" setzt alles zurück |

### 3.4 Fehler- und Undo-Bereich

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Fehlermeldung | Banner | Rotes Banner bei API-Fehlern |
| Undo-Banner | Banner | Gelber Banner nach Bulk-Edit mit „Rückgängig"-Button und Schließen-Button |

### 3.5 Bulk-Aktionsleiste

| Element | Typ | Beschreibung | Aktion |
|---------|-----|--------------|--------|
| Ausgewählt | Text | Anzahl der selektierten Dokumente | – |
| Feld wählen | Dropdown | Kategorie / Dokumenttyp / Absender | Bestimmt, welches Feld geändert wird |
| Neuer Wert | Textfeld / Dropdown | Freie Eingabe oder Kategorie-Dropdown | Neuer Wert für Bulk-Update |
| Anwenden | Button | Speichert Bulk-Update | `PATCH /documents/bulk` |
| Collection wählen | Dropdown | Verfügbare Sammlungen | Zielsammlung für Hinzufügen |
| Zu Collection | Button | Fügt ausgewählte Dokumente zur Sammlung hinzu | `POST /collections/{id}/documents` |
| Auswahl aufheben | Button | Entfernt alle Selektionen | – |

### 3.6 Listen-/Grid-Ansicht

| Element | Typ | Beschreibung | Aktion |
|---------|-----|--------------|--------|
| Trefferanzeige | Text | z. B. „12 von 150 Dokumenten" | – |
| CSV-Export | Link | Download aktueller gefilterter Liste als CSV | `GET /documents/export/csv` |
| Listenansicht | Button | `LayoutList`-Icon | Wechsel zur Tabellenansicht |
| Kachelansicht | Button | `LayoutGrid`-Icon | Wechsel zur Thumbnail-Ansicht |

### 3.7 Dokumententabelle (Listenansicht)

| Spalte | Typ | Beschreibung |
|--------|-----|--------------|
| Checkbox | Checkbox | Zeilenauswahl für Bulk-Actions; Header-Checkbox selektiert alle sichtbaren |
| Dateiname | Link | Klick öffnet Detailansicht; Schloss-Icon bei `locked` |
| Absender | Text | – |
| Kategorie | Badge | Blaues Badge |
| Typ | Text | Dokumententyp |
| Datum | Text | Dokumentendatum |
| Status | Badge | Farbiger Status-Badge |
| Archiviert | Text | Datum der Archivierung (YYYY-MM-DD) |

### 3.8 Grid-Ansicht

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Thumbnail | Bild | PDF-Vorschau; wird bei Fehler ausgeblendet |
| Dateiname | Text | Unten in der Kachel |
| Absender | Text | – |
| Datum (Monat) | Text | `YYYY-MM` |
| Status | Badge | Kleiner Status-Badge |

### 3.9 Pagination

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Bereichsanzeige | Text | z. B. „1–50 von 150" |
| Seitenzahlen | Buttons | Vor/Zurück und einzelne Seiten |

---

## 4. Dokumenten-Detail

### 4.1 Header

| Element | Typ | Beschreibung | Aktion |
|---------|-----|--------------|--------|
| Zurück | Button | Pfeil nach links | Zurück zur Dokumentenliste |
| Dateiname | Text | Anzeige/Edit-Modus | – |
| Umbenennen | Button | Bleistift-Icon | Aktiviert Dateinamen-Edit |
| Speichern | Button | `Save`-Icon | Speichert alle Metadaten-Änderungen |
| Gelöscht-Badge | Badge | Zeigt an, wenn Datei fehlt | – |

### 4.2 Metadaten-Formular

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| Dateiname | Textfeld | Nur im Edit-Modus änderbar; gesperrt bei `locked`/`ignored` |
| Sender | Textfeld mit Datalist | Autocomplete über bekannte Absender |
| Datum | Textfeld | ISO-Datum |
| Dokumententyp | Dropdown | Liste der konfigurierten Dokumententypen |
| Kategorie | Dropdown | Liste der konfigurierten Kategorien |
| Zusammenfassung | Textarea | Freitext |
| Tags | Textfeld | Kommaseparierte Tags |
| Steuerrelevant | Checkbox | 0/1 |
| Steuerjahr | Textfeld | Jahr |
| Läuft ab | Textfeld | Ablaufdatum |
| Notizen | Textarea | Freitext |
| Status | Dropdown | Alle Dokumentenstatus |

> Hinweis: Bei `locked` oder `ignored` sind alle Felder deaktiviert (read-only).

### 4.3 PDF-Vorschau

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| PDF-Viewer | iframe | Zeigt die PDF-Datei an |
| Fehlermeldung | Text | Falls Datei nicht gefunden wird |

### 4.4 Aktionen

| Element | Typ | Beschreibung | Aktion |
|---------|-----|--------------|--------|
| Neu verarbeiten | Button | `RefreshCw`-Icon | Öffnet Dialog mit optionalem Hinweis |
| Bestätigen | Button | `CheckCircle`-Icon | Setzt Status auf `ok` |
| Ignorieren / Wiederherstellen | Button | `EyeOff` / `Eye` | Toggle Ignore-Status |
| Sperren / Entsperren | Button | `Lock` / `Unlock` | Toggle Lock-Status |
| Im Explorer öffnen | Button | `FolderOpen`-Icon | Öffnet Dateipfad im Dateiexplorer |
| Löschen | Button | `Trash2`-Icon | Löscht Dokument + Datei |
| Zu Collection | Button | `BookMarked`-Icon | Öffnet Collection-Auswahl |

### 4.5 Duplikat-Hinweis

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Original-Dokument | Link | Wenn Status `duplicate`, Link zum Originaldokument |

---

## 5. Inbox

### 5.1 Tabs

| Tab | Beschreibung |
|-----|--------------|
| Zu überprüfen | Dokumente mit Status `review` |
| In Verarbeitung | Dokumente mit Status `pending` oder `processing` |
| Fehlgeschlagen | Dokumente mit Status `classification_failed` |

### 5.2 Listenansicht pro Dokument

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Checkbox | Checkbox | Einzel-/Massenauswahl |
| Dateiname | Link | Öffnet PDF |
| Sender / Kategorie / Typ | Text | Bearbeitbar im expandierten Bereich |
| Status | Badge | – |
| Expand-Icon | Button | Klappbare Detail-Bearbeitung auf |

### 5.3 Expand-Bereich (Bearbeiten)

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| Sender | Textfeld | – |
| Datum | Textfeld | – |
| Kategorie | Dropdown | – |
| Dokumententyp | Dropdown | – |
| Zusammenfassung | Textarea | – |

### 5.4 Aktionen pro Dokument

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Öffnen | Button | PDF anzeigen |
| Bestätigen | Button | Status `ok` |
| Neu verarbeiten | Button | Mit optionalem Hinweis |
| Löschen | Button | Dokument + Datei |

### 5.5 Massenaktionen

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Alle bestätigen | Button | Setzt alle selektierten auf `ok` |
| Alle neu verarbeiten | Button | Öffnet Hinweis-Dialog für alle selektierten |

---

## 6. Absender

### 6.1 Toolbar

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Suche | Textfeld | Filter nach Absendernamen |
| Nur Unreviewed | Toggle | Zeigt nur unreviewte Absender |
| Neu laden | Button | Lädt `senders.json` neu |
| Neu aufbereiten | Button | Baut Registry aus Dokumenten neu auf |
| Audit | Button | Startet Plausibilitätsprüfung |
| Ambiguous | Button | Zeigt mehrdeutige Absender |

### 6.2 Tabelle

| Spalte | Beschreibung |
|--------|--------------|
| Name | Absendername |
| Anzahl | OK / Review-Zahlen |
| Kategorien | Zugeordnete Kategorien |
| Gepinnt | Festgelegte Kategorie und Dokumententyp |
| Zusammenführen | Dropdown für Merge-Ziel |
| Aktionen | Umbenennen, Löschen, Kategorie entfernen |

### 6.3 Inline-Edit

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| Gepinnte Kategorie | Dropdown | Setzt `pinned_category` |
| Gepinnter Typ | Dropdown | Setzt `pinned_document_type` |
| Reviewed | Checkbox | Markiert Absender als geprüft |

---

## 7. Geringer-Wert-Regeln

### 7.1 Formular (Regel erstellen)

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| Name | Textfeld | Anzeigename |
| Kategorie | Dropdown | Optional |
| Dokumententyp | Dropdown | Optional |
| Maximalbetrag | Textfeld | Optional, in EUR |
| Älter als (Tage) | Textfeld | Optional |
| Aktiv | Checkbox | Regel ein-/ausschalten |
| Regel erstellen | Button | Speichert Regel |

### 7.2 Regel-Tabelle

| Spalte | Beschreibung |
|--------|--------------|
| Name | Regelname |
| Filter | Kategorie / Typ / Betrag / Alter |
| Aktiv | Toggle |
| Aktionen | Vorschau, Anwenden, Löschen |

### 7.3 Vorschau-Panel

| Element | Beschreibung |
|---------|--------------|
| Trefferliste | Dokumente, die zur Regel passen würden |
| Schließen | Entfernt Vorschau |

---

## 8. Sammlungen

### 8.1 Übersicht

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Neue Sammlung | Button | Öffnet Formular |
| Sammlungskacheln | Cards | Name, Beschreibung, Farbe, Dokumentenanzahl |

### 8.2 Formular

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| Name | Textfeld | – |
| Beschreibung | Textfeld | – |
| Farbe | Color Picker | Vorgegebene Farben |

### 8.3 Detailansicht

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Zurück | Button | Zur Übersicht |
| Bearbeiten | Button | Name/Beschreibung ändern |
| Löschen | Button | Sammlung löschen |
| ZIP-Download | Link | Alle Dokumente als ZIP |
| Dokumentenliste | Tabelle | Zugeordnete Dokumente |

---

## 9. Duplikate

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Duplikat-Gruppen | Liste | Nach Hash gruppierte Duplikate |
| Original | Link | Link zum Originaldokument |
| Löschen | Button | Entfernt Duplikat |

---

## 10. Steuer

### 10.1 Steuerjahre-Übersicht

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Jahr anlegen | Formular | Eingabe Jahr |
| Jahreskacheln | Cards | Jahr, Status, Anzahl Positionen |

### 10.2 Jahres-Detail

| Tab/Reiter | Beschreibung |
|------------|--------------|
| Dokumente | Verknüpfte Steuerprogramm-Exporte und Bescheide |
| Positionen | Extrahierte Steuerpositionen |
| Vergleich | Export vs. Bescheid |

### 10.3 Aktionen

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Dokument verknüpfen | Button | Fügt Dokument zum Jahr hinzu |
| Extrahieren | Button | Startet LLM-Extraktion |
| Position bearbeiten | Inline-Edit | Betrag, Kategorie, Verifizierung |
| Position löschen | Button | – |

---

## 11. KI-Suche

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Eingabe | Textfeld | Frage eingeben |
| Senden | Button | An LLM senden |
| Antwort | Chat-Bubble | Generierte Antwort |
| Steuer-Chat | Tab | Spezieller Modus für Steuerfragen |

---

## 12. Monitor

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| SSE-Status | Text | Zeigt Verbindungsstatus |
| Inbox-Dateien | Liste | Aktuell im Inbox-Ordner vorhandene Dateien |
| Verarbeitungslog | Liste | Live-Updates zu laufenden Dokumenten |
| Archiver starten | Button | Startet Verarbeitung manuell |
| Duplikat-Anzahl | Badge | – |

---

## 13. Inventar, Verträge, Ausgaben

Diese Module folgen einem ähnlichen Muster:

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Neuer Eintrag | Button | Formular öffnen |
| Tabelle | Tabelle | Alle erfassten Einträge |
| Bearbeiten | Button | Inline-Edit oder Dialog |
| Löschen | Button | Eintrag entfernen |
| Dokument-Link | Link | Zum Quelldokument springen |

---

## 14. Einstellungen

| Element | Typ | Beschreibung |
|---------|-----|--------------|
| Inbox-Pfad | Textfeld | Eingangsordner |
| Archiv-Pfad | Textfeld | Zielarchiv |
| Duplikat-Pfad | Textfeld | Duplikat-Ordner |
| Ignored-Pfad | Textfeld | Ignorieren-Ordner |
| Modell-Pfad | Textfeld | Pfad zum GGUF-Modell |
| Speichern | Button | Einstellungen persistieren |

---

## Legende zu Icons

| Icon | Bedeutung |
|------|-----------|
| 🔒 / `Lock` | Gesperrt |
| 🚫 | Ignoriert |
| 🧾 | Steuerrelevant |
| ⏰ | Läuft ab |
| 👤 | Kein Absender |
| ⚠️ | Geringer Wert |
| 🔴 / 🟡 / 🟢 | Confidence Low / Medium / High |
