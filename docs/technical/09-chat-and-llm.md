# Technisch: KI-Suche und Chat (Hybrid RAG)

## 1. Ziel

Nutzer können semantische Fragen an das lokale LLM stellen. Die Antworten basieren auf den im Archiv indexierten Dokumenteninhalten durch ein **Hybrid Retrieval-Augmented Generation (RAG)** System.

## 2. Komponenten

| Datei | Rolle |
|-------|-------|
| `backend/llm/driver.py` | LLM-Initialisierung, Completer, **Embeddings-Generierung** und Thread-Locking |
| `backend/llm/classify.py` | High-Level Dokumentenklassifizierung und Prompting-Assembling |
| `backend/db/embeddings_repo.py` | Speichern und Laden von Vektor-Embeddings als SQLite BLOBs |
| `backend/api/routes/chat.py` | Chat-Endpunkte mit Numpy Cosine Similarity |
| `backend/tax/chat.py` | Steuer-spezifischer Chat |
| `frontend/src/pages/Chat.tsx` | Allgemeiner Chat |

## 3. LLM-Initialisierung & Embeddings

```python
load_model(model_path)
```

- Lädt GGUF-Modell über `llama-cpp-python`.
- Optional GPU-beschleunigt (CUDA).
- Startet im Hintergrund-Thread beim Backend-Start.
- Das Modell liefert neben Textgenerierung auch dichte Vektor-Embeddings für Dokumententexte (`create_embedding`).

## 4. Hybrid RAG Architektur

Um Vektor-Datenbank-Overhead (wie ChromaDB/Qdrant) zu vermeiden, nutzt PaperVault eine hochperformante lokale Hybrid-Lösung:

1. **Embedding-Generierung:** Beim Import wird der Text durch das LLM in einen Vektor (z.B. 1024 Dimensionen) umgewandelt.
2. **SQLite BLOB Storage:** Dieser Float-Array wird via `struct.pack` in ein binäres BLOB komprimiert und in der Tabelle `embeddings` (`embeddings_repo.py`) neben der `document_id` gespeichert.
3. **RAM-Inference (Numpy):** Bei einer Chat-Anfrage wird die Frage ebenfalls vektorisiert. Alle BLOBs werden in den RAM geladen und mit **Numpy** (`np.dot` / Cosine Similarity) verglichen. Dies dauert bei <100.000 Dokumenten nur Millisekunden.
4. **Hybrid Retrieval:** Die Top-K Dokumente aus der semantischen Vektorsuche werden mit den Top-K Dokumenten einer klassischen Keyword-Suche (SQLite FTS5) kombiniert und dedupliziert.

## 5. Chat-Ablauf

### 5.1 Allgemeiner Chat

1. Nutzer stellt Frage (z.B. "Wo ist der Vertrag für das Internet?").
2. Backend führt Hybrid Search (Numpy Cosine Similarity + FTS5) durch.
3. Kontext wird aus den Top-K Treffern (`full_text`, `summary`, `keywords`) gebaut.
4. Prompt an LLM:

```
Du bist ein Assistent für ein Dokumentenarchiv.
Kontext:
- Dokument A (ID: 1): Rechnung Breitbandanschluss...
- Dokument B (ID: 2): ...

Frage: Wo ist der Vertrag für das Internet?
```

5. LLM generiert Antwort ("Im Dokument 'Rechnung Breitbandanschluss' (ID: 1) ...").
6. Antwort wird als SSE-Stream oder JSON zurückgegeben.

### 5.2 Steuer-Chat

- Zusätzlicher Kontext aus `tax_years`, `tax_positions`, `tax_documents`.
- Eingeschränkt auf steuerliche Fragen.

## 6. Architektur & Performance

### Prompt Engineering

- System-Prompt definiert Rolle und Ausgabeformat.
- Few-shot-Beispiele je nach Modul.
- JSON-Modus für strukturierte Extraktionen.

### Token-Management & Chunking

- Lange Dokumententexte werden gekürzt (`prepare_text_long_trimmed`), bevor Embeddings generiert werden.
- Die Context-Window des GGUF-Modells wird strikt überwacht.

## 7. Fehlerbehandlung

- Modell nicht geladen → Fehlermeldung.
- JSON nicht parsebar → Retry oder Fallback auf Textantwort.

## 8. Tests

- `tests/test_chat_api.py`
- `tests/test_embeddings_repo.py` (BLOB Packing/Unpacking)
