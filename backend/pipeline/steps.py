import hashlib
import os
import shutil
import subprocess
from config import DUPLICATES_DIR
from pdf_utils import unique_path
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


def cleanup_empty_inbox_folders(original_path: str) -> None:
    """Remove empty parent directories left behind after moving a file out of SOURCE_DIR.

    Stops at SOURCE_DIR itself and never deletes it. Only operates on paths that were
    originally inside SOURCE_DIR.
    """
    from config import SOURCE_DIR

    src_dir = os.path.dirname(os.path.abspath(original_path))
    source_dir = os.path.abspath(SOURCE_DIR)
    if not src_dir.startswith(source_dir + os.sep):
        return

    current = src_dir
    while current != source_dir:
        try:
            if os.path.isdir(current) and not os.listdir(current):
                os.rmdir(current)
            else:
                break
        except OSError:
            break
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent


def check_duplicate(file_path, text, doc_id):
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
    
    import db as _db
    existing_doc = _db.get_document_by_hash(content_hash)
    if existing_doc and existing_doc["id"] != doc_id:
        existing_path = existing_doc["file_path"]
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
        
        # Record duplicate in the SQLite database by updating the exact tracking ID
        _db.update_document(
            doc_id, 
            file_path=dest, 
            filename=os.path.basename(dest), 
            summary=f"DUPLIKAT: Identisch mit '{os.path.basename(existing_path)}' (Hash: {content_hash})", 
            status="duplicate"
        )

        cleanup_empty_inbox_folders(file_path)
        return True

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
