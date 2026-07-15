"""
SenderRepository – SQLite-backed storage for the sender registry.

Replaces senders.json as the primary data store. Each sender is one row
in the `senders` table. JSON columns store lists (categories, aliases,
excluded_categories).
"""
import json
from db.connection import get_conn

# ── Schema ─────────────────────────────────────────────────────────────────────

SENDER_SCHEMA = """
CREATE TABLE IF NOT EXISTS senders (
    name                 TEXT PRIMARY KEY,
    categories           TEXT NOT NULL DEFAULT '[]',
    pinned_category      TEXT,
    pinned_document_type TEXT,
    excluded_categories  TEXT NOT NULL DEFAULT '[]',
    aliases              TEXT NOT NULL DEFAULT '[]',
    reviewed             INTEGER NOT NULL DEFAULT 0
);
"""

SENDER_MIGRATION_ADD_PINNED_TYPE = """
ALTER TABLE senders ADD COLUMN pinned_document_type TEXT;
"""

SENDER_MIGRATION = "INSERT INTO senders SELECT name, categories, pinned_category, excluded_categories, aliases, reviewed FROM senders WHERE 0"


def init_sender_table():
    with get_conn() as conn:
        conn.executescript(SENDER_SCHEMA)
        try:
            conn.execute(SENDER_MIGRATION_ADD_PINNED_TYPE)
        except Exception:
            pass


# ── Helpers ────────────────────────────────────────────────────────────────────

def _row_to_entry(row) -> dict:
    return {
        "categories":          json.loads(row["categories"]),
        "pinned_category":     row["pinned_category"],
        "pinned_document_type": row["pinned_document_type"] if "pinned_document_type" in row.keys() else None,
        "excluded_categories": json.loads(row["excluded_categories"]),
        "aliases":             json.loads(row["aliases"]),
        "reviewed":            bool(row["reviewed"]),
    }


def _entry_defaults(entry: dict) -> dict:
    return {
        "categories":          entry.get("categories") or [],
        "pinned_category":     entry.get("pinned_category"),
        "pinned_document_type": entry.get("pinned_document_type"),
        "excluded_categories": entry.get("excluded_categories") or [],
        "aliases":             entry.get("aliases") or [],
        "reviewed":            bool(entry.get("reviewed", False)),
    }


# ── Read ───────────────────────────────────────────────────────────────────────

def get_all() -> dict[str, dict]:
    """Return all senders as {name: entry} dict."""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM senders ORDER BY name").fetchall()
    return {row["name"]: _row_to_entry(row) for row in rows}


def get(name: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM senders WHERE name = ?", (name,)).fetchone()
    return _row_to_entry(row) if row else None


def exists(name: str) -> bool:
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM senders WHERE name = ?", (name,)).fetchone() is not None


def count() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM senders").fetchone()[0]


# ── Write ──────────────────────────────────────────────────────────────────────

def upsert(name: str, entry: dict):
    """Insert or fully replace a sender entry."""
    e = _entry_defaults(entry)
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO senders (name, categories, pinned_category, pinned_document_type, excluded_categories, aliases, reviewed)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                 categories           = excluded.categories,
                 pinned_category      = excluded.pinned_category,
                 pinned_document_type = excluded.pinned_document_type,
                 excluded_categories  = excluded.excluded_categories,
                 aliases              = excluded.aliases,
                 reviewed             = excluded.reviewed""",
            (
                name,
                json.dumps(e["categories"], ensure_ascii=False),
                e["pinned_category"],
                e["pinned_document_type"],
                json.dumps(e["excluded_categories"], ensure_ascii=False),
                json.dumps(e["aliases"], ensure_ascii=False),
                int(e["reviewed"]),
            ),
        )


def update(name: str, **kwargs):
    """Partially update a sender entry. Only provided keys are changed."""
    with get_conn() as conn:
        if not exists(name):
            return
        entry = get(name)
        for key, val in kwargs.items():
            entry[key] = val
        upsert(name, entry)


def record_category(name: str, category: str) -> bool:
    """Add category to sender if not already present. Returns True if changed."""
    with get_conn() as conn:
        entry = get(name)
        if entry is None:
            upsert(name, {"categories": [category], "pinned_category": None,
                          "excluded_categories": [], "aliases": [], "reviewed": False})
            return True
        if category not in entry["categories"]:
            cats = sorted(entry["categories"] + [category])
            update(name, categories=cats)
            return True
        return False


def rename(old_name: str, new_name: str):
    """Rename sender: preserve old name as alias, update key."""
    with get_conn() as conn:
        entry = get(old_name)
        if entry is None:
            return
        aliases = entry.get("aliases") or []
        if old_name not in aliases:
            aliases = aliases + [old_name]
        entry["aliases"] = aliases
        upsert(new_name, entry)
        delete(old_name)


def delete(name: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM senders WHERE name = ?", (name,))


def cleanup_if_orphaned(name: str) -> bool:
    """Delete sender if no ok-documents reference it. Returns True if deleted."""
    if not name:
        return False
    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE sender = ? AND status = 'ok'", (name,)
        ).fetchone()[0]
        if count == 0:
            conn.execute("DELETE FROM senders WHERE name = ?", (name,))
            return True
    return False


# ── Bulk import (from senders.json) ───────────────────────────────────────────

def import_from_dict(data: dict):
    """Bulk import from the old senders.json dict format."""
    for name, entry in data.items():
        upsert(name, entry)


def _clear_all_for_tests():
    """Ensure senders table exists and delete all rows. Only for use in tests."""
    init_sender_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM senders")
