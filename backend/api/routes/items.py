"""
Items API – inventory items extracted from invoices.
"""
from datetime import datetime
import asyncio
import json
import anyio
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
import io

from db import items_repo
from db.documents_repo import get_document
from llm import extract_items_from_invoice
from utils import log

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/")
def list_items(
    q: str | None = Query(None),
    category: str | None = Query(None),
    vendor: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    min_price: float | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items, total = items_repo.get_items(
        q=q, category=category, vendor=vendor,
        date_from=date_from, date_to=date_to,
        min_price=min_price, limit=limit, offset=offset,
    )
    return {"total": total, "items": items}


@router.get("/stats")
def get_stats():
    return items_repo.get_stats()


@router.get("/export.csv")
def export_csv(
    q: str | None = Query(None),
    category: str | None = Query(None),
    vendor: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    min_price: float | None = Query(None),
):
    if q or category or vendor or date_from or date_to or min_price:
        items, _ = items_repo.get_items(
            q=q, category=category, vendor=vendor,
            date_from=date_from, date_to=date_to,
            min_price=min_price, limit=10000, offset=0,
        )
    else:
        items = items_repo.get_all_for_export()
    csv_content = items_repo.to_csv(items)
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventar.csv"},
    )


@router.get("/pending-count")
def pending_count():
    """Return count of invoices not yet processed."""
    ids = items_repo.get_unprocessed_invoice_ids()
    return {"pending": len(ids)}


@router.post("/extract-all")
async def extract_all():
    """Batch-process all invoices with SSE streaming progress."""
    async def _stream():
        ids = items_repo.get_unprocessed_invoice_ids()
        total = len(ids)
        processed = 0
        errors = 0
        items_added = 0

        yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"
        await asyncio.sleep(0)

        for i, doc_id in enumerate(ids, 1):
            try:
                doc = get_document(doc_id)
                filename = doc.get("filename", f"doc#{doc_id}") if doc else f"doc#{doc_id}"
                if not doc or not (doc.get("full_text") or ""):
                    errors += 1
                    yield f"data: {json.dumps({'type': 'progress', 'i': i, 'total': total, 'processed': processed, 'items_added': items_added, 'errors': errors, 'file': filename, 'action': 'skipped'})}\n\n"
                    await asyncio.sleep(0)
                    continue
                yield f"data: {json.dumps({'type': 'progress', 'i': i, 'total': total, 'processed': processed, 'items_added': items_added, 'errors': errors, 'file': filename, 'action': 'running'})}\n\n"
                await asyncio.sleep(0)
                _text = doc["full_text"][:4000]
                _vendor = doc.get("sender") or ""
                _date = doc.get("date") or ""
                _fname = filename
                extracted = await anyio.to_thread.run_sync(
                    lambda: extract_items_from_invoice(text=_text, filename=_fname, vendor=_vendor, purchase_date=_date)
                )
                n = 0
                if extracted:
                    n = items_repo.insert_items(doc_id, extracted,
                        extracted_at=datetime.now().isoformat(timespec="seconds"))
                    items_added += n
                processed += 1
                log(f"[ITEMS] [{i}/{total}] {filename} → {n} Artikel")
                yield f"data: {json.dumps({'type': 'progress', 'i': i, 'total': total, 'processed': processed, 'items_added': items_added, 'errors': errors, 'file': filename, 'action': 'done', 'n': n})}\n\n"
            except Exception as e:
                errors += 1
                log(f"[ITEMS] Batch-Fehler doc_id={doc_id}: {e}")
                yield f"data: {json.dumps({'type': 'progress', 'i': i, 'total': total, 'processed': processed, 'items_added': items_added, 'errors': errors, 'file': filename, 'action': 'error', 'msg': str(e)[:80]})}\n\n"
            await asyncio.sleep(0)

        yield f"data: {json.dumps({'type': 'done', 'total': total, 'processed': processed, 'items_added': items_added, 'errors': errors})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/extract/{document_id}")
def extract_single(document_id: int):
    """Extract items from a single invoice document."""
    if items_repo.has_items_for_document(document_id):
        return {"skipped": True, "reason": "Already extracted"}
    doc = get_document(document_id)
    if not doc:
        return {"error": "Document not found"}
    if doc.get("document_type") not in ("Rechnung", "Warenrechnung"):
        return {"error": "Not an invoice"}
    full_text = doc.get("full_text") or ""
    if not full_text:
        return {"error": "No text available"}
    extracted = extract_items_from_invoice(
        text=full_text,
        filename=doc.get("filename", ""),
        vendor=doc.get("sender") or "",
        purchase_date=doc.get("date") or "",
    )
    n = 0
    if extracted:
        n = items_repo.insert_items(
            document_id, extracted,
            extracted_at=datetime.now().isoformat(timespec="seconds"),
        )
    return {"items_added": n, "items": extracted}
