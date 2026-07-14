import os
import shutil

from config import TARGET_BASE
import db
from utils import log

class RepairService:
    def scan_missing(self):
        """Find DB entries where the physical file is missing."""
        missing = []
        for doc in db.search_documents():
            fpath = doc["file_path"]
            if fpath and not os.path.exists(fpath):
                missing.append({
                    "id": doc["id"],
                    "filename": doc["filename"],
                    "path": fpath,
                    "status": doc["status"]
                })
        return missing

    def repair_missing(self):
        """Fix DB entries pointing to missing files by searching the archive."""
        missing = self.scan_missing()
        if not missing:
            return {"repaired": 0, "still_missing": 0}

        file_map = {}
        for root, dirs, files in os.walk(TARGET_BASE):
            for fname in files:
                if fname.lower().endswith(".pdf"):
                    # keep first found path for a filename (naive)
                    if fname not in file_map:
                        file_map[fname] = os.path.join(root, fname)

        repaired = 0
        still_missing = []
        for doc in missing:
            fname = doc["filename"]
            if fname in file_map:
                new_path = file_map[fname]
                db.update_document(doc["id"], file_path=new_path)
                repaired += 1
            else:
                still_missing.append(doc)
                
        return {"repaired": repaired, "still_missing": len(still_missing), "details": still_missing}

    def delete_missing(self):
        """Delete DB entries where the file is missing and cannot be found."""
        missing = self.scan_missing()
        deleted = 0
        for doc in missing:
            db.delete_document(doc["id"])
            deleted += 1
        return {"deleted": deleted}

    def scan_orphans(self):
        """Find PDF files in the archive that are not in the DB."""
        db_paths = {os.path.normpath(d["file_path"]) for d in db.search_documents() if d["file_path"]}
        orphans = []
        
        # Don't scan special folders like failed/ duplicates/ review/
        SKIP_DIRS = {"duplicates", "failed", "encrypted", "review"}
        
        for root, dirs, files in os.walk(TARGET_BASE):
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
                            "rel_path": os.path.relpath(full_path, TARGET_BASE),
                            "size_kb": size_kb
                        })
        return orphans

    def import_orphans(self, paths: list):
        """Import specific orphan files back into the DB without moving them."""
        imported = 0
        errors = []
        for fpath in paths:
            if not os.path.exists(fpath):
                errors.append(f"Nicht gefunden: {fpath}")
                continue
            
            try:
                fname = os.path.basename(fpath)
                from pdf_utils import extract_text
                text, status = extract_text(fpath)
                summary = "Wiederhergestellt (Orphan)"
                doc_status = "ok"
                if status == "encrypted":
                    doc_status = "encrypted"
                    summary = "Wiederhergestellt (Verschlüsselt)"
                elif status == "corrupt":
                    doc_status = "corrupt"
                    summary = "Wiederhergestellt (Defekt)"
                
                db.upsert_document(
                    file_path=fpath,
                    filename=fname,
                    sender=None,
                    date=None,
                    document_type=None,
                    category=None,
                    summary=summary,
                    status=doc_status
                )
                imported += 1
            except Exception as e:
                errors.append(f"Fehler bei {os.path.basename(fpath)}: {str(e)}")
                
        return {"imported": imported, "errors": errors}

    def cleanup_empty_folders(self):
        """Remove empty directories inside TARGET_BASE (bottom-up)."""
        SKIP_TOPLEVEL = {"duplicates", "failed", "encrypted", "review"}
        target = os.path.abspath(TARGET_BASE)
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