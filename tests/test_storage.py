import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import json
import storage
import db
import db.sender_repo as sender_repo
from unittest.mock import patch
import config


def _reset():
    storage.sender_registry = {}
    storage.content_hashes = {}
    sender_repo._clear_all_for_tests()


def test_apply_sender_overrides_no_registry():
    _reset()
    data = {"sender": "ING", "category": "Sonstiges"}
    result = storage.apply_sender_overrides(data)
    assert result["category"] == "Sonstiges"


def test_apply_sender_overrides_with_pinned():
    _reset()
    storage.sender_registry["ING"] = {"categories": ["Bank & Finanzen"], "pinned_category": "Bank & Finanzen"}
    data = {"sender": "ING", "category": "Wohnen & Eigentum"}
    result = storage.apply_sender_overrides(data)
    assert result["category"] == "Bank & Finanzen"


def test_apply_sender_overrides_no_pin_unchanged():
    _reset()
    storage.sender_registry["ING"] = {"categories": ["Bank & Finanzen"], "pinned_category": None}
    data = {"sender": "ING", "category": "Wohnen & Eigentum"}
    result = storage.apply_sender_overrides(data)
    assert result["category"] == "Wohnen & Eigentum"


def test_apply_sender_overrides_invalid_pin_ignored():
    _reset()
    storage.sender_registry["X"] = {"categories": [], "pinned_category": "Nicht-Existente-Kategorie"}
    data = {"sender": "X", "category": "Sonstiges"}
    result = storage.apply_sender_overrides(data)
    assert result["category"] == "Sonstiges"


def test_record_sender_adds_new():
    _reset()
    storage.record_sender("Bank & Finanzen", "Sparkasse")
    assert "Sparkasse" in storage.sender_registry
    assert "Bank & Finanzen" in storage.sender_registry["Sparkasse"]["categories"]


def test_record_sender_no_duplicate_category():
    _reset()
    storage.record_sender("Bank & Finanzen", "Sparkasse")
    storage.record_sender("Bank & Finanzen", "Sparkasse")
    assert storage.sender_registry["Sparkasse"]["categories"].count("Bank & Finanzen") == 1


def test_processing_log_writes_jsonl(tmp_path, monkeypatch):
    _reset()
    log_file = tmp_path / "log.jsonl"
    monkeypatch.setattr(storage, "LOG_FILE", str(log_file))
    storage.processing_log("file.pdf", "ok", data={"category": "Bank"}, features={"page_count": 2})
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    entry = json.loads(content)
    assert entry["file"] == "file.pdf"
    assert entry["status"] == "ok"


def test_load_hashes_from_db(tmp_path, monkeypatch):
    _reset()
    import db
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO documents (file_path, filename, content_hash, status, archived_at) VALUES (?,?,?,?,?)",
            ("/a/x.pdf", "x.pdf", "h123", "ok", "2025-01-01")
        )
    storage.load_hashes()
    assert storage.content_hashes.get("h123") == "/a/x.pdf"


def test_migrate_from_json_old_format(tmp_path, monkeypatch):
    _reset()
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    senders_file = tmp_path / "senders.json"
    senders_file.write_text(json.dumps({"Kommunikation": ["Telekom", "Vodafone"], "Versicherung": ["Allianz"]}))
    monkeypatch.setattr(config, "SENDERS_FILE", str(senders_file))
    storage._migrate_from_json()
    assert sender_repo.exists("Telekom")
    assert sender_repo.exists("Vodafone")
    assert "Kommunikation" in sender_repo.get("Telekom")["categories"]


def test_apply_sender_overrides_excluded_category():
    _reset()
    storage.sender_registry["X"] = {"categories": ["Bank & Finanzen", "Sonstiges"], "pinned_category": None, "excluded_categories": ["Bank & Finanzen"]}
    data = {"sender": "X", "category": "Bank & Finanzen"}
    result = storage.apply_sender_overrides(data)
    assert result["category"] == "Sonstiges"


def test_load_sender_registry_migrates_when_empty(tmp_path, monkeypatch):
    _reset()
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    senders_file = tmp_path / "senders.json"
    senders_file.write_text(json.dumps({"Bank & Finanzen": ["Sparkasse"]}))
    monkeypatch.setattr(config, "SENDERS_FILE", str(senders_file))
    storage.load_sender_registry()
    assert "Sparkasse" in storage.sender_registry
