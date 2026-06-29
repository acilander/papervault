import hashlib
import os
import shutil
import subprocess
from config import DUPLICATES_DIR
from pdf_utils import unique_path
from storage import content_hashes, save_hashes
from utils import log

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
    cleaned_text = text.strip()
    if len(cleaned_text) >= 100:
        content_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()[:16]
        hash_type = "text"
    else:
        # [Fix: False-Collision Prevention]
        # If text is too short or empty (e.g., OCR failed or broken PDF), 
        # fall back to binary file hashing to prevent false duplicate collisions on generic text like "Page 1".
        try:
            with open(file_path, "rb") as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()[:16]
            hash_type = "binary"
        except Exception:
            content_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()[:16]
            hash_type = "text"

    check_duplicate.last_hash = content_hash  # expose hash to caller
    if content_hash in content_hashes:
        existing_path = content_hashes[content_hash]
        dup_dir = os.path.join(DUPLICATES_DIR, content_hash)
        os.makedirs(dup_dir, exist_ok=True)
        log(f"DUPLIKAT erkannt ({hash_type.upper()}-Hash: {content_hash}) – identisch mit: {os.path.basename(existing_path)}")

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
        
        # Record duplicate in the SQLite database so it is visible in the UI and counted in the badges
        import db as _db
        _db.upsert_document(dest, os.path.basename(dest), None, None, None, None, f"DUPLIKAT: Identisch mit '{os.path.basename(existing_path)}' (Hash: {content_hash})", status="duplicate")

        return True

    content_hashes[content_hash] = file_path
    save_hashes()
    return False


def archive_file_on_disk(file_path, category, sender, date):
    """Generates the correct final TARGET_BASE folder path and moves the file there.
    Returns the final destination file path."""
    import re
    import shutil
    from config import TARGET_BASE, CATEGORY_FOLDER_MAP, SENDER_SUBFOLDERS
    from pdf_utils import unique_path
    
    category = category or "Sonstiges"
    folder_name = CATEGORY_FOLDER_MAP.get(category, category)
    raw_date = str(date or "")
    year_match = re.search(r'\b(\d{4})\b', raw_date)
    year = year_match.group() if year_match else "Unbekannt"

    if SENDER_SUBFOLDERS and sender:
        safe_sender = re.sub(r'[\\/:*?"<>|]', '_', sender)[:50].strip()
        target_dir = os.path.join(TARGET_BASE, folder_name, safe_sender, year)
    else:
        target_dir = os.path.join(TARGET_BASE, folder_name, year)
        
    os.makedirs(target_dir, exist_ok=True)

    dest_pdf = unique_path(os.path.join(target_dir, os.path.basename(file_path)))
    shutil.move(file_path, dest_pdf)
    return dest_pdf
