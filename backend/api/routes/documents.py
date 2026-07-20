import io
import os
import re
import shutil
import subprocess
import zipfile
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse

import db
import feedback as fb
import storage
from api.models import DocumentOut, DocumentListOut, DocumentUpdate
from config import SOURCE_DIR, TARGET_BASE, CATEGORY_FOLDER_MAP, SENDER_SUBFOLDERS
from pdf_utils import unique_path, generate_thumbnail, get_thumbnail_path

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=list[DocumentListOut])
def list_documents(
    q: Optional[str] = Query(None, description="Volltext-Suche"),
    category: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    sender: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tax_relevant: Optional[int] = Query(None),
    tag: Optional[str] = Query(None),
    no_sender: Optional[int] = Query(None),
    low_value: Optional[int] = Query(None),
    confidence: Optional[str] = Query(None, description="Filter by confidence: low, medium, high"),
    sort_by: Optional[str] = Query("archived_at", description="Column to sort by"),
    sort_dir: Optional[str] = Query("desc", description="Sort direction: asc or desc"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    response: Response = None,
):
    filter_kwargs = dict(
        query=q, category=category, year=year, sender=sender,
        status=status, tax_relevant=tax_relevant, tag=tag,
        no_sender=bool(no_sender), low_value=low_value, confidence=confidence,
    )
    sort_kwargs = dict(sort_by=sort_by, sort_dir=sort_dir)
    docs = db.search_documents(**filter_kwargs, **sort_kwargs, limit=limit, offset=offset)
    total = db.count_documents(**filter_kwargs)
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
        response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return docs


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


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return doc


@router.get("/{doc_id}/traces")
def get_document_traces(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return db.get_traces_for_document(doc_id)


@router.patch("/{doc_id}", response_model=DocumentOut)
def update_document(doc_id: int, body: DocumentUpdate):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    if (doc.get("status") == "locked" or doc.get("verified") == 1) and "verified" not in body.model_fields_set:
        raise HTTPException(status_code=409, detail="Dokument ist gesperrt/verifiziert. Entsperren vor dem Bearbeiten.")
    if doc.get("status") == "ignored" and "status" not in body.model_fields_set:
        raise HTTPException(status_code=409, detail="Irrelevantes Dokument muss zuerst wiederhergestellt werden.")
    updates = {k: v for k, v in body.model_dump().items() if k in body.model_fields_set}

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

    updated_doc = db.get_document(doc_id)

    # --- Cascade effects ---
    old_sender = doc.get("sender")
    new_sender = updates.get("sender")
    sender_changed = "sender" in updates and new_sender != old_sender

    new_category = updates.get("category") or updated_doc.get("category")
    effective_sender = updated_doc.get("sender")

    # 1. Sender-Registry: record new sender/category, cleanup old if orphaned
    if updated_doc.get("status") == "ok" and effective_sender:
        if sender_changed or "category" in updates:
            storage.record_sender(new_category, effective_sender)
    if sender_changed and old_sender:
        import db.sender_repo as _sr
        if _sr.cleanup_if_orphaned(old_sender):
            storage._refresh_cache()

    # 2. Sync items.vendor, services.provider, contracts.partner when sender changed
    if sender_changed and new_sender:
        from db.items_repo import update_vendor_for_document
        from db.services_repo import update_provider_for_document
        from db.contracts_repo import update_partner_for_document
        update_vendor_for_document(doc_id, new_sender)
        update_provider_for_document(doc_id, new_sender)
        update_partner_for_document(doc_id, new_sender)

    # 3. Rename file on disk for ok-documents when sender, date or document_type changed
    filename_fields = {"sender", "date", "document_type"}
    if updated_doc.get("status") == "ok" and filename_fields & set(updates.keys()):
        from pdf_utils import build_filename
        current_path = updated_doc.get("file_path")
        if current_path and os.path.exists(current_path):
            current_name = os.path.basename(current_path)
            # Word and Excel files must never be renamed!
            if current_path.lower().endswith(".pdf"):
                new_name = build_filename(updated_doc, current_name)
            else:
                new_name = current_name
            if new_name != current_name:
                new_path = os.path.join(os.path.dirname(current_path), new_name)
                new_path = unique_path(new_path)
                try:
                    os.rename(current_path, new_path)
                    db.update_document(doc_id, file_path=new_path, filename=os.path.basename(new_path))
                    updated_doc = db.get_document(doc_id)
                except OSError:
                    pass

    return updated_doc


def _ensure_content_hash(doc: dict) -> str | None:
    """Return the document's content hash, computing it from disk if missing."""
    if doc.get("content_hash"):
        return doc["content_hash"]
    path = doc.get("file_path")
    if not path or not os.path.exists(path):
        return None
    try:
        from pipeline.steps import compute_content_hash
        from pdf_utils import extract_text
        text, _ = extract_text(path)
        content_hash, _ = compute_content_hash(path, text or "")
        return content_hash
    except Exception:
        return None


@router.post("/{doc_id}/ignore", status_code=200)
def ignore_document(doc_id: int):
    """Mark a document as irrelevant and block its hash from re-import."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    content_hash = _ensure_content_hash(doc)
    if content_hash:
        db.protect_document_hash(content_hash, "ignored", document_id=doc_id, filename=doc.get("filename"))
    db.update_document(doc_id, status="ignored")
    return db.get_document(doc_id)


@router.post("/{doc_id}/unignore", status_code=200)
def unignore_document(doc_id: int):
    """Restore an ignored document and remove its hash from the blocklist."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    if doc.get("status") != "ignored":
        raise HTTPException(status_code=400, detail="Dokument ist nicht als irrelevant markiert")
    content_hash = doc.get("content_hash") or _ensure_content_hash(doc)
    if content_hash:
        db.unprotect_document_hash(hash_value=content_hash)
    db.update_document(doc_id, status="ok")
    return db.get_document(doc_id)


@router.post("/{doc_id}/verify", status_code=200)
def verify_document(doc_id: int):
    """Mark a document as verified (locked)."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    db.update_document(doc_id, verified=1)
    return db.get_document(doc_id)


@router.post("/{doc_id}/unverify", status_code=200)
def unverify_document(doc_id: int):
    """Unverify a document (unlock)."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    db.update_document(doc_id, verified=0)
    return db.get_document(doc_id)


@router.post("/{doc_id}/lock", status_code=200)
def lock_document(doc_id: int):
    """Lock a verified document to prevent accidental edits or reclassification."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    content_hash = _ensure_content_hash(doc)
    if content_hash:
        db.protect_document_hash(content_hash, "locked", document_id=doc_id, filename=doc.get("filename"))
    db.update_document(doc_id, status="locked")
    return db.get_document(doc_id)


@router.post("/{doc_id}/unlock", status_code=200)
def unlock_document(doc_id: int):
    """Unlock a document so it can be edited again."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    if doc.get("status") != "locked":
        raise HTTPException(status_code=400, detail="Dokument ist nicht gesperrt")
    content_hash = doc.get("content_hash") or _ensure_content_hash(doc)
    if content_hash:
        db.unprotect_document_hash(hash_value=content_hash)
    db.update_document(doc_id, status="ok")
    return db.get_document(doc_id)


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    sender_name = doc.get("sender")
    db.delete_document(doc_id)
    if sender_name:
        import db.sender_repo as _sr
        if _sr.cleanup_if_orphaned(sender_name):
            storage._refresh_cache()


@router.get("/{doc_id}/file")
def serve_pdf(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    path = doc["file_path"]

    # [Fix 4: Lazy Auto-Healing] Check if file exists on disk
    if not os.path.exists(path):
        if doc["status"] != "missing":
            db.update_document(doc_id, status="missing")
        raise HTTPException(status_code=404, detail=f"Datei wurde auf dem Datenträger nicht gefunden (Status in DB auf 'missing' gesetzt): {path}")

    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=\"{doc['filename']}\""},
    )


@router.get("/{doc_id}/thumbnail")
async def get_thumbnail(doc_id: int):
    """Return cached WebP thumbnail; generate on-the-fly if missing."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    thumb = get_thumbnail_path(doc_id)
    media_type = "image/jpeg"
    if not os.path.exists(thumb):
        # Fallback: legacy .webp thumbnail from before migration
        webp_path = thumb.replace(".jpg", ".webp")
        if os.path.exists(webp_path):
            return FileResponse(webp_path, media_type="image/webp",
                                headers={"Cache-Control": "public, max-age=86400"})
        path = doc.get("file_path", "")
        if not path or not os.path.exists(path):
            raise HTTPException(status_code=404, detail="PDF nicht verfügbar")
        result = await run_in_threadpool(generate_thumbnail, path, doc_id)
        if not result:
            raise HTTPException(status_code=500, detail="Thumbnail konnte nicht erstellt werden")
    return FileResponse(thumb, media_type=media_type,
                        headers={"Cache-Control": "public, max-age=86400"})


@router.post("/{doc_id}/open", status_code=204)
def open_in_explorer(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    path = doc["file_path"]

    # [Fix 5: Secure OS Command]
    # Check if path is absolute and actually exists to prevent path traversal/command injection
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        if doc["status"] != "missing":
            db.update_document(doc_id, status="missing")
        raise HTTPException(status_code=404, detail=f"Datei nicht gefunden: {abs_path}")

    try:
        if os.name == "nt":
            # Safely request Windows Explorer to select the file using a list of arguments
            subprocess.Popen(["explorer.exe", "/select,", abs_path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", abs_path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(abs_path)])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Öffnen: {e}")


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


@router.get("/{doc_id}/original")
def get_original_for_duplicate(doc_id: int):
    """For a duplicate document, return the original document it was matched against."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    if doc.get("status") != "duplicate":
        raise HTTPException(status_code=400, detail="Dokument ist kein Duplikat")
    content_hash = doc.get("content_hash")
    if not content_hash:
        raise HTTPException(status_code=404, detail="Kein Hash gespeichert")
    original = db.get_document_by_hash(content_hash)
    if not original:
        raise HTTPException(status_code=404, detail="Original-Dokument nicht mehr in DB")
    return original


@router.post("/reprocess-no-sender", status_code=202)
def reprocess_documents_without_sender(body: dict = {}):
    """Re-process all archived/review documents that have no sender detected.
    Moves them back to inbox so the archiver can re-classify them.
    Optional body: {hint: str}
    """
    hint = (body or {}).get("hint", "").strip()
    docs = db.get_documents_without_sender()
    queued = 0
    skipped = 0
    errors = []
    for doc in docs:
        try:
            path = os.path.normpath(doc["file_path"])
            if not os.path.exists(path):
                skipped += 1
                continue
            os.makedirs(SOURCE_DIR, exist_ok=True)
            inbox_path = unique_path(os.path.join(SOURCE_DIR, os.path.basename(path)))
            shutil.move(path, inbox_path)
            existing = db.get_document_by_path(inbox_path)
            if existing and existing["id"] != doc["id"]:
                db.delete_document(existing["id"])
            db.update_document(doc["id"], status="pending", file_path=inbox_path, sender=None)
            if hint:
                hint_path = os.path.splitext(inbox_path)[0] + ".hint"
                try:
                    with open(hint_path, "w", encoding="utf-8") as f:
                        f.write(hint)
                except Exception:
                    pass
            queued += 1
        except Exception as e:
            errors.append({"id": doc["id"], "file": doc.get("filename"), "error": str(e)})
    return {"queued": queued, "skipped": skipped, "errors": errors}


@router.post("/{doc_id}/reprocess", status_code=202)
def reprocess_document(doc_id: int, body: dict = {}):
    """Queue the PDF for re-classification by the archiver worker. Optional body: {hint: str}"""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    if doc.get("status") in ("locked", "ignored"):
        raise HTTPException(status_code=409, detail=f"Dokument hat Status '{doc['status']}' und kann nicht neu klassifiziert werden.")
    path = os.path.normpath(doc["file_path"])
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Datei nicht gefunden: {path}")
    os.makedirs(SOURCE_DIR, exist_ok=True)
    inbox_path = unique_path(os.path.join(SOURCE_DIR, os.path.basename(path)))
    # Move file back to Inbox so the archiver watcher picks it up
    try:
        shutil.move(path, inbox_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Konnte Datei nicht in Inbox verschieben: {e}")
    # Remove any stale DB entry with the same inbox_path to avoid UNIQUE constraint violation
    existing = db.get_document_by_path(inbox_path)
    if existing and existing["id"] != doc_id:
        db.delete_document(existing["id"])
    db.update_document(doc_id, status="pending", file_path=inbox_path)
    hint = (body or {}).get("hint", "").strip()
    if hint:
        hint_path = os.path.splitext(inbox_path)[0] + ".hint"
        try:
            with open(hint_path, "w", encoding="utf-8") as f:
                f.write(hint)
        except Exception:
            pass
    return {"detail": "Datei zurück in Inbox verschoben – Archiver klassifiziert neu.", "file_path": inbox_path}


@router.post("/{doc_id}/reclassify", status_code=200)
def reclassify_document_live(doc_id: int, body: dict = {}):
    """Synchronously re-classify the document text via LLM. Optional body: {hint: str}"""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    if doc.get("status") in ("locked", "ignored") or doc.get("verified") == 1:
        raise HTTPException(status_code=409, detail="Dokument ist gesperrt/verifiziert und kann nicht neu klassifiziert werden.")
    
    text = doc.get("full_text") or ""
    if not text:
        from pdf_utils import extract_text
        text, _ = extract_text(doc["file_path"])
        if text:
            db.update_document(doc_id, full_text=text)
            
    from pdf_utils import prepare_text_for_llm
    safe_text = prepare_text_for_llm(text)
            
    hint = (body or {}).get("hint")
    from llm.classify import classify_document
    result = classify_document(safe_text=safe_text, filename=doc["filename"], user_hint=hint)
    if not result:
        raise HTTPException(status_code=500, detail="KI-Klassifizierung fehlgeschlagen.")
        
    db.update_document(doc_id, **result)
    updated_doc = db.get_document(doc_id)

    # --- Cascade effects ---
    old_sender = doc.get("sender")
    new_sender = result.get("sender")
    sender_changed = new_sender != old_sender

    new_category = result.get("category") or updated_doc.get("category")
    effective_sender = updated_doc.get("sender")

    # 1. Sender-Registry: record new sender/category, cleanup old if orphaned
    if updated_doc.get("status") == "ok" and effective_sender:
        storage.record_sender(new_category, effective_sender)
    if sender_changed and old_sender:
        import db.sender_repo as _sr
        if _sr.cleanup_if_orphaned(old_sender):
            storage._refresh_cache()

    # 2. Sync items.vendor, services.provider, contracts.partner when sender changed
    if sender_changed and new_sender:
        from db.items_repo import update_vendor_for_document
        from db.services_repo import update_provider_for_document
        from db.contracts_repo import update_partner_for_document
        update_vendor_for_document(doc_id, new_sender)
        update_provider_for_document(doc_id, new_sender)
        update_partner_for_document(doc_id, new_sender)

    # 3. Rename file on disk for ok-documents when sender, date or document_type changed
    filename_fields = {"sender", "date", "document_type"}
    if updated_doc.get("status") == "ok" and filename_fields & set(result.keys()):
        from pdf_utils import build_filename, unique_path
        current_path = updated_doc.get("file_path")
        if current_path and os.path.exists(current_path):
            current_name = os.path.basename(current_path)
            if current_path.lower().endswith(".pdf"):
                new_name = build_filename(updated_doc, current_name)
            else:
                new_name = current_name
            if new_name != current_name:
                new_path = os.path.join(os.path.dirname(current_path), new_name)
                new_path = unique_path(new_path)
                try:
                    os.rename(current_path, new_path)
                    db.update_document(doc_id, file_path=new_path, filename=os.path.basename(new_path))
                    updated_doc = db.get_document(doc_id)
                except OSError:
                    pass

    return updated_doc


@router.post("/{doc_id}/confirm", status_code=200)
def confirm_document(doc_id: int):
    """Move document from review/ to final archive folder and set status=ok."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    if doc["status"] in ("locked", "ignored"):
        raise HTTPException(status_code=409, detail=f"Dokument hat Status '{doc['status']}' und kann nicht bestätigt werden.")
    if doc["status"] != "review":
        raise HTTPException(status_code=400, detail=f"Dokument hat Status '{doc['status']}', erwartet 'review'")

    # Atomically claim the document to prevent race conditions (double-click / concurrent requests)
    from db.documents_repo import claim_document_status
    if not claim_document_status(doc_id, "review", "processing"):
        raise HTTPException(status_code=409, detail="Dokument wird bereits verarbeitet oder hat sich geändert")
    doc = db.get_document(doc_id)

    path = doc["file_path"]
    if not os.path.exists(path):
        db.update_document(doc_id, status="review")
        raise HTTPException(status_code=404, detail=f"Datei nicht gefunden: {path}")

    from pipeline.steps import archive_file_on_disk
    from pdf_utils import build_filename, is_cryptic_filename

    category = doc.get("category") or "Sonstiges"
    sender = doc.get("sender")
    current_name = os.path.basename(path)

    try:
        # Regenerate filename from current (possibly user-corrected) metadata
        # Word and Excel files must never be renamed!
        if path.lower().endswith(".pdf"):
            new_name = build_filename(doc, current_name)
        else:
            new_name = current_name
        if new_name != current_name:
            renamed_path = os.path.join(os.path.dirname(path), new_name)
            if not os.path.exists(renamed_path):
                os.rename(path, renamed_path)
                path = renamed_path

        # Call centralized archiving helper
        dest_pdf = archive_file_on_disk(path, category, sender, doc.get("date"),
                                        document_type=doc.get("document_type"), iban=doc.get("iban"))

        db.update_document(doc_id, status="ok", file_path=dest_pdf, filename=os.path.basename(dest_pdf))
        storage.record_sender(category, sender)
        return {"detail": "Dokument bestaetigt und archiviert.", "file_path": dest_pdf}
    except Exception:
        db.update_document(doc_id, status="review")
        raise


@router.post("/bulk-update")
def bulk_update(body: dict):
    """Apply field updates to multiple documents at once.
    Body: { ids: [1,2,3], fields: { category: "...", sender: "...", document_type: "..." } }
    Only sender, category, document_type, date, notes are allowed.
    Locked and ignored documents are skipped."""
    ids = body.get("ids", [])
    fields = body.get("fields", {})
    if not ids:
        raise HTTPException(status_code=400, detail="Keine Dokument-IDs angegeben")
    ALLOWED = {"sender", "category", "document_type", "date", "notes"}
    filtered = {k: v for k, v in fields.items() if k in ALLOWED}
    if not filtered:
        raise HTTPException(status_code=400, detail="Keine gültigen Felder zum Aktualisieren")
    # Skip protected documents
    allowed_ids = [doc_id for doc_id in ids
                   if (doc := db.get_document(doc_id)) and doc.get("status") not in ("locked", "ignored")]
    skipped = len(ids) - len(allowed_ids)
    updated = db.bulk_update_documents(allowed_ids, filtered) if allowed_ids else 0
    return {"updated": updated, "skipped": skipped + len(allowed_ids) - updated}


@router.get("/export/csv")
def export_csv(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    sender: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """Export the current filtered document list as a CSV file."""
    import csv
    docs = db.search_documents(query=q, category=category, year=year, sender=sender,
                               status=status, limit=99999)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["ID", "Dateiname", "Absender", "Datum", "Typ", "Kategorie",
                     "Status", "Archiviert", "Zusammenfassung"])
    for d in docs:
        writer.writerow([
            d.get("id"), d.get("filename"), d.get("sender", ""),
            d.get("date", ""), d.get("document_type", ""), d.get("category", ""),
            d.get("status", ""), d.get("archived_at", "")[:10],
            (d.get("summary") or "").replace("\n", " "),
        ])
    output = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        iter([output]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=\"dokumente.csv\""},
    )


@router.post("/~migrate-bank-folders")
def migrate_bank_folders():
    """One-time migration: extract IBAN from full_text for Bank & Finanzen docs
    and move them into the new IBAN subfolder structure."""
    import re as _re
    from pipeline.steps import archive_file_on_disk as _archive
    from db.connection import get_conn as _get_conn

    _IBAN_RE = _re.compile(r'\b(DE\d{2}[\s]?\d{4}[\s]?\d{4}[\s]?\d{4}[\s]?\d{4}[\s]?\d{2})\b')

    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM documents WHERE category = 'Bank & Finanzen' AND status = 'ok'"
        ).fetchall()
    docs = [dict(r) for r in rows]

    migrated, skipped, errors = 0, 0, []

    for doc in docs:
        existing_iban = doc.get("iban")
        if not existing_iban:
            full_text = doc.get("full_text") or ""
            match = _IBAN_RE.search(full_text)
            if match:
                iban_raw = _re.sub(r'\s+', '', match.group(1)).upper()
                if _re.match(r'^DE\d{20}$', iban_raw):
                    existing_iban = iban_raw
                    db.update_document(doc["id"], iban=existing_iban)

        src = doc.get("file_path") or ""
        if not os.path.exists(src):
            skipped += 1
            continue

        try:
            dest = _archive(src, "Bank & Finanzen", doc.get("sender"), doc.get("date"),
                            document_type=doc.get("document_type"), iban=existing_iban)
            if os.path.abspath(dest) != os.path.abspath(src):
                db.update_document(doc["id"], file_path=dest, filename=os.path.basename(dest))
                migrated += 1
            else:
                skipped += 1
        except Exception as e:
            errors.append({"id": doc["id"], "filename": doc.get("filename"), "error": str(e)})

    return {"migrated": migrated, "skipped": skipped, "errors": errors}


@router.delete("/{doc_id}/delete-file", status_code=204)
def delete_document_with_file(doc_id: int):
    """Delete the PDF from disk AND remove the DB entry, tracking saved bytes."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    path = doc["file_path"]
    sender_name = doc.get("sender")
    filename = doc["filename"]

    # Calculate file size before deletion
    size_bytes = doc.get("file_size_bytes") or 0
    if size_bytes == 0 and path and os.path.exists(path):
        size_bytes = os.path.getsize(path)

    db.delete_document(doc_id)
    if path and os.path.exists(path):
        os.remove(path)

    # Log space saved if applicable
    if size_bytes > 0:
        from datetime import datetime
        with db.connection.get_conn() as conn:
            conn.execute(
                "INSERT INTO cleanup_history (action_type, filename, bytes_saved, executed_at) VALUES (?, ?, ?, ?)",
                ("deleted_duplicate", filename, size_bytes, datetime.now().isoformat(timespec="seconds"))
            )

    if sender_name:
        import db.sender_repo as _sr
        if _sr.cleanup_if_orphaned(sender_name):
            storage._refresh_cache()
