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
