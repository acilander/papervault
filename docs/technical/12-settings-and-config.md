# Technisch: Einstellungen und Konfiguration

## 1. Ziel

Globale Einstellungen des Systems verwalten.

## 2. Konfiguration in `backend/config.py`

Wichtige Variablen:

| Variable | Bedeutung | Beispiel |
|----------|-----------|----------|
| `DB_PATH` | SQLite-Datenbank | `data/papervault.db` |
| `SOURCE_DIR` / `INBOX_DIR` | Eingangsordner | `data/inbox` |
| `TARGET_BASE` | Archiv-Ordner | `data/archive` |
| `DUPLICATES_DIR` | Duplikat-Ordner | `data/duplicates` |
| `IGNORED_DIR` | Ignorierte Dateien | `data/ignored` |
| `MODEL_PATH` | Pfad zum GGUF-Modell | `models/model.gguf` |
| `MOCK_LLM` | LLM simulieren | `False` |
| `CORS_ORIGINS` | Erlaubte Frontend-Origins | `["http://localhost:5173"]` |

## 3. Umgebungsvariablen

Konfiguration kann über `.env` erfolgen. Siehe `.env.example`.

## 4. Konfigurationsendpunkt

`GET /config/` und `PATCH /config/` liefern bzw. aktualisieren Einstellungen zur Laufzeit.

## 5. Frontend

- Seite `Settings.tsx` zeigt Einstellungen an.
- Änderungen werden per API an das Backend gesendet.
- Einige Änderungen erfordern Backend-Neustart (z. B. Pfad-Änderungen).

## 6. Hinweise

- Pfade sollten absolute Pfade verwenden.
- Das Backend erstellt fehlende Verzeichnisse beim Start.
- Änderungen am Modellpfad wirken sich erst nach dem nächsten `load_model()` aus.

