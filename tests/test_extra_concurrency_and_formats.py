"""Extra unit tests to close coverage gaps for RAG embeddings, DOCX/XLSX extractions,
schema migration error escalation, and robust locked-database rollback handling.
"""
import sys
import os
import zipfile
import sqlite3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import db


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    _local = getattr(db.connection, "_local", None)
    if _local:
        for attr in ("conn", "db_path"):
            if hasattr(_local, attr):
                delattr(_local, attr)
    yield


# ── 1. RAG Embedding Tests ───────────────────────────────────────────────────

def test_generate_embedding_mock(monkeypatch):
    """Verify generate_embedding returns a mock 1536-dim vector of 0s in mock mode."""
    monkeypatch.setattr("config.MOCK_LLM", True)
    from llm.driver import generate_embedding
    emb = generate_embedding("Guthabenkonto Sparkasse")
    assert isinstance(emb, list)
    assert len(emb) == 1536
    assert all(x == 0.0 for x in emb)


# ── 2. Word (.docx) & Excel (.xlsx) Extraction Tests ─────────────────────────

def test_extract_text_docx(tmp_path):
    """Verify extract_text parses a .docx zip file xml content."""
    fpath = str(tmp_path / "test.docx")
    
    doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body>
            <w:p>
                <w:r>
                    <w:t>Hello Word Document Text Content</w:t>
                </w:r>
            </w:p>
        </w:body>
    </w:document>"""
    
    with zipfile.ZipFile(fpath, "w") as zf:
        zf.writestr("word/document.xml", doc_xml.encode("utf-8"))
        
    from pdf_utils import extract_text
    text, status = extract_text(fpath)
    assert status == "ok"
    assert "Hello Word Document Text Content" in text


def test_extract_text_xlsx(tmp_path):
    """Verify extract_text parses .xlsx zip file sheets, inline strings, and cell numbers."""
    fpath = str(tmp_path / "test.xlsx")
    
    shared_strings_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
        <si><t>Shared Row Column Header</t></si>
        <si><t>Another Shared Value</t></si>
    </sst>"""
    
    sheet1_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
        <sheetData>
            <row r="1">
                <c r="A1" t="s"><v>0</v></c>
                <c r="B1"><v>5678.90</v></c>
                <c r="C1" t="inlineStr"><is><t>Direct Inline Cell String</t></is></c>
            </row>
        </sheetData>
    </worksheet>"""
    
    with zipfile.ZipFile(fpath, "w") as zf:
        zf.writestr("xl/sharedStrings.xml", shared_strings_xml.encode("utf-8"))
        zf.writestr("xl/worksheets/sheet1.xml", sheet1_xml.encode("utf-8"))
        
    from pdf_utils import extract_text
    text, status = extract_text(fpath)
    assert status == "ok"
    assert "Shared Row Column Header" in text
    assert "5678.90" in text
    assert "Direct Inline Cell String" in text


# ── 3. Database Migration Error Escalation Tests ──────────────────────────────

def test_init_db_escalates_on_syntax_error(monkeypatch):
    """Verify init_db raises and does not swallow genuine syntax errors in migrations."""
    import db.schema as schema
    
    # Temporarily monkeypatch MIGRATIONS to contain an invalid SQL statement
    monkeypatch.setattr(schema, "MIGRATIONS", ["ALTER TABLE documents ADD COLUMN invalid syntax table error here"])
    
    with pytest.raises(sqlite3.OperationalError):
        schema.init_db()


# ── 4. Pipeline Robust Rollback-Locked-Database Tests ─────────────────────────

def test_process_pdf_rollback_handles_locked_db(monkeypatch, tmp_path):
    """Verify process_pdf handles db lock exceptions during rollback without crashing."""
    from pipeline.core import process_pdf
    
    # Create a dummy PDF file
    pdf_path = str(tmp_path / "test.pdf")
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 ... dummy content")
        
    # We want Phase 6/7 file relocation to trigger rollback, and db updates to raise an error
    call_count = 0
    def mock_update_document(doc_id, **fields):
        nonlocal call_count
        call_count += 1
        # The first call is to register status="processing", which we let succeed.
        # The subsequent calls (where process_pdf tries to update metadata or failed status) raise lock error.
        if call_count > 1:
            raise sqlite3.OperationalError("database is locked")
            
    monkeypatch.setattr(db, "update_document", mock_update_document)
    monkeypatch.setattr("llm.classify_document", lambda *a, **kw: {"confidence": "high", "date": "2025-01-01"})
    
    # Run process_pdf and ensure it exits cleanly and does not raise an unhandled exception
    try:
        process_pdf(pdf_path)
    except Exception as e:
        pytest.fail(f"process_pdf raised an unhandled exception on database lock rollback: {e}")
