import json

from llm.driver import get_llm, _llm_lock
from utils import log

def extract_services_from_invoice(text: str, filename: str = "", vendor: str = "", invoice_date: str = "") -> list[dict]:
    """Extract service/expense entries from a non-goods invoice (handcraft, travel, medical, etc.).
    Returns a list of service dicts or empty list on failure.
    Call for document_type 'Dienstleistungsrechnung'."""
    safe_text = text[:3000]

    SERVICE_CATEGORIES = [
        "Handwerk & Reparatur", "Reise & Urlaub", "Arzt & Gesundheit",
        "Versicherung", "Telekommunikation", "Energie & Wasser",
        "Steuer & Behörden", "Bildung & Weiterbildung", "Reinigung & Pflege",
        "Transport & Mobilität", "Gastronomie & Catering",
        "Beratung & Dienstleistung", "Sonstiges",
    ]

    # ── Polymorphisches Inferenz-Routing (Mikro-Experten-Weiche) ─────────────────
    text_lower = text.lower()
    specialized_expert_instructions = ""

    # 1. Handwerker / Reparaturrechnung (Lohn- vs. Materialkosten nach § 35a EStG)
    if any(w in text_lower for w in ("handwerker", "lohnkosten", "arbeitskosten", "fahrkosten", "stundenlohn", "instandsetzung", "reparatur", "montage")):
        specialized_expert_instructions = (
            "\n\n!!! SPEZIALISIERTE ANWEISUNG FÜR HANDWERKERRECHNUNG !!!\n"
            "Dies ist eine Reparatur- oder Handwerkerrechnung. Trenne unbedingt die Lohnkosten (Arbeitskosten, Fahrtkosten, "
            "Maschinenmiete nach § 35a EStG) von den reinen Materialkosten/Ersatzteilen ab. Erzeuge im JSON-Array getrennte Objekte:\n"
            "  - Eines für 'Handwerker-Lohnkosten (§ 35a EStG)' mit dem genauen Lohnkostenbetrag (netto oder brutto).\n"
            "  - Eines für 'Materialkosten' mit dem verbleibenden Betrag.\n"
            "Das erleichtert die steuerliche Geltendmachung der Lohnkosten nach § 35a EStG enorm!"
        )
    # 2. Energierechnung / Nebenkosten (Verbräuche, Abschläge, Zählerstände)
    elif any(w in text_lower for w in ("strom", "erdgas", "heizung", "wasserzähler", "abschlag", "kwh", "m³", "zaehlerstand")):
        specialized_expert_instructions = (
            "\n\n!!! SPEZIALISIERTE ANWEISUNG FÜR ENERGIE-/NEBENKOSTEN !!!\n"
            "Dies ist eine Energie-, Wasser- oder Nebenkostenrechnung. Extrahiere neben den reinen Kosten auch wichtige "
            "Verbrauchsdaten in das 'notes'-Feld des jeweiligen Eintrags, zum Beispiel:\n"
            "  - Jahresverbrauch in kWh oder m³,\n"
            "  - Zählerstände,\n"
            "  - Neue monatliche Abschlagszahlungen für das nächste Jahr.\n"
            "Schreibe diese Werte verständlich in das 'notes'-Feld des jeweiligen Eintrags."
        )
    # 3. Telekommunikationsrechnung (Grundgebühr vs. Variable Kosten)
    elif any(w in text_lower for w in ("mobilfunk", "dsl", "festnetz", "grundgebühr", "telekom", "vodafone", "o2")):
        specialized_expert_instructions = (
            "\n\n!!! SPEZIALISIERTE ANWEISUNG FÜR TELEKOMMUNIKATION !!!\n"
            "Dies ist eine Telekommunikations- oder Handyrechnung. Trenne im JSON-Array möglichst:\n"
            "  - Die feste monatliche 'Grundgebühr' für den Tarif.\n"
            "  - Eventuelle 'Variable Verbindungskosten / Einmalentgelte' (Drittanbieter, Roaming, Extrakäufe).\n"
            "Das hilft, Kostentreiber im Vertrag sofort sichtbar zu machen."
        )

    system = (
        "Du bist ein Assistent der Dienstleistungen und Ausgaben aus Rechnungen extrahiert. "
        "Antworte IMMER NUR mit einem JSON-Array. Kein Markdown, keine Erklärungen."
    )
    user = (
        f"Extrahiere alle Dienstleistungen/Ausgaben aus dieser Rechnung als JSON-Array.\n"
        f"Anbieter: {vendor or 'unbekannt'}, Datum: {invoice_date or 'unbekannt'}\n\n"
        f"Jedes Objekt hat folgende Felder (alle optional außer 'name'):\n"
        f"  name (string, Bezeichnung der Leistung), "
        f"description (string, Details), "
        f"provider (string, Dienstleister/Anbieter), "
        f"service_date (string YYYY-MM-DD), "
        f"amount (number, Betrag in EUR), "
        f"currency (string, Default 'EUR'), "
        f"category (eines von: {', '.join(SERVICE_CATEGORIES)}), "
        f"notes (string),\n"
        f"  source_text (string, das exakte, wörtliche Textzitat aus der Rechnung, das die Erbringung dieser Dienstleistung und ihren Betrag belegt),\n"
        f"  source_page (integer, die 1-basierte Seitenzahl, auf der die Information gefunden wurde, z.B. 1 oder null)\n\n"
        f"Regeln:\n"
        f"- NUR Dienstleistungen erfassen, KEINE physischen Artikel oder Produkte\n"
        f"- Wenn es sich um eine Warenrechnung handelt (Elektronik, Möbel, etc.): leeres Array [] zurückgeben\n"
        f"- Gesamtbetrag als 'amount', Preise ohne Währungssymbol\n"
        f"- source_text MUSS ein exaktes, wortwörtliches Zitat aus dem Dokumenten-Text sein.\n"
        f"- Maximal 10 Einträge\n"
        f"{specialized_expert_instructions}\n\n"
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
                max_tokens=512,
                temperature=0.0,
            )
        raw = result["choices"][0]["message"]["content"]
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        start = cleaned.find("[")
        if start > 0:
            cleaned = cleaned[start:]
        services = json.loads(cleaned)
        if not isinstance(services, list):
            return []
        valid = []
        for s in services:
            if not isinstance(s, dict) or not s.get("name"):
                continue
            val = s.get("amount")
            if val is not None:
                try:
                    s["amount"] = float(str(val).replace(",", ".").replace(" ", ""))
                except (ValueError, TypeError):
                    s["amount"] = None
            # Fill invoice-level metadata if the model didn't provide it
            if not s.get("provider"):
                s["provider"] = vendor or None
            if not s.get("service_date"):
                s["service_date"] = invoice_date or None
            valid.append(s)
        log(f"[SERVICES] {len(valid)} Dienstleistungen extrahiert aus '{filename}'")
        return valid
    except Exception as e:
        log(f"[SERVICES] Extraktion fehlgeschlagen fuer '{filename}': {e}")
        return []
