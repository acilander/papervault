import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from unittest.mock import patch, MagicMock
import llm
import storage
import db


@pytest.fixture(autouse=True)
def mock_llm_mode(monkeypatch):
    monkeypatch.setattr("config.MOCK_LLM", True)
    yield


def test_classify_document_mock_mode_returns_dict():
    result = llm.classify_document("Rechnung Telekom 2025", filename="Telekom_Rechnung_2025.pdf")
    assert isinstance(result, dict)
    assert "category" in result
    assert "confidence" in result


def test_classify_document_uses_filename_for_sender():
    result = llm.classify_document("Text", filename="Sparkasse_Kontoauszug_2025.pdf")
    assert "Sparkasse" in result["sender"]


def test_filter_keywords_against_text_keeps_existing():
    text = "Rechnung Telekom Strom 2025"
    result = llm.filter_keywords_against_text("Telekom, Strom, Gas", text)
    assert "Telekom" in result
    assert "Strom" in result
    assert "Gas" not in result


def test_filter_keywords_removes_blocklisted_and_short():
    text = "Rechnung Telekom 2025"
    result = llm.filter_keywords_against_text("Rechnung, iban, x, Telekom", text)
    assert "Telekom" in result
    assert "iban" not in result
    assert "Rechnung" not in result
    assert "x" not in result


def test_validate_classification_accepts_valid():
    data = {
        "date": "2025-01-15",
        "category": "Bank & Finanzen",
        "sender": "Sparkasse",
        "document_type": "Kontoauszug",
        "summary": "Das ist eine vollständige Zusammenfassung des Dokuments.",
    }
    errors = llm.validate_classification(data)
    assert errors == []


def test_validate_classification_rejects_bad_date():
    data = {
        "date": "not-a-date",
        "category": "Bank & Finanzen",
        "sender": "X",
        "document_type": "Kontoauszug",
        "summary": "Das ist eine vollständige Zusammenfassung des Dokuments.",
    }
    errors = llm.validate_classification(data)
    assert any("date" in e for e in errors)


def test_normalize_sender_exact_match():
    storage.sender_registry = {"Telekom": {"categories": ["Kommunikation"], "aliases": []}}
    assert llm.normalize_sender("telekom") == "Telekom"
    storage.sender_registry = {}


def test_normalize_sender_alias_match():
    storage.sender_registry = {"Telekom": {"categories": ["Kommunikation"], "aliases": ["T-Mobile"]}}
    assert llm.normalize_sender("T-Mobile") == "Telekom"
    storage.sender_registry = {}


def test_build_similar_docs_hint_finds_sender_match(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    storage.sender_registry = {"Telekom": {"categories": ["Kommunikation"], "aliases": []}}
    doc_id = db.upsert_document(
        file_path="/archive/telekom.pdf", filename="telekom.pdf", sender="Telekom",
        date="2025-01-01", document_type="Rechnung", category="Kommunikation",
        summary="Rechnung", content_hash="h1", status="ok"
    )
    hint = llm.build_similar_docs_hint("Telekom Rechnung 2025")
    assert "Telekom" in hint
    storage.sender_registry = {}


def test_detect_known_sender():
    storage.sender_registry = {"Telekom": {"categories": ["Kommunikation"], "aliases": [], "pinned_category": "Kommunikation"}}
    sender, pinned = llm.detect_known_sender("Telekom Rechnung 2025")
    assert sender == "Telekom"
    assert pinned == "Kommunikation"
    storage.sender_registry = {}


def test_check_sender_semantic():
    assert llm.check_sender_semantic("Sparkasse", "Meine Sparkasse") is True
    assert llm.check_sender_semantic("Unbekannt", "Text") is False
