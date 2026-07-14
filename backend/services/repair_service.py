import os
import shutil

import config
import db
from utils import log

class RepairService:
    def scan_missing(self):
        """Find DB entries where the physical file is missing."""
        missing = []
        for doc in db.search_documents():
            fpath = doc["file_path"]
            if fpath and not os.path.exists(fpath):
                db.update_document(doc["id"], status="missing")
                missing.append({
                    "id": doc["id"],
                    "filename": doc["filename"],
                    "path": fpath,
                    "status": "missing"
                })
        return missing

    def repair_missing(self):
        """Fix DB entries pointing to missing files by searching the archive."""
        with db.get_conn() as conn:
            rows = conn.execute("SELECT id, file_path, filename FROM documents WHERE status='missing'").fetchall()
        missing = [dict(r) for r in rows]
        if not missing:
            return {"repaired": 0, "still_missing": 0}

        file_map = {}
        for root, dirs, files in os.walk(config.TARGET_BASE):
            for fname in files:
                if fname.lower().endswith(".pdf"):
                    # keep first found path for a filename (naive)
                    if fname not in file_map:
                        file_map[fname] = os.path.join(root, fname)

        repaired = 0
        still_missing = []
        for doc in missing:
            fname = doc["filename"] or os.path.basename(doc["file_path"] or "")
            if fname in file_map:
                new_path = file_map[fname]
                db.update_document(doc["id"], file_path=new_path, status="ok")
                repaired += 1
            else:
                still_missing.append(doc)
                
        return {"repaired": repaired, "still_missing": len(still_missing), "details": still_missing}

    def delete_missing(self):
        """Delete DB entries where the file is missing and cannot be found."""
        with db.get_conn() as conn:
            rows = conn.execute("SELECT id FROM documents WHERE status='missing'").fetchall()
        deleted = 0
        for r in rows:
            db.delete_document(r["id"])
            deleted += 1
        return {"deleted": deleted}

    def scan_orphans(self):
        """Find PDF files in the archive that are not in the DB."""
        with db.get_conn() as conn:
            rows = conn.execute("SELECT file_path FROM documents WHERE file_path IS NOT NULL").fetchall()
        db_paths = {os.path.normpath(r["file_path"]) for r in rows}
        orphans = []
        
        # Don't scan special folders like failed/ duplicates/ review/
        SKIP_DIRS = {"duplicates", "failed", "encrypted", "review"}
        
        for root, dirs, files in os.walk(config.TARGET_BASE):
            # Mutate dirs in-place to skip
            dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]
            
            for fname in files:
                if fname.lower().endswith(".pdf"):
                    full_path = os.path.normpath(os.path.join(root, fname))
                    if full_path not in db_paths:
                        try:
                            stat = os.stat(full_path)
                            size_kb = round(stat.st_size / 1024, 1)
                        except Exception:
                            size_kb = 0
                        orphans.append({
                            "filename": fname,
                            "path": full_path,
                            "rel_path": os.path.relpath(full_path, config.TARGET_BASE),
                            "size_kb": size_kb
                        })
        return orphans

    def import_orphans(self, paths: list):
        """Import selected orphan PDFs by moving them into the Inbox so the archiver picks them up."""
        from pdf_utils import unique_path
        os.makedirs(config.SOURCE_DIR, exist_ok=True)
        imported, skipped, errors = 0, 0, []
        for fpath in paths:
            fpath = os.path.normpath(fpath)
            if not os.path.exists(fpath):
                errors.append(f"Nicht gefunden: {fpath}")
                continue
            fname = os.path.basename(fpath)
            try:
                inbox_path = unique_path(os.path.join(config.SOURCE_DIR, fname))
                shutil.move(fpath, inbox_path)
                # Remove stale DB entry at old path if present
                existing = db.get_document_by_path(fpath)
                if existing:
                    db.delete_document(existing["id"])
                imported += 1
            except Exception as e:
                skipped += 1
                errors.append(f"{fname}: {e}")
                
        return {"imported": imported, "skipped": skipped, "errors": errors}

    def cleanup_empty_folders(self):
        """Remove empty directories inside TARGET_BASE (bottom-up)."""
        SKIP_TOPLEVEL = {"duplicates", "failed", "encrypted", "review"}
        target = os.path.abspath(config.TARGET_BASE)
        removed = []

        for root, dirs, files in os.walk(target, topdown=False):
            if os.path.abspath(root) == target:
                continue
            
            is_top_level = os.path.dirname(root) == target
            if is_top_level and os.path.basename(root).lower() in SKIP_TOPLEVEL:
                continue

            if not os.listdir(root):
                try:
                    os.rmdir(root)
                    removed.append(os.path.relpath(root, target))
                except OSError as e:
                    log(f"Fehler beim Loeschen von '{root}': {e}")
                    
        return {"removed_count": len(removed), "removed_folders": removed}

repair_service = RepairService()