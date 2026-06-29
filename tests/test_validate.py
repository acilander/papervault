import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from llm import validate_classification


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


def test_owner_as_sender_rejected():
    d = _valid()
    d["sender"] = "Alexander Staiger"
    errors = validate_classification(d)
    assert any("Empfaenger" in e for e in errors)


def test_placeholder_sender_rejected():
    for placeholder in ("unbekannt", "n/a", "???", "Absender", ""):
        d = _valid()
        d["sender"] = placeholder
        errors = validate_classification(d)
        assert errors, f"Platzhalter '{placeholder}' hätte abgelehnt werden sollen"


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


def test_type_category_mismatch_rejected():
    d = _valid()
    d["document_type"] = "Versicherungsschein"
    d["category"] = "Sonstiges"
    errors = validate_classification(d)
    assert any("Versicherungsschein" in e for e in errors)
