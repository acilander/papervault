import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import date, timedelta
import db


@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield


def _sample(**overrides):
    data = dict(
        file_path="/archive/02 - Bank & Finanzen/2025/Sparkasse/Kontoauszug.pdf",
        filename="Kontoauszug.pdf",
        sender="Sparkasse",
        date="2025-03-15",
        document_type="Kontoauszug",
        category="Bank & Finanzen",
        summary="Kontoauszug.",
        status="ok",
    )
    data.update(overrides)
    return data


# ── New columns ───────────────────────────────────────────────────────────────

def test_update_tags():
    db.upsert_document(**_sample())
    doc_id = db.search_documents()[0]["id"]
    db.update_document(doc_id, tags="steuern,wichtig")
    assert db.get_document(doc_id)["tags"] == "steuern,wichtig"


def test_update_tax_relevant():
    db.upsert_document(**_sample())
    doc_id = db.search_documents()[0]["id"]
    db.update_document(doc_id, tax_relevant=1, tax_year="2025")
    doc = db.get_document(doc_id)
    assert doc["tax_relevant"] == 1
    assert doc["tax_year"] == "2025"


def test_update_expires_at():
    db.upsert_document(**_sample())
    doc_id = db.search_documents()[0]["id"]
    db.update_document(doc_id, expires_at="2026-12-31")
    assert db.get_document(doc_id)["expires_at"] == "2026-12-31"


def test_update_notes():
    db.upsert_document(**_sample())
    doc_id = db.search_documents()[0]["id"]
    db.update_document(doc_id, notes="Wichtige Notiz")
    assert db.get_document(doc_id)["notes"] == "Wichtige Notiz"


# ── get_expiring_documents ────────────────────────────────────────────────────

def test_get_expiring_finds_soon():
    soon = (date.today() + timedelta(days=30)).isoformat()
    db.upsert_document(**_sample())
    doc_id = db.search_documents()[0]["id"]
    db.update_document(doc_id, expires_at=soon)
    results = db.get_expiring_documents(days=60)
    assert len(results) == 1
    assert results[0]["expires_at"] == soon


def test_get_expiring_excludes_far_future():
    far = (date.today() + timedelta(days=200)).isoformat()
    db.upsert_document(**_sample())
    doc_id = db.search_documents()[0]["id"]
    db.update_document(doc_id, expires_at=far)
    results = db.get_expiring_documents(days=60)
    assert len(results) == 0


def test_get_expiring_excludes_past():
    past = (date.today() - timedelta(days=1)).isoformat()
    db.upsert_document(**_sample())
    doc_id = db.search_documents()[0]["id"]
    db.update_document(doc_id, expires_at=past)
    results = db.get_expiring_documents(days=60)
    assert len(results) == 0


def test_get_expiring_excludes_null():
    db.upsert_document(**_sample())  # no expires_at
    results = db.get_expiring_documents(days=60)
    assert len(results) == 0


# ── get_tax_documents ─────────────────────────────────────────────────────────

def test_get_tax_documents_all():
    db.upsert_document(**_sample(file_path="/a/1.pdf", filename="1.pdf"))
    db.upsert_document(**_sample(file_path="/a/2.pdf", filename="2.pdf"))
    doc_ids = [d["id"] for d in db.search_documents()]
    db.update_document(doc_ids[0], tax_relevant=1, tax_year="2025")
    db.update_document(doc_ids[1], tax_relevant=1, tax_year="2024")
    results = db.get_tax_documents()
    assert len(results) == 2


def test_get_tax_documents_filtered_by_year():
    db.upsert_document(**_sample(file_path="/a/1.pdf", filename="1.pdf"))
    db.upsert_document(**_sample(file_path="/a/2.pdf", filename="2.pdf"))
    doc_ids = [d["id"] for d in db.search_documents()]
    db.update_document(doc_ids[0], tax_relevant=1, tax_year="2025")
    db.update_document(doc_ids[1], tax_relevant=1, tax_year="2024")
    results = db.get_tax_documents(year="2025")
    assert len(results) == 1
    assert results[0]["tax_year"] == "2025"


def test_get_tax_documents_excludes_non_tax():
    db.upsert_document(**_sample())  # tax_relevant not set
    results = db.get_tax_documents()
    assert len(results) == 0


# ── search by tax_relevant ────────────────────────────────────────────────────

def test_search_tax_filter():
    db.upsert_document(**_sample(file_path="/a/1.pdf", filename="1.pdf"))
    db.upsert_document(**_sample(file_path="/a/2.pdf", filename="2.pdf"))
    doc_ids = [d["id"] for d in db.search_documents()]
    db.update_document(doc_ids[0], tax_relevant=1)
    results = db.search_documents(tax_relevant=1)
    assert len(results) == 1
