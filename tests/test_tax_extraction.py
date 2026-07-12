import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import db
import db.tax_documents_repo as tax_documents_repo
import db.tax_positions_repo as tax_positions_repo
import db.tax_years_repo as tax_years_repo
from tax.extraction import extract_tax_positions


@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield


def _doc_sample(**overrides):
    data = dict(
        file_path="/archive/steuer/2025/lohnsteuer.pdf",
        filename="lohnsteuer.pdf",
        sender="Arbeitgeber GmbH",
        date="2025-03-15",
        document_type="Lohnsteuerbescheinigung",
        category="Arbeit & Rente",
        summary="Lohnsteuerbescheinigung 2025.",
        status="ok",
        archived_at="2025-03-20T10:00:00",
    )
    data.update(overrides)
    return data


def _make_tax_doc(source_type, full_text="Lohn und Gehalt 50.000,00 EUR, Krankenkosten 5.000,00 EUR"):
    year_id = tax_years_repo.insert(year=2025, status="draft")
    doc_id = db.upsert_document(**_doc_sample())
    db.update_document(doc_id, full_text=full_text)
    tax_doc_id = tax_documents_repo.insert(year_id, doc_id, source_type)
    return tax_doc_id, year_id


def test_extract_tax_program_export(monkeypatch):
    tax_doc_id, year_id = _make_tax_doc("tax_program_export")

    def fake_llm(system, prompt, **kwargs):
        return [
            {"category": "Einkünfte", "label": "Lohn und Gehalt", "amount": "50000,00", "page": 1, "source_text": "Lohn"},
            {"category": "Sonderausgaben", "label": "Krankenkosten", "amount": "5000,00", "subcategory": "Krankenkasse"},
        ]

    monkeypatch.setattr("tax.extraction.llm_json_completion", fake_llm)

    positions = extract_tax_positions(tax_doc_id)
    assert len(positions) == 2

    by_label = {p["label"]: p for p in positions}
    assert by_label["Lohn und Gehalt"]["amount"] == 50000.0
    assert by_label["Lohn und Gehalt"]["amount_assessed"] is None
    assert by_label["Krankenkosten"]["amount"] == 5000.0
    assert by_label["Krankenkosten"]["subcategory"] == "Krankenkasse"

    # Second extraction should replace unverified positions.
    def fake_llm2(system, prompt, **kwargs):
        return [{"category": "Einkünfte", "label": "Nur Lohn", "amount": "60000,00"}]

    monkeypatch.setattr("tax.extraction.llm_json_completion", fake_llm2)
    positions2 = extract_tax_positions(tax_doc_id)
    assert len(positions2) == 1
    assert positions2[0]["label"] == "Nur Lohn"


def test_extract_assessment_notice(monkeypatch):
    tax_doc_id, year_id = _make_tax_doc("assessment_notice")

    def fake_llm(system, prompt, **kwargs):
        return [
            {"category": "Steuerliche Ergebnisse", "label": "Festgesetzte Einkommensteuer", "amount": "8.500,00"},
        ]

    monkeypatch.setattr("tax.extraction.llm_json_completion", fake_llm)

    positions = extract_tax_positions(tax_doc_id)
    assert len(positions) == 1
    pos = positions[0]
    assert pos["amount"] is None
    assert pos["amount_assessed"] == 8500.0
    assert pos["category"] == "Steuerliche Ergebnisse"


def test_extract_validates_unknown_category(monkeypatch):
    tax_doc_id, year_id = _make_tax_doc("tax_program_export")

    def fake_llm(system, prompt, **kwargs):
        return [{"category": "Unbekannt", "label": "Test", "amount": "100"}]

    monkeypatch.setattr("tax.extraction.llm_json_completion", fake_llm)

    positions = extract_tax_positions(tax_doc_id)
    assert positions[0]["category"] == "Sonstiges"


def test_extract_no_text():
    tax_doc_id, year_id = _make_tax_doc("tax_program_export", full_text="")

    with pytest.raises(ValueError, match="keinen extrahierten Text"):
        extract_tax_positions(tax_doc_id)


def test_extract_no_result(monkeypatch):
    tax_doc_id, year_id = _make_tax_doc("tax_program_export")

    def fake_llm(system, prompt, **kwargs):
        return None

    monkeypatch.setattr("tax.extraction.llm_json_completion", fake_llm)

    positions = extract_tax_positions(tax_doc_id)
    assert positions == []
