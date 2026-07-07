import os
from datetime import datetime
from db.connection import get_conn
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path     TEXT UNIQUE NOT NULL,
    filename      TEXT NOT NULL,
    sender        TEXT,
    date          TEXT,
    document_type TEXT,
    category      TEXT,
    summary       TEXT,
    content_hash  TEXT,
    status        TEXT DEFAULT 'ok',
    archived_at   TEXT NOT NULL,
    tags          TEXT DEFAULT '',
    tax_relevant  INTEGER DEFAULT 0,
    tax_year      TEXT,
    expires_at    TEXT,
    notes         TEXT,
    keywords      TEXT DEFAULT '',
    low_value     INTEGER DEFAULT 0,
    full_text     TEXT DEFAULT '',
    confidence    TEXT DEFAULT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    filename, sender, summary, keywords, full_text,
    content=documents, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, filename, sender, summary, keywords, full_text)
    VALUES (new.id, new.filename, new.sender, new.summary, new.keywords, new.full_text);
END;

CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, filename, sender, summary, keywords, full_text)
    VALUES ('delete', old.id, old.filename, old.sender, old.summary, old.keywords, old.full_text);
    INSERT INTO documents_fts(rowid, filename, sender, summary, keywords, full_text)
    VALUES (new.id, new.filename, new.sender, new.summary, new.keywords, new.full_text);
END;

CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, filename, sender, summary, keywords, full_text)
    VALUES ('delete', old.id, old.filename, old.sender, old.summary, old.keywords, old.full_text);
END;
"""

MIGRATIONS = [
    "ALTER TABLE documents ADD COLUMN tags TEXT DEFAULT ''",
    "ALTER TABLE documents ADD COLUMN tax_relevant INTEGER DEFAULT 0",
    "ALTER TABLE documents ADD COLUMN tax_year TEXT",
    "ALTER TABLE documents ADD COLUMN expires_at TEXT",
    "ALTER TABLE documents ADD COLUMN notes TEXT",
    "ALTER TABLE documents ADD COLUMN keywords TEXT DEFAULT ''",
    # Rebuild FTS index to include new keywords column
    "INSERT INTO documents_fts(documents_fts) VALUES('rebuild')",
    "ALTER TABLE documents ADD COLUMN low_value INTEGER DEFAULT 0",
    "ALTER TABLE documents ADD COLUMN full_text TEXT DEFAULT ''",
    "ALTER TABLE documents ADD COLUMN sim_hash INTEGER DEFAULT NULL",
    "CREATE INDEX IF NOT EXISTS idx_documents_archived_at ON documents(archived_at DESC)",
    "INSERT INTO documents_fts(documents_fts) VALUES('rebuild')",
    "ALTER TABLE documents ADD COLUMN confidence TEXT DEFAULT NULL",
    "ALTER TABLE documents ADD COLUMN iban TEXT DEFAULT NULL",
]

def init_db():
    import db
    from db.sender_repo import init_sender_table
    from db.feedback_repo import init_feedback_table
    os.makedirs(os.path.dirname(db.DB_PATH) if os.path.dirname(db.DB_PATH) else ".", exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # Run additive migrations (safe to re-run – ignore 'duplicate column' errors)
        for migration in MIGRATIONS:
            try:
                conn.execute(migration)
            except Exception:
                pass
    init_sender_table()
    init_feedback_table()
    from db.collections_repo import init_collections_table
    init_collections_table()
    from db.items_repo import init_items_table
    init_items_table()
    from db.contracts_repo import init_contracts_table
    init_contracts_table()
    from db.services_repo import init_services_table
    init_services_table()
