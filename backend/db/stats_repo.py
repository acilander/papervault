from db.connection import get_conn

def get_stats():
    """Returns counts per category, per year, total, recent, and new dashboard metrics."""
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM documents WHERE status IN ('ok', 'locked')").fetchone()[0]

        by_category = conn.execute("""
            SELECT category, COUNT(*) as count
            FROM documents WHERE status IN ('ok', 'locked')
            GROUP BY category ORDER BY count DESC
        """).fetchall()

        by_year = conn.execute("""
            SELECT SUBSTR(date, 1, 4) as year, COUNT(*) as count
            FROM documents WHERE status IN ('ok', 'locked') AND date IS NOT NULL
            GROUP BY year ORDER BY year DESC
        """).fetchall()

        by_status = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM documents GROUP BY status
        """).fetchall()

        recent = conn.execute("""
            SELECT * FROM documents WHERE status IN ('ok', 'locked')
            ORDER BY archived_at DESC LIMIT 10
        """).fetchall()

        no_sender = conn.execute("""
            SELECT COUNT(*) FROM documents
            WHERE status IN ('ok', 'locked') AND (sender IS NULL OR sender = '')
        """).fetchone()[0]

        low_value = conn.execute("""
            SELECT COUNT(*) FROM documents
            WHERE status IN ('ok', 'locked') AND low_value = 1
        """).fetchone()[0]

        # Inferenz-Ampel & Audit metrics
        verified_count = conn.execute("""
            SELECT COUNT(*) FROM documents
            WHERE status IN ('ok', 'locked') AND verified = 1
        """).fetchone()[0]
        locked_count = conn.execute("""
            SELECT COUNT(*) FROM documents WHERE status = 'locked'
        """).fetchone()[0]

        confidence_high = conn.execute("""
            SELECT COUNT(*) FROM documents
            WHERE status IN ('ok', 'locked') AND confidence = 'high'
        """).fetchone()[0]

        confidence_medium = conn.execute("""
            SELECT COUNT(*) FROM documents
            WHERE status IN ('ok', 'locked') AND confidence = 'medium'
        """).fetchone()[0]

        confidence_low = conn.execute("""
            SELECT COUNT(*) FROM documents
            WHERE status IN ('ok', 'locked') AND confidence = 'low'
        """).fetchone()[0]

        # Financial active contracts fix costs (normalized to monthly)
        monthly_fix_costs = 0.0
        try:
            from db.contracts_repo import get_stats as get_contracts_stats
            c_stats = get_contracts_stats()
            # Calculate total monthly equivalent from yearly_equiv
            monthly_fix_costs = round(c_stats.get("yearly_equiv", 0.0) / 12.0, 2)
        except Exception:
            pass

        return {
            "total": total,
            "by_category": [dict(r) for r in by_category],
            "by_year": [dict(r) for r in by_year],
            "by_status": [dict(r) for r in by_status],
            "recent": [dict(r) for r in recent],
            "no_sender": no_sender,
            "low_value": low_value,
            "verified_count": verified_count,
            "locked_count": locked_count,
            "confidence_high": confidence_high,
            "confidence_medium": confidence_medium,
            "confidence_low": confidence_low,
            "monthly_fix_costs": monthly_fix_costs,
        }
