import json
import os
import threading
from datetime import datetime

from config import SENDERS_FILE, LOG_FILE, CATEGORIES
from utils import log

# ── Locks & In-memory state ───────────────────────────────────────────────────
_registry_lock = threading.RLock()
sender_registry: dict = {}
content_hashes: dict = {}



# ── Processing log ───────────────────────────────────────────────────────────

def processing_log(filename, status, data=None, error=None, features=None, user_hint=None):
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "file": filename,
        "status": status,
    }
    if data:
        entry["classification"] = data
    if error:
        entry["error"] = error
    if features:
        entry["features"] = {
            "category_candidates": features.get("category_candidates", []),
            "type_candidate": features.get("type_candidate"),
            "has_amount": features.get("has_amount"),
            "has_iban": features.get("has_iban"),
            "has_tax_id": features.get("has_tax_id"),
            "page_count": features.get("page_count"),
            "type_from_filename": features.get("type_from_filename"),
        }
    if user_hint:
        entry["user_hint"] = user_hint
    with _registry_lock:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass


# ── Hash registry ─────────────────────────────────────────────────────────────

def load_hashes():
    global content_hashes
    with _registry_lock:
        try:
            import db as _db
            with _db.get_conn() as conn:
                rows = conn.execute(
                    "SELECT content_hash, file_path FROM documents WHERE content_hash IS NOT NULL AND status='ok'"
                ).fetchall()
            content_hashes = {r["content_hash"]: r["file_path"] for r in rows}
            log(f"Hash-Register geladen: {len(content_hashes)} Eintraege (aus DB).")
        except Exception as e:
            log(f"Hash-Register konnte nicht aus DB geladen werden: {e}")
            content_hashes = {}


# ── Sender registry ───────────────────────────────────────────────────────────

def load_sender_registry():
    global sender_registry
    with _registry_lock:
        if not os.path.exists(SENDERS_FILE):
            sender_registry = {}
            return
        try:
            with open(SENDERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Migrate old format {category: [sender, ...]} -> {sender: {categories, pinned_category}}
            if data and isinstance(next(iter(data.values())), list):
                log("Absender-Register: migriere altes Format...")
                migrated = {}
                for cat, senders in data.items():
                    for s in senders:
                        if s not in migrated:
                            migrated[s] = {"categories": [], "pinned_category": None}
                        if cat not in migrated[s]["categories"]:
                            migrated[s]["categories"].append(cat)
                data = migrated
                with open(SENDERS_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            sender_registry = data
            pinned = sum(1 for v in sender_registry.values() if v.get("pinned_category"))
            log(f"Absender-Register geladen: {len(sender_registry)} Absender, {pinned} mit fester Kategorie.")
        except Exception as e:
            log(f"Absender-Register konnte nicht geladen werden: {e}")
            sender_registry = {}


def record_sender(category, sender):
    if not sender or not category:
        return
    changed = False
    if sender not in sender_registry:
        sender_registry[sender] = {"categories": [], "pinned_category": None, "reviewed": False, "excluded_categories": []}
        changed = True
    entry = sender_registry[sender]
    if category not in entry["categories"]:
        entry["categories"].append(category)
        entry["categories"].sort()
        changed = True
    if changed:
        try:
            with open(SENDERS_FILE, "w", encoding="utf-8") as f:
                json.dump(dict(sorted(sender_registry.items())), f, ensure_ascii=False, indent=2)
        except Exception as e:
            log(f"Absender-Register konnte nicht gespeichert werden: {e}")


def apply_sender_overrides(data):
    sender = data.get("sender")
    if not sender or sender not in sender_registry:
        return data
    entry = sender_registry[sender]
    pinned = entry.get("pinned_category")
    excluded = entry.get("excluded_categories", [])
    if pinned and pinned in CATEGORIES:
        if data.get("category") != pinned:
            log(f"Kategorie durch Absender-Register ueberschrieben: '{data['category']}' -> '{pinned}' (Absender: {sender})")
            data["category"] = pinned
    elif excluded and data.get("category") in excluded:
        fallback = next((c for c in entry.get("categories", []) if c not in excluded), "Sonstiges")
        log(f"Kategorie '{data['category']}' ist gesperrt fuer '{sender}', verwende '{fallback}'")
        data["category"] = fallback
    return data
