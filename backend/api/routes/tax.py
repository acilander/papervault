from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import db
import db.tax_years_repo as tax_years_repo
import db.tax_documents_repo as tax_documents_repo
import db.tax_positions_repo as tax_positions_repo
from api.models import DocumentListOut
from tax.extraction import extract_tax_positions
from tax.chat import answer_tax_question
from tax.prompts import TAX_CATEGORIES

router = APIRouter(prefix="/tax", tags=["tax"])


class TaxYearCreate(BaseModel):
    year: int
    status: str = "draft"
    notes: Optional[str] = None


class TaxYearUpdate(BaseModel):
    year: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class TaxDocumentCreate(BaseModel):
    document_id: int
    source_type: str


class TaxPositionCreate(BaseModel):
    tax_document_id: int
    category: str
    label: str
    amount: Optional[float] = None
    subcategory: Optional[str] = None
    amount_assessed: Optional[float] = None
    page: Optional[int] = None
    source_text: Optional[str] = None
    verified: bool = False


class TaxPositionUpdate(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    label: Optional[str] = None
    amount: Optional[float] = None
    amount_assessed: Optional[float] = None
    page: Optional[int] = None
    source_text: Optional[str] = None
    verified: Optional[bool] = None


@router.get("/categories")
def list_tax_categories():
    return TAX_CATEGORIES


@router.get("/years")
def list_tax_years():
    return tax_years_repo.get_all()


@router.post("/years")
def create_tax_year(body: TaxYearCreate):
    existing = tax_years_repo.get_by_year(body.year)
    if existing:
        raise HTTPException(status_code=409, detail=f"Steuerjahr {body.year} existiert bereits")
    tax_year_id = tax_years_repo.insert(year=body.year, status=body.status, notes=body.notes)
    return tax_years_repo.get(tax_year_id)


@router.get("/years/{tax_year_id}")
def get_tax_year(tax_year_id: int):
    year = tax_years_repo.get(tax_year_id)
    if not year:
        raise HTTPException(status_code=404, detail="Steuerjahr nicht gefunden")
    documents = tax_documents_repo.get_all_for_year(tax_year_id)
    positions = tax_positions_repo.get_all_for_year(tax_year_id)
    summary = tax_positions_repo.get_summary_by_year(tax_year_id)
    return {
        **year,
        "documents": documents,
        "positions": positions,
        "summary": summary,
    }


@router.patch("/years/{tax_year_id}")
def update_tax_year(tax_year_id: int, body: TaxYearUpdate):
    year = tax_years_repo.get(tax_year_id)
    if not year:
        raise HTTPException(status_code=404, detail="Steuerjahr nicht gefunden")
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return year
    tax_years_repo.update(tax_year_id, **fields)
    return tax_years_repo.get(tax_year_id)


@router.delete("/years/{tax_year_id}", status_code=204)
def delete_tax_year(tax_year_id: int):
    year = tax_years_repo.get(tax_year_id)
    if not year:
        raise HTTPException(status_code=404, detail="Steuerjahr nicht gefunden")
    tax_years_repo.delete(tax_year_id)
    return None


@router.get("/years/{tax_year_id}/documents")
def list_tax_documents(tax_year_id: int):
    year = tax_years_repo.get(tax_year_id)
    if not year:
        raise HTTPException(status_code=404, detail="Steuerjahr nicht gefunden")
    return tax_documents_repo.get_all_for_year(tax_year_id)


@router.post("/years/{tax_year_id}/documents")
def create_tax_document(tax_year_id: int, body: TaxDocumentCreate):
    year = tax_years_repo.get(tax_year_id)
    if not year:
        raise HTTPException(status_code=404, detail="Steuerjahr nicht gefunden")
    doc = db.get_document(body.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    existing = tax_documents_repo.get_by_year_and_document(tax_year_id, body.document_id, body.source_type)
    if existing:
        raise HTTPException(status_code=409, detail="Dokument ist bereits für diesen Typ verknüpft")
    tax_doc_id = tax_documents_repo.insert(
        tax_year_id=tax_year_id,
        document_id=body.document_id,
        source_type=body.source_type,
    )
    return tax_documents_repo.get(tax_doc_id)


@router.delete("/documents/{tax_document_id}", status_code=204)
def delete_tax_document(tax_document_id: int):
    tax_doc = tax_documents_repo.get(tax_document_id)
    if not tax_doc:
        raise HTTPException(status_code=404, detail="Steuerdokument nicht gefunden")
    tax_documents_repo.delete(tax_document_id)
    return None


@router.patch("/documents/{tax_document_id}")
def update_tax_document(tax_document_id: int, body: dict):
    tax_doc = tax_documents_repo.get(tax_document_id)
    if not tax_doc:
        raise HTTPException(status_code=404, detail="Steuerdokument nicht gefunden")
    allowed = {"source_type", "parsed_at", "verified"}
    filtered = {k: v for k, v in body.items() if k in allowed}
    if not filtered:
        return tax_doc
    tax_documents_repo.update(tax_document_id, **filtered)
    return tax_documents_repo.get(tax_document_id)


@router.get("/years/{tax_year_id}/positions")
def list_tax_positions(tax_year_id: int):
    year = tax_years_repo.get(tax_year_id)
    if not year:
        raise HTTPException(status_code=404, detail="Steuerjahr nicht gefunden")
    return tax_positions_repo.get_all_for_year(tax_year_id)


@router.post("/years/{tax_year_id}/positions")
def create_tax_position(tax_year_id: int, body: TaxPositionCreate):
    year = tax_years_repo.get(tax_year_id)
    if not year:
        raise HTTPException(status_code=404, detail="Steuerjahr nicht gefunden")
    tax_doc = tax_documents_repo.get(body.tax_document_id)
    if not tax_doc or tax_doc["tax_year_id"] != tax_year_id:
        raise HTTPException(status_code=404, detail="Steuerdokument nicht gefunden oder gehört zu anderem Jahr")
    position_id = tax_positions_repo.insert(
        tax_year_id=tax_year_id,
        tax_document_id=body.tax_document_id,
        category=body.category,
        label=body.label,
        amount=body.amount,
        subcategory=body.subcategory,
        amount_assessed=body.amount_assessed,
        page=body.page,
        source_text=body.source_text,
        verified=body.verified,
    )
    return tax_positions_repo.get(position_id)


@router.get("/positions/{position_id}")
def get_tax_position(position_id: int):
    pos = tax_positions_repo.get(position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")
    return pos


@router.patch("/positions/{position_id}")
def update_tax_position(position_id: int, body: TaxPositionUpdate):
    pos = tax_positions_repo.get(position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return pos
    tax_positions_repo.update(position_id, **fields)
    return tax_positions_repo.get(position_id)


@router.delete("/positions/{position_id}", status_code=204)
def delete_tax_position(position_id: int):
    pos = tax_positions_repo.get(position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")
    tax_positions_repo.delete(position_id)
    return None


@router.post("/documents/{tax_document_id}/extract")
def extract_tax_document_positions(tax_document_id: int):
    tax_doc = tax_documents_repo.get(tax_document_id)
    if not tax_doc:
        raise HTTPException(status_code=404, detail="Steuerdokument nicht gefunden")
    try:
        positions = extract_tax_positions(tax_document_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraktion fehlgeschlagen: {e}")
    return {"tax_document_id": tax_document_id, "positions": positions}


@router.get("/years/{tax_year_id}/summary")
def get_year_summary(tax_year_id: int):
    year = tax_years_repo.get(tax_year_id)
    if not year:
        raise HTTPException(status_code=404, detail="Steuerjahr nicht gefunden")
    return tax_positions_repo.get_summary_by_year(tax_year_id)


@router.get("/years/{tax_year_id}/comparison")
def compare_tax_year(tax_year_id: int):
    year = tax_years_repo.get(tax_year_id)
    if not year:
        raise HTTPException(status_code=404, detail="Steuerjahr nicht gefunden")
    positions = tax_positions_repo.get_all_for_year(tax_year_id)
    compared = []
    for pos in positions:
        amount = pos.get("amount") or 0
        assessed = pos.get("amount_assessed") or 0
        compared.append({
            **pos,
            "difference": round(assessed - amount, 2),
        })
    return {
        "tax_year": year,
        "positions": compared,
        "summary": tax_positions_repo.get_summary_by_year(tax_year_id),
    }


@router.get("/development")
def tax_development(
    category: Optional[str] = Query(None),
):
    return tax_positions_repo.get_development(category=category)


@router.get("/documents/available")
def list_available_documents(
    q: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
):
    """Return documents that can be linked to a tax year."""
    docs = db.search_documents(
        query=q,
        status="ok",
        sort_by="archived_at",
        sort_dir="desc",
        limit=limit,
        offset=0,
    )
    return docs


class TaxChatRequest(BaseModel):
    question: str


class TaxChatResponse(BaseModel):
    answer: str


@router.post("/chat")
def tax_chat(payload: TaxChatRequest) -> TaxChatResponse:
    answer = answer_tax_question(payload.question)
    return TaxChatResponse(answer=answer)
