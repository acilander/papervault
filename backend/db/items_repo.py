"""
ItemsRepository – SQLite-backed storage for inventory items extracted from invoices.
"""
import csv
import io
from db.connection import get_conn

ITEMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    quantity        REAL DEFAULT 1,
    unit_price      REAL,
    total_price     REAL,
    currency        TEXT DEFAULT 'EUR',
    purchase_date   TEXT,
    vendor          TEXT,
    category        TEXT,
    warranty_until  TEXT,
    extracted_at    TEXT,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_document_id ON items(document_id);
CREATE INDEX IF NOT EXISTS idx_items_purchase_date ON items(purchase_date);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
"""


def init_items_table():
    with get_conn() as conn:
        conn.executescript(ITEMS_SCHEMA)


def _row_to_dict(row) -> dict:
    return {
        "id":            row["id"],
        "document_id":   row["document_id"],
        "name":          row["name"],
        "description":   row["description"],
        "quantity":      row["quantity"],
        "unit_price":    row["unit_price"],
        "total_price":   row["total_price"],
        "currency":      row["currency"],
        "purchase_date": row["purchase_date"],
        "vendor":        row["vendor"],
        "category":      row["category"],
        "warranty_until": row["warranty_until"],
        "extracted_at":  row["extracted_at"],
        "notes":         row["notes"],
    }


def update_vendor_for_document(document_id: int, vendor: str) -> int:
    """Update vendor on all items for a document. Returns number of updated rows."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE items SET vendor = ? WHERE document_id = ?", (vendor, document_id)
        )
        return cur.rowcount


def has_items_for_document(document_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM items WHERE document_id = ? LIMIT 1", (document_id,)
        ).fetchone()
    return row is not None


def insert_items(document_id: int, items: list[dict], extracted_at: str) -> int:
    """Insert items for a document. Returns number of inserted rows."""
    if not items:
        return 0
    with get_conn() as conn:
        count = 0
        for item in items:
            conn.execute(
                """INSERT INTO items
                   (document_id, name, description, quantity, unit_price, total_price,
                    currency, purchase_date, vendor, category, warranty_until, extracted_at, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    document_id,
                    item.get("name", ""),
                    item.get("description"),
                    item.get("quantity", 1),
                    item.get("unit_price"),
                    item.get("total_price"),
                    item.get("currency", "EUR"),
                    item.get("purchase_date"),
                    item.get("vendor"),
                    item.get("category"),
                    item.get("warranty_until"),
                    extracted_at,
                    item.get("notes"),
                ),
            )
            count += 1
    return count


_VALID_ITEM_SORT_COLS = {"name", "vendor", "category", "purchase_date", "quantity", "unit_price", "total_price", "warranty_until"}


def get_items(
    q: str | None = None,
    category: str | None = None,
    vendor: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_price: float | None = None,
    sort_by: str | None = "purchase_date",
    sort_dir: str | None = "desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return (items, total_count) with optional filters."""
    where = []
    params: list = []

    if q:
        where.append("(name LIKE ? OR description LIKE ? OR vendor LIKE ?)")
        like = f"%{q}%"
        params += [like, like, like]
    if category:
        where.append("category = ?")
        params.append(category)
    if vendor:
        where.append("vendor LIKE ?")
        params.append(f"%{vendor}%")
    if date_from:
        where.append("purchase_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("purchase_date <= ?")
        params.append(date_to)
    if min_price is not None:
        where.append("total_price >= ?")
        params.append(min_price)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    order_col = sort_by if sort_by in _VALID_ITEM_SORT_COLS else "purchase_date"
    direction = "ASC" if str(sort_dir).upper() == "ASC" else "DESC"

    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM items {where_sql}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM items {where_sql} ORDER BY {order_col} {direction} NULLS LAST, id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    return [_row_to_dict(r) for r in rows], total


def get_stats() -> dict:
    with get_conn() as conn:
        total_items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        total_value = conn.execute(
            "SELECT COALESCE(SUM(total_price), 0) FROM items WHERE total_price IS NOT NULL"
        ).fetchone()[0]
        by_category = conn.execute(
            """SELECT category, COUNT(*) as count, COALESCE(SUM(total_price), 0) as value
               FROM items GROUP BY category ORDER BY value DESC"""
        ).fetchall()
        docs_processed = conn.execute(
            "SELECT COUNT(DISTINCT document_id) FROM items WHERE document_id IS NOT NULL"
        ).fetchone()[0]
    return {
        "total_items": total_items,
        "total_value": round(total_value, 2),
        "docs_processed": docs_processed,
        "by_category": [
            {"category": r["category"] or "–", "count": r["count"], "value": round(r["value"], 2)}
            for r in by_category
        ],
    }


def get_all_for_export() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT i.*, d.filename as source_filename FROM items i "
            "LEFT JOIN documents d ON d.id = i.document_id "
            "ORDER BY i.purchase_date DESC, i.id DESC"
        ).fetchall()
    result = []
    for r in rows:
        d = _row_to_dict(r)
        d["source_filename"] = r["source_filename"]
        result.append(d)
    return result


def to_csv(items: list[dict]) -> str:
    if not items:
        return ""
    output = io.StringIO()
    fields = ["id", "name", "description", "quantity", "unit_price", "total_price",
              "currency", "purchase_date", "vendor", "category", "warranty_until",
              "notes", "source_filename"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(items)
    return output.getvalue()


def get_unprocessed_invoice_ids() -> list[int]:
    """Return IDs of documents with document_type 'Rechnung' or 'Warenrechnung' that have no items yet."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT d.id FROM documents d
               WHERE d.document_type IN ('Rechnung', 'Warenrechnung')
               AND d.status = 'ok'
               AND NOT EXISTS (SELECT 1 FROM items i WHERE i.document_id = d.id)
               ORDER BY d.archived_at DESC"""
        ).fetchall()
    return [r["id"] for r in rows]
