"""Tests for backend/llm.py real-mode paths and helper functions."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import json
import pytest
from unittest.mock import MagicMock, patch
import llm
import storage
import db


@pytest.fixture(autouse=True)
def reset_llm(monkeypatch):
    llm._llm = None
    monkeypatch.setattr("config.MOCK_LLM", False)
    yield
    llm._llm = None


def test_load_model_skips_when_mock(monkeypatch):
    monkeypatch.setattr("config.MOCK_LLM", True)
    llm._llm = None
    llm.load_model()
    assert llm._llm is None


def test_get_llm_loads_model(monkeypatch):
    fake = MagicMock()
    fake.tokenize = lambda s: s.split()
    monkeypatch.setattr(llm, "_llm", fake)
    assert llm.get_llm() is fake


def test_classify_document_real_mode_returns_data(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.DB_PATH = test_db
    db.init_db()

    fake_llm = MagicMock()
    fake_llm.tokenize = lambda s: s.split()
    fake_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "sender": "Sparkasse",
            "date": "2025-03-15",
            "document_type": "Kontoauszug",
            "category": "Bank & Finanzen",
            "summary": "Kontoauszug der Sparkasse für März 2025.",
            "keywords": "Sparkasse, Kontoauszug",
        })}}]
    }
    monkeypatch.setattr(llm, "_llm", fake_llm)

    result = llm.classify_document("Sparkasse Kontoauszug März 2025", filename="Sparkasse_Kontoauszug_2025.pdf")
    assert result is not None
    assert result["category"] == "Bank & Finanzen"
    assert result["sender"] == "Sparkasse"
    assert result["confidence"] in ("high", "medium", "low")


def test_classify_document_retries_on_invalid_json(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.DB_PATH = test_db
    db.init_db()

    fake_llm = MagicMock()
    fake_llm.tokenize = lambda s: s.split()
    fake_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "not json"}}]
    }
    monkeypatch.setattr(llm, "_llm", fake_llm)

    result = llm.classify_document("Text", filename="doc.pdf")
    assert result is None


def test_validate_classification_rejects_owner_and_short_summary():
    data = {
        "date": "2025-01-15",
        "category": "Bank & Finanzen",
        "sender": "Alexander Staiger",
        "document_type": "Kontoauszug",
        "summary": "kurz",
    }
    errors = llm.validate_classification(data)
    assert any("Empfaenger" in e for e in errors)
    assert any("summary" in e.lower() for e in errors)


def test_detect_known_sender_with_alias():
    storage.sender_registry = {"Telekom": {"categories": ["Kommunikation"], "aliases": ["T-Mobile"], "pinned_category": "Kommunikation"}}
    sender, pinned = llm.detect_known_sender("Ihre T-Mobile Rechnung")
    assert sender == "Telekom"
    assert pinned == "Kommunikation"


def test_build_similar_docs_hint_category_fallback(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.DB_PATH = test_db
    db.init_db()
    storage.sender_registry = {}
    db.upsert_document(
        file_path="/archive/strom.pdf", filename="strom.pdf", sender="Strom AG",
        date="2025-01-01", document_type="Rechnung", category="Energie & Versorgung",
        summary="Stromrechnung", content_hash="h1", status="ok"
    )
    hint = llm.build_similar_docs_hint("Stromabrechnung Verbrauch kWh")
    assert "Energie & Versorgung" in hint


def test_normalize_sender_fuzzy():
    storage.sender_registry = {"Telekom": {"categories": ["Kommunikation"], "aliases": []}}
    assert llm.normalize_sender("Telekom") == "Telekom"
    assert llm.normalize_sender("Telekom AG") == "Telekom"  # fuzzy cutoff 0.82


def test_check_sender_semantic_word_parts():
    assert llm.check_sender_semantic("CinemaXX Entertainment", "CinemaXX Kino") is True
    assert llm.check_sender_semantic("CinemaXX", "Sparkasse") is False
