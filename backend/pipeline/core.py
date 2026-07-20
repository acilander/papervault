import json
import os
import re
import shutil
import sys
from datetime import datetime

from config import (
    TARGET_BASE, DUPLICATES_DIR, FAILED_DIR, ENCRYPTED_DIR, REVIEW_DIR,
    CATEGORY_FOLDER_MAP, SENDER_SUBFOLDERS, CATEGORIES,
)
from pdf_utils import (
    extract_text, ocr_pdf, prepare_text_for_llm,
    unique_path, extract_features, build_feature_prompt,
    detect_receipt, compute_simhash, generate_thumbnail
)
from storage import record_sender, apply_sender_overrides, processing_log
import db
from utils import log, is_periodic_document
from pipeline.steps import check_duplicate, check_fuzzy_duplicate, cleanup_empty_inbox_folders

_COMMON_GERMAN_WORDS = {
    "der", "die", "das", "und", "ist", "in", "zu", "von", "mit", "den", "dem", "im", "für", "ein", "eine",
    "einer", "einem", "einen", "eines", "an", "auf", "aus", "bei", "als", "nach", "um", "über", "vor",
    "durch", "ohne", "gegen", "wie", "so", "noch", "nur", "auch", "mehr", "oder", "aber", "doch", "sich",
    "sie", "er", "es", "wir", "ihr", "ihm", "ihn", "ihnen", "ihre", "ihres", "ihrem", "ihren", "mein",
    "dein", "sein", "unser", "euer", "man", "wer", "was", "wo", "wann", "warum", "rechnung", "datum",
    "betrag", "eur", "euro", "mwst", "steuer", "telefon", "mobilfunk", "kasse", "rechnungsdatum",
    "kundennummer", "vertrag", "versicherung", "arbeit", "gehalt", "lohn", "miete", "kosten", "strom",
    "gas", "wasser", "anbieter", "hersteller", "kaufbeleg", "quittung", "bon", "gesamt", "summe",
    "netto", "brutto", "umsatzsteuer", "beleg", "adresse", "straße", "str", "plz", "ort", "stadt",
    "deutschland", "fax", "email", "mail", "web", "internet", "online", "sparkasse", "bank", "konto",
    "iban", "bic", "überweisung", "lastschrift", "abbuchung", "gutschrift", "saldo", "auszug", "kontoauszug"
}

def _register_doc(file_path: str, doc_id) -> int:
    """Ensure document has a DB identity. Returns doc_id."""
    size_bytes = 0
    if os.path.exists(file_path):
        size_bytes = os.path.getsize(file_path)

    if doc_id is None:
        existing = db.get_document_by_path(file_path)
        if existing:
            doc_id = existing["id"]
        else:
            doc_id = db.upsert_document(
                file_path=file_path,
                filename=os.path.basename(file_path),
                sender=None, date=None, document_type=None,
                category=None, summary=None, status="processing"
            )
    db.update_document(doc_id, status="processing", file_size_bytes=size_bytes)
    return doc_id


def _extract_text(file_path: str, doc_id: int):
    """Extract text from PDF. Returns (text, status) or calls _fail_doc and returns None."""
    log("Extrahiere Text via PyMuPDF...")
    text, status = extract_text(file_path)

    if status == "encrypted":
        os.makedirs(ENCRYPTED_DIR, exist_ok=True)
        dest = unique_path(os.path.join(ENCRYPTED_DIR, os.path.basename(file_path)))
        shutil.move(file_path, dest)
        log(f"VERSCHLUESSELT: PDF ist passwortgeschuetzt. Verschoben nach: {dest}")
        log("--- Abgeschlossen (verschluesselt) ---")
        processing_log(os.path.basename(file_path), "encrypted")
        try:
            db.update_document(doc_id, file_path=dest, filename=os.path.basename(dest),
                               summary="VERSCHLUESSELT: Das PDF-Dokument ist passwortgeschützt.", status="encrypted")
            db.insert_trace(doc_id, "text_extraction", "failed", "Das PDF-Dokument ist passwortgeschützt.", {"file_path": dest})
        except Exception as e:
            log(f"WARNUNG: Datei nach encrypted/ verschoben, aber DB-Status-Update/Trace fehlgeschlagen: {e}")
        cleanup_empty_inbox_folders(file_path)
        return None, None

    if status == "corrupt":
        os.makedirs(FAILED_DIR, exist_ok=True)
        dest = unique_path(os.path.join(FAILED_DIR, os.path.basename(file_path)))
        shutil.move(file_path, dest)
        log(f"FEHLER: PDF nicht lesbar (korrupt). Verschoben nach: {dest}")
        log("--- Abgeschlossen (fehlgeschlagen) ---")
        processing_log(os.path.basename(file_path), "corrupt")
        try:
            db.update_document(doc_id, file_path=dest, filename=os.path.basename(dest),
                               summary="FEHLER: PDF-Datei ist nicht lesbar (Datei beschädigt oder ungültig).", status="corrupt")
            db.insert_trace(doc_id, "text_extraction", "failed", "PDF-Datei ist beschädigt oder ungültig.", {"file_path": dest})
        except Exception as e:
            log(f"WARNUNG: Datei nach failed/ verschoben, aber DB-Status-Update/Trace fehlgeschlagen: {e}")
        cleanup_empty_inbox_folders(file_path)
        return None, None

    log(f"PyMuPDF: {len(text.strip())} Zeichen gefunden.")

    # Calculate German dictionary density to detect garbage character-soup scan artifacts
    words = [w.strip(".,;:!?()[]-–\"'").lower() for w in text.split()]
    words = [w for w in words if w]
    german_word_count = sum(1 for w in words if w in _COMMON_GERMAN_WORDS)
    density = (german_word_count / len(words)) if words else 0.0

    # Calculate alphanumeric ratio (to protect structured tables, timesheets, and numeric reports)
    stripped_text = text.strip()
    alnum_count = sum(1 for c in stripped_text if c.isalnum() or c.isspace())
    alnum_ratio = (alnum_count / len(stripped_text)) if stripped_text else 0.0

    log(f"Wörterbuch-Prüfung: {len(words)} Wörter, davon {german_word_count} deutsche Begriffe ({density * 100:.1f}% Dichte) | Alnum-Verhältnis: {alnum_ratio * 100:.1f}%")

    # Force OCR only if:
    # 1. Character count is too low (< 50)
    # OR 2. Text density is under 15% AND it is NOT a clean alphanumeric structured document (alnum_ratio < 75%)
    is_garbage_scan = len(text.strip()) >= 50 and density < 0.15 and alnum_ratio < 0.75

    if len(text.strip()) < 50 or is_garbage_scan:
        if is_garbage_scan:
            log(f"WARNUNG: Text-Zeichensalat erkannt (Dichte {density*100:.1f}% < 15%, Alnum {alnum_ratio*100:.1f}% < 75%). Erzwinge echtes OCR...")
            try:
                db.insert_trace(doc_id, "text_extraction", "warning", f"Zeichensalat erkannt (deutsche Wörterbuch-Dichte {density*100:.1f}% < 15%). Starte OCR-Texterkennung...", {"char_count_original": len(text.strip()), "density": round(density, 3), "alnum_ratio": round(alnum_ratio, 3)})
            except Exception:
                pass
        else:
            try:
                db.insert_trace(doc_id, "text_extraction", "warning", f"Zu wenig Text ({len(text.strip())} Zeichen). Starte OCR-Texterkennung...", {"char_count_original": len(text.strip())})
            except Exception:
                pass
        text = ocr_pdf(file_path)

    if len(text.strip()) < 50:
        os.makedirs(FAILED_DIR, exist_ok=True)
        dest = unique_path(os.path.join(FAILED_DIR, os.path.basename(file_path)))
        shutil.move(file_path, dest)
        log(f"WARNUNG: Kein verwertbarer Text gefunden (auch nach OCR). Verschoben nach: {dest}")
        log("--- Abgeschlossen (fehlgeschlagen) ---")
        processing_log(os.path.basename(file_path), "no_text")
        db.update_document(doc_id, file_path=dest, filename=os.path.basename(dest),
                           summary="FEHLER: Kein verwertbarer Text im Dokument gefunden (auch nach OCR-Texterkennung).", status="no_text")
        try:
            db.insert_trace(doc_id, "text_extraction", "failed", "Kein verwertbarer Text im Dokument gefunden (auch nach OCR-Texterkennung).", {"file_path": dest})
        except Exception:
            pass
        cleanup_empty_inbox_folders(file_path)
        return None, None

    try:
        db.insert_trace(doc_id, "text_extraction", "success", f"Text erfolgreich extrahiert ({len(text.strip())} Zeichen).", {
            "character_count": len(text.strip()),
            "density": round(density, 3),
            "alnum_ratio": round(alnum_ratio, 3)
        })
    except Exception:
        pass

    return text, status


def _build_user_hint(file_path: str, text: str) -> tuple[str | None, str | None]:
    """Read .hint sidecar and run receipt detection. Returns (user_hint, hint_path)."""
    hint_path = os.path.splitext(file_path)[0] + ".hint"
    user_hint = None
    if os.path.exists(hint_path):
        try:
            with open(hint_path, "r", encoding="utf-8") as f:
                user_hint = f.read().strip()
            log(f"Benutzerhinweis geladen: {user_hint[:80]}")
        except Exception:
            pass

    is_receipt, receipt_sender = detect_receipt(text, filename=os.path.basename(file_path))
    if is_receipt and not user_hint:
        user_hint = (
            f"Dieses Dokument ist ein Kassenbon/Quittung"
            + (f" von {receipt_sender}" if receipt_sender else "")
            + ". Klassifiziere als document_type=Warenrechnung und category=Kassenbon & Quittung, "
            "es sei denn die gekauften Artikel sind eindeutig einer anderen Kategorie zuzuordnen "
            "(z.B. Wohnen & Eigentum fuer Baumaterial, Fahrzeug & Werkstatt fuer Autoteile)."
        )
        log(f"Kassenbon erkannt – LLM-Hinweis gesetzt. Absender: {receipt_sender}")

    return user_hint, hint_path


def _stage_or_archive(file_path: str, new_name: str, confidence: str, data: dict):
    """Move file to review/ or archive directly. Returns (dest_pdf, status, log_status, log_msg, log_fin)."""
    if not os.path.exists(file_path):
        return None, None, None, None, None
    if confidence == "high" and data.get("date") and data.get("date") != "null":
        log("[AUTO-ARCHIV] Hohes Vertrauen verifiziert. Archiviere Dokument direkt...")
        from pipeline.steps import archive_file_on_disk
        try:
            dest_pdf = archive_file_on_disk(file_path, data.get("category") or "Sonstiges", data.get("sender"), data.get("date"), document_type=data.get("document_type"), iban=data.get("iban"))
        except FileNotFoundError:
            return None, None, None, None, None
        return dest_pdf, "ok", "auto_archived", f"[AUTO-ARCHIV] Erfolgreich einsortiert nach: {dest_pdf}", "--- Abgeschlossen (automatisch archiviert) ---"
    else:
        os.makedirs(REVIEW_DIR, exist_ok=True)
        dest_pdf = unique_path(os.path.join(REVIEW_DIR, new_name))
        try:
            shutil.move(file_path, dest_pdf)
        except FileNotFoundError:
            return None, None, None, None, None
        return dest_pdf, "review", "review", f"Bereit zur Pruefung – verschoben nach: {dest_pdf}", "--- Abgeschlossen (wartet auf Bestaetigung) ---"


def process_pdf(file_path, doc_id=None):
    from llm import classify_document, filter_keywords_against_text
    log(f"--- Neue Datei: {os.path.basename(file_path)} ---")

    # Reload sender_registry from DB to guarantee absolute multi-process/concurrency synchronization
    try:
        from storage import load_sender_registry
        load_sender_registry()
    except Exception:
        pass

    # Phase 1: DB identity
    doc_id = _register_doc(file_path, doc_id)
    try:
        db.insert_trace(doc_id, "ingest", "success", f"Dateisystem-Ingestion gestartet: '{os.path.basename(file_path)}' registriert.")
    except Exception:
        pass

    if not os.path.exists(file_path):
        log(f"WARNUNG: Datei nicht gefunden beim Start der Verarbeitung (bereits verschoben?): {file_path}")
        db.update_document(doc_id, status="failed", summary="FEHLER: Datei beim Start der Verarbeitung nicht gefunden.")
        try:
            db.insert_trace(doc_id, "ingest", "failed", "Datei beim Start der Verarbeitung nicht gefunden.")
        except Exception:
            pass
        return

    if os.path.getsize(file_path) == 0:
        os.makedirs(FAILED_DIR, exist_ok=True)
        dest = unique_path(os.path.join(FAILED_DIR, os.path.basename(file_path)))
        shutil.move(file_path, dest)
        log(f"FEHLER: Datei ist leer (0 Bytes). Verschoben nach: {dest}")
        log("--- Abgeschlossen (fehlgeschlagen) ---")
        processing_log(os.path.basename(file_path), "empty_file")
        db.update_document(doc_id, file_path=dest, filename=os.path.basename(dest),
                           summary="FEHLER: Datei ist leer (0 Bytes) – keine gültige PDF.", status="empty_file")
        try:
            db.insert_trace(doc_id, "ingest", "failed", "Datei ist leer (0 Bytes) – keine gültige PDF.", {"file_path": dest})
        except Exception:
            pass
        cleanup_empty_inbox_folders(file_path)
        return

    # Phase 2: Text extraction
    text, _ = _extract_text(file_path, doc_id)
    if text is None:
        return

    # Phase 3: Duplicate check (exact hash)
    if check_duplicate(file_path, text, doc_id):
        return
    doc_content_hash = getattr(check_duplicate, 'last_hash', None)

    # Phase 3b: SimHash near-duplicate check (rescanned documents)
    doc_sim_hash = compute_simhash(text)
    sim_duplicate_note = None
    if not is_periodic_document("", os.path.basename(file_path), text):
        sim_matches = db.get_similar_by_simhash(doc_sim_hash, doc_id)
        if sim_matches:
            best = sim_matches[0]
            similarity = round((1.0 - best['simhash_distance'] / 64) * 100, 1)
            log(f"SCAN-DUPLIKAT erkannt ({similarity}% Textübereinstimmung) – ähnlich wie: {os.path.basename(best['file_path'])}")
            sim_duplicate_note = f"Mögliches Scan-Duplikat ({similarity}% Textübereinstimmung) von: {os.path.basename(best['file_path'])}"
            try:
                db.insert_trace(doc_id, "duplicate_check", "warning", f"Scan-Duplikat erkannt ({similarity}% Textübereinstimmung) – ähnlich wie: {os.path.basename(best['file_path'])}", {"similarity": similarity, "original_id": best["id"]})
            except Exception:
                pass
        else:
            try:
                db.insert_trace(doc_id, "duplicate_check", "success", "SimHash-Ähnlichkeitsprüfung abgeschlossen. Keine Scan-Duplikate gefunden.")
            except Exception:
                pass
    else:
        log("Periodischer Beleg erkannt – überspringe SimHash-Vergleich.")
        try:
            db.insert_trace(doc_id, "duplicate_check", "success", "Periodischer Beleg erkannt – SimHash-Vergleich übersprungen.")
        except Exception:
            pass

    # Phase 4: Pre-analysis (features, hints, receipt detection)
    safe_text = prepare_text_for_llm(text)
    features = extract_features(text, filename=os.path.basename(file_path), file_path=file_path)
    feature_prompt = build_feature_prompt(features)
    similar_docs = db.find_similar_by_features(
        features.get("category_candidates", []),
        features.get("type_candidate"),
    )
    log(f"Merkmale: {', '.join(features.get('category_candidates', [])) or '–'} | Typ: {features.get('type_candidate') or '–'}")
    user_hint, hint_path = _build_user_hint(file_path, text)
    try:
        db.insert_trace(doc_id, "pre_analysis", "success", f"Dokumenten-Merkmale analysiert: {', '.join(features.get('category_candidates', [])) or 'Keine'} | Typ: {features.get('type_candidate') or 'Keiner'}", {"features": features, "has_user_hint": bool(user_hint)})
    except Exception:
        pass

    # Phase 4b: Deterministic Identifier check (Stufe 0 Input & Override)
    from db.identifiers_repo import match_existing_identifiers
    matched_sender, matched_item = match_existing_identifiers(text)

    if matched_sender:
        log(f"[IDENTIFIER] Deterministischer Absender-Treffer für '{matched_sender}' über ID '{matched_item['identifier_value']}'.")
        id_hint = f"Absender ist definitiv '{matched_sender}'"
        if matched_item.get("target_category"):
            id_hint += f" und die Kategorie ist definitiv '{matched_item['target_category']}'"
        user_hint = f"[{id_hint}] {user_hint}" if user_hint else f"[{id_hint}]"
        try:
            db.insert_trace(doc_id, "pre_analysis", "success", f"Absender '{matched_sender}' deterministisch über ID '{matched_item['identifier_value']}' verifiziert.", {"matched_sender": matched_sender, "identifier_value": matched_item['identifier_value']})
        except Exception:
            pass

    # Phase 5: LLM classification
    data = classify_document(
        safe_text,
        filename=os.path.basename(file_path),
        user_hint=user_hint,
        feature_prompt=feature_prompt,
        similar_docs=similar_docs,
        header_zone=features.get("header_zone")
    )

    if data:
        # Overwrite with deterministic match to guarantee 100% correctness and avoid AI-drift
        if matched_sender:
            data["sender"] = matched_sender
            if matched_item.get("target_category"):
                data["category"] = matched_item["target_category"]
            if matched_item.get("target_unit"):
                data["property_unit"] = matched_item["target_unit"]
            # Override confidence to high since the match is deterministically verified
            data["confidence"] = "high"
            data["confidence_reason"] = f"Absender deterministisch verifiziert über ID: {matched_item['identifier_value']}"
        else:
            # If no confirmed identifier matched, scan and record potential new unassigned ones for the inbox
            from pipeline.steps import extract_and_match_identifiers
            # Call extract_and_match_identifiers only to scan and record novel unassigned IDs
            # (it won't return anything since we already checked matching above)
            extract_and_match_identifiers(text, doc_id)

    if data is None:
        os.makedirs(REVIEW_DIR, exist_ok=True)
        dest_pdf = unique_path(os.path.join(REVIEW_DIR, os.path.basename(file_path)))
        shutil.move(file_path, dest_pdf)
        log(f"Alle Versuche fehlgeschlagen. Zur manuellen Pruefung verschoben nach: {dest_pdf}")
        log("--- Abgeschlossen (manuelle Pruefung erforderlich) ---")
        processing_log(os.path.basename(dest_pdf), "review")
        db.update_document(doc_id, file_path=dest_pdf, filename=os.path.basename(dest_pdf),
                           summary="FEHLER: LLM-Klassifizierung nach allen Versuchen fehlgeschlagen.",
                           status="review")
        try:
            db.insert_trace(doc_id, "llm_classification", "failed", "LLM-Klassifizierung nach allen Versuchen fehlgeschlagen. Datei zur manuellen Erfassung verschoben.", {"file_path": dest_pdf})
        except Exception:
            pass
        cleanup_empty_inbox_folders(file_path)
        return

    try:
        db.insert_trace(doc_id, "llm_classification", "success", f"Erfolgreich klassifiziert: {data.get('sender')} | {data.get('document_type')} | {data.get('category')} (Vertrauen: {data.get('confidence', 'low').upper()})", {"confidence": data.get("confidence"), "confidence_reason": data.get("confidence_reason"), "metadata": data})
    except Exception:
        pass

    data = apply_sender_overrides(data)
    category = data.get("category") or "Sonstiges"
    sender = data.get("sender")
    confidence = data.get("confidence", "low")
    confidence_reason = data.get("confidence_reason", "")

    # Phase 5b: Fuzzy duplicate check (Sender + Datum + Typ)
    fuzzy_match = check_fuzzy_duplicate(doc_id, sender, data.get("date"), data.get("document_type"))
    if fuzzy_match:
        log(f"WAHRSCHEINLICHES DUPLIKAT: Gleicher Absender/Datum/Typ wie '{os.path.basename(fuzzy_match['file_path'])}' – zur Prüfung verschoben.")
        confidence = "low"
        data["confidence"] = "low"
        data["notes"] = f"Wahrscheinliches Duplikat von: {os.path.basename(fuzzy_match['file_path'])} (gleicher Absender/Datum/Typ)"
        try:
            db.insert_trace(doc_id, "duplicate_check", "warning", f"Fuzzy-Duplikat erkannt (gleicher Absender/Datum/Typ wie '{os.path.basename(fuzzy_match['file_path'])}'). Vertrauen auf LOW gesetzt.", {"original_id": fuzzy_match["id"]})
        except Exception:
            pass
    elif sim_duplicate_note:
        confidence = "low"
        data["confidence"] = "low"
        data["notes"] = sim_duplicate_note

    if user_hint and os.path.exists(hint_path):
        try:
            os.remove(hint_path)
        except Exception:
            pass

    new_name = os.path.basename(file_path)

    db.update_document(doc_id, sim_hash=doc_sim_hash)

    # Phase 6: File placement + DB update (transactional)
    dest_pdf = None
    try:
        dest_pdf, final_status, log_status, log_msg, log_fin = _stage_or_archive(file_path, new_name, confidence, data)

        if dest_pdf is None:
            log(f"WARNUNG: Quelldatei nicht mehr vorhanden (wurde während der Verarbeitung verschoben/gelöscht?): {file_path}")
            db.update_document(doc_id, status="failed", summary="FEHLER: Quelldatei verschwunden während der LLM-Verarbeitung.")
            try:
                db.insert_trace(doc_id, "archiving", "failed", "Quelldatei verschwunden während der LLM-Verarbeitung.")
            except Exception:
                pass
            return

        processing_log(os.path.basename(dest_pdf), log_status, data=data, features=features, user_hint=user_hint)
        db.update_document(
            doc_id,
            file_path=dest_pdf,
            filename=os.path.basename(dest_pdf),
            sender=sender,
            date=data.get("date"),
            document_type=data.get("document_type"),
            category=category,
            property_unit=data.get("property_unit"),
            vehicle_id=data.get("vehicle_id"),
            child_name=data.get("child_name"),
            summary=data.get("summary"),
            content_hash=doc_content_hash,
            status=final_status,
            low_value=data.get("low_value", 0),
            full_text=safe_text,
            iban=data.get("iban"),
        )
        try:
            db.insert_trace(doc_id, "archiving", "success", f"Dokument erfolgreich abgelegt (Status: '{final_status}'). Ziel-Pfad: {dest_pdf}", {"file_path": dest_pdf, "status": final_status})
        except Exception:
            pass
        log(log_msg)
        log(log_fin)
    except Exception as db_err:
        log(f"FEHLER: Dateisystem-DB Transaktionsfehler. Starte Rollback... (Fehler: {db_err})")
        try:
            db.insert_trace(doc_id, "archiving", "failed", f"DB-Transaktionsfehler beim Archivieren: {db_err}. Rollback gestartet...", {"error": str(db_err)})
        except Exception:
            pass
        if dest_pdf and os.path.exists(dest_pdf):
            try:
                os.makedirs(FAILED_DIR, exist_ok=True)
                rollback_dest = unique_path(os.path.join(FAILED_DIR, os.path.basename(dest_pdf)))
                shutil.move(dest_pdf, rollback_dest)
                log(f"Rollback: Datei in failed/ verschoben: {rollback_dest}")
                try:
                    db.update_document(doc_id, file_path=rollback_dest,
                                       filename=os.path.basename(rollback_dest),
                                       status="failed",
                                       summary=f"FEHLER: DB-Transaktionsfehler beim Archivieren ({db_err})")
                    db.insert_trace(doc_id, "archiving", "failed", f"Rollback abgeschlossen. Datei gesichert unter failed/", {"rollback_path": rollback_dest})
                except Exception as db_write_err:
                    log(f"WARNUNG: Rollback-Datei in failed/ verschoben, aber DB-Status-Update fehlgeschlagen (DB gesperrt/offline): {db_write_err}")
            except Exception as rollback_err:
                log(f"FATAL: Rollback fehlgeschlagen, Datei festgefahren unter {dest_pdf}! (Fehler: {rollback_err})")
        return
    finally:
        if dest_pdf:
            generate_thumbnail(dest_pdf, doc_id)
            cleanup_empty_inbox_folders(file_path)

    if final_status == "ok" and sender:
        record_sender(category, sender)

    # Phase 7: Post-processing (confidence notes, keyword validation)
    notes = f"[Vertrauen: {confidence.upper()}] {confidence_reason}"
    db.update_document(doc_id, notes=notes)
    if data.get("keywords"):
        validated_kw = filter_keywords_against_text(data["keywords"], text)
        if validated_kw:
            db.update_document(doc_id, keywords=validated_kw)

    # Phase 8b: Contract extraction for contract documents
    CONTRACT_TYPES = {"Vertrag", "Kündigung", "Mahnung", "Abonnement"}
    if final_status == "ok" and data.get("document_type") in CONTRACT_TYPES:
        try:
            from llm import extract_contract_from_document
            from db.contracts_repo import has_contract_for_document, insert_contract
            from datetime import datetime as _dt2
            if not has_contract_for_document(doc_id):
                contract = extract_contract_from_document(
                    text=safe_text,
                    filename=os.path.basename(dest_pdf),
                    sender=sender or "",
                    doc_type=data.get("document_type") or "",
                )
                if contract:
                    insert_contract(doc_id, contract, extracted_at=_dt2.now().isoformat(timespec="seconds"))
                    log(f"[CONTRACTS] Vertragsdaten gespeichert: '{contract.get('partner')}'")
                    try:
                        db.insert_trace(doc_id, "contract_extraction", "success", f"Vertragsdaten erfolgreich extrahiert für '{contract.get('partner')}'.", {"contract": contract})
                    except Exception:
                        pass
        except Exception as e:
            log(f"[CONTRACTS] Fehler bei Vertrags-Extraktion (ignoriert): {e}")
            try:
                db.insert_trace(doc_id, "contract_extraction", "failed", f"Fehler bei Vertrags-Extraktion (ignoriert): {e}")
            except Exception:
                pass

    # Phase 8c: Auto-Link deductible landlord documents to Tax Module (Proaktive Steuer-Verknüpfung)
    if final_status == "ok" and category in ("Haus_Gemeinkosten", "OG_Miete", "DG_Miete"):
        try:
            import db.tax_years_repo as tax_years_repo
            import db.tax_documents_repo as tax_documents_repo
            raw_date = str(data.get("date") or "")
            year_match = re.search(r'\b(\d{4})\b', raw_date)
            if year_match:
                year_num = int(year_match.group())
                year_row = tax_years_repo.get_by_year(year_num)
                if year_row:
                    tax_year_id = year_row["id"]
                else:
                    tax_year_id = tax_years_repo.insert(year_num, status="draft", notes=f"Vollautomatisch erstellt für Beleg {doc_id}")

                existing_link = tax_documents_repo.get_by_year_and_document(tax_year_id, doc_id, source_type="assessment_notice")
                if not existing_link:
                    tax_documents_repo.insert(
                        tax_year_id=tax_year_id,
                        document_id=doc_id,
                        source_type="assessment_notice",
                        verified=False
                    )
                    log(f"[TAX_LINKER] Beleg {doc_id} vollautomatisch mit Steuerjahr {year_num} verknüpft.")
                    try:
                        db.insert_trace(doc_id, "tax_linker", "success", f"Beleg automatisch mit Steuerjahr {year_num} verknüpft.")
                    except Exception:
                        pass
        except Exception as te:
            log(f"[TAX_LINKER] Fehler bei automatischer Steuer-Verknüpfung (ignoriert): {te}")
            try:
                db.insert_trace(doc_id, "tax_linker", "failed", f"Fehler bei automatischer Steuer-Verknüpfung: {te}")
            except Exception:
                pass

    # Phase 8: Extraction pipeline – routed by document_type
    doc_type = data.get("document_type")
    INVOICE_TYPES = {"Warenrechnung", "Dienstleistungsrechnung"}
    if final_status == "ok" and doc_type in INVOICE_TYPES:
        try:
            from llm import extract_items_from_invoice, extract_services_from_invoice
            from db.items_repo import has_items_for_document, insert_items
            from db.services_repo import has_services_for_document, insert_services
            from datetime import datetime as _dt
            fname = os.path.basename(dest_pdf)
            inv_date = data.get("date") or ""

            # Route: Warenrechnung → try Items
            if doc_type == "Warenrechnung" and not has_items_for_document(doc_id):
                items = extract_items_from_invoice(
                    text=safe_text, filename=fname,
                    vendor=sender or "", purchase_date=inv_date,
                )
                if items:
                    n = insert_items(doc_id, items, extracted_at=_dt.now().isoformat(timespec="seconds"))
                    log(f"[ITEMS] {n} Artikel in Inventar eingetragen.")
                    try:
                        db.insert_trace(doc_id, "items_extraction", "success", f"{n} Artikel extrahiert und im Inventar gespeichert.", {"items_count": n, "items": items})
                    except Exception:
                        pass

            # Route: Dienstleistungsrechnung → try Services
            if doc_type == "Dienstleistungsrechnung" and not has_services_for_document(doc_id):
                services = extract_services_from_invoice(
                    text=safe_text, filename=fname,
                    vendor=sender or "", invoice_date=inv_date,
                )
                if services:
                    n = insert_services(doc_id, services, extracted_at=_dt.now().isoformat(timespec="seconds"))
                    log(f"[SERVICES] {n} Dienstleistungen in Ausgaben eingetragen.")
                    try:
                        db.insert_trace(doc_id, "services_extraction", "success", f"{n} Dienstleistungen extrahiert und in Ausgaben gespeichert.", {"services_count": n, "services": services})
                    except Exception:
                        pass

                    # Mathematischer Summen-Validator (Datenintegrität)
                    try:
                        total_services_sum = sum(s.get("amount") or 0.0 for s in services)
                        import re as _re
                        total_matches = _re.findall(r'(?:gesamt|brutto|summe|endbetrag|rechnungsbetrag|gesamtbetrag)[\s:]*([0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{2}))', safe_text.lower())
                        if total_matches:
                            invoice_total = float(total_matches[0].replace(".", "").replace(",", "."))
                            if abs(total_services_sum - invoice_total) > 0.05:
                                warn_msg = f"Achtung: Mathematische Summen-Inkonsistenz! Die Summe der extrahierten Dienstleistungen ({total_services_sum:.2f} EUR) weicht vom erkannten Rechnungsbetrag ({invoice_total:.2f} EUR) ab."
                                db.update_document(doc_id, notes=warn_msg)
                                log(f"[SERVICES_VALIDATOR] {warn_msg}")
                                try:
                                    db.insert_trace(doc_id, "services_extraction", "warning", f"Mathematische Summen-Inkonsistenz! Summe extrahierter Leistungen ({total_services_sum:.2f} EUR) weicht von Rechnungsbetrag ({invoice_total:.2f} EUR) ab.", {"services_sum": total_services_sum, "invoice_total": invoice_total})
                                except Exception:
                                    pass
                    except Exception as ve:
                        log(f"[SERVICES_VALIDATOR] Mathematische Validierung fehlgeschlagen: {ve}")
        except Exception as e:
            log(f"[PIPELINE] Fehler bei Extraktion (ignoriert): {e}")
            try:
                db.insert_trace(doc_id, "items_extraction" if doc_type == "Warenrechnung" else "services_extraction", "failed", f"Fehler bei Extraktion (ignoriert): {e}")
            except Exception:
                pass


def reindex_from_archive():
    from storage import record_sender as _record
    log(f"Reindex: Lese bestehende JSON-Sidecar-Dateien aus {TARGET_BASE}...")
    skip_dirs = {DUPLICATES_DIR, FAILED_DIR, ENCRYPTED_DIR}
    count = 0
    skipped = 0
    for root, dirs, files in os.walk(TARGET_BASE):
        dirs[:] = [
            d for d in dirs
            if os.path.abspath(os.path.join(root, d)) not in {os.path.abspath(p) for p in skip_dirs}
        ]
        for f in files:
            if not f.lower().endswith(".json"):
                continue
            json_path = os.path.join(root, f)
            try:
                with open(json_path, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                sender = data.get("sender")
                category = data.get("category")
                if sender and category and category in CATEGORIES:
                    _record(category, sender)
                    count += 1
                else:
                    skipped += 1
            except Exception as e:
                log(f"  Fehler beim Lesen von {f}: {e}")
    log(f"Reindex abgeschlossen: {count} Eintraege verarbeitet, {skipped} uebersprungen.")
