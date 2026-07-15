import os
import hashlib
import shutil
import json
import asyncio
import anyio

from config import SOURCE_DIR
from pdf_utils import extract_text, compute_simhash, unique_path
import db

class ImportService:
    def __init__(self):
        import threading
        self.cancel_flag = threading.Event()

    def cancel(self):
        self.cancel_flag.set()

    def _candidate_status(self, fpath: str):
        """Return (status, reason, existing_path) for a candidate file."""
        norm_path = os.path.normpath(fpath)
        existing = db.get_document_by_path(norm_path)
        if existing:
            return "duplicate", "path", existing["file_path"]

        text, pdf_status = extract_text(fpath)
        if pdf_status == "encrypted":
            return "error", "encrypted", None
        if pdf_status == "corrupt":
            return "error", "corrupt", None

        cleaned = (text or "").strip()
        if len(cleaned) >= 100:
            content_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]
        else:
            try:
                with open(fpath, "rb") as f:
                    content_hash = hashlib.sha256(f.read()).hexdigest()[:16]
            except Exception:
                content_hash = None

        if content_hash:
            with db.get_conn() as conn:
                row = conn.execute(
                    "SELECT id, file_path FROM documents WHERE content_hash = ? LIMIT 1",
                    (content_hash,)
                ).fetchone()
            if row:
                return "duplicate", "hash", row["file_path"]

        sim_hash = compute_simhash(cleaned) if cleaned else 0
        if sim_hash:
            matches = db.get_similar_by_simhash(sim_hash, -1, max_distance=8, limit=3)
            if matches:
                best = matches[0]
                return "likely_duplicate", f"simhash {best['simhash_distance']}/64", best["file_path"]
        return "new", None, None

    def _copy_file_to_inbox(self, fpath: str) -> str:
        """Copy a single file into the inbox and return the target path."""
        fpath = os.path.normpath(fpath)
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"Nicht gefunden: {fpath}")
        fname = os.path.basename(fpath)
        os.makedirs(SOURCE_DIR, exist_ok=True)
        target = unique_path(os.path.join(SOURCE_DIR, fname))
        shutil.copy2(fpath, target)
        return target

    async def stream_candidates(self, folder: str):
        all_files = []
        for root, dirs, files in os.walk(folder):
            for fname in files:
                if fname.lower().endswith((".pdf", ".docx", ".xlsx")):
                    all_files.append(os.path.normpath(os.path.join(root, fname)))
        total = len(all_files)
        yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"
        await asyncio.sleep(0)

        self.cancel_flag.clear()
        candidates = []
        for i, fpath in enumerate(all_files, 1):
            if self.cancel_flag.is_set():
                yield f"data: {json.dumps({'type': 'stopped', 'i': i - 1, 'total': total})}\n\n"
                break
            rel = os.path.relpath(fpath, folder)
            try:
                stat = os.stat(fpath)
                size_kb = round(stat.st_size / 1024, 1)
            except Exception:
                size_kb = 0
            try:
                status, reason, existing_path = await anyio.to_thread.run_sync(self._candidate_status, fpath)
            except Exception as e:
                status, reason, existing_path = "error", str(e), None
            candidates.append({
                "file_path": fpath,
                "rel_path": rel,
                "filename": os.path.basename(fpath),
                "size_kb": size_kb,
                "status": status,
                "reason": reason,
                "existing_path": existing_path,
            })
            yield f"data: {json.dumps({'type': 'progress', 'i': i, 'total': total, 'file': os.path.basename(fpath), 'status': status})}\n\n"
            await asyncio.sleep(0)

        yield f"data: {json.dumps({'type': 'done', 'folder': folder, 'total': total, 'candidates': candidates})}\n\n"

    async def stream_copy(self, paths: list):
        total = len(paths)
        yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"
        await asyncio.sleep(0)

        self.cancel_flag.clear()
        copied, errors = [], []
        for i, fpath in enumerate(paths, 1):
            if self.cancel_flag.is_set():
                yield f"data: {json.dumps({'type': 'stopped', 'i': i - 1, 'total': total})}\n\n"
                break
            status = "ok"
            detail = None
            try:
                target = await anyio.to_thread.run_sync(self._copy_file_to_inbox, fpath)
                copied.append(target)
            except Exception as e:
                status = "error"
                detail = str(e)
                errors.append(f"{os.path.basename(fpath)}: {e}")
            yield f"data: {json.dumps({'type': 'progress', 'i': i, 'total': total, 'file': os.path.basename(fpath), 'status': status, 'detail': detail})}\n\n"
            await asyncio.sleep(0)

        yield f"data: {json.dumps({'type': 'done', 'copied': len(copied), 'targets': copied, 'errors': errors})}\n\n"

import_service = ImportService()
