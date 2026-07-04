import asyncio
import os
import subprocess
import sys
import time
from datetime import datetime

aiofiles = None
try:
    import aiofiles as _aiofiles
    aiofiles = _aiofiles
except ImportError:
    pass

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from config import TARGET_BASE, SOURCE_DIR
import db

router = APIRouter(prefix="/monitor", tags=["monitor"])

LOG_FILE = os.path.join(TARGET_BASE, "processing_log.jsonl")
ARCHIVER_STDOUT = os.path.join(TARGET_BASE, "archiver.log")

# Global archiver process handle
_archiver_proc: subprocess.Popen | None = None


async def _tail_file(path: str):
    """Async generator that tails a file, yielding new lines as SSE events."""
    if not os.path.exists(path):
        yield f"data: Log-Datei nicht gefunden: {path}\n\n"
        yield ": keepalive\n\n"
        return

    if aiofiles:
        async with aiofiles.open(path, mode='r', encoding='utf-8', errors='replace') as f:
            await f.seek(0, 2)
            while True:
                line = await f.readline()
                if line:
                    yield f"data: {line.rstrip()}\n\n"
                else:
                    await asyncio.sleep(0.5)
                    yield ": keepalive\n\n"
    else:
        with open(path, encoding='utf-8', errors='replace') as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line.rstrip()}\n\n"
                else:
                    await asyncio.sleep(0.5)
                    yield ": keepalive\n\n"


@router.get("/stream")
async def stream_logs():
    log_path = ARCHIVER_STDOUT if os.path.exists(ARCHIVER_STDOUT) else LOG_FILE
    return StreamingResponse(
        _tail_file(log_path),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/buffer")
def get_buffer():
    path = ARCHIVER_STDOUT if os.path.exists(ARCHIVER_STDOUT) else LOG_FILE
    if not os.path.exists(path):
        return {"lines": []}
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = f.readlines()[-100:]
    return {"lines": [l.rstrip() for l in lines]}


# ── Archiver control ────────────────────────────────────────────────────────

def _proc_running() -> bool:
    global _archiver_proc
    if _archiver_proc is None:
        return False
    return _archiver_proc.poll() is None


@router.get("/archiver/status")
def archiver_status():
    running = _proc_running()
    pid = _archiver_proc.pid if running else None
    return {"running": running, "pid": pid}


@router.post("/archiver/start")
def archiver_start():
    global _archiver_proc
    if _proc_running():
        raise HTTPException(status_code=409, detail="Archiver läuft bereits")
    python = sys.executable
    project_root = os.path.join(os.path.dirname(__file__), "..", "..")
    log_out = open(ARCHIVER_STDOUT, "a", encoding="utf-8")
    _archiver_proc = subprocess.Popen(
        [python, "archiver.py"],
        cwd=os.path.abspath(project_root),
        stdout=log_out,
        stderr=log_out,
        text=True,
    )
    return {"started": True, "pid": _archiver_proc.pid}


@router.post("/archiver/stop")
def archiver_stop():
    global _archiver_proc
    if not _proc_running():
        raise HTTPException(status_code=409, detail="Archiver läuft nicht")
    _archiver_proc.terminate()
    try:
        _archiver_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _archiver_proc.kill()
    return {"stopped": True}


# ── Inbox preview ───────────────────────────────────────────────────────────

@router.get("/inbox")
def inbox_preview():
    """List PDFs in SOURCE_DIR that have not been archived yet."""
    if not os.path.isdir(SOURCE_DIR):
        return {"source_dir": SOURCE_DIR, "files": [], "error": "Inbox-Ordner nicht gefunden"}

    files = []
    for fname in sorted(os.listdir(SOURCE_DIR)):
        if not fname.lower().endswith(".pdf"):
            continue
        fpath = os.path.join(SOURCE_DIR, fname)
        stat = os.stat(fpath)
        files.append({
            "filename": fname,
            "size_kb": round(stat.st_size / 1024, 1),
            "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
        })
    return {"source_dir": SOURCE_DIR, "files": files}


@router.post("/scan-missing")
def scan_missing():
    """
    Check ALL DB entries against the filesystem (regardless of current status).
    Entries whose file_path no longer exists are marked status='missing'.
    Returns list of affected documents.
    """
    docs = db.search_documents(limit=99999)
    missing = []
    for doc in docs:
        if doc.get("file_path") and not os.path.exists(doc["file_path"]):
            db.update_document(doc["id"], status="missing")
            missing.append({
                "id": doc["id"],
                "filename": doc.get("filename"),
                "sender": doc.get("sender"),
                "date": doc.get("date"),
                "category": doc.get("category"),
                "file_path": doc.get("file_path"),
            })
    return {"scanned": len(docs), "missing_found": len(missing), "missing": missing}


@router.post("/repair-missing")
def repair_missing():
    """
    For each DB entry with status='missing', search TARGET_BASE recursively for a file
    with the same filename. If found, update file_path and restore status to previous value.
    """
    docs = db.search_documents(status="missing", limit=99999)
    repaired, not_found = [], []

    # Build a filename→path index of all PDFs in TARGET_BASE once (fast)
    file_index: dict[str, list[str]] = {}
    for root, dirs, files in os.walk(TARGET_BASE):
        # Skip special dirs
        skip = {"duplicates", "failed", "encrypted", "review", "Inbox"}
        dirs[:] = [d for d in dirs if d not in skip]
        for fname in files:
            if fname.lower().endswith(".pdf"):
                file_index.setdefault(fname, []).append(os.path.join(root, fname))

    for doc in docs:
        fname = doc.get("filename") or os.path.basename(doc.get("file_path", ""))
        matches = file_index.get(fname, [])
        if matches:
            new_path = matches[0]  # take first match
            db.update_document(doc["id"], file_path=new_path, status="ok")
            repaired.append({"id": doc["id"], "filename": fname, "new_path": new_path})
        else:
            not_found.append({"id": doc["id"], "filename": fname})

    return {
        "scanned": len(docs),
        "repaired": len(repaired),
        "not_found": len(not_found),
        "details": repaired,
        "missing_still": not_found,
    }


@router.delete("/missing")
def delete_missing():
    """Delete all DB entries with status='missing' at once."""
    docs = db.search_documents(status="missing", limit=99999)
    for doc in docs:
        db.delete_document(doc["id"])
    return {"deleted": len(docs)}


@router.get("/orphans")
def scan_orphans():
    """
    Scan TARGET_BASE for PDFs that have no matching DB entry (by file_path).
    Excludes SOURCE_DIR, duplicates/, failed/, encrypted/ folders.
    """
    EXCLUDE_DIRS = {"duplicates", "failed", "encrypted", "review"}

    # Get all known file paths from DB
    all_docs = db.search_documents(limit=99999)
    known_paths = {os.path.normcase(os.path.normpath(d["file_path"])) for d in all_docs if d.get("file_path")}

    orphans = []
    for root, dirs, files in os.walk(TARGET_BASE):
        # Skip root dir – only process subdirectories
        rel = os.path.relpath(root, TARGET_BASE)
        if rel == ".":
            continue
        # Skip excluded top-level dirs
        top = rel.split(os.sep)[0]
        if top in EXCLUDE_DIRS:
            dirs.clear()
            continue
        # Skip SOURCE_DIR
        if os.path.normcase(os.path.normpath(root)).startswith(
            os.path.normcase(os.path.normpath(SOURCE_DIR))
        ):
            dirs.clear()
            continue

        for fname in files:
            if not fname.lower().endswith(".pdf"):
                continue
            fpath = os.path.join(root, fname)
            norm = os.path.normcase(os.path.normpath(fpath))
            if norm not in known_paths:
                stat = os.stat(fpath)
                # Try to infer category from folder name
                parts = rel.split(os.sep)
                category_hint = parts[0] if parts else ""
                orphans.append({
                    "file_path": fpath,
                    "filename": fname,
                    "folder": rel,
                    "category_hint": category_hint,
                    "size_kb": round(stat.st_size / 1024, 1),
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
                })

    orphans.sort(key=lambda x: x["modified"], reverse=True)
    return {"count": len(orphans), "orphans": orphans}


@router.post("/orphans/import")
def import_orphans(body: dict):
    """
    Import selected orphan PDFs by moving them into the Inbox so the archiver picks them up.
    body: { "paths": ["/path/to/file.pdf", ...] }
    """
    import shutil
    from pdf_utils import unique_path
    paths = body.get("paths", [])
    if not paths:
        raise HTTPException(status_code=400, detail="Keine Pfade angegeben")

    os.makedirs(SOURCE_DIR, exist_ok=True)
    imported, skipped, errors = 0, 0, []
    for fpath in paths:
        fpath = os.path.normpath(fpath)
        if not os.path.exists(fpath):
            errors.append(f"Nicht gefunden: {fpath}")
            continue
        fname = os.path.basename(fpath)
        try:
            inbox_path = unique_path(os.path.join(SOURCE_DIR, fname))
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
