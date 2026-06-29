import os
import sys

from fastapi import APIRouter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import db
from config import CATEGORIES, DOCUMENT_TYPES
from api.models import StatsOut

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/", response_model=StatsOut)
def get_stats():
    return db.get_stats()


@router.get("/categories", response_model=list[str])
def get_categories():
    return CATEGORIES


@router.get("/document-types", response_model=list[str])
def get_document_types():
    return DOCUMENT_TYPES

