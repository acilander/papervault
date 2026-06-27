import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import storage


def _reset():
    storage.sender_registry = {}
    storage.content_hashes = {}


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


def test_record_sender_adds_new(tmp_path, monkeypatch):
    _reset()
    monkeypatch.setattr(storage, "SENDERS_FILE", str(tmp_path / "senders.json"))
    storage.record_sender("Bank & Finanzen", "Sparkasse")
    assert "Sparkasse" in storage.sender_registry
    assert "Bank & Finanzen" in storage.sender_registry["Sparkasse"]["categories"]


def test_record_sender_no_duplicate_category(tmp_path, monkeypatch):
    _reset()
    monkeypatch.setattr(storage, "SENDERS_FILE", str(tmp_path / "senders.json"))
    storage.record_sender("Bank & Finanzen", "Sparkasse")
    storage.record_sender("Bank & Finanzen", "Sparkasse")
    assert storage.sender_registry["Sparkasse"]["categories"].count("Bank & Finanzen") == 1
