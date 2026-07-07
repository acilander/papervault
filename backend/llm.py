import json
import os
import re
import time
import threading
from datetime import datetime
from difflib import get_close_matches

from llama_cpp import Llama
import llama_cpp

import config as _config
from config import (
    MAX_RETRIES, CATEGORIES, DOCUMENT_TYPES,
    OWNER_NAMES, SYSTEM_PROMPT, N_GPU_LAYERS,
)
import storage
import feedback as fb
from utils import log, normalize_umlauts, extract_year

_llm_lock = threading.Lock()
_llm = None


def get_llm():
    """Return the loaded LLM instance (loads if necessary)."""
    load_model()
    return _llm


def assert_gpu_support():
    if N_GPU_LAYERS == 0:
        raise RuntimeError(
            f"GPU-Betrieb erzwungen, aber N_GPU_LAYERS=0 (CPU-only). "
            "Setze N_GPU_LAYERS=-1 in der .env-Datei."
        )
    if not llama_cpp.llama_supports_gpu_offload():
        raise RuntimeError(
            "GPU-Unterstuetzung fehlt: llama-cpp-python wurde ohne GPU-Backend kompiliert. "
            "Bitte mit CUDA-Index reinstallieren: "
            "pip install llama-cpp-python==0.3.32 --force-reinstall --no-cache-dir "
            "--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu132"
        )


def load_model():
    global _llm
    from config import MOCK_LLM
    if MOCK_LLM:
        return
    if _llm is None:
        assert_gpu_support()
        model_path = _config.MODEL_PATH
        model_name = os.path.basename(model_path)
        model_size = os.path.getsize(model_path) / (1024 ** 3) if os.path.exists(model_path) else 0
        log(f"Lade LLM-Modell: {model_name} ({model_size:.1f} GB)...")
        t0 = time.time()
        _llm = Llama(model_path=model_path, n_ctx=4096, n_threads=6, n_gpu_layers=N_GPU_LAYERS, verbose=False, chat_format="chatml")
        elapsed = time.time() - t0
        log(f"Modell geladen: {model_name} in {elapsed:.1f}s [GPU-Layer: {N_GPU_LAYERS}]")


def normalize_sender(sender):
    """Match sender against known senders (and their aliases) using exact + fuzzy matching.
    Always returns the canonical registry key name."""
    if not sender or not storage.sender_registry:
        return sender
    sender = re.sub(r'[\r\n\t]+', ' ', sender).strip()
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


def sanitize_llm_output(data: dict) -> dict:
    """Strip control characters (newlines, tabs) from all string fields.
    Must be called immediately after json.loads before any further processing."""
    STRING_FIELDS = ("sender", "date", "document_type", "category", "summary", "keywords", "confidence_reason", "iban")
    for field in STRING_FIELDS:
        val = data.get(field)
        if isinstance(val, str):
            val = re.sub(r'[\r\n\t]+', ' ', val)
            val = re.sub(r' {2,}', ' ', val).strip()
            data[field] = val if val else None
    # Nullify sender if it looks like OCR garbage
    sender = data.get("sender")
    if isinstance(sender, str) and _looks_like_ocr_garbage(sender):
        log(f"Absender sieht nach OCR-Artefakt aus – setze null: '{sender}'")
        data["sender"] = None
    # Normalize IBAN: strip spaces, uppercase, validate DE-IBAN format
    iban = data.get("iban")
    if isinstance(iban, str):
        iban_clean = re.sub(r'\s+', '', iban).upper()
        if re.match(r'^DE\d{20}$', iban_clean):
            data["iban"] = iban_clean
        else:
            data["iban"] = None
    return data


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

    return errors


def filter_keywords_against_text(keywords_str: str, source_text: str) -> str:
    """
    Remove keywords that do not appear in the source text (hallucinations).
    Matching is case-insensitive and umlaut-normalized. Also allows fuzzy matches
    so OCR-corrected keywords (e.g. 'Baden' when the text says 'Bodan') survive.
    Single-char tokens and generic placeholder words are always removed.
    Returns cleaned comma-separated string, or '' if nothing survives.
    """
    from difflib import get_close_matches

    BLOCKLIST = {
        "ibans", "iban", "vertragsnummern", "produktnamen", "ortsangaben",
        "fachbegriffe", "betraege", "betrag", "dokument", "brief", "datum",
        "absender", "empfaenger", "rechnung", "sonstiges",
    }

    text_norm = normalize_umlauts(source_text)
    text_words = text_norm.split()
    kept = []
    for kw in keywords_str.split(","):
        kw = kw.strip()
        if not kw or len(kw) < 3:
            continue
        kw_norm = normalize_umlauts(kw)
        if kw_norm in BLOCKLIST:
            continue
        # Accept if the keyword (or its meaningful words ≥4 chars) is in text
        # either exactly or via fuzzy match (catches OCR typos like Bodan -> Baden)
        words = [w for w in kw_norm.split() if len(w) >= 4]
        exact = kw_norm in text_norm or any(w in text_norm for w in words)
        fuzzy = any(get_close_matches(w, text_words, n=1, cutoff=0.85) for w in words)
        if exact or fuzzy:
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

        text_lower = normalize_umlauts(text_snippet[:2000])
        # Longest match wins (avoids "ING" matching inside "ING-DiBa")
        for s in sorted(known_senders, key=len, reverse=True):
            if normalize_umlauts(s) in text_lower:
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


def detect_known_sender(text):
    """Scan raw text for exact word-boundary matches of registered senders or their aliases.
    Returns (sender_name, pinned_category) if matched, else (None, None)."""
    text_norm = normalize_umlauts(text)
    # Sort senders by length descending to match longest first
    for sender, entry in sorted(storage.sender_registry.items(), key=lambda x: len(x[0]), reverse=True):
        sender_esc = re.escape(normalize_umlauts(sender))
        if re.search(r'\b' + sender_esc + r'\b', text_norm, re.IGNORECASE):
            return sender, entry.get("pinned_category")
        for alias in entry.get("aliases") or []:
            alias_esc = re.escape(normalize_umlauts(alias))
            if re.search(r'\b' + alias_esc + r'\b', text_norm, re.IGNORECASE):
                return sender, entry.get("pinned_category")
    return None, None


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


def _reconciliation_pass(data: dict, sender: str) -> dict:
    """Second LLM pass: check consistency of document_type and category against existing
    DB documents from the same sender. Only triggered when confidence != 'high' and
    the sender has ≥3 documents in the DB with a clear majority type/category.
    Returns updated data dict (may be unchanged)."""
    try:
        import db as _db
        from collections import Counter
        past = _db.search_documents(sender=sender, status="ok", limit=20)
        if len(past) < 3:
            return data

        type_counts = Counter(d.get("document_type") for d in past if d.get("document_type"))
        cat_counts = Counter(d.get("category") for d in past if d.get("category"))
        if not type_counts and not cat_counts:
            return data

        majority_type, majority_type_n = type_counts.most_common(1)[0] if type_counts else (None, 0)
        majority_cat, majority_cat_n = cat_counts.most_common(1)[0] if cat_counts else (None, 0)

        # Only proceed if current result deviates from majority
        type_ok = (data.get("document_type") == majority_type) or (majority_type_n < 3)
        cat_ok = (data.get("category") == majority_cat) or (majority_cat_n < 3)
        if type_ok and cat_ok:
            return data

        # Build reconciliation prompt
        summary_lines = []
        for dtype, cnt in type_counts.most_common(3):
            summary_lines.append(f"  - Typ: {dtype} ({cnt}x)")
        for cat, cnt in cat_counts.most_common(3):
            summary_lines.append(f"  - Kategorie: {cat} ({cnt}x)")

        reconcile_prompt = (
            f"Du hast dieses Dokument klassifiziert als:\n"
            f"  Absender: {sender}\n"
            f"  Typ: {data.get('document_type')}, Kategorie: {data.get('category')}\n\n"
            f"Im Archiv existieren bereits {len(past)} Dokumente von '{sender}':\n"
            + "\n".join(summary_lines) +
            f"\n\nIst deine Klassifizierung konsistent mit dem bisherigen Archiv?\n"
            f"Falls das aktuelle Dokument wirklich abweicht (z.B. anderer Typ), behalte deine Klassifizierung.\n"
            f"Falls es ein Fehler war, korrigiere. Antworte NUR mit JSON: "
            f'{{\"document_type\": \"...\", \"category\": \"...\"}}'
        )

        with _llm_lock:
            result = _llm.create_chat_completion(
                messages=[{"role": "user", "content": reconcile_prompt}],
                max_tokens=64,
                temperature=0.0,
            )
        raw = result["choices"][0]["message"]["content"]
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        patch = json.loads(cleaned)

        changed = []
        if patch.get("document_type") in DOCUMENT_TYPES and patch["document_type"] != data.get("document_type"):
            changed.append(f"document_type: {data.get('document_type')} → {patch['document_type']}")
            data["document_type"] = patch["document_type"]
        if patch.get("category") in CATEGORIES and patch["category"] != data.get("category"):
            changed.append(f"category: {data.get('category')} → {patch['category']}")
            data["category"] = patch["category"]
        if changed:
            log(f"[RECONCILIATION] Korrigiert: {'; '.join(changed)}")
        else:
            log(f"[RECONCILIATION] Klassifizierung bestätigt (keine Änderung)")
    except Exception as e:
        log(f"[RECONCILIATION] Fehler (ignoriert): {e}")
    return data


def classify_document(safe_text, filename=None, user_hint=None, feature_prompt=None, similar_docs=None, header_zone=None):
    from config import MOCK_LLM
    if MOCK_LLM:
        log("[MOCK] Generiere simulierte Klassifizierung...")
        from pdf_utils import extract_features
        features = extract_features(safe_text, filename=filename)
        
        # Match category and type based on rule-based feature candidates
        cat = features.get("category_candidates", ["Sonstiges"])[0] if features.get("category_candidates") else "Sonstiges"
        doc_type = features.get("type_from_filename") or features.get("type_candidate") or "Sonstiges"
        
        # Sender extraction from filename or fallback
        sender = "Unbekannter Absender"
        if filename:
            clean_name = os.path.splitext(filename)[0]
            clean_name = re.sub(r'^\d{8}_', '', clean_name)
            parts = clean_name.split("_")
            if parts and len(parts[0]) > 2:
                sender = parts[0].replace("-", " ")
        
        year_str = extract_year(safe_text) or str(datetime.now().year)
        date = f"{year_str}-01-15"
        
        first_words = " ".join(safe_text.split()[:12])
        summary = f"Simuliertes Dokument von {sender} bezüglich {doc_type} ({first_words}...)"
        
        mock_data = {
            "sender": sender,
            "date": date,
            "document_type": doc_type,
            "category": cat,
            "summary": summary,
            "keywords": f"mock, test, {cat.lower().replace(' & ', '_')}",
            "confidence": "high",
            "confidence_reason": "[MOCK] Simulation erfolgreich."
        }
        log(f"[MOCK] Resultat generiert: {mock_data}")
        return mock_data

    # [Weg 1: Hard-Rules Pre-Matching]
    # Scan text for known senders/aliases and guide the LLM using a custom hint.
    # CRITICAL: We restrict this strictly to the header_zone or first 400 characters of the page
    # to prevent generic/tax words (like "Netto" on a paycheck) from triggering false-positives!
    rule_sender, rule_category = detect_known_sender(header_zone or safe_text[:400])
    if rule_sender:
        sender_hint_prefix = f"\n\nHinweis: Der Absender dieses Dokuments ist bereits verifiziert als '{rule_sender}'."
        if user_hint:
            user_hint = sender_hint_prefix + " " + user_hint
        else:
            user_hint = sender_hint_prefix

    load_model()
    safe_text = safe_text[:2000]  # n_ctx=4096; prepare_text_for_llm already compresses
    system_prompt = SYSTEM_PROMPT.replace("{current_year}", str(datetime.now().year))

    if storage.sender_registry:
        # Match only against header zone to avoid generic terms (e.g. "Netto", "Gas") matching mid-document
        header_text = normalize_umlauts(header_zone or safe_text[:400])
        matching = [
            k for k in storage.sender_registry
            if len(k) > 5 and re.search(r'\b' + re.escape(normalize_umlauts(k)) + r'\b', header_text, re.IGNORECASE)
        ]
        if matching:
            sender_hint = f"\n\nHinweis: Folgender bekannter Absender wurde im Briefkopf gefunden – verwende genau diese Schreibweise: {', '.join(matching)}"
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

    few_shot_hint = fb.build_few_shot_prompt(n=5)

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
        # True fallback: only run keyword-based search when DB feature-match returned nothing
        similar_block = build_similar_docs_hint(safe_text) if not rule_sender else ""

    # [Königsweg: Structural Context Isolation]
    # Pass the top portion of the first page (briefkopf) as a distinct, isolated block.
    # The system prompt instructs the LLM to strictly resolve 'sender' from this block.
    header_block = f"\n\n--- DOKUMENT-BRIEFKOPF (Ausschließliche Absender-Quelle) ---\n{header_zone}\n----------------------------------" if header_zone else ""
    hint_instruction = f"\n\n!!! WICHTIGE ANWEISUNG DES BENUTZERS (hat hoechste Prioritaet, ignoriere nichts davon): {user_hint} !!!" if user_hint else ""
    user_content = f"Klassifiziere dieses Dokument:{feature_block}{sender_hint}{filename_hint}{few_shot_hint}{similar_block}{header_block}\n\n--- DOKUMENT-VOLLTEXT ---\n{safe_text}{hint_instruction}"

    # Emergency char-count guard
    # n_ctx=4096 tokens; German text averages ~3 chars/token.
    # System prompt ≈ 800 tokens → ~3200 tokens left ≈ 9600 chars, but with safety margin: 7500.
    _CHAR_LIMIT = 7500
    if len(system_prompt) + len(user_content) > _CHAR_LIMIT:
        # Strip all optional blocks, calculate budget for safe_text only
        _overhead = len(system_prompt) + len(sender_hint) + len(filename_hint) + len(header_block) + len(hint_instruction) + 200
        _text_budget = max(500, _CHAR_LIMIT - _overhead)
        user_content = f"Klassifiziere dieses Dokument:{sender_hint}{filename_hint}{header_block}\n\n--- DOKUMENT-VOLLTEXT ---\n{safe_text[:_text_budget]}{hint_instruction}"
        log(f"Prompt zu lang – kuerze Text auf {_text_budget} Zeichen.")

    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    feedback = None

    for attempt in range(1, MAX_RETRIES + 1):
        if feedback:
            current_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": (
                    f"Fehler in vorheriger Antwort: {feedback}\n\n"
                    f"Bitte korrigiere und klassifiziere dieses Dokument erneut:{feature_block}{header_block}\n\n--- DOKUMENT-VOLLTEXT ---\n{safe_text}{hint_instruction}"
                )},
            ]
        else:
            current_messages = base_messages

        log(f"LLM Klassifizierung, Versuch {attempt}/{MAX_RETRIES}...")
        t0 = time.time()
        try:
            with _llm_lock:
                result = _llm.create_chat_completion(
                    messages=current_messages,
                    max_tokens=384,
                    temperature=0.0
                )
            raw = result["choices"][0]["message"]["content"]

            cleaned = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)
            data = sanitize_llm_output(data)

            known_fields = {"sender", "date", "document_type", "category", "summary", "keywords", "low_value", "iban"}
            data = {k: v for k, v in data.items() if k in known_fields}

            # Normalize low_value to int (LLM may return bool or string)
            if "low_value" in data:
                data["low_value"] = 1 if data["low_value"] in (True, "true", 1, "1") else 0
            else:
                data["low_value"] = 0

            if data.get("sender"):
                data["sender"] = normalize_sender(data["sender"])

            # Auto-fix invalid category: fuzzy match, then fallback to 'Sonstiges'
            if data.get("category") not in CATEGORIES:
                close = get_close_matches(data["category"] or "", CATEGORIES, n=1, cutoff=0.4)
                if close:
                    log(f"Kategorie '{data['category']}' auto-korrigiert zu '{close[0]}'")
                    data["category"] = close[0]
                else:
                    log(f"Kategorie '{data['category']}' unbekannt – setze 'Sonstiges'")
                    data["category"] = "Sonstiges"

            # Auto-fix invalid document_type: fuzzy match, then fallback to 'Sonstiges'
            if data.get("document_type") not in DOCUMENT_TYPES:
                close = get_close_matches(data["document_type"] or "", DOCUMENT_TYPES, n=1, cutoff=0.6)
                if close:
                    log(f"Dokumenttyp '{data['document_type']}' auto-korrigiert zu '{close[0]}'")
                    data["document_type"] = close[0]
                else:
                    log(f"Dokumenttyp '{data['document_type']}' unbekannt – setze 'Sonstiges'")
                    data["document_type"] = "Sonstiges"

            # Apply Stufe-0 Rule overrides
            # CRITICAL: We restrict this strictly to the header_zone or first 400 characters of the page
            # to prevent generic/tax words (like "Netto" on a paycheck) from triggering false-positives!
            rule_sender, rule_category = detect_known_sender(header_zone or safe_text[:400])
            if rule_sender:
                data["sender"] = rule_sender
                if rule_category:
                    data["category"] = rule_category

            # Check semantic validity
            passes_semantic = check_sender_semantic(data.get("sender"), safe_text)

            errors = validate_classification(data)
            if not errors:
                # Determine confidence score
                if rule_sender:
                    confidence = "high"
                    reason = f"Absender ueber feste Stufe-0 Regel verifiziert ('{rule_sender}')"
                elif passes_semantic:
                    confidence = "medium"
                    reason = "Klassifizierung valide, Absender im Text semantisch verifiziert"
                else:
                    confidence = "low"
                    reason = "Absender existiert nicht im extrahierten PDF-Text (hohes Halluzinationsrisiko!)"

                data["confidence"] = confidence
                data["confidence_reason"] = reason

                # If sender was hallucinated (not found in text), clear it rather than
                # archiving with a made-up name. Document still gets processed correctly.
                if confidence == "low" and data.get("sender"):
                    log(f"Absender '{data['sender']}' nicht im Text gefunden – setze null (Halluzination).")
                    data["sender"] = None

                # Phase 5c: Reconciliation pass — only when confidence != high and sender known
                if confidence != "high" and data.get("sender"):
                    data = _reconciliation_pass(data, data["sender"])

                log(f"LLM OK [{confidence.upper()}] in {time.time()-t0:.1f}s: {json.dumps(data, ensure_ascii=False)}")
                return data

            owner_error = any("Empfaenger" in e for e in errors)
            if owner_error and len(errors) == 1:
                data["sender"] = None
                log("Absender ist Archivinhaber – setze sender=null und akzeptiere restliche Klassifizierung.")
                confidence = "medium" if passes_semantic or not data.get("sender") else "low"
                reason = "Absender ist Archivinhaber, restliche Felder sind valide"
                data["confidence"] = confidence
                data["confidence_reason"] = reason
                return data

            # Auto-fix sender errors that a retry cannot resolve:
            # - too short (single char / garbage) → null
            # - control characters → already stripped by sanitize, but guard anyway
            # These are structural document issues, not LLM mistakes worth retrying.
            non_retryable = [e for e in errors if "'sender' ist zu kurz" in e or "Steuerzeichen" in e]
            if non_retryable:
                log(f"Sender-Fehler nicht retry-wuerdig – setze sender=null: {'; '.join(non_retryable)}")
                data["sender"] = None
                errors = [e for e in errors if e not in non_retryable]
                if not errors:
                    passes_semantic = check_sender_semantic(data.get("sender"), safe_text)
                    confidence = "low"
                    reason = "Absender ungueltig oder nicht erkennbar – auf null gesetzt."
                    data["confidence"] = confidence
                    data["confidence_reason"] = reason
                    log(f"LLM OK [LOW] in {time.time()-t0:.1f}s: {json.dumps(data, ensure_ascii=False)}")
                    return data

            feedback = "; ".join(errors)
            log(f"Plausibilitaetsfehler (Versuch {attempt}): {feedback}")

        except json.JSONDecodeError:
            log(f"LLM antwortete kein valides JSON (Versuch {attempt}): {raw[:200]!r}")
            feedback = None
        except Exception as e:
            err_str = str(e)
            if "exceed context window" in err_str:
                # Token overflow: aggressively halve the text budget and rebuild prompt
                _overhead = len(system_prompt) + len(sender_hint) + len(filename_hint) + len(header_block) + len(hint_instruction) + 200
                _new_budget = max(300, (len(user_content) - _overhead) // 2)
                user_content = f"Klassifiziere dieses Dokument:{sender_hint}{filename_hint}{header_block}\n\n--- DOKUMENT-VOLLTEXT ---\n{safe_text[:_new_budget]}{hint_instruction}"
                base_messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
                feedback = None
                log(f"Token-Overflow – kuerze Text auf {_new_budget} Zeichen fuer naechsten Versuch.")
            log(f"LLM Fehler nach {time.time()-t0:.1f}s (Versuch {attempt}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2)

    return None


def extract_items_from_invoice(text: str, filename: str = "", vendor: str = "", purchase_date: str = "") -> list[dict]:
    """Extract line items from an invoice using the LLM.
    Returns a list of item dicts or empty list on failure.
    Call for document_type 'Rechnung' or 'Warenrechnung'."""
    load_model()
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
        with _llm_lock:
            result = _llm.create_chat_completion(
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


def extract_services_from_invoice(text: str, filename: str = "", vendor: str = "", invoice_date: str = "") -> list[dict]:
    """Extract service/expense entries from a non-goods invoice (handcraft, travel, medical, etc.).
    Returns a list of service dicts or empty list on failure.
    Call for document_type 'Rechnung' or 'Dienstleistungsrechnung'."""
    load_model()
    safe_text = text[:3000]

    SERVICE_CATEGORIES = [
        "Handwerk & Reparatur", "Reise & Urlaub", "Arzt & Gesundheit",
        "Versicherung", "Telekommunikation", "Energie & Wasser",
        "Steuer & Behörden", "Bildung & Weiterbildung", "Reinigung & Pflege",
        "Transport & Mobilität", "Gastronomie & Catering",
        "Beratung & Dienstleistung", "Sonstiges",
    ]

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
        f"notes (string)\n\n"
        f"Regeln:\n"
        f"- NUR Dienstleistungen erfassen, KEINE physischen Artikel oder Produkte\n"
        f"- Wenn es sich um eine Warenrechnung handelt (Elektronik, Möbel, etc.): leeres Array [] zurückgeben\n"
        f"- Gesamtbetrag als 'amount', Preise ohne Währungssymbol\n"
        f"- Maximal 10 Einträge\n\n"
        f"--- RECHNUNGSTEXT ---\n{safe_text}"
    )

    try:
        with _llm_lock:
            result = _llm.create_chat_completion(
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


def extract_contract_from_document(text: str, filename: str = "", sender: str = "", doc_type: str = "") -> dict | None:
    """Extract contract/subscription details from a document using the LLM.
    Returns a dict or None on failure.
    Only call for document_type in ('Vertrag', 'Kündigung', 'Mahnung', 'Abonnement')."""
    load_model()
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
        with _llm_lock:
            result = _llm.create_chat_completion(
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
