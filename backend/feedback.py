"""
feedback.py – Sammelt manuelle Korrekturen aus der GUI als Few-Shot-Beispiele.

Format von feedback.json:
[
  {
    "ts": "2024-01-15T10:30:00",
    "sender": "Deutsche Telekom AG",
    "document_type": "Rechnung",
    "category": "Kommunikation",
    "summary": "Monatsrechnung für Mobilfunkvertrag",
    "corrected_fields": ["category"]   # welche Felder der User geändert hat
  },
  ...
]
"""
import json
import os
from datetime import datetime

from config import FEEDBACK_FILE

MAX_EXAMPLES = 200  # Maximale Anzahl gespeicherter Beispiele


def load_feedback() -> list:
    if not os.path.exists(FEEDBACK_FILE):
        return []
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_feedback(examples: list):
    try:
        with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(examples, f, ensure_ascii=False, indent=2)
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
        return  # No meaningful change

    example = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "sender": corrected.get("sender") or original.get("sender"),
        "document_type": corrected.get("document_type") or original.get("document_type"),
        "category": corrected.get("category") or original.get("category"),
        "summary": corrected.get("summary") or original.get("summary"),
        "corrected_fields": corrected_fields,
    }

    examples = load_feedback()
    # Deduplicate: remove older entry with same sender+category+type
    examples = [
        e for e in examples
        if not (e.get("sender") == example["sender"]
                and e.get("category") == example["category"]
                and e.get("document_type") == example["document_type"])
    ]
    examples.append(example)
    # Keep most recent MAX_EXAMPLES
    examples = examples[-MAX_EXAMPLES:]
    save_feedback(examples)


def get_few_shot_examples(n: int = 20) -> list:
    """Return the n most recent unique examples for LLM prompt injection."""
    examples = load_feedback()
    # Prefer examples where user corrected the category (most valuable signal)
    corrected = [e for e in examples if "category" in e.get("corrected_fields", [])]
    others = [e for e in examples if "category" not in e.get("corrected_fields", [])]
    # Take up to n, filling first from category-corrected, then others
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
