import os
from datetime import datetime, timezone
from db.connection import get_conn


COLLECTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS collections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    color       TEXT DEFAULT '#6366f1',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_documents (
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    document_id   INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    added_at      TEXT NOT NULL,
    PRIMARY KEY (collection_id, document_id)
);
"""


def init_collections_table():
    with get_conn() as conn:
        conn.executescript(COLLECTIONS_SCHEMA)


def get_all_collections():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT c.*, COUNT(cd.document_id) as doc_count
               FROM collections c
               LEFT JOIN collection_documents cd ON c.id = cd.collection_id
               GROUP BY c.id ORDER BY c.updated_at DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


_VALID_COLLECTION_DOC_SORT_COLS = {"filename", "sender", "category", "document_type", "date", "added_at"}


def get_collection(collection_id: int, sort_by: str = "added_at", sort_dir: str = "desc"):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
        if not row:
            return None
        col = dict(row)
        order_col = sort_by if sort_by in _VALID_COLLECTION_DOC_SORT_COLS else "added_at"
        direction = "ASC" if str(sort_dir).upper() == "ASC" else "DESC"
        doc_rows = conn.execute(
            f"""SELECT d.id, d.filename, d.sender, d.date, d.document_type, d.category,
                      d.summary, d.file_path, d.status, cd.added_at
               FROM collection_documents cd
               JOIN documents d ON d.id = cd.document_id
               WHERE cd.collection_id = ?
               ORDER BY {order_col} {direction} NULLS LAST""",
            (collection_id,)
        ).fetchall()
        col["documents"] = [dict(r) for r in doc_rows]
    return col


def create_collection(name: str, description: str = "", color: str = "#6366f1"):
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO collections (name, description, color, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (name, description, color, now, now)
        )
        return cur.lastrowid


def update_collection(collection_id: int, **fields):
    allowed = {"name", "description", "color"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [collection_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE collections SET {set_clause} WHERE id = ?", values)


def delete_collection(collection_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,))


def add_document(collection_id: int, document_id: int):
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO collection_documents (collection_id, document_id, added_at) VALUES (?, ?, ?)",
            (collection_id, document_id, now)
        )
        conn.execute("UPDATE collections SET updated_at = ? WHERE id = ?", (now, collection_id))


def remove_document(collection_id: int, document_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM collection_documents WHERE collection_id = ? AND document_id = ?",
            (collection_id, document_id)
        )
        conn.execute(
            "UPDATE collections SET updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), collection_id)
        )


def get_collections_for_document(document_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT c.id, c.name, c.color FROM collections c
               JOIN collection_documents cd ON c.id = cd.collection_id
               WHERE cd.document_id = ?
               ORDER BY c.name""",
            (document_id,)
        ).fetchall()
    return [dict(r) for r in rows]
