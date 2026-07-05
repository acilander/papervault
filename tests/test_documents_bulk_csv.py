"""Tests for POST /documents/bulk-update and GET /documents/export/csv endpoints."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import csv
import io
import pytest
from fastapi.testclient import TestClient

import db
from db.connection import get_conn
from api.main import app

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield


def _insert(file_path, sender="Testbank", date="2024-01-15",
            doc_type="Kontoauszug", category="Bank & Finanzen",
            summary="Test", status="ok"):
    """Insert a document directly into DB, returns id."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO documents "
            "(file_path, filename, sender, date, document_type, category, summary, "
            "status, archived_at) VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
            (file_path, os.path.basename(file_path), sender, date, doc_type,
             category, summary, status)
        )
        return cur.lastrowid


# ── POST /documents/bulk-update ───────────────────────────────────────────────

class TestBulkUpdate:

    def test_empty_ids_returns_400(self):
        resp = client.post("/documents/bulk-update",
                           json={"ids": [], "fields": {"category": "Sonstiges"}})
        assert resp.status_code == 400

    def test_no_valid_fields_returns_400(self):
        doc_id = _insert("/a/doc.pdf")
        resp = client.post("/documents/bulk-update",
                           json={"ids": [doc_id], "fields": {"status": "ok"}})
        assert resp.status_code == 400

    def test_disallowed_field_ignored(self):
        doc_id = _insert("/a/doc.pdf")
        resp = client.post("/documents/bulk-update",
                           json={"ids": [doc_id], "fields": {"status": "duplicate", "category": "Sonstiges"}})
        assert resp.status_code == 200
        doc = db.get_document(doc_id)
        assert doc["status"] == "ok"
        assert doc["category"] == "Sonstiges"

    def test_valid_single_doc_update(self):
        doc_id = _insert("/a/doc.pdf")
        resp = client.post("/documents/bulk-update",
                           json={"ids": [doc_id], "fields": {"category": "Fahrzeug & Werkstatt"}})
        assert resp.status_code == 200
        assert resp.json()["updated"] == 1
        assert resp.json()["skipped"] == 0
        doc = db.get_document(doc_id)
        assert doc["category"] == "Fahrzeug & Werkstatt"

    def test_valid_multiple_docs_update(self):
        ids = [_insert(f"/a/doc{i}.pdf") for i in range(3)]
        resp = client.post("/documents/bulk-update",
                           json={"ids": ids, "fields": {"sender": "Neue Bank"}})
        assert resp.status_code == 200
        assert resp.json()["updated"] == 3
        assert resp.json()["skipped"] == 0
        for doc_id in ids:
            assert db.get_document(doc_id)["sender"] == "Neue Bank"

    def test_nonexistent_ids_counted_as_skipped(self):
        resp = client.post("/documents/bulk-update",
                           json={"ids": [99999, 88888], "fields": {"category": "Sonstiges"}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 0
        assert data["skipped"] == 2

    def test_mixed_valid_invalid_ids(self):
        doc_id = _insert("/a/doc.pdf")
        resp = client.post("/documents/bulk-update",
                           json={"ids": [doc_id, 99999], "fields": {"category": "Sonstiges"}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 1
        assert data["skipped"] == 1

    def test_multiple_fields_updated_at_once(self):
        doc_id = _insert("/a/doc.pdf")
        resp = client.post("/documents/bulk-update",
                           json={"ids": [doc_id],
                                 "fields": {"category": "Sonstiges", "sender": "Neuer Absender",
                                            "document_type": "Vertrag"}})
        assert resp.status_code == 200
        doc = db.get_document(doc_id)
        assert doc["category"] == "Sonstiges"
        assert doc["sender"] == "Neuer Absender"
        assert doc["document_type"] == "Vertrag"

    def test_date_field_allowed(self):
        doc_id = _insert("/a/doc.pdf")
        resp = client.post("/documents/bulk-update",
                           json={"ids": [doc_id], "fields": {"date": "2025-06-01"}})
        assert resp.status_code == 200
        assert db.get_document(doc_id)["date"] == "2025-06-01"

    def test_notes_field_allowed(self):
        doc_id = _insert("/a/doc.pdf")
        resp = client.post("/documents/bulk-update",
                           json={"ids": [doc_id], "fields": {"notes": "Wichtige Notiz"}})
        assert resp.status_code == 200
        assert db.get_document(doc_id)["notes"] == "Wichtige Notiz"


# ── GET /documents/export/csv ─────────────────────────────────────────────────

def _parse_csv(content_bytes: bytes) -> list[dict]:
    """Parse CSV bytes (UTF-8-BOM, semicolon-delimited) into list of row dicts."""
    text = content_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    return list(reader)


class TestCsvExport:

    def test_empty_db_returns_200_with_header_only(self):
        resp = client.get("/documents/export/csv")
        assert resp.status_code == 200
        rows = _parse_csv(resp.content)
        assert rows == []

    def test_content_type_is_csv(self):
        resp = client.get("/documents/export/csv")
        assert "text/csv" in resp.headers["content-type"]

    def test_content_disposition_set(self):
        resp = client.get("/documents/export/csv")
        assert "attachment" in resp.headers["content-disposition"]
        assert "dokumente.csv" in resp.headers["content-disposition"]

    def test_utf8_bom_present(self):
        resp = client.get("/documents/export/csv")
        assert resp.content[:3] == b"\xef\xbb\xbf"

    def test_doc_appears_in_csv(self):
        _insert("/a/doc.pdf", sender="Telekom", date="2024-03-15",
                doc_type="Rechnung", category="Telekommunikation", summary="Handyrechnung")
        resp = client.get("/documents/export/csv")
        rows = _parse_csv(resp.content)
        assert len(rows) == 1
        assert rows[0]["Absender"] == "Telekom"
        assert rows[0]["Datum"] == "2024-03-15"
        assert rows[0]["Typ"] == "Rechnung"
        assert rows[0]["Kategorie"] == "Telekommunikation"

    def test_multiple_docs_all_in_csv(self):
        for i in range(5):
            _insert(f"/a/doc{i}.pdf")
        resp = client.get("/documents/export/csv")
        rows = _parse_csv(resp.content)
        assert len(rows) == 5

    def test_filter_by_category(self):
        _insert("/a/bank.pdf", category="Bank & Finanzen")
        _insert("/a/tel.pdf", category="Telekommunikation")
        resp = client.get("/documents/export/csv?category=Bank+%26+Finanzen")
        rows = _parse_csv(resp.content)
        assert len(rows) == 1
        assert rows[0]["Kategorie"] == "Bank & Finanzen"

    def test_filter_by_year(self):
        _insert("/a/doc2023.pdf", date="2023-05-01")
        _insert("/a/doc2024.pdf", date="2024-05-01")
        resp = client.get("/documents/export/csv?year=2023")
        rows = _parse_csv(resp.content)
        assert len(rows) == 1
        assert rows[0]["Datum"] == "2023-05-01"

    def test_filter_by_sender(self):
        _insert("/a/tel.pdf", sender="Telekom")
        _insert("/a/bank.pdf", sender="Sparkasse")
        resp = client.get("/documents/export/csv?sender=Telekom")
        rows = _parse_csv(resp.content)
        assert len(rows) == 1
        assert rows[0]["Absender"] == "Telekom"

    def test_filter_by_status(self):
        _insert("/a/ok.pdf", status="ok")
        _insert("/a/dup.pdf", status="duplicate")
        resp = client.get("/documents/export/csv?status=duplicate")
        rows = _parse_csv(resp.content)
        assert len(rows) == 1
        assert rows[0]["Status"] == "duplicate"

    def test_summary_newlines_replaced_with_space(self):
        _insert("/a/doc.pdf", summary="Zeile 1\nZeile 2\nZeile 3")
        resp = client.get("/documents/export/csv")
        rows = _parse_csv(resp.content)
        assert "\n" not in rows[0]["Zusammenfassung"]
        assert "Zeile 1" in rows[0]["Zusammenfassung"]

    def test_csv_has_correct_column_headers(self):
        resp = client.get("/documents/export/csv")
        text = resp.content.decode("utf-8-sig")
        header_line = text.split("\r\n")[0] if "\r\n" in text else text.split("\n")[0]
        expected_cols = ["ID", "Dateiname", "Absender", "Datum", "Typ",
                         "Kategorie", "Status", "Archiviert", "Zusammenfassung"]
        for col in expected_cols:
            assert col in header_line

    def test_archived_at_truncated_to_date(self):
        _insert("/a/doc.pdf")
        resp = client.get("/documents/export/csv")
        rows = _parse_csv(resp.content)
        archived = rows[0]["Archiviert"]
        assert len(archived) == 10
        assert archived.count("-") == 2
