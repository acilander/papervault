from datetime import datetime, timezone

from db.connection import get_conn


SOURCE_TYPES = {"tax_program_export", "assessment_notice"}


def init_tax_documents_table():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tax_documents (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tax_year_id     INTEGER NOT NULL,
                document_id     INTEGER NOT NULL,
                source_type     TEXT NOT NULL,
                parsed_at       TEXT,
                verified        INTEGER DEFAULT 0,
                FOREIGN KEY (tax_year_id) REFERENCES tax_years(id) ON DELETE CASCADE,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                UNIQUE(tax_year_id, document_id, source_type)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tax_documents_year ON tax_documents(tax_year_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tax_documents_document ON tax_documents(document_id)")


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["verified"] = bool(d.get("verified"))
    return d


def get_all_for_year(tax_year_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT td.*, d.filename, d.sender, d.document_type, d.category, d.date, d.archived_at
            FROM tax_documents td
            JOIN documents d ON d.id = td.document_id
            WHERE td.tax_year_id = ?
            ORDER BY td.source_type, d.archived_at DESC
            """,
            (tax_year_id,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get(tax_document_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tax_documents WHERE id = ?", (tax_document_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_by_year_and_document(tax_year_id: int, document_id: int, source_type: str) -> dict | None:
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"Ungueltiger source_type: {source_type}")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tax_documents WHERE tax_year_id = ? AND document_id = ? AND source_type = ?",
            (tax_year_id, document_id, source_type)
        ).fetchone()
    return _row_to_dict(row) if row else None


def insert(tax_year_id: int, document_id: int, source_type: str, parsed_at: str | None = None, verified: bool = False) -> int:
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"Ungueltiger source_type: {source_type}")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tax_documents (tax_year_id, document_id, source_type, parsed_at, verified) VALUES (?, ?, ?, ?, ?)",
            (tax_year_id, document_id, source_type, parsed_at, 1 if verified else 0)
        )
        return cur.lastrowid


def update(tax_document_id: int, **fields):
    allowed = {"source_type", "parsed_at", "verified"}
    filtered = {k: v for k, v in fields.items() if k in allowed}
    if not filtered:
        return
    if "source_type" in filtered and filtered["source_type"] not in SOURCE_TYPES:
        raise ValueError(f"Ungueltiger source_type: {filtered['source_type']}")
    if "verified" in filtered:
        filtered["verified"] = 1 if filtered["verified"] else 0
    set_clause = ", ".join(f"{k} = ?" for k in filtered)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE tax_documents SET {set_clause} WHERE id = ?",
            list(filtered.values()) + [tax_document_id]
        )


def delete(tax_document_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM tax_documents WHERE id = ?", (tax_document_id,))


def set_parsed_now(tax_document_id: int, verified: bool = False):
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE tax_documents SET parsed_at = ?, verified = ? WHERE id = ?",
            (now, 1 if verified else 0, tax_document_id)
        )
