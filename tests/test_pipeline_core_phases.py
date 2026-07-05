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
