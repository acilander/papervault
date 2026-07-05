"""Tests for /monitor endpoints."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from fastapi.testclient import TestClient

import db
import config
from api.main import app


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

    from api.routes import monitor as monitor_module
    monkeypatch.setattr(monitor_module, "TARGET_BASE", target_dir)
    monkeypatch.setattr(monitor_module, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(monitor_module, "LOG_FILE", os.path.join(target_dir, "processing_log.jsonl"))
    monkeypatch.setattr(monitor_module, "ARCHIVER_STDOUT", os.path.join(target_dir, "archiver.log"))

    # Recreate client against fresh app modules to pick up patched paths
    import api.main as main_mod
    main_mod.app.dependency_overrides = {}
    global client
    client = TestClient(main_mod.app)
    yield


client = TestClient(app)


def _insert_pdf(tmp_path, name="doc.pdf", sender="Test", category="Sonstiges", status="ok", date="2024-01-15", path=None, content_hash=None, sim_hash=None):
    if path is None:
        path = tmp_path / "Archive" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF")
    doc_id = db.upsert_document(
        file_path=str(path), filename=name, sender=sender, date=date,
        document_type="Rechnung", category=category, summary="Test", status=status
    )
    updates = {}
    if content_hash is not None:
        updates["content_hash"] = content_hash
    if sim_hash is not None:
        updates["sim_hash"] = sim_hash
    if updates:
        from db.connection import get_conn
        with get_conn() as conn:
            for k, v in updates.items():
                conn.execute(f"UPDATE documents SET {k}=? WHERE id=?", (v, doc_id))
    return doc_id, str(path)


def test_buffer_returns_lines(tmp_path):
    log = tmp_path / "Archive" / "archiver.log"
    log.write_text("line1\nline2\n", encoding="utf-8")
    resp = client.get("/monitor/buffer")
    assert resp.status_code == 200
    assert len(resp.json()["lines"]) == 2


def test_inbox_preview(tmp_path):
    inbox = tmp_path / "Inbox"
    (inbox / "scan.pdf").write_bytes(b"%PDF")
    (inbox / "skip.txt").write_bytes(b"text")
    resp = client.get("/monitor/inbox")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["files"]) == 1


def test_find_duplicates_hash(tmp_path):
    _insert_pdf(tmp_path, name="a.pdf", content_hash="same", path=tmp_path / "Archive" / "a.pdf")
    _insert_pdf(tmp_path, name="b.pdf", content_hash="same", path=tmp_path / "Archive" / "b.pdf")
    resp = client.get("/monitor/duplicates")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


def test_validation_report_inconsistent_category(tmp_path):
    _insert_pdf(tmp_path, name="jan.pdf", sender="Telekom", category="Kommunikation", date="2024-01-15")
    _insert_pdf(tmp_path, name="feb.pdf", sender="Telekom", category="Sonstiges", date="2024-02-15")
    resp = client.get("/monitor/validation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_groups"] >= 1
    assert any(i["type"] == "inconsistent_category" for g in data["groups"] for i in g["issues"])


def test_generate_thumbnails(tmp_path, monkeypatch):
    import pdf_utils
    doc_id, path = _insert_pdf(tmp_path, name="thumb.pdf")
    monkeypatch.setattr(pdf_utils, "generate_thumbnail", lambda p, _id: p)
    monkeypatch.setattr(pdf_utils, "get_thumbnail_path", lambda _id: path)
    resp = client.post("/monitor/generate-thumbnails")
    assert resp.status_code == 200
    data = resp.json()
    assert data["generated"] + data["skipped"] >= 1


def test_scan_missing_and_repair_and_delete(tmp_path):
    doc_id, path = _insert_pdf(tmp_path, name="missing.pdf")
    os.remove(path)
    resp = client.post("/monitor/scan-missing")
    assert resp.status_code == 200
    assert resp.json()["missing_found"] == 1
    assert db.get_document(doc_id)["status"] == "missing"

    # repair: place file back in target
    new_path = tmp_path / "Archive" / "missing.pdf"
    new_path.write_bytes(b"%PDF")
    resp = client.post("/monitor/repair-missing")
    assert resp.status_code == 200
    assert resp.json()["repaired"] == 1
    assert db.get_document(doc_id)["status"] == "ok"

    # mark missing again and delete
    db.update_document(doc_id, status="missing")
    resp = client.delete("/monitor/missing")
    assert resp.status_code == 200
    assert db.get_document(doc_id) is None


def test_orphans_and_import(tmp_path):
    orphan_dir = tmp_path / "Archive" / "Sonstiges"
    orphan_dir.mkdir(parents=True, exist_ok=True)
    orphan = orphan_dir / "orphan.pdf"
    orphan.write_bytes(b"%PDF")
    resp = client.get("/monitor/orphans")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1

    resp = client.post("/monitor/orphans/import", json={"paths": [str(orphan)]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 1
    assert not os.path.exists(str(orphan))
