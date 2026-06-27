import io
import os
import queue
import subprocess
import sys
import threading
import zipfile
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import db
import feedback as fb
import storage
from api.models import DocumentOut, DocumentUpdate

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=list[DocumentOut])
def list_documents(
    q: Optional[str] = Query(None, description="Volltext-Suche"),
    category: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    sender: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tax_relevant: Optional[int] = Query(None),
    tag: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    return db.search_documents(
        query=q, category=category, year=year, sender=sender,
        status=status, tax_relevant=tax_relevant, tag=tag,
        limit=limit, offset=offset,
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

    # Record correction as few-shot example if classification fields changed
    fb.record_correction(original=doc, corrected=updates)

    # Auto-apply pinned_category for this sender (no LLM needed)
    sender_name = updates.get("sender") or doc.get("sender")
    if sender_name and sender_name in storage.sender_registry:
        pinned = storage.sender_registry[sender_name].get("pinned_category")
        if pinned and "category" not in updates:
            updates["category"] = pinned

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
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=\"{doc['filename']}\""},
    )


@router.post("/{doc_id}/open", status_code=204)
def open_in_explorer(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    path = doc["file_path"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Datei nicht gefunden: {path}")
    subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])


@router.post("/{doc_id}/rename")
def rename_document(doc_id: int, body: dict):
    """Rename the PDF file on disk and update the DB."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    new_name: str = (body.get("filename") or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Kein Dateiname angegeben")
    if not new_name.lower().endswith(".pdf"):
        new_name += ".pdf"
    # Sanitize: remove path separators
    new_name = os.path.basename(new_name)
    src = doc["file_path"]
    dest = os.path.join(os.path.dirname(src), new_name)
    if os.path.abspath(src) != os.path.abspath(dest):
        if os.path.exists(dest):
            raise HTTPException(status_code=409, detail=f"Datei existiert bereits: {new_name}")
        if os.path.exists(src):
            os.rename(src, dest)
    db.update_document(doc_id, file_path=dest, filename=new_name)
    return db.get_document(doc_id)


@router.post("/{doc_id}/reprocess", status_code=202)
def reprocess_document(doc_id: int):
    """Queue the PDF for re-classification by the archiver worker."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    path = doc["file_path"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Datei nicht gefunden: {path}")
    # Reset status to trigger reprocessing
    db.update_document(doc_id, status="pending")
    # Try to trigger via the archiver's queue if it is running in-process
    try:
        import archive
        t = threading.Thread(target=archive.process_pdf, args=(path,), daemon=True)
        t.start()
    except Exception:
        pass
    return {"detail": "Neu-Klassifizierung gestartet", "file_path": path}


@router.get("/expiring")
def get_expiring(days: int = Query(30, ge=1, le=365)):
    return db.get_expiring_documents(days=days)


@router.get("/tax-export")
def tax_export(year: Optional[str] = Query(None)):
    """Stream a ZIP of all tax-relevant PDFs for the given year."""
    docs = db.get_tax_documents(year=year)
    existing = [d for d in docs if os.path.exists(d["file_path"])]
    if not existing:
        raise HTTPException(status_code=404, detail="Keine steuerrelevanten Dokumente gefunden")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in existing:
            arcname = f"{doc['tax_year'] or 'kein-jahr'}/{doc['filename']}"
            zf.write(doc["file_path"], arcname=arcname)
    buf.seek(0)
    label = f"steuer_{year}" if year else "steuer_alle"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={label}.zip"},
    )


@router.delete("/{doc_id}/delete-file", status_code=204)
def delete_document_with_file(doc_id: int):
    """Delete the PDF from disk AND remove the DB entry."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    path = doc["file_path"]
    db.delete_document(doc_id)
    if path and os.path.exists(path):
        os.remove(path)
