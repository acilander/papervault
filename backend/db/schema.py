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
    confidence    TEXT DEFAULT NULL,
    verified      INTEGER DEFAULT 0,
    file_size_bytes INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cleanup_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL,
    filename    TEXT NOT NULL,
    bytes_saved INTEGER NOT NULL,
    executed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS low_value_rule_executions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id     INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    old_value   INTEGER NOT NULL,
    new_value   INTEGER NOT NULL,
    applied_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS system_incidents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_type TEXT NOT NULL,
    file_path   TEXT,
    message     TEXT NOT NULL,
    resolved    INTEGER DEFAULT 0,
    logged_at   TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS tax_years (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    year        INTEGER NOT NULL UNIQUE,
    status      TEXT DEFAULT 'draft',
    notes       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tax_documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tax_year_id     INTEGER NOT NULL,
    document_id     INTEGER NOT NULL,
    source_type     TEXT NOT NULL,
    parsed_at       TEXT,
    verified        INTEGER DEFAULT 0,
    FOREIGN KEY (tax_year_id) REFERENCES tax_years(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    UNIQUE(tax_year_id, document_id, source_type)
);

CREATE INDEX IF NOT EXISTS idx_tax_documents_year ON tax_documents(tax_year_id);
CREATE INDEX IF NOT EXISTS idx_tax_documents_document ON tax_documents(document_id);

CREATE TABLE IF NOT EXISTS tax_positions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    tax_year_id         INTEGER NOT NULL,
    tax_document_id     INTEGER NOT NULL,
    category            TEXT NOT NULL,
    subcategory         TEXT,
    label               TEXT NOT NULL,
    amount              REAL,
    amount_assessed     REAL,
    page                INTEGER,
    verified            INTEGER DEFAULT 0,
    source_text         TEXT,
    created_at          TEXT NOT NULL,
    FOREIGN KEY (tax_year_id) REFERENCES tax_years(id) ON DELETE CASCADE,
    FOREIGN KEY (tax_document_id) REFERENCES tax_documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tax_positions_year ON tax_positions(tax_year_id);
CREATE INDEX IF NOT EXISTS idx_tax_positions_document ON tax_positions(tax_document_id);
CREATE INDEX IF NOT EXISTS idx_tax_positions_category ON tax_positions(category);

CREATE TABLE IF NOT EXISTS document_embeddings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL UNIQUE,
    embedding    BLOB NOT NULL,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_embeddings_document ON document_embeddings(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_verified ON documents(verified);
CREATE INDEX IF NOT EXISTS idx_documents_confidence ON documents(confidence);
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
    """
    CREATE TABLE IF NOT EXISTS protected_document_hashes (
        hash         TEXT PRIMARY KEY,
        type         TEXT NOT NULL CHECK(type IN ('ignored', 'locked')),
        document_id  INTEGER,
        filename     TEXT,
        created_at   TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_protected_hashes_type ON protected_document_hashes(type)",
    "ALTER TABLE documents ADD COLUMN property_unit TEXT DEFAULT NULL",
    "CREATE INDEX IF NOT EXISTS idx_documents_property_unit ON documents(property_unit)",
    "ALTER TABLE documents ADD COLUMN vehicle_id TEXT DEFAULT NULL",
    "CREATE INDEX IF NOT EXISTS idx_documents_vehicle_id ON documents(vehicle_id)",
    "ALTER TABLE documents ADD COLUMN child_name TEXT DEFAULT NULL",
    "CREATE INDEX IF NOT EXISTS idx_documents_child_name ON documents(child_name)",
    """
    CREATE TABLE IF NOT EXISTS document_embeddings (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id  INTEGER NOT NULL UNIQUE,
        embedding    BLOB NOT NULL,
        created_at   TEXT NOT NULL,
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_embeddings_document ON document_embeddings(document_id)",
    "ALTER TABLE contracts ADD COLUMN source_text TEXT DEFAULT NULL",
    "ALTER TABLE contracts ADD COLUMN source_page INTEGER DEFAULT NULL",
    "ALTER TABLE items ADD COLUMN source_text TEXT DEFAULT NULL",
    "ALTER TABLE items ADD COLUMN source_page INTEGER DEFAULT NULL",
    "ALTER TABLE services ADD COLUMN source_text TEXT DEFAULT NULL",
    "ALTER TABLE services ADD COLUMN source_page INTEGER DEFAULT NULL",
    "ALTER TABLE documents ADD COLUMN verified INTEGER DEFAULT 0",
    "CREATE INDEX IF NOT EXISTS idx_documents_verified ON documents(verified)",
    "CREATE INDEX IF NOT EXISTS idx_documents_confidence ON documents(confidence)",
    "ALTER TABLE documents ADD COLUMN file_size_bytes INTEGER DEFAULT 0",
]

def init_db():
    import db
    import sqlite3
    from db.sender_repo import init_sender_table
    from db.feedback_repo import init_feedback_table
    os.makedirs(os.path.dirname(db.DB_PATH) if os.path.dirname(db.DB_PATH) else ".", exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # Run additive migrations (safe to re-run – ignore 'duplicate column' errors)
        for migration in MIGRATIONS:
            try:
                conn.execute(migration)
            except sqlite3.OperationalError as e:
                err_msg = str(e).lower()
                if "duplicate column name" in err_msg or "already exists" in err_msg or "no such table" in err_msg:
                    continue
                from utils import log as _log_err
                _log_err(f"SCHWERER FEHLER: Migration fehlgeschlagen: '{migration}' | Fehler: {e}")
                raise
            except Exception as e:
                from utils import log as _log_err
                _log_err(f"SCHWERER FEHLER: Unerwarteter Migrationsfehler: '{migration}' | Fehler: {e}")
                raise
    init_sender_table()
    init_feedback_table()
    from db.embeddings_repo import init_embeddings_table
    init_embeddings_table()
    from db.collections_repo import init_collections_table
    init_collections_table()
    from db.items_repo import init_items_table
    init_items_table()
    from db.contracts_repo import init_contracts_table
    init_contracts_table()
    from db.services_repo import init_services_table
    init_services_table()
    from db.protected_hashes_repo import init_protected_hashes_table
    init_protected_hashes_table()
    from db.low_value_rules_repo import init_low_value_rules_table
    init_low_value_rules_table()
    from db.tax_years_repo import init_tax_years_table
    init_tax_years_table()
    from db.tax_documents_repo import init_tax_documents_table
    init_tax_documents_table()
    from db.tax_positions_repo import init_tax_positions_table
    init_tax_positions_table()
