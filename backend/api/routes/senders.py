import os
import shutil
from typing import Optional

from fastapi import APIRouter, HTTPException

import db
import storage
import db.sender_repo as sender_repo
from config import TARGET_BASE, CATEGORY_FOLDER_MAP, SENDER_SUBFOLDERS
from utils import log
from api.models import SenderEntry, SenderUpdate
from pdf_utils import build_filename, unique_path

router = APIRouter(prefix="/senders", tags=["senders"])


def _reload():
    storage.load_sender_registry()


@router.post("/~reload")
def reload_senders():
    """Reload sender registry from DB into memory."""
    storage.load_sender_registry()
    return {"reloaded": True, "count": len(storage.sender_registry)}


@router.post("/~rebuild")
def rebuild_senders():
    """Populate the sender registry from existing documents.

    Useful after the pipeline did not record senders for previously processed
    documents (e.g. before the fix was applied). Iterates over all documents
    with a non-empty sender and records their category.
    """
    log(f"[Registry] Baue Absender-Register aus Dokumenten auf (DB: {db.DB_PATH})...")
    added = 0
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT sender, category FROM documents WHERE sender IS NOT NULL AND sender != '' AND status = 'ok'"
        ).fetchall()
        for row in rows:
            if sender_repo.record_category(row["sender"], row["category"]):
                added += 1
    storage._refresh_cache()
    db_count = sender_repo.count()
    log(f"[Registry] Aufbau abgeschlossen: in-memory={len(storage.sender_registry)}, DB={db_count}, neu={added}")
    return {"rebuilt": True, "count": len(storage.sender_registry), "added": added}


@router.get("/", response_model=dict[str, SenderEntry])
def list_senders():
    return storage.sender_registry


@router.post("/~cleanup")
def cleanup_senders():
    """Delete all senders that have no documents with status='ok'."""
    with db.get_conn() as conn:
        rows = conn.execute(
            """SELECT name FROM senders
               WHERE name NOT IN (
                   SELECT DISTINCT sender FROM documents
                   WHERE status = 'ok' AND sender IS NOT NULL AND sender != ''
               )"""
        ).fetchall()
    deleted_names = [row["name"] for row in rows]
    for name in deleted_names:
        sender_repo.delete(name)
    storage._refresh_cache()
    log(f"[Sender] Cleanup: {len(deleted_names)} verwaiste Absender gelöscht.")
    return {"deleted": len(deleted_names), "names": deleted_names}


@router.get("/~audit")
def audit_senders():
    """Return senders that fail plausibility checks (too short, stopwords, generic terms, etc.)."""
    import re as _re
    from config import DOCUMENT_TYPES, CATEGORIES
    from categories import OWNER_NAMES

    _STOPWORDS = {"und", "der", "die", "das", "von", "bei", "für", "mit", "an", "am", "im", "zu", "zur", "zum"}
    _GENERIC = {
        "versicherung", "wohnung", "bank", "finanzen", "energie", "strom", "gas",
        "wasser", "rechnung", "abrechnung", "sonstiges", "unbekannt", "dokument",
        "brief", "schreiben", "mitteilung", "information", "anfrage", "angebot",
        "vertrag", "behörde", "behoerde", "amt", "verwaltung",
    }
    _ABBREV_RE = _re.compile(r'^(DE|AG|GmbH|UG|KG|eV|e\.V\.|Inc|Ltd|Corp|LLC)$', _re.IGNORECASE)
    _PLACEHOLDERS = {"null", "unbekannt", "unknown", "n/a", "???", "absender", "keine angabe", "nicht definiert", "nicht angegeben"}

    with db.get_conn() as conn:
        count_rows = conn.execute(
            "SELECT sender, COUNT(*) as cnt FROM documents WHERE status='ok' AND sender IS NOT NULL GROUP BY sender"
        ).fetchall()
    doc_counts = {r["sender"]: r["cnt"] for r in count_rows}

    results = []
    for name in list(storage.sender_registry.keys()):
        s = name.strip()
        sl = s.lower()
        reason = None
        if len(s) <= 2:
            reason = "zu_kurz"
        elif sl in _PLACEHOLDERS:
            reason = "platzhalter"
        elif sl in _STOPWORDS:
            reason = "stoppwort"
        elif s in DOCUMENT_TYPES:
            reason = "dokumenttyp_als_absender"
        elif sl in _GENERIC:
            reason = "generischer_Begriff"
        elif _ABBREV_RE.match(s):
            reason = "nur_kuerzel"
        elif any(owner in sl for owner in OWNER_NAMES):
            reason = "archivinhaber"
        if reason:
            results.append({
                "name": name,
                "reason": reason,
                "doc_count": doc_counts.get(name, 0),
            })

    results.sort(key=lambda x: x["doc_count"], reverse=True)
    return results


@router.get("/~ambiguous")
def ambiguous_senders(min_categories: int = 3):
    """Return senders with >= min_categories categories, with majority category stats."""
    with db.get_conn() as conn:
        count_rows = conn.execute(
            "SELECT sender, category, COUNT(*) as cnt FROM documents "
            "WHERE status='ok' AND sender IS NOT NULL AND category IS NOT NULL "
            "GROUP BY sender, category"
        ).fetchall()

    from collections import defaultdict
    sender_cats: dict[str, dict[str, int]] = defaultdict(dict)
    for row in count_rows:
        sender_cats[row["sender"]][row["category"]] = row["cnt"]

    results = []
    for name, cat_counts in sender_cats.items():
        if len(cat_counts) < min_categories:
            continue
        total = sum(cat_counts.values())
        majority_cat = max(cat_counts, key=lambda c: cat_counts[c])
        majority_n = cat_counts[majority_cat]
        results.append({
            "name": name,
            "categories": cat_counts,
            "doc_count": total,
            "majority_category": majority_cat,
            "majority_pct": round(majority_n / total * 100) if total else 0,
        })
    results.sort(key=lambda x: len(x["categories"]), reverse=True)
    return results


@router.post("/{name}/reclassify")
def reclassify_sender(name: str, body: dict):
    """Queue documents of a sender for reprocessing with a category hint.

    Body: { "target_category": str, "dry_run": bool (default false) }
    Only documents whose category != target_category are queued.
    """
    if name not in storage.sender_registry:
        raise HTTPException(status_code=404, detail="Absender nicht gefunden")

    target_category = (body.get("target_category") or "").strip()
    dry_run = bool(body.get("dry_run", False))

    if not target_category:
        raise HTTPException(status_code=400, detail="target_category ist erforderlich")

    docs = db.search_documents(sender=name, status="ok", limit=1000)
    affected = [d for d in docs if d.get("category") != target_category]

    if dry_run:
        return {
            "dry_run": True,
            "queued": 0,
            "preview": [{"id": d["id"], "filename": d.get("filename"), "category": d.get("category")} for d in affected],
        }

    queued = 0
    errors = []
    hint = (
        f"Dieser Absender ist bekannt als '{name}'. "
        f"Die überwiegende Mehrheit seiner Dokumente gehört zur Kategorie '{target_category}'. "
        f"Klassifiziere dieses Dokument erneut und bevorzuge diese Kategorie, "
        f"sofern der Dokumentinhalt dies rechtfertigt."
    )
    for doc in affected:
        path = doc.get("file_path") or ""
        if not os.path.exists(path):
            errors.append({"id": doc["id"], "error": "Datei nicht gefunden"})
            continue
        os.makedirs(SOURCE_DIR, exist_ok=True)
        inbox_path = unique_path(os.path.join(SOURCE_DIR, os.path.basename(path)))
        try:
            shutil.move(path, inbox_path)
            existing = db.get_document_by_path(inbox_path)
            if existing and existing["id"] != doc["id"]:
                db.delete_document(existing["id"])
            db.update_document(doc["id"], status="pending", file_path=inbox_path)
            hint_path = os.path.splitext(inbox_path)[0] + ".hint"
            with open(hint_path, "w", encoding="utf-8") as f:
                f.write(hint)
            queued += 1
        except Exception as e:
            errors.append({"id": doc["id"], "error": str(e)})

    return {"dry_run": False, "queued": queued, "errors": errors}


@router.get("/counts")
def sender_counts():
    """Return document count per sender in one query."""
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT sender, COUNT(*) as cnt FROM documents WHERE status='ok' GROUP BY sender"
        ).fetchall()
    return {row["sender"]: row["cnt"] for row in rows if row["sender"]}


@router.get("/{name}", response_model=SenderEntry)
def get_sender(name: str):
    if name not in storage.sender_registry:
        raise HTTPException(status_code=404, detail="Absender nicht gefunden")
    return storage.sender_registry[name]


@router.patch("/{name}", response_model=SenderEntry)
def update_sender(name: str, body: SenderUpdate):
    if name not in storage.sender_registry:
        raise HTTPException(status_code=404, detail="Absender nicht gefunden")
    entry = storage.sender_registry[name]
    if body.pinned_category is not None:
        entry["pinned_category"] = body.pinned_category or None
    if body.pinned_document_type is not None:
        entry["pinned_document_type"] = body.pinned_document_type or None
    if body.categories is not None:
        entry["categories"] = body.categories
    if body.reviewed is not None:
        entry["reviewed"] = body.reviewed
    if body.excluded_categories is not None:
        entry["excluded_categories"] = body.excluded_categories
    sender_repo.upsert(name, entry)
    storage._refresh_cache()
    return entry


@router.post("/~rename")
def rename_sender(body: dict):
    """
    Rename a sender to a new canonical name.
    The old name is preserved as an alias so the LLM can still recognize it.
    All DB documents are updated to the new name.
    body: { "old_name": str, "new_name": str }
    """
    name = (body.get("old_name") or "").strip()
    new_name = (body.get("new_name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="old_name darf nicht leer sein")
    if not new_name:
        raise HTTPException(status_code=400, detail="new_name darf nicht leer sein")
    if name not in storage.sender_registry:
        raise HTTPException(status_code=404, detail=f"Absender '{name}' nicht gefunden")
    if new_name in storage.sender_registry and new_name != name:
        raise HTTPException(status_code=409, detail=f"Absender '{new_name}' existiert bereits")
    if new_name == name:
        return {"renamed": False, "message": "Name unverändert"}

    sender_repo.rename(name, new_name)
    storage._refresh_cache()

    # Update all DB documents
    docs = db.search_documents(sender=name, limit=9999)
    for doc in docs:
        db.update_document(doc["id"], sender=new_name)

    return {
        "renamed": True,
        "old_name": name,
        "new_name": new_name,
        "alias_added": name,
        "docs_updated": len(docs),
        "entry": storage.sender_registry.get(new_name, {}),
    }


@router.post("/{name}/merge/{target}")
def merge_sender(name: str, target: str):
    """Merge 'name' into 'target': combine categories, move PDFs, reassign DB entries."""
    if name not in storage.sender_registry:
        raise HTTPException(status_code=404, detail=f"Absender '{name}' nicht gefunden")
    if target not in storage.sender_registry:
        raise HTTPException(status_code=404, detail=f"Ziel-Absender '{target}' nicht gefunden")

    src = storage.sender_registry[name]
    dst = storage.sender_registry[target]

    # Merge categories
    for cat in src["categories"]:
        if cat not in dst["categories"]:
            dst["categories"].append(cat)
    dst["categories"].sort()

    if not dst["pinned_category"] and src.get("pinned_category"):
        dst["pinned_category"] = src["pinned_category"]

    # Merge excluded_categories
    src_excl = src.get("excluded_categories", [])
    dst_excl = dst.get("excluded_categories", [])
    for e in src_excl:
        if e not in dst_excl:
            dst_excl.append(e)
    dst["excluded_categories"] = dst_excl

    # Determine target category for file placement
    dest_cat = dst.get("pinned_category") or (dst["categories"][0] if dst["categories"] else "Sonstiges")
    dest_folder = CATEGORY_FOLDER_MAP.get(dest_cat, "14 - Sonstiges")
    dest_dir = os.path.join(TARGET_BASE, dest_folder, target) if SENDER_SUBFOLDERS else os.path.join(TARGET_BASE, dest_folder)
    os.makedirs(dest_dir, exist_ok=True)

    # Move all PDFs of source sender and reassign in DB
    docs = db.search_documents(sender=name, limit=500)
    moved, skipped, errors = 0, 0, []

    for doc in docs:
        src_path = doc["file_path"]
        # Update sender name in DB regardless of file existence
        new_category = dest_cat if doc.get("status") == "ok" else doc.get("category")
        if doc.get("status") == "ok" and os.path.exists(src_path):
            # Regenerate filename with new sender name
            merged_doc = {**doc, "sender": target, "category": new_category}
            new_filename = build_filename(merged_doc, os.path.basename(src_path))
            dest_path = unique_path(os.path.join(dest_dir, new_filename))
            if os.path.abspath(src_path) != os.path.abspath(dest_path):
                try:
                    shutil.move(src_path, dest_path)
                    db.update_document(doc["id"], sender=target, category=new_category,
                                       file_path=dest_path, filename=os.path.basename(dest_path))
                    moved += 1
                except Exception as e:
                    errors.append(f"{os.path.basename(src_path)}: {e}")
                    db.update_document(doc["id"], sender=target)
            else:
                db.update_document(doc["id"], sender=target, category=new_category)
                skipped += 1
        else:
            db.update_document(doc["id"], sender=target)
            skipped += 1

    # Save merged target, remove source
    sender_repo.upsert(target, dst)
    sender_repo.delete(name)
    storage._refresh_cache()

    return {
        "merged_into": target,
        "moved": moved,
        "skipped": skipped,
        "errors": errors,
        "dest_dir": dest_dir,
        "entry": dst,
    }


@router.delete("/{name}", status_code=204)
def delete_sender(name: str):
    if name not in storage.sender_registry:
        log(f"[Sender] Löschen fehlgeschlagen: '{name}' nicht im Register")
        raise HTTPException(status_code=404, detail="Absender nicht gefunden")
    log(f"[Sender] Lösche '{name}' aus DB...")
    sender_repo.delete(name)
    storage._refresh_cache()
    log(f"[Sender] '{name}' gelöscht. Verbleibend: {len(storage.sender_registry)}")


@router.post("/{name}/remove-category")
def remove_category(name: str, body: dict):
    """
    Remove a category from a sender with optional action on affected documents.
    body: {
      category: str,
      action: 'keep' | 'sonstiges' | 'reclassify' | 'move',
      target_category: str  (only for action='move')
    }
    Returns count of affected documents and what was done.
    """
    if name not in storage.sender_registry:
        raise HTTPException(status_code=404, detail="Absender nicht gefunden")

    category = body.get("category")
    action = body.get("action", "keep")
    target_category = body.get("target_category", "Sonstiges")

    if not category:
        raise HTTPException(status_code=400, detail="Keine Kategorie angegeben")

    entry = storage.sender_registry[name]

    # Remove from categories list
    entry["categories"] = [c for c in entry["categories"] if c != category]

    # [Selective Banning]
    # If ban is True, add to excluded so LLM won't pick it again.
    # Otherwise, just remove from categories list and ensure it is not banned.
    should_ban = body.get("ban", True)
    if should_ban:
        excluded = entry.get("excluded_categories", [])
        if category not in excluded:
            excluded.append(category)
        entry["excluded_categories"] = excluded
    else:
        if "excluded_categories" in entry:
            entry["excluded_categories"] = [c for c in entry["excluded_categories"] if c != category]

    # Clear pinned if it was this category
    if entry.get("pinned_category") == category:
        entry["pinned_category"] = None

    sender_repo.upsert(name, entry)
    storage._refresh_cache()

    # Handle affected documents
    docs = db.search_documents(sender=name, status="ok", limit=500)
    affected = [d for d in docs if d.get("category") == category]
    moved, errors = 0, []

    if action == "keep":
        pass  # Leave files in place

    elif action in ("sonstiges", "move"):
        dest_cat = "Sonstiges" if action == "sonstiges" else target_category
        if dest_cat not in CATEGORY_FOLDER_MAP:
            raise HTTPException(status_code=400, detail=f"Unbekannte Zielkategorie: {dest_cat}")
        cat_folder = os.path.join(TARGET_BASE, CATEGORY_FOLDER_MAP[dest_cat])
        dest_dir = os.path.join(cat_folder, name) if SENDER_SUBFOLDERS else cat_folder
        os.makedirs(dest_dir, exist_ok=True)
        for doc in affected:
            src = doc["file_path"]
            if not os.path.exists(src):
                continue
            dest = os.path.join(dest_dir, os.path.basename(src))
            if os.path.exists(dest):
                base, ext = os.path.splitext(os.path.basename(src))
                dest = os.path.join(dest_dir, f"{base}_1{ext}")
            try:
                shutil.move(src, dest)
                db.update_document(doc["id"], file_path=dest, category=dest_cat)
                moved += 1
            except Exception as e:
                errors.append(str(e))

    elif action == "reclassify":
        # Reset status to pending – reprocess endpoint handles the rest
        for doc in affected:
            db.update_document(doc["id"], status="pending", category=None)
        moved = len(affected)

    return {
        "affected": len(affected),
        "action": action,
        "moved": moved,
        "errors": errors,
    }


@router.post("/{name}/reorganize")
def reorganize_sender(name: str):
    """Move all PDFs of a sender into the folder matching their current category."""
    from pipeline.steps import archive_file_on_disk as _archive

    if name not in storage.sender_registry:
        raise HTTPException(status_code=404, detail="Absender nicht gefunden")

    entry = storage.sender_registry[name]
    target_category = entry.get("pinned_category") or (entry["categories"][0] if entry["categories"] else None)
    if not target_category:
        raise HTTPException(status_code=400, detail="Kein Kategorie für diesen Absender festgelegt")
    if target_category not in CATEGORY_FOLDER_MAP:
        raise HTTPException(status_code=400, detail=f"Unbekannte Kategorie: {target_category}")

    docs = db.search_documents(sender=name, limit=500)
    moved, skipped, errors = 0, 0, []
    dest_dir = None

    for doc in docs:
        if doc["status"] != "ok":
            skipped += 1
            continue
        src = doc["file_path"]
        if not os.path.exists(src):
            skipped += 1
            continue
        try:
            dest = _archive(src, target_category, name, doc.get("date"),
                            document_type=doc.get("document_type"), iban=doc.get("iban"))
            db.update_document(doc["id"], file_path=dest, category=target_category,
                               filename=os.path.basename(dest))
            dest_dir = os.path.dirname(dest)
            moved += 1
        except Exception as e:
            errors.append(f"{os.path.basename(src)}: {e}")

    return {"moved": moved, "skipped": skipped, "errors": errors, "dest_dir": dest_dir or ""}
