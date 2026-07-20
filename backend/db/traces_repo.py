import json
from datetime import datetime
from db.connection import get_conn

def insert_trace(document_id: int, step_name: str, status: str, message: str, details: dict = None):
    """
    Inserts a trace log entry for a specific document.
    status can be: 'success', 'warning', 'failed', 'skipped'
    """
    details_str = json.dumps(details, ensure_ascii=False) if details else None
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO document_traces (document_id, timestamp, step_name, status, message, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (document_id, timestamp, step_name, status, message, details_str)
        )

def get_traces_for_document(document_id: int) -> list[dict]:
    """
    Returns all trace logs for a specific document sorted by ID (order of occurrence).
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, document_id, timestamp, step_name, status, message, details "
            "FROM document_traces WHERE document_id = ? ORDER BY id ASC",
            (document_id,)
        ).fetchall()
    
    traces = []
    for r in rows:
        trace = dict(r)
        if trace.get("details"):
            try:
                trace["details"] = json.loads(trace["details"])
            except Exception:
                pass
        traces.append(trace)
    return traces

def delete_traces_for_document(document_id: int):
    """
    Deletes all traces for a specific document.
    """
    with get_conn() as conn:
        conn.execute("DELETE FROM document_traces WHERE document_id = ?", (document_id,))
