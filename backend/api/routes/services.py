"""
Services API – service/expense entries extracted from invoices (non-physical goods).
"""
import asyncio
import anyio
import json
from datetime import datetime
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
import io

from db import services_repo
from db.documents_repo import get_document
from llm import extract_services_from_invoice
from utils import log

router = APIRouter(prefix="/services", tags=["services"])


@router.get("/")
def list_services(
    q: str | None = Query(None),
    category: str | None = Query(None),
    provider: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    min_amount: float | None = Query(None),
    sort_by: str | None = Query("service_date"),
    sort_dir: str | None = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    services, total = services_repo.get_services(
        q=q, category=category, provider=provider,
        date_from=date_from, date_to=date_to,
        min_amount=min_amount, sort_by=sort_by, sort_dir=sort_dir,
        limit=limit, offset=offset,
    )
    return {"total": total, "services": services}


@router.get("/stats")
def get_stats():
    return services_repo.get_stats()


@router.get("/pending-count")
def pending_count():
    ids = services_repo.get_unprocessed_service_invoice_ids()
    return {"pending": len(ids)}


@router.get("/export.csv")
def export_csv(
    q: str | None = Query(None),
    category: str | None = Query(None),
    provider: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    min_amount: float | None = Query(None),
):
    if any([q, category, provider, date_from, date_to, min_amount]):
        services, _ = services_repo.get_services(
            q=q, category=category, provider=provider,
            date_from=date_from, date_to=date_to,
            min_amount=min_amount, limit=10000, offset=0,
        )
    else:
        services = services_repo.get_all_for_export()
    csv_content = services_repo.to_csv(services)
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ausgaben.csv"},
    )


@router.post("/extract-all")
async def extract_all():
    """Batch-process all invoices with SSE streaming progress."""
    async def _stream():
        ids = services_repo.get_unprocessed_service_invoice_ids()
        total = len(ids)
        processed = 0
        errors = 0
        added = 0

        yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"
        await asyncio.sleep(0)

        for i, doc_id in enumerate(ids, 1):
            try:
                doc = get_document(doc_id)
                filename = doc.get("filename", f"doc#{doc_id}") if doc else f"doc#{doc_id}"
                if not doc or not (doc.get("full_text") or ""):
                    errors += 1
                    yield f"data: {json.dumps({'type': 'progress', 'i': i, 'total': total, 'processed': processed, 'added': added, 'errors': errors, 'file': filename, 'action': 'skipped'})}\n\n"
                    await asyncio.sleep(0)
                    continue
                yield f"data: {json.dumps({'type': 'progress', 'i': i, 'total': total, 'processed': processed, 'added': added, 'errors': errors, 'file': filename, 'action': 'running'})}\n\n"
                await asyncio.sleep(0)
                _text = doc["full_text"][:4000]
                _vendor = doc.get("sender") or ""
                _idate = doc.get("date") or ""
                _fname = filename
                extracted = await anyio.to_thread.run_sync(
                    lambda: extract_services_from_invoice(text=_text, filename=_fname, vendor=_vendor, invoice_date=_idate)
                )
                n = 0
                if extracted:
                    n = services_repo.insert_services(
                        doc_id, extracted,
                        extracted_at=datetime.now().isoformat(timespec="seconds"),
                    )
                    added += n
                processed += 1
                log(f"[SERVICES] [{i}/{total}] {filename} → {n} Einträge")
                yield f"data: {json.dumps({'type': 'progress', 'i': i, 'total': total, 'processed': processed, 'added': added, 'errors': errors, 'file': filename, 'action': 'done', 'n': n})}\n\n"
            except Exception as e:
                errors += 1
                log(f"[SERVICES] Batch-Fehler doc_id={doc_id}: {e}")
                yield f"data: {json.dumps({'type': 'progress', 'i': i, 'total': total, 'processed': processed, 'added': added, 'errors': errors, 'file': filename, 'action': 'error', 'msg': str(e)[:80]})}\n\n"
            await asyncio.sleep(0)

        yield f"data: {json.dumps({'type': 'done', 'total': total, 'processed': processed, 'added': added, 'errors': errors})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/extract/{document_id}")
def extract_single(document_id: int):
    if services_repo.has_services_for_document(document_id):
        return {"skipped": True, "reason": "Already extracted"}
    doc = get_document(document_id)
    if not doc:
        return {"error": "Document not found"}
    full_text = doc.get("full_text") or ""
    if not full_text:
        return {"error": "No text available"}
    extracted = extract_services_from_invoice(
        text=full_text,
        filename=doc.get("filename", ""),
        vendor=doc.get("sender") or "",
        invoice_date=doc.get("date") or "",
    )
    n = 0
    if extracted:
        n = services_repo.insert_services(
            document_id, extracted,
            extracted_at=datetime.now().isoformat(timespec="seconds"),
        )
    return {"services_added": n, "services": extracted}
