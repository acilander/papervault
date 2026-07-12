# Technisch: Feedback

## 1. Ziel

Sammeln von Nutzer-Feedback zu Dokumenten oder zur Anwendung.

## 2. Speicherung

- Primär in SQLite-Tabelle.
- Rückwärtskompatibilität: `feedback.json` wird bei Bedarf migriert.

## 3. Datenmodell

Typische Felder:

- `document_id` (optional)
- `rating` (z. B. 1–5)
- `comment`
- `category` (bug, feature, general)
- `created_at`

## 4. Ablauf

1. Nutzer öffnet Feedback-Seite.
2. Wählt Kategorie, gibt Kommentar ein.
3. Optional Bewertung.
4. Absenden → Speicherung in DB.

## 5. Migration

```python
feedback._migrate_from_json()
```

Wird beim Backend-Start ausgeführt und überträgt alte JSON-Einträge in die Datenbank.

## 6. API

- `GET /feedback/` – Liste
- `POST /feedback/` – Neuer Eintrag
