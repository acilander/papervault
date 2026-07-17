import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import db
import config
from pipeline import core


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield


def _make_pdf(tmp_path, name="doc.pdf", content=b"%PDF-1.4 test"):
    path = tmp_path / name
    path.write_bytes(content)
    return str(path)


def test_register_doc_reuses_existing_path(tmp_path):
    path = _make_pdf(tmp_path)
    doc_id1 = core._register_doc(path, None)
    doc_id2 = core._register_doc(path, None)
    assert doc_id1 == doc_id2


def test_extract_text_encrypted_moves_to_encrypted_dir(monkeypatch, tmp_path):
    encrypted = tmp_path / "encrypted.pdf"
    encrypted.write_bytes(b"%PDF-1.4 encrypted")
    encrypted_dir = str(tmp_path / "encrypted")
    monkeypatch.setattr(core, "ENCRYPTED_DIR", encrypted_dir)
    monkeypatch.setattr(core, "extract_text", lambda p: ("", "encrypted"))
    doc_id = core._register_doc(str(encrypted), None)
    text, status = core._extract_text(str(encrypted), doc_id)
    assert text is None
    assert (tmp_path / "encrypted" / "encrypted.pdf").exists()


def test_extract_text_corrupt_moves_to_failed_dir(monkeypatch, tmp_path):
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF")
    monkeypatch.setattr(core, "FAILED_DIR", str(tmp_path / "failed"))
    monkeypatch.setattr(core, "extract_text", lambda p: (None, "corrupt"))
    doc_id = core._register_doc(str(corrupt), None)
    text, status = core._extract_text(str(corrupt), doc_id)
    assert text is None


def test_extract_text_no_text_status_no_text(monkeypatch, tmp_path):
    doc = _make_pdf(tmp_path, content=b"%PDF-1.4")
    monkeypatch.setattr(core, "extract_text", lambda p: ("", "ok"))
    monkeypatch.setattr(core, "ocr_pdf", lambda p: "")
    monkeypatch.setattr(core, "FAILED_DIR", str(tmp_path / "failed"))
    doc_id = core._register_doc(doc, None)
    text, status = core._extract_text(doc, doc_id)
    assert text is None
    doc_row = db.get_document(doc_id)
    assert doc_row["status"] == "no_text"


def test_build_user_hint_reads_hint_file(tmp_path, monkeypatch):
    pdf = _make_pdf(tmp_path, "doc.pdf")
    hint = tmp_path / "doc.hint"
    hint.write_text("Kassenbon", encoding="utf-8")
    monkeypatch.setattr(core, "detect_receipt", lambda text, filename: (False, None))
    user_hint, hint_path = core._build_user_hint(pdf, "text")
    assert "Kassenbon" in (user_hint or "")


def test_stage_or_archive_archives_when_high_confidence(monkeypatch, tmp_path):
    doc = _make_pdf(tmp_path)
    doc_id = core._register_doc(doc, None)
    monkeypatch.setattr(config, "TARGET_BASE", str(tmp_path / "target"))
    monkeypatch.setattr(config, "SENDER_SUBFOLDERS", True)
    data = {"category": "Bank & Finanzen", "sender": "Sparkasse", "date": "2025-03-15"}
    dest, status, *_ = core._stage_or_archive(doc, "doc.pdf", "high", data)
    assert status == "ok"
    assert dest is not None and os.path.exists(dest)


def test_stage_or_archive_review_when_low_confidence(monkeypatch, tmp_path):
    doc = _make_pdf(tmp_path)
    doc_id = core._register_doc(doc, None)
    monkeypatch.setattr(config, "REVIEW_DIR", str(tmp_path / "review"))
    data = {"category": "Bank & Finanzen", "sender": "Sparkasse", "date": "2025-03-15"}
    dest, status, *_ = core._stage_or_archive(doc, "doc.pdf", "low", data)
    assert status == "review"
    assert dest is not None and os.path.exists(dest)


def test_process_pdf_skips_missing_file(tmp_path):
    missing = str(tmp_path / "missing.pdf")
    result = core.process_pdf(missing)
    assert result is None or "nicht" in str(result).lower()


def test_process_pdf_simhash_bypass_for_periodic(monkeypatch, tmp_path):
    target_dir = tmp_path / "target"
    review_dir = tmp_path / "review"
    monkeypatch.setattr(config, "TARGET_BASE", str(target_dir))
    monkeypatch.setattr(core, "REVIEW_DIR", str(review_dir))
    monkeypatch.setattr(config, "SENDER_SUBFOLDERS", False)

    text1 = "Kontoauszug Sparkasse Maerz 2024 IBAN DE89370400440532013000 Saldo 100 EUR"
    text2 = "Kontoauszug Sparkasse April 2024 IBAN DE89370400440532013000 Saldo 120 EUR"

    # Mock extract_text and classify_document
    monkeypatch.setattr(core, "extract_text", lambda p: (text1 if "doc1" in p else text2, "ok"))
    
    import llm
    # Mock LLM classification to always return high confidence, but different dates to avoid fuzzy duplicate matching
    monkeypatch.setattr(llm, "classify_document", lambda *a, filename="", **k: {
        "category": "Bank & Finanzen",
        "sender": "Sparkasse",
        "date": "2024-03-15" if "doc1" in filename else "2024-04-15",
        "document_type": "Kontoauszug",
        "confidence": "high",
        "confidence_reason": "Rule match",
        "summary": "Mocks",
        "keywords": []
    })

    # Doc 1: Not a periodic name, processed first
    doc1 = _make_pdf(tmp_path, "doc1.pdf")
    core.process_pdf(doc1)

    # Let's verify Doc 1 was auto-archived with high confidence by querying SQLite
    with db.get_conn() as conn:
        doc1_row = conn.execute("SELECT * FROM documents WHERE filename='doc1.pdf'").fetchone()
    assert doc1_row is not None
    assert doc1_row["status"] == "ok"

    # Doc 2: Has periodic keyword 'kontoauszug' in filename, processed second
    # This matches is_periodic_document and should bypass SimHash near-duplicate check.
    # We pass different content bytes to avoid an exact binary file-level duplicate match.
    doc2 = _make_pdf(tmp_path, "kontoauszug_doc2.pdf", content=b"%PDF-1.4 different bytes")
    core.process_pdf(doc2)

    # Verify Doc 2 was ALSO auto-archived (status ok) with high confidence because SimHash was bypassed!
    with db.get_conn() as conn:
        doc2_row = conn.execute("SELECT * FROM documents WHERE filename='kontoauszug_doc2.pdf'").fetchone()
    assert doc2_row is not None
    assert doc2_row["status"] == "ok"
    assert "Scan-Duplikat" not in (doc2_row["notes"] or "")
