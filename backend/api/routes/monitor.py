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
_ARCHIVER_PID_FILE = os.path.join(TARGET_BASE, "archiver.pid")


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

def _pid_is_alive(pid: int) -> bool:
    """Check if a process with given PID is still running (Windows-compatible)."""
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        pass
    # Fallback: Windows tasklist
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"], text=True, stderr=subprocess.DEVNULL
        )
        return str(pid) in out
    except Exception:
        return False


def _proc_running() -> bool:
    global _archiver_proc
    # Fast path: in-memory handle
    if _archiver_proc is not None:
        if _archiver_proc.poll() is None:
            return True
        _archiver_proc = None
    # Fallback: check PID file (survives backend restart)
    if os.path.exists(_ARCHIVER_PID_FILE):
        try:
            pid = int(open(_ARCHIVER_PID_FILE).read().strip())
            if _pid_is_alive(pid):
                return True
        except (ValueError, OSError):
            pass
        # Stale PID file — clean up
        try:
            os.remove(_ARCHIVER_PID_FILE)
        except OSError:
            pass
    return False


@router.get("/archiver/status")
def archiver_status():
    running = _proc_running()
    pid = None
    if running:
        if _archiver_proc is not None:
            pid = _archiver_proc.pid
        elif os.path.exists(_ARCHIVER_PID_FILE):
            try:
                pid = int(open(_ARCHIVER_PID_FILE).read().strip())
            except (ValueError, OSError):
                pass
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
    with open(_ARCHIVER_PID_FILE, "w") as f:
        f.write(str(_archiver_proc.pid))
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
    try:
        os.remove(_ARCHIVER_PID_FILE)
    except OSError:
        pass
    return {"stopped": True}


# ── Manual processing ───────────────────────────────────────────────────────

_processing_lock = __import__("threading").Lock()
_processing_busy = False


class ProcessFileRequest(__import__("pydantic").BaseModel):
    file_path: str


@router.post("/process-file")
def process_single_file(req: ProcessFileRequest):
    """Process a single PDF immediately in a background thread. Non-blocking."""
    global _processing_busy
    import threading
    from pipeline import process_pdf

    if not os.path.isfile(req.file_path):
        raise HTTPException(status_code=404, detail=f"Datei nicht gefunden: {req.file_path}")
    if not req.file_path.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Nur PDF-Dateien werden unterstützt.")

    def _run():
        global _processing_busy
        import utils as _utils
        _utils._FORCED_LOG_FILE = ARCHIVER_STDOUT
        try:
            process_pdf(req.file_path)
        finally:
            _utils._FORCED_LOG_FILE = None
            fname = os.path.basename(req.file_path)
            _inbox_cache["files"] = [f for f in _inbox_cache["files"] if f["filename"] != fname]
            with _processing_lock:
                _processing_busy = False

    with _processing_lock:
        _processing_busy = True
    threading.Thread(target=_run, daemon=True, name="manual-process").start()
    return {"started": True, "file": os.path.basename(req.file_path)}


@router.post("/process-inbox")
def process_all_inbox():
    """Queue all unprocessed PDFs from the inbox for immediate processing. Non-blocking."""
    global _processing_busy
    import threading
    from pipeline import process_pdf

    if not os.path.isdir(SOURCE_DIR):
        raise HTTPException(status_code=404, detail=f"Inbox-Ordner nicht gefunden: {SOURCE_DIR}")

    known_paths = set(db.get_all_file_paths())
    pdfs = []
    for root, _, files in os.walk(SOURCE_DIR):
        for f in files:
            if f.lower().endswith(".pdf"):
                fp = os.path.join(root, f)
                if fp not in known_paths:
                    pdfs.append(fp)

    if not pdfs:
        return {"started": False, "count": 0, "message": "Keine neuen PDFs in der Inbox."}

    def _run():
        global _processing_busy
        import utils as _utils
        _utils._FORCED_LOG_FILE = ARCHIVER_STDOUT
        try:
            for fp in pdfs:
                process_pdf(fp)
        finally:
            _utils._FORCED_LOG_FILE = None
            with _processing_lock:
                _processing_busy = False

    with _processing_lock:
        _processing_busy = True
    threading.Thread(target=_run, daemon=True, name="manual-process-all").start()
    return {"started": True, "count": len(pdfs), "files": [os.path.basename(p) for p in pdfs]}


@router.get("/processing-status")
def processing_status():
    """Returns whether a manual processing job is currently running."""
    return {"busy": _processing_busy}


# ── Inbox preview ───────────────────────────────────────────────────────────

_inbox_cache: dict = {"files": [], "ts": 0.0}
_INBOX_TTL = 10.0  # seconds


def _scan_inbox() -> list:
    files = []
    try:
        for root, dirs, fnames in os.walk(SOURCE_DIR):
            dirs[:] = [d for d in dirs if not os.path.join(root, d).startswith(os.path.abspath(TARGET_BASE))]
            for fname in fnames:
                if fname.lower().endswith(".pdf"):
                    fpath = os.path.join(root, fname)
                    rel = os.path.relpath(fpath, SOURCE_DIR)
                    try:
                        st = os.stat(fpath)
                        size_kb = round(st.st_size / 1024, 1)
                        modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
                    except OSError:
                        size_kb = 0
                        modified = ""
                    files.append({"filename": rel, "size_kb": size_kb, "modified": modified})
    except PermissionError:
        return []
    files.sort(key=lambda f: f["filename"])
    return files


def _refresh_inbox_cache():
    """Refresh cache in background thread so requests never block."""
    import threading
    def _run():
        result = _scan_inbox()
        _inbox_cache["files"] = result
        _inbox_cache["ts"] = time.time()
    threading.Thread(target=_run, daemon=True, name="inbox-scan").start()


@router.get("/inbox")
def inbox_preview(force: bool = False):
    """List PDFs in SOURCE_DIR. Uses a cache to avoid slow network drive scans."""
    if not os.path.isdir(SOURCE_DIR):
        return {"source_dir": SOURCE_DIR, "files": [], "error": "Inbox-Ordner nicht gefunden"}

    age = time.time() - _inbox_cache["ts"]
    if _inbox_cache["ts"] == 0.0:
        # First request ever — scan synchronously so we don't return empty list
        result = _scan_inbox()
        _inbox_cache["files"] = result
        _inbox_cache["ts"] = time.time()
    elif force or age > _INBOX_TTL:
        _refresh_inbox_cache()

    return {"source_dir": SOURCE_DIR, "files": _inbox_cache["files"]}


@router.post("/inbox/refresh")
def inbox_refresh():
    """Force an immediate inbox rescan (blocks until done)."""
    if not os.path.isdir(SOURCE_DIR):
        return {"source_dir": SOURCE_DIR, "files": []}
    result = _scan_inbox()
    _inbox_cache["files"] = result
    _inbox_cache["ts"] = time.time()
    return {"source_dir": SOURCE_DIR, "files": result}


@router.get("/duplicates")
def find_duplicates(min_score: int = 60):
    """Find probable duplicate document pairs using exact hash, SimHash, and metadata matching.
    Returns pairs sorted by confidence score descending."""
    from db.connection import get_conn

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, file_path, filename, sender, date, document_type, content_hash, sim_hash "
            "FROM documents WHERE status IN ('ok', 'review') ORDER BY id"
        ).fetchall()

    docs = [dict(r) for r in rows]
    pairs = {}  # key: (min_id, max_id) -> pair dict

    # Pass 1: Exact content_hash match (score=100)
    hash_groups: dict = {}
    for doc in docs:
        h = doc.get("content_hash")
        if h:
            hash_groups.setdefault(h, []).append(doc)
    for h, group in hash_groups.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                key = (min(a["id"], b["id"]), max(a["id"], b["id"]))
                pairs[key] = {"doc_a": a, "doc_b": b, "score": 100, "reason": "Identischer Inhalt (Hash-Match)"}

    # Pass 2: SimHash near-duplicate via LSH band bucketing — O(n) instead of O(n²)
    # 64-bit SimHash split into 8 bands of 8 bits each.
    # Two docs collide in a bucket ↔ they share at least one identical 8-bit band,
    # which statistically captures pairs with Hamming distance ≤ ~8 (≥87.5% similarity).
    sim_docs = [d for d in docs if d.get("sim_hash")]
    NUM_BANDS, BITS_PER_BAND = 8, 8
    lsh_buckets: dict = {}
    for doc in sim_docs:
        h = doc["sim_hash"]
        for band in range(NUM_BANDS):
            band_val = (h >> (band * BITS_PER_BAND)) & ((1 << BITS_PER_BAND) - 1)
            bucket_key = (band, band_val)
            lsh_buckets.setdefault(bucket_key, []).append(doc)
    candidate_pairs: set = set()
    for bucket_docs in lsh_buckets.values():
        if len(bucket_docs) < 2:
            continue
        for i in range(len(bucket_docs)):
            for j in range(i + 1, len(bucket_docs)):
                a, b = bucket_docs[i], bucket_docs[j]
                candidate_pairs.add((min(a["id"], b["id"]), max(a["id"], b["id"])))
    id_to_doc = {d["id"]: d for d in sim_docs}
    for cand_key in candidate_pairs:
        if cand_key in pairs:
            continue
        a = id_to_doc[cand_key[0]]
        b = id_to_doc[cand_key[1]]
        dist = bin(a["sim_hash"] ^ b["sim_hash"]).count("1")
        score = round((1.0 - dist / 64) * 100)
        if score >= 80:
            pairs[cand_key] = {"doc_a": a, "doc_b": b, "score": score, "reason": f"Ähnlicher Text ({score}% Übereinstimmung)"}

    # Pass 3: Metadata match — same sender + date + document_type (score=70)
    from itertools import combinations
    meta_docs = [d for d in docs if d.get("sender") and d.get("date") and d.get("document_type")]
    meta_groups: dict = {}
    for doc in meta_docs:
        mk = (doc["sender"].strip().lower(), doc["date"][:10] if doc["date"] else "", doc["document_type"].strip().lower())
        meta_groups.setdefault(mk, []).append(doc)
    for mk, group in meta_groups.items():
        for a, b in combinations(group, 2):
            key = (min(a["id"], b["id"]), max(a["id"], b["id"]))
            if key in pairs:
                continue
            pairs[key] = {"doc_a": a, "doc_b": b, "score": 70, "reason": f"Gleicher Absender, Datum & Typ ({a['sender']} / {a['date'][:10] if a['date'] else '?'} / {a['document_type']})"}

    result = [p for p in pairs.values() if p["score"] >= min_score]
    result.sort(key=lambda p: p["score"], reverse=True)
    return {"total": len(result), "pairs": result}


@router.get("/duplicates/count")
def duplicates_count(min_score: int = 70):
    """Lightweight endpoint: returns only the count of similar pairs (for sidebar badge).
    Uses the same SimHash logic as /duplicates but skips building full pair objects."""
    from pdf_utils import simhash_distance
    from db.connection import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, sim_hash FROM documents WHERE sim_hash IS NOT NULL AND status IN ('ok', 'review')"
        ).fetchall()
    docs = [(r["id"], r["sim_hash"]) for r in rows]
    seen: set = set()
    count = 0
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            aid, ah = docs[i]
            bid, bh = docs[j]
            dist = simhash_distance(ah, bh)
            if round((1.0 - dist / 64) * 100) >= min_score:
                key = (min(aid, bid), max(aid, bid))
                if key not in seen:
                    seen.add(key)
                    count += 1
    return {"count": count}


@router.get("/validation")
def validation_report(min_docs: int = 2):
    """Group documents by sender+document_type and check for:
    1. Classification inconsistencies (category or document_type varies within group)
    2. Missing months in regular monthly series (>=3 docs spanning >=2 months)
    Only returns groups with at least one issue."""
    from db.connection import get_conn
    from collections import Counter
    import re as _re

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, filename, sender, date, document_type, category, file_path "
            "FROM documents WHERE status IN ('ok', 'review') AND sender IS NOT NULL AND sender != '' "
            "ORDER BY sender, document_type, date"
        ).fetchall()

    docs = [dict(r) for r in rows]

    # Group by (sender, document_type)
    groups: dict = {}
    for doc in docs:
        key = (
            (doc["sender"] or "").strip(),
            (doc["document_type"] or "").strip(),
        )
        if not key[0]:
            continue
        groups.setdefault(key, []).append(doc)

    result = []
    for (sender, doc_type), members in groups.items():
        if len(members) < min_docs:
            continue

        issues = []

        # --- Consistency check ---
        categories = Counter(d["category"] for d in members if d.get("category"))
        if len(categories) > 1:
            dominant = categories.most_common(1)[0][0]
            outliers = [d for d in members if d.get("category") and d["category"] != dominant]
            issues.append({
                "type": "inconsistent_category",
                "message": f"Kategorie inkonsistent: meist '{dominant}', aber {len(outliers)} Dokument(e) abweichend",
                "dominant": dominant,
                "outliers": [{"id": d["id"], "filename": d["filename"], "category": d["category"], "date": d["date"]} for d in outliers],
            })

        # --- Gap detection for monthly series ---
        # Extract YYYY-MM from date strings
        months = []
        for d in members:
            raw = d.get("date") or ""
            m = _re.search(r'(\d{4})-(\d{2})', raw)
            if m:
                months.append((int(m.group(1)), int(m.group(2)), d))

        if len(months) >= 3:
            months.sort(key=lambda x: (x[0], x[1]))
            # Check if series looks monthly (avg gap ~1 month)
            month_set = set((y, mo) for y, mo, _ in months)
            first_y, first_mo = months[0][0], months[0][1]
            last_y, last_mo = months[-1][0], months[-1][1]
            total_months = (last_y - first_y) * 12 + (last_mo - first_mo) + 1
            # Only flag as series if coverage >50% of expected months
            if len(month_set) >= 3 and len(month_set) / total_months >= 0.5:
                missing = []
                y, mo = first_y, first_mo
                while (y, mo) <= (last_y, last_mo):
                    if (y, mo) not in month_set:
                        missing.append(f"{y}-{mo:02d}")
                    mo += 1
                    if mo > 12:
                        mo = 1
                        y += 1
                if missing:
                    issues.append({
                        "type": "missing_months",
                        "message": f"Mögliche Lücken in monatlicher Serie: {', '.join(missing[:6])}{'…' if len(missing) > 6 else ''}",
                        "missing_months": missing,
                    })

        if not issues:
            continue

        result.append({
            "sender": sender,
            "document_type": doc_type,
            "category": members[0].get("category"),
            "count": len(members),
            "date_range": f"{months[0][0]}-{months[0][1]:02d} – {months[-1][0]}-{months[-1][1]:02d}" if len(months) >= 2 else "",
            "issues": issues,
            "members": [{"id": d["id"], "filename": d["filename"], "date": d["date"], "category": d["category"], "document_type": d["document_type"]} for d in members],
        })

    result.sort(key=lambda g: (len(g["issues"]), g["count"]), reverse=True)
    return {"total_groups": len(result), "groups": result}


@router.post("/generate-thumbnails")
def generate_thumbnails_job(force: bool = False):
    """Generate thumbnails for all ok/review documents that don't have one yet.
    Set force=true to regenerate existing thumbnails."""
    from pdf_utils import generate_thumbnail, get_thumbnail_path
    docs = db.search_documents(limit=99999)
    done = 0
    skipped = 0
    failed = 0
    for doc in docs:
        if doc.get("status") not in ("ok", "review"):
            continue
        path = doc.get("file_path", "")
        if not path or not os.path.exists(path):
            continue
        thumb = get_thumbnail_path(doc["id"])
        if not force and os.path.exists(thumb):
            skipped += 1
            continue
        result = generate_thumbnail(path, doc["id"])
        if result:
            done += 1
        else:
            failed += 1
    return {"generated": done, "skipped": skipped, "failed": failed}


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
