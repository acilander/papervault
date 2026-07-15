# PaperVault – Bedienungsanleitung

> Aus dem Code abgeleitete Bedienungsanleitung für Endanwender.

---

## Inhalt

1. [Erste Schritte](#1-erste-schritte)
2. [Dashboard](#2-dashboard)
3. [Prüfung – Dokumente kontrollieren](#3-prüfung--dokumente-kontrollieren)
4. [Dokumente durchsuchen](#4-dokumente-durchsuchen)
5. [Dokument bearbeiten](#5-dokument-bearbeiten)
6. [Duplikate](#6-duplikate)
7. [Absender verwalten](#7-absender-verwalten)
8. [Geringer-Wert-Regeln](#8-geringer-wert-regeln)
9. [Ignorieren und Sperren](#9-ignorieren-und-sperren)
10. [Sammlungen](#10-sammlungen)
11. [Steuer-Modul](#11-steuer-modul)
12. [Haus & Vermietung (MFH), Verträge, Ausgaben](#12-haus--vermietung-mfh-verträge-ausgaben)
13. [KI-Suche & Hybrid RAG](#13-ki-suche--hybrid-rag)
14. [Monitor & Forecasting](#14-monitor--forecasting)
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

### Navigation & Sidebar

Die Navigation ist in vier übersichtliche Bereiche gegliedert:
- **Eingang & Suche:** Dashboard, Prüfung (früher Inbox), Dokumente, Sammlungen, KI-Suche.
- **Haus & Vermietung:** Inventar, Verträge, Services, Absender.
- **Steuern & Qualität:** Steuer-Modul, Geringer Wert, Feedback, Duplikate.
- **System:** Monitor, Einstellungen.

### Dark Mode

- Über das Sonne/Mond-Icon oben links in der Sidebar umschalten.
- Der Modus folgt initial der Systemeinstellung.

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

## 3. Prüfung – Dokumente kontrollieren

Unter **Prüfung** (früher "Inbox") finden Sie Dokumente, die noch nicht als endgültig klassifiziert sind.

### Reiter

- **Zu überprüfen** (`review`): Dokumente, bei denen die KI-Klassifikation geprüft werden soll.
- **In Verarbeitung** (`processing` / `pending`): Dokumente, die gerade verarbeitet werden (PDF, Word, Excel).
- **Fehlgeschlagen** (`classification_failed`): Dokumente, die nicht automatisch klassifiziert werden konnten.

### Aktionen pro Dokument

- **Öffnen**: Datei ansehen.
- **Bearbeiten**: Sender, Datum, Kategorie, Dokumententyp, Wohneinheit (MFH), Zusammenfassung korrigieren.
- **Bestätigen**: Dokument als überprüft markieren (`status = ok`).
- **Neu verarbeiten**: KI-Klassifikation mit optionalem Hinweis wiederholen.
- **Löschen**: Dokument samt Datei entfernen.

---

## 4. Dokumente durchsuchen

Unter **Dokumente** befindet sich die zentrale Übersicht aller archivierten Dokumente.

### Ansichten

- **Listenansicht**: Tabellarische Darstellung mit Sortierung.
- **Grid-Ansicht**: Thumbnail-Vorschau der Dokumente.

### Filter

Oben in der Leiste stehen verschiedene Filter zur Verfügung:

- **Suche** (`q`): Volltextsuche über Dateiname, Sender, Zusammenfassung, Keywords.
- **Kategorie & Wohneinheit**: Nach Dokumentenkategorie oder MFH-Einheit (EG, OG) filtern.
- **Jahr**: Archivierungsjahr.
- **Sender**: Nach Absender filtern.
- **Status**: z. B. `ok`, `review`, `locked`, `ignored`, `missing`.
- **Steuerrelevant**: Nur als steuerrelevant markierte Dokumente.

---

## 5. Dokument bearbeiten

Klick auf einen Dateinamen öffnet die Detailansicht.

### Metadaten bearbeiten

Folgende Felder können geändert werden:

- Dateiname (optional umbenennen, bei Office-Dateien bleibt die Endung)
- Sender
- Datum
- Dokumententyp
- Kategorie & **Wohneinheit (MFH)** (EG, OG, DG, UG, Gesamthaus)
- Zusammenfassung
- Tags (kommasepariert, z.B. Auto-Modell `vehicle_id` oder Kind `child_name`)
- Steuerrelevant & Steuerjahr
- Läuft ab (Ablaufdatum)
- Notizen (Hier hinterlegt der Contract Auditor auch Warnungen)

---

## 6. Duplikate
## 7. Absender verwalten
## 8. Geringer-Wert-Regeln
## 9. Ignorieren und Sperren
## 10. Sammlungen
*(Diese Funktionen funktionieren wie gehabt, siehe UI)*

---

## 11. Steuer-Modul

### Proactive Tax Linking (Phase 8c)
Dokumente der Kategorien `Haus_Gemeinkosten`, `OG_Miete` oder `DG_Miete` werden vom System beim Archivieren vollautomatisch als Entwurf ("draft") im passenden Steuerjahr angelegt. Sie müssen diese nur noch prüfen.

---

## 12. Haus & Vermietung (MFH), Verträge, Ausgaben

### Haus & Vermietung (MFH)
Die MFH-Architektur erlaubt die Zuordnung von Dokumenten, Verträgen und Inventar zu spezifischen Wohneinheiten (EG, OG, DG, UG, Gesamthaus). Dies spiegelt sich in den Tabellen und Formularen wider.

### Contract Risk Auditor (Verträge)
Die KI prüft beim Import von Verträgen automatisch auf Klauseln wie "Indexmiete", "Staffelmiete" oder "Selbstbeteiligung" und hinterlegt eine Warnung im Notizfeld des Dokuments, damit Sie diese nicht übersehen.

### Asset & Family Tracking (Inventar & Tags)
Dokumente können mit `vehicle_id` (z.B. Kennzeichen oder Modell) oder `child_name` getaggt werden. Das System sortiert diese automatisch in entsprechende Unterordner im Dateisystem.

---

## 13. KI-Suche & Hybrid RAG

Unter **KI-Suche** befragen Sie das lokale LLM über Ihr gesamtes Archiv.

- **Hybrid RAG Chat:** Die Suche nutzt nun "Hybrid Retrieval". Das bedeutet, es wird nicht nur nach exakten Stichworten (FTS5) gesucht, sondern auch nach semantischer Bedeutung (Vektor-Embeddings via GPU). Wenn Sie "Wo ist der Vertrag für das Internet?" fragen, findet das System auch Dokumente, die nur "Breitbandanschluss" oder "Router" erwähnen.

---

## 14. Monitor & Forecasting

Der **Monitor** zeigt den Live-Status der Verarbeitung an.

### Predictive Utility Forecasting
Neu auf der Monitor/Analytics Seite ist das **Forecasting**. Das System nutzt lineare Regression (Numpy Polyfit) über Ihre historischen Rechnungen für Wasser, Strom und Heizung, um die Kosten für das nächste Jahr vorherzusagen. Es generiert Empfehlungen, ob die Nebenkostenvorauszahlungen der Mieter (MFH) angepasst werden sollten.

---

## 15. Feedback
## 16. Einstellungen

Unter **Einstellungen** werden globale Optionen konfiguriert, unter anderem auch die Aktivierung der MFH-Einheiten und die LLM-Pfade.

---

## 17. Fehlerbehebung

- **VLM OCR Fallback:** Wenn ein Dokument sehr schlecht gescannt ist, übernimmt im Hintergrund das Moondream2 Vision-Language Model. Dies kann etwas länger dauern als klassisches OCR, liefert aber deutlich bessere Ergebnisse bei Handy-Fotos.
- **Word/Excel:** `docx` und `xlsx` Dateien werden nun nativ unterstützt und müssen nicht mehr als PDF gedruckt werden.
