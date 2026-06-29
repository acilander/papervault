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
