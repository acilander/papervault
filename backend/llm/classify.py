import json
import os
import re
import time
from contextvars import ContextVar
from datetime import datetime
from difflib import get_close_matches

import config as _config
from config import CATEGORIES, DOCUMENT_TYPES, SYSTEM_PROMPT, MAX_RETRIES
import storage
import feedback as fb
from utils import log, normalize_umlauts, extract_year
from pipeline.validation import validate_classification, _looks_like_ocr_garbage, check_sender_semantic

from llm.driver import _llm_lock, load_model


_classification_diagnostics: ContextVar[list[dict]] = ContextVar("classification_diagnostics", default=[])


def get_classification_diagnostics() -> list[dict]:
    return _classification_diagnostics.get()


def _build_retry_instruction(errors: list[str]) -> str:
    guidance = []
    joined = " ".join(errors).lower()
    if "'sender'" in joined:
        guidance.append("Bestimme den Aussteller ausschließlich aus Briefkopf oder Logo. Wenn er nicht eindeutig ist, setze sender auf null.")
    if "'date'" in joined:
        guidance.append("Verwende nur ein belegtes Datum im Format YYYY-MM-DD oder YYYY. Wenn keines erkennbar ist, setze date auf null.")
    if "'category'" in joined:
        guidance.append("Wähle exakt eine der erlaubten Kategorien aus dem Systemprompt.")
    if "'summary'" in joined:
        guidance.append("Formuliere eine konkrete, vollständige Zusammenfassung mit mindestens einem Satz.")
    if "'document_type'" in joined:
        guidance.append("Wähle möglichst einen erlaubten Dokumenttyp. Falls keiner passt, schlage einen kurzen präzisen neuen Typ vor.")
    return " ".join(guidance) or "Korrigiere alle genannten Felder anhand des Dokumenttexts und gib ausschließlich valides JSON zurück."


def normalize_sender(sender):
    if not sender or not storage.sender_registry:
        return sender
    sender = re.sub(r'[\r\n\t]+', ' ', sender).strip()
    known = list(storage.sender_registry.keys())
    for k in known:
        if k.lower() == sender.lower():
            return k
    for k, entry in storage.sender_registry.items():
        for alias in entry.get("aliases") or []:
            if alias.lower() == sender.lower():
                log(f"Absender via Alias erkannt: '{sender}' -> '{k}'")
                return k
    matches = get_close_matches(sender, known, n=1, cutoff=0.82)
    if matches:
        log(f"Absender normalisiert: '{sender}' -> '{matches[0]}'")
        return matches[0]
    all_aliases = {alias: k for k, entry in storage.sender_registry.items()
                   for alias in (entry.get("aliases") or [])}
    alias_matches = get_close_matches(sender, list(all_aliases.keys()), n=1, cutoff=0.82)
    if alias_matches:
        canonical = all_aliases[alias_matches[0]]
        log(f"Absender via Alias-Fuzzy erkannt: '{sender}' -> '{canonical}'")
        return canonical
    return sender


def sanitize_llm_output(data: dict) -> dict:
    STRING_FIELDS = ("sender", "date", "document_type", "category", "summary", "keywords", "confidence_reason", "iban", "property_unit")
    for field in STRING_FIELDS:
        val = data.get(field)
        if isinstance(val, str):
            val = re.sub(r'[\r\n\t]+', ' ', val)
            val = re.sub(r' {2,}', ' ', val).strip()
            data[field] = val if val else None

    sender = data.get("sender")
    if isinstance(sender, str) and _looks_like_ocr_garbage(sender):
        log(f"Absender sieht nach OCR-Artefakt aus – setze null: '{sender}'")
        data["sender"] = None
    iban = data.get("iban")
    if isinstance(iban, str):
        iban_clean = re.sub(r'\s+', '', iban).upper()
        if re.match(r'^DE\d{20}$', iban_clean):
            data["iban"] = iban_clean
        else:
            data["iban"] = None

    pu = data.get("property_unit")
    if isinstance(pu, str):
        pu_clean = pu.strip().replace('"', '').replace("'", "")
        if pu_clean in ("Gesamthaus", "EG", "UG", "OG", "DG"):
            data["property_unit"] = pu_clean
        else:
            data["property_unit"] = None
    return data


def filter_keywords_against_text(keywords_str: str, source_text: str) -> str:
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
        words = [w for w in kw_norm.split() if len(w) >= 4]
        exact = kw_norm in text_norm or any(w in text_norm for w in words)
        fuzzy = any(get_close_matches(w, text_words, n=1, cutoff=0.85) for w in words)
        if exact or fuzzy:
            kept.append(kw)
    return ", ".join(kept)


def build_similar_docs_hint(text_snippet: str) -> str:
    try:
        import db as _db
        known_senders = list(storage.sender_registry.keys())
        matched_sender = None
        text_lower = normalize_umlauts(text_snippet[:2000])
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
    text_norm = normalize_umlauts(text)
    for sender, entry in sorted(storage.sender_registry.items(), key=lambda x: len(x[0]), reverse=True):
        sender_esc = re.escape(normalize_umlauts(sender))
        if re.search(r'\b' + sender_esc + r'\b', text_norm, re.IGNORECASE):
            return sender, entry.get("pinned_category")
        for alias in entry.get("aliases") or []:
            alias_esc = re.escape(normalize_umlauts(alias))
            if re.search(r'\b' + alias_esc + r'\b', text_norm, re.IGNORECASE):
                return sender, entry.get("pinned_category")
    return None, None


def _reconciliation_pass(data: dict, sender: str) -> dict:
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

        type_ok = (data.get("document_type") == majority_type) or (majority_type_n < 3)
        cat_ok = (data.get("category") == majority_cat) or (majority_cat_n < 3)
        if type_ok and cat_ok:
            return data

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
            f'{{"document_type": "...\", "category": "..."}}'
        )

        with _llm_lock:
            from llm.driver import _llm
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
    _classification_diagnostics.set([])
    from config import MOCK_LLM
    if MOCK_LLM:
        log("[MOCK] Generiere simulierte Klassifizierung...")
        from pdf_utils import extract_features
        features = extract_features(safe_text, filename=filename)
        cat = features.get("category_candidates", ["Sonstiges"])[0] if features.get("category_candidates") else "Sonstiges"
        doc_type = features.get("type_from_filename") or features.get("type_candidate") or "Sonstiges"
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

    rule_sender, rule_category = detect_known_sender(header_zone or safe_text[:400])
    if rule_sender:
        sender_hint_prefix = f"\n\nHinweis: Der Absender dieses Dokuments ist bereits verifiziert als '{rule_sender}'."
        if user_hint:
            user_hint = sender_hint_prefix + " " + user_hint
        else:
            user_hint = sender_hint_prefix

    load_model()
    system_prompt = ""
    safe_text = safe_text[:2000]
    from config_manager import get_settings
    from prompts import build_stage1_system_prompt, build_stage2_system_prompt
    _settings = get_settings()

    if storage.sender_registry:
        header_text = normalize_umlauts(header_zone or safe_text[:400])
        matching = [
            k for k in storage.sender_registry
            if len(k) > 5 and re.search(r'\b' + re.escape(normalize_umlauts(k)) + r'\b', header_text, re.IGNORECASE)
        ]
        if matching:
            sender_hint = f"\n\nHinweis: Folgender bekannte Absender wurde im Briefkopf gefunden – verwende genau diese Schreibweise: {', '.join(matching)}"
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

    few_shot_hint = fb.build_few_shot_prompt(n=3, text=safe_text)
    hint_block = f"\n\nBenutzerhinweis (hohe Prioritaet): {user_hint}" if user_hint else ""
    feature_block = f"\n\n{feature_prompt}" if feature_prompt else ""

    if similar_docs:
        lines = ["\n\nStrukturell aehnliche Dokumente aus dem Archiv (als Referenz):"]
        for d in similar_docs:
            lines.append(
                f"  - Absender: {d.get('sender','?')} | Kategorie: {d.get('category','?')} "
                f"| Typ: {d.get('document_type','?')} | Datum: {d.get('date','?')}"
                + (f" | {d['summary'][:60]}" if d.get("summary") else "")
            )
        similar_block = "\n".join(lines)
    else:
        similar_block = build_similar_docs_hint(safe_text) if not rule_sender else ""

    header_block = f"\n\n--- DOKUMENT-BRIEFKOPF (Ausschließliche Absender-Quelle) ---\n{header_zone}\n----------------------------------" if header_zone else ""
    hint_instruction = f"\n\n!!! WICHTIGE ANWEISUNG DES BENUTZERS (hat hoechste Prioritaet, ignoriere nichts davon): {user_hint} !!!" if user_hint else ""
    user_content = f"Dokumenten-Inhalt:{feature_block}{sender_hint}{filename_hint}{few_shot_hint}{similar_block}{header_block}\n\n--- DOKUMENT-VOLLTEXT ---\n{safe_text}{hint_instruction}"

    _CHAR_LIMIT = 12000
    if len(user_content) > _CHAR_LIMIT:
        _overhead = len(sender_hint) + len(filename_hint) + len(header_block) + len(hint_instruction) + 200
        _text_budget = max(1500, _CHAR_LIMIT - _overhead)
        user_content = f"Dokumenten-Inhalt:{sender_hint}{filename_hint}{header_block}\n\n--- DOKUMENT-VOLLTEXT ---\n{safe_text[:_text_budget]}{hint_instruction}"
        log(f"Prompt zu lang – kuerze Text auf {_text_budget} Zeichen.")

    feedback = None
    failure_signatures: set[tuple[str, ...]] = set()

    for attempt in range(1, MAX_RETRIES + 1):
        log(f"LLM Klassifizierung (Zwei-Stufen-Kaskade), Versuch {attempt}/{MAX_RETRIES}...")
        t0 = time.time()
        raw = ""
        temperature = 0.0 if attempt == 1 else 0.15
        try:
            # Stage 1: Basis-Metadaten (sender, date, document_type)
            system_prompt_s1 = build_stage1_system_prompt(_settings)
            messages_s1 = [
                {"role": "system", "content": system_prompt_s1},
                {"role": "user", "content": f"Extrahiere Absender, Datum und Typ für dieses Dokument:\n\n{user_content}"}
            ]
            if feedback:
                messages_s1.append({"role": "user", "content": f"Korrekturauftrag nach dem vorherigen Versuch: {feedback} Antworte ausschließlich mit einem vollständigen JSON-Objekt."})

            from llm.driver import _llm
            with _llm_lock:
                result_s1 = _llm.create_chat_completion(
                    messages=messages_s1,
                    max_tokens=128,
                    temperature=temperature
                )
            raw_s1 = result_s1["choices"][0]["message"]["content"]
            raw = raw_s1
            cleaned_s1 = raw_s1.replace("```json", "").replace("```", "").strip()
            # Handle possible leading/trailing junk
            start_idx = cleaned_s1.find("{")
            if start_idx >= 0:
                cleaned_s1 = cleaned_s1[start_idx:]
            end_idx = cleaned_s1.rfind("}")
            if end_idx >= 0:
                cleaned_s1 = cleaned_s1[:end_idx+1]
            data_s1 = json.loads(cleaned_s1)

            # Stage 2: Tiefe Extraktion (category, property_unit, summary, keywords, low_value, iban)
            system_prompt_s2 = build_stage2_system_prompt(_settings, data_s1)
            messages_s2 = [
                {"role": "system", "content": system_prompt_s2},
                {"role": "user", "content": f"Extrahiere die restlichen tiefen Daten:\n\n{user_content}"}
            ]
            if feedback:
                messages_s2.append({"role": "user", "content": f"Korrekturauftrag: {feedback} Antworte ausschließlich mit einem vollständigen JSON-Objekt."})
            with _llm_lock:
                result_s2 = _llm.create_chat_completion(
                    messages=messages_s2,
                    max_tokens=512,
                    temperature=temperature
                )
            raw_s2 = result_s2["choices"][0]["message"]["content"]
            raw = raw_s2
            cleaned_s2 = raw_s2.replace("```json", "").replace("```", "").strip()
            # Handle possible leading/trailing junk
            start_idx2 = cleaned_s2.find("{")
            if start_idx2 >= 0:
                cleaned_s2 = cleaned_s2[start_idx2:]
            end_idx2 = cleaned_s2.rfind("}")
            if end_idx2 >= 0:
                cleaned_s2 = cleaned_s2[:end_idx2+1]
            data_s2 = json.loads(cleaned_s2)

            # Merge results
            data = {**data_s1, **data_s2}
            data = sanitize_llm_output(data)

            known_fields = {"sender", "date", "document_type", "category", "property_unit", "vehicle_id", "child_name", "summary", "keywords", "low_value", "iban"}
            data = {k: v for k, v in data.items() if k in known_fields}

            if "low_value" in data:
                data["low_value"] = 1 if data["low_value"] in (True, "true", 1, "1") else 0
            else:
                data["low_value"] = 0

            if data.get("sender"):
                data["sender"] = normalize_sender(data["sender"])

            if data.get("category") not in CATEGORIES:
                close = get_close_matches(data["category"] or "", CATEGORIES, n=1, cutoff=0.4)
                if close:
                    log(f"Kategorie '{data['category']}' auto-korrigiert zu '{close[0]}'")
                    data["category"] = close[0]
                else:
                    log(f"Kategorie '{data['category']}' unbekannt – setze 'Sonstiges'")
                    data["category"] = "Sonstiges"

            from config_manager import get_settings
            active_types = get_settings().get("document_types", DOCUMENT_TYPES)
            if data.get("document_type") not in active_types:
                # We do NOT force "Sonstiges" anymore if it's not in the list!
                # We only try to auto-correct typos against known types, otherwise keep the new invention.
                close = get_close_matches(data["document_type"] or "", active_types, n=1, cutoff=0.6)
                if close:
                    log(f"Dokumenttyp '{data['document_type']}' auto-korrigiert zu '{close[0]}'")
                    data["document_type"] = close[0]
                else:
                    # Keep the LLM's invented type!
                    pass

            rule_sender, rule_category = detect_known_sender(header_zone or safe_text[:400])
            if rule_sender:
                data["sender"] = rule_sender
                if rule_category:
                    data["category"] = rule_category

            passes_semantic = check_sender_semantic(data.get("sender"), safe_text)
            errors = validate_classification(data)

            if not errors:
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

                if confidence == "low" and data.get("sender"):
                    log(f"Absender '{data['sender']}' nicht im Text gefunden – setze null (Halluzination).")
                    data["sender"] = None

                if confidence != "high" and data.get("sender"):
                    data = _reconciliation_pass(data, data["sender"])

                log(f"LLM OK [{confidence.upper()}] in {time.time()-t0:.1f}s: {json.dumps(data, ensure_ascii=False)}")
                return data

            type_errors = [e for e in errors if e.startswith("'document_type'")]
            if type_errors and len(type_errors) == len(errors):
                data["confidence"] = "low"
                data["confidence_reason"] = "Vorgeschlagener Dokumenttyp benötigt eine Entscheidung in der Dokumentprüfung."
                log(f"KI-Vorschlag für neuen Dokumenttyp '{data.get('document_type')}' zur manuellen Freigabe vorgemerkt.")
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

            signature = tuple(sorted(errors))
            diagnostics = list(_classification_diagnostics.get())
            diagnostics.append({
                "attempt": attempt,
                "failure_type": "validation",
                "errors": errors,
                "proposed": {field: data.get(field) for field in ("sender", "date", "document_type", "category")},
            })
            _classification_diagnostics.set(diagnostics)
            if signature in failure_signatures:
                data["confidence"] = "low"
                data["confidence_reason"] = "Gleicher Validierungsfehler trotz adaptivem Wiederholungsversuch. Manuelle Prüfung erforderlich."
                log(f"Wiederholter Plausibilitaetsfehler nach Versuch {attempt}; Übergabe an Dokumentprüfung.")
                return data
            failure_signatures.add(signature)
            feedback = _build_retry_instruction(errors)
            log(f"Plausibilitaetsfehler (Versuch {attempt}): {'; '.join(errors)}")

        except json.JSONDecodeError as e:
            diagnostics = list(_classification_diagnostics.get())
            diagnostics.append({
                "attempt": attempt,
                "failure_type": "invalid_json",
                "error": str(e),
                "response_length": len(raw),
            })
            _classification_diagnostics.set(diagnostics)
            log(f"LLM antwortete kein valides JSON (Versuch {attempt}): {raw[:200]!r}")
            feedback = "Die vorherige Antwort war kein valides JSON. Gib ausschließlich das angeforderte vollständige JSON-Objekt ohne zusätzlichen Text zurück."
        except Exception as e:
            err_str = str(e)
            context_overflow = "exceed context window" in err_str
            if context_overflow:
                _overhead = len(system_prompt) + len(sender_hint) + len(filename_hint) + len(header_block) + len(hint_instruction) + 200
                _new_budget = max(300, (len(user_content) - _overhead) // 2)
                user_content = f"Klassifiziere dieses Dokument:{sender_hint}{filename_hint}{header_block}\n\n--- DOKUMENT-VOLLTEXT ---\n{safe_text[:_new_budget]}{hint_instruction}"
                base_messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
                feedback = None
                log(f"Token-Overflow – kuerze Text auf {_new_budget} Zeichen fuer naechsten Versuch.")
            diagnostics = list(_classification_diagnostics.get())
            diagnostics.append({
                "attempt": attempt,
                "failure_type": "runtime_error",
                "error": err_str[:300],
            })
            _classification_diagnostics.set(diagnostics)
            if not context_overflow:
                feedback = f"Beim vorherigen Modellaufruf trat ein technischer Fehler auf: {err_str[:200]}. Prüfe die geforderten Felder erneut und gib valides JSON zurück."
            log(f"LLM Fehler nach {time.time()-t0:.1f}s (Versuch {attempt}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2)

    return None
