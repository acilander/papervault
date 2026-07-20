import sys
import os
import shutil
import pytest
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import db
import config
import db.sender_repo as sender_repo
import db.identifiers_repo as identifiers_repo
from pipeline.core import process_pdf
import llm

@pytest.fixture(autouse=True)
def init_test_env(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()

    source_dir = str(tmp_path / "Inbox")
    target_dir = str(tmp_path / "Archive")
    review_dir = str(tmp_path / "Archive/review")
    failed_dir = str(tmp_path / "Archive/failed")
    
    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(review_dir, exist_ok=True)
    os.makedirs(failed_dir, exist_ok=True)

    monkeypatch.setattr(config, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(config, "TARGET_BASE", target_dir)
    monkeypatch.setattr(config, "REVIEW_DIR", review_dir)
    monkeypatch.setattr(config, "FAILED_DIR", failed_dir)
    monkeypatch.setattr(config, "DUPLICATES_DIR", str(tmp_path / "duplicates"))
    monkeypatch.setattr(config, "ENCRYPTED_DIR", str(tmp_path / "encrypted"))
    yield

def test_pipeline_identifier_bypass(monkeypatch, tmp_path):
    # 1. Setup Sender & Identifier in DB
    sender_repo.upsert("Müller GmbH", {})
    identifiers_repo.add_identifier(
        sender_name="Müller GmbH",
        identifier_type="PERSONAL_NO",
        identifier_value="12345",
        label="Personalnummer Müller",
        target_category="Arbeit & Rente",
        target_unit="EG"
    )

    # Mock text extraction to return a text containing our identifier and a date
    text_content = "Zeitnachweis. Personalnummer: 12345. Datum des Berichts: 15.07.2026."
    monkeypatch.setattr("pipeline.core.extract_text", lambda path: (text_content, "ok"))

    # Create dummy file in Inbox
    pdf_path = os.path.join(config.SOURCE_DIR, "zeitnachweis_juli.pdf")
    with open(pdf_path, "w") as f:
        f.write("DUMMY PDF CONTENT")

    # Mock LLM classify_document in llm module
    llm_called = False
    def mock_classify(*args, **kwargs):
        nonlocal llm_called
        llm_called = True
        return {
            "sender": "Mock LLM",
            "category": "Müll",
            "document_type": "Dienstleistungsrechnung",
            "date": "2026-07-15",
            "summary": "Rich LLM Summary",
            "keywords": "test, info"
        }
    monkeypatch.setattr(llm, "classify_document", mock_classify)

    # 2. Run Ingestion Pipeline
    process_pdf(pdf_path)

    # 3. Assertions
    assert llm_called is True, "LLM classification should HAVE been called to extract document details!"
    
    # Check if document was successfully auto-archived directly with overridden values
    docs = db.search_documents(sender="Müller GmbH")
    assert len(docs) == 1
    doc = db.get_document(docs[0]["id"])
    
    # Overridden deterministic values
    assert doc["sender"] == "Müller GmbH"
    assert doc["category"] == "Arbeit & Rente"
    assert doc["property_unit"] == "EG"
    
    # Richly extracted LLM metadata (not generic!)
    assert doc["document_type"] == "Dienstleistungsrechnung"
    assert doc["date"] == "2026-07-15"
    assert doc["summary"] == "Rich LLM Summary"
    assert doc["status"] == "ok" # Auto-archived directly because confidence is overridden to high!

def test_pipeline_identifier_scanning(monkeypatch, tmp_path):
    # Setup standard sender in DB
    sender_repo.upsert("Stadtwerke", {})

    # Match existing should not match, forcing LLM classification
    text_content = "Rechnung der Stadtwerke. Kundennummer: KD-99182, Zähler-Nr.: 88121. IBAN für Überweisung: DE11223344556677889900."
    monkeypatch.setattr("pipeline.core.extract_text", lambda path: (text_content, "ok"))

    pdf_path = os.path.join(config.SOURCE_DIR, "rechnung_juli.pdf")
    with open(pdf_path, "w") as f:
        f.write("DUMMY PDF CONTENT")

    # Mock LLM classification to return successfully in llm module
    llm_called = False
    def mock_classify(*args, **kwargs):
        nonlocal llm_called
        llm_called = True
        return {
            "sender": "Stadtwerke",
            "category": "Energie & Versorgung",
            "date": "2026-07-15",
            "document_type": "Warenrechnung",
            "summary": "Stadtwerke Rechnung",
            "confidence": "medium",
            "confidence_reason": "Recognized keywords"
        }
    monkeypatch.setattr(llm, "classify_document", mock_classify)

    # Run Ingestion
    process_pdf(pdf_path)

    assert llm_called is True, "LLM classification should have run as fallback!"

    # Assert that unassigned identifiers were recorded in the DB!
    unassigned = identifiers_repo.get_unassigned_identifiers()
    assert len(unassigned) >= 2
    types = [u["identifier_type"] for u in unassigned]
    values = [u["identifier_value"] for u in unassigned]
    
    assert "IBAN" not in types
    assert "99182" in values
    assert "88121" in values


def test_pipeline_uses_registered_iban_only_for_bank_statements(monkeypatch):
    iban = "DE11111111111111111111"
    sender_repo.upsert("Musterbank", {})
    identifiers_repo.add_identifier("Musterbank", "IBAN", iban, target_category="Bank & Finanzen")
    monkeypatch.setattr("pipeline.core.extract_text", lambda path: (f"Rechnung der Beispiel GmbH vom 15.07.2026. Vielen Dank für Ihren Auftrag. Kontodaten und Bankverbindung: IBAN {iban}.", "ok"))

    def classify_invoice(*args, **kwargs):
        return {
            "sender": "Rechnungssteller",
            "category": "Sonstiges",
            "date": "2026-07-15",
            "document_type": "Warenrechnung",
            "summary": "Rechnung",
            "confidence": "medium",
            "confidence_reason": "Rechnung"
        }

    monkeypatch.setattr(llm, "classify_document", classify_invoice)
    invoice_path = os.path.join(config.SOURCE_DIR, "rechnung.pdf")
    with open(invoice_path, "w") as f:
        f.write("DUMMY PDF CONTENT")
    process_pdf(invoice_path)
    invoice = db.search_documents(query="Rechnung")[0]
    assert invoice["sender"] == "Rechnungssteller"

    monkeypatch.setattr(llm, "classify_document", lambda *args, **kwargs: {
        "sender": "Unbekannt",
        "category": "Sonstiges",
        "date": "2026-07-16",
        "document_type": "Kontoauszug",
        "summary": "Kontoauszug",
        "confidence": "medium",
        "confidence_reason": "Bankdokument"
    })
    statement_path = os.path.join(config.SOURCE_DIR, "kontoauszug.pdf")
    with open(statement_path, "w") as f:
        f.write("DUMMY PDF CONTENT")
    process_pdf(statement_path)
    statement = db.search_documents(query="Kontoauszug")[0]
    assert statement["sender"] == "Musterbank"
