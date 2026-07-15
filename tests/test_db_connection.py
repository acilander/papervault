import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import threading
import pytest
import sqlite3

import db
from db.connection import get_conn, _connect


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    # clear thread-local state so each test starts fresh
    _local = getattr(db.connection, "_local", None)
    if _local:
        for attr in ("conn", "db_path"):
            if hasattr(_local, attr):
                delattr(_local, attr)
    yield


def test_connection_is_sqlite():
    with get_conn() as conn:
        assert isinstance(conn, sqlite3.Connection)


def test_wal_mode_enabled():
    with get_conn() as conn:
        row = conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0].lower() == "wal"


def test_foreign_keys_enabled():
    with get_conn() as conn:
        row = conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1


def test_connection_reused_in_same_thread():
    with get_conn() as conn1:
        with get_conn() as conn2:
            assert conn1 is conn2


def test_new_connection_when_db_path_changes(monkeypatch, tmp_path):
    with get_conn() as conn1:
        pass
    new_db = str(tmp_path / "other.db")
    monkeypatch.setattr(db, "DB_PATH", new_db)
    db.init_db()
    with get_conn() as conn2:
        assert conn2 is not conn1


def test_connection_rollback_on_exception():
    with get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS temp_rollback(x TEXT)")
    with pytest.raises(RuntimeError):
        with get_conn() as conn:
            conn.execute("INSERT INTO temp_rollback VALUES ('should-be-rolled-back')")
            raise RuntimeError("boom")
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM temp_rollback").fetchall()
        assert rows == []


def test_connection_is_thread_local():
    conns = []

    def worker():
        with get_conn() as conn:
            conns.append(conn)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(conns) == 2
    assert conns[0] is not conns[1]


def test_transaction_nesting_depth_commit():
    """Verify nested transactions only commit on outermost exit."""
    with get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS test_nesting(x TEXT)")

    with get_conn() as conn1:
        conn1.execute("INSERT INTO test_nesting VALUES ('outer-start')")
        with get_conn() as conn2:
            conn2.execute("INSERT INTO test_nesting VALUES ('inner-val')")
        # Since outer is not exited, we shouldn't commit if inner had its own commit logic,
        # but with depth counter both are committed only when outer exits.

    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM test_nesting").fetchall()
        assert len(rows) == 2


def test_transaction_nesting_depth_rollback():
    """Verify nested transactions rollback completely on exception in inner block."""
    with get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS test_nesting_rollback(x TEXT)")

    with pytest.raises(RuntimeError):
        with get_conn() as conn1:
            conn1.execute("INSERT INTO test_nesting_rollback VALUES ('outer-val')")
            with get_conn() as conn2:
                conn2.execute("INSERT INTO test_nesting_rollback VALUES ('inner-val')")
                raise RuntimeError("inner boom")

    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM test_nesting_rollback").fetchall()
        assert len(rows) == 0


def test_claim_document_status():
    """Verify atomic state transitions via claim_document_status."""
    from db.documents_repo import upsert_document, get_document, claim_document_status
    doc_id = upsert_document("C:/temp/test.pdf", "test.pdf", "Sender", "2025-01-01", "Rechnung", "Sonstiges", "Summary", status="review")

    # Successful transition
    success = claim_document_status(doc_id, "review", "processing")
    assert success is True
    doc = get_document(doc_id)
    assert doc["status"] == "processing"

    # Unsuccessful transition (wrong old_status)
    fail = claim_document_status(doc_id, "review", "ok")
    assert fail is False
    doc = get_document(doc_id)
    assert doc["status"] == "processing"
