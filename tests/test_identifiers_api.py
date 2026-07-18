import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import db
import config
from api.main import app

@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch, tmp_path):
    """Redirect DB_PATH to a temporary sqlite file for each test."""
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr("db.DB_PATH", test_db)
    db.DB_PATH = test_db
    db.init_db()
    yield

def test_identifiers_api_workflow():
    client = TestClient(app)

    # 1. Create a confirmed identifier (will auto-create sender "Allianz")
    payload = {
        "sender_name": "Allianz",
        "identifier_type": "POLICY_NO",
        "identifier_value": "V-992182",
        "label": "Versicherung Allianz Auto",
        "target_category": "Fahrzeug",
        "target_unit": "EG"
    }
    response = client.post("/identifiers/", json=payload)
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assigned_id = response.json()["id"]

    # 2. Get list of confirmed identifiers
    response = client.get("/identifiers/")
    assert response.status_code == 200
    ids = response.json()
    assert len(ids) == 1
    assert ids[0]["sender_name"] == "Allianz"
    assert ids[0]["identifier_value"] == "V-992182"
    assert ids[0]["target_unit"] == "EG"

    # 3. Save unassigned identifier suggestion
    doc_id = db.upsert_document(
        file_path="/tmp/unassigned.pdf",
        filename="unassigned.pdf",
        sender=None, date=None, document_type=None, category=None, summary=None
    )
    import db.identifiers_repo as identifiers_repo
    identifiers_repo.save_unassigned_identifier(doc_id, "IBAN", "DE987654321", "Empfänger: Allianz")

    # 4. Get list of unassigned identifiers
    response = client.get("/identifiers/unassigned")
    assert response.status_code == 200
    unassigned = response.json()
    assert len(unassigned) == 1
    assert unassigned[0]["identifier_value"] == "DE987654321"
    assert unassigned[0]["document_filename"] == "unassigned.pdf"
    unassigned_id = unassigned[0]["id"]

    # 5. Assign unassigned identifier to sender "Allianz"
    assign_payload = {
        "sender_name": "Allianz",
        "label": "Allianz IBAN",
        "target_category": "Fahrzeug",
        "target_unit": "EG"
    }
    response = client.post(f"/identifiers/assign/{unassigned_id}", json=assign_payload)
    assert response.status_code == 200
    assert response.json()["ok"] is True

    # 6. Verify lists are updated
    response = client.get("/identifiers/unassigned")
    assert len(response.json()) == 0

    response = client.get("/identifiers/")
    assert len(response.json()) == 2 # The manually added one + the promoted one!

    # 7. Delete one identifier
    response = client.delete(f"/identifiers/{assigned_id}")
    assert response.status_code == 200
    
    response = client.get("/identifiers/")
    assert len(response.json()) == 1
