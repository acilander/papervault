import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import db
from db.connection import get_conn


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    yield


def test_init_db_creates_documents_table():
    db.init_db()
    with get_conn() as conn:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents'").fetchall()
        assert tables


def test_init_db_creates_fts_virtual_table():
    db.init_db()
    with get_conn() as conn:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents_fts'").fetchall()
        assert tables


def test_init_db_creates_sender_and_feedback_tables():
    db.init_db()
    with get_conn() as conn:
        tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "senders" in tables
        assert "feedback" in tables
        assert "collections" in tables
        assert "collection_documents" in tables


def test_init_db_is_idempotent():
    db.init_db()
    db.init_db()
    db.init_db()
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0


def test_migrations_are_idempotent():
    db.init_db()
    # Re-running init should not fail even after migrations have been applied
    db.init_db()
    with get_conn() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)")}
        assert "tags" in cols
        assert "tax_relevant" in cols
        assert "keywords" in cols
        assert "low_value" in cols
        assert "sim_hash" in cols


def test_fts_triggers_maintain_index():
    db.init_db()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO documents (file_path, filename, sender, date, document_type, category, summary, status, archived_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            ("/a/b.pdf", "b.pdf", "X", "2024-01-01", "Rechnung", "Sonstiges", "Test summary", "ok")
        )
        conn.commit()
        rows = conn.execute("SELECT * FROM documents_fts WHERE documents_fts MATCH ?", ("Test",)).fetchall()
        assert len(rows) == 1


def test_fts_trigger_updates_on_delete():
    db.init_db()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO documents (file_path, filename, sender, summary, status, archived_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            ("/a/b.pdf", "b.pdf", "X", "uniquekeyword", "ok")
        )
        conn.commit()
        rows_before = conn.execute("SELECT * FROM documents_fts WHERE documents_fts MATCH ?", ('"uniquekeyword"',)).fetchall()
        assert len(rows_before) == 1
        conn.execute("DELETE FROM documents WHERE file_path=?", ("/a/b.pdf",))
        conn.commit()
        rows_after = conn.execute("SELECT * FROM documents_fts WHERE documents_fts MATCH ?", ('"uniquekeyword"',)).fetchall()
        assert rows_after == []
