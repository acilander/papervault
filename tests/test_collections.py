"""Tests for collections_repo.py — CRUD, membership, cascade delete, ZIP export."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import zipfile
import pytest
import db
from db import collections_repo as cr
from db.connection import get_conn
import db.documents_repo as doc_repo
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    """Each test gets a fresh in-memory SQLite via a temp file."""
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield


def _make_doc(**overrides):
    """Insert a minimal document and return its id."""
    n = overrides.pop('n', 1)
    fp = overrides.pop('file_path', f"/archive/test_{n}.pdf")
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
            "INSERT INTO documents (file_path, filename, sender, date, document_type, "
            "category, summary, status, archived_at) VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
            (data['file_path'], data['filename'], data['sender'], data['date'],
             data['document_type'], data['category'], data['summary'], data['status'])
        )
        return cur.lastrowid


# ── Collection CRUD ──────────────────────────────────────────────────────────

def test_create_collection_returns_id():
    cid = cr.create_collection("Hauskauf 2022")
    assert isinstance(cid, int)
    assert cid > 0


def test_get_collection_basic():
    cid = cr.create_collection("Steuer 2023", description="Alle Steuerunterlagen", color="#ef4444")
    col = cr.get_collection(cid)
    assert col is not None
    assert col["name"] == "Steuer 2023"
    assert col["description"] == "Alle Steuerunterlagen"
    assert col["color"] == "#ef4444"
    assert col["documents"] == []


def test_get_collection_nonexistent_returns_none():
    assert cr.get_collection(99999) is None


def test_get_all_collections_empty():
    assert cr.get_all_collections() == []


def test_get_all_collections_lists_all():
    cr.create_collection("A")
    cr.create_collection("B")
    cr.create_collection("C")
    result = cr.get_all_collections()
    assert len(result) == 3
    names = {c["name"] for c in result}
    assert names == {"A", "B", "C"}


def test_get_all_collections_includes_doc_count():
    cid = cr.create_collection("With Docs")
    doc_id = _make_doc(n=1)
    cr.add_document(cid, doc_id)
    cols = cr.get_all_collections()
    target = next(c for c in cols if c["id"] == cid)
    assert target["doc_count"] == 1


def test_update_collection_name():
    cid = cr.create_collection("Old Name")
    cr.update_collection(cid, name="New Name")
    col = cr.get_collection(cid)
    assert col["name"] == "New Name"


def test_update_collection_color():
    cid = cr.create_collection("Colored")
    cr.update_collection(cid, color="#10b981")
    col = cr.get_collection(cid)
    assert col["color"] == "#10b981"


def test_update_collection_noop_on_empty_fields():
    cid = cr.create_collection("Stable")
    cr.update_collection(cid)
    assert cr.get_collection(cid)["name"] == "Stable"


def test_delete_collection():
    cid = cr.create_collection("To Delete")
    cr.delete_collection(cid)
    assert cr.get_collection(cid) is None


def test_delete_collection_removes_from_list():
    cid = cr.create_collection("Gone")
    cr.delete_collection(cid)
    assert all(c["id"] != cid for c in cr.get_all_collections())


# ── Document membership ───────────────────────────────────────────────────────

def test_add_document_to_collection():
    cid = cr.create_collection("Mixed")
    doc_id = _make_doc(n=1)
    cr.add_document(cid, doc_id)
    col = cr.get_collection(cid)
    assert len(col["documents"]) == 1
    assert col["documents"][0]["id"] == doc_id


def test_add_document_idempotent():
    cid = cr.create_collection("Idempotent")
    doc_id = _make_doc(n=1)
    cr.add_document(cid, doc_id)
    cr.add_document(cid, doc_id)
    col = cr.get_collection(cid)
    assert len(col["documents"]) == 1


def test_add_multiple_documents():
    cid = cr.create_collection("Multi")
    ids = [_make_doc(n=i, file_path=f"/archive/doc{i}.pdf") for i in range(3)]
    for did in ids:
        cr.add_document(cid, did)
    col = cr.get_collection(cid)
    assert len(col["documents"]) == 3


def test_remove_document_from_collection():
    cid = cr.create_collection("Removable")
    doc_id = _make_doc(n=1)
    cr.add_document(cid, doc_id)
    cr.remove_document(cid, doc_id)
    col = cr.get_collection(cid)
    assert len(col["documents"]) == 0


def test_remove_nonexistent_document_is_noop():
    cid = cr.create_collection("Safe")
    cr.remove_document(cid, 99999)
    assert cr.get_collection(cid)["documents"] == []


def test_get_collections_for_document():
    cid1 = cr.create_collection("Col1")
    cid2 = cr.create_collection("Col2")
    doc_id = _make_doc(n=1)
    cr.add_document(cid1, doc_id)
    cr.add_document(cid2, doc_id)
    result = cr.get_collections_for_document(doc_id)
    assert len(result) == 2
    ids = {c["id"] for c in result}
    assert ids == {cid1, cid2}


def test_get_collections_for_document_not_in_any():
    doc_id = _make_doc(n=1)
    assert cr.get_collections_for_document(doc_id) == []


# ── Cascade delete ────────────────────────────────────────────────────────────

def test_deleting_collection_removes_memberships():
    cid = cr.create_collection("Cascade")
    doc_id = _make_doc(n=1)
    cr.add_document(cid, doc_id)
    cr.delete_collection(cid)
    assert cr.get_collections_for_document(doc_id) == []


def test_document_in_multiple_collections_partial_delete():
    cid1 = cr.create_collection("Keep")
    cid2 = cr.create_collection("Del")
    doc_id = _make_doc(n=1)
    cr.add_document(cid1, doc_id)
    cr.add_document(cid2, doc_id)
    cr.delete_collection(cid2)
    result = cr.get_collections_for_document(doc_id)
    assert len(result) == 1
    assert result[0]["id"] == cid1


# ── GET /collections/{id}/export/zip ─────────────────────────────────────────

class TestCollectionZipExport:

    def test_unknown_collection_returns_404(self):
        resp = client.get("/collections/99999/export/zip")
        assert resp.status_code == 404

    def test_empty_collection_returns_404(self):
        cid = cr.create_collection("Leer")
        resp = client.get(f"/collections/{cid}/export/zip")
        assert resp.status_code == 404

    def test_collection_with_missing_files_returns_404(self, tmp_path):
        cid = cr.create_collection("Fehlende Dateien")
        doc_id = _make_doc(n=1, file_path="/nonexistent/doc.pdf")
        cr.add_document(cid, doc_id)
        resp = client.get(f"/collections/{cid}/export/zip")
        assert resp.status_code == 404

    def test_valid_collection_returns_zip(self, tmp_path):
        pdf = tmp_path / "testdoc.pdf"
        pdf.write_bytes(b"%PDF-1.4 test")
        cid = cr.create_collection("Meine Sammlung")
        doc_id = _make_doc(n=1, file_path=str(pdf))
        cr.add_document(cid, doc_id)
        resp = client.get(f"/collections/{cid}/export/zip")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"

    def test_zip_contains_pdf_file(self, tmp_path):
        pdf = tmp_path / "meinpdf.pdf"
        pdf.write_bytes(b"%PDF-1.4 content")
        cid = cr.create_collection("Mit PDF")
        doc_id = _make_doc(n=1, file_path=str(pdf))
        cr.add_document(cid, doc_id)
        resp = client.get(f"/collections/{cid}/export/zip")
        assert resp.status_code == 200
        buf = __import__("io").BytesIO(resp.content)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
        assert "meinpdf.pdf" in names

    def test_content_disposition_contains_collection_name(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF")
        cid = cr.create_collection("Steuer 2024")
        doc_id = _make_doc(n=1, file_path=str(pdf))
        cr.add_document(cid, doc_id)
        resp = client.get(f"/collections/{cid}/export/zip")
        assert resp.status_code == 200
        disposition = resp.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert "Steuer 2024" in disposition

    def test_duplicate_filenames_renamed(self, tmp_path):
        pdf1 = tmp_path / "doc.pdf"
        pdf2 = tmp_path / "sub" / "doc.pdf"
        pdf2.parent.mkdir()
        pdf1.write_bytes(b"%PDF-1")
        pdf2.write_bytes(b"%PDF-2")
        cid = cr.create_collection("Doppelt")
        doc_id1 = _make_doc(n=1, file_path=str(pdf1))
        doc_id2 = _make_doc(n=2, file_path=str(pdf2))
        cr.add_document(cid, doc_id1)
        cr.add_document(cid, doc_id2)
        resp = client.get(f"/collections/{cid}/export/zip")
        assert resp.status_code == 200
        buf = __import__("io").BytesIO(resp.content)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
        assert len(names) == len(set(names)), "Duplicate filenames in ZIP"

    def test_special_chars_in_collection_name_sanitized(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF")
        cid = cr.create_collection("Rechnungen/2024 & Co.")
        doc_id = _make_doc(n=1, file_path=str(pdf))
        cr.add_document(cid, doc_id)
        resp = client.get(f"/collections/{cid}/export/zip")
        assert resp.status_code == 200
        disposition = resp.headers.get("content-disposition", "")
        assert "/" not in disposition.split("filename=")[-1]

    def test_smart_collection_dynamic_view(self):
        _make_doc(n=1, sender="Allianz", category="Privatversicherungen", document_type="Police")
        _make_doc(n=2, sender="Allianz", category="Fahrzeug", document_type="Rechnung")
        _make_doc(n=3, sender="Telekom", category="Bank & Finanzen", document_type="Kontoauszug")

        import json
        criteria = json.dumps({"sender": "Allianz"})
        cid = cr.create_collection("Allianz Smart", query_criteria=criteria)

        col = cr.get_collection(cid)
        assert len(col["documents"]) == 2
        names = {d["filename"] for d in col["documents"]}
        assert "test_1.pdf" in names
        assert "test_2.pdf" in names
        assert "test_3.pdf" not in names
