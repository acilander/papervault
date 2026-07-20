import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import json
import pytest
from unittest.mock import MagicMock, patch
import llm
import storage
import db
import config
from llm.classify import get_classification_diagnostics


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    # Disable MOCK_LLM so actual LLM logic runs
    monkeypatch.setattr(config, "MOCK_LLM", False)
    monkeypatch.setattr("llm.driver.assert_gpu_support", MagicMock())
    monkeypatch.setattr("llm.classify.load_model", lambda: None)
    
    # Isolate database
    test_db = str(tmp_path / "test_classify.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.DB_PATH = test_db
    db.init_db()
    
    # Isolate sender registry
    storage.sender_registry = {}
    yield
    storage.sender_registry = {}


def test_classify_document_mock_mode_returns_dict(monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", True)
    result = llm.classify_document("Rechnung Telekom 2025", filename="Telekom_Rechnung_2025.pdf")
    assert isinstance(result, dict)
    assert "category" in result
    assert "confidence" in result


def test_classify_document_uses_filename_for_sender(monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", True)
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


# ── ADAPTIVE RETRY PIPELINE TESTS ───────────────────────────────────────────

def test_retry_temperature_scaling(monkeypatch):
    calls = []
    
    def mock_create_chat_completion(messages, max_tokens, temperature):
        calls.append({"messages": messages, "temperature": temperature})
        
        # On first attempt (Stage 1 and Stage 2)
        if len(calls) == 1:
            # First attempt Stage 1: return invalid date to force failure
            return {
                "choices": [{"message": {"content": json.dumps({
                    "sender": "Telekom",
                    "date": "invalid-date",
                    "document_type": "Rechnung"
                })}}]
            }
        elif len(calls) == 2:
            # First attempt Stage 2: return valid stage 2
            return {
                "choices": [{"message": {"content": json.dumps({
                    "category": "Arbeit & Rente",
                    "summary": "Das ist eine lange Zusammenfassung für die Rechnung.",
                    "keywords": "Telekom, Rechnung",
                    "low_value": 0
                })}}]
            }
        elif len(calls) == 3:
            # Second attempt Stage 1: return valid date
            return {
                "choices": [{"message": {"content": json.dumps({
                    "sender": "Telekom",
                    "date": "2025-01-15",
                    "document_type": "Rechnung"
                })}}]
            }
        else:
            # Second attempt Stage 2: return valid stage 2
            return {
                "choices": [{"message": {"content": json.dumps({
                    "category": "Arbeit & Rente",
                    "summary": "Das ist eine lange Zusammenfassung für die Rechnung.",
                    "keywords": "Telekom, Rechnung",
                    "low_value": 0
                })}}]
            }

    fake_llm = MagicMock()
    fake_llm.create_chat_completion = mock_create_chat_completion
    monkeypatch.setattr(llm.driver, "_llm", fake_llm)

    result = llm.classify_document("Telekom Rechnung 2025", filename="doc.pdf")
    
    assert result is not None
    assert result["date"] == "2025-01-15"
    assert len(calls) == 4
    
    # Assert temperatures: attempt 1 (calls 1 & 2) should be 0.0, attempt 2 (calls 3 & 4) should be 0.15
    assert calls[0]["temperature"] == 0.0
    assert calls[1]["temperature"] == 0.0
    assert calls[2]["temperature"] == 0.15
    assert calls[3]["temperature"] == 0.15


def test_retry_correction_guidance_in_prompt(monkeypatch):
    calls = []
    
    def mock_create_chat_completion(messages, max_tokens, temperature):
        calls.append({"messages": messages, "temperature": temperature})
        
        if len(calls) == 1:
            # S1: invalid date, sender too short
            return {
                "choices": [{"message": {"content": json.dumps({
                    "sender": "T", # too short
                    "date": "invalid-date",
                    "document_type": "Rechnung"
                })}}]
            }
        elif len(calls) == 2:
            # S2: valid, but summary too short
            return {
                "choices": [{"message": {"content": json.dumps({
                    "category": "Arbeit & Rente",
                    "summary": "kurz", # too short
                    "keywords": "Telekom, Rechnung",
                    "low_value": 0
                })}}]
            }
        elif len(calls) == 3:
            # S1 Retry: valid
            return {
                "choices": [{"message": {"content": json.dumps({
                    "sender": "Telekom",
                    "date": "2025-01-15",
                    "document_type": "Rechnung"
                })}}]
            }
        else:
            # S2 Retry: valid
            return {
                "choices": [{"message": {"content": json.dumps({
                    "category": "Arbeit & Rente",
                    "summary": "Das ist eine lange Zusammenfassung für die Rechnung.",
                    "keywords": "Telekom, Rechnung",
                    "low_value": 0
                })}}]
            }

    fake_llm = MagicMock()
    fake_llm.create_chat_completion = mock_create_chat_completion
    monkeypatch.setattr(llm.driver, "_llm", fake_llm)

    result = llm.classify_document("Telekom Rechnung 2025", filename="doc.pdf")
    assert result is not None
    assert result["sender"] == "Telekom"
    assert result["date"] == "2025-01-15"
    assert len(calls) == 4
    
    s1_retry_msg = calls[2]["messages"][-1]["content"]
    s2_retry_msg = calls[3]["messages"][-1]["content"]
    
    assert "Korrekturauftrag" in s1_retry_msg
    assert "sender" in s1_retry_msg.lower() or "date" in s1_retry_msg.lower() or "summary" in s1_retry_msg.lower()
    
    assert "Korrekturauftrag" in s2_retry_msg
    assert "sender" in s2_retry_msg.lower() or "date" in s2_retry_msg.lower() or "summary" in s2_retry_msg.lower()


def test_retry_loop_prevention_on_identical_signature(monkeypatch):
    calls = []
    
    def mock_create_chat_completion(messages, max_tokens, temperature):
        calls.append({"messages": messages, "temperature": temperature})
        
        # Keep returning the same invalid structure to check if loop stops
        return {
            "choices": [{"message": {"content": json.dumps({
                "sender": "Telekom",
                "date": "invalid-date", # forces date error
                "document_type": "Rechnung",
                "category": "Arbeit & Rente",
                "summary": "Das ist eine lange Zusammenfassung für die Rechnung.",
                "keywords": "Telekom, Rechnung",
                "low_value": 0
            })}}]
        }

    fake_llm = MagicMock()
    fake_llm.create_chat_completion = mock_create_chat_completion
    monkeypatch.setattr(llm.driver, "_llm", fake_llm)

    result = llm.classify_document("Telekom Rechnung 2025", filename="doc.pdf")
    
    # Should break loop early on identical signature and return a low confidence result with notes
    assert result is not None
    assert result["confidence"] == "low"
    assert "Identischer Validierungsfehler" in result["confidence_reason"] or "Gleicher Validierungsfehler" in result["confidence_reason"]
    
    # We should have made exactly 2 attempts (4 calls to complete_chat_completion)
    assert len(calls) == 4
    
    # Check diagnostics
    diags = get_classification_diagnostics()
    assert len(diags) >= 1
    assert diags[0]["failure_type"] == "validation"
    assert any("date" in err for err in diags[0]["errors"])


def test_retry_on_invalid_json(monkeypatch):
    calls = []
    
    def mock_create_chat_completion(messages, max_tokens, temperature):
        calls.append({"messages": messages, "temperature": temperature})
        
        if len(calls) == 1:
            return {"choices": [{"message": {"content": "Not a JSON structure!"}}]}
        elif len(calls) == 2:
            return {
                "choices": [{"message": {"content": json.dumps({
                    "sender": "Telekom",
                    "date": "2025-01-15",
                    "document_type": "Rechnung"
                })}}]
            }
        else:
            return {
                "choices": [{"message": {"content": json.dumps({
                    "category": "Arbeit & Rente",
                    "summary": "Das ist eine lange Zusammenfassung für die Rechnung.",
                    "keywords": "Telekom, Rechnung",
                    "low_value": 0
                })}}]
            }

    fake_llm = MagicMock()
    fake_llm.create_chat_completion = mock_create_chat_completion
    monkeypatch.setattr(llm.driver, "_llm", fake_llm)

    result = llm.classify_document("Telekom Rechnung 2025", filename="doc.pdf")
    assert result is not None
    assert result["sender"] == "Telekom"
    assert result["date"] == "2025-01-15"
    assert len(calls) == 3
    
    diags = get_classification_diagnostics()
    assert any(d["failure_type"] == "invalid_json" for d in diags)


def test_retry_on_context_overflow(monkeypatch):
    calls = []
    
    def mock_create_chat_completion(messages, max_tokens, temperature):
        calls.append({"messages": messages, "temperature": temperature})
        
        if len(calls) == 1:
            raise Exception("This prompt would exceed context window of model!")
        elif len(calls) == 2:
            # Second attempt Stage 1 (after handling context overflow)
            return {
                "choices": [{"message": {"content": json.dumps({
                    "sender": "Telekom",
                    "date": "2025-01-15",
                    "document_type": "Rechnung"
                })}}]
            }
        else:
            # Second attempt Stage 2
            return {
                "choices": [{"message": {"content": json.dumps({
                    "category": "Arbeit & Rente",
                    "summary": "Das ist eine lange Zusammenfassung für die Rechnung.",
                    "keywords": "Telekom, Rechnung",
                    "low_value": 0
                })}}]
            }

    fake_llm = MagicMock()
    fake_llm.create_chat_completion = mock_create_chat_completion
    monkeypatch.setattr(llm.driver, "_llm", fake_llm)

    result = llm.classify_document("Telekom Rechnung 2025", filename="doc.pdf")
    assert result is not None
    assert result["sender"] == "Telekom"
    assert result["date"] == "2025-01-15"
    
    # First call failed with context window exception. It shortened and retried (calls 2 & 3).
    assert len(calls) == 3
    
    # Verify diagnostic was logged
    diags = get_classification_diagnostics()
    assert diags[0]["failure_type"] == "runtime_error"
    assert "exceed context window" in diags[0]["error"]


def test_invented_document_type_immediate_return(monkeypatch):
    calls = []
    
    def mock_create_chat_completion(messages, max_tokens, temperature):
        calls.append({"messages": messages, "temperature": temperature})
        
        if len(calls) == 1:
            return {
                "choices": [{"message": {"content": json.dumps({
                    "sender": "Telekom",
                    "date": "2025-01-15",
                    "document_type": "InventedTypeXYZ" # not in allowed active document types list
                })}}]
            }
        else:
            return {
                "choices": [{"message": {"content": json.dumps({
                    "category": "Arbeit & Rente",
                    "summary": "Das ist eine lange Zusammenfassung für die Rechnung.",
                    "keywords": "Telekom, Rechnung",
                    "low_value": 0
                })}}]
            }

    fake_llm = MagicMock()
    fake_llm.create_chat_completion = mock_create_chat_completion
    monkeypatch.setattr(llm.driver, "_llm", fake_llm)

    result = llm.classify_document("Telekom Rechnung 2025", filename="doc.pdf")
    
    assert result is not None
    assert result["document_type"] == "InventedTypeXYZ" # preserved!
    assert result["confidence"] == "low"
    assert "vorgeschlagener dokumenttyp" in result["confidence_reason"].lower() or "entscheidung" in result["confidence_reason"].lower()
    
    # Should complete immediately on invented document type (exactly 2 calls made)
    assert len(calls) == 2
