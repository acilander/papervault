import os
from datetime import datetime
from db.connection import get_conn

def upsert_document(file_path, filename, sender, date, document_type,
                    category, summary, content_hash=None, status="ok", archived_at=None, property_unit=None, vehicle_id=None, child_name=None):
    from utils import normalize_path
    file_path = normalize_path(file_path) if file_path else file_path
    archived_at = archived_at or datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO documents
                (file_path, filename, sender, date, document_type, category, summary, content_hash, status, archived_at, property_unit, vehicle_id, child_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                filename      = excluded.filename,
                sender        = excluded.sender,
                date          = excluded.date,
                document_type = excluded.document_type,
                category      = excluded.category,
                summary       = excluded.summary,
                content_hash  = excluded.content_hash,
                status        = excluded.status,
                property_unit = excluded.property_unit,
                vehicle_id    = excluded.vehicle_id,
                child_name    = excluded.child_name
        """, (file_path, filename, sender, date, document_type, category, summary, content_hash, status, archived_at, property_unit, vehicle_id, child_name))
        row = conn.execute("SELECT id FROM documents WHERE file_path = ?", (file_path,)).fetchone()
        return row["id"] if row else None


def get_all_file_paths() -> set:
    with get_conn() as conn:
        rows = conn.execute("SELECT file_path FROM documents").fetchall()
    return {os.path.normpath(r["file_path"]) for r in rows if r["file_path"]}


def get_document(doc_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None


def get_document_by_path(file_path):
    path = os.path.normpath(file_path) if file_path else file_path
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM documents WHERE file_path = ?", (path,)).fetchone()
        return dict(row) if row else None


def get_document_by_hash(content_hash):
    if not content_hash:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE content_hash = ? AND status IN ('ok', 'review', 'processing', 'locked') LIMIT 1",
            (content_hash,)
        ).fetchone()
        return dict(row) if row else None


def get_documents_without_sender():
    """Return all ok/review documents with empty or null sender."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM documents WHERE status IN ('ok', 'review') AND (sender IS NULL OR sender = '') ORDER BY archived_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_document(doc_id, **fields):
    from utils import normalize_path
    if "file_path" in fields and fields["file_path"]:
        fields["file_path"] = normalize_path(fields["file_path"])
        # If the target path is already owned by a different document, disambiguate
        target_path = fields["file_path"]
        with get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM documents WHERE file_path = ? AND id != ?", (target_path, doc_id)
            ).fetchone()
        if row:
            from pdf_utils import unique_path
            new_path = unique_path(target_path)
            if os.path.exists(target_path):
                import shutil
                shutil.move(target_path, new_path)
            fields["file_path"] = new_path
            if "filename" in fields:
                fields["filename"] = os.path.basename(new_path)
    allowed = {"sender", "date", "document_type", "category", "summary", "status",
               "file_path", "filename", "tags", "tax_relevant", "tax_year", "expires_at", "notes",
               "keywords", "low_value", "full_text", "sim_hash", "content_hash", "iban", "property_unit", "vehicle_id", "child_name", "verified"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [doc_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE documents SET {set_clause} WHERE id = ?", values)


def claim_document_status(doc_id: int, old_status: str, new_status: str) -> bool:
    """Atomically transition document status. Returns True on success, False if already updated."""
    with get_conn() as conn:
        cursor = conn.execute(
            "UPDATE documents SET status = ? WHERE id = ? AND status = ?",
            (new_status, doc_id, old_status)
        )
        return cursor.rowcount > 0


_LIST_COLS = """
    d.id, d.file_path, d.filename, d.sender, d.date, d.document_type, d.category,
    SUBSTR(d.summary, 1, 200) AS summary, d.content_hash, d.status, d.archived_at,
    d.tags, d.tax_relevant, d.tax_year, d.expires_at, d.notes, d.low_value, d.confidence, d.verified
"""


_VALID_SORT_COLS = {"filename", "sender", "category", "document_type", "date", "status", "archived_at", "confidence"}


def search_documents(query=None, category=None, year=None, sender=None,
                     status=None, tax_relevant=None, tag=None, no_sender=False, low_value=None, confidence=None,
                     sort_by=None, sort_dir=None, limit=100, offset=0):
    """Full-text search + optional filters. Returns list of dicts (no full_text/sim_hash/keywords)."""
    with get_conn() as conn:
        if query:
            sql = f"""
                SELECT {_LIST_COLS}
                FROM documents d
                WHERE EXISTS (
                    SELECT 1 FROM documents_fts
                    WHERE documents_fts.rowid = d.id AND documents_fts MATCH ?
                )
            """
            params = [query]
        else:
            sql = f"SELECT {_LIST_COLS} FROM documents d WHERE 1=1"
            params = []

        if category:
            sql += " AND d.category = ?"
            params.append(category)
        if year:
            sql += " AND d.date LIKE ?"
            params.append(f"{year}%")
        if sender:
            sql += " AND d.sender LIKE ?"
            params.append(f"%{sender}%")
        if status:
            sql += " AND d.status = ?"
            params.append(status)
        else:
            sql += " AND d.status != 'ignored'"
        if tax_relevant is not None:
            sql += " AND d.tax_relevant = ?"
            params.append(int(tax_relevant))
        if tag:
            sql += " AND d.tags LIKE ?"
            params.append(f"%{tag}%")
        if no_sender:
            sql += " AND (d.sender IS NULL OR d.sender = '')"
        if low_value is not None:
            sql += " AND d.low_value = ?"
            params.append(int(low_value))
        if confidence:
            sql += " AND d.confidence = ?"
            params.append(confidence)

        order_col = sort_by if sort_by in _VALID_SORT_COLS else "archived_at"
        direction = "ASC" if str(sort_dir).upper() == "ASC" else "DESC"
        sql += f" ORDER BY d.{order_col} {direction} LIMIT ? OFFSET ?"
        params += [limit, offset]

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def bulk_update_documents(ids: list, fields: dict) -> int:
    """Update multiple documents in a single SQL transaction. Returns rowcount."""
    allowed = {"sender", "category", "document_type", "date", "notes"}
    filtered = {k: v for k, v in fields.items() if k in allowed}
    if not filtered or not ids:
        return 0
    set_clause = ", ".join(f"{k} = ?" for k in filtered)
    placeholders = ",".join("?" * len(ids))
    values = list(filtered.values()) + list(ids)
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE documents SET {set_clause} WHERE id IN ({placeholders})",
            values
        )
        return cur.rowcount


def count_documents(query=None, category=None, year=None, sender=None,
                    status=None, tax_relevant=None, tag=None, no_sender=False, low_value=None, confidence=None):
    """Count matching documents (same filters as search_documents, no limit/offset)."""
    with get_conn() as conn:
        if query:
            sql = """
                SELECT COUNT(*) FROM documents d
                WHERE EXISTS (
                    SELECT 1 FROM documents_fts
                    WHERE documents_fts.rowid = d.id AND documents_fts MATCH ?
                )
            """
            params = [query]
        else:
            sql = "SELECT COUNT(*) FROM documents d WHERE 1=1"
            params = []

        if category:
            sql += " AND d.category = ?"
            params.append(category)
        if year:
            sql += " AND d.date LIKE ?"
            params.append(f"{year}%")
        if sender:
            sql += " AND d.sender LIKE ?"
            params.append(f"%{sender}%")
        if status:
            sql += " AND d.status = ?"
            params.append(status)
        else:
            sql += " AND d.status != 'ignored'"
        if tax_relevant is not None:
            sql += " AND d.tax_relevant = ?"
            params.append(int(tax_relevant))
        if tag:
            sql += " AND d.tags LIKE ?"
            params.append(f"%{tag}%")
        if no_sender:
            sql += " AND (d.sender IS NULL OR d.sender = '')"
        if low_value is not None:
            sql += " AND d.low_value = ?"
            params.append(int(low_value))
        if confidence:
            sql += " AND d.confidence = ?"
            params.append(confidence)

        return conn.execute(sql, params).fetchone()[0]


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


def get_similar_by_simhash(sim_hash: int, doc_id: int, max_distance: int = 8, limit: int = 3):
    """Find documents with similar SimHash (near-duplicates from rescanning).
    max_distance=8 out of 64 bits means ~87.5% similarity threshold."""
    if not sim_hash:
        return []
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, file_path, filename, sender, date, document_type, sim_hash, hamming_distance(?, sim_hash) as dist
               FROM documents
               WHERE sim_hash IS NOT NULL AND id != ? AND status IN ('ok', 'review')
                 AND hamming_distance(?, sim_hash) <= ?
               ORDER BY dist ASC LIMIT ?""",
            (sim_hash, doc_id, sim_hash, max_distance, limit)
        ).fetchall()
    return [{**dict(row), "simhash_distance": row["dist"]} for row in rows]


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
