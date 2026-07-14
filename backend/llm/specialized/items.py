import json
from datetime import datetime

from llm.driver import get_llm, _llm_lock
from utils import log

def extract_items_from_invoice(text: str, filename: str = "", vendor: str = "", purchase_date: str = "") -> list[dict]:
    """Extract line items from an invoice using the LLM.
    Returns a list of item dicts or empty list on failure.
    Call for document_type 'Warenrechnung'."""
    safe_text = text[:3000]

    ITEM_CATEGORIES = [
        "Elektronik & IT", "Haushaltsgeräte", "Möbel & Einrichtung",
        "Werkzeug & Heimwerken", "Garten & Außen", "Fahrzeug & KFZ",
        "Kleidung & Schuhe", "Sport & Freizeit", "Lebensmittel",
        "Gesundheit & Pflege", "Büro & Schreibwaren", "Sonstiges",
    ]

    system = (
        "Du bist ein Assistent der Artikel aus Rechnungen extrahiert. "
        "Antworte IMMER NUR mit einem JSON-Array. Kein Markdown, keine Erklärungen."
    )
    user = (
        f"Extrahiere alle Artikel aus dieser Rechnung als JSON-Array.\n"
        f"Händler: {vendor or 'unbekannt'}, Datum: {purchase_date or 'unbekannt'}\n\n"
        f"Jedes Objekt im Array hat folgende Felder (alle optional außer 'name'):\n"
        f"  name (string), description (string), quantity (number), "
        f"unit_price (number, EUR), total_price (number, EUR), "
        f"warranty_until (string YYYY-MM-DD oder null), "
        f"category (eines von: {', '.join(ITEM_CATEGORIES)}), "
        f"vendor (string), purchase_date (string YYYY-MM-DD)\n\n"
        f"Regeln:\n"
        f"- Nur echte Artikel/Produkte extrahieren, keine Versand-, Rabatt- oder MwSt-Zeilen\n"
        f"- Preise als reine Zahlen ohne Währungssymbol\n"
        f"- Garantie: Suche nach Angaben wie 'Garantie bis', 'Garantie: 24 Monate', 'Herstellergarantie'. "
        f"Wenn eine Garantiedauer erkennbar ist, rechne das Enddatum aus dem Kaufdatum. "
        f"Gib `warranty_until` immer als YYYY-MM-DD an (z. B. 2026-05-31), sonst null.\n"
        f"- Maximal 30 Artikel\n\n"
        f"--- RECHNUNGSTEXT ---\n{safe_text}"
    )

    try:
        _llm_instance = get_llm()
        with _llm_lock:
            result = _llm_instance.create_chat_completion(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=1024,
                temperature=0.0,
            )
        raw = result["choices"][0]["message"]["content"]
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        # Strip any leading text before the array
        start = cleaned.find("[")
        if start > 0:
            cleaned = cleaned[start:]
        items = json.loads(cleaned)
        if not isinstance(items, list):
            return []
        valid = []
        for item in items:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            # Normalize numeric fields
            for field in ("quantity", "unit_price", "total_price"):
                val = item.get(field)
                if val is not None:
                    try:
                        item[field] = float(str(val).replace(",", ".").replace(" ", ""))
                    except (ValueError, TypeError):
                        item[field] = None
            # Normalize warranty date if present
            warranty = item.get("warranty_until")
            if warranty:
                parsed = None
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"):
                    try:
                        parsed = datetime.strptime(str(warranty).strip(), fmt).strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        pass
                item["warranty_until"] = parsed
            # Fill invoice-level metadata if the model didn't provide it
            if not item.get("vendor"):
                item["vendor"] = vendor or None
            if not item.get("purchase_date"):
                item["purchase_date"] = purchase_date or None
            valid.append(item)
        log(f"[ITEMS] {len(valid)} Artikel extrahiert aus '{filename}'")
        return valid
    except Exception as e:
        log(f"[ITEMS] Extraktion fehlgeschlagen fuer '{filename}': {e}")
        return []
