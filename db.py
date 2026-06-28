import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

from config import DB_PATH


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path     TEXT UNIQUE NOT NULL,
    filename      TEXT NOT NULL,
    sender        TEXT,
    date          TEXT,
    document_type TEXT,
    category      TEXT,
    summary       TEXT,
    content_hash  TEXT,
    status        TEXT DEFAULT 'ok',
    archived_at   TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    filename, sender, summary, keywords,
    content=documents, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, filename, sender, summary, keywords)
    VALUES (new.id, new.filename, new.sender, new.summary, new.keywords);
END;

CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, filename, sender, summary, keywords)
    VALUES ('delete', old.id, old.filename, old.sender, old.summary, old.keywords);
    INSERT INTO documents_fts(rowid, filename, sender, summary, keywords)
    VALUES (new.id, new.filename, new.sender, new.summary, new.keywords);
END;

CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, filename, sender, summary, keywords)
    VALUES ('delete', old.id, old.filename, old.sender, old.summary, old.keywords);
END;
"""


MIGRATIONS = [
    "ALTER TABLE documents ADD COLUMN tags TEXT DEFAULT ''",
    "ALTER TABLE documents ADD COLUMN tax_relevant INTEGER DEFAULT 0",
    "ALTER TABLE documents ADD COLUMN tax_year TEXT",
    "ALTER TABLE documents ADD COLUMN expires_at TEXT",
    "ALTER TABLE documents ADD COLUMN notes TEXT",
    "ALTER TABLE documents ADD COLUMN keywords TEXT DEFAULT ''",
    # Rebuild FTS index to include new keywords column
    "INSERT INTO documents_fts(documents_fts) VALUES('rebuild')",
]


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # Run additive migrations (safe to re-run – ignore 'duplicate column' errors)
        for migration in MIGRATIONS:
            try:
                conn.execute(migration)
            except Exception:
                pass


def upsert_document(file_path, filename, sender, date, document_type,
                    category, summary, content_hash=None, status="ok", archived_at=None):
    archived_at = archived_at or datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO documents
                (file_path, filename, sender, date, document_type, category, summary, content_hash, status, archived_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                filename      = excluded.filename,
                sender        = excluded.sender,
                date          = excluded.date,
                document_type = excluded.document_type,
                category      = excluded.category,
                summary       = excluded.summary,
                content_hash  = excluded.content_hash,
                status        = excluded.status
        """, (file_path, filename, sender, date, document_type, category, summary, content_hash, status, archived_at))
        row = conn.execute("SELECT id FROM documents WHERE file_path = ?", (file_path,)).fetchone()
        return row["id"] if row else None


def get_document(doc_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None


def update_document(doc_id, **fields):
    allowed = {"sender", "date", "document_type", "category", "summary", "status",
               "file_path", "filename", "tags", "tax_relevant", "tax_year", "expires_at", "notes",
               "keywords"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [doc_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE documents SET {set_clause} WHERE id = ?", values)


def search_documents(query=None, category=None, year=None, sender=None,
                     status=None, tax_relevant=None, tag=None, limit=100, offset=0):
    """Full-text search + optional filters. Returns list of dicts."""
    with get_conn() as conn:
        if query:
            sql = """
                SELECT d.* FROM documents d
                JOIN documents_fts fts ON d.id = fts.rowid
                WHERE documents_fts MATCH ?
            """
            params = [query]
        else:
            sql = "SELECT * FROM documents WHERE 1=1"
            params = []

        if category:
            sql += " AND category = ?"
            params.append(category)
        if year:
            sql += " AND date LIKE ?"
            params.append(f"{year}%")
        if sender:
            sql += " AND sender LIKE ?"
            params.append(f"%{sender}%")
        if status:
            sql += " AND status = ?"
            params.append(status)
        if tax_relevant is not None:
            sql += " AND tax_relevant = ?"
            params.append(int(tax_relevant))
        if tag:
            sql += " AND tags LIKE ?"
            params.append(f"%{tag}%")

        sql += " ORDER BY archived_at DESC LIMIT ? OFFSET ?"
        params += [limit, offset]

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_stats():
    """Returns counts per category, per year, total, and recent."""
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM documents WHERE status = 'ok'").fetchone()[0]

        by_category = conn.execute("""
            SELECT category, COUNT(*) as count
            FROM documents WHERE status = 'ok'
            GROUP BY category ORDER BY count DESC
        """).fetchall()

        by_year = conn.execute("""
            SELECT SUBSTR(date, 1, 4) as year, COUNT(*) as count
            FROM documents WHERE status = 'ok' AND date IS NOT NULL
            GROUP BY year ORDER BY year DESC
        """).fetchall()

        by_status = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM documents GROUP BY status
        """).fetchall()

        recent = conn.execute("""
            SELECT * FROM documents WHERE status = 'ok'
            ORDER BY archived_at DESC LIMIT 10
        """).fetchall()

        return {
            "total": total,
            "by_category": [dict(r) for r in by_category],
            "by_year": [dict(r) for r in by_year],
            "by_status": [dict(r) for r in by_status],
            "recent": [dict(r) for r in recent],
        }


def delete_document(doc_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


def get_expiring_documents(days=30):
    """Return documents whose expires_at is within the next `days` days."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM documents
            WHERE expires_at IS NOT NULL AND expires_at != ''
              AND expires_at <= date('now', 'localtime', ? || ' days')
              AND expires_at > date('now', 'localtime')
            ORDER BY expires_at ASC
        """, (f"+{days}",)).fetchall()
        return [dict(r) for r in rows]


def get_tax_documents(year=None):
    """Return all tax-relevant documents, optionally filtered by tax_year."""
    with get_conn() as conn:
        if year:
            rows = conn.execute(
                "SELECT * FROM documents WHERE tax_relevant = 1 AND tax_year = ? ORDER BY date",
                (str(year),)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM documents WHERE tax_relevant = 1 ORDER BY tax_year DESC, date"
            ).fetchall()
        return [dict(r) for r in rows]


def find_similar_by_features(category_candidates, type_candidate, limit=3):
    """Find successfully classified documents that match the given structural features.
    Returns up to `limit` docs ordered by relevance (category match first)."""
    if not category_candidates and not type_candidate:
        return []
    with get_conn() as conn:
        results = []
        seen_ids = set()
        # 1. Exact category + type match
        for cat in category_candidates:
            if type_candidate:
                rows = conn.execute(
                    "SELECT id, sender, category, document_type, summary, date FROM documents "
                    "WHERE status='ok' AND category=? AND document_type=? ORDER BY archived_at DESC LIMIT ?",
                    (cat, type_candidate, limit)
                ).fetchall()
                for r in rows:
                    if r["id"] not in seen_ids:
                        results.append(dict(r))
                        seen_ids.add(r["id"])
        # 2. Category match only
        for cat in category_candidates:
            if len(results) >= limit:
                break
            rows = conn.execute(
                "SELECT id, sender, category, document_type, summary, date FROM documents "
                "WHERE status='ok' AND category=? ORDER BY archived_at DESC LIMIT ?",
                (cat, limit)
            ).fetchall()
            for r in rows:
                if r["id"] not in seen_ids and len(results) < limit:
                    results.append(dict(r))
                    seen_ids.add(r["id"])
        return results[:limit]
