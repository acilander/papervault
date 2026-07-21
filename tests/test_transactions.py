import pytest
import db
from db.connection import get_conn
import db.transactions_repo as tx_repo
from db.documents_repo import upsert_document

def test_transactions_crud():
    # Make sure DB schema is loaded
    db.init_db()
    
    # 1. Create transaction
    tx_id = tx_repo.create_transaction(title="Waschmaschinenkauf", status="open", type_val="discrete")
    assert tx_id > 0
    
    # 2. Get transaction
    tx = tx_repo.get_transaction(tx_id)
    assert tx is not None
    assert tx["title"] == "Waschmaschinenkauf"
    assert tx["status"] == "open"
    assert tx["type"] == "discrete"
    assert len(tx["documents"]) == 0
    
    # 3. List transactions
    txs = tx_repo.list_transactions()
    assert len(txs) >= 1
    assert any(t["id"] == tx_id for t in txs)
    
    # Filter by status
    txs_open = tx_repo.list_transactions(status="open")
    assert len(txs_open) >= 1
    txs_closed = tx_repo.list_transactions(status="closed")
    assert len(txs_closed) == 0
    
    # 4. Update transaction
    updated = tx_repo.update_transaction(tx_id, title="Waschmaschine MediaMarkt", status="closed")
    assert updated is True
    
    tx = tx_repo.get_transaction(tx_id)
    assert tx["title"] == "Waschmaschine MediaMarkt"
    assert tx["status"] == "closed"
    
    # 5. Link a document
    doc_id = upsert_document(
        file_path="C:/Archive/test.pdf",
        filename="Rechnung.pdf",
        sender="MediaMarkt",
        date="12.12.2026",
        document_type="Warenrechnung",
        category="Einkauf & Konsum",
        summary="Testrechnung"
    )
    assert doc_id > 0
    
    added = tx_repo.add_document_to_transaction(tx_id, doc_id, role="invoice")
    assert added is True
    
    # Verify linking in transaction
    tx = tx_repo.get_transaction(tx_id)
    assert len(tx["documents"]) == 1
    assert tx["documents"][0]["id"] == doc_id
    assert tx["documents"][0]["role"] == "invoice"
    
    # Verify reverse lookup
    doc_txs = tx_repo.get_transactions_for_document(doc_id)
    assert len(doc_txs) == 1
    assert doc_txs[0]["id"] == tx_id
    assert doc_txs[0]["role"] == "invoice"
    
    # 6. Unlink document
    removed = tx_repo.remove_document_from_transaction(tx_id, doc_id)
    assert removed is True
    
    tx = tx_repo.get_transaction(tx_id)
    assert len(tx["documents"]) == 0
    
    # 7. Delete transaction
    deleted = tx_repo.delete_transaction(tx_id)
    assert deleted is True
    assert tx_repo.get_transaction(tx_id) is None
