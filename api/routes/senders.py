import os
import sys
from typing import Optional

from fastapi import APIRouter, HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import storage
from api.models import SenderEntry, SenderUpdate

router = APIRouter(prefix="/senders", tags=["senders"])


def _reload():
    storage.load_sender_registry()


@router.get("/", response_model=dict[str, SenderEntry])
def list_senders():
    return storage.sender_registry


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
    if body.categories is not None:
        entry["categories"] = body.categories
    # persist
    import json
    from config import SENDERS_FILE
    with open(SENDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(storage.sender_registry.items())), f, ensure_ascii=False, indent=2)
    return entry


@router.post("/{name}/merge/{target}", response_model=SenderEntry)
def merge_sender(name: str, target: str):
    """Merge 'name' into 'target': combine categories, delete 'name'."""
    if name not in storage.sender_registry:
        raise HTTPException(status_code=404, detail=f"Absender '{name}' nicht gefunden")
    if target not in storage.sender_registry:
        raise HTTPException(status_code=404, detail=f"Ziel-Absender '{target}' nicht gefunden")

    src = storage.sender_registry[name]
    dst = storage.sender_registry[target]

    for cat in src["categories"]:
        if cat not in dst["categories"]:
            dst["categories"].append(cat)
    dst["categories"].sort()

    if not dst["pinned_category"] and src.get("pinned_category"):
        dst["pinned_category"] = src["pinned_category"]

    del storage.sender_registry[name]

    import json
    from config import SENDERS_FILE
    with open(SENDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(storage.sender_registry.items())), f, ensure_ascii=False, indent=2)

    return dst


@router.delete("/{name}", status_code=204)
def delete_sender(name: str):
    if name not in storage.sender_registry:
        raise HTTPException(status_code=404, detail="Absender nicht gefunden")
    del storage.sender_registry[name]
    import json
    from config import SENDERS_FILE
    with open(SENDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(storage.sender_registry.items())), f, ensure_ascii=False, indent=2)
