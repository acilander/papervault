from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import db.identifiers_repo as repo

router = APIRouter(prefix="/identifiers", tags=["identifiers"])


class IdentifierCreate(BaseModel):
    sender_name: str
    identifier_type: str
    identifier_value: str
    label: Optional[str] = None
    target_category: Optional[str] = None
    target_unit: Optional[str] = None


class IdentifierAssign(BaseModel):
    sender_name: str
    label: Optional[str] = None
    target_category: Optional[str] = None
    target_unit: Optional[str] = None


@router.get("/")
def list_identifiers():
    """Lists all active confirmed identifiers."""
    return repo.get_all_identifiers()


@router.post("/")
def create_identifier(body: IdentifierCreate):
    """Manually registers a new verified identifier."""
    try:
        id_val = body.identifier_value.strip()
        # Verify sender exists
        import db.sender_repo as sender_repo
        if not sender_repo.exists(body.sender_name):
            # Proactively register the sender if it doesn't exist
            sender_repo.upsert(body.sender_name, {})
        
        inserted_id = repo.add_identifier(
            sender_name=body.sender_name,
            identifier_type=body.identifier_type,
            identifier_value=id_val,
            label=body.label,
            target_category=body.target_category,
            target_unit=body.target_unit
        )
        return {"ok": True, "id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Erstellen des Identifikators: {e}")


@router.put("/{id}")
def update_identifier(id: int, body: IdentifierCreate):
    try:
        import db.sender_repo as sender_repo
        sender_name = body.sender_name.strip()
        if not sender_repo.exists(sender_name):
            sender_repo.upsert(sender_name, {})
        success = repo.update_identifier(
            identifier_id=id,
            sender_name=sender_name,
            identifier_type=body.identifier_type,
            identifier_value=body.identifier_value.strip(),
            label=body.label,
            target_category=body.target_category,
            target_unit=body.target_unit
        )
        if not success:
            raise HTTPException(status_code=404, detail="Identifikator nicht gefunden.")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Aktualisieren des Identifikators: {e}")


@router.delete("/{id}")
def delete_identifier(id: int):
    """Deletes/removes a confirmed identifier."""
    success = repo.delete_identifier(id)
    if not success:
        raise HTTPException(status_code=404, detail="Identifikator nicht gefunden.")
    return {"ok": True}


@router.get("/unassigned")
def list_unassigned_identifiers():
    """Returns all currently unassigned identifiers awaiting verification."""
    return repo.get_unassigned_identifiers()


@router.post("/assign/{unassigned_id}")
def assign_unassigned(unassigned_id: int, body: IdentifierAssign):
    """Assigns/Promotes an unassigned identifier to a canonical sender."""
    try:
        import db.sender_repo as sender_repo
        if not sender_repo.exists(body.sender_name):
            sender_repo.upsert(body.sender_name, {})
            
        inserted_id = repo.assign_unassigned_identifier(
            unassigned_id=unassigned_id,
            sender_name=body.sender_name,
            label=body.label,
            target_category=body.target_category,
            target_unit=body.target_unit
        )
        return {"ok": True, "id": inserted_id}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Zuweisen: {e}")


@router.delete("/unassigned/{unassigned_id}")
def delete_unassigned(unassigned_id: int):
    """Deletes/Dismisses an unassigned identifier suggestion."""
    success = repo.delete_unassigned_identifier(unassigned_id)
    if not success:
        raise HTTPException(status_code=404, detail="Vorschlag nicht gefunden.")
    return {"ok": True}
