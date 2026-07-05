import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import db
import db.feedback_repo as feedback_repo


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield


def _entry(**overrides):
    data = dict(
        ts="2025-01-01T00:00:00",
        sender="Telekom",
        document_type="Rechnung",
        category="Kommunikation",
        summary="Monatsrechnung",
        corrected_fields=["category"],
    )
    data.update(overrides)
    return data


def test_get_all_empty():
    assert feedback_repo.get_all() == []


def test_insert_and_get_all():
    feedback_repo.insert(_entry())
    rows = feedback_repo.get_all()
    assert len(rows) == 1
    assert rows[0]["sender"] == "Telekom"


def test_insert_replaces_duplicate_key():
    feedback_repo.insert(_entry(category="Kommunikation", summary="Old"))
    feedback_repo.insert(_entry(category="Kommunikation", summary="New"))
    rows = feedback_repo.get_all()
    assert len(rows) == 1
    assert rows[0]["summary"] == "New"


def test_get_recent():
    for i in range(5):
        feedback_repo.insert(_entry(ts=f"2025-01-0{i+1}T00:00:00", sender=f"S{i}"))
    recent = feedback_repo.get_recent(n=1)
    assert len(recent) == 3
    assert recent[0]["sender"] == "S4"


def test_trim_respects_max():
    original = feedback_repo.MAX_EXAMPLES
    feedback_repo.MAX_EXAMPLES = 3
    try:
        for i in range(5):
            feedback_repo.insert(_entry(sender=f"S{i}", category=f"Cat{i}", document_type=f"Type{i}"))
        assert len(feedback_repo.get_all()) <= 3
    finally:
        feedback_repo.MAX_EXAMPLES = original


def test_import_from_list():
    feedback_repo.import_from_list([_entry(), _entry(sender="Vodafone", category="Sonstiges")])
    assert len(feedback_repo.get_all()) == 2


def test_row_to_dict_parses_corrected_fields():
    feedback_repo.insert(_entry(corrected_fields=["category", "sender"]))
    row = feedback_repo.get_all()[0]
    assert "category" in row["corrected_fields"]
    assert "sender" in row["corrected_fields"]
