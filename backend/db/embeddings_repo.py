import struct
from datetime import datetime, timezone
import numpy as np
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

def find_similar_documents(query_embedding: list[float], limit: int = 5) -> list[dict]:
    """Retrieve all embeddings, compute cosine similarities via Numpy,
    and return the top matching documents from the DB."""
    import db as _db
    
    # 1. Fetch all embeddings from SQLite
    all_embeds = get_all_embeddings()
    if not all_embeds:
        return []
        
    # 2. Convert to Numpy arrays
    doc_ids = list(all_embeds.keys())
    vectors = np.array(list(all_embeds.values()), dtype=np.float32) # shape: (num_docs, dim)
    q_vec = np.array(query_embedding, dtype=np.float32) # shape: (dim,)
    
    # 3. Calculate Cosine Similarity: dot product divided by norms
    # Cosine Sim = (A . B) / (||A|| * ||B||)
    dot_products = np.dot(vectors, q_vec)
    vectors_norm = np.linalg.norm(vectors, axis=1)
    q_vec_norm = np.linalg.norm(q_vec)
    
    # Avoid division by zero
    norms = vectors_norm * q_vec_norm
    norms[norms == 0.0] = 1.0
    similarities = dot_products / norms
    
    # 4. Sort and get top matches
    top_indices = np.argsort(similarities)[::-1][:limit]
    
    # 5. Fetch full document records for the top doc_ids
    results = []
    for idx in top_indices:
        doc_id = doc_ids[idx]
        sim_score = float(similarities[idx])
        doc = _db.get_document(doc_id)
        if doc:
            doc_copy = dict(doc)
            doc_copy["semantic_similarity"] = sim_score
            results.append(doc_copy)
    return results
