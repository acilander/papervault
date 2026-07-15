"""
ServicesRepository – SQLite storage for services/expenses extracted from invoices.
Covers non-physical invoices: handcraft, travel, medical, insurance, etc.
"""
import csv
import io
from db.connection import get_conn

SERVICES_SCHEMA = """
CREATE TABLE IF NOT EXISTS services (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    provider        TEXT,
    service_date    TEXT,
    amount          REAL,
    currency        TEXT DEFAULT 'EUR',
    category        TEXT,
    extracted_at    TEXT,
    notes           TEXT,
    source_text     TEXT,
    source_page     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_services_document_id ON services(document_id);
CREATE INDEX IF NOT EXISTS idx_services_service_date ON services(service_date);
CREATE INDEX IF NOT EXISTS idx_services_category ON services(category);
"""

SERVICE_CATEGORIES = [
    "Handwerk & Reparatur",
    "Reise & Urlaub",
    "Arzt & Gesundheit",
    "Versicherung",
    "Telekommunikation",
    "Energie & Wasser",
    "Steuer & Behörden",
    "Bildung & Weiterbildung",
    "Reinigung & Pflege",
    "Transport & Mobilität",
    "Gastronomie & Catering",
    "Beratung & Dienstleistung",
    "Sonstiges",
]


def init_services_table():
    with get_conn() as conn:
        conn.executescript(SERVICES_SCHEMA)


_VALID_SERVICE_SORT_COLS = {"name", "provider", "category", "service_date", "amount"}


def get_services(
    q=None, category=None, provider=None,
    date_from=None, date_to=None,
    min_amount=None, sort_by="service_date", sort_dir="desc",
    limit=50, offset=0
):
    conditions = []
    params = []
    if q:
        conditions.append("(s.name LIKE ? OR s.description LIKE ? OR s.provider LIKE ?)")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if category:
        conditions.append("s.category = ?")
        params.append(category)
    if provider:
        conditions.append("s.provider LIKE ?")
        params.append(f"%{provider}%")
    if date_from:
        conditions.append("s.service_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("s.service_date <= ?")
        params.append(date_to)
    if min_amount is not None:
        conditions.append("s.amount >= ?")
        params.append(min_amount)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    order_col = sort_by if sort_by in _VALID_SERVICE_SORT_COLS else "service_date"
    direction = "ASC" if str(sort_dir).upper() == "ASC" else "DESC"

    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM services s {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT s.*, d.filename as doc_filename FROM services s "
            f"LEFT JOIN documents d ON s.document_id = d.id "
            f"{where} ORDER BY s.{order_col} {direction} NULLS LAST, s.id DESC "
            f"LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()
    return [dict(r) for r in rows], total


def get_all_for_export():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT s.*, d.filename as doc_filename FROM services s "
            "LEFT JOIN documents d ON s.document_id = d.id "
            "ORDER BY s.service_date DESC NULLS LAST"
        ).fetchall()
    return [dict(r) for r in rows]


def get_stats():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM services").fetchone()[0]
        total_amount = conn.execute("SELECT COALESCE(SUM(amount),0) FROM services").fetchone()[0]
        docs_processed = conn.execute(
            "SELECT COUNT(DISTINCT document_id) FROM services WHERE document_id IS NOT NULL"
        ).fetchone()[0]
        by_cat = conn.execute(
            "SELECT category, COUNT(*) as count, COALESCE(SUM(amount),0) as amount "
            "FROM services GROUP BY category ORDER BY amount DESC"
        ).fetchall()
    return {
        "total_services": total,
        "total_amount": total_amount,
        "docs_processed": docs_processed,
        "by_category": [dict(r) for r in by_cat],
    }


def insert_services(document_id: int, services: list[dict], extracted_at: str) -> int:
    with get_conn() as conn:
        count = 0
        for s in services:
            conn.execute(
                "INSERT INTO services (document_id, name, description, provider, "
                "service_date, amount, currency, category, extracted_at, notes, source_text, source_page) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    document_id,
                    s.get("name", ""),
                    s.get("description"),
                    s.get("provider"),
                    s.get("service_date"),
                    s.get("amount"),
                    s.get("currency", "EUR"),
                    s.get("category"),
                    extracted_at,
                    s.get("notes"),
                    s.get("source_text"),
                    s.get("source_page"),
                )
            )
            count += 1
    return count


def update_provider_for_document(document_id: int, provider: str) -> int:
    """Update provider on all services for a document. Returns number of updated rows."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE services SET provider = ? WHERE document_id = ?", (provider, document_id)
        )
        return cur.rowcount


def has_services_for_document(document_id: int) -> bool:
    with get_conn() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM services WHERE document_id = ?", (document_id,)
        ).fetchone()[0]
    return n > 0


def get_unprocessed_service_invoice_ids() -> list[int]:
    """Return doc IDs for Rechnung or Dienstleistungsrechnung docs that have no extracted services yet
    AND no extracted items (i.e. not already identified as goods invoices)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT d.id FROM documents d "
            "WHERE d.document_type IN ('Rechnung', 'Dienstleistungsrechnung') "
            "AND d.status IN ('ok', 'review') "
            "AND d.full_text IS NOT NULL AND d.full_text != '' "
            "AND NOT EXISTS (SELECT 1 FROM services s WHERE s.document_id = d.id) "
            "AND NOT EXISTS (SELECT 1 FROM items i WHERE i.document_id = d.id) "
            "ORDER BY d.date DESC"
        ).fetchall()
    return [r["id"] for r in rows]


def to_csv(services: list[dict]) -> str:
    if not services:
        return ""
    fields = ["id", "document_id", "doc_filename", "name", "description",
              "provider", "service_date", "amount", "currency", "category", "notes"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(services)
    return buf.getvalue()
