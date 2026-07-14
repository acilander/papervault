import json

from llm.driver import get_llm, _llm_lock
from utils import log

def extract_contract_from_document(text: str, filename: str = "", sender: str = "", doc_type: str = "") -> dict | None:
    """Extract contract/subscription details from a document using the LLM.
    Returns a dict or None on failure.
    Only call for document_type in ('Vertrag', 'Kündigung', 'Mahnung', 'Abonnement')."""
    safe_text = text[:3000]

    CONTRACT_CATEGORIES = [
        "Versicherung", "Telekommunikation", "Energie & Wasser", "Streaming & Medien",
        "Mitgliedschaft & Verein", "Software & Lizenz", "Finanzdienstleistung",
        "Mietvertrag", "Arbeitsvertrag", "Wartung & Service", "Sonstiges",
    ]
    INTERVALS = ["monatlich", "vierteljährlich", "halbjährlich", "jährlich", "einmalig"]
    STATUSES = ["aktiv", "gekündigt", "ausgelaufen", "pausiert", "unbekannt"]

    system = (
        "Du bist ein Assistent der Vertragsdaten aus Dokumenten extrahiert. "
        "Antworte IMMER NUR mit einem einzigen JSON-Objekt. Kein Markdown, keine Erklärungen."
    )
    user = (
        f"Extrahiere die Vertragsdaten aus diesem Dokument als JSON-Objekt.\n"
        f"Vertragspartner/Absender: {sender or 'unbekannt'}, Dokumenttyp: {doc_type or 'unbekannt'}\n\n"
        f"Das JSON-Objekt hat folgende Felder (alle optional außer 'partner'):\n"
        f"  partner (string, Vertragspartner/Unternehmen),\n"
        f"  description (string, kurze Beschreibung des Vertrags/Abos),\n"
        f"  category (eines von: {', '.join(CONTRACT_CATEGORIES)}),\n"
        f"  status (eines von: {', '.join(STATUSES)}),\n"
        f"  amount (number, Betrag in EUR ohne Symbol),\n"
        f"  amount_interval (eines von: {', '.join(INTERVALS)}),\n"
        f"  start_date (string YYYY-MM-DD oder null),\n"
        f"  end_date (string YYYY-MM-DD oder null),\n"
        f"  next_due_date (string YYYY-MM-DD oder null),\n"
        f"  cancellation_deadline (string YYYY-MM-DD, Datum bis wann gekündigt werden muss, oder null),\n"
        f"  notice_period_days (integer, Kündigungsfrist in Tagen, oder null),\n"
        f"  auto_renews (boolean, verlängert sich automatisch),\n"
        f"  notes (string, zusätzliche wichtige Hinweise, oder null)\n\n"
        f"Regeln:\n"
        f"- Bei Kündigung: status='gekündigt', end_date=Datum der Kündigung/Ablauf\n"
        f"- Wenn Datum nicht erkennbar: null\n"
        f"- Betrag als reine Zahl ohne Währungssymbol\n\n"
        f"--- DOKUMENTTEXT ---\n{safe_text}"
    )

    try:
        _llm_instance = get_llm()
        with _llm_lock:
            result = _llm_instance.create_chat_completion(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=512,
                temperature=0.0,
            )
        raw = result["choices"][0]["message"]["content"]
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        start = cleaned.find("{")
        if start > 0:
            cleaned = cleaned[start:]
        end = cleaned.rfind("}")
        if end >= 0:
            cleaned = cleaned[:end + 1]
        contract = json.loads(cleaned)
        if not isinstance(contract, dict) or not contract.get("partner"):
            return None
        # Normalize amount
        val = contract.get("amount")
        if val is not None:
            try:
                contract["amount"] = float(str(val).replace(",", ".").replace(" ", ""))
            except (ValueError, TypeError):
                contract["amount"] = None
        # Normalize booleans
        if "auto_renews" in contract:
            contract["auto_renews"] = bool(contract["auto_renews"])
        log(f"[CONTRACTS] Vertrag extrahiert: '{contract.get('partner')}' ({contract.get('category')}) aus '{filename}'")
        return contract
    except Exception as e:
        log(f"[CONTRACTS] Extraktion fehlgeschlagen fuer '{filename}': {e}")
        return None
