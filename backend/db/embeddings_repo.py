import struct
from datetime import datetime, timezone
from db.connection import get_conn

def init_embeddings_table():
    """Ensure table exist (handled by schema migrations, but good pattern)."""
    pass

def _serialize_embedding(vector: list[float]) -> bytes:
    """Pack list of floats into a binary blob of 32-bit floats."""
    return struct.pack(f"{len(vector)}f", *vector)

def _deserialize_embedding(blob: bytes) -> list[float]:
    """Unpack a binary blob of 32-bit floats back into a list of floats."""
    num_floats = len(blob) // 4
    return list(struct.unpack(f"{num_floats}f", blob))

def insert_embedding(document_id: int, embedding: list[float]) -> bool:
    """Store or overwrite the embedding for a document."""
    blob = _serialize_embedding(embedding)
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        try:
            conn.execute("""
                INSERT INTO document_embeddings (document_id, embedding, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    embedding  = excluded.embedding,
                    created_at = excluded.created_at
            """, (document_id, blob, now))
            return True
        except Exception:
            return False

def get_embedding(document_id: int) -> list[float] | None:
    """Retrieve the embedding vector for a single document."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT embedding FROM document_embeddings WHERE document_id = ?",
            (document_id,)
        ).fetchone()
    if row:
        return _deserialize_embedding(row["embedding"])
    return None

def get_all_embeddings() -> dict[int, list[float]]:
    """Retrieve all document embeddings. Returns dict mapping doc_id -> float vector."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT document_id, embedding FROM document_embeddings"
        ).fetchall()
    return {r["document_id"]: _deserialize_embedding(r["embedding"]) for r in rows}

def delete_embedding(document_id: int):
    """Delete a document's embedding."""
    with get_conn() as conn:
        conn.execute("DELETE FROM document_embeddings WHERE document_id = ?", (document_id,))
