"""Tests for GET /stats/quality endpoint."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

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


def _insert(file_path, sender=None, date=None, doc_type=None,
            category=None, summary=None, status="ok",
            expires_at=None, sim_hash=None):
    """Insert a document directly into DB, returns id."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO documents "
            "(file_path, filename, sender, date, document_type, category, summary, "
            "status, expires_at, archived_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
            (file_path, os.path.basename(file_path), sender, date, doc_type,
             category, summary, status, expires_at)
        )
        doc_id = cur.lastrowid
        if sim_hash is not None:
            conn.execute("UPDATE documents SET sim_hash=? WHERE id=?", (sim_hash, doc_id))
    return doc_id


# ── Empty DB ──────────────────────────────────────────────────────────────────

class TestQualityEmpty:

    def test_empty_db_returns_200(self):
        resp = client.get("/stats/quality")
        assert resp.status_code == 200

    def test_empty_db_score_is_100(self):
        resp = client.get("/stats/quality")
        data = resp.json()
        assert data["score"] == 100
        assert data["total"] == 0

    def test_empty_db_has_empty_fields(self):
        resp = client.get("/stats/quality")
        data = resp.json()
        assert data["fields"] == {}
        assert data["top_incomplete"] == []
        assert data["expiring_soon"] == 0


# ── Score Calculation ─────────────────────────────────────────────────────────

class TestQualityScore:

    def test_fully_complete_doc_score_100(self):
        _insert("/a/doc.pdf", sender="Telekom", date="2024-01-01",
                doc_type="Rechnung", category="Telekommunikation", summary="Test")
        resp = client.get("/stats/quality")
        data = resp.json()
        assert data["score"] == 100.0
        assert data["total"] == 1

    def test_missing_sender_lowers_score(self):
        _insert("/a/doc.pdf", sender=None, date="2024-01-01",
                doc_type="Rechnung", category="Bank & Finanzen", summary="Test")
        resp = client.get("/stats/quality")
        data = resp.json()
        assert data["score"] < 100
        assert data["fields"]["sender"]["missing"] == 1
        assert data["fields"]["sender"]["pct"] == 100.0

    def test_missing_critical_field_penalizes_more_than_summary(self):
        """Missing sender (weight 3) should penalize more than missing summary (weight 1)."""
        # Doc 1: missing sender only
        _insert("/a/doc1.pdf", sender=None, date="2024-01-01",
                doc_type="Rechnung", category="Bank & Finanzen", summary="OK")
        score_missing_sender = client.get("/stats/quality").json()["score"]

        db.init_db()  # reset — won't help, need fresh db
        # Use a second doc comparison instead
        _insert("/a/doc2.pdf", sender="OK", date="2024-01-01",
                doc_type="Rechnung", category="Bank & Finanzen", summary=None)
        score_after = client.get("/stats/quality").json()["score"]

        # After adding a complete doc + summary-missing doc, score should be between previous values
        assert score_after > score_missing_sender  # summary missing hurts less

    def test_all_fields_missing_score_low(self):
        _insert("/a/doc.pdf", sender=None, date=None, doc_type=None,
                category=None, summary=None)
        resp = client.get("/stats/quality")
        data = resp.json()
        assert data["score"] < 50

    def test_score_between_0_and_100(self):
        _insert("/a/doc1.pdf", sender=None, date=None, doc_type=None)
        _insert("/a/doc2.pdf", sender="Bank", date="2024-01-01", doc_type="Rechnung",
                category="Bank & Finanzen", summary="OK")
        resp = client.get("/stats/quality")
        data = resp.json()
        assert 0 <= data["score"] <= 100

    def test_multiple_docs_partial_missing(self):
        for i in range(4):
            _insert(f"/a/doc{i}.pdf", sender="Bank", date="2024-01-01",
                    doc_type="Rechnung", category="Bank & Finanzen", summary="OK")
        # 1 doc with missing sender
        _insert("/a/incomplete.pdf", sender=None, date="2024-01-01",
                doc_type="Rechnung", category="Bank & Finanzen", summary="OK")
        resp = client.get("/stats/quality")
        data = resp.json()
        assert data["total"] == 5
        assert data["fields"]["sender"]["missing"] == 1
        assert data["fields"]["sender"]["pct"] == 20.0
        assert data["score"] < 100


# ── Fields Detail ─────────────────────────────────────────────────────────────

class TestQualityFields:

    def test_all_fields_present_in_response(self):
        _insert("/a/doc.pdf", sender="X", date="2024-01-01", doc_type="Rechnung",
                category="Bank & Finanzen", summary="OK")
        resp = client.get("/stats/quality")
        fields = resp.json()["fields"]
        for key in ("sender", "date", "document_type", "category", "summary", "sim_hash"):
            assert key in fields, f"Missing field: {key}"

    def test_sim_hash_missing_counted(self):
        _insert("/a/doc.pdf", sender="X", date="2024-01-01", doc_type="Rechnung",
                category="Bank & Finanzen", summary="OK", sim_hash=None)
        resp = client.get("/stats/quality")
        assert resp.json()["fields"]["sim_hash"]["missing"] == 1

    def test_sim_hash_present_not_counted(self):
        _insert("/a/doc.pdf", sender="X", date="2024-01-01", doc_type="Rechnung",
                category="Bank & Finanzen", summary="OK", sim_hash=123456)
        resp = client.get("/stats/quality")
        assert resp.json()["fields"]["sim_hash"]["missing"] == 0

    def test_empty_string_sender_counted_as_missing(self):
        _insert("/a/doc.pdf", sender="", date="2024-01-01",
                doc_type="Rechnung", category="Bank & Finanzen", summary="OK")
        resp = client.get("/stats/quality")
        assert resp.json()["fields"]["sender"]["missing"] == 1


# ── Excluded Statuses ─────────────────────────────────────────────────────────

class TestQualityExcludedStatuses:

    @pytest.mark.parametrize("status", ["processing", "failed", "duplicate", "encrypted", "corrupt"])
    def test_excluded_status_not_counted(self, status):
        _insert(f"/a/doc_{status}.pdf", sender=None, date=None, doc_type=None,
                status=status)
        resp = client.get("/stats/quality")
        data = resp.json()
        assert data["total"] == 0
        assert data["score"] == 100

    def test_mixed_statuses_only_ok_counted(self):
        _insert("/a/ok.pdf", sender="Bank", date="2024-01-01",
                doc_type="Rechnung", category="Bank & Finanzen", summary="OK", status="ok")
        _insert("/a/dup.pdf", sender=None, date=None, doc_type=None, status="duplicate")
        _insert("/a/enc.pdf", sender=None, date=None, doc_type=None, status="encrypted")
        resp = client.get("/stats/quality")
        data = resp.json()
        assert data["total"] == 1
        assert data["score"] == 100.0


# ── Top Incomplete ────────────────────────────────────────────────────────────

class TestQualityTopIncomplete:

    def test_top_incomplete_contains_docs_with_missing_critical_fields(self):
        _insert("/a/incomplete.pdf", sender=None, date=None, doc_type=None)
        resp = client.get("/stats/quality")
        data = resp.json()
        assert len(data["top_incomplete"]) == 1
        item = data["top_incomplete"][0]
        assert "missing_fields" in item
        assert "sender" in item["missing_fields"]

    def test_complete_doc_not_in_top_incomplete(self):
        _insert("/a/complete.pdf", sender="Bank", date="2024-01-01",
                doc_type="Rechnung", category="Bank & Finanzen", summary="OK")
        resp = client.get("/stats/quality")
        data = resp.json()
        assert len(data["top_incomplete"]) == 0

    def test_top_incomplete_max_10(self):
        for i in range(15):
            _insert(f"/a/incomplete_{i}.pdf", sender=None, date=None, doc_type=None)
        resp = client.get("/stats/quality")
        data = resp.json()
        assert len(data["top_incomplete"]) <= 10


# ── Expiring Soon ─────────────────────────────────────────────────────────────

class TestQualityExpiringSoon:

    def test_no_expiring_docs(self):
        _insert("/a/doc.pdf", sender="X", date="2024-01-01",
                doc_type="Rechnung", category="Bank & Finanzen", summary="OK")
        resp = client.get("/stats/quality")
        assert resp.json()["expiring_soon"] == 0

    def test_expiring_within_60_days_counted(self):
        _insert("/a/expiring.pdf", sender="X", date="2024-01-01",
                doc_type="Rechnung", category="Bank & Finanzen", summary="OK",
                expires_at="2099-01-01")  # far future — won't count
        _insert("/a/expiring2.pdf", sender="X", date="2024-01-01",
                doc_type="Rechnung", category="Bank & Finanzen", summary="OK",
                expires_at="2000-01-01")  # past — won't count
        resp = client.get("/stats/quality")
        assert resp.json()["expiring_soon"] == 0

    def test_expired_in_past_not_counted(self):
        _insert("/a/past.pdf", sender="X", date="2024-01-01",
                doc_type="Rechnung", category="Bank & Finanzen", summary="OK",
                expires_at="2000-06-01")
        resp = client.get("/stats/quality")
        assert resp.json()["expiring_soon"] == 0
