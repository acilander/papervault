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
    extract_text, ocr_pdf, prepare_text_for_llm, is_cryptic_filename,
    build_filename, unique_path, extract_features, build_feature_prompt,
    detect_receipt
)
from llm import classify_document, filter_keywords_against_text
from storage import record_sender, apply_sender_overrides, processing_log
import db
from utils import log
from pipeline.steps import check_duplicate

def process_pdf(file_path):
    log(f"--- Neue Datei: {os.path.basename(file_path)} ---")

    log("Extrahiere Text via PyMuPDF...")
    text, status = extract_text(file_path)

    if status == "encrypted":
        os.makedirs(ENCRYPTED_DIR, exist_ok=True)
        dest = unique_path(os.path.join(ENCRYPTED_DIR, os.path.basename(file_path)))
        shutil.move(file_path, dest)
        log(f"VERSCHLUESSELT: PDF ist passwortgeschuetzt. Verschoben nach: {dest}")
        log("--- Abgeschlossen (verschluesselt) ---")
        processing_log(os.path.basename(file_path), "encrypted")
        db.upsert_document(dest, os.path.basename(dest), None, None, None, None, None, status="encrypted")
        return

    if status == "corrupt":
        os.makedirs(FAILED_DIR, exist_ok=True)
        dest = unique_path(os.path.join(FAILED_DIR, os.path.basename(file_path)))
        shutil.move(file_path, dest)
        log(f"FEHLER: PDF nicht lesbar (korrupt). Verschoben nach: {dest}")
        log("--- Abgeschlossen (fehlgeschlagen) ---")
        processing_log(os.path.basename(file_path), "corrupt")
        db.upsert_document(dest, os.path.basename(dest), None, None, None, None, None, status="corrupt")
        return

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
        db.upsert_document(dest, os.path.basename(dest), None, None, None, None, None, status="no_text")
        return

    if check_duplicate(file_path, text):
        return
    doc_content_hash = getattr(check_duplicate, 'last_hash', None)

    safe_text = prepare_text_for_llm(text)

    # Structural pre-analysis
    features = extract_features(text, filename=os.path.basename(file_path), file_path=file_path)
    feature_prompt = build_feature_prompt(features)
    similar_docs = db.find_similar_by_features(
        features.get("category_candidates", []),
        features.get("type_candidate"),
    )
    log(f"Merkmale: {', '.join(features.get('category_candidates', [])) or '–'} | Typ: {features.get('type_candidate') or '–'}")

    # Read optional .hint sidecar file
    hint_path = os.path.splitext(file_path)[0] + ".hint"
    user_hint = None
    if os.path.exists(hint_path):
        try:
            with open(hint_path, "r", encoding="utf-8") as f:
                user_hint = f.read().strip()
            os.remove(hint_path)
            log(f"Benutzerhinweis geladen: {user_hint[:80]}")
        except Exception:
            pass

    # Receipt detection – add hint to LLM instead of bypassing it
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

    data = classify_document(safe_text, filename=os.path.basename(file_path), user_hint=user_hint,
                             feature_prompt=feature_prompt, similar_docs=similar_docs)

    if data is None:
        os.makedirs(FAILED_DIR, exist_ok=True)
        dest_pdf = unique_path(os.path.join(FAILED_DIR, os.path.basename(file_path)))
        shutil.move(file_path, dest_pdf)
        log(f"Alle Versuche fehlgeschlagen. Verschoben nach: {dest_pdf}")
        log("--- Abgeschlossen (fehlgeschlagen) ---")
        processing_log(os.path.basename(file_path), "classification_failed")
        db.upsert_document(dest_pdf, os.path.basename(dest_pdf), None, None, None, None, None, status="classification_failed")
        return

    data = apply_sender_overrides(data)

    category = data.get("category") or "Sonstiges"
    sender = data.get("sender")

    # Move to review/ staging area – confirmed via UI before final archiving
    os.makedirs(REVIEW_DIR, exist_ok=True)
    original_name = os.path.basename(file_path)
    if is_cryptic_filename(original_name):
        new_name = build_filename(data, original_name)
        log(f"Kryptischer Dateiname erkannt – umbenannt zu: {new_name}")
    else:
        new_name = original_name

    dest_pdf = unique_path(os.path.join(REVIEW_DIR, new_name))
    shutil.move(file_path, dest_pdf)

    processing_log(os.path.basename(dest_pdf), "review", data=data, features=features, user_hint=user_hint)
    doc_id = db.upsert_document(
        file_path=dest_pdf,
        filename=os.path.basename(dest_pdf),
        sender=sender,
        date=data.get("date"),
        document_type=data.get("document_type"),
        category=category,
        summary=data.get("summary"),
        content_hash=doc_content_hash,
        status="review",
    )
    if doc_id and data.get("keywords"):
        validated_kw = filter_keywords_against_text(data["keywords"], text)
        if validated_kw:
            db.update_document(doc_id, keywords=validated_kw)

    log(f"Bereit zur Pruefung – verschoben nach: {dest_pdf}")
    log("--- Abgeschlossen (wartet auf Bestaetigung) ---")


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
