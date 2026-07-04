from db.connection import get_conn

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

        no_sender = conn.execute("""
            SELECT COUNT(*) FROM documents
            WHERE status = 'ok' AND (sender IS NULL OR sender = '')
        """).fetchone()[0]

        low_value = conn.execute("""
            SELECT COUNT(*) FROM documents
            WHERE status = 'ok' AND low_value = 1
        """).fetchone()[0]

        return {
            "total": total,
            "by_category": [dict(r) for r in by_category],
            "by_year": [dict(r) for r in by_year],
            "by_status": [dict(r) for r in by_status],
            "recent": [dict(r) for r in recent],
            "no_sender": no_sender,
            "low_value": low_value,
        }
