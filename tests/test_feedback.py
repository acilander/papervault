import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import json
import pytest
import feedback


@pytest.fixture(autouse=True)
def tmp_feedback(monkeypatch, tmp_path):
    monkeypatch.setattr(feedback, "FEEDBACK_FILE", str(tmp_path / "feedback.json"))
    yield


# ── load/save ─────────────────────────────────────────────────────────────────

def test_load_empty_if_no_file():
    assert feedback.load_feedback() == []


def test_save_and_load_roundtrip():
    examples = [{"sender": "Telekom", "category": "Kommunikation", "corrected_fields": ["category"]}]
    feedback.save_feedback(examples)
    assert feedback.load_feedback() == examples


# ── record_correction ─────────────────────────────────────────────────────────

def test_record_correction_saves_on_change():
    original = {"sender": "Telekom", "category": "Sonstiges", "document_type": "Rechnung", "summary": "Monatsrechnung"}
    corrected = {"category": "Kommunikation"}
    feedback.record_correction(original, corrected)
    examples = feedback.load_feedback()
    assert len(examples) == 1
    assert examples[0]["category"] == "Kommunikation"
    assert "category" in examples[0]["corrected_fields"]


def test_record_correction_no_save_if_unchanged():
    original = {"sender": "Telekom", "category": "Kommunikation"}
    corrected = {"category": "Kommunikation"}
    feedback.record_correction(original, corrected)
    assert feedback.load_feedback() == []


def test_record_correction_deduplicates():
    original = {"sender": "Telekom", "category": "Sonstiges", "document_type": "Rechnung", "summary": "x"}
    corrected = {"category": "Kommunikation", "document_type": "Rechnung"}
    feedback.record_correction(original, corrected)
    feedback.record_correction(original, corrected)
    examples = feedback.load_feedback()
    assert len(examples) == 1


def test_record_correction_multiple_fields():
    original = {"sender": "Allianz", "category": "Sonstiges", "document_type": "Brief", "summary": "x"}
    corrected = {"sender": "Allianz GmbH", "category": "Versicherung", "document_type": "Police"}
    feedback.record_correction(original, corrected)
    ex = feedback.load_feedback()[0]
    assert "category" in ex["corrected_fields"]
    assert "document_type" in ex["corrected_fields"]
    assert "sender" in ex["corrected_fields"]


# ── get_few_shot_examples ─────────────────────────────────────────────────────

def test_get_few_shot_examples_returns_n():
    for i in range(25):
        feedback.save_feedback(feedback.load_feedback() + [{
            "sender": f"Sender{i}", "category": "Sonstiges",
            "document_type": "Rechnung", "summary": "x",
            "corrected_fields": ["category"], "ts": "2025-01-01T00:00:00"
        }])
    examples = feedback.get_few_shot_examples(n=10)
    assert len(examples) == 10


def test_get_few_shot_prefers_category_corrections():
    # Use unique senders so deduplication doesn't collapse entries
    non_cat = [{"sender": f"NonCat{i}", "category": "Sonstiges", "document_type": "x",
                "summary": "s", "corrected_fields": ["sender"], "ts": "2025-01-01T00:00:00"}
               for i in range(5)]
    cat = [{"sender": f"CatSender{i}", "category": "Kommunikation", "document_type": "x",
            "summary": "s", "corrected_fields": ["category"], "ts": "2025-01-01T00:00:00"}
           for i in range(5)]
    feedback.save_feedback(non_cat + cat)
    examples = feedback.get_few_shot_examples(n=5)
    # category-corrected ones should appear first/be prioritized
    cat_count = sum(1 for e in examples if "category" in e.get("corrected_fields", []))
    assert cat_count >= 3


# ── build_few_shot_prompt ─────────────────────────────────────────────────────

def test_build_few_shot_prompt_empty_if_no_data():
    assert feedback.build_few_shot_prompt() == ""


def test_build_few_shot_prompt_contains_sender():
    feedback.save_feedback([{
        "sender": "Telekom", "category": "Kommunikation",
        "document_type": "Rechnung", "summary": "x",
        "corrected_fields": ["category"], "ts": "2025-01-01T00:00:00"
    }])
    prompt = feedback.build_few_shot_prompt()
    assert "Telekom" in prompt
    assert "Kommunikation" in prompt


def test_build_few_shot_prompt_has_header():
    feedback.save_feedback([{
        "sender": "X", "category": "Sonstiges",
        "document_type": "Brief", "summary": "y",
        "corrected_fields": ["category"], "ts": "2025-01-01T00:00:00"
    }])
    prompt = feedback.build_few_shot_prompt()
    assert "Klassifizierungen" in prompt


# ── max cap ───────────────────────────────────────────────────────────────────

def test_feedback_capped_at_max():
    original_max = feedback.MAX_EXAMPLES
    feedback.MAX_EXAMPLES = 5
    try:
        for i in range(10):
            original = {"sender": f"S{i}", "category": "alt", "document_type": "R", "summary": "x"}
            corrected = {"category": "Kommunikation", "document_type": "R"}
            feedback.record_correction(original, corrected)
        assert len(feedback.load_feedback()) <= 5
    finally:
        feedback.MAX_EXAMPLES = original_max
