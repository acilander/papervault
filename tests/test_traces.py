import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from fastapi.testclient import TestClient

import db
import config
from api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.DB_PATH = test_db
    db.init_db()
    yield


def _insert_sample_doc():
    doc_id = db.upsert_document(
        file_path="/archive/test.pdf",
        filename="test.pdf",
        sender="Test Sender",
        date="2026-07-20",
        document_type="Rechnung",
        category="Sonstiges",
        summary="A test document summary.",
        status="review"
    )
    return doc_id


def test_insert_and_get_traces():
    doc_id = _insert_sample_doc()
    
    # Insert multiple traces
    db.insert_trace(doc_id, "ingest", "success", "Dateisystem-Ingestion gestartet.")
    db.insert_trace(doc_id, "text_extraction", "warning", "OCR-Texterkennung erzwungen.", {"pages": 3})
    db.insert_trace(doc_id, "llm_classification", "failed", "LLM-Inferenz fehlgeschlagen.", {"error": "ConnectionTimeout"})
    
    # Retrieve traces
    traces = db.get_traces_for_document(doc_id)
    
    assert len(traces) == 3
    
    # Verify first trace
    assert traces[0]["step_name"] == "ingest"
    assert traces[0]["status"] == "success"
    assert traces[0]["message"] == "Dateisystem-Ingestion gestartet."
    assert traces[0]["details"] is None
    
    # Verify second trace (with details dict)
    assert traces[1]["step_name"] == "text_extraction"
    assert traces[1]["status"] == "warning"
    assert traces[1]["message"] == "OCR-Texterkennung erzwungen."
    assert traces[1]["details"] == {"pages": 3}
    
    # Verify third trace
    assert traces[2]["step_name"] == "llm_classification"
    assert traces[2]["status"] == "failed"
    assert traces[2]["details"] == {"error": "ConnectionTimeout"}


def test_delete_traces():
    doc_id = _insert_sample_doc()
    
    db.insert_trace(doc_id, "ingest", "success", "Importiert.")
    assert len(db.get_traces_for_document(doc_id)) == 1
    
    db.delete_traces_for_document(doc_id)
    assert len(db.get_traces_for_document(doc_id)) == 0


def test_get_traces_api():
    doc_id = _insert_sample_doc()
    
    db.insert_trace(doc_id, "ingest", "success", "API Test Importiert.", {"file_size": 1024})
    
    # Test GET endpoint
    response = client.get(f"/documents/{doc_id}/traces")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 1
    assert data[0]["step_name"] == "ingest"
    assert data[0]["status"] == "success"
    assert data[0]["message"] == "API Test Importiert."
    assert data[0]["details"] == {"file_size": 1024}


def test_get_traces_api_not_found():
    response = client.get("/documents/999999/traces")
    assert response.status_code == 404
    assert response.json()["detail"] == "Dokument nicht gefunden"
