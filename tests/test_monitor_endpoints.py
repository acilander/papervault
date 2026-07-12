"""Tests for /monitor/duplicates, /monitor/validation, /monitor/generate-thumbnails
and /documents/{id}/thumbnail endpoints."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from unittest.mock import patch, MagicMock
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


def _insert_doc(file_path, sender, date, doc_type, category="Bank & Finanzen",
                content_hash=None, sim_hash=None, status="ok"):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO documents (file_path, filename, sender, date, document_type, "
            "category, summary, status, content_hash, archived_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
            (file_path, os.path.basename(file_path), sender, date, doc_type,
             category, "Test", status, content_hash)
        )
        doc_id = cur.lastrowid
        if sim_hash is not None:
            conn.execute("UPDATE documents SET sim_hash=? WHERE id=?", (sim_hash, doc_id))
    return doc_id


# ── /monitor/duplicates ───────────────────────────────────────────────────────

class TestDuplicatesEndpoint:

    def test_returns_200_empty(self):
        resp = client.get("/monitor/duplicates")
        assert resp.status_code == 200
        data = resp.json()
        assert "pairs" in data
        assert data["total"] == 0

    def test_exact_hash_match_detected(self):
        _insert_doc("/a/doc1.pdf", "Telekom", "2024-01-01", "Rechnung",
                    content_hash="SAME_HASH")
        _insert_doc("/a/doc2.pdf", "Telekom", "2024-01-15", "Rechnung",
                    content_hash="SAME_HASH")
        resp = client.get("/monitor/duplicates?min_score=100")
        data = resp.json()
        assert data["total"] >= 1
        pair = data["pairs"][0]
        assert pair["score"] == 100
        assert "Hash" in pair["reason"]

    def test_exact_hash_pair_contains_both_docs(self):
        id1 = _insert_doc("/a/docA.pdf", "ING", "2024-02-01", "Kontoauszug",
                           content_hash="HASH_AB")
        id2 = _insert_doc("/a/docB.pdf", "ING", "2024-02-15", "Kontoauszug",
                           content_hash="HASH_AB")
        resp = client.get("/monitor/duplicates?min_score=100")
        pair = resp.json()["pairs"][0]
        ids = {pair["doc_a"]["id"], pair["doc_b"]["id"]}
        assert ids == {id1, id2}

    def test_metadata_match_detected(self):
        _insert_doc("/a/m1.pdf", "Sparkasse", "2024-03-15", "Kontoauszug")
        _insert_doc("/a/m2.pdf", "Sparkasse", "2024-03-15", "Kontoauszug")
        resp = client.get("/monitor/duplicates?min_score=60")
        data = resp.json()
        assert data["total"] >= 1
        scores = [p["score"] for p in data["pairs"]]
        assert any(s == 70 for s in scores)

    def test_metadata_different_date_no_match(self):
        _insert_doc("/a/d1.pdf", "Sparkasse", "2024-01-15", "Kontoauszug")
        _insert_doc("/a/d2.pdf", "Sparkasse", "2024-02-15", "Kontoauszug")
        resp = client.get("/monitor/duplicates?min_score=70")
        data = resp.json()
        assert data["total"] == 0

    def test_simhash_near_duplicate_detected(self):
        from pdf_utils import compute_simhash
        base_text = "Kontoauszug Commerzbank März 2024 Betrag 1234 EUR"
        sim1 = compute_simhash(base_text)
        sim2 = compute_simhash(base_text + " leichte Abweichung")
        id1 = _insert_doc("/a/s1.pdf", "Commerzbank", "2024-03-01", "Kontoauszug",
                           sim_hash=sim1)
        id2 = _insert_doc("/a/s2.pdf", "Commerzbank", "2024-04-01", "Kontoauszug",
                           sim_hash=sim2)
        resp = client.get("/monitor/duplicates?min_score=80")
        data = resp.json()
        # Both docs have nearly identical SimHash → should appear as a pair
        ids_found = {
            (p["doc_a"]["id"], p["doc_b"]["id"])
            for p in data["pairs"]
        }
        pair_ids = {frozenset([id1, id2])}
        result_pairs = {frozenset(p) for p in ids_found}
        assert pair_ids & result_pairs or data["total"] >= 1

    def test_min_score_filter_works(self):
        _insert_doc("/a/f1.pdf", "Telekom", "2024-05-01", "Rechnung")
        _insert_doc("/a/f2.pdf", "Telekom", "2024-05-01", "Rechnung")
        high = client.get("/monitor/duplicates?min_score=100").json()
        low = client.get("/monitor/duplicates?min_score=60").json()
        assert low["total"] >= high["total"]

    def test_no_duplicates_different_senders(self):
        _insert_doc("/a/x1.pdf", "Telekom", "2024-01-01", "Rechnung",
                    content_hash="H1")
        _insert_doc("/a/x2.pdf", "Vodafone", "2024-01-01", "Rechnung",
                    content_hash="H2")
        resp = client.get("/monitor/duplicates?min_score=100")
        assert resp.json()["total"] == 0

    def test_review_status_docs_included(self):
        _insert_doc("/a/r1.pdf", "ING", "2024-06-01", "Kontoauszug",
                    content_hash="REV_HASH", status="review")
        _insert_doc("/a/r2.pdf", "ING", "2024-06-01", "Kontoauszug",
                    content_hash="REV_HASH", status="ok")
        resp = client.get("/monitor/duplicates?min_score=100")
        assert resp.json()["total"] >= 1

    def test_processing_status_excluded(self):
        _insert_doc("/a/p1.pdf", "ING", "2024-07-01", "Kontoauszug",
                    content_hash="PROC_HASH", status="processing")
        _insert_doc("/a/p2.pdf", "ING", "2024-07-01", "Kontoauszug",
                    content_hash="PROC_HASH", status="ok")
        resp = client.get("/monitor/duplicates?min_score=100")
        assert resp.json()["total"] == 0


# ── /monitor/validation ───────────────────────────────────────────────────────

class TestValidationEndpoint:

    def test_returns_200_empty(self):
        resp = client.get("/monitor/validation")
        assert resp.status_code == 200
        data = resp.json()
        assert "groups" in data
        assert data["total_groups"] == 0

    def test_consistent_group_not_reported(self):
        for i in range(3):
            _insert_doc(f"/a/c{i}.pdf", "Sparkasse", f"2024-0{i+1}-15",
                        "Kontoauszug", category="Bank & Finanzen")
        resp = client.get("/monitor/validation")
        assert resp.json()["total_groups"] == 0

    def test_inconsistent_category_detected(self):
        _insert_doc("/a/i1.pdf", "Commerzbank", "2024-01-15", "Kontoauszug",
                    category="Bank & Finanzen")
        _insert_doc("/a/i2.pdf", "Commerzbank", "2024-02-15", "Kontoauszug",
                    category="Sonstiges")
        _insert_doc("/a/i3.pdf", "Commerzbank", "2024-03-15", "Kontoauszug",
                    category="Bank & Finanzen")
        resp = client.get("/monitor/validation")
        data = resp.json()
        assert data["total_groups"] >= 1
        group = data["groups"][0]
        issue_types = [i["type"] for i in group["issues"]]
        assert "inconsistent_category" in issue_types

    def test_inconsistent_category_outlier_identified(self):
        _insert_doc("/a/o1.pdf", "ING", "2024-01-15", "Kontoauszug",
                    category="Bank & Finanzen")
        _insert_doc("/a/o2.pdf", "ING", "2024-02-15", "Kontoauszug",
                    category="Bank & Finanzen")
        id_outlier = _insert_doc("/a/o3.pdf", "ING", "2024-03-15", "Kontoauszug",
                                  category="Sonstiges")
        resp = client.get("/monitor/validation")
        groups = resp.json()["groups"]
        cat_issues = [
            i for g in groups for i in g["issues"]
            if i["type"] == "inconsistent_category"
        ]
        assert len(cat_issues) >= 1
        outlier_ids = [o["id"] for i in cat_issues for o in i.get("outliers", [])]
        assert id_outlier in outlier_ids

    def test_gap_detection_monthly_series(self):
        months = ["2024-01-15", "2024-02-15", "2024-04-15", "2024-05-15"]
        for i, m in enumerate(months):
            _insert_doc(f"/a/gap{i}.pdf", "Telekom", m, "Rechnung",
                        category="Kommunikation")
        resp = client.get("/monitor/validation")
        data = resp.json()
        gap_issues = [
            i for g in data["groups"] for i in g["issues"]
            if i["type"] == "missing_months"
        ]
        assert len(gap_issues) >= 1
        missing = gap_issues[0]["missing_months"]
        assert "2024-03" in missing

    def test_no_gap_when_complete_series(self):
        months = ["2024-01-15", "2024-02-15", "2024-03-15", "2024-04-15"]
        for i, m in enumerate(months):
            _insert_doc(f"/a/full{i}.pdf", "Vodafone", m, "Rechnung",
                        category="Kommunikation")
        resp = client.get("/monitor/validation")
        groups = resp.json()["groups"]
        gap_issues = [
            i for g in groups for i in g["issues"]
            if i["type"] == "missing_months"
        ]
        assert len(gap_issues) == 0

    def test_min_docs_filter(self):
        _insert_doc("/a/single.pdf", "Kleinanbieter", "2024-01-15", "Rechnung",
                    category="Sonstiges")
        resp = client.get("/monitor/validation?min_docs=2")
        assert resp.json()["total_groups"] == 0

    def test_group_contains_member_list(self):
        for i in range(1, 4):
            _insert_doc(f"/a/mem{i}.pdf", "DKB", f"2024-0{i}-15", "Kontoauszug",
                        category="Bank & Finanzen" if i < 3 else "Sonstiges")
        resp = client.get("/monitor/validation")
        groups = resp.json()["groups"]
        assert len(groups) >= 1
        assert "members" in groups[0]
        assert len(groups[0]["members"]) >= 2

    def test_different_sender_not_grouped(self):
        _insert_doc("/a/s1.pdf", "BankA", "2024-01-15", "Kontoauszug",
                    category="Sonstiges")
        _insert_doc("/a/s2.pdf", "BankB", "2024-02-15", "Kontoauszug",
                    category="Bank & Finanzen")
        resp = client.get("/monitor/validation")
        assert resp.json()["total_groups"] == 0


def _parse_sse_done(resp):
    """Extract the final 'done' JSON event from an SSE streaming response."""
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            payload = line[5:].strip()
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "done":
                return event
    return None


# ── /monitor/generate-thumbnails ──────────────────────────────────────────────

class TestGenerateThumbnailsJob:

    def test_returns_200(self):
        resp = client.post("/monitor/generate-thumbnails")
        assert resp.status_code == 200

    def test_response_has_counts(self):
        resp = client.post("/monitor/generate-thumbnails")
        data = _parse_sse_done(resp)
        assert data is not None
        assert "generated" in data
        assert "skipped" in data
        assert "failed" in data

    def test_skips_existing_thumbnails(self, tmp_path):
        import pdf_utils as pu
        original_dir = pu.THUMBNAILS_DIR
        pu.THUMBNAILS_DIR = str(tmp_path)
        try:
            doc_file = tmp_path / "existing.pdf"
            doc_file.write_bytes(b"%PDF")
            doc_id = _insert_doc(str(doc_file), "Bank", "2024-01-01", "Kontoauszug")
            # Pre-create the thumbnail so the job sees it as already done
            thumb = tmp_path / f"{doc_id}.jpg"
            thumb.write_bytes(b"EXISTING")
            with patch("pdf_utils.generate_thumbnail") as mock_gen:
                resp = client.post("/monitor/generate-thumbnails")
            data = _parse_sse_done(resp)
            assert data is not None
            assert data["skipped"] >= 1
            mock_gen.assert_not_called()
        finally:
            pu.THUMBNAILS_DIR = original_dir

    def test_force_regenerates_existing(self, tmp_path):
        thumb = tmp_path / "99.webp"
        thumb.write_bytes(b"old")
        doc_file = tmp_path / "force.pdf"
        doc_file.write_bytes(b"%PDF")
        _insert_doc(str(doc_file), "Bank", "2024-01-01", "Kontoauszug")
        with patch("pdf_utils.get_thumbnail_path", return_value=str(thumb)), \
             patch("pdf_utils.generate_thumbnail", return_value=str(thumb)) as mock_gen:
            resp = client.post("/monitor/generate-thumbnails?force=true")
        assert resp.status_code == 200
        mock_gen.assert_called()

    def test_skips_non_ok_status(self, tmp_path):
        _insert_doc("/a/pending.pdf", "Bank", "2024-01-01", "Kontoauszug",
                    status="processing")
        with patch("pdf_utils.generate_thumbnail") as mock_gen, \
             patch("pdf_utils.get_thumbnail_path", return_value=str(tmp_path / "x.webp")):
            client.post("/monitor/generate-thumbnails")
        mock_gen.assert_not_called()


# ── /documents/{id}/thumbnail ─────────────────────────────────────────────────

class TestThumbnailEndpoint:
    # Patches target api.routes.documents where get_thumbnail_path/generate_thumbnail are imported
    _mod = "api.routes.documents"

    def test_404_for_unknown_doc(self):
        resp = client.get("/documents/99999/thumbnail")
        assert resp.status_code == 404

    def test_serves_existing_thumbnail(self, tmp_path):
        thumb = tmp_path / "cached.jpg"
        thumb.write_bytes(b"\xff\xd8\xff" + b"\x00" * 10)
        doc_id = _insert_doc("/a/thumb_doc.pdf", "Telekom", "2024-01-01", "Rechnung")
        with patch(f"{self._mod}.get_thumbnail_path", return_value=str(thumb)), \
             patch(f"{self._mod}.os.path.exists", return_value=True):
            resp = client.get(f"/documents/{doc_id}/thumbnail")
        assert resp.status_code == 200
        assert "jpeg" in resp.headers["content-type"]

    def test_generates_thumbnail_if_missing(self, tmp_path):
        thumb = tmp_path / "new.webp"
        thumb.write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
        doc_file = tmp_path / "doc.pdf"
        doc_file.write_bytes(b"%PDF fake")
        doc_id = _insert_doc(str(doc_file), "ING", "2024-02-01", "Kontoauszug")

        call_count = [0]
        def exists_side(p):
            call_count[0] += 1
            if str(p) == str(doc_file):
                return True
            if str(p) == str(thumb):
                # First call (pre-generate check) → False, second (post-generate) → True
                return call_count[0] > 2
            return False

        with patch(f"{self._mod}.get_thumbnail_path", return_value=str(thumb)), \
             patch(f"{self._mod}.generate_thumbnail", return_value=str(thumb)) as mock_gen, \
             patch(f"{self._mod}.os.path.exists", side_effect=exists_side):
            resp = client.get(f"/documents/{doc_id}/thumbnail")
        mock_gen.assert_called_once()

    def test_404_when_pdf_missing_and_no_thumb(self, tmp_path):
        doc_id = _insert_doc("/nonexistent/doc.pdf", "Bank", "2024-01-01", "Kontoauszug")
        with patch(f"{self._mod}.get_thumbnail_path", return_value=str(tmp_path / "missing.webp")), \
             patch(f"{self._mod}.os.path.exists", return_value=False):
            resp = client.get(f"/documents/{doc_id}/thumbnail")
        assert resp.status_code == 404

    def test_cache_control_header_present(self, tmp_path):
        thumb = tmp_path / "cached2.webp"
        thumb.write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
        doc_id = _insert_doc("/a/cached_doc.pdf", "Vodafone", "2024-03-01", "Rechnung")
        with patch(f"{self._mod}.get_thumbnail_path", return_value=str(thumb)), \
             patch(f"{self._mod}.os.path.exists", return_value=True):
            resp = client.get(f"/documents/{doc_id}/thumbnail")
        assert resp.status_code == 200
        assert "max-age" in resp.headers.get("cache-control", "")


# ── generate_thumbnail() unit tests ──────────────────────────────────────────

class TestGenerateThumbnailFunction:

    def test_returns_none_for_invalid_file(self, tmp_path):
        from pdf_utils import generate_thumbnail
        import pdf_utils
        original = pdf_utils.THUMBNAILS_DIR
        pdf_utils.THUMBNAILS_DIR = str(tmp_path)
        try:
            result = generate_thumbnail(str(tmp_path / "nonexistent_xyz.pdf"), doc_id=1)
            assert result is None
        finally:
            pdf_utils.THUMBNAILS_DIR = original

    def test_returns_none_for_missing_file(self, tmp_path):
        from pdf_utils import generate_thumbnail
        result = generate_thumbnail(str(tmp_path / "nonexistent.pdf"), doc_id=1)
        assert result is None

    def test_get_thumbnail_path_format(self, tmp_path):
        from pdf_utils import get_thumbnail_path
        import pdf_utils
        monkeypatch_dir = str(tmp_path / "thumbs")
        original = pdf_utils.THUMBNAILS_DIR
        pdf_utils.THUMBNAILS_DIR = monkeypatch_dir
        try:
            path = get_thumbnail_path(42)
            assert path.endswith("42.jpg")
            assert "42" in path
        finally:
            pdf_utils.THUMBNAILS_DIR = original
