"""Tests for sender quality features:
- validate_classification() new checks (Plan 5 prevention)
- GET /senders/~audit endpoint (Plan 5)
- GET /senders/~ambiguous endpoint (Plan 4)
- POST /senders/{name}/reclassify endpoint (Plan 4)
- update_vendor/provider/partner cascade helpers (Plan 1)
"""
import os
import pytest
import config
import db
import storage
from db.connection import get_conn


@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr("db.DB_PATH", test_db)
    db.DB_PATH = test_db
    db.init_db()

    source_dir = str(tmp_path / "Inbox")
    target_dir = str(tmp_path / "Archive")
    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(target_dir, exist_ok=True)

    monkeypatch.setattr(config, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(config, "TARGET_BASE", target_dir)

    storage.sender_registry = {}
    yield tmp_path


# ---------------------------------------------------------------------------
# Plan 5 – validate_classification() new checks
# ---------------------------------------------------------------------------

class TestValidateClassificationNewChecks:
    def _base_data(self):
        return {
            "sender": "TestFirma GmbH",
            "date": "2024-01-15",
            "document_type": "Warenrechnung",
            "category": "Einkauf & Bestellungen",
            "summary": "Eine Rechnung über Bürombedarf im Januar 2024.",
            "keywords": "rechnung, büro",
            "low_value": 0,
        }

    def test_document_type_as_sender_triggers_error(self):
        from llm import validate_classification
        data = self._base_data()
        data["sender"] = "Warenrechnung"
        errors = validate_classification(data)
        assert any("Dokumenttyp" in e for e in errors), errors

    def test_kontoauszug_as_sender_triggers_error(self):
        from llm import validate_classification
        data = self._base_data()
        data["sender"] = "Kontoauszug"
        errors = validate_classification(data)
        assert any("Dokumenttyp" in e for e in errors), errors

    def test_generic_word_versicherung_triggers_error(self):
        from llm import validate_classification
        data = self._base_data()
        data["sender"] = "Versicherung"
        errors = validate_classification(data)
        assert any("generischer Begriff" in e for e in errors), errors

    def test_generic_word_wohnung_triggers_error(self):
        from llm import validate_classification
        data = self._base_data()
        data["sender"] = "Wohnung"
        errors = validate_classification(data)
        assert any("generischer Begriff" in e for e in errors), errors

    def test_stopword_und_triggers_error(self):
        from llm import validate_classification
        data = self._base_data()
        data["sender"] = "Und"
        errors = validate_classification(data)
        assert any("gültiger Absendername" in e for e in errors), errors

    def test_stopword_der_triggers_error(self):
        from llm import validate_classification
        data = self._base_data()
        data["sender"] = "Der"
        errors = validate_classification(data)
        assert any("gültiger Absendername" in e for e in errors), errors

    def test_abbreviation_DE_triggers_error(self):
        from llm import validate_classification
        data = self._base_data()
        data["sender"] = "DE"
        errors = validate_classification(data)
        assert any("Kürzel" in e or "zu kurz" in e.lower() for e in errors), errors

    def test_abbreviation_AG_alone_triggers_error(self):
        from llm import validate_classification
        data = self._base_data()
        data["sender"] = "AG"
        errors = validate_classification(data)
        assert any("Kürzel" in e or "zu kurz" in e.lower() for e in errors), errors

    def test_valid_sender_passes(self):
        from llm import validate_classification
        data = self._base_data()
        errors = validate_classification(data)
        assert errors == [], errors

    def test_sender_none_does_not_trigger_new_checks(self):
        from llm import validate_classification
        data = self._base_data()
        data["sender"] = None
        errors = validate_classification(data)
        assert not any("Dokumenttyp" in e or "generischer" in e or "Kürzel" in e for e in errors)

    def test_gmbh_suffix_alone_triggers_error(self):
        from llm import validate_classification
        data = self._base_data()
        data["sender"] = "GmbH"
        errors = validate_classification(data)
        assert any("Kürzel" in e for e in errors), errors

    def test_bosch_gmbh_passes(self):
        """Full company name with suffix should NOT trigger abbreviation check."""
        from llm import validate_classification
        data = self._base_data()
        data["sender"] = "Bosch GmbH"
        errors = validate_classification(data)
        assert not any("Kürzel" in e for e in errors), errors


# ---------------------------------------------------------------------------
# Plan 5 – GET /senders/~audit
# ---------------------------------------------------------------------------

class TestAuditEndpoint:
    def _client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def _insert_doc(self, sender, status="ok"):
        doc_id = db.upsert_document(
            file_path=f"/tmp/{sender}_test.pdf",
            filename=f"{sender}_test.pdf",
            sender=sender,
            date="2024-01-01",
            document_type="Sonstiges",
            category="Sonstiges",
            summary="Test",
            content_hash=f"hash_{sender}",
            status=status,
        )
        return doc_id

    def test_audit_detects_too_short(self):
        storage.sender_registry = {"B": {"categories": ["Sonstiges"], "pinned_category": None,
                                         "pinned_document_type": None, "excluded_categories": [],
                                         "aliases": [], "reviewed": False}}
        self._insert_doc("B")
        resp = self._client().get("/senders/~audit")
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json()]
        assert "B" in names

    def test_audit_detects_stopword(self):
        storage.sender_registry = {"Und": {"categories": ["Sonstiges"], "pinned_category": None,
                                           "pinned_document_type": None, "excluded_categories": [],
                                           "aliases": [], "reviewed": False}}
        self._insert_doc("Und")
        resp = self._client().get("/senders/~audit")
        assert resp.status_code == 200
        entry = next((r for r in resp.json() if r["name"] == "Und"), None)
        assert entry is not None
        assert entry["reason"] == "stoppwort"

    def test_audit_detects_document_type_as_sender(self):
        storage.sender_registry = {"Kontoauszug": {"categories": ["Bank & Finanzen"], "pinned_category": None,
                                                   "pinned_document_type": None, "excluded_categories": [],
                                                   "aliases": [], "reviewed": False}}
        self._insert_doc("Kontoauszug")
        resp = self._client().get("/senders/~audit")
        assert resp.status_code == 200
        entry = next((r for r in resp.json() if r["name"] == "Kontoauszug"), None)
        assert entry is not None
        assert entry["reason"] == "dokumenttyp_als_absender"

    def test_audit_passes_valid_sender(self):
        storage.sender_registry = {"Postbank": {"categories": ["Bank & Finanzen"], "pinned_category": None,
                                                "pinned_document_type": None, "excluded_categories": [],
                                                "aliases": [], "reviewed": False}}
        self._insert_doc("Postbank")
        resp = self._client().get("/senders/~audit")
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json()]
        assert "Postbank" not in names

    def test_audit_includes_doc_count(self):
        import time
        storage.sender_registry = {"DE": {"categories": ["Sonstiges"], "pinned_category": None,
                                          "pinned_document_type": None, "excluded_categories": [],
                                          "aliases": [], "reviewed": False}}
        db.upsert_document(file_path="/tmp/de_doc1.pdf", filename="de_doc1.pdf",
                           sender="DE", date="2024-01-01", document_type="Sonstiges",
                           category="Sonstiges", summary="Test 1",
                           content_hash=f"hash_de_1_{time.time_ns()}", status="ok")
        db.upsert_document(file_path="/tmp/de_doc2.pdf", filename="de_doc2.pdf",
                           sender="DE", date="2024-02-01", document_type="Sonstiges",
                           category="Sonstiges", summary="Test 2",
                           content_hash=f"hash_de_2_{time.time_ns()}", status="ok")
        resp = self._client().get("/senders/~audit")
        entry = next((r for r in resp.json() if r["name"] == "DE"), None)
        assert entry is not None
        assert entry["doc_count"] == 2


# ---------------------------------------------------------------------------
# Plan 4 – GET /senders/~ambiguous
# ---------------------------------------------------------------------------

class TestAmbiguousEndpoint:
    def _client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def _insert_doc(self, sender, category):
        import hashlib, time
        unique = hashlib.md5(f"{sender}{category}{time.time_ns()}".encode()).hexdigest()[:12]
        doc_id = db.upsert_document(
            file_path=f"/tmp/{sender}_{category}_{unique}.pdf",
            filename=f"{sender}_{category}.pdf",
            sender=sender,
            date="2024-01-01",
            document_type="Sonstiges",
            category=category,
            summary="Test",
            content_hash=unique,
            status="ok",
        )
        return doc_id

    def test_ambiguous_returns_senders_above_threshold(self):
        for cat in ["Bank & Finanzen", "Versicherung", "Sonstiges"]:
            self._insert_doc("Sparkasse", cat)
        resp = self._client().get("/senders/~ambiguous?min_categories=3")
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json()]
        assert "Sparkasse" in names

    def test_ambiguous_excludes_below_threshold(self):
        self._insert_doc("Telekom", "Kommunikation")
        self._insert_doc("Telekom", "Sonstiges")
        resp = self._client().get("/senders/~ambiguous?min_categories=3")
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json()]
        assert "Telekom" not in names

    def test_ambiguous_includes_majority_category(self):
        for _ in range(5):
            self._insert_doc("Amazon", "Einkauf & Bestellungen")
        self._insert_doc("Amazon", "Kommunikation")
        self._insert_doc("Amazon", "Sonstiges")
        resp = self._client().get("/senders/~ambiguous?min_categories=3")
        entry = next((r for r in resp.json() if r["name"] == "Amazon"), None)
        assert entry is not None
        assert entry["majority_category"] == "Einkauf & Bestellungen"
        assert entry["majority_pct"] > 50


# ---------------------------------------------------------------------------
# Plan 1 – Cascade helpers: update_vendor, update_provider, update_partner
# ---------------------------------------------------------------------------

class TestCascadeHelpers:
    def _make_doc(self, tmp_path):
        doc_id = db.upsert_document(
            file_path=str(tmp_path / "test.pdf"),
            filename="test.pdf",
            sender="AltFirma",
            date="2024-01-01",
            document_type="Rechnung",
            category="Sonstiges",
            summary="Test",
            content_hash="hash_cascade",
            status="ok",
        )
        return doc_id

    def test_update_vendor_for_document(self, tmp_path):
        from db.items_repo import update_vendor_for_document, insert_items
        doc_id = self._make_doc(tmp_path)
        insert_items(doc_id, [{"name": "Widget", "quantity": 1, "unit_price": 10.0,
                               "total_price": 10.0, "currency": "EUR",
                               "vendor": "AltFirma", "category": None,
                               "warranty_until": None, "notes": None}], "2024-01-01")
        updated = update_vendor_for_document(doc_id, "NeuFirma")
        assert updated == 1
        with get_conn() as conn:
            row = conn.execute("SELECT vendor FROM items WHERE document_id = ?", (doc_id,)).fetchone()
        assert row["vendor"] == "NeuFirma"

    def test_update_provider_for_document(self, tmp_path):
        from db.services_repo import update_provider_for_document, insert_services
        doc_id = self._make_doc(tmp_path)
        insert_services(doc_id, [{"name": "Service A", "description": None,
                                  "provider": "AltFirma", "service_date": None,
                                  "amount": 50.0, "currency": "EUR",
                                  "category": None, "notes": None}], "2024-01-01")
        updated = update_provider_for_document(doc_id, "NeuFirma")
        assert updated == 1
        with get_conn() as conn:
            row = conn.execute("SELECT provider FROM services WHERE document_id = ?", (doc_id,)).fetchone()
        assert row["provider"] == "NeuFirma"

    def test_update_partner_for_document(self, tmp_path):
        from db.contracts_repo import update_partner_for_document, insert_contract
        doc_id = self._make_doc(tmp_path)
        insert_contract(doc_id, {
            "partner": "AltFirma", "description": "Test Vertrag",
            "category": "Kommunikation", "status": "active",
            "amount": 10.0, "amount_interval": "monthly",
            "start_date": "2024-01-01", "end_date": None,
            "next_due_date": None, "cancellation_deadline": None,
            "notice_period_days": None, "auto_renews": False, "notes": None,
        }, "2024-01-01")
        updated = update_partner_for_document(doc_id, "NeuFirma")
        assert updated == 1
        with get_conn() as conn:
            row = conn.execute("SELECT partner FROM contracts WHERE document_id = ?", (doc_id,)).fetchone()
        assert row["partner"] == "NeuFirma"

    def test_update_vendor_returns_zero_when_no_items(self, tmp_path):
        from db.items_repo import update_vendor_for_document
        doc_id = self._make_doc(tmp_path)
        updated = update_vendor_for_document(doc_id, "NeuFirma")
        assert updated == 0
