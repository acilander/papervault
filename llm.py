import json
import os
import re
import time
from datetime import datetime
from difflib import get_close_matches

from llama_cpp import Llama

from config import (
    MODEL_PATH, MAX_RETRIES, CATEGORIES, DOCUMENT_TYPES,
    OWNER_NAMES, TYPE_CATEGORY_MAP, SYSTEM_PROMPT,
)
import storage
import feedback as fb

_llm = None


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_model():
    global _llm
    if _llm is None:
        log("Lade LLM-Modell (einmalig)...")
        t0 = time.time()
        _llm = Llama(model_path=MODEL_PATH, n_ctx=4096, n_threads=6, verbose=False, chat_format="chatml")
        log(f"Modell geladen in {time.time()-t0:.1f}s")


def normalize_sender(sender):
    """Match sender against known senders (and their aliases) using exact + fuzzy matching.
    Always returns the canonical registry key name."""
    if not sender or not storage.sender_registry:
        return sender
    known = list(storage.sender_registry.keys())
    # 1. Exact match on canonical name
    for k in known:
        if k.lower() == sender.lower():
            return k
    # 2. Exact match on any alias → return canonical name
    for k, entry in storage.sender_registry.items():
        for alias in entry.get("aliases") or []:
            if alias.lower() == sender.lower():
                log(f"Absender via Alias erkannt: '{sender}' -> '{k}'")
                return k
    # 3. Fuzzy match on canonical names
    matches = get_close_matches(sender, known, n=1, cutoff=0.82)
    if matches:
        log(f"Absender normalisiert: '{sender}' -> '{matches[0]}'")
        return matches[0]
    # 4. Fuzzy match on aliases
    all_aliases = {alias: k for k, entry in storage.sender_registry.items()
                   for alias in (entry.get("aliases") or [])}
    alias_matches = get_close_matches(sender, list(all_aliases.keys()), n=1, cutoff=0.82)
    if alias_matches:
        canonical = all_aliases[alias_matches[0]]
        log(f"Absender via Alias-Fuzzy erkannt: '{sender}' -> '{canonical}'")
        return canonical
    return sender


def validate_classification(data):
    errors = []
    current_year = datetime.now().year

    # Check 1 & 8: date plausibility
    raw_date = str(data.get("date") or "")
    if raw_date and raw_date.lower() != "null":
        year_match = re.search(r'\b(\d{4})\b', raw_date)
        if year_match:
            year = int(year_match.group())
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
    if not sender_is_null and (not sender or sender.lower() in ("null", "unbekannt", "n/a", "???", "absender", "")):
        errors.append(f"'sender' ist leer oder ein Platzhalter ('{sender}'). Bitte den Namen der ausstellenden Organisation angeben.")

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

    # Check 9: type/category consistency
    doc_type = data.get("document_type")
    expected_cat = TYPE_CATEGORY_MAP.get(doc_type)
    if expected_cat and data.get("category") != expected_cat:
        errors.append(f"'document_type' '{doc_type}' erfordert 'category' '{expected_cat}', aber '{data.get('category')}' wurde gewaehlt.")

    # Check 10: sender same as summary
    if sender and summary and sender.lower() == summary.lower():
        errors.append("'sender' und 'summary' sind identisch – die Felder wurden verwechselt.")

    return errors


def filter_keywords_against_text(keywords_str: str, source_text: str) -> str:
    """
    Remove keywords that do not appear in the source text (hallucinations).
    Matching is case-insensitive and umlaut-normalized.
    Single-char tokens and generic placeholder words are always removed.
    Returns cleaned comma-separated string, or '' if nothing survives.
    """
    BLOCKLIST = {
        "ibans", "iban", "vertragsnummern", "produktnamen", "ortsangaben",
        "fachbegriffe", "betraege", "betrag", "dokument", "brief", "datum",
        "absender", "empfaenger", "rechnung", "sonstiges",
    }

    def _norm(s: str) -> str:
        return (s.lower()
                .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
                .replace("ß", "ss"))

    text_norm = _norm(source_text)
    kept = []
    for kw in keywords_str.split(","):
        kw = kw.strip()
        if not kw or len(kw) < 3:
            continue
        kw_norm = _norm(kw)
        if kw_norm in BLOCKLIST:
            continue
        # Accept if the keyword (or its first meaningful word ≥4 chars) is in text
        words = [w for w in kw_norm.split() if len(w) >= 4]
        if kw_norm in text_norm or any(w in text_norm for w in words):
            kept.append(kw)

    return ", ".join(kept)


def build_similar_docs_hint(text_snippet: str) -> str:
    """
    Look up similar documents from the DB to guide LLM classification.
    Strategy:
      1. Try to match known senders in the text → fetch last 3 docs of that sender
      2. If no sender match → skip (category fallback would need LLM-classified category first)
    Returns a formatted hint string or empty string.
    """
    try:
        import db as _db
        known_senders = list(storage.sender_registry.keys())
        matched_sender = None
        def _normalize(s: str) -> str:
            return (s.lower()
                    .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
                    .replace("ß", "ss"))

        text_lower = _normalize(text_snippet[:2000])
        # Longest match wins (avoids "ING" matching inside "ING-DiBa")
        for s in sorted(known_senders, key=len, reverse=True):
            if _normalize(s) in text_lower:
                matched_sender = s
                break

        lines = []
        if matched_sender:
            past = _db.search_documents(sender=matched_sender, status="ok", limit=3)
            if past:
                lines.append(f"\n\nBekannte Dokumente von '{matched_sender}' in deinem Archiv:")
                for d in past:
                    date_str = d.get("date") or "?"
                    lines.append(
                        f"  - {date_str}: Typ={d.get('document_type','?')}, "
                        f"Kategorie={d.get('category','?')}"
                        + (f", Zusammenfassung: {d['summary'][:80]}" if d.get("summary") else "")
                    )
                lines.append("→ Orientiere dich an dieser Klassifizierung wenn das aktuelle Dokument aehnlich ist.")
        else:
            # No sender match – try category hint from keyword patterns
            CATEGORY_KEYWORDS = {
                "Kommunikation":       ["mobilfunk", "handyrechnung", "datenvolumen", "tarif", "sim", "router", "internet flat", "telefon"],
                "Energie & Versorgung":["strom", "gas", "kwh", "abschlag", "jahresverbrauch", "netzbetreiber", "zaehlerstand"],
                "Bank & Finanzen":     ["kontoauszug", "iban", "bic", "buchung", "ueberweisung", "depot", "zinsen", "lastschrift"],
                "Versicherung":        ["versicherungsschein", "police", "praemie", "deckungssumme", "versicherungsnehmer", "beitrag"],
                "Gesundheit":          ["arzt", "krankenhaus", "rezept", "diagnose", "behandlung", "krankenkasse", "patient"],
                "KFZ":                 ["fahrzeugschein", "kfz", "fahrzeug", "hauptuntersuchung", "kennzeichen", "kraftstoff"],
                "Wohnen & Eigentum":   ["miete", "nebenkosten", "betriebskosten", "grundsteuer", "eigentuemer", "mietvertrag"],
                "Behoerde & Urkunden": ["bescheid", "finanzamt", "behoerde", "steuernummer", "personalausweis", "ummeldung"],
            }
            cat_scores: dict[str, int] = {}
            for cat, kws in CATEGORY_KEYWORDS.items():
                score = sum(1 for kw in kws if kw in text_lower)
                if score:
                    cat_scores[cat] = score
            if cat_scores:
                best_cat = max(cat_scores, key=lambda c: cat_scores[c])
                recent = _db.search_documents(category=best_cat, status="ok", limit=2)
                if recent:
                    lines.append(f"\n\nAehnliche Dokumente der Kategorie '{best_cat}' in deinem Archiv:")
                    for d in recent:
                        lines.append(
                            f"  - {d.get('sender','?')} ({d.get('date','?')}): "
                            f"Typ={d.get('document_type','?')}"
                            + (f", {d['summary'][:70]}" if d.get("summary") else "")
                        )
                    lines.append("→ Falls das aktuelle Dokument aehnlich ist, koennte dies die passende Kategorie sein.")

        return "\n".join(lines)
    except Exception:
        return ""


def classify_document(safe_text, filename=None, user_hint=None, feature_prompt=None, similar_docs=None):
    load_model()
    safe_text = safe_text[:3000]  # hard cap to stay within context window
    system_prompt = SYSTEM_PROMPT.replace("{current_year}", str(datetime.now().year))

    if storage.sender_registry:
        def _norm(s): return s.lower().replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")
        text_norm = _norm(safe_text)
        matching = [k for k in storage.sender_registry if _norm(k) in text_norm]
        if matching:
            sender_hint = f"\n\nHinweis: Folgender bekannter Absender wurde im Text gefunden – verwende genau diese Schreibweise: {', '.join(matching)}"
        else:
            sender_hint = ""
    else:
        sender_hint = ""

    if filename:
        clean_name = os.path.splitext(filename)[0]
        clean_name = re.sub(r'^\d{8}_', '', clean_name)
        filename_hint = f"\n\nDateiname des Dokuments (kann zusaetzliche Hinweise auf Absender/Typ enthalten): {clean_name}"
    else:
        filename_hint = ""

    few_shot_hint = fb.build_few_shot_prompt(n=15)

    hint_block = f"\n\nBenutzerhinweis (hohe Prioritaet): {user_hint}" if user_hint else ""

    feature_block = f"\n\n{feature_prompt}" if feature_prompt else ""

    if similar_docs:
        lines = ["\n\nStrukturell aehnliche Dokumente aus dem Archiv (als Referenz):"]
        for d in similar_docs:
            lines.append(
                f"  - Absender: {d.get('sender','?')} | Kategorie: {d.get('category','?')} "
                f"| Typ: {d.get('document_type','?')} | Datum: {d.get('date','?')}"
                + (f" | {d['summary'][:60]}" if d.get('summary') else "")
            )
        similar_block = "\n".join(lines)
    else:
        similar_block = build_similar_docs_hint(safe_text)

    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Klassifiziere dieses Dokument:{hint_block}{feature_block}{sender_hint}{filename_hint}{few_shot_hint}{similar_block}\n\n{safe_text}"},
    ]
    feedback = None

    for attempt in range(1, MAX_RETRIES + 1):
        if feedback:
            current_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": (
                    f"Fehler in vorheriger Antwort: {feedback}\n\n"
                    f"Bitte korrigiere und klassifiziere dieses Dokument erneut:\n\n{safe_text}"
                )},
            ]
        else:
            current_messages = base_messages

        log(f"LLM Klassifizierung, Versuch {attempt}/{MAX_RETRIES}...")
        t0 = time.time()
        try:
            result = _llm.create_chat_completion(messages=current_messages, max_tokens=300)
            raw = result["choices"][0]["message"]["content"]

            cleaned = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)

            known_fields = {"sender", "date", "document_type", "category", "summary", "keywords"}
            data = {k: v for k, v in data.items() if k in known_fields}

            if data.get("sender"):
                data["sender"] = normalize_sender(data["sender"])

            # Auto-fix invalid category via fuzzy match
            if data.get("category") not in CATEGORIES:
                close = get_close_matches(data["category"] or "", CATEGORIES, n=1, cutoff=0.4)
                if close:
                    log(f"Kategorie '{data['category']}' auto-korrigiert zu '{close[0]}'")
                    data["category"] = close[0]

            errors = validate_classification(data)
            if not errors:
                log(f"LLM OK in {time.time()-t0:.1f}s: {data}")
                return data

            owner_error = any("Empfaenger" in e for e in errors)
            if owner_error and len(errors) == 1:
                data["sender"] = None
                log("Absender ist Archivinhaber – setze sender=null und akzeptiere restliche Klassifizierung.")
                return data

            feedback = "; ".join(errors)
            log(f"Plausibilitaetsfehler (Versuch {attempt}): {feedback}")

        except json.JSONDecodeError:
            log(f"LLM antwortete kein valides JSON (Versuch {attempt}): {raw[:200]!r}")
            feedback = None
        except Exception as e:
            log(f"LLM Fehler nach {time.time()-t0:.1f}s (Versuch {attempt}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2)

    return None
