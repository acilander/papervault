import sys
import os
import shutil
import pytest
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import db
import config
from pipeline.core import process_pdf
from llm import detect_known_sender, check_sender_semantic
import storage


@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch, tmp_path):
    """Redirect DB_PATH to a temporary sqlite file for each test, and configure mock dirs."""
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()

    # Re-route SOURCE and TARGET directories to temp paths
    source_dir = str(tmp_path / "Inbox")
    review_dir = str(tmp_path / "review")
    failed_dir = str(tmp_path / "failed")
    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(review_dir, exist_ok=True)
    os.makedirs(failed_dir, exist_ok=True)

    target_dir = str(tmp_path / "Archive")
    duplicates_dir = str(tmp_path / "duplicates")
    encrypted_dir = str(tmp_path / "encrypted")
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(duplicates_dir, exist_ok=True)
    os.makedirs(encrypted_dir, exist_ok=True)

    monkeypatch.setattr(config, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(config, "TARGET_BASE", target_dir)
    monkeypatch.setattr(config, "REVIEW_DIR", review_dir)
    monkeypatch.setattr(config, "FAILED_DIR", failed_dir)
    monkeypatch.setattr(config, "DUPLICATES_DIR", duplicates_dir)
    monkeypatch.setattr(config, "ENCRYPTED_DIR", encrypted_dir)
    monkeypatch.setattr(config, "MOCK_LLM", True)

    import pipeline.core as _core
    monkeypatch.setattr(_core, "TARGET_BASE", target_dir)
    monkeypatch.setattr(_core, "REVIEW_DIR", review_dir)
    monkeypatch.setattr(_core, "FAILED_DIR", failed_dir)
    monkeypatch.setattr(_core, "DUPLICATES_DIR", duplicates_dir)
    monkeypatch.setattr(_core, "ENCRYPTED_DIR", encrypted_dir)

    yield tmp_path


def test_process_pdf_id_tracking_and_reprocess(in_memory_db, monkeypatch):
    """Verify that reprocessing a document updates the exact same database row and leaves no ghost entries."""
    # Create mock inbox file
    inbox_file = os.path.join(config.SOURCE_DIR, "test_invoice.pdf")
    with open(inbox_file, "w") as f:
        f.write("Dummy PDF Text Content")

    # Mock PyMuPDF text extraction to return mock string (>= 50 chars to skip OCR trigger!)
    monkeypatch.setattr("pipeline.core.extract_text", lambda path: ("Rechnung von Sparkasse. Dies ist ein sehr langer Text mit vielen Details, um OCR zu ueberspringen.", "ok"))

    # 1. Run first Ingest
    process_pdf(inbox_file)

    # Verify document is in review (auto-archived because MOCK_LLM has high confidence!)
    docs = db.search_documents()
    assert len(docs) == 1
    doc = docs[0]
    original_id = doc["id"]
    assert doc["status"] == "ok"
    assert "test_invoice" in doc["file_path"]

    # 2. Simulate Reprocess click from Web UI (Reposition and status update)
    reprocess_inbox_path = os.path.join(config.SOURCE_DIR, "test_invoice_reprocess.pdf")
    shutil.move(doc["file_path"], reprocess_inbox_path)
    db.update_document(original_id, file_path=reprocess_inbox_path, status="pending")

    # Run pipeline on the reprocess path
    process_pdf(reprocess_inbox_path)

    # 3. VERIFY: The existing database row was updated, NOT duplicated!
    final_docs = db.search_documents()
    assert len(final_docs) == 1
    assert final_docs[0]["id"] == original_id
    assert final_docs[0]["status"] == "ok"
    assert "test_invoice_reprocess" in final_docs[0]["file_path"]


def test_cleanup_empty_inbox_folders_after_processing(in_memory_db, monkeypatch):
    """Verify that nested empty inbox folders are removed after a PDF is processed."""
    from pipeline.steps import cleanup_empty_inbox_folders
    subdir = os.path.join(config.SOURCE_DIR, "2025", "Unsorted")
    os.makedirs(subdir, exist_ok=True)
    inbox_file = os.path.join(subdir, "nested_invoice.pdf")
    with open(inbox_file, "w") as f:
        f.write("Dummy PDF Text Content")

    monkeypatch.setattr("pipeline.core.extract_text", lambda path: ("Rechnung von Telekom. Dies ist ein sehr langer Text mit vielen Details, um OCR zu ueberspringen.", "ok"))

    process_pdf(inbox_file)

    assert not os.path.exists(os.path.join(config.SOURCE_DIR, "2025", "Unsorted"))
    assert not os.path.exists(os.path.join(config.SOURCE_DIR, "2025"))
    assert os.path.exists(config.SOURCE_DIR)


def test_cleanup_preserves_non_empty_inbox_folders(in_memory_db, monkeypatch):
    """Verify that non-empty inbox folders are kept during cleanup."""
    from pipeline.steps import cleanup_empty_inbox_folders
    subdir = os.path.join(config.SOURCE_DIR, "2025", "Mixed")
    os.makedirs(subdir, exist_ok=True)
    keep_file = os.path.join(subdir, "keep.pdf")
    with open(keep_file, "w") as f:
        f.write("Another PDF")
    inbox_file = os.path.join(subdir, "move_me.pdf")
    with open(inbox_file, "w") as f:
        f.write("Dummy PDF Text Content")

    monkeypatch.setattr("pipeline.core.extract_text", lambda path: ("Rechnung von Telekom. Dies ist ein sehr langer Text mit vielen Details, um OCR zu ueberspringen.", "ok"))

    process_pdf(inbox_file)

    assert os.path.exists(os.path.join(config.SOURCE_DIR, "2025", "Mixed"))
    assert os.path.exists(keep_file)


def test_cleanup_ignores_paths_outside_source_dir(in_memory_db, monkeypatch):
    """Verify that cleanup does nothing if the file was not inside SOURCE_DIR."""
    from pipeline.steps import cleanup_empty_inbox_folders
    outside_dir = os.path.join(os.path.dirname(config.SOURCE_DIR), "other")
    os.makedirs(outside_dir, exist_ok=True)
    outside_file = os.path.join(outside_dir, "outside.pdf")
    with open(outside_file, "w") as f:
        f.write("Outside")

    dest = os.path.join(config.TARGET_BASE, "outside.pdf")
    shutil.move(outside_file, dest)
    cleanup_empty_inbox_folders(outside_file)

    assert os.path.exists(outside_dir)


def test_detect_known_sender_word_boundaries_and_header(monkeypatch):
    """Verify that Stufe-0 rules strictly require word boundaries and are isolated from body text."""
    # Configure mock registry
    monkeypatch.setattr(storage, "sender_registry", {
        "Netto": {
            "categories": ["Kassenbon & Quittung"],
            "pinned_category": "Kassenbon & Quittung",
            "aliases": ["Netto Marken-Discount"]
        }
    })

    # Test Case 1: 'Netto' as a substring inside salary labels (should NOT match)
    body_text = "Nettolohn: 2500 EUR, Nettobezüge: 1500 EUR"
    sender, category = detect_known_sender(body_text)
    assert sender is None

    # Test Case 2: 'Netto' as a standalone word (should match)
    header_text = "Netto Marken-Discount, Filiale Siegelsbach"
    sender, category = detect_known_sender(header_text)
    assert sender == "Netto"
    assert category == "Kassenbon & Quittung"


def test_pipeline_transactional_rollback(in_memory_db, monkeypatch):
    """Verify that if database write fails, the file system automatically rolls back the PDF move."""
    inbox_file = os.path.join(config.SOURCE_DIR, "test_rollback.pdf")
    with open(inbox_file, "w") as f:
        f.write("Some invoice contents")

    monkeypatch.setattr("pipeline.core.extract_text", lambda path: ("Rechnung von Telekom", "ok"))

    # Force a database exception during upsert/update
    def raise_db_error(*args, **kwargs):
        raise Exception("Simulated SQLite write error")
    monkeypatch.setattr(db, "update_document", raise_db_error)

    # Execute and expect raise
    with pytest.raises(Exception):
        process_pdf(inbox_file)

    # VERIFY: PDF file was safely restored to its original inbox location (Rollback succeeded!)
    assert os.path.exists(inbox_file)
    assert not os.path.exists(os.path.join(config.REVIEW_DIR, "test_rollback.pdf"))
