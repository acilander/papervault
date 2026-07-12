from datetime import datetime, timezone

from db.connection import get_conn


TAX_YEAR_STATUSES = {"draft", "submitted", "assessed", "final"}


def init_tax_years_table():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tax_years (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                year        INTEGER NOT NULL UNIQUE,
                status      TEXT DEFAULT 'draft',
                notes       TEXT,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)


def _row_to_dict(row) -> dict:
    d = dict(row)
    return d


def get_all() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tax_years ORDER BY year DESC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get(tax_year_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tax_years WHERE id = ?", (tax_year_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_by_year(year: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tax_years WHERE year = ?", (year,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def insert(year: int, status: str = "draft", notes: str | None = None) -> int:
    if status not in TAX_YEAR_STATUSES:
        raise ValueError(f"Ungueltiger Status: {status}")
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tax_years (year, status, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (year, status, notes, now, now)
        )
        return cur.lastrowid


def update(tax_year_id: int, **fields):
    allowed = {"year", "status", "notes"}
    filtered = {k: v for k, v in fields.items() if k in allowed}
    if not filtered:
        return
    if "status" in filtered and filtered["status"] not in TAX_YEAR_STATUSES:
        raise ValueError(f"Ungueltiger Status: {filtered['status']}")
    now = datetime.now(timezone.utc).isoformat()
    filtered["updated_at"] = now
    set_clause = ", ".join(f"{k} = ?" for k in filtered)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE tax_years SET {set_clause} WHERE id = ?",
            list(filtered.values()) + [tax_year_id]
        )


def delete(tax_year_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM tax_years WHERE id = ?", (tax_year_id,))
