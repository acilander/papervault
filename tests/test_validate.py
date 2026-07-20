import sys, os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from llm import validate_classification


@pytest.fixture(autouse=True)
def stable_document_types(monkeypatch):
    import pipeline.validation as validation
    monkeypatch.setattr(validation, "DOCUMENT_TYPES", ["Kontoauszug", "Warenrechnung", "Dienstleistungsrechnung", "Abrechnung", "Vertrag", "Sonstiges"])


def _valid():
    return {
        "sender": "Sparkasse Karlsruhe",
        "date": "2025-03-15",
        "document_type": "Kontoauszug",
        "category": "Bank & Finanzen",
        "summary": "Monatlicher Kontoauszug der Sparkasse Karlsruhe.",
    }


def test_valid_data_has_no_errors():
    assert validate_classification(_valid()) == []


def test_future_date_rejected():
    d = _valid()
    d["date"] = "2099-01-01"
    errors = validate_classification(d)
    assert any("2099" in e for e in errors)


def test_past_date_too_old_rejected():
    d = _valid()
    d["date"] = "1900-01-01"
    errors = validate_classification(d)
    assert any("1900" in e for e in errors)


def test_invalid_category_rejected():
    d = _valid()
    d["category"] = "Rechnung"
    errors = validate_classification(d)
    assert any("category" in e for e in errors)


def test_invalid_document_type_rejected():
    d = _valid()
    d["document_type"] = "Kassenzettel"
    errors = validate_classification(d)
    assert any("document_type" in e for e in errors)


def test_owner_as_sender_rejected(monkeypatch):
    import pipeline.validation as validation
    monkeypatch.setattr(validation, "OWNER_NAMES", ["alexander staiger"])
    d = _valid()
    d["sender"] = "Alexander Staiger"
    errors = validate_classification(d)
    assert any("Empfaenger" in e for e in errors)


def test_placeholder_sender_normalized_to_none():
    for placeholder in ("unbekannt", "n/a", "???", "Absender", ""):
        d = _valid()
        d["sender"] = placeholder
        validate_classification(d)
        assert d["sender"] is None, f"Platzhalter '{placeholder}' hätte zu None normalisiert werden sollen"


def test_retry_guidance_targets_invalid_fields():
    from llm.classify import _build_retry_instruction
    guidance = _build_retry_instruction(["'sender' ist zu kurz", "'summary' ist zu kurz"])
    assert "Briefkopf" in guidance
    assert "Zusammenfassung" in guidance


def test_null_sender_is_accepted():
    d = _valid()
    d["sender"] = None
    errors = validate_classification(d)
    assert not any("sender" in e.lower() for e in errors)


def test_summary_too_short_rejected():
    d = _valid()
    d["summary"] = "Kurz"
    errors = validate_classification(d)
    assert any("summary" in e for e in errors)


def test_summary_uncertainty_rejected():
    d = _valid()
    d["summary"] = "Ich weiss nicht worum es geht."
    errors = validate_classification(d)
    assert any("summary" in e for e in errors)


def test_sender_equals_summary_rejected():
    d = _valid()
    d["summary"] = d["sender"]
    errors = validate_classification(d)
    assert any("identisch" in e for e in errors)


def test_type_category_any_combination_allowed():
    d = _valid()
    d["document_type"] = "Versicherungsschein"
    d["category"] = "Sonstiges"
    errors = validate_classification(d)
    assert not any("erfordert" in e for e in errors)
