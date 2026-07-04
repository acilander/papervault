import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import feedback
import db.feedback_repo as feedback_repo


@pytest.fixture(autouse=True)
def clean_db():
    feedback_repo._clear_all_for_tests()
    yield
    feedback_repo._clear_all_for_tests()


def _insert(sender, category, doc_type="Rechnung", corrected_fields=None):
    feedback_repo.insert({
        "ts": "2025-01-01T00:00:00",
        "sender": sender,
        "category": category,
        "document_type": doc_type,
        "summary": "x",
        "corrected_fields": corrected_fields or ["category"],
    })


# ── record_correction ─────────────────────────────────────────────────────────

def test_record_correction_saves_on_change():
    original = {"sender": "Telekom", "category": "Sonstiges", "document_type": "Rechnung", "summary": "Monatsrechnung"}
    corrected = {"category": "Kommunikation"}
    feedback.record_correction(original, corrected)
    examples = feedback_repo.get_all()
    assert len(examples) == 1
    assert examples[0]["category"] == "Kommunikation"
    assert "category" in examples[0]["corrected_fields"]


def test_record_correction_no_save_if_unchanged():
    original = {"sender": "Telekom", "category": "Kommunikation"}
    corrected = {"category": "Kommunikation"}
    feedback.record_correction(original, corrected)
    assert feedback_repo.get_all() == []


def test_record_correction_deduplicates():
    original = {"sender": "Telekom", "category": "Sonstiges", "document_type": "Rechnung", "summary": "x"}
    corrected = {"category": "Kommunikation", "document_type": "Rechnung"}
    feedback.record_correction(original, corrected)
    feedback.record_correction(original, corrected)
    assert len(feedback_repo.get_all()) == 1


def test_record_correction_multiple_fields():
    original = {"sender": "Allianz", "category": "Sonstiges", "document_type": "Brief", "summary": "x"}
    corrected = {"sender": "Allianz GmbH", "category": "Versicherung", "document_type": "Police"}
    feedback.record_correction(original, corrected)
    ex = feedback_repo.get_all()[0]
    assert "category" in ex["corrected_fields"]
    assert "document_type" in ex["corrected_fields"]
    assert "sender" in ex["corrected_fields"]


# ── get_few_shot_examples ─────────────────────────────────────────────────────

def test_get_few_shot_examples_returns_n():
    for i in range(25):
        _insert(f"Sender{i}", "Sonstiges")
    examples = feedback.get_few_shot_examples(n=10)
    assert len(examples) == 10


def test_get_few_shot_prefers_category_corrections():
    for i in range(5):
        _insert(f"NonCat{i}", "Sonstiges", corrected_fields=["sender"])
    for i in range(5):
        _insert(f"CatSender{i}", "Kommunikation", corrected_fields=["category"])
    examples = feedback.get_few_shot_examples(n=5)
    cat_count = sum(1 for e in examples if "category" in e.get("corrected_fields", []))
    assert cat_count >= 3


# ── build_few_shot_prompt ─────────────────────────────────────────────────────

def test_build_few_shot_prompt_empty_if_no_data():
    assert feedback.build_few_shot_prompt() == ""


def test_build_few_shot_prompt_contains_sender():
    _insert("Telekom", "Kommunikation")
    prompt = feedback.build_few_shot_prompt()
    assert "Telekom" in prompt
    assert "Kommunikation" in prompt


def test_build_few_shot_prompt_has_header():
    _insert("X", "Sonstiges")
    prompt = feedback.build_few_shot_prompt()
    assert "Klassifizierungen" in prompt


# ── max cap ───────────────────────────────────────────────────────────────────

def test_feedback_capped_at_max():
    original_max = feedback_repo.MAX_EXAMPLES
    feedback_repo.MAX_EXAMPLES = 5
    try:
        for i in range(10):
            original = {"sender": f"S{i}", "category": "alt", "document_type": "R", "summary": "x"}
            corrected = {"category": "Kommunikation", "document_type": "R"}
            feedback.record_correction(original, corrected)
        assert len(feedback_repo.get_all()) <= 5
    finally:
        feedback_repo.MAX_EXAMPLES = original_max
