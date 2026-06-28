"""
Einmaliges Migrationsskript: liest alle JSON-Sidecar-Dateien aus dem Archiv
und fuegt sie in die SQLite-Datenbank ein.

Verwendung:
    python migrate_to_db.py
    python migrate_to_db.py --dry-run
"""
import json
import os
import sys
from datetime import datetime

from config import TARGET_BASE, DUPLICATES_DIR, FAILED_DIR, ENCRYPTED_DIR, SENDERS_FILE
import db

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DRY_RUN = "--dry-run" in sys.argv
SKIP_DIRS = {
    os.path.abspath(DUPLICATES_DIR),
    os.path.abspath(FAILED_DIR),
    os.path.abspath(ENCRYPTED_DIR),
}

SPECIAL_DIRS = [
    (FAILED_DIR, "classification_failed"),
    (ENCRYPTED_DIR, "encrypted"),
    (DUPLICATES_DIR, "duplicate"),
]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    log(f"Migration gestartet. Archiv: {TARGET_BASE}")
    if DRY_RUN:
        log("DRY-RUN: Keine Änderungen werden gespeichert.")

    if not DRY_RUN:
        db.init_db()

    ok = 0
    skipped = 0
    errors = 0

    for root, dirs, files in os.walk(TARGET_BASE):
        # Skip special directories
        dirs[:] = [
            d for d in dirs
            if os.path.abspath(os.path.join(root, d)) not in SKIP_DIRS
        ]

        for f in files:
            if not f.lower().endswith(".json"):
                continue
            # Skip senders.json and other non-sidecar JSONs
            json_path = os.path.join(root, f)
            if os.path.abspath(json_path) == os.path.abspath(SENDERS_FILE):
                continue

            pdf_path = os.path.splitext(json_path)[0] + ".pdf"
            if not os.path.exists(pdf_path):
                skipped += 1
                continue

            try:
                with open(json_path, "r", encoding="utf-8") as jf:
                    data = json.load(jf)

                # Skip error-only sidecars (failed classifications)
                if "error" in data and len(data) <= 2:
                    skipped += 1
                    continue

                sender = data.get("sender")
                date = data.get("date")
                document_type = data.get("document_type")
                category = data.get("category")
                summary = data.get("summary")

                # Try to get archived_at from file mtime as fallback
                mtime = os.path.getmtime(pdf_path)
                archived_at = datetime.fromtimestamp(mtime).isoformat(timespec="seconds")

                if DRY_RUN:
                    log(f"  [DRY] {os.path.basename(pdf_path)} | {category} | {sender}")
                else:
                    db.upsert_document(
                        file_path=pdf_path,
                        filename=os.path.basename(pdf_path),
                        sender=sender,
                        date=str(date) if date else None,
                        document_type=document_type,
                        category=category,
                        summary=summary,
                        content_hash=None,
                        status="ok",
                        archived_at=archived_at,
                    )

                ok += 1

            except Exception as e:
                log(f"  FEHLER bei {f}: {e}")
                errors += 1

    # Scan failed/ and encrypted/ directories
    for special_dir, status_label in SPECIAL_DIRS:
        if not os.path.isdir(special_dir):
            continue
        log(f"\nScanne {os.path.basename(special_dir)}/ ({status_label})...")
        for f in os.listdir(special_dir):
            if not f.lower().endswith(".pdf"):
                continue
            pdf_path = os.path.join(special_dir, f)
            try:
                mtime = os.path.getmtime(pdf_path)
                archived_at = datetime.fromtimestamp(mtime).isoformat(timespec="seconds")
                if DRY_RUN:
                    log(f"  [DRY] {f} | {status_label}")
                else:
                    db.upsert_document(
                        file_path=pdf_path,
                        filename=f,
                        sender=None,
                        date=None,
                        document_type=None,
                        category=None,
                        summary=None,
                        content_hash=None,
                        status=status_label,
                        archived_at=archived_at,
                    )
                ok += 1
            except Exception as e:
                log(f"  FEHLER bei {f}: {e}")
                errors += 1

    log(f"\nMigration abgeschlossen:")
    log(f"  Migriert:     {ok}")
    log(f"  Uebersprungen: {skipped}")
    log(f"  Fehler:       {errors}")
    if not DRY_RUN:
        log(f"  Datenbank:    {db.DB_PATH if hasattr(db, 'DB_PATH') else 'siehe config.py'}")


if __name__ == "__main__":
    main()
