# Feature: Geringer-Wert-Regeln (Low Value Rules)

## Überblick

Regeln markieren Dokumente automatisch als low_value = 1, wenn sie bestimmte Kriterien erfüllen. Damit lassen sich unwichtige Belege von wichtigen Dokumenten trennen.

## Regel-Kriterien

| Feld | Bedeutung |
|------|-----------|
| Name | Anzeigename der Regel |
| Kategorie | Optional: Dokument muss dieser Kategorie zugeordnet sein |
| Dokumententyp | Optional: Dokument muss diesem Typ entsprechen |
| Maximalbetrag | Optional: Betrag in EUR; geprüft gegen items, services, contracts |
| Älter als (Tage) | Optional: Mindestalter des Dokuments |
| Aktiv | Regel ein-/ausschalten |

## Bedienung

| Aktion | Vorgehen |
|--------|----------|
| **Regel erstellen** | Menü **Geringer Wert** öffnen, Name und Bedingungen eintragen, **Regel erstellen** klicken. |
| **Vorschau** | Augen-Icon klicken: Zeigt Treffer ohne Änderung. |
| **Anwenden** | Play-Icon klicken: Markiert alle passenden Dokumente mit low_value = 1. |
| **Aktivieren/Deaktivieren** | Toggle-Schalter in der Liste verwenden. |
| **Löschen** | Mülleimer-Icon klicken und bestätigen. |

## Anzeige

- Sidebar-Badge zeigt die Anzahl der low_value-Dokumente an.
- In der Dokumentenliste kann über **Geringer Wert** gefiltert werden.

## Technische Details

> Architektur, SQL-Matching, API, Mathematik und Tests: [	echnical/04-low-value-rules.md](technical/04-low-value-rules.md)

