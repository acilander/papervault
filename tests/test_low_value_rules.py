"""Tests for /low-value-rules endpoints."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from fastapi.testclient import TestClient

import db
from api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.DB_PATH = test_db
    db.init_db()
    yield


def test_list_rules_returns_array():
    resp = client.get("/low-value-rules/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_and_list_rules():
    resp = client.post("/low-value-rules/", json={
        "name": "Kleine Rechnungen",
        "category": "Sonstiges",
        "document_type": "Rechnung",
        "max_amount": 25.0,
        "older_than_days": 365,
        "active": True,
    })
    assert resp.status_code == 200
    rule = resp.json()
    assert rule["name"] == "Kleine Rechnungen"
    assert rule["active"] is True

    resp = client.get("/low-value-rules/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "Kleine Rechnungen"


def test_update_rule_active():
    resp = client.post("/low-value-rules/", json={"name": "Rule", "active": True})
    rule_id = resp.json()["id"]

    resp = client.patch(f"/low-value-rules/{rule_id}", json={"active": False})
    assert resp.status_code == 200
    assert resp.json()["active"] is False


def test_delete_rule():
    resp = client.post("/low-value-rules/", json={"name": "ToDelete"})
    rule_id = resp.json()["id"]

    resp = client.delete(f"/low-value-rules/{rule_id}")
    assert resp.status_code == 204

    resp = client.get("/low-value-rules/")
    assert resp.json() == []


def test_preview_and_apply_rule(tmp_path):
    resp = client.post("/low-value-rules/", json={
        "name": "Test",
        "category": "Sonstiges",
        "document_type": "Rechnung",
        "max_amount": 100.0,
        "active": True,
    })
    rule_id = resp.json()["id"]

    resp = client.post(f"/low-value-rules/{rule_id}/preview")
    assert resp.status_code == 200
    preview = resp.json()
    assert "rule" in preview
    assert "matches" in preview
    assert isinstance(preview["matches"], list)

    resp = client.post(f"/low-value-rules/{rule_id}/apply")
    assert resp.status_code == 200
    result = resp.json()
    assert "matched" in result
    assert "updated" in result
