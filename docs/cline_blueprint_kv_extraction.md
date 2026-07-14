# Cline Blueprint: Key-Value Extraction für Rechnungsdaten

**Zielsetzung:**
Wir wollen die Vorverarbeitung in `backend/pdf_utils.py` erweitern. Anstatt das LLM das Rechnungsdatum und die Rechnungsnummer selbst aus dem riesigen Textblock heraussuchen zu lassen, sollen diese (falls sie offensichtlich als "Schlüssel: Wert" vorliegen) mit Regex (Regular Expressions) direkt extrahiert und als harter Fakt an das LLM übergeben werden. Das reduziert Halluzinationen weiter.

---

## Schritt-für-Schritt Anleitung für Cline

### Schritt 1: Datei öffnen
Öffne die Datei `backend/pdf_utils.py`. Lies dir die Funktionen `extract_features` und `build_feature_prompt` aufmerksam durch.

### Schritt 2: Regex-Extraktion in `extract_features` hinzufügen
Suche in der Funktion `extract_features(text, filename=None, file_path=None)` nach der Stelle, an der das Dictionary `features = {}` erstellt wird (ca. Zeile 181).

Füge dort einen neuen Block für **Exact Key-Value Matches** hinzu. Nutze `re.search` (auf dem normalisierten Text `t_norm` oder dem Original `t`), um folgende typische Muster zu finden:

1. **Rechnungsdatum:** Suche nach dem Wort "rechnungsdatum" (oder "datum"), gefolgt von Doppelpunkt/Leerzeichen und einem echten Datum. 
   *(Tipp für Regex: `r'rechnungsdatum[\s:]*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})'`)*
   Speichere das gefundene Datum (Group 1) in `features["exact_date"]`.

2. **Rechnungsnummer:** Suche nach "rechnungsnummer" oder "rechnungs-nr", gefolgt von einer alphanumerischen Nummer.
   *(Tipp für Regex: `r'rechnungsnummer[\s:]*([a-zA-Z0-9\-/]{4,20})'`)*
   Speichere die Nummer in `features["exact_invoice_no"]`.

### Schritt 3: Den Prompt-Builder aktualisieren
Suche die Funktion `build_feature_prompt(features)`. Diese Funktion erstellt den String, der an das LLM geschickt wird.

Füge Logik hinzu, um die neu extrahierten Daten (falls vorhanden) in die Liste `lines` aufzunehmen:
* `if features.get("exact_date"):` -> Hänge den Text `"  Gefundenes Rechnungsdatum: {Datum}"` an `lines` an.
* `if features.get("exact_invoice_no"):` -> Hänge den Text `"  Gefundene Rechnungsnummer: {Nummer}"` an `lines` an.

### Schritt 4: Code prüfen und speichern
Überprüfe, ob die Einrückungen (Indentation) korrekt sind und keine Syntax-Fehler vorliegen. Speichere die Datei.

---
**Hinweis für den Agenten:** Fokussiere dich ausschließlich auf diese Änderungen in `backend/pdf_utils.py`. Ändere keine anderen Teile der Architektur.
