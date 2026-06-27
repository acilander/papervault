import os
import subprocess
import sys
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import db
from api.models import DocumentOut, DocumentUpdate

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=list[DocumentOut])
def list_documents(
    q: Optional[str] = Query(None, description="Volltext-Suche"),
    category: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    sender: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    return db.search_documents(
        query=q, category=category, year=year,
        sender=sender, status=status, limit=limit, offset=offset,
    )


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return doc


@router.patch("/{doc_id}", response_model=DocumentOut)
def update_document(doc_id: int, body: DocumentUpdate):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        db.update_document(doc_id, **updates)
    return db.get_document(doc_id)


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    db.delete_document(doc_id)


@router.get("/{doc_id}/file")
def serve_pdf(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    path = doc["file_path"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Datei nicht gefunden: {path}")
    return FileResponse(path, media_type="application/pdf", filename=doc["filename"])


@router.post("/{doc_id}/open", status_code=204)
def open_in_explorer(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    path = doc["file_path"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Datei nicht gefunden: {path}")
    subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
