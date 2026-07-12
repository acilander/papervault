from datetime import datetime, timezone

import db
import db.tax_documents_repo as tax_documents_repo
import db.tax_positions_repo as tax_positions_repo
from llm import llm_json_completion
from tax.prompts import SYSTEM_TAX_EXTRACTOR, tax_program_prompt, assessment_notice_prompt, TAX_CATEGORIES
from utils import log


def _normalize_amount(value) -> float | None:
    if value is None:
        return None
    try:
        s = str(value).replace(".", "").replace(",", ".").replace(" ", "").replace("€", "").replace("EUR", "")
        return float(s)
    except (ValueError, TypeError):
        return None


def _validate_category(category: str | None) -> str:
    if category in TAX_CATEGORIES:
        return category
    close = [c for c in TAX_CATEGORIES if c.lower() in (category or "").lower()]
    if close:
        return close[0]
    return "Sonstiges"


def extract_tax_positions(tax_document_id: int) -> list[dict]:
    """Extract tax positions from a linked document using the LLM.

    Deletes previous unverified positions for the document and inserts new ones.
    Returns the list of inserted positions.
    """
    tax_doc = tax_documents_repo.get(tax_document_id)
    if not tax_doc:
        raise ValueError("Steuerdokument nicht gefunden")

    doc = db.get_document(tax_doc["document_id"])
    if not doc:
        raise ValueError("Dokument nicht gefunden")

    text = doc.get("full_text") or ""
    if not text.strip():
        raise ValueError("Dokument enthält keinen extrahierten Text")

    source_type = tax_doc["source_type"]
    if source_type == "tax_program_export":
        user_prompt = tax_program_prompt(text)
    elif source_type == "assessment_notice":
        user_prompt = assessment_notice_prompt(text)
    else:
        raise ValueError(f"Unbekannter source_type: {source_type}")

    log(f"[TAX] Starte Extraktion fuer Dokument {tax_document_id} ({source_type})")
    raw = llm_json_completion(SYSTEM_TAX_EXTRACTOR, user_prompt, max_tokens=1024)
    if raw is None:
        log(f"[TAX] Extraktion lieferte kein Ergebnis fuer Dokument {tax_document_id}")
        return []

    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        log(f"[TAX] Extraktion lieferte kein Array fuer Dokument {tax_document_id}")
        return []

    tax_positions_repo.delete_all_for_document(tax_document_id)

    inserted = []
    now = datetime.now(timezone.utc).isoformat()
    for item in raw:
        if not isinstance(item, dict):
            continue
        category = _validate_category(item.get("category"))
        label = str(item.get("label") or "").strip() or "Unbekannte Position"
        subcategory = str(item.get("subcategory") or "").strip() or None
        raw_amount = _normalize_amount(item.get("amount"))
        page = item.get("page")
        try:
            page = int(page) if page is not None else None
        except (ValueError, TypeError):
            page = None
        source_text = str(item.get("source_text") or "").strip() or None

        # Assessment notices fill the assessed column; tax program exports fill amount.
        amount = raw_amount if source_type == "tax_program_export" else None
        amount_assessed = raw_amount if source_type == "assessment_notice" else None

        position_id = tax_positions_repo.insert(
            tax_year_id=tax_doc["tax_year_id"],
            tax_document_id=tax_document_id,
            category=category,
            subcategory=subcategory,
            label=label,
            amount=amount,
            amount_assessed=amount_assessed,
            page=page,
            source_text=source_text,
            verified=False,
        )
        inserted.append(tax_positions_repo.get(position_id))

    tax_documents_repo.set_parsed_now(tax_document_id, verified=False)
    log(f"[TAX] {len(inserted)} Positionen extrahiert fuer Dokument {tax_document_id}")
    return inserted
