import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import storage


def _reset():
    storage.sender_registry = {}
    storage.content_hashes = {}


# ── reviewed flag ─────────────────────────────────────────────────────────────

def test_new_sender_has_reviewed_false(tmp_path, monkeypatch):
    _reset()
    monkeypatch.setattr(storage, "SENDERS_FILE", str(tmp_path / "senders.json"))
    storage.record_sender("Bank & Finanzen", "Sparkasse")
    assert storage.sender_registry["Sparkasse"]["reviewed"] is False


def test_new_sender_has_excluded_categories_empty(tmp_path, monkeypatch):
    _reset()
    monkeypatch.setattr(storage, "SENDERS_FILE", str(tmp_path / "senders.json"))
    storage.record_sender("Bank & Finanzen", "Sparkasse")
    assert storage.sender_registry["Sparkasse"]["excluded_categories"] == []


def test_existing_sender_not_reset_reviewed(tmp_path, monkeypatch):
    _reset()
    monkeypatch.setattr(storage, "SENDERS_FILE", str(tmp_path / "senders.json"))
    storage.record_sender("Bank & Finanzen", "Sparkasse")
    storage.sender_registry["Sparkasse"]["reviewed"] = True
    storage.record_sender("Versicherung", "Sparkasse")  # add second category
    assert storage.sender_registry["Sparkasse"]["reviewed"] is True


# ── excluded_categories in apply_sender_overrides ─────────────────────────────

def test_excluded_category_triggers_fallback():
    _reset()
    storage.sender_registry["Telekom"] = {
        "categories": ["Kommunikation", "Sonstiges"],
        "pinned_category": None,
        "excluded_categories": ["Kommunikation"],
    }
    data = {"sender": "Telekom", "category": "Kommunikation"}
    result = storage.apply_sender_overrides(data)
    assert result["category"] != "Kommunikation"


def test_excluded_category_falls_back_to_first_non_excluded():
    _reset()
    storage.sender_registry["Telekom"] = {
        "categories": ["Kommunikation", "Sonstiges"],
        "pinned_category": None,
        "excluded_categories": ["Kommunikation"],
    }
    data = {"sender": "Telekom", "category": "Kommunikation"}
    result = storage.apply_sender_overrides(data)
    assert result["category"] == "Sonstiges"


def test_excluded_category_falls_back_to_sonstiges_if_all_excluded():
    _reset()
    storage.sender_registry["X"] = {
        "categories": ["Kommunikation"],
        "pinned_category": None,
        "excluded_categories": ["Kommunikation"],
    }
    data = {"sender": "X", "category": "Kommunikation"}
    result = storage.apply_sender_overrides(data)
    assert result["category"] == "Sonstiges"


def test_pinned_takes_priority_over_excluded():
    _reset()
    storage.sender_registry["ING"] = {
        "categories": ["Bank & Finanzen"],
        "pinned_category": "Bank & Finanzen",
        "excluded_categories": ["Bank & Finanzen"],  # contradictory, pinned wins
    }
    data = {"sender": "ING", "category": "Sonstiges"}
    result = storage.apply_sender_overrides(data)
    assert result["category"] == "Bank & Finanzen"


def test_no_excluded_categories_key_is_safe():
    _reset()
    storage.sender_registry["Old"] = {
        "categories": ["Sonstiges"],
        "pinned_category": None,
        # no excluded_categories key – old format
    }
    data = {"sender": "Old", "category": "Sonstiges"}
    result = storage.apply_sender_overrides(data)
    assert result["category"] == "Sonstiges"
