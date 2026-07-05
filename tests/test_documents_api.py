"""Tests for /documents/* endpoints not covered by bulk-update/csv tests."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from fastapi.testclient import TestClient

import db
import config
import storage
from api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.DB_PATH = test_db
    db.init_db()

    source_dir = str(tmp_path / "Inbox")
    target_dir = str(tmp_path / "Archive")
    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(target_dir, exist_ok=True)
    monkeypatch.setattr(config, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(config, "TARGET_BASE", target_dir)
    monkeypatch.setattr(config, "SENDER_SUBFOLDERS", False)
    monkeypatch.setattr(config, "CATEGORY_FOLDER_MAP", {"Sonstiges": "14 - Sonstiges"})

    storage.sender_registry = {}
    yield


def _insert_pdf(tmp_path, name="doc.pdf", sender="Test", category="Sonstiges", status="ok", date="2024-01-15"):
    path = tmp_path / name
    path.write_bytes(b"%PDF")
    doc_id = db.upsert_document(
        file_path=str(path), filename=name, sender=sender, date=date,
        document_type="Rechnung", category=category, summary="Test", status=status
    )
    return doc_id, str(path)


def test_list_documents_with_filters(tmp_path):
    _insert_pdf(tmp_path, "a.pdf", sender="Bank", category="Bank & Finanzen")
    _insert_pdf(tmp_path, "b.pdf", sender="Telekom", category="Kommunikation")

    resp = client.get("/documents/")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = client.get("/documents/?sender=Bank")
    assert len(resp.json()) == 1

    resp = client.get("/documents/?year=2024")
    assert len(resp.json()) == 2


def test_get_document_by_id(tmp_path):
    doc_id, _ = _insert_pdf(tmp_path)
    resp = client.get(f"/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["filename"] == "doc.pdf"

    resp = client.get("/documents/9999")
    assert resp.status_code == 404


def test_update_document_and_pinned_category(tmp_path):
    import db.sender_repo as sender_repo
    sender_repo.upsert("Bank", {"categories": ["Bank & Finanzen"], "pinned_category": "Bank & Finanzen", "excluded_categories": [], "reviewed": False})
    storage._refresh_cache()
    doc_id, _ = _insert_pdf(tmp_path, sender="Bank", category="Sonstiges")

    resp = client.patch(f"/documents/{doc_id}", json={"sender": "Bank", "category": "Bank & Finanzen"})
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["category"] == "Bank & Finanzen"

    resp = client.patch("/documents/9999", json={"category": "Sonstiges"})
    assert resp.status_code == 404


def test_delete_document(tmp_path):
    doc_id, _ = _insert_pdf(tmp_path)
    resp = client.delete(f"/documents/{doc_id}")
    assert resp.status_code == 204
    assert db.get_document(doc_id) is None

    resp = client.delete("/documents/9999")
    assert resp.status_code == 404


def test_serve_pdf_and_missing(tmp_path):
    doc_id, path = _insert_pdf(tmp_path)
    resp = client.get(f"/documents/{doc_id}/file")
    assert resp.status_code == 200

    os.remove(path)
    resp = client.get(f"/documents/{doc_id}/file")
    assert resp.status_code == 404


def test_thumbnail_endpoint(tmp_path, monkeypatch):
    doc_id, path = _insert_pdf(tmp_path)
    from api.routes import documents as doc_module
    thumb_path = tmp_path / f"thumb_{doc_id}.webp"
    thumb_path.write_bytes(b"webp")
    monkeypatch.setattr(doc_module, "get_thumbnail_path", lambda _id: str(thumb_path))
    monkeypatch.setattr(doc_module, "generate_thumbnail", lambda _path, _id: str(thumb_path))
    resp = client.get(f"/documents/{doc_id}/thumbnail")
    assert resp.status_code == 200


def test_open_in_explorer(tmp_path, monkeypatch):
    import subprocess
    doc_id, path = _insert_pdf(tmp_path)
    monkeypatch.setattr(subprocess, "Popen", lambda args: None)
    resp = client.post(f"/documents/{doc_id}/open")
    assert resp.status_code == 204

    os.remove(path)
    resp = client.post(f"/documents/{doc_id}/open")
    assert resp.status_code == 404


def test_rename_document(tmp_path):
    doc_id, path = _insert_pdf(tmp_path, name="old.pdf")
    resp = client.post(f"/documents/{doc_id}/rename", json={"filename": "new.pdf"})
    assert resp.status_code == 200
    assert resp.json()["filename"] == "new.pdf"
    assert os.path.exists(str(tmp_path / "new.pdf"))

    resp = client.post(f"/documents/{doc_id}/rename", json={"filename": ""})
    assert resp.status_code == 400


def test_original_for_duplicate(tmp_path):
    doc_id, _ = _insert_pdf(tmp_path, name="orig.pdf", status="ok")
    db.update_document(doc_id, content_hash="hash123")
    dup_id, _ = _insert_pdf(tmp_path, name="dup.pdf", status="duplicate")
    db.update_document(dup_id, content_hash="hash123")
    original = db.get_document_by_hash("hash123")
    assert original is not None

    resp = client.get(f"/documents/{dup_id}/original")
    assert resp.status_code == 200
    assert resp.json()["id"] == doc_id

    resp = client.get(f"/documents/{doc_id}/original")
    assert resp.status_code == 400


def test_reprocess_document(tmp_path, monkeypatch):
    doc_id, path = _insert_pdf(tmp_path, name="review.pdf", status="review")
    resp = client.post(f"/documents/{doc_id}/reprocess", json={"hint": "Rechnung"})
    assert resp.status_code == 202
    data = resp.json()
    assert "Inbox" in data["file_path"]

    os.remove(data["file_path"])
    resp = client.post(f"/documents/{doc_id}/reprocess")
    assert resp.status_code == 404


def test_confirm_review_document(tmp_path, monkeypatch):
    from pipeline import steps
    import config as cfg
    cfg.CATEGORY_FOLDER_MAP = {"Sonstiges": "14 - Sonstiges"}
    doc_id, path = _insert_pdf(tmp_path, name="review.pdf", status="review", category="Sonstiges")
    resp = client.post(f"/documents/{doc_id}/confirm")
    assert resp.status_code == 200
    data = resp.json()
    assert data["detail"]
    assert db.get_document(doc_id)["status"] == "ok"

    resp = client.post(f"/documents/{doc_id}/confirm")
    assert resp.status_code == 400


def test_delete_document_with_file(tmp_path):
    doc_id, path = _insert_pdf(tmp_path)
    resp = client.delete(f"/documents/{doc_id}/delete-file")
    assert resp.status_code == 204
    assert db.get_document(doc_id) is None
    assert not os.path.exists(path)

    resp = client.delete("/documents/9999/delete-file")
    assert resp.status_code == 404


def test_tax_export(tmp_path):
    doc_id, path = _insert_pdf(tmp_path, name="tax.pdf", category="Bank & Finanzen")
    db.update_document(doc_id, tax_relevant=1, tax_year="2024")
    resp = client.get("/documents/tax-export?year=2024")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

    resp = client.get("/documents/tax-export?year=2099")
    assert resp.status_code == 404


def test_expiring_documents(tmp_path):
    from datetime import datetime, timedelta
    doc_id, path = _insert_pdf(tmp_path)
    future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    db.update_document(doc_id, expires_at=future)
    resp = client.get("/documents/expiring?days=365")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
