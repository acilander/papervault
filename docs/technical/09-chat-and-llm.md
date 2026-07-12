# Technisch: KI-Suche und Chat

## 1. Ziel

Nutzer können Fragen an das lokale LLM stellen. Die Antworten basieren auf den im Archiv indexierten Dokumenteninhalten.

## 2. Komponenten

| Datei | Rolle |
|-------|-------|
| `backend/llm.py` | LLM-Initialisierung, Prompting, JSON-Parsing |
| `backend/api/routes/chat.py` | Chat-Endpunkte |
| `backend/tax/chat.py` | Steuer-spezifischer Chat |
| `frontend/src/pages/Chat.tsx` | Allgemeiner Chat |
| `frontend/src/pages/tax/TaxChat.tsx` | Steuer-Chat |

## 3. LLM-Initialisierung

```python
load_model(model_path)
```

- Lädt GGUF-Modell über `llama-cpp-python`.
- Optional GPU-beschleunigt (CUDA).
- Startet im Hintergrund-Thread beim Backend-Start.

## 4. Chat-Ablauf

### 4.1 Allgemeiner Chat

1. Nutzer stellt Frage.
2. Backend sucht relevante Dokumente (FTS5 oder Filter).
3. Kontext wird aus `full_text`, `summary`, `keywords` gebaut.
4. Prompt an LLM:

```
Du bist ein Assistent für ein Dokumentenarchiv.
Kontext:
- Dokument A: Rechnung Musterfirma, 123 EUR, Büromaterial
- Dokument B: ...

Frage: Wie viel habe ich 2024 für Büromaterial ausgegeben?
```

5. LLM generiert Antwort.
6. Antwort wird als SSE-Stream oder JSON zurückgegeben.

### 4.2 Steuer-Chat

- Zusätzlicher Kontext aus `tax_years`, `tax_positions`, `tax_documents`.
- Eingeschränkt auf steuerliche Fragen.

## 5. Architektur

### Prompt Engineering

- System-Prompt definiert Rolle und Ausgabeformat.
- Few-shot-Beispiele je nach Modul.
- JSON-Modus für strukturierte Extraktionen.

### Token-Management

- Lange Dokumententexte werden gekürzt (`prepare_text_long_trimmed`).
- Chunking oder Top-K-Auswahl relevanter Dokumente.

## 6. Fehlerbehandlung

- Modell nicht geladen → Fehlermeldung.
- JSON nicht parsebar → Retry oder Fallback auf Textantwort.

## 7. Tests

- `tests/test_chat_api.py`
