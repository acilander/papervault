from fastapi import APIRouter
from db.connection import get_conn

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


@router.get("/quality")
def get_quality():
    """Archive quality / completeness report for the dashboard."""
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE status NOT IN ('processing','failed','duplicate','encrypted','corrupt')"
        ).fetchone()[0]

        if total == 0:
            return {"total": 0, "score": 100, "fields": {}, "top_incomplete": [], "expiring_soon": 0}

        def _missing(col):
            return conn.execute(
                f"SELECT COUNT(*) FROM documents WHERE status NOT IN "
                f"('processing','failed','duplicate','encrypted','corrupt') "
                f"AND ({col} IS NULL OR TRIM({col})='')"
            ).fetchone()[0]

        missing_sender   = _missing("sender")
        missing_date     = _missing("date")
        missing_type     = _missing("document_type")
        missing_category = _missing("category")
        missing_summary  = _missing("summary")
        no_simhash       = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE status NOT IN "
            "('processing','failed','duplicate','encrypted','corrupt') AND sim_hash IS NULL"
        ).fetchone()[0]

        # weighted score: sender+date+type are critical (weight 3 each), others weight 1
        weights = {"sender": 3, "date": 3, "document_type": 3, "category": 1, "summary": 1}
        total_weight = sum(weights.values())
        penalty = (
            (missing_sender   / total) * weights["sender"] +
            (missing_date     / total) * weights["date"] +
            (missing_type     / total) * weights["document_type"] +
            (missing_category / total) * weights["category"] +
            (missing_summary  / total) * weights["summary"]
        ) / total_weight
        score = round((1 - penalty) * 100, 1)

        # Top-10 incomplete docs (most missing fields)
        rows = conn.execute(
            "SELECT id, filename, sender, date, document_type, category, summary "
            "FROM documents WHERE status NOT IN "
            "('processing','failed','duplicate','encrypted','corrupt') "
            "AND (sender IS NULL OR date IS NULL OR document_type IS NULL OR TRIM(COALESCE(sender,''))=''"
            " OR TRIM(COALESCE(date,''))='' OR TRIM(COALESCE(document_type,''))='') "
            "LIMIT 10"
        ).fetchall()
        top_incomplete = []
        for r in rows:
            missing = [f for f in ("sender","date","document_type","category","summary")
                       if not r[f] or str(r[f]).strip() == ""]
            top_incomplete.append({"id": r["id"], "filename": r["filename"], "missing_fields": missing})

        # Expiring within 60 days
        expiring = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE expires_at IS NOT NULL "
            "AND date(expires_at) <= date('now','+60 days') AND date(expires_at) >= date('now')"
        ).fetchone()[0]

    return {
        "total": total,
        "score": score,
        "fields": {
            "sender":        {"missing": missing_sender,   "pct": round(missing_sender/total*100,1)},
            "date":          {"missing": missing_date,     "pct": round(missing_date/total*100,1)},
            "document_type": {"missing": missing_type,     "pct": round(missing_type/total*100,1)},
            "category":      {"missing": missing_category, "pct": round(missing_category/total*100,1)},
            "summary":       {"missing": missing_summary,  "pct": round(missing_summary/total*100,1)},
            "sim_hash":      {"missing": no_simhash,       "pct": round(no_simhash/total*100,1)},
        },
        "top_incomplete": top_incomplete,
        "expiring_soon": expiring,
    }

