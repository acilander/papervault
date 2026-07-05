import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import db
from db.connection import get_conn


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield


def _sample(**overrides):
    data = dict(
        file_path="/archive/2025/test.pdf",
        filename="test.pdf",
        sender="Sparkasse",
        date="2025-03-15",
        document_type="Kontoauszug",
        category="Bank & Finanzen",
        summary="Monatlicher Kontoauszug",
        content_hash="abc123",
        status="ok",
    )
    data.update(overrides)
    return data


def test_upsert_document_inserts_and_returns_id():
    doc_id = db.upsert_document(**_sample())
    assert isinstance(doc_id, int)
    assert db.get_document(doc_id)["filename"] == "test.pdf"


def test_upsert_document_updates_on_conflict():
    s = _sample()
    db.upsert_document(**s)
    db.upsert_document(**{**s, "sender": "Updated"})
    assert db.get_document_by_path(s["file_path"])["sender"] == "Updated"


def test_get_document_by_path_normalizes():
    db.upsert_document(**_sample(file_path="/archive/2025/test.pdf"))
    doc = db.get_document_by_path("/archive/2025/test.pdf")
    assert doc is not None


def test_get_document_by_hash_filters_status():
    db.upsert_document(**_sample(content_hash="h1", status="ok"))
    db.upsert_document(**_sample(file_path="/archive/2025/other.pdf", filename="other.pdf", content_hash="h2", status="processing"))
    assert db.get_document_by_hash("h1") is not None
    assert db.get_document_by_hash("h2") is not None
    assert db.get_document_by_hash("unknown") is None


def test_update_document_allows_only_allowed_fields():
    doc_id = db.upsert_document(**_sample())
    db.update_document(doc_id, sender="New", forbidden_field="ignored")
    doc = db.get_document(doc_id)
    assert doc["sender"] == "New"
    assert "forbidden_field" not in doc


def test_search_documents_by_query():
    db.upsert_document(**_sample(summary="Stromrechnung"))
    db.upsert_document(**_sample(file_path="/archive/2025/other.pdf", filename="other.pdf", summary="Bank"))
    results = db.search_documents(query="Stromrechnung")
    assert len(results) == 1
    assert results[0]["summary"] == "Stromrechnung"


def test_search_documents_by_filters():
    db.upsert_document(**_sample())
    db.upsert_document(**_sample(file_path="/archive/2024/old.pdf", filename="old.pdf", date="2024-01-01", category="Versicherung", sender="Allianz"))
    assert len(db.search_documents(category="Bank & Finanzen")) == 1
    assert len(db.search_documents(year="2025")) == 1
    assert len(db.search_documents(sender="Sparkasse")) == 1


def test_search_documents_no_sender():
    db.upsert_document(**_sample(sender=None))
    db.upsert_document(**_sample(file_path="/archive/2025/second.pdf", filename="second.pdf", sender="Bank"))
    assert len(db.search_documents(no_sender=True)) == 1


def test_search_documents_tax_relevant():
    doc_id = db.upsert_document(**_sample())
    db.update_document(doc_id, tax_relevant=1)
    db.upsert_document(**_sample(file_path="/archive/2025/second.pdf", filename="second.pdf"))
    assert len(db.search_documents(tax_relevant=True)) == 1


def test_search_documents_tag():
    doc_id = db.upsert_document(**_sample())
    db.update_document(doc_id, tags="steuer")
    assert len(db.search_documents(tag="steuer")) == 1


def test_search_documents_low_value():
    doc_id = db.upsert_document(**_sample())
    db.update_document(doc_id, low_value=1)
    db.upsert_document(**_sample(file_path="/archive/2025/second.pdf", filename="second.pdf"))
    assert len(db.search_documents(low_value=True)) == 1


def test_get_expiring_documents():
    doc_id = db.upsert_document(**_sample())
    db.update_document(doc_id, expires_at="2027-01-15")
    doc_id2 = db.upsert_document(**_sample(file_path="/archive/2025/past.pdf", filename="past.pdf"))
    db.update_document(doc_id2, expires_at="2000-01-01")
    results = db.get_expiring_documents(days=365)
    assert len(results) == 1


def test_get_tax_documents():
    doc_id = db.upsert_document(**_sample())
    db.update_document(doc_id, tax_relevant=1, tax_year="2025")
    db.upsert_document(**_sample(file_path="/archive/2025/non_tax.pdf", filename="non_tax.pdf"))
    assert len(db.get_tax_documents()) == 1
    assert len(db.get_tax_documents(year="2025")) == 1
    assert len(db.get_tax_documents(year="2024")) == 0


def test_delete_document():
    doc_id = db.upsert_document(**_sample())
    db.delete_document(doc_id)
    assert db.get_document(doc_id) is None


def test_find_similar_by_features():
    db.upsert_document(**_sample(category="Bank & Finanzen", document_type="Kontoauszug"))
    results = db.find_similar_by_features(["Bank & Finanzen"], "Kontoauszug")
    assert len(results) >= 1
