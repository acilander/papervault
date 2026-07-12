import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import config
import db
import storage


@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch, tmp_path):
    """Redirect DB_PATH and SOURCE_DIR to temp paths for each test."""
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr("db.DB_PATH", test_db)
    db.DB_PATH = test_db
    db.init_db()

    source_dir = str(tmp_path / "Inbox")
    target_dir = str(tmp_path / "Archive")
    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(target_dir, exist_ok=True)

    monkeypatch.setattr(config, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(config, "TARGET_BASE", target_dir)

    # Start with an empty sender registry
    storage.sender_registry = {}

    yield tmp_path


def test_rebuild_senders_populates_registry_from_documents(in_memory_db):
    """Verify that POST /senders/~rebuild populates the sender registry from documents."""
    from fastapi.testclient import TestClient
    from api.main import app

    # Insert documents with different senders
    db.upsert_document(
        file_path="/tmp/telekom.pdf",
        filename="telekom.pdf",
        sender="Telekom",
        date="2026-01-15",
        document_type="Rechnung",
        category="Kommunikation",
        summary="Telekom Rechnung",
        status="ok",
    )
    db.upsert_document(
        file_path="/tmp/aok.pdf",
        filename="aok.pdf",
        sender="AOK Baden-Württemberg",
        date="2026-01-15",
        document_type="Bescheid",
        category="Gesundheit",
        summary="AOK Beitragsbescheid",
        status="review",
    )
    db.upsert_document(
        file_path="/tmp/no_sender.pdf",
        filename="no_sender.pdf",
        sender=None,
        date="2026-01-15",
        document_type="Sonstiges",
        category="Sonstiges",
        summary="Dokument ohne Absender",
        status="ok",
    )

    client = TestClient(app)
    response = client.post("/senders/~rebuild")
    assert response.status_code == 200
    data = response.json()
    assert data["rebuilt"] is True
    assert data["count"] == 2
    assert data["added"] == 2

    response = client.get("/senders/")
    assert response.status_code == 200
    registry = response.json()
    assert "Telekom" in registry
    assert "AOK Baden-Württemberg" in registry
    assert "Kommunikation" in registry["Telekom"]["categories"]
    assert "Gesundheit" in registry["AOK Baden-Württemberg"]["categories"]


def test_rebuild_senders_persists_after_restart(in_memory_db):
    """Verify that senders rebuilt via the API are still present after a new TestClient start."""
    from fastapi.testclient import TestClient
    from api.main import app
    import db.sender_repo as sender_repo

    db.upsert_document(
        file_path="/tmp/telekom.pdf",
        filename="telekom.pdf",
        sender="Telekom",
        date="2026-01-15",
        document_type="Rechnung",
        category="Kommunikation",
        summary="Telekom Rechnung",
        status="ok",
    )

    # First client: rebuild and verify in-memory
    client1 = TestClient(app)
    response = client1.post("/senders/~rebuild")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["added"] == 1
    assert sender_repo.count() == 1

    # Second client: simulate backend restart, verify DB senders are loaded
    client2 = TestClient(app)
    response = client2.get("/senders/")
    assert response.status_code == 200
    registry = response.json()
    assert "Telekom" in registry
    assert "Kommunikation" in registry["Telekom"]["categories"]


def test_delete_sender_removes_entry_from_registry(in_memory_db):
    """Verify that DELETE /senders/{name} removes the sender and refreshes the registry."""
    from fastapi.testclient import TestClient
    from api.main import app
    import db.sender_repo as sender_repo

    db.upsert_document(
        file_path="/tmp/telekom.pdf",
        filename="telekom.pdf",
        sender="Telekom",
        date="2026-01-15",
        document_type="Rechnung",
        category="Kommunikation",
        summary="Telekom Rechnung",
        status="ok",
    )

    client = TestClient(app)
    client.post("/senders/~rebuild")
    assert sender_repo.count() == 1

    response = client.delete("/senders/Telekom")
    assert response.status_code == 204
    assert sender_repo.count() == 0

    response = client.get("/senders/")
    assert response.status_code == 200
    registry = response.json()
    assert "Telekom" not in registry


def test_delete_sender_with_special_characters(in_memory_db):
    """Verify that URL-encoded sender names are decoded and deleted correctly."""
    from fastapi.testclient import TestClient
    from api.main import app
    import db.sender_repo as sender_repo

    name = "AOK Baden-Württemberg"
    db.upsert_document(
        file_path="/tmp/aok.pdf",
        filename="aok.pdf",
        sender=name,
        date="2026-01-15",
        document_type="Bescheid",
        category="Gesundheit",
        summary="AOK Beitragsbescheid",
        status="ok",
    )

    client = TestClient(app)
    client.post("/senders/~rebuild")
    assert sender_repo.count() == 1
    assert name in sender_repo.get_all()

    from urllib.parse import quote
    response = client.delete(f"/senders/{quote(name, safe='')}")
    assert response.status_code == 204
    assert sender_repo.count() == 0

    response = client.get("/senders/")
    assert response.status_code == 200
    registry = response.json()
    assert name not in registry


def test_reload_senders_returns_count(in_memory_db):
    from fastapi.testclient import TestClient
    from api.main import app
    import db.sender_repo as sender_repo

    sender_repo.upsert("Telekom", {"categories": ["Kommunikation"], "pinned_category": None, "excluded_categories": [], "reviewed": False})
    client = TestClient(app)
    response = client.post("/senders/~reload")
    assert response.status_code == 200
    data = response.json()
    assert data["reloaded"] is True
    assert data["count"] >= 1


def test_sender_counts_and_get(in_memory_db):
    from fastapi.testclient import TestClient
    from api.main import app

    db.upsert_document(file_path="/tmp/telekom1.pdf", filename="telekom1.pdf", sender="Telekom", date="2026-01-15", document_type="Rechnung", category="Kommunikation", summary="x", status="ok")
    db.upsert_document(file_path="/tmp/telekom2.pdf", filename="telekom2.pdf", sender="Telekom", date="2026-01-15", document_type="Rechnung", category="Kommunikation", summary="x", status="review")
    db.upsert_document(file_path="/tmp/aok.pdf", filename="aok.pdf", sender="AOK", date="2026-01-15", document_type="Bescheid", category="Gesundheit", summary="x", status="ok")
    client = TestClient(app)
    client.post("/senders/~rebuild")

    resp = client.get("/senders/counts")
    assert resp.status_code == 200
    counts = resp.json()
    assert counts.get("Telekom") == {"ok": 1, "review": 1}
    assert counts.get("AOK") == {"ok": 1, "review": 0}

    resp = client.get("/senders/Telekom")
    assert resp.status_code == 200
    assert resp.json()["categories"] == ["Kommunikation"]

    resp = client.get("/senders/Fehlend")
    assert resp.status_code == 404


def test_update_sender_patches_fields(in_memory_db):
    from fastapi.testclient import TestClient
    from api.main import app
    import db.sender_repo as sender_repo

    sender_repo.upsert("Telekom", {"categories": ["Kommunikation"], "pinned_category": None, "excluded_categories": [], "reviewed": False})
    storage._refresh_cache()
    client = TestClient(app)
    resp = client.patch("/senders/Telekom", json={"pinned_category": "Kommunikation", "reviewed": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["pinned_category"] == "Kommunikation"
    assert data["reviewed"] is True

    resp = client.patch("/senders/Fehlend", json={"reviewed": True})
    assert resp.status_code == 404


def test_rename_sender_updates_documents(in_memory_db, tmp_path):
    from fastapi.testclient import TestClient
    from api.main import app

    db.upsert_document(file_path="/tmp/telekom.pdf", filename="telekom.pdf", sender="Telekom", date="2026-01-15", document_type="Rechnung", category="Kommunikation", summary="x", status="ok")
    import db.sender_repo as sender_repo
    sender_repo.upsert("Telekom", {"categories": ["Kommunikation"], "pinned_category": None, "excluded_categories": [], "reviewed": False})
    storage._refresh_cache()
    client = TestClient(app)

    resp = client.post("/senders/~rename", json={"old_name": "Telekom", "new_name": "T-Mobile"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["renamed"] is True
    assert data["new_name"] == "T-Mobile"
    assert db.get_document(1)["sender"] == "T-Mobile"

    resp = client.post("/senders/~rename", json={"old_name": "Telekom", "new_name": "T-Mobile"})
    assert resp.status_code == 404

    resp = client.post("/senders/~rename", json={"old_name": "T-Mobile", "new_name": "T-Mobile"})
    assert resp.json()["renamed"] is False


def test_merge_sender_moves_and_combines_categories(in_memory_db, tmp_path):
    from fastapi.testclient import TestClient
    from api.main import app

    import config
    monkeypatch_target = tmp_path / "archive"
    monkeypatch_target.mkdir(parents=True, exist_ok=True)
    # Patching is done via fixture below in real code, but we can just use absolute temp paths
    import config as cfg
    cfg.TARGET_BASE = str(monkeypatch_target)
    cfg.SENDER_SUBFOLDERS = False

    src_pdf = tmp_path / "telekom.pdf"
    src_pdf.write_bytes(b"%PDF")
    db.upsert_document(file_path=str(src_pdf), filename="telekom.pdf", sender="Telekom", date="2026-01-15", document_type="Rechnung", category="Kommunikation", summary="x", status="ok")
    import db.sender_repo as sender_repo
    sender_repo.upsert("Telekom", {"categories": ["Kommunikation"], "pinned_category": None, "excluded_categories": [], "reviewed": False})
    sender_repo.upsert("Vodafone", {"categories": ["Kommunikation"], "pinned_category": None, "excluded_categories": [], "reviewed": False})
    storage._refresh_cache()

    client = TestClient(app)
    resp = client.post("/senders/Telekom/merge/Vodafone")
    assert resp.status_code == 200
    data = resp.json()
    assert data["merged_into"] == "Vodafone"
    assert db.get_document(1)["sender"] == "Vodafone"

    resp = client.post("/senders/Fehlend/merge/Vodafone")
    assert resp.status_code == 404


def test_remove_category_and_reclassify(in_memory_db):
    from fastapi.testclient import TestClient
    from api.main import app

    import db.sender_repo as sender_repo
    sender_repo.upsert("Telekom", {"categories": ["Kommunikation", "Sonstiges"], "pinned_category": "Kommunikation", "excluded_categories": [], "reviewed": False})
    storage._refresh_cache()
    db.upsert_document(file_path="/tmp/telekom.pdf", filename="telekom.pdf", sender="Telekom", date="2026-01-15", document_type="Rechnung", category="Kommunikation", summary="x", status="ok")

    client = TestClient(app)
    resp = client.post("/senders/Telekom/remove-category", json={"category": "Kommunikation", "action": "reclassify", "ban": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "reclassify"
    assert data["affected"] == 1
    assert db.get_document(1)["status"] == "pending"

    resp = client.post("/senders/Fehlend/remove-category", json={"category": "x"})
    assert resp.status_code == 404

    resp = client.post("/senders/Telekom/remove-category", json={})
    assert resp.status_code == 400


def test_reorganize_sender_moves_files(in_memory_db, tmp_path):
    from fastapi.testclient import TestClient
    from api.main import app

    import config as cfg
    cfg.TARGET_BASE = str(tmp_path / "archive")
    cfg.SENDER_SUBFOLDERS = False

    import db.sender_repo as sender_repo
    sender_repo.upsert("Telekom", {"categories": ["Kommunikation"], "pinned_category": "Kommunikation", "excluded_categories": [], "reviewed": False})
    storage._refresh_cache()
    src = tmp_path / "telekom.pdf"
    src.write_bytes(b"%PDF")
    db.upsert_document(file_path=str(src), filename="telekom.pdf", sender="Telekom", date="2026-01-15", document_type="Rechnung", category="Kommunikation", summary="x", status="ok")

    client = TestClient(app)
    resp = client.post("/senders/Telekom/reorganize")
    assert resp.status_code == 200
    data = resp.json()
    assert data["moved"] == 1

    resp = client.post("/senders/Fehlend/reorganize")
    assert resp.status_code == 404
