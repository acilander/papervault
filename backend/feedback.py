"""
feedback.py – Sammelt manuelle Korrekturen aus der GUI als Few-Shot-Beispiele.
Persistenz: SQLite-Tabelle `feedback` via db.feedback_repo.
"""
import json
import os
from datetime import datetime

import db.feedback_repo as feedback_repo


def _migrate_from_json():
    """One-time migration: import feedback.json into DB if it exists and DB is empty."""
    from config import FEEDBACK_FILE
    if not os.path.exists(FEEDBACK_FILE):
        return
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data:
            feedback_repo.import_from_list(data)
    except Exception:
        pass


def record_correction(original: dict, corrected: dict):
    """
    Call this when the user saves edits in the GUI.
    original: the doc dict before edit (from DB)
    corrected: the new values dict (DocumentUpdate body)
    """
    corrected_fields = [
        k for k in ("sender", "document_type", "category", "summary")
        if corrected.get(k) and corrected.get(k) != original.get(k)
    ]
    if not corrected_fields:
        return

    example = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "sender": corrected.get("sender") or original.get("sender"),
        "document_type": corrected.get("document_type") or original.get("document_type"),
        "category": corrected.get("category") or original.get("category"),
        "summary": corrected.get("summary") or original.get("summary"),
        "corrected_fields": corrected_fields,
    }
    feedback_repo.insert(example)


def get_few_shot_examples(n: int = 20) -> list:
    """Return the n most recent unique examples for LLM prompt injection."""
    examples = feedback_repo.get_recent(n * 3)
    corrected = [e for e in examples if "category" in e.get("corrected_fields", [])]
    others = [e for e in examples if "category" not in e.get("corrected_fields", [])]
    combined = corrected[-n:] + others[-(max(0, n - len(corrected))):] if len(corrected) < n else corrected[-n:]
    return combined[:n]


def build_few_shot_prompt(n: int = 15) -> str:
    """Build a prompt snippet with few-shot examples to prepend to LLM context."""
    examples = get_few_shot_examples(n)
    if not examples:
        return ""

    lines = ["\n\nBewährte Klassifizierungen aus dem Archiv (vom Nutzer bestätigt):"]
    for e in examples:
        fields = []
        if e.get("sender"):
            fields.append(f"sender: {e['sender']}")
        if e.get("document_type"):
            fields.append(f"document_type: {e['document_type']}")
        if e.get("category"):
            fields.append(f"category: {e['category']}")
        if fields:
            lines.append("  - " + ", ".join(fields))
    return "\n".join(lines)
