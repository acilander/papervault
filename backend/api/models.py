from typing import Optional
from pydantic import BaseModel


class DocumentListOut(BaseModel):
    """Lightweight model for list endpoints — excludes full_text, keywords, sim_hash."""
    id: int
    file_path: str
    filename: str
    sender: Optional[str]
    date: Optional[str]
    document_type: Optional[str]
    category: Optional[str]
    summary: Optional[str]
    content_hash: Optional[str]
    status: str
    archived_at: str
    tags: Optional[str] = ""
    tax_relevant: Optional[int] = 0
    tax_year: Optional[str] = None
    expires_at: Optional[str] = None
    notes: Optional[str] = None
    low_value: Optional[int] = 0
    confidence: Optional[str] = None
    verified: Optional[int] = 0


class DocumentOut(BaseModel):
    id: int
    file_path: str
    filename: str
    sender: Optional[str]
    date: Optional[str]
    document_type: Optional[str]
    category: Optional[str]
    summary: Optional[str]
    content_hash: Optional[str]
    status: str
    archived_at: str
    tags: Optional[str] = ""
    tax_relevant: Optional[int] = 0
    tax_year: Optional[str] = None
    expires_at: Optional[str] = None
    notes: Optional[str] = None
    low_value: Optional[int] = 0
    confidence: Optional[str] = None
    verified: Optional[int] = 0


class DocumentUpdate(BaseModel):
    sender: Optional[str] = None
    date: Optional[str] = None
    document_type: Optional[str] = None
    category: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[str] = None
    tax_relevant: Optional[int] = None
    tax_year: Optional[str] = None
    expires_at: Optional[str] = None
    notes: Optional[str] = None
    low_value: Optional[int] = None
    verified: Optional[int] = None


class SenderEntry(BaseModel):
    categories: list[str]
    pinned_category: Optional[str]
    pinned_document_type: Optional[str] = None
    reviewed: Optional[bool] = None
    excluded_categories: Optional[list[str]] = None
    aliases: Optional[list[str]] = None


class SenderUpdate(BaseModel):
    pinned_category: Optional[str] = None
    pinned_document_type: Optional[str] = None
    categories: Optional[list[str]] = None
    reviewed: Optional[bool] = None
    excluded_categories: Optional[list[str]] = None


class StatsOut(BaseModel):
    total: int
    by_category: list[dict]
    by_year: list[dict]
    by_status: list[dict]
    recent: list[dict]
    no_sender: int = 0
    low_value: int = 0
    verified_count: int = 0
    locked_count: int = 0
    confidence_high: int = 0
    confidence_medium: int = 0
    confidence_low: int = 0
    monthly_fix_costs: float = 0.0


class TransactionCreate(BaseModel):
    title: str
    status: Optional[str] = "open"
    type: Optional[str] = "discrete"


class TransactionUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    type: Optional[str] = None


class TransactionDocAdd(BaseModel):
    document_id: int
    role: str


class TransactionDocumentOut(DocumentListOut):
    role: str
    linked_at: str


class TransactionOut(BaseModel):
    id: int
    title: str
    status: str
    type: str
    created_at: str
    updated_at: str
    document_count: int


class TransactionDetailOut(BaseModel):
    id: int
    title: str
    status: str
    type: str
    created_at: str
    updated_at: str
    documents: list[TransactionDocumentOut]
