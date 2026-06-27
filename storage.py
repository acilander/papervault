import json
import os
from datetime import datetime

from config import SENDERS_FILE, HASHES_FILE, LOG_FILE, CATEGORIES

# ── In-memory state ──────────────────────────────────────────────────────────
sender_registry: dict = {}
content_hashes: dict = {}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Processing log ───────────────────────────────────────────────────────────

def processing_log(filename, status, data=None, error=None):
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "file": filename,
        "status": status,
    }
    if data:
        entry["classification"] = data
    if error:
        entry["error"] = error
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── Hash registry ─────────────────────────────────────────────────────────────

def load_hashes():
    global content_hashes
    if os.path.exists(HASHES_FILE):
        try:
            with open(HASHES_FILE, "r", encoding="utf-8") as f:
                content_hashes = json.load(f)
            log(f"Hash-Register geladen: {len(content_hashes)} Eintraege.")
        except Exception as e:
            log(f"Hash-Register konnte nicht geladen werden: {e}")
            content_hashes = {}
    else:
        content_hashes = {}


def save_hashes():
    try:
        with open(HASHES_FILE, "w", encoding="utf-8") as f:
            json.dump(content_hashes, f, ensure_ascii=False)
    except Exception as e:
        log(f"Hash-Register konnte nicht gespeichert werden: {e}")


# ── Sender registry ───────────────────────────────────────────────────────────

def load_sender_registry():
    global sender_registry
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
