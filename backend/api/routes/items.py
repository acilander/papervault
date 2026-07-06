"""
Items API – inventory items extracted from invoices.
"""
from datetime import datetime
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


@router.post("/extract-all")
def extract_all():
    """Batch-process all invoices that have no items yet."""
    ids = items_repo.get_unprocessed_invoice_ids()
    total = len(ids)
    processed = 0
    errors = 0
    items_added = 0

    for doc_id in ids:
        try:
            doc = get_document(doc_id)
            if not doc:
                continue
            full_text = doc.get("full_text") or ""
            if not full_text:
                continue
            extracted = extract_items_from_invoice(
                text=full_text,
                filename=doc.get("filename", ""),
                vendor=doc.get("sender") or "",
                purchase_date=doc.get("date") or "",
            )
            if extracted:
                n = items_repo.insert_items(
                    doc_id, extracted,
                    extracted_at=datetime.now().isoformat(timespec="seconds"),
                )
                items_added += n
            processed += 1
        except Exception as e:
            log(f"[ITEMS] Batch-Fehler für doc_id={doc_id}: {e}")
            errors += 1

    return {
        "total_invoices": total,
        "processed": processed,
        "errors": errors,
        "items_added": items_added,
    }


@router.post("/extract/{document_id}")
def extract_single(document_id: int):
    """Extract items from a single invoice document."""
    if items_repo.has_items_for_document(document_id):
        return {"skipped": True, "reason": "Already extracted"}
    doc = get_document(document_id)
    if not doc:
        return {"error": "Document not found"}
    if doc.get("document_type") != "Rechnung":
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
