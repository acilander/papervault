import os
import time
import threading

import anyio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import config as _config
from config import SOURCE_DIR, TARGET_BASE, LOG_FILE
import db
from utils import log
from pipeline import process_pdf
from pdf_utils import generate_thumbnail

ARCHIVER_STDOUT = "archiver_stdout.log"

# Import our new business logic services
from services.archiver_service import archiver_status, archiver_start, archiver_stop
from services.import_service import import_service
from services.repair_service import repair_service
from services.quality_service import quality_service

router = APIRouter(prefix="/monitor", tags=["Monitor"])

# ── Logs & Status ───────────────────────────────────────────────────────────

@router.get("/stream")
async def stream_logs():
    """Stream the contents of LOG_FILE as Server-Sent Events."""
    async def _tail_file(path: str):
        import asyncio as _asyncio
        if not os.path.exists(path):
            yield "data: [Logfile nicht gefunden]\n\n"
            return
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    await _asyncio.sleep(0.5)
                    continue
                yield f"data: {line.strip()}\n\n"
    return StreamingResponse(_tail_file(LOG_FILE), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@router.get("/buffer")
def get_buffer():
    """Return the last 100 lines of the archiver stdout or log file."""
    path = ARCHIVER_STDOUT if os.path.exists(ARCHIVER_STDOUT) else LOG_FILE
    if not os.path.exists(path):
        return {"lines": []}
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = f.readlines()[-100:]
    return {"lines": [l.rstrip() for l in lines]}

# ── Archiver control (Delegated) ────────────────────────────────────────────

@router.get("/archiver/status")
def get_archiver_status():
    return archiver_status()

@router.post("/archiver/start")
def start_archiver():
    return archiver_start()

@router.post("/archiver/stop")
def stop_archiver():
    return archiver_stop()

# ── Manual processing ───────────────────────────────────────────────────────

_processing_lock = threading.Lock()
_processing_busy = False

class ProcessFileRequest(BaseModel):
    file_path: str

@router.post("/process-file")
def process_single_file(req: ProcessFileRequest):
    global _processing_busy
    if not _processing_lock.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Ein anderer Prozess läuft bereits.")
    _processing_busy = True
    def _run():
        global _processing_busy
        try:
            process_pdf(req.file_path)
        finally:
            _processing_busy = False
            _processing_lock.release()
    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started", "file": req.file_path}

@router.post("/process-inbox")
def process_all_inbox():
    global _processing_busy
    if not _processing_lock.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Ein Prozess läuft bereits.")
    _processing_busy = True
    def _run():
        global _processing_busy
        try:
            if os.path.isdir(SOURCE_DIR):
                for fname in os.listdir(SOURCE_DIR):
                    if fname.lower().endswith(".pdf"):
                        fpath = os.path.join(SOURCE_DIR, fname)
                        try:
                            process_pdf(fpath)
                        except Exception as e:
                            log(f"Fehler bei manueller Massenverarbeitung ({fname}): {e}")
        finally:
            _processing_busy = False
            _processing_lock.release()
    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started", "message": "Massenverarbeitung gestartet."}

@router.get("/processing-status")
def processing_status():
    return {"busy": _processing_busy}

# ── Inbox Management ────────────────────────────────────────────────────────

_inbox_cache = {}
_inbox_last_scan = 0
_inbox_lock = threading.Lock()

def _pre_classify_file(fpath: str) -> dict:
    """Runs a super fast regex/text-based pre-classification on a PDF file
    without running any LLM inference."""
    import fitz
    from llm.driver import detect_known_sender
    try:
        doc = fitz.open(fpath)
        text = ""
        if len(doc) > 0:
            page = doc[0]
            text = page.get_text("text")[:1000]
        doc.close()
        
        sender, category = detect_known_sender(text)
        return {"pre_sender": sender, "pre_category": category}
    except Exception:
        return {"pre_sender": None, "pre_category": None}

def _scan_inbox() -> list:
    res = []
    if os.path.isdir(SOURCE_DIR):
        for fname in os.listdir(SOURCE_DIR):
            if fname.lower().endswith(".pdf"):
                fpath = os.path.join(SOURCE_DIR, fname)
                try:
                    st = os.stat(fpath)
                    pre = _pre_classify_file(fpath)
                    res.append({
                        "filename": fname,
                        "file_path": fpath,
                        "size": st.st_size,
                        "modified": st.st_mtime,
                        "created": st.st_ctime,
                        "pre_sender": pre["pre_sender"],
                        "pre_category": pre["pre_category"]
                    })
                except OSError:
                    pass
    res.sort(key=lambda x: x["modified"])
    return res

def _refresh_inbox_cache():
    global _inbox_cache, _inbox_last_scan
    with _inbox_lock:
        _inbox_cache["files"] = _scan_inbox()
        _inbox_last_scan = time.time()

@router.get("/inbox")
def inbox_preview(force: bool = False):
    global _inbox_last_scan, _inbox_cache
    if force or (time.time() - _inbox_last_scan > 5) or "files" not in _inbox_cache:
        _refresh_inbox_cache()
    docs = db.search_documents(status="processing")
    proc_files = {os.path.normpath(d["file_path"]) for d in docs if d["file_path"]}
    res = []
    for item in _inbox_cache.get("files", []):
        item_copy = dict(item)
        item_copy["is_processing"] = os.path.normpath(item["file_path"]) in proc_files
        res.append(item_copy)
    return {"source_dir": SOURCE_DIR, "files": res}

@router.post("/inbox/refresh")
def inbox_refresh():
    _refresh_inbox_cache()
    return {"status": "ok"}

# ── Quality & Duplicates (Delegated) ────────────────────────────────────────

@router.get("/duplicates")
def get_duplicates(min_score: int = 60):
    return quality_service.find_duplicates(min_score)

@router.get("/duplicates/count")
def get_duplicates_count(min_score: int = 90):
    return quality_service.duplicates_count(min_score)

@router.get("/validation")
def get_validation_report(min_docs: int = 2):
    return quality_service.validation_report(min_docs)

# ── Data Maintenance & Repair (Delegated) ───────────────────────────────────

@router.post("/scan-missing")
def scan_missing():
    missing = repair_service.scan_missing()
    return {"missing_found": len(missing), "details": missing}

@router.post("/repair-missing")
def repair_missing():
    return repair_service.repair_missing()

@router.delete("/missing")
def delete_missing():
    return repair_service.delete_missing()

@router.get("/orphans")
def scan_orphans():
    orphans = repair_service.scan_orphans()
    return {"count": len(orphans), "orphans": orphans}

@router.post("/orphans/import")
def import_orphans(body: dict):
    paths = body.get("paths", [])
    if not paths:
        raise HTTPException(status_code=400, detail="Keine Pfade angegeben")
    return repair_service.import_orphans(paths)

@router.post("/cleanup-empty-folders")
def cleanup_empty_folders():
    return repair_service.cleanup_empty_folders()

# ── Import (Delegated) ──────────────────────────────────────────────────────

@router.get("/import-candidates")
async def import_candidates(folder_path: str):
    folder = os.path.normpath(folder_path)
    if not os.path.isdir(folder):
        raise HTTPException(status_code=400, detail=f"Kein Ordner: {folder}")
    return StreamingResponse(import_service.stream_candidates(folder), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@router.post("/import-copy")
async def import_copy(body: dict):
    paths = body.get("paths", [])
    if not paths:
        raise HTTPException(status_code=400, detail="Keine Pfade angegeben")
    os.makedirs(SOURCE_DIR, exist_ok=True)
    return StreamingResponse(import_service.stream_copy(paths), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@router.post("/import-cancel")
def import_cancel():
    import_service.cancel()
    return {"cancelled": True}

# ── Background Jobs (Thumbnails & Reclassify) ───────────────────────────────

@router.post("/generate-thumbnails")
async def generate_thumbnails_job(force: bool = False):
    from pdf_utils import generate_thumbnail, THUMBNAILS_DIR as thumb_dir
    docs = db.search_documents()
    all_docs_count = len(docs)
    if not force:
        existing = set()
        if os.path.exists(thumb_dir):
            existing = {int(f.split(".")[0]) for f in os.listdir(thumb_dir) if f.split(".")[0].isdigit() and f.split(".")[-1].lower() in ("webp", "jpg", "jpeg")}
        docs = [d for d in docs if d["id"] not in existing and d["status"] not in ("corrupt", "encrypted")]

    async def _stream():
        import json as _json
        import asyncio as _asyncio
        total = len(docs)
        yield f"data: {_json.dumps({'type': 'start', 'total': total})}\n\n"
        await _asyncio.sleep(0)

        generated = 0
        failed = 0
        skipped = all_docs_count - total
        for i, doc in enumerate(docs, 1):
            if doc.get("file_path") and os.path.exists(doc["file_path"]):
                try:
                    await anyio.to_thread.run_sync(generate_thumbnail, doc["file_path"], doc["id"])
                    generated += 1
                except Exception:
                    failed += 1
            else:
                failed += 1
            yield f"data: {_json.dumps({'type': 'progress', 'i': i, 'total': total, 'file': doc['filename']})}\n\n"
            await _asyncio.sleep(0)
        yield f"data: {_json.dumps({'type': 'done', 'total': total, 'generated': generated, 'skipped': skipped, 'failed': failed})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

_reclassify_cancel = threading.Event()

@router.get("/reclassify-pending")
def reclassify_pending():
    docs = db.search_documents(status="ok")
    pending = [d for d in docs if d.get("document_type") == "Sonstiges" or d.get("category") == "Sonstiges"]
    return {"count": len(pending), "docs": pending}

@router.post("/reclassify-invoices")
async def reclassify_invoices():
    docs = db.search_documents(status="ok")
    pending = [d for d in docs if d.get("document_type") == "Sonstiges" or d.get("category") == "Sonstiges"]

    async def _stream():
        import json as _json
        import asyncio as _asyncio
        total = len(pending)
        yield f"data: {_json.dumps({'type': 'start', 'total': total})}\n\n"
        await _asyncio.sleep(0)

        _reclassify_cancel.clear()
        for i, doc in enumerate(pending, 1):
            if _reclassify_cancel.is_set():
                yield f"data: {_json.dumps({'type': 'stopped', 'i': i - 1, 'total': total})}\n\n"
                break

            status_msg = "übersprungen"
            if doc.get("file_path") and os.path.exists(doc["file_path"]):
                try:
                    def _classify():
                        from pdf_utils import extract_text, extract_features, build_feature_prompt, prepare_text_for_llm
                        from llm import classify_document
                        text, status = extract_text(doc["file_path"])
                        if status != "ok" or not text:
                            return None
                        safe_text = prepare_text_for_llm(text)
                        features = extract_features(text, filename=doc["filename"], file_path=doc["file_path"])
                        fp = build_feature_prompt(features)
                        from db import find_similar_by_features
                        sim = find_similar_by_features(features.get("category_candidates", []), features.get("type_candidate"))
                        return classify_document(
                            safe_text,
                            filename=doc["filename"],
                            feature_prompt=fp,
                            similar_docs=sim,
                            header_zone=features.get("header_zone")
                        )
                    res = await anyio.to_thread.run_sync(_classify)
                    if res:
                        from storage import apply_sender_overrides
                        res = apply_sender_overrides(res)
                        db.update_document(
                            doc["id"],
                            sender=res.get("sender"),
                            date=res.get("date"),
                            document_type=res.get("document_type"),
                            category=res.get("category"),
                            summary=res.get("summary"),
                            notes=res.get("confidence_reason"),
                        )
                        status_msg = f"{res.get('document_type')} / {res.get('category')}"
                    else:
                        status_msg = "LLM Fehler"
                except Exception as e:
                    status_msg = f"Fehler: {e}"

            yield f"data: {_json.dumps({'type': 'progress', 'i': i, 'total': total, 'file': doc['filename'], 'status': status_msg})}\n\n"
            await _asyncio.sleep(0)

        yield f"data: {_json.dumps({'type': 'done', 'total': total})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@router.post("/reclassify-cancel")
def reclassify_cancel():
    _reclassify_cancel.set()
    return {"cancelled": True}


class MFHCalculationRequest(BaseModel):
    year: int
    total_sqm: float = 280.0
    unit_1_sqm: float = 80.0
    unit_2_sqm: float = 80.0


@router.post("/mfh-calculation")
def calculate_mfh_u_allocation(req: MFHCalculationRequest):
    """Calculate the proportional allocation of Gesamthaus Gemeinkosten
    for a given year based on sqm areas."""
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, filename, sender, date, category, summary, notes, keywords "
            "FROM documents WHERE property_unit = 'Gesamthaus' AND date LIKE ? AND status='ok'",
            (f"{req.year}%",)
        ).fetchall()

    costs = [dict(r) for r in rows]
    total_mfh_cost = 0.0
    details = []

    for c in costs:
        doc_id = c["id"]
        # Query services and items sums for exact costs
        with db.get_conn() as conn:
            s_row = conn.execute("SELECT SUM(amount) as s_sum FROM services WHERE document_id = ?", (doc_id,)).fetchone()
            i_row = conn.execute("SELECT SUM(total_price) as i_sum FROM items WHERE document_id = ?", (doc_id,)).fetchone()

        s_sum = s_row["s_sum"] if s_row and s_row["s_sum"] else 0.0
        i_sum = i_row["i_sum"] if i_row and i_row["i_sum"] else 0.0
        doc_cost = max(s_sum, i_sum)

        # Fallback check: parse amount from keywords or notes
        if doc_cost == 0.0:
            keywords = c.get("keywords") or ""
            m = re.search(r'(\d+(?:[\.,]\d{2})?)\s*eur', keywords.lower())
            if m:
                doc_cost = float(m.group(1).replace(".", "").replace(",", "."))

        total_mfh_cost += doc_cost
        details.append({
            "id": doc_id,
            "filename": c["filename"],
            "sender": c["sender"],
            "date": c["date"],
            "cost": doc_cost
        })

    # Proportional Allocation
    owner_sqm = req.total_sqm - req.unit_1_sqm - req.unit_2_sqm
    unit_1_share = (req.unit_1_sqm / req.total_sqm) * total_mfh_cost
    unit_2_share = (req.unit_2_sqm / req.total_sqm) * total_mfh_cost
    owner_share = (owner_sqm / req.total_sqm) * total_mfh_cost

    return {
        "year": req.year,
        "total_gemeinkosten": round(total_mfh_cost, 2),
        "owner_share": round(owner_share, 2),
        "unit_1_share": round(unit_1_share, 2),
        "unit_2_share": round(unit_2_share, 2),
        "total_sqm": req.total_sqm,
        "details": details
    }