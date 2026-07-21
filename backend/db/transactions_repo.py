"""
transactions_repo.py – SQLite-backed repository for business and long-running transactions (Vorgänge).
Handles CRUD operations for transactions and linking documents to transactions with specific roles.
"""

from datetime import datetime
from db.connection import get_conn

def create_transaction(title: str, status: str = "open", type_val: str = "discrete") -> int:
    """Create a new transaction and return its ID."""
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO transactions (title, status, type, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (title, status, type_val, now, now)
        )
        return cursor.lastrowid

def get_transaction(tx_id: int) -> dict | None:
    """Retrieve a single transaction with all its linked documents."""
    with get_conn() as conn:
        tx_row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()
        if not tx_row:
            return None
        
        tx = dict(tx_row)
        
        # Get linked documents
        doc_rows = conn.execute(
            """SELECT td.role, td.created_at as linked_at, d.*
               FROM transaction_documents td
               JOIN documents d ON td.document_id = d.id
               WHERE td.transaction_id = ?
               ORDER BY d.date ASC, d.archived_at ASC""",
            (tx_id,)
        ).fetchall()
        
        tx["documents"] = [dict(r) for r in doc_rows]
        return tx

def list_transactions(status: str = None, type_val: str = None) -> list[dict]:
    """List all transactions, optionally filtered by status or type.
    Includes document count for each transaction."""
    query = """
        SELECT t.*, COUNT(td.document_id) as document_count
        FROM transactions t
        LEFT JOIN transaction_documents td ON t.id = td.transaction_id
    """
    conditions = []
    params = []
    if status:
        conditions.append("t.status = ?")
        params.append(status)
    if type_val:
        conditions.append("t.type = ?")
        params.append(type_val)
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    query += " GROUP BY t.id ORDER BY t.updated_at DESC"
    
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

def update_transaction(tx_id: int, **kwargs) -> bool:
    """Update transaction fields (title, status, type)."""
    allowed_fields = {"title", "status", "type"}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not updates:
        return False
        
    now = datetime.now().isoformat(timespec="seconds")
    updates["updated_at"] = now
    
    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    params = list(updates.values()) + [tx_id]
    
    with get_conn() as conn:
        cursor = conn.execute(
            f"UPDATE transactions SET {set_clause} WHERE id = ?", params
        )
        return cursor.rowcount > 0

def delete_transaction(tx_id: int) -> bool:
    """Delete a transaction. SQLite cascade will delete linked document references."""
    with get_conn() as conn:
        cursor = conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        return cursor.rowcount > 0

def add_document_to_transaction(tx_id: int, doc_id: int, role: str) -> bool:
    """Link a document to a transaction with a specific role."""
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO transaction_documents (transaction_id, document_id, role, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(transaction_id, document_id) DO UPDATE SET role=excluded.role""",
            (tx_id, doc_id, role, now)
        )
        # Update transaction updated_at
        conn.execute(
            "UPDATE transactions SET updated_at = ? WHERE id = ?", (now, tx_id)
        )
        return True

def remove_document_from_transaction(tx_id: int, doc_id: int) -> bool:
    """Unlink a document from a transaction."""
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        cursor = conn.execute(
            "DELETE FROM transaction_documents WHERE transaction_id = ? AND document_id = ?",
            (tx_id, doc_id)
        )
        if cursor.rowcount > 0:
            conn.execute(
                "UPDATE transactions SET updated_at = ? WHERE id = ?", (now, tx_id)
            )
            return True
        return False

def get_transactions_for_document(doc_id: int) -> list[dict]:
    """Retrieve all transactions linked to a specific document, including the document's role in each."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT t.*, td.role, td.created_at as linked_at
               FROM transaction_documents td
               JOIN transactions t ON td.transaction_id = t.id
               WHERE td.document_id = ?
               ORDER BY t.updated_at DESC""",
            (doc_id,)
        ).fetchall()
        return [dict(r) for r in rows]
