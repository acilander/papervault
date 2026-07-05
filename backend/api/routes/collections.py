import io
import os
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from db.collections_repo import (
    get_all_collections, get_collection, create_collection,
    update_collection, delete_collection,
    add_document, remove_document, get_collections_for_document,
)

router = APIRouter(prefix="/collections", tags=["collections"])


class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    color: Optional[str] = "#6366f1"


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


@router.get("/")
def list_collections():
    return get_all_collections()


@router.post("/", status_code=201)
def create(body: CollectionCreate):
    cid = create_collection(body.name, body.description or "", body.color or "#6366f1")
    return get_collection(cid)


@router.get("/{collection_id}")
def get(collection_id: int):
    col = get_collection(collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")
    return col


@router.patch("/{collection_id}")
def update(collection_id: int, body: CollectionUpdate):
    col = get_collection(collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")
    update_collection(collection_id, **body.model_dump(exclude_none=True))
    return get_collection(collection_id)


@router.delete("/{collection_id}", status_code=204)
def delete(collection_id: int):
    col = get_collection(collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")
    delete_collection(collection_id)


@router.post("/{collection_id}/documents/{document_id}", status_code=200)
def add_doc(collection_id: int, document_id: int):
    col = get_collection(collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")
    add_document(collection_id, document_id)
    return {"detail": "Dokument hinzugefügt"}


@router.delete("/{collection_id}/documents/{document_id}", status_code=204)
def remove_doc(collection_id: int, document_id: int):
    remove_document(collection_id, document_id)


@router.get("/by-document/{document_id}")
def collections_for_doc(document_id: int):
    return get_collections_for_document(document_id)


@router.get("/{collection_id}/export/zip")
def export_zip(collection_id: int):
    """Download all PDFs in a collection as a ZIP archive."""
    col = get_collection(collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")
    docs = col.get("documents", [])
    if not docs:
        raise HTTPException(status_code=404, detail="Sammlung enthält keine Dokumente")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        seen_names: dict[str, int] = {}
        found_any = False
        for doc in docs:
            path = doc.get("file_path", "")
            if not path or not os.path.exists(path):
                continue
            found_any = True
            name = doc.get("filename") or os.path.basename(path)
            if name in seen_names:
                seen_names[name] += 1
                base, ext = os.path.splitext(name)
                name = f"{base}_{seen_names[name]}{ext}"
            else:
                seen_names[name] = 0
            zf.write(path, arcname=name)

    if not found_any:
        raise HTTPException(status_code=404, detail="Keine Dateien in der Sammlung gefunden")

    buf.seek(0)
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in col["name"]).strip()
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=\"{safe_name}.zip\""},
    )
