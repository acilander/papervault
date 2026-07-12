# Feature: Dokumente ignorieren und sperren (Ignore / Lock)

## Überblick

Dokumente können als **irrelevant** markiert oder **gegen Änderungen gesperrt** werden. Der Schutz basiert auf einem SHA256-Hash des Dokumenteninhalts, sodass geschützte Dokumente beim Re-Import erkannt werden.

## Status

- `ignored` – Dokument ist irrelevant, wird in der Standardliste ausgeblendet.
- `locked` – Dokument ist gesperrt, Änderungen sind blockiert.

## Bedienung

| Aktion | Vorgehen |
|--------|----------|
| **Ignorieren** | In der Dokumenten-Detailansicht auf **Ignorieren** klicken. Datei wird nach `ignored/` verschoben. |
| **Wiederherstellen** | Status-Filter **Irrelevant** wählen, Dokument öffnen, **Wiederherstellen** klicken. |
| **Sperren** | In der Detailansicht auf **Sperren** klicken. Dokument bleibt im Archiv, wird aber schreibgeschützt. |
| **Entsperren** | In der Detailansicht auf **Entsperren** klicken. |

## Auswirkungen

- **Standardliste**: `ignored`-Dokumente werden ausgeblendet (sichtbar über Status-Filter).
- **Duplikat-Import**: Ein erneuter Import eines `ignored`-Hashes wird abgewiesen; ein Import eines `locked`-Hashes wird als Duplikat markiert.
- **Bearbeiten**: `PATCH`, Bulk-Update, Reprocess und Confirm sind für `locked`/`ignored` blockiert (HTTP 409).

## Technische Details

> Architektur, Datenbankschema, API, Algorithmen und Tests: [`technical/03-ignore-lock.md`](technical/03-ignore-lock.md)
