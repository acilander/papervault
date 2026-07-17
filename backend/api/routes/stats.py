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


@router.get("/config")
def get_config():
    from config_manager import get_settings
    import config
    settings = get_settings()
    settings["paths"] = {
        "source_dir": config.SOURCE_DIR,
        "target_base": config.TARGET_BASE
    }
    return settings


@router.get("/cleanup")
def get_cleanup_stats():
    """Returns the total bytes saved from deleting duplicates."""
    with get_conn() as conn:
        row = conn.execute("SELECT SUM(bytes_saved) FROM cleanup_history").fetchone()
        return {"total_bytes_saved": row[0] or 0}
@router.get("/quality")
def get_quality():
    """Archive quality / completeness report for the dashboard."""
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE status NOT IN ('processing','failed','duplicate','encrypted','corrupt')"
        ).fetchone()[0]

        if total == 0:
            return {"total": 0, "score": 100, "fields": {}, "top_incomplete": [], "expiring_soon": 0}

        row = conn.execute("""
            SELECT
                SUM(CASE WHEN sender IS NULL OR TRIM(sender)='' THEN 1 ELSE 0 END) AS missing_sender,
                SUM(CASE WHEN date IS NULL OR TRIM(date)='' THEN 1 ELSE 0 END) AS missing_date,
                SUM(CASE WHEN document_type IS NULL OR TRIM(document_type)='' THEN 1 ELSE 0 END) AS missing_type,
                SUM(CASE WHEN category IS NULL OR TRIM(category)='' THEN 1 ELSE 0 END) AS missing_category,
                SUM(CASE WHEN summary IS NULL OR TRIM(summary)='' THEN 1 ELSE 0 END) AS missing_summary,
                SUM(CASE WHEN sim_hash IS NULL THEN 1 ELSE 0 END) AS no_simhash
            FROM documents
            WHERE status NOT IN ('processing','failed','duplicate','encrypted','corrupt')
        """).fetchone()
        missing_sender   = row["missing_sender"]   or 0
        missing_date     = row["missing_date"]     or 0
        missing_type     = row["missing_type"]     or 0
        missing_category = row["missing_category"] or 0
        missing_summary  = row["missing_summary"]  or 0
        no_simhash       = row["no_simhash"]       or 0

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

