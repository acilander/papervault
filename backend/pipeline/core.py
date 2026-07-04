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
    detect_receipt
)
from llm import classify_document, filter_keywords_against_text
from storage import record_sender, apply_sender_overrides, processing_log
import db
from utils import log
from pipeline.steps import check_duplicate

def _register_doc(file_path: str, doc_id) -> int:
    """Ensure document has a DB identity. Returns doc_id."""
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
    db.update_document(doc_id, status="processing")
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
        db.update_document(doc_id, file_path=dest, filename=os.path.basename(dest),
                           summary="VERSCHLUESSELT: Das PDF-Dokument ist passwortgeschützt.", status="encrypted")
        return None, None

    if status == "corrupt":
        os.makedirs(FAILED_DIR, exist_ok=True)
        dest = unique_path(os.path.join(FAILED_DIR, os.path.basename(file_path)))
        shutil.move(file_path, dest)
        log(f"FEHLER: PDF nicht lesbar (korrupt). Verschoben nach: {dest}")
        log("--- Abgeschlossen (fehlgeschlagen) ---")
        processing_log(os.path.basename(file_path), "corrupt")
        db.update_document(doc_id, file_path=dest, filename=os.path.basename(dest),
                           summary="FEHLER: PDF-Datei ist nicht lesbar (Datei beschädigt oder ungültig).", status="corrupt")
        return None, None

    log(f"PyMuPDF: {len(text.strip())} Zeichen gefunden.")

    if len(text.strip()) < 50:
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
        return None, None

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
            + ". Klassifiziere als document_type=Rechnung und category=Kassenbon & Quittung, "
            "es sei denn die gekauften Artikel sind eindeutig einer anderen Kategorie zuzuordnen "
            "(z.B. Wohnen & Eigentum fuer Baumaterial, Fahrzeug & Werkstatt fuer Autoteile)."
        )
        log(f"Kassenbon erkannt – LLM-Hinweis gesetzt. Absender: {receipt_sender}")

    return user_hint, hint_path


def _stage_or_archive(file_path: str, new_name: str, confidence: str, data: dict):
    """Move file to review/ or archive directly. Returns (dest_pdf, status, log_status, log_msg, log_fin)."""
    if confidence == "high" and data.get("date") and data.get("date") != "null":
        log("[AUTO-ARCHIV] Hohes Vertrauen verifiziert. Archiviere Dokument direkt...")
        from pipeline.steps import archive_file_on_disk
        dest_pdf = archive_file_on_disk(file_path, data.get("category") or "Sonstiges", data.get("sender"), data.get("date"))
        return dest_pdf, "ok", "auto_archived", f"[AUTO-ARCHIV] Erfolgreich einsortiert nach: {dest_pdf}", "--- Abgeschlossen (automatisch archiviert) ---"
    else:
        os.makedirs(REVIEW_DIR, exist_ok=True)
        dest_pdf = unique_path(os.path.join(REVIEW_DIR, new_name))
        if not os.path.exists(file_path):
            return None, None, None, None, None
        shutil.move(file_path, dest_pdf)
        return dest_pdf, "review", "review", f"Bereit zur Pruefung – verschoben nach: {dest_pdf}", "--- Abgeschlossen (wartet auf Bestaetigung) ---"


def process_pdf(file_path, doc_id=None):
    log(f"--- Neue Datei: {os.path.basename(file_path)} ---")

    # Phase 1: DB identity
    doc_id = _register_doc(file_path, doc_id)

    if not os.path.exists(file_path):
        log(f"WARNUNG: Datei nicht gefunden beim Start der Verarbeitung (bereits verschoben?): {file_path}")
        db.update_document(doc_id, status="failed", summary="FEHLER: Datei beim Start der Verarbeitung nicht gefunden.")
        return

    # Phase 2: Text extraction
    text, _ = _extract_text(file_path, doc_id)
    if text is None:
        return

    # Phase 3: Duplicate check
    if check_duplicate(file_path, text, doc_id):
        return
    doc_content_hash = getattr(check_duplicate, 'last_hash', None)

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

    # Phase 5: LLM classification
    data = classify_document(
        safe_text,
        filename=os.path.basename(file_path),
        user_hint=user_hint,
        feature_prompt=feature_prompt,
        similar_docs=similar_docs,
        header_zone=features.get("header_zone")
    )

    if data is None:
        os.makedirs(FAILED_DIR, exist_ok=True)
        dest_pdf = unique_path(os.path.join(FAILED_DIR, os.path.basename(file_path)))
        shutil.move(file_path, dest_pdf)
        log(f"Alle Versuche fehlgeschlagen. Verschoben nach: {dest_pdf}")
        log("--- Abgeschlossen (fehlgeschlagen) ---")
        processing_log(os.path.basename(file_path), "classification_failed")
        db.update_document(doc_id, file_path=dest_pdf, filename=os.path.basename(dest_pdf),
                           summary="FEHLER: LLM-Klassifizierung nach allen Versuchen fehlgeschlagen.",
                           status="classification_failed")
        return

    data = apply_sender_overrides(data)
    category = data.get("category") or "Sonstiges"
    sender = data.get("sender")
    confidence = data.get("confidence", "low")
    confidence_reason = data.get("confidence_reason", "")

    if user_hint and os.path.exists(hint_path):
        try:
            os.remove(hint_path)
        except Exception:
            pass

    new_name = os.path.basename(file_path)

    # Phase 6: File placement + DB update (transactional)
    try:
        dest_pdf, final_status, log_status, log_msg, log_fin = _stage_or_archive(file_path, new_name, confidence, data)

        if dest_pdf is None:
            log(f"WARNUNG: Quelldatei nicht mehr vorhanden (wurde während der Verarbeitung verschoben/gelöscht?): {file_path}")
            db.update_document(doc_id, status="failed", summary="FEHLER: Quelldatei verschwunden während der LLM-Verarbeitung.")
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
            summary=data.get("summary"),
            content_hash=doc_content_hash,
            status=final_status,
            low_value=data.get("low_value", 0),
            full_text=safe_text,
        )
    except Exception as db_err:
        log(f"FEHLER: Dateisystem-DB Transaktionsfehler. Starte Rollback... (Fehler: {db_err})")
        if 'dest_pdf' in locals() and dest_pdf and os.path.exists(dest_pdf):
            try:
                shutil.move(dest_pdf, file_path)
                log(f"Rollback erfolgreich: Datei zurückverschoben nach {file_path}")
            except Exception as rollback_err:
                log(f"FATAL: Rollback fehlgeschlagen, Datei festgefahren unter {dest_pdf}! (Fehler: {rollback_err})")
        raise

    # Phase 7: Post-processing (confidence notes, keyword validation)
    notes = f"[Vertrauen: {confidence.upper()}] {confidence_reason}"
    db.update_document(doc_id, notes=notes)
    if data.get("keywords"):
        validated_kw = filter_keywords_against_text(data["keywords"], text)
        if validated_kw:
            db.update_document(doc_id, keywords=validated_kw)

    log(log_msg)
    log(log_fin)


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
