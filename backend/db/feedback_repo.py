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


def _clear_all_for_tests():
    init_feedback_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM feedback")
