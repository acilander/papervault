"""
extract_keywords.py – Batch-Nachextraktion von Keywords für bestehende Dokumente.

Liest alle DB-Einträge ohne Keywords, extrahiert den PDF-Text und fragt das LLM
nach Suchbegriffen. Läuft einmalig im Hintergrund.

Verwendung:
    python extract_keywords.py            # alle ohne Keywords
    python extract_keywords.py --dry-run  # zeigt was gemacht würde
    python extract_keywords.py --limit 20 # max. 20 Dokumente
"""

import argparse
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

import db
from pdf_utils import extract_text
from llm import load_model, log, filter_keywords_against_text

try:
    from llama_cpp import Llama
    from config import MODEL_PATH
    _LLM_AVAILABLE = True
except ImportError:
    _LLM_AVAILABLE = False


KEYWORD_PROMPT = """Lies den folgenden Dokumenttext und schreibe die wichtigsten Suchbegriffe auf - durch Komma getrennt.
Schreibe nur die Begriffe, nichts anderes.
Bevorzuge: Betraege in EUR, IBANs, Vertragsnummern, Produktnamen, spezifische Fachbegriffe aus dem Text.

Dokumenttext:
{text}

Suchbegriffe:"""


def extract_keywords_for_doc(doc: dict, llm, dry_run: bool) -> str | None:
    file_path = doc.get("file_path", "")
    if not os.path.exists(file_path):
        print(f"  SKIP: Datei nicht gefunden: {file_path}")
        return None

    text, status = extract_text(file_path)
    if status in ("encrypted", "corrupt", "no_text") or not text.strip():
        print(f"  SKIP ({status}): kein verwertbarer Text")
        return None

    safe_text = text[:3000]  # Kurz halten für schnelle Extraktion

    if dry_run:
        print(f"  DRY-RUN: Würde Keywords extrahieren für: {os.path.basename(file_path)}")
        return None

    try:
        result = llm.create_chat_completion(
            messages=[
                {"role": "user", "content": KEYWORD_PROMPT.format(text=safe_text)}
            ],
            max_tokens=150,
            temperature=0.1,
        )
        raw = result["choices"][0]["message"]["content"].strip()
        # Try to parse JSON response
        try:
            cleaned = raw.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(cleaned)
            kw_list = parsed.get("keywords", [])
            if isinstance(kw_list, list) and kw_list:
                keywords = ", ".join(str(k).strip() for k in kw_list if k)
                keywords = filter_keywords_against_text(keywords, text)
                return keywords[:500] if keywords else None
        except (json.JSONDecodeError, AttributeError):
            pass
        # Fallback: treat as plain comma-separated text, skip JSON artifacts
        lines = [l.lstrip("-•*0123456789. \t") for l in raw.splitlines()]
        lines = [l.strip() for l in lines
                 if l.strip() and len(l.strip()) < 80
                 and not l.strip().startswith(('{', '}', '[', ']', '`'))]
        keywords = ", ".join(lines) if len(lines) > 1 else (lines[0] if lines else "")
        keywords = keywords.replace('"', '').strip()
        keywords = filter_keywords_against_text(keywords, text)
        return keywords[:500] if keywords else None
    except Exception as e:
        print(f"  FEHLER bei LLM: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Batch-Keyword-Extraktion für archivierte Dokumente")
    parser.add_argument("--dry-run", action="store_true", help="Keine Änderungen schreiben")
    parser.add_argument("--limit", type=int, default=0, help="Maximale Anzahl Dokumente (0 = alle)")
    parser.add_argument("--force", action="store_true", help="Auch Dokumente mit vorhandenen Keywords überschreiben")
    args = parser.parse_args()

    db.init_db()

    # Fetch documents that need keywords
    all_docs = db.search_documents(status="ok", limit=99999)
    if not args.force:
        docs = [d for d in all_docs if not d.get("keywords")]
    else:
        docs = all_docs

    if args.limit:
        docs = docs[:args.limit]

    print(f"\n{'DRY-RUN: ' if args.dry_run else ''}Dokumente ohne Keywords: {len(docs)}")
    if not docs:
        print("Nichts zu tun.")
        return

    if not args.dry_run:
        if not _LLM_AVAILABLE:
            print("FEHLER: llama_cpp nicht verfügbar. Bitte .venv aktivieren.")
            sys.exit(1)
        print("Lade LLM-Modell...")
        load_model()
        from llm import _llm as llm_instance
    else:
        llm_instance = None

    updated, skipped, errors = 0, 0, 0
    for i, doc in enumerate(docs, 1):
        fname = os.path.basename(doc.get("file_path", "?"))
        print(f"\n[{i}/{len(docs)}] {fname}")
        print(f"  Absender: {doc.get('sender')} | Kategorie: {doc.get('category')}")

        keywords = extract_keywords_for_doc(doc, llm_instance, args.dry_run)
        if keywords:
            if not args.dry_run:
                db.update_document(doc["id"], keywords=keywords)
                print(f"  OK: {keywords}")
                updated += 1
        else:
            if not args.dry_run:
                skipped += 1

    print(f"\n{'=' * 50}")
    if args.dry_run:
        print(f"DRY-RUN abgeschlossen. {len(docs)} Dokumente würden verarbeitet.")
    else:
        print(f"Fertig: {updated} aktualisiert, {skipped} übersprungen, {errors} Fehler.")


if __name__ == "__main__":
    main()
