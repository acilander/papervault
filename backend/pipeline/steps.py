import hashlib
import os
import shutil
import subprocess
from config import DUPLICATES_DIR, IGNORED_DIR
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


def compute_content_hash(file_path: str, text: str) -> tuple[str, str]:
    """Compute the same content hash used for duplicate detection.

    Returns (hash, type) where type is 'text' or 'binary'.
    """
    cleaned_text = text.strip()
    
    # Check if filename or text indicates a periodic recurring document
    # where text-based duplicate collisions are highly likely (e.g. payslips, bank statements)
    from utils import is_periodic_document
    is_periodic = is_periodic_document("", os.path.basename(file_path or ""), cleaned_text)

    if len(cleaned_text) >= 100 and not is_periodic:
        content_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()[:16]
        hash_type = "text"
    else:
        # [Fix: False-Collision Prevention]
        # If text is too short or empty (e.g., OCR failed or broken PDF), or the document is periodic,
        # fall back to binary file hashing to prevent false duplicate collisions on generic text or boilerplate.
        try:
            with open(file_path, "rb") as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()[:16]
            hash_type = "binary"
        except Exception:
            content_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()[:16]
            hash_type = "text"
    return content_hash, hash_type


def check_duplicate(file_path, text, doc_id):
    content_hash, hash_type = compute_content_hash(file_path, text)

    check_duplicate.last_hash = content_hash  # expose hash to caller
    check_duplicate.last_fuzzy_match = None   # expose fuzzy match to caller

    import db as _db

    # --- Protected hash check (ignored / locked) ---
    protected = _db.get_protected_hash(content_hash)
    if protected:
        if protected["type"] == "ignored":
            os.makedirs(IGNORED_DIR, exist_ok=True)
            dest = unique_path(os.path.join(IGNORED_DIR, os.path.basename(file_path)))
            shutil.move(file_path, dest)
            log(f"IGNORIERT ({hash_type.upper()}-Hash: {content_hash}) – in ignored/ verschoben")
            _db.update_document(
                doc_id,
                file_path=dest,
                filename=os.path.basename(dest),
                summary=f"IGNORIERT: Hash steht auf der Ignorieren-Liste.",
                status="ignored",
                content_hash=content_hash,
            )
            try:
                _db.insert_trace(doc_id, "duplicate_check", "skipped", "Dokument steht auf der Ignorieren-Liste. Import übersprungen.", {"hash": content_hash, "type": "ignored"})
            except Exception:
                pass
            cleanup_empty_inbox_folders(file_path)
            return True

        if protected["type"] == "locked":
            dup_dir = os.path.join(DUPLICATES_DIR, content_hash)
            os.makedirs(dup_dir, exist_ok=True)
            dest = unique_path(os.path.join(dup_dir, os.path.basename(file_path)))
            shutil.move(file_path, dest)
            log(f"DUPLIKAT VON GESPERRTEM DOKUMENT ({hash_type.upper()}-Hash: {content_hash})")
            original_doc = _db.get_document(protected["document_id"]) if protected.get("document_id") else None
            original_name = os.path.basename(original_doc["file_path"]) if original_doc else "gesperrtes Original"
            _db.update_document(
                doc_id,
                file_path=dest,
                filename=os.path.basename(dest),
                summary=f"DUPLIKAT: Identisch mit gesperrtem Original '{original_name}' (Hash: {content_hash})",
                status="duplicate",
                content_hash=content_hash,
            )
            try:
                _db.insert_trace(doc_id, "duplicate_check", "skipped", f"Identisch mit gesperrtem Original '{original_name}'.", {"hash": content_hash, "original_id": protected.get("document_id")})
            except Exception:
                pass
            cleanup_empty_inbox_folders(file_path)
            return True

    # --- Exact hash match ---
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

        _db.update_document(
            doc_id,
            file_path=dest,
            filename=os.path.basename(dest),
            summary=f"DUPLIKAT: Identisch mit '{os.path.basename(existing_path)}' (Hash: {content_hash})",
            status="duplicate"
        )
        try:
            _db.insert_trace(doc_id, "duplicate_check", "skipped", f"Identisch mit bereits archiviertem Beleg '{os.path.basename(existing_path)}'.", {"hash": content_hash, "original_id": existing_doc["id"]})
        except Exception:
            pass

        cleanup_empty_inbox_folders(file_path)
        return True

    try:
        _db.insert_trace(doc_id, "duplicate_check", "success", "Inhalts-Prüfung abgeschlossen. Keine exakten Duplikate gefunden.", {"hash": content_hash, "hash_type": hash_type})
    except Exception:
        pass
    return False


def check_fuzzy_duplicate(doc_id, sender, date, document_type):
    """Check for probable duplicate by matching sender + date + document_type.
    Returns the existing document if a match is found, else None."""
    if not sender or not date or not document_type:
        return None
    import db as _db
    from db.connection import get_conn as _get_conn
    with _get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM documents
               WHERE sender = ? AND date = ? AND document_type = ?
                 AND status IN ('ok', 'review')
                 AND id != ?
               LIMIT 1""",
            (sender, date, document_type, doc_id)
        ).fetchone()
    if row:
        check_duplicate.last_fuzzy_match = dict(row)
        return dict(row)
    return None


def archive_file_on_disk(file_path, category, sender, date, document_type=None, iban=None):
    """Generates the correct final TARGET_BASE folder path and moves the file there.
    Returns the final destination file path."""
    import re
    import shutil
    from config import TARGET_BASE, CATEGORY_FOLDER_MAP, SENDER_SUBFOLDERS
    from categories import CATEGORIES_CONFIG
    from pdf_utils import unique_path

    category = category or "Sonstiges"
    folder_name = CATEGORY_FOLDER_MAP.get(category, category)
    config = CATEGORIES_CONFIG.get(category, {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None})
    root_dir = config.get("root", "1_Privat_und_Alltag")
    use_year = config.get("use_year_folder", True)

    full_folder_name = os.path.join(root_dir, folder_name)

    raw_date = str(date or "")
    year_match = re.search(r'\b(\d{4})\b', raw_date)
    year = year_match.group() if year_match else "Unbekannt"

    safe_sender = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', sender)[:50].strip() if sender else None

    # Check if this is an outgoing document from the landlord/owner
    from config import OWNER_NAMES
    if safe_sender and any(owner in safe_sender.lower() for owner in OWNER_NAMES):
        safe_sender = "00_Ausgehend_Vermieter"

    if category == "Bank & Finanzen" and SENDER_SUBFOLDERS and safe_sender:
        subtype = "Kontoauszüge" if document_type == "Kontoauszug" else "Dokumente"
        if iban:
            safe_iban = re.sub(r'[^A-Z0-9]', '', iban.upper())[:34]
            if use_year:
                target_dir = os.path.join(TARGET_BASE, full_folder_name, safe_sender, safe_iban, subtype, year)
            else:
                target_dir = os.path.join(TARGET_BASE, full_folder_name, safe_sender, safe_iban, subtype)
        else:
            if use_year:
                target_dir = os.path.join(TARGET_BASE, full_folder_name, safe_sender, subtype, year)
            else:
                target_dir = os.path.join(TARGET_BASE, full_folder_name, safe_sender, subtype)
    elif SENDER_SUBFOLDERS and safe_sender:
        if use_year:
            target_dir = os.path.join(TARGET_BASE, full_folder_name, safe_sender, year)
        else:
            target_dir = os.path.join(TARGET_BASE, full_folder_name, safe_sender)
    else:
        if use_year:
            target_dir = os.path.join(TARGET_BASE, full_folder_name, year)
        else:
            target_dir = os.path.join(TARGET_BASE, full_folder_name)

    os.makedirs(target_dir, exist_ok=True)

    target_path = os.path.join(target_dir, os.path.basename(file_path))
    if os.path.normcase(os.path.abspath(file_path)) == os.path.normcase(os.path.abspath(target_path)):
        return file_path

    dest_pdf = unique_path(target_path)
    shutil.move(file_path, dest_pdf)
    return dest_pdf


def extract_first_date(text: str) -> str | None:
    """Extracts the first valid German date (DD.MM.YYYY or DD.MM.YY) and converts it to YYYY-MM-DD."""
    if not text:
        return None
    import re
    from datetime import datetime
    match = re.search(r'\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b', text)
    if match:
        d, m, y = match.groups()
        if len(y) == 2:
            y = "20" + y
        try:
            dt = datetime(int(y), int(m), int(d))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def extract_and_match_identifiers(text: str, doc_id: int) -> dict | None:
    """
    1. Checks if raw text matches any verified identifier in sender_identifiers.
       If yes, returns pre-filled classification data (bypassing the LLM).
    2. Extracts potential novel identifiers (IBANs, Meter IDs, Customer Nos) and
       saves them to unassigned_identifiers for manual review.
    """
    import re
    from db.identifiers_repo import match_existing_identifiers, save_unassigned_identifier
    from config_manager import get_settings

    # Phase 1: Match existing verified identifier
    matched_sender, item = match_existing_identifiers(text)
    if matched_sender:
        detected_date = extract_first_date(text)
        log(f"[IDENTIFIER] Deterministischen Absender '{matched_sender}' über ID '{item['identifier_value']}' erkannt.")
        return {
            "sender": matched_sender,
            "category": item.get("target_category") or "Sonstiges",
            "document_type": "Sonstiges",
            "property_unit": item.get("target_unit"),
            "date": detected_date,
            "summary": f"Automatisch erfasst über verifizierten Identifikator '{item['identifier_value']}'.",
            "confidence": "high",
            "confidence_reason": f"Absender automatisch verifiziert über ID: {item['identifier_value']}",
            "low_value": 0,
            "keywords": "",
            "iban": item["identifier_value"] if item["identifier_type"] == "IBAN" else None
        }

    # Phase 2: Scan and record new novel unassigned identifiers
    settings = get_settings()
    own_ibans = [iban.replace(" ", "").upper() for iban in settings.get("own_ibans", [])]

    # Convert text to uppercase and strip whitespace for precise IBAN detection
    text_upper = text.upper().replace(" ", "").replace("\n", "").replace("\r", "")

    # 2a. IBAN scanning
    ibans = re.findall(r'DE\d{20}', text_upper)
    for iban in ibans:
        if iban in own_ibans:
            continue

        # Extract context around the IBAN from the original spaced text
        raw_text_clean = text.replace(" ", "")
        pos = raw_text_clean.find(iban)
        context = ""
        if pos != -1:
            start = max(0, pos - 40)
            end = min(len(raw_text_clean), pos + len(iban) + 40)
            context = raw_text_clean[start:end]

        save_unassigned_identifier(doc_id, "IBAN", iban, context_text=f"...{context}...")

    # 2b. Meter IDs scanning (Zählernummern)
    meter_matches = re.finditer(r'(?:zähler-?nr|meter-?no|zählerstand)[^\d]{0,10}(\d{5,12})', text, re.IGNORECASE)
    for match in meter_matches:
        meter_val = match.group(1)
        # Context snippet
        start = max(0, match.start() - 30)
        end = min(len(text), match.end() + 30)
        context = text[start:end].strip().replace("\n", " ").replace("\r", "")
        save_unassigned_identifier(doc_id, "METER_ID", meter_val, context_text=f"...{context}...")

    # 2c. Customer numbers scanning (Kundennummern)
    customer_matches = re.finditer(r'(?:kunden-?nummer|kd-?nr)[^\d]{0,10}([A-Z0-9-]{5,15})', text, re.IGNORECASE)
    for match in customer_matches:
        cust_val = match.group(1)
        # Context snippet
        start = max(0, match.start() - 30)
        end = min(len(text), match.end() + 30)
        context = text[start:end].strip().replace("\n", " ").replace("\r", "")
        save_unassigned_identifier(doc_id, "CUSTOMER_NO", cust_val, context_text=f"...{context}...")

    return None

