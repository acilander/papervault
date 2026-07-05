import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import db
from db import collections_repo as cr
from db.connection import get_conn


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield


def _make_doc(**overrides):
    fp = overrides.pop("file_path", "/archive/test.pdf")
    data = dict(
        file_path=fp,
        filename=os.path.basename(fp),
        sender="Testbank",
        date="2024-01-15",
        document_type="Kontoauszug",
        category="Bank & Finanzen",
        summary="Test",
        status="ok",
    )
    data.update(overrides)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO documents (file_path, filename, sender, date, document_type, category, summary, status, archived_at) "
            "VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
            (data["file_path"], data["filename"], data["sender"], data["date"],
             data["document_type"], data["category"], data["summary"], data["status"])
        )
        return cur.lastrowid


def test_create_collection_returns_id():
    cid = cr.create_collection("Steuer 2024")
    assert isinstance(cid, int) and cid > 0


def test_get_collection_basic():
    cid = cr.create_collection("Steuer 2024", description="Doku", color="#ef4444")
    col = cr.get_collection(cid)
    assert col["name"] == "Steuer 2024"
    assert col["description"] == "Doku"
    assert col["color"] == "#ef4444"
    assert col["documents"] == []


def test_get_collection_nonexistent():
    assert cr.get_collection(99999) is None


def test_get_all_collections_empty():
    assert cr.get_all_collections() == []


def test_get_all_collections_count():
    cr.create_collection("A")
    cr.create_collection("B")
    assert len(cr.get_all_collections()) == 2


def test_get_all_collections_includes_doc_count():
    cid = cr.create_collection("With Docs")
    doc_id = _make_doc()
    cr.add_document(cid, doc_id)
    col = next(c for c in cr.get_all_collections() if c["id"] == cid)
    assert col["doc_count"] == 1


def test_update_collection_name():
    cid = cr.create_collection("Old")
    cr.update_collection(cid, name="New")
    assert cr.get_collection(cid)["name"] == "New"


def test_update_collection_noop_on_empty():
    cid = cr.create_collection("Stable")
    cr.update_collection(cid)
    assert cr.get_collection(cid)["name"] == "Stable"


def test_delete_collection():
    cid = cr.create_collection("Gone")
    cr.delete_collection(cid)
    assert cr.get_collection(cid) is None


def test_add_document_to_collection():
    cid = cr.create_collection("C")
    doc_id = _make_doc()
    cr.add_document(cid, doc_id)
    assert len(cr.get_collection(cid)["documents"]) == 1


def test_add_document_idempotent():
    cid = cr.create_collection("C")
    doc_id = _make_doc()
    cr.add_document(cid, doc_id)
    cr.add_document(cid, doc_id)
    assert len(cr.get_collection(cid)["documents"]) == 1


def test_remove_document_from_collection():
    cid = cr.create_collection("C")
    doc_id = _make_doc()
    cr.add_document(cid, doc_id)
    cr.remove_document(cid, doc_id)
    assert cr.get_collection(cid)["documents"] == []


def test_get_collections_for_document():
    cid1 = cr.create_collection("C1")
    cid2 = cr.create_collection("C2")
    doc_id = _make_doc()
    cr.add_document(cid1, doc_id)
    cr.add_document(cid2, doc_id)
    result = cr.get_collections_for_document(doc_id)
    assert {c["id"] for c in result} == {cid1, cid2}


def test_delete_collection_cascades_memberships():
    cid = cr.create_collection("C")
    doc_id = _make_doc()
    cr.add_document(cid, doc_id)
    cr.delete_collection(cid)
    assert cr.get_collections_for_document(doc_id) == []
