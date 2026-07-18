"""
identifiers_repo.py – SQLite-backed repository for deterministic entity identifiers.
Handles confirmed sender_identifiers and temporary unassigned_identifiers.
"""
from datetime import datetime
import json
from db.connection import get_conn

def get_all_identifiers() -> list[dict]:
    """Returns a list of all confirmed identifiers, sorted by sender_name."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT id, sender_name, identifier_type, identifier_value, label, target_category, target_unit, created_at
            FROM sender_identifiers
            ORDER BY sender_name ASC, identifier_type ASC
        """).fetchall()
    return [dict(r) for r in rows]

def add_identifier(sender_name: str, identifier_type: str, identifier_value: str, label: str = None, target_category: str = None, target_unit: str = None) -> int:
    """Adds a new confirmed identifier. Returns the inserted row's ID."""
    with get_conn() as conn:
        cursor = conn.execute("""
            INSERT INTO sender_identifiers (sender_name, identifier_type, identifier_value, label, target_category, target_unit, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sender_name, identifier_type, identifier_value, label, target_category, target_unit, datetime.now().isoformat(timespec="seconds")))
        return cursor.lastrowid

def delete_identifier(identifier_id: int) -> bool:
    """Deletes a confirmed identifier by ID."""
    with get_conn() as conn:
        cursor = conn.execute("DELETE FROM sender_identifiers WHERE id = ?", (identifier_id,))
        return cursor.rowcount > 0

def get_unassigned_identifiers() -> list[dict]:
    """Returns all pending unassigned identifiers, enriched with document filename."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ui.id, ui.document_id, ui.identifier_type, ui.identifier_value, ui.context_text, ui.detected_at,
                   d.filename as document_filename
            FROM unassigned_identifiers ui
            LEFT JOIN documents d ON ui.document_id = d.id
            ORDER BY ui.detected_at DESC
        """).fetchall()
    return [dict(r) for r in rows]

def save_unassigned_identifier(document_id: int, identifier_type: str, identifier_value: str, context_text: str = None) -> bool:
    """Inserts a new unassigned identifier suggestion if it does not already exist."""
    with get_conn() as conn:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO unassigned_identifiers (document_id, identifier_type, identifier_value, context_text, detected_at)
                VALUES (?, ?, ?, ?, ?)
            """, (document_id, identifier_type, identifier_value, context_text, datetime.now().isoformat(timespec="seconds")))
            return True
        except Exception:
            return False

def delete_unassigned_identifier(unassigned_id: int) -> bool:
    """Deletes/dismisses an unassigned identifier from the inbox."""
    with get_conn() as conn:
        cursor = conn.execute("DELETE FROM unassigned_identifiers WHERE id = ?", (unassigned_id,))
        return cursor.rowcount > 0

def assign_unassigned_identifier(unassigned_id: int, sender_name: str, label: str = None, target_category: str = None, target_unit: str = None) -> int:
    """Moves an unassigned identifier to sender_identifiers and deletes it from unassigned_identifiers."""
    with get_conn() as conn:
        # Retrieve the unassigned identifier details
        row = conn.execute("SELECT identifier_type, identifier_value FROM unassigned_identifiers WHERE id = ?", (unassigned_id,)).fetchone()
        if not row:
            raise ValueError(f"Unassigned identifier with ID {unassigned_id} not found.")
        
        # Insert into sender_identifiers
        cursor = conn.execute("""
            INSERT INTO sender_identifiers (sender_name, identifier_type, identifier_value, label, target_category, target_unit, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sender_name, row["identifier_type"], row["identifier_value"], label, target_category, target_unit, datetime.now().isoformat(timespec="seconds")))
        
        # Delete from unassigned_identifiers
        conn.execute("DELETE FROM unassigned_identifiers WHERE id = ?", (unassigned_id,))
        return cursor.lastrowid

def match_existing_identifiers(text: str) -> tuple[str, dict] | tuple[None, None]:
    """
    Scans the given raw text to see if any verified identifier_value exists as a substring.
    Matching is case-insensitive.
    Returns (sender_name, config_dict) of the first match, or (None, None).
    """
    if not text:
        return None, None
    text_lower = text.lower()
    
    # Fetch all registered identifiers
    identifiers = get_all_identifiers()
    for item in identifiers:
        val = str(item["identifier_value"]).lower().strip()
        if val and val in text_lower:
            return item["sender_name"], item
            
    return None, None
