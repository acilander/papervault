import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import db
import db.sender_repo as sender_repo


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield


def test_get_all_empty():
    assert sender_repo.get_all() == {}


def test_get_nonexistent_returns_none():
    assert sender_repo.get("Unknown") is None


def test_exists_false_for_empty_db():
    assert sender_repo.exists("Unknown") is False


def test_count_zero():
    assert sender_repo.count() == 0


def test_upsert_and_get():
    sender_repo.upsert("Telekom", {"categories": ["Kommunikation"], "pinned_category": None,
                                    "excluded_categories": [], "aliases": [], "reviewed": False})
    entry = sender_repo.get("Telekom")
    assert entry["categories"] == ["Kommunikation"]
    assert entry["pinned_category"] is None
    assert entry["reviewed"] is False


def test_upsert_replaces_entry():
    sender_repo.upsert("Telekom", {"categories": ["Kommunikation"]})
    sender_repo.upsert("Telekom", {"categories": ["Kommunikation", "Sonstiges"], "pinned_category": "Sonstiges"})
    entry = sender_repo.get("Telekom")
    assert "Sonstiges" in entry["categories"]
    assert entry["pinned_category"] == "Sonstiges"


def test_update_partial():
    sender_repo.upsert("Telekom", {"categories": ["Kommunikation"]})
    sender_repo.update("Telekom", pinned_category="Kommunikation")
    assert sender_repo.get("Telekom")["pinned_category"] == "Kommunikation"


def test_update_nonexistent_is_noop():
    sender_repo.update("Ghost", pinned_category="X")
    assert sender_repo.get("Ghost") is None


def test_record_category_creates_sender():
    changed = sender_repo.record_category("Telekom", "Kommunikation")
    assert changed is True
    assert sender_repo.exists("Telekom")


def test_record_category_no_duplicate():
    sender_repo.record_category("Telekom", "Kommunikation")
    changed = sender_repo.record_category("Telekom", "Kommunikation")
    assert changed is False


def test_record_category_adds_second_category():
    sender_repo.record_category("Telekom", "Kommunikation")
    sender_repo.record_category("Telekom", "Sonstiges")
    assert sender_repo.get("Telekom")["categories"] == ["Kommunikation", "Sonstiges"]


def test_rename_preserves_alias():
    sender_repo.upsert("Telekom", {"categories": ["Kommunikation"], "aliases": ["T-Mobile"]})
    sender_repo.rename("Telekom", "Telekom Deutschland")
    assert sender_repo.get("Telekom") is None
    new = sender_repo.get("Telekom Deutschland")
    assert "Telekom" in new["aliases"]
    assert "T-Mobile" in new["aliases"]


def test_delete_removes_sender():
    sender_repo.upsert("Telekom", {"categories": ["Kommunikation"]})
    sender_repo.delete("Telekom")
    assert sender_repo.get("Telekom") is None



def test_import_from_dict_new_format():
    sender_repo.import_from_dict({
        "Telekom": {"categories": ["Kommunikation"], "pinned_category": "Kommunikation", "reviewed": True},
    })
    entry = sender_repo.get("Telekom")
    assert entry["pinned_category"] == "Kommunikation"
    assert entry["reviewed"] is True
