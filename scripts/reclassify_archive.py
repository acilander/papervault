import os
import sys
import time
import argparse
from tqdm import tqdm
import json

# Add backend directory to Python path so we can import our modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

import db
from llm.driver import classify_document
from pdf_utils import extract_text, extract_features, build_feature_prompt, prepare_text_for_llm
from storage import apply_sender_overrides
from utils import log

def main():
    parser = argparse.ArgumentParser(description="PaperVault - Global Archive Reclassification Tool")
    parser.add_argument("--force", action="store_true", help="Include 'review' documents. (Locked documents are ALWAYS ignored).")
    parser.add_argument("--limit", type=int, default=0, help="Limit the number of documents to process (for testing).")
    args = parser.parse_args()

    print("=" * 80)
    print(" PaperVault - Safe Archive Reclassification")
    print("=" * 80)
    print("WARNUNG: Diese Aktion wird viele Dokumente neu bewerten.")
    print("Alle geänderten Dokumente werden auf den Status 'review' gesetzt,")
    print("damit du sie in der UI (unter 'Prüfung') vor der physischen Ordner-Verschiebung freigeben kannst.\n")

    # 1. Fetch eligible documents
    with db.get_conn() as conn:
        status_filter = "('ok', 'review', 'no_text', 'classification_failed')" if args.force else "('ok', 'no_text', 'classification_failed')"
        query = f"""
            SELECT id, file_path, filename, sender, category, document_type, date, summary, status 
            FROM documents 
            WHERE status IN {status_filter}
        """
        if args.limit > 0:
            query += f" LIMIT {args.limit}"
            
        rows = conn.execute(query).fetchall()
        
    docs = [dict(r) for r in rows]
    total_docs = len(docs)
    
    if total_docs == 0:
        print("Keine Dokumente zur Re-Klassifizierung gefunden.")
        return

    confirm = input(f"Bist du sicher, dass du {total_docs} Dokumente neu klassifizieren willst? (ja/nein): ")
    if confirm.lower() not in ['ja', 'j', 'yes', 'y']:
        print("Abbruch.")
        return

    print("\nStarte GPU-Inferenz (Dies kann mehrere Stunden dauern)...\n")

    changed_count = 0
    error_count = 0
    unchanged_count = 0

    # 2. Iterate and process
    for doc in tqdm(docs, desc="Reclassifying", unit="doc"):
        fpath = doc["file_path"]
        if not fpath or not os.path.exists(fpath):
            error_count += 1
            continue

        try:
            # Extract fresh text
            text, status = extract_text(fpath)
            if status != "ok" or not text:
                error_count += 1
                continue
                
            safe_text = prepare_text_for_llm(text)
            features = extract_features(text, filename=doc["filename"], file_path=fpath)
            fp = build_feature_prompt(features)
            
            # Find similar docs (excluding self)
            sim = db.find_similar_by_features(features.get("category_candidates", []), features.get("type_candidate"))
            sim = [s for s in sim if s["id"] != doc["id"]]

            # Run LLM
            res = classify_document(
                safe_text,
                filename=doc["filename"],
                feature_prompt=fp,
                similar_docs=sim,
                header_zone=features.get("header_zone")
            )

            if not res:
                error_count += 1
                continue

            # Apply hard overrides
            res = apply_sender_overrides(res)

            # Check if relevant metadata actually changed
            fields_to_check = ["sender", "category", "document_type", "date"]
            has_changed = False
            for f in fields_to_check:
                old_val = str(doc.get(f) or "").strip().lower()
                new_val = str(res.get(f) or "").strip().lower()
                if old_val != new_val:
                    has_changed = True
                    break

            if has_changed:
                # Update DB and set status to 'review'
                db.update_document(
                    doc["id"],
                    sender=res.get("sender"),
                    date=res.get("date"),
                    document_type=res.get("document_type"),
                    category=res.get("category"),
                    summary=res.get("summary"),
                    notes=f"[RECLASSIFIED] {res.get('confidence_reason', '')}",
                    status="review" # FORCE REVIEW STATUS!
                )
                changed_count += 1
            else:
                unchanged_count += 1

        except Exception as e:
            # log(f"Error on {doc['filename']}: {e}")
            error_count += 1

    print("\n" + "=" * 80)
    print(" ZUSAMMENFASSUNG")
    print("=" * 80)
    print(f"Erfolgreich verarbeitet: {total_docs - error_count} / {total_docs}")
    print(f"Fehlerhaft übersprungen: {error_count}")
    print(f"Unverändert (KI bestätigt alte Werte): {unchanged_count}")
    print(f"GEÄNDERT (Zurück auf 'Prüfung' gesetzt): {changed_count}")
    print("\nBitte öffne die Web-UI und gehe in den Reiter 'Prüfung', um die")
    print("geänderten Dokumente zu kontrollieren und die Ordner-Verschiebung freizugeben!")

if __name__ == "__main__":
    main()