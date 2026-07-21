from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response

import db
import db.transactions_repo as tx_repo
from api.models import (
    TransactionCreate,
    TransactionUpdate,
    TransactionDocAdd,
    TransactionOut,
    TransactionDetailOut
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/", response_model=list[TransactionOut])
def list_transactions(
    status: Optional[str] = Query(None, description="Filter by status: open, closed, cancelled"),
    type: Optional[str] = Query(None, description="Filter by type: discrete, continuous"),
):
    """List all transactions, optionally filtered by status or type."""
    return tx_repo.list_transactions(status=status, type_val=type)


@router.post("/", response_model=TransactionDetailOut, status_code=201)
def create_transaction(body: TransactionCreate):
    """Create a new transaction (Vorgang)."""
    tx_id = tx_repo.create_transaction(title=body.title, status=body.status, type_val=body.type)
    tx = tx_repo.get_transaction(tx_id)
    if not tx:
        raise HTTPException(status_code=500, detail="Vorgang konnte nicht angelegt werden")
    return tx


@router.get("/{tx_id}", response_model=TransactionDetailOut)
def get_transaction(tx_id: int):
    """Retrieve a single transaction with all linked documents."""
    tx = tx_repo.get_transaction(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")
    return tx


@router.patch("/{tx_id}", response_model=TransactionDetailOut)
def update_transaction(tx_id: int, body: TransactionUpdate):
    """Update transaction metadata (title, status, type)."""
    tx = tx_repo.get_transaction(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")
        
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        tx_repo.update_transaction(tx_id, **updates)
        
    updated = tx_repo.get_transaction(tx_id)
    return updated


@router.delete("/{tx_id}", status_code=24)
def delete_transaction(tx_id: int):
    """Delete a transaction."""
    tx = tx_repo.get_transaction(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")
    tx_repo.delete_transaction(tx_id)
    return Response(status_code=204)


@router.post("/{tx_id}/documents", response_model=TransactionDetailOut)
def add_document(tx_id: int, body: TransactionDocAdd):
    """Link a document to a transaction with a specific role."""
    tx = tx_repo.get_transaction(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")
        
    doc = db.get_document(body.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
        
    tx_repo.add_document_to_transaction(tx_id, body.document_id, body.role)
    return tx_repo.get_transaction(tx_id)


@router.delete("/{tx_id}/documents/{doc_id}", response_model=TransactionDetailOut)
def remove_document(tx_id: int, doc_id: int):
    """Unlink a document from a transaction."""
    tx = tx_repo.get_transaction(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")
        
    tx_repo.remove_document_from_transaction(tx_id, doc_id)
    return tx_repo.get_transaction(tx_id)


@router.get("/document/{doc_id}", response_model=list[dict])
def get_document_transactions(doc_id: int):
    """Retrieve all transactions linked to a specific document."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return tx_repo.get_transactions_for_document(doc_id)
