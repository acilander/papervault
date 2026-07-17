from db.connection import get_conn

MAX_EXAMPLES = 200


def init_feedback_table():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                ts               TEXT NOT NULL,
                sender           TEXT,
                document_type    TEXT,
                category         TEXT,
                summary          TEXT,
                corrected_fields TEXT NOT NULL DEFAULT ''
            )
        """)


def get_all() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM feedback ORDER BY ts DESC LIMIT ?", (MAX_EXAMPLES,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def insert(entry: dict):
    """Insert feedback, replacing any existing entry with same sender+category+document_type."""
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM feedback WHERE sender = ? AND category = ? AND document_type = ?",
            (entry.get("sender"), entry.get("category"), entry.get("document_type")),
        )
        conn.execute(
            "INSERT INTO feedback (ts, sender, document_type, category, summary, corrected_fields) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                entry.get("ts", ""),
                entry.get("sender"),
                entry.get("document_type"),
                entry.get("category"),
                entry.get("summary"),
                ",".join(entry.get("corrected_fields", [])),
            ),
        )
        _trim()


def _trim():
    """Keep only the MAX_EXAMPLES most recent rows."""
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM feedback WHERE id NOT IN "
            "(SELECT id FROM feedback ORDER BY ts DESC LIMIT ?)",
            (MAX_EXAMPLES,),
        )


def get_recent(n: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM feedback ORDER BY ts DESC LIMIT ?", (n * 3,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["corrected_fields"] = [f for f in d.get("corrected_fields", "").split(",") if f]
    return d


def import_from_list(examples: list[dict]):
    """Bulk import from old feedback.json list."""
    for entry in examples:
        insert(entry)


def delete(feedback_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM feedback WHERE id = ?", (feedback_id,))


def get_coverage_stats() -> dict:
    from config import CATEGORIES, DOCUMENT_TYPES
    with get_conn() as conn:
        rows_cat = conn.execute(
            "SELECT category, COUNT(*) as count FROM feedback WHERE category IS NOT NULL GROUP BY category"
        ).fetchall()
        rows_type = conn.execute(
            "SELECT document_type, COUNT(*) as count FROM feedback WHERE document_type IS NOT NULL GROUP BY document_type"
        ).fetchall()
        
    counts_cat = {r["category"]: r["count"] for r in rows_cat}
    counts_type = {r["document_type"]: r["count"] for r in rows_type}
    
    under_represented_categories = [c for c in CATEGORIES if counts_cat.get(c, 0) < 2]
    under_represented_types = [t for t in DOCUMENT_TYPES if counts_type.get(t, 0) < 1]
    
    return {
        "counts_by_category": counts_cat,
        "counts_by_document_type": counts_type,
        "under_represented_categories": under_represented_categories,
        "under_represented_document_types": under_represented_types,
    }


def _clear_all_for_tests():
    init_feedback_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM feedback")
