import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import db


@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch, tmp_path):
    """Redirect DB_PATH to a temp file for each test."""
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield


def _sample(**overrides):
    data = dict(
        file_path="/archive/02 - Bank & Finanzen/2025/Sparkasse/Kontoauszug.pdf",
        filename="Kontoauszug.pdf",
        sender="Sparkasse Karlsruhe",
        date="2025-03-15",
        document_type="Kontoauszug",
        category="Bank & Finanzen",
        summary="Monatlicher Kontoauszug der Sparkasse.",
        content_hash="abc123",
        status="ok",
        archived_at="2025-03-20T10:00:00",
    )
    data.update(overrides)
    return data


def test_init_creates_schema():
    stats = db.get_stats()
    assert stats["total"] == 0


def test_upsert_and_get():
    s = _sample()
    db.upsert_document(**s)
    results = db.search_documents()
    assert len(results) == 1
    assert results[0]["sender"] == "Sparkasse Karlsruhe"
    assert results[0]["category"] == "Bank & Finanzen"


def test_upsert_is_idempotent():
    s = _sample()
    db.upsert_document(**s)
    db.upsert_document(**s)
    assert len(db.search_documents()) == 1


def test_upsert_updates_on_conflict():
    s = _sample()
    db.upsert_document(**s)
    db.upsert_document(**{**s, "sender": "Sparkasse Updated"})
    results = db.search_documents()
    assert len(results) == 1
    assert results[0]["sender"] == "Sparkasse Updated"


def test_get_document_by_id():
    db.upsert_document(**_sample())
    results = db.search_documents()
    doc_id = results[0]["id"]
    doc = db.get_document(doc_id)
    assert doc["filename"] == "Kontoauszug.pdf"


def test_get_document_not_found():
    assert db.get_document(9999) is None


def test_update_document():
    db.upsert_document(**_sample())
    doc_id = db.search_documents()[0]["id"]
    db.update_document(doc_id, category="Sonstiges", sender="Neue Bank")
    doc = db.get_document(doc_id)
    assert doc["category"] == "Sonstiges"
    assert doc["sender"] == "Neue Bank"


def test_search_by_category():
    db.upsert_document(**_sample())
    db.upsert_document(**_sample(
        file_path="/archive/other.pdf", filename="other.pdf",
        category="Versicherung", sender="Allianz"
    ))
    results = db.search_documents(category="Bank & Finanzen")
    assert len(results) == 1
    assert results[0]["sender"] == "Sparkasse Karlsruhe"


def test_search_by_year():
    db.upsert_document(**_sample(date="2025-03-15"))
    db.upsert_document(**_sample(
        file_path="/archive/old.pdf", filename="old.pdf", date="2023-01-01"
    ))
    results = db.search_documents(year="2025")
    assert len(results) == 1


def test_search_by_sender():
    db.upsert_document(**_sample())
    results = db.search_documents(sender="Sparkasse")
    assert len(results) == 1
    results_none = db.search_documents(sender="Commerzbank")
    assert len(results_none) == 0


def test_search_fulltext():
    db.upsert_document(**_sample(summary="Rechnung fuer Strom und Gas"))
    db.upsert_document(**_sample(
        file_path="/archive/other.pdf", filename="other.pdf",
        summary="Kontoauszug Bank Buchungen"
    ))
    results = db.search_documents(query="Strom")
    assert len(results) == 1


def test_get_stats():
    db.upsert_document(**_sample())
    db.upsert_document(**_sample(
        file_path="/archive/other.pdf", filename="other.pdf",
        category="Versicherung", sender="Allianz", date="2024-06-01"
    ))
    stats = db.get_stats()
    assert stats["total"] == 2
    cats = {r["category"]: r["count"] for r in stats["by_category"]}
    assert cats["Bank & Finanzen"] == 1
    assert cats["Versicherung"] == 1
    years = {r["year"]: r["count"] for r in stats["by_year"]}
    assert "2025" in years
    assert "2024" in years


def test_delete_document():
    db.upsert_document(**_sample())
    doc_id = db.search_documents()[0]["id"]
    db.delete_document(doc_id)
    assert db.get_document(doc_id) is None
    assert len(db.search_documents()) == 0


def test_status_filter():
    db.upsert_document(**_sample(status="ok"))
    db.upsert_document(**_sample(
        file_path="/archive/fail.pdf", filename="fail.pdf", status="classification_failed"
    ))
    ok_results = db.search_documents(status="ok")
    assert len(ok_results) == 1
    fail_results = db.search_documents(status="classification_failed")
    assert len(fail_results) == 1
