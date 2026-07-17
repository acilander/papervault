from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from db import low_value_rules_repo as repo

router = APIRouter(prefix="/low-value-rules", tags=["low_value_rules"])


class RuleCreate(BaseModel):
    name: str
    category: Optional[str] = None
    document_type: Optional[str] = None
    max_amount: Optional[float] = None
    older_than_days: Optional[int] = None
    active: bool = True


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    document_type: Optional[str] = None
    max_amount: Optional[float] = None
    older_than_days: Optional[int] = None
    active: Optional[bool] = None


@router.get("/")
def list_rules():
    return repo.get_all()


@router.post("/")
def create_rule(body: RuleCreate):
    rule_id = repo.insert(
        name=body.name,
        category=body.category,
        document_type=body.document_type,
        max_amount=body.max_amount,
        older_than_days=body.older_than_days,
        active=body.active,
    )
    rule = repo.get(rule_id)
    return rule


@router.get("/{rule_id}")
def get_rule(rule_id: int):
    rule = repo.get(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Regel nicht gefunden")
    return rule


@router.patch("/{rule_id}")
def update_rule(rule_id: int, body: RuleUpdate):
    existing = repo.get(rule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Regel nicht gefunden")
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return existing
    repo.update(rule_id, **fields)
    return repo.get(rule_id)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int):
    existing = repo.get(rule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Regel nicht gefunden")
    repo.delete(rule_id)
    return None


@router.post("/{rule_id}/preview")
def preview_rule(rule_id: int):
    rule = repo.get(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Regel nicht gefunden")
    matches = repo.find_matching_docs(rule, limit=200)
    return {"rule": rule, "matches": matches}


@router.post("/{rule_id}/apply")
def apply_rule(rule_id: int):
    rule = repo.get(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Regel nicht gefunden")
    result = repo.apply_rule(rule_id)
    return {"rule": rule, "matched": result["matched"], "updated": result["updated"]}

@router.post("/{rule_id}/rollback")
def rollback_rule(rule_id: int):
    """Undo the effects of a low value rule."""
    rule = repo.get(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Regel nicht gefunden")
    restored = repo.rollback_rule(rule_id)
    return {"rule": rule, "restored": restored}
