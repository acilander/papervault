import json
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import db
from llm import get_llm
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
    llm = get_llm()
    prompt = FILTER_PROMPT.format(question=question)
    try:
        output = llm(prompt, max_tokens=200, temperature=0.1, stop=["\n\n"])
        raw = output["choices"][0]["text"].strip()
        # Try to find the first syntactically valid JSON object in the output.
        for match in re.finditer(r'\{.*?\}', raw, re.DOTALL):
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
    except Exception as e:
        log(f"[Chat] Filter-Extraktion fehlgeschlagen: {e}")
    return {}


def _build_context(docs: list[dict]) -> str:
    parts = []
    for i, doc in enumerate(docs[:8], 1):
        full = doc.get("full_text", "").strip()
        content = full[:400] if full else doc.get("summary", "–")
        parts.append(
            f"[{i}] {doc.get('filename', '?')} | {doc.get('sender', '–')} | "
            f"{doc.get('date', '–')} | {doc.get('document_type', '–')}\n{content}"
        )
    return "\n\n".join(parts)


def _generate_answer(question: str, docs: list[dict]) -> str:
    if not docs:
        return "Ich habe keine passenden Dokumente in deinem Archiv gefunden."
    llm = get_llm()
    context = _build_context(docs)
    prompt = ANSWER_PROMPT.format(question=question, count=len(docs), context=context)
    try:
        output = llm(prompt, max_tokens=300, temperature=0.3, stop=["\n\n\n"])
        return output["choices"][0]["text"].strip()
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

    answer = _generate_answer(req.question, docs)
    log(f"[Chat] {len(docs)} Dokumente gefunden, Antwort generiert.")

    safe_docs = [
        {k: v for k, v in d.items() if k != "full_text"}
        for d in docs[:8]
    ]

    return ChatResponse(answer=answer, filters=filters, documents=safe_docs)
