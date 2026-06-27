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
        _llm = Llama(model_path=MODEL_PATH, n_ctx=2048, n_threads=6, verbose=False, chat_format="chatml")
        log(f"Modell geladen in {time.time()-t0:.1f}s")


def normalize_sender(sender):
    """Match sender against known senders in registry using fuzzy matching."""
    if not sender or not storage.sender_registry:
        return sender
    known = list(storage.sender_registry.keys())
    for k in known:
        if k.lower() == sender.lower():
            return k
    matches = get_close_matches(sender, known, n=1, cutoff=0.82)
    if matches:
        log(f"Absender normalisiert: '{sender}' -> '{matches[0]}'")
        return matches[0]
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


def classify_document(safe_text, filename=None):
    load_model()
    system_prompt = SYSTEM_PROMPT.replace("{current_year}", str(datetime.now().year))

    if storage.sender_registry:
        known_list = ", ".join(sorted(storage.sender_registry.keys())[:60])
        sender_hint = f"\n\nBekannte Absender aus dem Archiv (bevorzuge diese Schreibweise wenn passend): {known_list}"
    else:
        sender_hint = ""

    if filename:
        clean_name = os.path.splitext(filename)[0]
        clean_name = re.sub(r'^\d{8}_', '', clean_name)
        filename_hint = f"\n\nDateiname des Dokuments (kann zusaetzliche Hinweise auf Absender/Typ enthalten): {clean_name}"
    else:
        filename_hint = ""

    few_shot_hint = fb.build_few_shot_prompt(n=15)

    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Klassifiziere dieses Dokument:{sender_hint}{filename_hint}{few_shot_hint}\n\n{safe_text}"},
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
            result = _llm.create_chat_completion(messages=current_messages, max_tokens=200)
            raw = result["choices"][0]["message"]["content"]

            cleaned = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)

            known_fields = {"sender", "date", "document_type", "category", "summary"}
            data = {k: v for k, v in data.items() if k in known_fields}

            if data.get("sender"):
                data["sender"] = normalize_sender(data["sender"])

            errors = validate_classification(data)
            if not errors:
                log(f"LLM OK in {time.time()-t0:.1f}s: {data}")
                return data

            owner_error = any("Empfaenger" in e for e in errors)
            if attempt == MAX_RETRIES and owner_error and len(errors) == 1:
                data["sender"] = None
                log("Letzter Versuch: Absender nicht erkennbar, setze auf null. Akzeptiere restliche Klassifizierung.")
                return data

            feedback = "; ".join(errors)
            log(f"Plausibilitaetsfehler (Versuch {attempt}): {feedback}")

        except json.JSONDecodeError:
            log(f"LLM antwortete kein valides JSON (Versuch {attempt}), wiederhole...")
            feedback = None
        except Exception as e:
            log(f"LLM Fehler nach {time.time()-t0:.1f}s (Versuch {attempt}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2)

    return None
