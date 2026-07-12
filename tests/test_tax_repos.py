import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import db
import db.tax_years_repo as tax_years_repo
import db.tax_documents_repo as tax_documents_repo
import db.tax_positions_repo as tax_positions_repo


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


def test_tax_year_crud():
    year_id = tax_years_repo.insert(year=2024, status="draft", notes="Test")
    row = tax_years_repo.get(year_id)
    assert row["year"] == 2024
    assert row["status"] == "draft"
    assert row["notes"] == "Test"

    tax_years_repo.update(year_id, status="submitted")
    assert tax_years_repo.get(year_id)["status"] == "submitted"

    all_years = tax_years_repo.get_all()
    assert len(all_years) == 1
    assert all_years[0]["year"] == 2024

    tax_years_repo.delete(year_id)
    assert tax_years_repo.get(year_id) is None


def test_tax_year_unique_year():
    tax_years_repo.insert(year=2024, status="draft")
    with pytest.raises(Exception):
        tax_years_repo.insert(year=2024, status="draft")


def test_tax_year_invalid_status():
    with pytest.raises(ValueError):
        tax_years_repo.insert(year=2024, status="invalid")


def test_tax_document_crud():
    year_id = tax_years_repo.insert(year=2024, status="draft")
    db.upsert_document(**_doc_sample())
    doc_id = db.search_documents()[0]["id"]

    tax_doc_id = tax_documents_repo.insert(
        tax_year_id=year_id,
        document_id=doc_id,
        source_type="tax_program_export",
    )
    row = tax_documents_repo.get(tax_doc_id)
    assert row["tax_year_id"] == year_id
    assert row["document_id"] == doc_id
    assert row["source_type"] == "tax_program_export"
    assert row["verified"] is False

    docs = tax_documents_repo.get_all_for_year(year_id)
    assert len(docs) == 1
    assert docs[0]["filename"] == "lohnsteuer.pdf"

    tax_documents_repo.delete(tax_doc_id)
    assert tax_documents_repo.get(tax_doc_id) is None


def test_tax_document_duplicate_link():
    year_id = tax_years_repo.insert(year=2024, status="draft")
    db.upsert_document(**_doc_sample())
    doc_id = db.search_documents()[0]["id"]

    tax_documents_repo.insert(year_id, doc_id, "tax_program_export")
    with pytest.raises(Exception):
        tax_documents_repo.insert(year_id, doc_id, "tax_program_export")


def test_tax_position_crud():
    year_id = tax_years_repo.insert(year=2024, status="draft")
    db.upsert_document(**_doc_sample())
    doc_id = db.search_documents()[0]["id"]
    tax_doc_id = tax_documents_repo.insert(year_id, doc_id, "tax_program_export")

    pos_id = tax_positions_repo.insert(
        tax_year_id=year_id,
        tax_document_id=tax_doc_id,
        category="Einkünfte",
        label="Lohn und Gehalt",
        amount=50000.0,
        subcategory="Lohn",
        verified=False,
    )
    row = tax_positions_repo.get(pos_id)
    assert row["category"] == "Einkünfte"
    assert row["label"] == "Lohn und Gehalt"
    assert row["amount"] == 50000.0

    positions = tax_positions_repo.get_all_for_year(year_id)
    assert len(positions) == 1
    assert positions[0]["source_type"] == "tax_program_export"

    tax_positions_repo.update(pos_id, verified=True, amount=51000.0)
    updated = tax_positions_repo.get(pos_id)
    assert updated["verified"] is True
    assert updated["amount"] == 51000.0

    tax_positions_repo.delete(pos_id)
    assert tax_positions_repo.get(pos_id) is None


def test_tax_position_invalid_category():
    year_id = tax_years_repo.insert(year=2024, status="draft")
    db.upsert_document(**_doc_sample())
    doc_id = db.search_documents()[0]["id"]
    tax_doc_id = tax_documents_repo.insert(year_id, doc_id, "tax_program_export")

    with pytest.raises(ValueError):
        tax_positions_repo.insert(
            tax_year_id=year_id,
            tax_document_id=tax_doc_id,
            category="Ungueltig",
            label="Test",
        )


def test_summary_by_year():
    year_id = tax_years_repo.insert(year=2024, status="draft")
    db.upsert_document(**_doc_sample())
    doc_id = db.search_documents()[0]["id"]
    tax_doc_id = tax_documents_repo.insert(year_id, doc_id, "tax_program_export")

    tax_positions_repo.insert(year_id, tax_doc_id, "Einkünfte", "Lohn", amount=50000.0)
    tax_positions_repo.insert(year_id, tax_doc_id, "Sonderausgaben", "Krankenkasse", amount=5000.0)

    summary = tax_positions_repo.get_summary_by_year(year_id)
    by_cat = {s["category"]: s for s in summary}
    assert by_cat["Einkünfte"]["total_amount"] == 50000.0
    assert by_cat["Sonderausgaben"]["total_amount"] == 5000.0


def test_development():
    year_2024 = tax_years_repo.insert(year=2024, status="draft")
    year_2025 = tax_years_repo.insert(year=2025, status="draft")
    db.upsert_document(**_doc_sample())
    doc_id = db.search_documents()[0]["id"]

    td_2024 = tax_documents_repo.insert(year_2024, doc_id, "tax_program_export")
    td_2025 = tax_documents_repo.insert(year_2025, doc_id, "tax_program_export")

    tax_positions_repo.insert(year_2024, td_2024, "Einkünfte", "Lohn", amount=50000.0)
    tax_positions_repo.insert(year_2025, td_2025, "Einkünfte", "Lohn", amount=55000.0)

    dev = tax_positions_repo.get_development(category="Einkünfte")
    by_year = {d["year"]: d for d in dev}
    assert by_year[2024]["total_amount"] == 50000.0
    assert by_year[2025]["total_amount"] == 55000.0

    dev_all = tax_positions_repo.get_development()
    assert len(dev_all) == 2


def test_delete_document_cascades_to_tax():
    year_id = tax_years_repo.insert(year=2024, status="draft")
    db.upsert_document(**_doc_sample())
    doc_id = db.search_documents()[0]["id"]
    tax_doc_id = tax_documents_repo.insert(year_id, doc_id, "tax_program_export")
    tax_positions_repo.insert(year_id, tax_doc_id, "Einkünfte", "Lohn", amount=1000.0)

    db.delete_document(doc_id)
    assert tax_documents_repo.get(tax_doc_id) is None
    assert len(tax_positions_repo.get_all_for_year(year_id)) == 0


def test_delete_year_cascades():
    year_id = tax_years_repo.insert(year=2024, status="draft")
    db.upsert_document(**_doc_sample())
    doc_id = db.search_documents()[0]["id"]
    tax_doc_id = tax_documents_repo.insert(year_id, doc_id, "tax_program_export")
    tax_positions_repo.insert(year_id, tax_doc_id, "Einkünfte", "Lohn", amount=1000.0)

    tax_years_repo.delete(year_id)
    assert tax_years_repo.get(year_id) is None
    assert tax_documents_repo.get(tax_doc_id) is None
    assert len(tax_positions_repo.get_all_for_year(year_id)) == 0
