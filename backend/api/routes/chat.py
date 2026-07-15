import json
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import db
from llm import get_llm, llm_completion
from utils import log

router = APIRouter(prefix="/chat", tags=["chat"])

FILTER_PROMPT = """Du bist ein Assistent der Dokumentenverwaltung PaperVault.
Der Nutzer stellt eine Frage über seine archivierten Dokumente.

Extrahiere aus der Frage strukturierte Suchfilter als JSON.
Verfügbare Felder:
- sender: Absendername (Firma, Person)
- category: Kategorie (z.B. "Bank & Finanzen", "Fahrzeug & Werkstatt", "Wohnen & Eigentum")
- document_type: Dokumenttyp (z.B. "Rechnung", "Kontoauszug", "Vertrag")
- year: Jahr als String (z.B. "2024")
- keywords: Stichwort das im Dokument vorkommen soll

Gib NUR ein JSON-Objekt zurück, nur mit den Feldern die in der Frage erkennbar sind.
Beispiel: {{"sender": "Autohaus Hohlweck", "year": "2025", "document_type": "Rechnung"}}
Wenn keine Filter erkennbar sind: {{}}

Frage: {question}"""

ANSWER_PROMPT = """Du bist ein Assistent der Dokumentenverwaltung PaperVault.
Beantworte die Frage des Nutzers basierend auf den gefundenen Dokumenten.
Antworte auf Deutsch, präzise und hilfreich. Maximal 3 Sätze.
Wenn keine Dokumente gefunden wurden, sage das klar.

Frage: {question}

Gefundene Dokumente ({count} Treffer):
{context}"""


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    filters: dict
    documents: list[dict]


def _extract_filters(question: str) -> dict:
    # ── CPU-Schutz & Begrüßungs-Bypass ──────────────────────────────────────────
    q_clean = question.strip().lower()
    if q_clean in ("hallo", "hi", "hey", "moin", "guten tag", "guten morgen", "servus", "hallo!", "hi!"):
        return {}

    system_prompt = (
        "Du bist ein Assistent der Dokumentenverwaltung PaperVault.\n"
        "Der Nutzer stellt eine Frage über seine archivierten Dokumente.\n\n"
        "Extrahiere aus der Frage strukturierte Suchfilter als JSON.\n"
        "Verfügbare Felder:\n"
        "- sender: Absendername (Firma, Person)\n"
        "- category: Kategorie (z.B. \"Bank & Finanzen\", \"Fahrzeug & Werkstatt\", \"Wohnen & Eigentum\")\n"
        "- document_type: Dokumenttyp (z.B. \"Rechnung\", \"Kontoauszug\", \"Vertrag\")\n"
        "- year: Jahr als String (z.B. \"2024\")\n"
        "- keywords: Stichwort das im Dokument vorkommen soll\n\n"
        "Gib NUR ein JSON-Objekt zurück, nur mit den Feldern die in der Frage erkennbar sind.\n"
        "Beispiel: {\"sender\": \"Autohaus Hohlweck\", \"year\": \"2025\", \"document_type\": \"Rechnung\"}\n"
        "Wenn keine Filter erkennbar sind: {}"
    )
    try:
        raw = llm_completion(system_prompt, question, max_tokens=200, temperature=0.1)
        if not raw:
            return {}
        # Try to find the first syntactically valid JSON object in the output.
        for match in re.finditer(r'\{.*?\}', raw, re.DOTALL):
            try:
                filters = json.loads(match.group())
                # Safeguard: Discard few-shot example copying hallucination
                if "hohlweck" in str(filters).lower() and "hohlweck" not in question.lower():
                    return {}
                return filters
            except json.JSONDecodeError:
                continue
    except Exception as e:
        log(f"[Chat] Filter-Extraktion fehlgeschlagen: {e}")
    return {}


def _build_context(docs: list[dict]) -> str:
    parts = []
    for i, doc in enumerate(docs[:8], 1):
        full = doc.get("full_text", "").strip()
        content = full[:800] if full else doc.get("summary", "–")
        parts.append(
            f"[{i}] {doc.get('filename', '?')} | {doc.get('sender', '–')} | "
            f"{doc.get('date', '–')} | {doc.get('document_type', '–')}\n{content}"
        )
    return "\n\n".join(parts)


def _generate_answer(question: str, docs: list[dict]) -> str:
    if not docs:
        # ── Allgemeines Konversations-Routing (Allgemeines Wissen Fallback) ──────
        system_prompt = (
            "Du bist ein hilfsbereiter KI-Assistent. Beantworte die Frage des Nutzers auf Deutsch, "
            "präzise, freundlich und in maximal 3-4 Sätzen."
        )
        try:
            raw = llm_completion(system_prompt, question, max_tokens=300, temperature=0.5)
            if raw:
                return raw
            return "Ich habe keine passenden Dokumente in deinem Archiv gefunden."
        except Exception as e:
            log(f"[Chat] Allgemeines Fallback-Loading fehlgeschlagen: {e}")
            return "Ich habe keine passenden Dokumente in deinem Archiv gefunden."

    system_prompt = (
        "Du bist ein Assistent der Dokumentenverwaltung PaperVault.\n"
        "Beantworte die Frage des Nutzers basierend auf den gefundenen Dokumenten.\n"
        "Antworte auf Deutsch, präzise und hilfreich. Maximal 3 Sätze.\n"
        "Wenn keine Dokumente gefunden wurden, sage das klar.\n\n"
        f"Gefundene Dokumente ({len(docs)} Treffer):\n" + _build_context(docs)
    )
    try:
        raw = llm_completion(system_prompt, question, max_tokens=300, temperature=0.3)
        if raw:
            return raw
        return f"Ich habe {len(docs)} Dokument(e) gefunden, konnte aber keine Antwort generieren."
    except Exception as e:
        log(f"[Chat] Antwort-Generierung fehlgeschlagen: {e}")
        return f"Ich habe {len(docs)} Dokument(e) gefunden, konnte aber keine Antwort generieren."


@router.post("/", response_model=ChatResponse)
def chat(req: ChatRequest):
    log(f"[Chat] Frage: {req.question}")

    llm = get_llm()
    if llm is None:
        log("[Chat] LLM nicht verfügbar.")
        raise HTTPException(status_code=503, detail="KI-Modell ist nicht geladen oder nicht konfiguriert.")

    # 1. Try semantic vector search (RAG)
    semantic_docs = []
    try:
        from llm.driver import generate_embedding
        q_emb = generate_embedding(req.question)
        semantic_docs = db.find_similar_documents(q_emb, limit=8)
        if semantic_docs:
            log(f"[Chat] Semantische Suche erfolgreich: {len(semantic_docs)} Dokumente gefunden.")
    except Exception as se:
        log(f"[Chat] Fehler bei semantischer Suche (ignoriert): {se}")

    # 2. Extract filters and run traditional search
    filters = _extract_filters(req.question)
    log(f"[Chat] Extrahierte Filter: {filters}")

    docs = db.search_documents(
        query=filters.get("keywords"),
        sender=filters.get("sender"),
        category=filters.get("category"),
        year=filters.get("year"),
        status="ok",
        limit=20,
    )

    if not docs and filters:
        docs = db.search_documents(query=req.question, status="ok", limit=20)

    # 3. Merge results (Hybrid Retrieval: semantic first, then unique traditional matches)
    seen_ids = set()
    merged_docs = []
    for d in semantic_docs:
        if d["id"] not in seen_ids:
            seen_ids.add(d["id"])
            merged_docs.append(d)
    for d in docs:
        if d["id"] not in seen_ids:
            seen_ids.add(d["id"])
            merged_docs.append(d)
    docs = merged_docs

    answer = _generate_answer(req.question, docs)
    log(f"[Chat] {len(docs)} Dokumente insgesamt gefunden, Antwort generiert.")

    safe_docs = [
        {k: v for k, v in d.items() if k != "full_text"}
        for d in docs[:8]
    ]

    return ChatResponse(answer=answer, filters=filters, documents=safe_docs)
