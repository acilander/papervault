import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime

from config import (
    TARGET_BASE, DUPLICATES_DIR, FAILED_DIR, ENCRYPTED_DIR,
    CATEGORY_FOLDER_MAP, SENDER_SUBFOLDERS, CATEGORIES,
)
from pdf_utils import extract_text, ocr_pdf, prepare_text_for_llm, is_cryptic_filename, build_filename, unique_path, extract_features, build_feature_prompt
from llm import classify_document, filter_keywords_against_text
from storage import content_hashes, save_hashes, record_sender, apply_sender_overrides, processing_log
import db


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def create_shortcut(target_path, shortcut_path):
    try:
        ps_cmd = (
            f'$ws = New-Object -ComObject WScript.Shell; '
            f'$s = $ws.CreateShortcut("{shortcut_path}"); '
            f'$s.TargetPath = "{target_path}"; '
            f'$s.Save()'
        )
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
    except Exception as e:
        log(f"Shortcut konnte nicht erstellt werden: {e}")


def check_duplicate(file_path, text):
    content_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]
    check_duplicate.last_hash = content_hash  # expose hash to caller
    if content_hash in content_hashes:
        existing_path = content_hashes[content_hash]
        dup_dir = os.path.join(DUPLICATES_DIR, content_hash)
        os.makedirs(dup_dir, exist_ok=True)
        log(f"DUPLIKAT erkannt (Hash: {content_hash}) – identisch mit: {os.path.basename(existing_path)}")

        dest = unique_path(os.path.join(dup_dir, os.path.basename(file_path)))
        shutil.move(file_path, dest)
        log(f"Duplikat verschoben nach: {dest}")

        if os.path.exists(existing_path):
            shortcut_name = "ORIGINAL - " + os.path.splitext(os.path.basename(existing_path))[0] + ".lnk"
            shortcut_path = os.path.join(dup_dir, shortcut_name)
            if not os.path.exists(shortcut_path):
                create_shortcut(os.path.abspath(existing_path), shortcut_path)
                log(f"Shortcut zum Original erstellt: {shortcut_name}")

        log("--- Abgeschlossen (als Duplikat) ---")
        return True

    content_hashes[content_hash] = file_path
    save_hashes()
    return False


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
    folder_name = CATEGORY_FOLDER_MAP.get(category, category)
    raw_date = str(data.get("date") or "")
    year_match = re.search(r'\b(\d{4})\b', raw_date)
    year = year_match.group() if year_match else "Unbekannt"
    sender = data.get("sender")

    if SENDER_SUBFOLDERS and sender:
        safe_sender = re.sub(r'[\\/:*?"<>|]', '_', sender)[:50].strip()
        target_dir = os.path.join(TARGET_BASE, folder_name, safe_sender, year)
    else:
        target_dir = os.path.join(TARGET_BASE, folder_name, year)
    os.makedirs(target_dir, exist_ok=True)

    original_name = os.path.basename(file_path)
    if is_cryptic_filename(original_name):
        new_name = build_filename(data, original_name)
        log(f"Kryptischer Dateiname erkannt – umbenannt zu: {new_name}")
    else:
        new_name = original_name

    dest_pdf = unique_path(os.path.join(target_dir, new_name))

    shutil.move(file_path, dest_pdf)

    record_sender(category, data.get("sender"))
    processing_log(os.path.basename(dest_pdf), "ok", data=data, features=features, user_hint=user_hint)
    doc_id = db.upsert_document(
        file_path=dest_pdf,
        filename=os.path.basename(dest_pdf),
        sender=data.get("sender"),
        date=data.get("date"),
        document_type=data.get("document_type"),
        category=category,
        summary=data.get("summary"),
        content_hash=doc_content_hash,
        status="ok",
    )
    if doc_id and data.get("keywords"):
        validated_kw = filter_keywords_against_text(data["keywords"], text)
        if validated_kw:
            db.update_document(doc_id, keywords=validated_kw)

    log(f"Fertig – verschoben nach: {dest_pdf}")
    log("--- Abgeschlossen ---")


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
