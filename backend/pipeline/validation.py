import re
from datetime import datetime

from config import CATEGORIES, DOCUMENT_TYPES, OWNER_NAMES
from utils import extract_year, normalize_umlauts

def _looks_like_ocr_garbage(text: str) -> bool:
    """Return True if the string contains too many OCR-typical artifacts to be a valid sender name.
    Heuristic: >25% of chars are digits/uppercase-only-noise or non-latin characters after stripping
    common German chars, OR the string contains typical OCR substitution patterns."""
    if not text or len(text) < 2:
        return False
    # OCR artifact patterns: mixed-case garbage, runs of uppercase with digits
    ocr_patterns = [
        r'[A-Z]{2,}[0-9][A-Z]{2,}',   # e.g. "UMPNU", "airektJperviceW"
        r'[a-z][A-Z][a-z][A-Z]',        # alternating case: e.g. "jüncÜen"
        r'\b[A-Z][a-z]+[A-Z][a-z]+\b',  # CamelCase garbage: "mostfacÜ"
    ]
    for pat in ocr_patterns:
        if re.search(pat, text):
            return True
    # High ratio of uppercase consonant clusters (OCR noise)
    upper_consonants = re.findall(r'[BCDFGHJKLMNPQRSTVWXYZ]{3,}', text)
    if upper_consonants and sum(len(c) for c in upper_consonants) > len(text) * 0.3:
        return True
    return False

def check_sender_semantic(predicted_sender, raw_text):
    """Verify if the predicted sender (or its base word) actually exists inside the raw text.
    Matching is case-insensitive and umlaut-normalized.
    Excludes very generic placeholder words."""
    if not predicted_sender or predicted_sender.lower() in ("null", "unbekannt", "n/a", "???", ""):
        return False

    sender_norm = normalize_umlauts(predicted_sender)
    text_norm = normalize_umlauts(raw_text)

    # 1. Direct substring match
    if sender_norm in text_norm:
        return True

    # 2. Check if first two meaningful words (>=3 chars) are in the text
    # (e.g. "CinemaXX Entertainment" -> "cinemaxx" or "entertainment")
    words = [w for w in re.split(r'\W+', sender_norm) if len(w) >= 3]
    if words:
        if any(w in text_norm for w in words[:2]):
            return True

    return False

def validate_classification(data):
    errors = []
    current_year = datetime.now().year

    # Check 0: control characters in string fields (should have been sanitized, but guard anyway)
    for _field in ("sender", "summary", "keywords"):
        _val = str(data.get(_field) or "")
        if any(c in _val for c in ('\n', '\r', '\t')):
            errors.append(f"'{_field}' enthaelt ungueltige Steuerzeichen (Newline/Tab) – mehrzeiliger LLM-Output.")

    # Check 1 & 8: date plausibility
    raw_date = str(data.get("date") or "")
    if raw_date and raw_date.lower() != "null":
        year_str = extract_year(raw_date)
        if year_str:
            year = int(year_str)
            if year < 1950 or year > current_year:
                errors.append(f"'date' enthaelt Jahr {year}, erwartet 1950–{current_year}. Das aktuelle Jahr ist {current_year}.")
        else:
            errors.append(f"'date' ist kein erkennbares Datum: '{raw_date}'. Verwende Format YYYY-MM-DD oder YYYY.")

    # Check 2: category in allowed list
    if data.get("category") not in CATEGORIES:
        errors.append(f"'category' '{data.get('category')}' ist nicht erlaubt. Waehle aus: {', '.join(CATEGORIES)}")

    # Check 3 & 7: sender not empty or placeholder
    sender = str(data.get("sender") or "").strip()
    sender_is_null = data.get("sender") is None
    _sender_placeholders = ("null", "unbekannt", "unknown", "n/a", "???", "absender", "keine angabe", "nicht definiert", "nicht angegeben", "")
    if not sender_is_null and sender.lower() in _sender_placeholders:
        # Normalize to null instead of erroring — sender genuinely unknown is valid
        data["sender"] = None
        sender_is_null = True
    elif not sender_is_null and len(sender) < 2:
        errors.append(f"'sender' ist zu kurz ('{sender}') – Einzelbuchstaben oder Sonderzeichen sind kein gueltiger Absender. Bitte den vollstaendigen Namen angeben oder null setzen.")

    # Check 4: sender is not the archive owner
    elif not sender_is_null and any(owner in sender.lower() for owner in OWNER_NAMES):
        errors.append(f"'sender' ist '{sender}' – das ist der Empfaenger (Archivinhaber), nicht der Absender. Bitte die ausstellende Firma oder Behoerde angeben.")

    # Check 5 & 13: summary not empty or uncertainty phrase
    summary = str(data.get("summary") or "").strip()
    uncertainty = ["ich weiss nicht", "unklar", "keine information", "kann nicht", "nicht erkennbar"]
    if len(summary) < 10:
        errors.append(f"'summary' ist zu kurz oder leer: '{summary}'. Bitte einen vollstaendigen Satz schreiben.")
    elif any(u in summary.lower() for u in uncertainty):
        errors.append(f"'summary' drueckt Unsicherheit aus: '{summary}'. Bitte den Inhalt des Dokuments beschreiben, auch wenn er vage ist.")

    # Check 6: document_type in allowed list
    if data.get("document_type") not in DOCUMENT_TYPES:
        errors.append(f"'document_type' '{data.get('document_type')}' ist nicht erlaubt. Waehle aus: {', '.join(DOCUMENT_TYPES)}")

    # Check 10: sender same as summary
    if sender and summary and sender.lower() == summary.lower():
        errors.append("'sender' und 'summary' sind identisch – die Felder wurden verwechselt.")

    # Check 11: sender is a document type name
    if not sender_is_null and sender in DOCUMENT_TYPES:
        errors.append(f"'sender' ist '{sender}' – das ist ein Dokumenttyp, kein Absendername. Bitte die ausstellende Firma angeben.")

    # Check 12: sender is a generic category/domain word
    _GENERIC_SENDER_WORDS = {
        "versicherung", "wohnung", "bank", "finanzen", "energie", "strom", "gas",
        "wasser", "rechnung", "abrechnung", "sonstiges", "unbekannt", "dokument",
        "brief", "schreiben", "mitteilung", "information", "anfrage", "angebot",
        "vertrag", "behörde", "behoerde", "amt", "verwaltung",
    }
    if not sender_is_null and sender.lower().strip() in _GENERIC_SENDER_WORDS:
        errors.append(f"'sender' ist '{sender}' – das ist ein generischer Begriff, kein konkreter Absendername. Bitte die spezifische Firma oder Behörde angeben.")

    # Check 13: sender is a stopword or single conjunction
    _STOPWORDS = {"und", "der", "die", "das", "von", "bei", "für", "mit", "an", "am", "im", "zu", "zur", "zum"}
    if not sender_is_null and sender.lower().strip() in _STOPWORDS:
        errors.append(f"'sender' ist '{sender}' – das ist kein gültiger Absendername.")

    # Check 14: sender is only an abbreviation/legal suffix
    if not sender_is_null and re.match(r'^(DE|AG|GmbH|UG|KG|eV|e\.V\.|Inc|Ltd|Corp|LLC)$', sender.strip(), re.IGNORECASE):
        errors.append(f"'sender' ist nur ein Kürzel oder Rechtsform: '{sender}'. Bitte den vollständigen Firmennamen angeben.")

    # Check 15: property_unit validation
    pu = data.get("property_unit")
    if pu is not None and pu not in ("Gesamthaus", "Eigene_Wohnung", "Wohnung_1", "Wohnung_2"):
        errors.append(f"'property_unit' '{pu}' ist nicht erlaubt. Waehle aus: Gesamthaus, Eigene_Wohnung, Wohnung_1, Wohnung_2")

    return errors
