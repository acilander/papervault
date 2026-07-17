import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import db


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
        summary="Test",
        status="ok",
    )
    data.update(overrides)
    return data


def test_stats_empty():
    stats = db.get_stats()
    assert stats["total"] == 0
    assert stats["by_category"] == []
    assert stats["no_sender"] == 0


def test_stats_total_and_categories():
    db.upsert_document(**_sample())
    db.upsert_document(**_sample(file_path="/archive/2025/insurance.pdf", filename="insurance.pdf", category="Versicherung", sender="Allianz"))
    stats = db.get_stats()
    assert stats["total"] == 2
    cats = {r["category"]: r["count"] for r in stats["by_category"]}
    assert cats["Bank & Finanzen"] == 1
    assert cats["Versicherung"] == 1


def test_stats_by_year():
    db.upsert_document(**_sample(date="2025-03-15"))
    db.upsert_document(**_sample(file_path="/archive/2024/old.pdf", filename="old.pdf", date="2024-01-01"))
    stats = db.get_stats()
    years = {r["year"]: r["count"] for r in stats["by_year"]}
    assert years["2025"] == 1
    assert years["2024"] == 1


def test_stats_by_status():
    db.upsert_document(**_sample(status="ok"))
    db.upsert_document(**_sample(file_path="/archive/2025/rev.pdf", filename="rev.pdf", status="review"))
    stats = db.get_stats()
    statuses = {r["status"]: r["count"] for r in stats["by_status"]}
    assert statuses["ok"] == 1
    assert statuses["review"] == 1


def test_stats_no_sender():
    db.upsert_document(**_sample(sender=None))
    db.upsert_document(**_sample(file_path="/archive/2025/second.pdf", filename="second.pdf", sender="Bank"))
    stats = db.get_stats()
    assert stats["no_sender"] == 1


def test_stats_low_value():
    doc_id = db.upsert_document(**_sample())
    db.update_document(doc_id, low_value=1)
    db.upsert_document(**_sample(file_path="/archive/2025/second.pdf", filename="second.pdf"))
    stats = db.get_stats()
    assert stats["low_value"] == 1


def test_stats_recent():
    db.upsert_document(**_sample())
    stats = db.get_stats()
    assert len(stats["recent"]) == 1
    assert stats["recent"][0]["filename"] == "test.pdf"


def test_stats_new_metrics():
    # Insert some documents and update their verified and confidence values
    doc1 = db.upsert_document(**_sample(file_path="/archive/2025/1.pdf", filename="1.pdf"))
    doc2 = db.upsert_document(**_sample(file_path="/archive/2025/2.pdf", filename="2.pdf"))
    doc3 = db.upsert_document(**_sample(file_path="/archive/2025/3.pdf", filename="3.pdf"))

    db.update_document(doc1, verified=1, confidence="high")
    db.update_document(doc2, verified=0, confidence="medium")
    db.update_document(doc3, verified=0, confidence="low")

    stats = db.get_stats()
    assert stats["verified_count"] == 1
    assert stats["confidence_high"] == 1
    assert stats["confidence_medium"] == 1
    assert stats["confidence_low"] == 1
    assert stats["monthly_fix_costs"] == 0.0  # Empty contracts table

