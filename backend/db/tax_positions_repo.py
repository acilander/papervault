from datetime import datetime, timezone

from db.connection import get_conn


TAX_CATEGORIES = {
    "Einkünfte",
    "Werbungskosten",
    "Sonderausgaben",
    "Außergewöhnliche Belastungen",
    "Steuerliche Ergebnisse",
    "Vermietung und Verpachtung",
    "Selbstständige Einkünfte",
    "Sonstiges",
}


def init_tax_positions_table():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tax_positions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                tax_year_id         INTEGER NOT NULL,
                tax_document_id     INTEGER NOT NULL,
                category            TEXT NOT NULL,
                subcategory         TEXT,
                label               TEXT NOT NULL,
                amount              REAL,
                amount_assessed     REAL,
                page                INTEGER,
                verified            INTEGER DEFAULT 0,
                source_text         TEXT,
                created_at          TEXT NOT NULL,
                FOREIGN KEY (tax_year_id) REFERENCES tax_years(id) ON DELETE CASCADE,
                FOREIGN KEY (tax_document_id) REFERENCES tax_documents(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tax_positions_year ON tax_positions(tax_year_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tax_positions_document ON tax_positions(tax_document_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tax_positions_category ON tax_positions(category)")


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["verified"] = bool(d.get("verified"))
    return d


def get_all_for_year(tax_year_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT tp.*, d.filename, td.source_type
            FROM tax_positions tp
            JOIN tax_documents td ON td.id = tp.tax_document_id
            JOIN documents d ON d.id = td.document_id
            WHERE tp.tax_year_id = ?
            ORDER BY tp.category, tp.label
            """,
            (tax_year_id,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_all_for_document(tax_document_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tax_positions WHERE tax_document_id = ? ORDER BY category, label",
            (tax_document_id,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get(position_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tax_positions WHERE id = ?", (position_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def insert(
    tax_year_id: int,
    tax_document_id: int,
    category: str,
    label: str,
    amount: float | None = None,
    subcategory: str | None = None,
    amount_assessed: float | None = None,
    page: int | None = None,
    source_text: str | None = None,
    verified: bool = False,
) -> int:
    if category not in TAX_CATEGORIES:
        raise ValueError(f"Ungueltige Kategorie: {category}")
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO tax_positions
            (tax_year_id, tax_document_id, category, subcategory, label, amount, amount_assessed, page, verified, source_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (tax_year_id, tax_document_id, category, subcategory, label, amount, amount_assessed, page, 1 if verified else 0, source_text, now)
        )
        return cur.lastrowid


def update(position_id: int, **fields):
    allowed = {"category", "subcategory", "label", "amount", "amount_assessed", "page", "source_text", "verified"}
    filtered = {k: v for k, v in fields.items() if k in allowed}
    if not filtered:
        return
    if "category" in filtered and filtered["category"] not in TAX_CATEGORIES:
        raise ValueError(f"Ungueltige Kategorie: {filtered['category']}")
    if "verified" in filtered:
        filtered["verified"] = 1 if filtered["verified"] else 0
    set_clause = ", ".join(f"{k} = ?" for k in filtered)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE tax_positions SET {set_clause} WHERE id = ?",
            list(filtered.values()) + [position_id]
        )


def delete(position_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM tax_positions WHERE id = ?", (position_id,))


def delete_all_for_document(tax_document_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM tax_positions WHERE tax_document_id = ?", (tax_document_id,))


def get_summary_by_year(tax_year_id: int) -> list[dict]:
    """Return sum per category for a given year."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT category,
                   COALESCE(SUM(amount), 0) as total_amount,
                   COALESCE(SUM(amount_assessed), 0) as total_assessed,
                   COUNT(*) as position_count
            FROM tax_positions
            WHERE tax_year_id = ?
            GROUP BY category
            ORDER BY category
            """,
            (tax_year_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_development(category: str | None = None) -> list[dict]:
    """Return yearly sums, optionally filtered by category."""
    params: list = []
    where_sql = ""
    if category:
        where_sql = "WHERE category = ?"
        params.append(category)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT ty.year,
                   tp.category,
                   COALESCE(SUM(tp.amount), 0) as total_amount,
                   COALESCE(SUM(tp.amount_assessed), 0) as total_assessed,
                   COUNT(*) as position_count
            FROM tax_positions tp
            JOIN tax_years ty ON ty.id = tp.tax_year_id
            {where_sql}
            GROUP BY ty.year, tp.category
            ORDER BY ty.year DESC, tp.category
            """,
            params
        ).fetchall()
    return [dict(r) for r in rows]
