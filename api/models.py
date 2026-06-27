from typing import Optional
from pydantic import BaseModel


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


class SenderEntry(BaseModel):
    categories: list[str]
    pinned_category: Optional[str]
    reviewed: Optional[bool] = None
    excluded_categories: Optional[list[str]] = None


class SenderUpdate(BaseModel):
    pinned_category: Optional[str] = None
    categories: Optional[list[str]] = None
    reviewed: Optional[bool] = None
    excluded_categories: Optional[list[str]] = None


class StatsOut(BaseModel):
    total: int
    by_category: list[dict]
    by_year: list[dict]
    by_status: list[dict]
    recent: list[dict]
