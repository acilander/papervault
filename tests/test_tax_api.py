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

    storage.sender_registry = {}
    yield


def _insert_doc(tmp_path, name="tax.pdf", full_text="Lohn 50000 EUR"):
    path = tmp_path / name
    path.write_bytes(b"%PDF")
    doc_id = db.upsert_document(
        file_path=str(path), filename=name, sender="Arbeitgeber", date="2025-01-15",
        document_type="Lohnsteuerbescheinigung", category="Arbeit & Rente", summary="Steuer", status="ok",
        archived_at="2025-01-20T10:00:00"
    )
    db.update_document(doc_id, full_text=full_text)
    return doc_id


def test_list_tax_categories():
    resp = client.get("/tax/categories")
    assert resp.status_code == 200
    categories = resp.json()
    assert "Einkünfte" in categories
    assert "Sonderausgaben" in categories


def test_tax_year_crud(tmp_path):
    resp = client.post("/tax/years", json={"year": 2024, "status": "draft", "notes": "Test"})
    assert resp.status_code == 200
    year_id = resp.json()["id"]
    assert resp.json()["year"] == 2024

    resp = client.get("/tax/years")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.patch(f"/tax/years/{year_id}", json={"status": "submitted"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"

    resp = client.delete(f"/tax/years/{year_id}")
    assert resp.status_code == 204

    resp = client.get(f"/tax/years/{year_id}")
    assert resp.status_code == 404


def test_duplicate_year_rejected(tmp_path):
    resp = client.post("/tax/years", json={"year": 2024})
    assert resp.status_code == 200
    resp = client.post("/tax/years", json={"year": 2024})
    assert resp.status_code == 409


def test_link_and_unlink_document(tmp_path):
    year_resp = client.post("/tax/years", json={"year": 2024})
    year_id = year_resp.json()["id"]
    doc_id = _insert_doc(tmp_path, "lohn.pdf")

    resp = client.post(f"/tax/years/{year_id}/documents", json={"document_id": doc_id, "source_type": "tax_program_export"})
    assert resp.status_code == 200
    tax_doc_id = resp.json()["id"]

    resp = client.get(f"/tax/years/{year_id}")
    assert resp.status_code == 200
    assert len(resp.json()["documents"]) == 1

    resp = client.post(f"/tax/years/{year_id}/documents", json={"document_id": doc_id, "source_type": "tax_program_export"})
    assert resp.status_code == 409

    resp = client.delete(f"/tax/documents/{tax_doc_id}")
    assert resp.status_code == 204

    resp = client.get(f"/tax/years/{year_id}")
    assert len(resp.json()["documents"]) == 0


def test_extract_and_manage_positions(monkeypatch, tmp_path):
    year_resp = client.post("/tax/years", json={"year": 2024})
    year_id = year_resp.json()["id"]
    doc_id = _insert_doc(tmp_path, "lohn.pdf", full_text="Lohn 50000 EUR")

    link_resp = client.post(f"/tax/years/{year_id}/documents", json={"document_id": doc_id, "source_type": "tax_program_export"})
    tax_doc_id = link_resp.json()["id"]

    def fake_llm(system, prompt, **kwargs):
        return [{"category": "Einkünfte", "label": "Lohn", "amount": "50000,00"}]

    monkeypatch.setattr("tax.extraction.llm_json_completion", fake_llm)

    resp = client.post(f"/tax/documents/{tax_doc_id}/extract")
    assert resp.status_code == 200
    positions = resp.json()["positions"]
    assert len(positions) == 1
    pos_id = positions[0]["id"]
    assert positions[0]["amount"] == 50000.0

    resp = client.patch(f"/tax/positions/{pos_id}", json={"verified": True, "amount": 51000.0})
    assert resp.status_code == 200
    assert resp.json()["verified"] is True
    assert resp.json()["amount"] == 51000.0

    resp = client.get(f"/tax/years/{year_id}/comparison")
    assert resp.status_code == 200

    resp = client.delete(f"/tax/positions/{pos_id}")
    assert resp.status_code == 204

    resp = client.get(f"/tax/years/{year_id}/positions")
    assert len(resp.json()) == 0


def test_assessment_notice_fills_assessed(monkeypatch, tmp_path):
    year_resp = client.post("/tax/years", json={"year": 2024})
    year_id = year_resp.json()["id"]
    doc_id = _insert_doc(tmp_path, "bescheid.pdf", full_text="Einkommensteuer 8500 EUR")

    link_resp = client.post(f"/tax/years/{year_id}/documents", json={"document_id": doc_id, "source_type": "assessment_notice"})
    tax_doc_id = link_resp.json()["id"]

    def fake_llm(system, prompt, **kwargs):
        return [{"category": "Steuerliche Ergebnisse", "label": "Einkommensteuer", "amount": "8500,00"}]

    monkeypatch.setattr("tax.extraction.llm_json_completion", fake_llm)

    resp = client.post(f"/tax/documents/{tax_doc_id}/extract")
    assert resp.status_code == 200
    pos = resp.json()["positions"][0]
    assert pos["amount"] is None
    assert pos["amount_assessed"] == 8500.0

    resp = client.get(f"/tax/years/{year_id}/comparison")
    data = resp.json()
    assert data["positions"][0]["difference"] == 8500.0
