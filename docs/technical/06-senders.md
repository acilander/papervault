# Technisch: Absender-Verwaltung

## 1. Ziel

Absender konsistent identifizieren, kategorisieren und über alle Dokumente hinweg steuern.

## 2. Datenquellen

- **Sender-Registry**: Gespeichert in `senders.json` (JSON-Datei, nicht SQLite).
- **Dokumenten-Statistiken**: `GET /senders/counts` zählt Dokumente pro Absender aus der `documents`-Tabelle.

## 3. Datenstruktur

### Sender-Eintrag

```json
{
  "Musterfirma GmbH": {
    "categories": ["Sonstiges", "Kommunikation"],
    "pinned_category": "Sonstiges",
    "pinned_document_type": "Rechnung",
    "reviewed": true,
    "excluded_categories": ["Versicherung"],
    "aliases": ["Musterfirma"]
  }
}
```

## 4. Abläufe

### 4.1 Erkennen

- LLM extrahiert `sender` beim Import.
- Normalisierung (Trim, gewisse Sonderzeichen).
- Neue Sender werden automatisch in die Registry eingetragen (`reviewed = false`).

### 4.2 Kategorie pinnen

```python
sender_entry["pinned_category"] = "Kommunikation"
```

Beim nächsten Import eines Dokuments dieses Absenders:

1. Pipeline prüft Registry.
2. Wenn `pinned_category` gesetzt, wird diese Kategorie vorgeschlagen/verwendet.
3. LLM-Vorschlag kann überschrieben werden.

### 4.3 Zusammenführen (Merge)

```python
mergeSender(source, target):
    # Alle Dokumente mit source.sender bekommen target
    update documents set sender = target where sender = source
    # Registry-Einträge verschmelzen
    target_entry.categories += source_entry.categories
    delete source_entry
```

### 4.4 Umbenennen

```python
renameSender(old_name, new_name):
    update documents set sender = new_name where sender = old_name
    rename key in senders.json
```

### 4.5 Neu aufbauen

```python
rebuildSenders():
    senders = {}
    for doc in documents:
        if not doc.sender: continue
        entry = senders.setdefault(doc.sender, default_entry)
        entry.categories.add(doc.category)
    save senders.json
```

## 5. Algorithmen

### 5.1 Kategoriewahl beim Import

```python
if sender in registry and registry[sender].pinned_category:
    category = registry[sender].pinned_category
else:
    category = llm_prediction
```

### 5.2 Unreviewte Absender

```python
unreviewed = [name for name, entry in senders.items() if entry.reviewed == False]
```

Wird im Sidebar-Badge und auf der Senders-Seite angezeigt.

### 5.3 Aliase

- Aliase ermöglichen verschiedene Schreibweisen desselben Absenders.
- Beim Import wird der Alias auf den Hauptnamen normalisiert.

## 6. API-Endpunkte

- `GET /senders/` – Liste aller Sender
- `GET /senders/counts` – Dokumentenzahlen pro Sender
- `POST /senders/~reload` – `senders.json` neu laden
- `POST /senders/~rebuild` – Registry aus Dokumenten neu aufbauen
- `PATCH /senders/{name}` – Eintrag aktualisieren
- `POST /senders/{name}/merge` – Zwei Sender zusammenführen
- `POST /senders/{name}/rename` – Absender umbenennen
- Weitere: cleanup, audit, ambiguous, reclassify

## 7. Frontend

- Seite `Senders.tsx` zeigt Tabelle aller Absender.
- Inline-Edit für Kategorie und Typ.
- Merge-Dialog, Rename-Dialog, Audit-Panel.
- Schnellfilter für unreviewte Absender.

## 8. Tests

- `tests/test_senders_api.py` (falls vorhanden)
- Integrationstests in `tests/test_pipeline_steps.py`

## 9. Hinweis

Die Sender-Registry ist ein JSON-Datei-basiertes Konstrukt. Dadurch ist sie leicht manuell editierbar, muss aber bei Operationen wie Merge/Rename konsistent gehalten werden.
