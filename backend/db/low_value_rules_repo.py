from datetime import datetime, timezone
from db.connection import get_conn


def init_low_value_rules_table():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS low_value_rules (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                category        TEXT,
                document_type   TEXT,
                max_amount      REAL,
                older_than_days INTEGER,
                active          INTEGER DEFAULT 1,
                created_at      TEXT NOT NULL
            )
        """)


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["active"] = bool(d.get("active"))
    return d


def get_all() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM low_value_rules ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_active() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM low_value_rules WHERE active = 1 ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get(rule_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM low_value_rules WHERE id = ?", (rule_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def insert(name: str, category: str | None, document_type: str | None,
           max_amount: float | None, older_than_days: int | None, active: bool = True) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO low_value_rules (name, category, document_type, max_amount, older_than_days, active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, category, document_type, max_amount, older_than_days, 1 if active else 0, now)
        )
        return cur.lastrowid


def update(rule_id: int, **fields):
    allowed = {"name", "category", "document_type", "max_amount", "older_than_days", "active"}
    filtered = {k: v for k, v in fields.items() if k in allowed}
    if not filtered:
        return
    if "active" in filtered:
        filtered["active"] = 1 if filtered["active"] else 0
    set_clause = ", ".join(f"{k} = ?" for k in filtered)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE low_value_rules SET {set_clause} WHERE id = ?",
            list(filtered.values()) + [rule_id]
        )


def delete(rule_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM low_value_rules WHERE id = ?", (rule_id,))


def find_matching_docs(rule: dict, limit: int = 1000) -> list[dict]:
    """Return documents matching the rule that are not yet marked low_value."""
    conditions = ["low_value = 0", "status IN ('ok', 'review')"]
    params: list = []
    if rule.get("category"):
        conditions.append("category = ?")
        params.append(rule["category"])
    if rule.get("document_type"):
        conditions.append("document_type = ?")
        params.append(rule["document_type"])
    max_amount_sql = ""
    if rule.get("max_amount") is not None:
        max_amount = float(rule["max_amount"])
        max_amount_sql = (
            f"AND EXISTS ("
            f"SELECT 1 FROM ("
            f"  SELECT total_price AS amount FROM items WHERE document_id = d.id AND total_price IS NOT NULL"
            f"  UNION ALL"
            f"  SELECT amount FROM services WHERE document_id = d.id AND amount IS NOT NULL"
            f"  UNION ALL"
            f"  SELECT amount FROM contracts WHERE document_id = d.id AND amount IS NOT NULL"
            f") WHERE amount <= {max_amount}"
        )
    if rule.get("older_than_days") is not None:
        days = int(rule["older_than_days"])
        conditions.append(f"archived_at < datetime('now', '-{days} days')")

    where_sql = "WHERE " + " AND ".join(conditions)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id, filename, sender, document_type, category, date, archived_at FROM documents d {where_sql} {max_amount_sql} ORDER BY archived_at DESC LIMIT ?",
            params + [limit]
        ).fetchall()
    return [dict(r) for r in rows]


def apply_rule(rule_id: int) -> dict:
    rule = get(rule_id)
    if not rule:
        raise ValueError("Regel nicht gefunden")
    matches = find_matching_docs(rule, limit=10000)
    ids = [d["id"] for d in matches]
    if ids:
        placeholders = ",".join("?" * len(ids))
        with get_conn() as conn:
            conn.execute(
                f"UPDATE documents SET low_value = 1 WHERE id IN ({placeholders})",
                ids
            )
    return {"matched": len(ids), "updated": len(ids)}
