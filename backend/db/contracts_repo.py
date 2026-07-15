"""
ContractsRepository – SQLite-backed storage for contracts and subscriptions
extracted from documents.
"""
import csv
import io
from db.connection import get_conn

CONTRACTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS contracts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id         INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    partner             TEXT NOT NULL,
    description         TEXT,
    category            TEXT,
    status              TEXT DEFAULT 'aktiv',
    amount              REAL,
    amount_interval     TEXT,
    start_date          TEXT,
    end_date            TEXT,
    next_due_date       TEXT,
    cancellation_deadline TEXT,
    notice_period_days  INTEGER,
    auto_renews         INTEGER DEFAULT 0,
    extracted_at        TEXT,
    notes               TEXT,
    source_text         TEXT,
    source_page         INTEGER
);
CREATE INDEX IF NOT EXISTS idx_contracts_document_id ON contracts(document_id);
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
CREATE INDEX IF NOT EXISTS idx_contracts_end_date ON contracts(end_date);
CREATE INDEX IF NOT EXISTS idx_contracts_partner ON contracts(partner);
"""


def init_contracts_table():
    with get_conn() as conn:
        conn.executescript(CONTRACTS_SCHEMA)


def _row_to_dict(row) -> dict:
    return {
        "id":                   row["id"],
        "document_id":          row["document_id"],
        "partner":              row["partner"],
        "description":          row["description"],
        "category":             row["category"],
        "status":               row["status"],
        "amount":               row["amount"],
        "amount_interval":      row["amount_interval"],
        "start_date":           row["start_date"],
        "end_date":             row["end_date"],
        "next_due_date":        row["next_due_date"],
        "cancellation_deadline": row["cancellation_deadline"],
        "notice_period_days":   row["notice_period_days"],
        "auto_renews":          bool(row["auto_renews"]),
        "extracted_at":         row["extracted_at"],
        "notes":                row["notes"],
        "source_text":          row["source_text"] if "source_text" in row.keys() else None,
        "source_page":          row["source_page"] if "source_page" in row.keys() else None,
    }


def has_contract_for_document(document_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM contracts WHERE document_id = ? LIMIT 1", (document_id,)
        ).fetchone()
    return row is not None


def insert_contract(document_id: int, contract: dict, extracted_at: str) -> int:
    """Insert a single contract. Returns new row id."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO contracts
               (document_id, partner, description, category, status, amount, amount_interval,
                start_date, end_date, next_due_date, cancellation_deadline,
                notice_period_days, auto_renews, extracted_at, notes, source_text, source_page)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                document_id,
                contract.get("partner", ""),
                contract.get("description"),
                contract.get("category"),
                contract.get("status", "aktiv"),
                contract.get("amount"),
                contract.get("amount_interval"),
                contract.get("start_date"),
                contract.get("end_date"),
                contract.get("next_due_date"),
                contract.get("cancellation_deadline"),
                contract.get("notice_period_days"),
                int(bool(contract.get("auto_renews", False))),
                extracted_at,
                contract.get("notes"),
                contract.get("source_text"),
                contract.get("source_page"),
            ),
        )
        return cur.lastrowid


def update_partner_for_document(document_id: int, partner: str) -> int:
    """Update partner on all contracts for a document. Returns number of updated rows."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE contracts SET partner = ? WHERE document_id = ?", (partner, document_id)
        )
        return cur.rowcount


def update_contract(contract_id: int, **fields):
    allowed = {"partner", "description", "category", "status", "amount", "amount_interval",
               "start_date", "end_date", "next_due_date", "cancellation_deadline",
               "notice_period_days", "auto_renews", "notes"}
    filtered = {k: v for k, v in fields.items() if k in allowed}
    if not filtered:
        return
    set_clause = ", ".join(f"{k} = ?" for k in filtered)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE contracts SET {set_clause} WHERE id = ?",
            list(filtered.values()) + [contract_id],
        )


def delete_contract(contract_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM contracts WHERE id = ?", (contract_id,))


_VALID_CONTRACT_SORT_COLS = {"partner", "category", "status", "amount", "start_date", "end_date", "next_due_date", "cancellation_deadline"}


def get_contracts(
    q: str | None = None,
    category: str | None = None,
    status: str | None = None,
    partner: str | None = None,
    expiring_within_days: int | None = None,
    sort_by: str | None = "end_date",
    sort_dir: str | None = "asc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    where = []
    params: list = []

    if q:
        where.append("(partner LIKE ? OR description LIKE ?)")
        like = f"%{q}%"
        params += [like, like]
    if category:
        where.append("category = ?")
        params.append(category)
    if status:
        where.append("status = ?")
        params.append(status)
    if partner:
        where.append("partner LIKE ?")
        params.append(f"%{partner}%")
    if expiring_within_days is not None:
        where.append(
            "end_date IS NOT NULL AND end_date != '' "
            "AND date(end_date) <= date('now', ?) "
            "AND date(end_date) >= date('now')"
        )
        params.append(f"+{expiring_within_days} days")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    order_col = sort_by if sort_by in _VALID_CONTRACT_SORT_COLS else "end_date"
    direction = "ASC" if str(sort_dir).upper() == "ASC" else "DESC"

    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM contracts {where_sql}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM contracts {where_sql} ORDER BY {order_col} {direction} NULLS LAST, id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    return [_row_to_dict(r) for r in rows], total


def get_stats() -> dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM contracts").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM contracts WHERE status = 'aktiv'").fetchone()[0]
        monthly_cost = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM contracts WHERE status = 'aktiv' AND amount_interval = 'monatlich'"
        ).fetchone()[0]
        yearly_equiv = conn.execute(
            """SELECT COALESCE(SUM(CASE
               WHEN amount_interval = 'monatlich' THEN amount * 12
               WHEN amount_interval = 'jährlich' THEN amount
               WHEN amount_interval = 'vierteljährlich' THEN amount * 4
               WHEN amount_interval = 'halbjährlich' THEN amount * 2
               ELSE 0 END), 0)
               FROM contracts WHERE status = 'aktiv' AND amount IS NOT NULL"""
        ).fetchone()[0]
        by_category = conn.execute(
            """SELECT category, COUNT(*) as count, COALESCE(SUM(amount), 0) as amount
               FROM contracts WHERE status = 'aktiv' GROUP BY category ORDER BY amount DESC"""
        ).fetchall()
        expiring_soon = conn.execute(
            """SELECT COUNT(*) FROM contracts
               WHERE status = 'aktiv' AND end_date IS NOT NULL AND end_date != ''
               AND date(end_date) <= date('now', '+60 days') AND date(end_date) >= date('now')"""
        ).fetchone()[0]
    return {
        "total": total,
        "active": active,
        "monthly_cost": round(monthly_cost, 2),
        "yearly_equivalent": round(yearly_equiv, 2),
        "expiring_soon": expiring_soon,
        "by_category": [
            {"category": r["category"] or "–", "count": r["count"], "amount": round(r["amount"], 2)}
            for r in by_category
        ],
    }


def get_all_for_export() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.*, d.filename as source_filename FROM contracts c "
            "LEFT JOIN documents d ON d.id = c.document_id "
            "ORDER BY c.end_date ASC NULLS LAST"
        ).fetchall()
    result = []
    for r in rows:
        d = _row_to_dict(r)
        d["source_filename"] = r["source_filename"]
        result.append(d)
    return result


def to_csv(contracts: list[dict]) -> str:
    if not contracts:
        return ""
    output = io.StringIO()
    fields = ["id", "partner", "description", "category", "status", "amount",
              "amount_interval", "start_date", "end_date", "next_due_date",
              "cancellation_deadline", "notice_period_days", "auto_renews",
              "notes", "source_filename"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(contracts)
    return output.getvalue()


def get_unprocessed_contract_doc_ids() -> list[int]:
    """Return IDs of contract/subscription documents with no extracted contract yet."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT d.id FROM documents d
               WHERE d.document_type IN ('Vertrag', 'Kündigung', 'Mahnung', 'Abonnement')
               AND d.status = 'ok'
               AND NOT EXISTS (SELECT 1 FROM contracts c WHERE c.document_id = d.id)
               ORDER BY d.archived_at DESC"""
        ).fetchall()
    return [r["id"] for r in rows]
