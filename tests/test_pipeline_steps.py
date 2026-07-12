import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import hashlib
import pytest
import db
from db.connection import get_conn
from pipeline import steps
import config


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield


def _make_doc(file_path, content_hash, **overrides):
    data = dict(
        file_path=file_path,
        filename=os.path.basename(file_path),
        sender="Bank",
        date="2025-01-01",
        document_type="Kontoauszug",
        category="Bank & Finanzen",
        summary="Test",
        content_hash=content_hash,
        status="ok",
    )
    data.update(overrides)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO documents (file_path, filename, sender, date, document_type, category, summary, content_hash, status, archived_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
            (data["file_path"], data["filename"], data["sender"], data["date"],
             data["document_type"], data["category"], data["summary"], data["content_hash"], data["status"])
        )
        return cur.lastrowid


def test_check_duplicate_text_hash(monkeypatch, tmp_path):
    text = "PDF same content long enough to be text hash"
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    src = tmp_path / "inbox" / "doc.pdf"
    src.parent.mkdir()
    src.write_bytes(text.encode("utf-8"))
    duplicate = tmp_path / "archive" / "orig.pdf"
    duplicate.parent.mkdir()
    duplicate.write_bytes(text.encode("utf-8"))
    doc_id = _make_doc(str(duplicate), content_hash)
    monkeypatch.setattr(steps, "DUPLICATES_DIR", str(tmp_path / "duplicates"))
    monkeypatch.setattr(steps, "create_shortcut", lambda *a, **k: None)
    result = steps.check_duplicate(str(src), text, doc_id + 1)
    assert result is True


def test_check_duplicate_binary_hash(monkeypatch, tmp_path):
    content = b"%PDF"
    content_hash = hashlib.sha256(content).hexdigest()[:16]
    src = tmp_path / "inbox" / "short.pdf"
    src.parent.mkdir()
    src.write_bytes(content)
    duplicate = tmp_path / "archive" / "orig.pdf"
    duplicate.parent.mkdir()
    duplicate.write_bytes(content)
    doc_id = _make_doc(str(duplicate), content_hash)
    result = steps.check_duplicate(str(src), "short", doc_id + 1)
    assert result is True


def test_check_duplicate_not_duplicate(tmp_path):
    src = tmp_path / "inbox" / "doc.pdf"
    src.parent.mkdir()
    src.write_bytes(b"%PDF unique content")
    result = steps.check_duplicate(str(src), "unique content text that is long enough", 9999)
    assert result is False


def test_check_fuzzy_duplicate_finds_match(tmp_path):
    doc_path = tmp_path / "archive" / "orig.pdf"
    doc_path.parent.mkdir()
    doc_path.write_bytes(b"%PDF")
    doc_id = _make_doc(str(doc_path), "h1", sender="Telekom", date="2025-03-01", document_type="Rechnung")
    result = steps.check_fuzzy_duplicate(doc_id + 1, "Telekom", "2025-03-01", "Rechnung")
    assert result is not None


def test_check_fuzzy_duplicate_no_match(tmp_path):
    doc_path = tmp_path / "archive" / "orig.pdf"
    doc_path.parent.mkdir()
    doc_path.write_bytes(b"%PDF")
    doc_id = _make_doc(str(doc_path), "h1", sender="Telekom", date="2025-03-01", document_type="Rechnung")
    result = steps.check_fuzzy_duplicate(doc_id + 1, "Vodafone", "2025-03-01", "Rechnung")
    assert result is None


def test_archive_file_on_disk_with_sender_subfolders(monkeypatch, tmp_path):
    src = tmp_path / "inbox" / "doc.pdf"
    src.parent.mkdir()
    src.write_bytes(b"%PDF")
    monkeypatch.setattr(config, "TARGET_BASE", str(tmp_path / "target"))
    monkeypatch.setattr(config, "SENDER_SUBFOLDERS", True)
    dest = steps.archive_file_on_disk(str(src), "Bank & Finanzen", "Sparkasse", "2025-03-15")
    assert os.path.exists(dest)
    assert "Bank & Finanzen" in dest
    assert "Sparkasse" in dest


def test_archive_file_on_disk_without_sender_subfolders(monkeypatch, tmp_path):
    src = tmp_path / "inbox" / "doc.pdf"
    src.parent.mkdir()
    src.write_bytes(b"%PDF")
    monkeypatch.setattr(config, "TARGET_BASE", str(tmp_path / "target"))
    monkeypatch.setattr(config, "SENDER_SUBFOLDERS", False)
    dest = steps.archive_file_on_disk(str(src), "Bank & Finanzen", "Sparkasse", "2025-03-15")
    assert os.path.exists(dest)
    assert "Bank & Finanzen" in dest


def test_archive_file_on_disk_bank_with_iban_kontoauszug(monkeypatch, tmp_path):
    src = tmp_path / "inbox" / "konto.pdf"
    src.parent.mkdir()
    src.write_bytes(b"%PDF")
    monkeypatch.setattr(config, "TARGET_BASE", str(tmp_path / "target"))
    monkeypatch.setattr(config, "SENDER_SUBFOLDERS", True)
    dest = steps.archive_file_on_disk(
        str(src), "Bank & Finanzen", "Postbank", "2025-03-15",
        document_type="Kontoauszug", iban="DE89370400440532013000"
    )
    assert os.path.exists(dest)
    assert "Postbank" in dest
    assert "DE89370400440532013000" in dest
    assert "Kontoauszüge" in dest
    assert "2025" in dest


def test_archive_file_on_disk_bank_with_iban_dokument(monkeypatch, tmp_path):
    src = tmp_path / "inbox" / "bankbrief.pdf"
    src.parent.mkdir()
    src.write_bytes(b"%PDF")
    monkeypatch.setattr(config, "TARGET_BASE", str(tmp_path / "target"))
    monkeypatch.setattr(config, "SENDER_SUBFOLDERS", True)
    dest = steps.archive_file_on_disk(
        str(src), "Bank & Finanzen", "Sparkasse", "2025-01-10",
        document_type="Vertrag", iban="DE89370400440532013000"
    )
    assert os.path.exists(dest)
    assert "DE89370400440532013000" in dest
    assert "Dokumente" in dest


def test_archive_file_on_disk_bank_without_iban_fallback(monkeypatch, tmp_path):
    src = tmp_path / "inbox" / "brief.pdf"
    src.parent.mkdir()
    src.write_bytes(b"%PDF")
    monkeypatch.setattr(config, "TARGET_BASE", str(tmp_path / "target"))
    monkeypatch.setattr(config, "SENDER_SUBFOLDERS", True)
    dest = steps.archive_file_on_disk(
        str(src), "Bank & Finanzen", "DKB", "2025-06-01",
        document_type="Sonstiges", iban=None
    )
    assert os.path.exists(dest)
    assert "DKB" in dest
    assert "Dokumente" in dest
    # No IBAN folder level
    parts = dest.replace("\\", "/").split("/")
    assert not any(p.startswith("DE") and len(p) == 22 for p in parts)


def test_archive_file_on_disk_bank_no_sender_subfolders(monkeypatch, tmp_path):
    src = tmp_path / "inbox" / "doc.pdf"
    src.parent.mkdir()
    src.write_bytes(b"%PDF")
    monkeypatch.setattr(config, "TARGET_BASE", str(tmp_path / "target"))
    monkeypatch.setattr(config, "SENDER_SUBFOLDERS", False)
    dest = steps.archive_file_on_disk(
        str(src), "Bank & Finanzen", "Postbank", "2025-03-15",
        document_type="Kontoauszug", iban="DE89370400440532013000"
    )
    # Without SENDER_SUBFOLDERS the Bank special path should NOT apply
    assert os.path.exists(dest)
    assert "DE89370400440532013000" not in dest


def test_cleanup_empty_inbox_folders(monkeypatch, tmp_path):
    inbox = tmp_path / "inbox"
    empty = inbox / "empty"
    nonempty = inbox / "nonempty"
    empty.mkdir(parents=True)
    nonempty.mkdir(parents=True)
    (nonempty / "file.txt").write_text("x")
    monkeypatch.setattr(config, "SOURCE_DIR", str(inbox))
    original_pdf = empty / "doc.pdf"
    original_pdf.write_bytes(b"%PDF")
    original_pdf.unlink()  # simulate file already moved out
    steps.cleanup_empty_inbox_folders(str(original_pdf))
    assert not empty.exists()
    assert nonempty.exists()
    assert inbox.exists()


def test_check_duplicate_ignored_hash(monkeypatch, tmp_path):
    text = "This document content is ignored and should not be re-imported"
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    db.protect_document_hash(content_hash, "ignored", document_id=1, filename="ignored.pdf")

    src = tmp_path / "inbox" / "reimport.pdf"
    src.parent.mkdir()
    src.write_bytes(text.encode("utf-8"))
    ignored_dir = tmp_path / "ignored"
    ignored_dir.mkdir()
    monkeypatch.setattr(steps, "IGNORED_DIR", str(ignored_dir))

    doc_id = _make_doc(str(tmp_path / "placeholder.pdf"), "other")
    result = steps.check_duplicate(str(src), text, doc_id)
    assert result is True
    assert db.get_document(doc_id)["status"] == "ignored"
    assert not src.exists()


def test_check_duplicate_locked_hash(monkeypatch, tmp_path):
    text = "This document content is locked and duplicates should be rejected"
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    original_path = tmp_path / "archive" / "locked_original.pdf"
    original_path.parent.mkdir()
    original_path.write_bytes(text.encode("utf-8"))
    original_id = _make_doc(str(original_path), content_hash, status="locked")
    db.protect_document_hash(content_hash, "locked", document_id=original_id, filename="locked_original.pdf")

    src = tmp_path / "inbox" / "reimport.pdf"
    src.parent.mkdir()
    src.write_bytes(text.encode("utf-8"))
    duplicates_dir = tmp_path / "duplicates"
    duplicates_dir.mkdir()
    monkeypatch.setattr(steps, "DUPLICATES_DIR", str(duplicates_dir))

    new_id = _make_doc(str(tmp_path / "incoming.pdf"), "incoming")
    result = steps.check_duplicate(str(src), text, new_id)
    assert result is True
    assert db.get_document(new_id)["status"] == "duplicate"
    assert not src.exists()
