import pytest
from fastapi.testclient import TestClient
import db
import config
from api.main import app
from db.documents_repo import upsert_document

client = TestClient(app)

def test_transactions_api():
    # Make sure DB schema is loaded
    db.init_db()

    # 1. Create a transaction
    res = client.post("/transactions/", json={
        "title": "Stromvertrag Vattenfall",
        "status": "open",
        "type": "continuous"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["id"] > 0
    assert data["title"] == "Stromvertrag Vattenfall"
    assert data["status"] == "open"
    assert data["type"] == "continuous"
    assert len(data["documents"]) == 0
    tx_id = data["id"]

    # 2. Update transaction
    res = client.patch(f"/transactions/{tx_id}", json={
        "title": "Vattenfall Strom",
        "status": "closed"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Vattenfall Strom"
    assert data["status"] == "closed"

    # 3. Create a test document
    doc_id = upsert_document(
        file_path="C:/Archive/test_doc.pdf",
        filename="Abrechnung_2026.pdf",
        sender="Vattenfall",
        date="15.11.2026",
        document_type="Abrechnung",
        category="Betriebskosten",
        summary="Strom-Jahresabrechnung"
    )
    assert doc_id > 0

    # 4. Link document to transaction
    res = client.post(f"/transactions/{tx_id}/documents", json={
        "document_id": doc_id,
        "role": "periodic_statement"
    })
    assert res.status_code == 200
    data = res.json()
    assert len(data["documents"]) == 1
    assert data["documents"][0]["id"] == doc_id
    assert data["documents"][0]["role"] == "periodic_statement"

    # 5. Get document reverse lookup
    res = client.get(f"/transactions/document/{doc_id}")
    assert res.status_code == 200
    txs = res.json()
    assert len(txs) == 1
    assert txs[0]["id"] == tx_id
    assert txs[0]["role"] == "periodic_statement"

    # 6. Unlink document
    res = client.delete(f"/transactions/{tx_id}/documents/{doc_id}")
    assert res.status_code == 200
    data = res.json()
    assert len(data["documents"]) == 0

    # 7. Delete transaction
    res = client.delete(f"/transactions/{tx_id}")
    assert res.status_code == 204

    # Verify transaction 404
    res = client.get(f"/transactions/{tx_id}")
    assert res.status_code == 404
