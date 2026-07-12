from datetime import datetime, timezone

from db.connection import get_conn


PROTECTED_TYPES = {"ignored", "locked"}


def init_protected_hashes_table():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS protected_document_hashes (
                hash         TEXT PRIMARY KEY,
                type         TEXT NOT NULL CHECK(type IN ('ignored', 'locked')),
                document_id  INTEGER,
                filename     TEXT,
                created_at   TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_protected_hashes_type
            ON protected_document_hashes(type)
        """)


def protect_document_hash(hash_value: str, type_: str, document_id: int | None = None, filename: str | None = None):
    if type_ not in PROTECTED_TYPES:
        raise ValueError(f"Ungueltiger Schutztyp: {type_}")
    if not hash_value:
        return
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO protected_document_hashes (hash, type, document_id, filename, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(hash) DO UPDATE SET
                type = excluded.type,
                document_id = excluded.document_id,
                filename = excluded.filename
            """,
            (hash_value, type_, document_id, filename, now),
        )


def unprotect_document_hash(hash_value: str | None = None, document_id: int | None = None):
    if not hash_value and document_id is None:
        raise ValueError("hash oder document_id angeben")
    with get_conn() as conn:
        if hash_value:
            conn.execute("DELETE FROM protected_document_hashes WHERE hash = ?", (hash_value,))
        else:
            conn.execute("DELETE FROM protected_document_hashes WHERE document_id = ?", (document_id,))


def get_protected_hash(hash_value: str) -> dict | None:
    if not hash_value:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM protected_document_hashes WHERE hash = ?",
            (hash_value,),
        ).fetchone()
        return dict(row) if row else None


def is_hash_protected(hash_value: str) -> bool:
    return get_protected_hash(hash_value) is not None


def list_protected_hashes(type_: str | None = None, limit: int = 1000, offset: int = 0) -> list[dict]:
    with get_conn() as conn:
        if type_:
            rows = conn.execute(
                "SELECT * FROM protected_document_hashes WHERE type = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (type_, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM protected_document_hashes ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]
