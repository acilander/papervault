import os
from datetime import datetime
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


def get_collection(collection_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
        if not row:
            return None
        col = dict(row)
        doc_rows = conn.execute(
            """SELECT d.id, d.filename, d.sender, d.date, d.document_type, d.category,
                      d.summary, d.file_path, d.status, cd.added_at
               FROM collection_documents cd
               JOIN documents d ON d.id = cd.document_id
               WHERE cd.collection_id = ?
               ORDER BY cd.added_at DESC""",
            (collection_id,)
        ).fetchall()
        col["documents"] = [dict(r) for r in doc_rows]
    return col


def create_collection(name: str, description: str = "", color: str = "#6366f1"):
    now = datetime.utcnow().isoformat()
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
    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [collection_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE collections SET {set_clause} WHERE id = ?", values)


def delete_collection(collection_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,))


def add_document(collection_id: int, document_id: int):
    now = datetime.utcnow().isoformat()
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
            (datetime.utcnow().isoformat(), collection_id)
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
