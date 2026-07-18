import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import db
import db.sender_repo as sender_repo
import db.identifiers_repo as repo

@pytest.fixture(autouse=True)
def init_test_db(monkeypatch, tmp_path):
    # Ensure fresh DB for each test run
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield

def test_add_and_get_identifiers():
    # Insert required sender first to satisfy foreign key
    sender_repo.upsert("Müller GmbH", {})

    # Insert a new identifier
    id1 = repo.add_identifier(
        sender_name="Müller GmbH",
        identifier_type="PERSONAL_NO",
        identifier_value="12345",
        label="Personalnummer Müller",
        target_category="Arbeit & Lohn",
        target_unit="EG"
    )
    assert id1 > 0

    # Retrieve all
    all_ids = repo.get_all_identifiers()
    assert len(all_ids) == 1
    assert all_ids[0]["sender_name"] == "Müller GmbH"
    assert all_ids[0]["identifier_type"] == "PERSONAL_NO"
    assert all_ids[0]["identifier_value"] == "12345"
    assert all_ids[0]["label"] == "Personalnummer Müller"
    assert all_ids[0]["target_category"] == "Arbeit & Lohn"
    assert all_ids[0]["target_unit"] == "EG"

    # Match existing
    sender, item = repo.match_existing_identifiers("Der Mitarbeiter mit der Nr. 12345 hat gearbeitet.")
    assert sender == "Müller GmbH"
    assert item["id"] == id1

    # Match case-insensitive
    sender2, item2 = repo.match_existing_identifiers("Nr. 12345")
    assert sender2 == "Müller GmbH"

    # No match
    sender3, item3 = repo.match_existing_identifiers("Kein match hier.")
    assert sender3 is None

    # Boundary checks: should NOT match inside longer numbers or letters
    sender_boundary, _ = repo.match_existing_identifiers("Mitarbeiter-Nr. 123456")
    assert sender_boundary is None

    sender_boundary2, _ = repo.match_existing_identifiers("Mitarbeiter-Nr. A12345B")
    assert sender_boundary2 is None

    # Delete
    assert repo.delete_identifier(id1) is True
    assert len(repo.get_all_identifiers()) == 0

def test_unassigned_identifiers():
    # Insert required sender first to satisfy foreign key
    sender_repo.upsert("Sparkasse", {})

    # Create a document first to reference
    doc_id = db.upsert_document(
        file_path="/archive/test.pdf",
        filename="test.pdf",
        sender=None, date=None, document_type=None, category=None, summary=None
    )

    # Save unassigned suggestion
    assert repo.save_unassigned_identifier(doc_id, "IBAN", "DE123456789", "IBAN: DE123456789") is True
    
    # Get unassigned
    unassigned = repo.get_unassigned_identifiers()
    assert len(unassigned) == 1
    assert unassigned[0]["document_id"] == doc_id
    assert unassigned[0]["identifier_value"] == "DE123456789"
    assert unassigned[0]["document_filename"] == "test.pdf"

    # Assign it to a sender
    new_id = repo.assign_unassigned_identifier(unassigned[0]["id"], "Sparkasse", "Konto Sparkasse", "Finanzen", "OG")
    assert new_id > 0

    # Confirmed list should have it now
    confirmed = repo.get_all_identifiers()
    assert len(confirmed) == 1
    assert confirmed[0]["sender_name"] == "Sparkasse"
    assert confirmed[0]["identifier_value"] == "DE123456789"
    assert confirmed[0]["target_category"] == "Finanzen"
    assert confirmed[0]["target_unit"] == "OG"

    # Unassigned list should be empty
    assert len(repo.get_unassigned_identifiers()) == 0
