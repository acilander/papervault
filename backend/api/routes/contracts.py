"""
Contracts API – contracts and subscriptions extracted from documents.
"""
import asyncio
import anyio
import json
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import io

from db import contracts_repo
from db.documents_repo import get_document
from llm import extract_contract_from_document
from utils import log

router = APIRouter(prefix="/contracts", tags=["contracts"])


class ContractUpdate(BaseModel):
    partner: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[float] = None
    amount_interval: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    next_due_date: Optional[str] = None
    cancellation_deadline: Optional[str] = None
    notice_period_days: Optional[int] = None
    auto_renews: Optional[bool] = None
    notes: Optional[str] = None


@router.get("/")
def list_contracts(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    partner: Optional[str] = Query(None),
    expiring_within_days: Optional[int] = Query(None),
    sort_by: Optional[str] = Query("end_date"),
    sort_dir: Optional[str] = Query("asc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    contracts, total = contracts_repo.get_contracts(
        q=q, category=category, status=status, partner=partner,
        expiring_within_days=expiring_within_days,
        sort_by=sort_by, sort_dir=sort_dir,
        limit=limit, offset=offset,
    )
    return {"total": total, "contracts": contracts}


@router.get("/stats")
def get_stats():
    return contracts_repo.get_stats()


@router.get("/export.csv")
def export_csv(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    if q or category or status:
        contracts, _ = contracts_repo.get_contracts(
            q=q, category=category, status=status, limit=10000, offset=0,
        )
    else:
        contracts = contracts_repo.get_all_for_export()
    csv_content = contracts_repo.to_csv(contracts)
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=vertraege.csv"},
    )


@router.patch("/{contract_id}")
def update_contract(contract_id: int, body: ContractUpdate):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    contracts_repo.update_contract(contract_id, **fields)
    return {"updated": True}


@router.delete("/{contract_id}")
def delete_contract(contract_id: int):
    contracts_repo.delete_contract(contract_id)
    return {"deleted": True}


@router.get("/pending-count")
def pending_count():
    """Return count of contract documents not yet processed."""
    ids = contracts_repo.get_unprocessed_contract_doc_ids()
    return {"pending": len(ids)}


@router.post("/extract-all")
async def extract_all():
    """Batch-process all contract documents with SSE streaming progress."""
    async def _stream():
        ids = contracts_repo.get_unprocessed_contract_doc_ids()
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
                _sender = doc.get("sender") or ""
                _dtype = doc.get("document_type") or ""
                _fname = filename
                contract = await anyio.to_thread.run_sync(
                    lambda: extract_contract_from_document(text=_text, filename=_fname, sender=_sender, doc_type=_dtype)
                )
                if contract:
                    contracts_repo.insert_contract(doc_id, contract,
                        extracted_at=datetime.now().isoformat(timespec="seconds"))
                    added += 1
                processed += 1
                log(f"[CONTRACTS] [{i}/{total}] {filename} → {contract.get('partner','?') if contract else 'kein Ergebnis'}")
                yield f"data: {json.dumps({'type': 'progress', 'i': i, 'total': total, 'processed': processed, 'added': added, 'errors': errors, 'file': filename, 'action': 'done', 'partner': contract.get('partner','') if contract else ''})}\n\n"
            except Exception as e:
                errors += 1
                log(f"[CONTRACTS] Batch-Fehler doc_id={doc_id}: {e}")
                yield f"data: {json.dumps({'type': 'progress', 'i': i, 'total': total, 'processed': processed, 'added': added, 'errors': errors, 'file': filename, 'action': 'error', 'msg': str(e)[:80]})}\n\n"
            await asyncio.sleep(0)

        yield f"data: {json.dumps({'type': 'done', 'total': total, 'processed': processed, 'added': added, 'errors': errors})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/extract/{document_id}")
def extract_single(document_id: int):
    """Extract contract from a single document."""
    if contracts_repo.has_contract_for_document(document_id):
        return {"skipped": True, "reason": "Already extracted"}
    doc = get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    CONTRACT_TYPES = {"Vertrag", "Kündigung", "Mahnung", "Abonnement"}
    if doc.get("document_type") not in CONTRACT_TYPES:
        return {"error": f"document_type '{doc.get('document_type')}' not supported"}
    full_text = doc.get("full_text") or ""
    if not full_text:
        return {"error": "No text available"}
    contract = extract_contract_from_document(
        text=full_text,
        filename=doc.get("filename", ""),
        sender=doc.get("sender") or "",
        doc_type=doc.get("document_type") or "",
    )
    if not contract:
        return {"error": "Extraction failed"}
    new_id = contracts_repo.insert_contract(
        document_id, contract,
        extracted_at=datetime.now().isoformat(timespec="seconds"),
    )
    return {"contract_id": new_id, "contract": contract}
