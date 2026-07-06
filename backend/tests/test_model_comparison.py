"""
LLM Model Comparison Test
=========================
Selects 100 representative documents from the DB and runs both LLM models
(large + small) against them, comparing results to the DB ground truth.

Usage:
    cd backend
    python tests/test_model_comparison.py

    # Override model paths:
    MODEL_LARGE=path/to/large.gguf MODEL_SMALL=path/to/small.gguf python tests/test_model_comparison.py

    # Limit to fewer documents for quick test:
    python tests/test_model_comparison.py --limit 20
"""

import sys
import os
import time
import json
import argparse
import textwrap
from collections import defaultdict

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from db.connection import get_conn
from db.schema import init_db

# ── Config ─────────────────────────────────────────────────────────────────────

MODEL_LARGE = os.getenv(
    "MODEL_LARGE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 "models", "Qwen", "Qwen2.5-14B-Instruct-GGUF", "Qwen2.5-14B-Instruct-Q4_K_M.gguf")
)
MODEL_SMALL = os.getenv(
    "MODEL_SMALL",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 "models", "Qwen2.5-7B-Instruct-Q4_K_M.gguf")
)

FIELDS_TO_COMPARE = ["sender", "document_type", "category"]


# ── Sample selection ───────────────────────────────────────────────────────────

def select_sample(n: int = 100) -> list[dict]:
    """
    Stratified sample: pick documents evenly across categories and document_types.
    Only documents with status='ok', non-empty full_text, and all ground-truth fields set.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, filename, sender, date, document_type, category, full_text,
                      confidence, archived_at
               FROM documents
               WHERE status = 'ok'
                 AND full_text IS NOT NULL AND full_text != ''
                 AND sender IS NOT NULL AND sender != ''
                 AND document_type IS NOT NULL AND document_type != ''
                 AND category IS NOT NULL AND category != ''
               ORDER BY RANDOM()"""
        ).fetchall()

    docs = [dict(r) for r in rows]
    if not docs:
        print("ERROR: No eligible documents found in DB.")
        sys.exit(1)

    # Stratified: group by (category, document_type), pick evenly
    buckets: dict[tuple, list] = defaultdict(list)
    for d in docs:
        key = (d["category"], d["document_type"])
        buckets[key].append(d)

    sample: list[dict] = []
    bucket_keys = list(buckets.keys())
    per_bucket = max(1, n // len(bucket_keys))
    for key in bucket_keys:
        sample.extend(buckets[key][:per_bucket])
        if len(sample) >= n:
            break

    # Fill up to n if needed
    if len(sample) < n:
        remaining = [d for d in docs if d not in sample]
        sample.extend(remaining[:n - len(sample)])

    sample = sample[:n]
    print(f"Selected {len(sample)} documents across {len(set((d['category'], d['document_type']) for d in sample))} category/type combinations.")
    return sample


# ── LLM runner ────────────────────────────────────────────────────────────────

def run_model(model_path: str, docs: list[dict], label: str) -> tuple[list[dict], float]:
    """Load model, classify all docs, return (results, total_seconds)."""
    print(f"\n{'='*60}")
    print(f"Running: {label}")
    print(f"Model:   {os.path.basename(model_path)}")
    print(f"{'='*60}")

    if not os.path.exists(model_path):
        print(f"ERROR: Model not found: {model_path}")
        return [], 0.0

    # Temporarily override MODEL_PATH
    original_path = config.MODEL_PATH
    config.MODEL_PATH = model_path

    # Force reload of LLM
    import llm as llm_module
    llm_module._llm = None

    results = []
    t_start = time.time()

    for i, doc in enumerate(docs, 1):
        doc_id = doc["id"]
        full_text = doc["full_text"] or ""
        filename = doc.get("filename", "")
        print(f"  [{i:3d}/{len(docs)}] {filename[:60]:<60}", end=" ", flush=True)

        t0 = time.time()
        try:
            result = llm_module.classify_document(
                safe_text=full_text[:4000],
                filename=filename,
            )
            elapsed = time.time() - t0
            if result:
                results.append({
                    "doc_id": doc_id,
                    "predicted": result,
                    "elapsed": round(elapsed, 2),
                    "error": None,
                })
                print(f"OK  {elapsed:.1f}s  → {result.get('sender','?')} / {result.get('document_type','?')} / {result.get('category','?')}")
            else:
                results.append({"doc_id": doc_id, "predicted": None, "elapsed": round(elapsed, 2), "error": "no result"})
                print(f"FAIL {elapsed:.1f}s")
        except Exception as e:
            elapsed = time.time() - t0
            results.append({"doc_id": doc_id, "predicted": None, "elapsed": round(elapsed, 2), "error": str(e)[:100]})
            print(f"ERROR {elapsed:.1f}s: {e}")

        # Unload model between docs to avoid memory issues when switching models
        # (keep loaded — faster, but only practical for same model)

    total_time = time.time() - t_start

    # Restore and unload
    config.MODEL_PATH = original_path
    llm_module._llm = None

    return results, total_time


# ── Comparison ────────────────────────────────────────────────────────────────

def compare(docs: list[dict], results_large: list[dict], results_small: list[dict]) -> dict:
    """Compare both models against ground truth and against each other."""
    doc_map = {d["id"]: d for d in docs}
    large_map = {r["doc_id"]: r for r in results_large}
    small_map = {r["doc_id"]: r for r in results_small}

    stats = {
        "large": {f: {"match": 0, "total": 0} for f in FIELDS_TO_COMPARE},
        "small": {f: {"match": 0, "total": 0} for f in FIELDS_TO_COMPARE},
        "agreement": {f: {"agree": 0, "total": 0} for f in FIELDS_TO_COMPARE},
        "large_errors": 0,
        "small_errors": 0,
        "large_times": [],
        "small_times": [],
    }
    disagreements = []

    for doc in docs:
        doc_id = doc["id"]
        r_large = large_map.get(doc_id, {})
        r_small = small_map.get(doc_id, {})

        p_large = r_large.get("predicted") or {}
        p_small = r_small.get("predicted") or {}

        if not p_large:
            stats["large_errors"] += 1
        if not p_small:
            stats["small_errors"] += 1

        if r_large.get("elapsed"):
            stats["large_times"].append(r_large["elapsed"])
        if r_small.get("elapsed"):
            stats["small_times"].append(r_small["elapsed"])

        for field in FIELDS_TO_COMPARE:
            gt = (doc.get(field) or "").strip().lower()
            vl = (p_large.get(field) or "").strip().lower()
            vs = (p_small.get(field) or "").strip().lower()

            if gt and vl:
                stats["large"][field]["total"] += 1
                if gt == vl:
                    stats["large"][field]["match"] += 1
            if gt and vs:
                stats["small"][field]["total"] += 1
                if gt == vs:
                    stats["small"][field]["match"] += 1
            if vl and vs:
                stats["agreement"][field]["total"] += 1
                if vl == vs:
                    stats["agreement"][field]["agree"] += 1

        # Record disagreements
        for field in FIELDS_TO_COMPARE:
            vl = (p_large.get(field) or "").strip()
            vs = (p_small.get(field) or "").strip()
            gt = (doc.get(field) or "").strip()
            if vl != vs:
                disagreements.append({
                    "doc_id": doc_id,
                    "filename": doc.get("filename", ""),
                    "field": field,
                    "ground_truth": gt,
                    "large": vl,
                    "small": vs,
                    "large_correct": vl.lower() == gt.lower(),
                    "small_correct": vs.lower() == gt.lower(),
                })

    return {
        "stats": stats,
        "disagreements": disagreements,
    }


# ── Report ────────────────────────────────────────────────────────────────────

def print_report(n_docs: int, comparison: dict, time_large: float, time_small: float,
                 large_label: str, small_label: str):
    stats = comparison["stats"]
    disagreements = comparison["disagreements"]

    print(f"\n{'='*70}")
    print(f"  MODEL COMPARISON REPORT  ({n_docs} documents)")
    print(f"{'='*70}")
    print(f"  Large: {large_label}")
    print(f"  Small: {small_label}")
    print(f"{'='*70}")

    print(f"\n{'Field':<20} {'Large acc':>10} {'Small acc':>10} {'Agreement':>10}")
    print(f"{'-'*55}")
    for field in FIELDS_TO_COMPARE:
        ls = stats["large"][field]
        ss = stats["small"][field]
        ag = stats["agreement"][field]
        l_acc = f"{ls['match']}/{ls['total']} ({100*ls['match']//max(ls['total'],1)}%)" if ls["total"] else "–"
        s_acc = f"{ss['match']}/{ss['total']} ({100*ss['match']//max(ss['total'],1)}%)" if ss["total"] else "–"
        agree = f"{ag['agree']}/{ag['total']} ({100*ag['agree']//max(ag['total'],1)}%)" if ag["total"] else "–"
        print(f"  {field:<18} {l_acc:>10} {s_acc:>10} {agree:>10}")

    avg_large = sum(stats["large_times"]) / max(len(stats["large_times"]), 1)
    avg_small = sum(stats["small_times"]) / max(len(stats["small_times"]), 1)
    print(f"\n{'Metric':<30} {'Large':>10} {'Small':>10}")
    print(f"{'-'*55}")
    print(f"  {'Errors':<28} {stats['large_errors']:>10} {stats['small_errors']:>10}")
    print(f"  {'Avg time/doc (s)':<28} {avg_large:>10.1f} {avg_small:>10.1f}")
    print(f"  {'Total time (s)':<28} {time_large:>10.1f} {time_small:>10.1f}")

    print(f"\n  Disagreements (models differ): {len(disagreements)}")
    if disagreements:
        print(f"\n  {'Doc':<35} {'Field':<15} {'GT':<20} {'Large':<20} {'Small':<20}")
        print(f"  {'-'*110}")
        for d in disagreements[:30]:
            fn = d["filename"][:33]
            gt = d["ground_truth"][:18]
            lv = d["large"][:18]
            sv = d["small"][:18]
            lc = "✓" if d["large_correct"] else "✗"
            sc = "✓" if d["small_correct"] else "✗"
            print(f"  {fn:<35} {d['field']:<15} {gt:<20} {lc}{lv:<19} {sc}{sv:<19}")
        if len(disagreements) > 30:
            print(f"  ... and {len(disagreements) - 30} more (see JSON output)")

    print(f"\n{'='*70}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Compare two LLM models on document classification")
    parser.add_argument("--limit", type=int, default=100, help="Number of documents to test (default: 100)")
    parser.add_argument("--output", type=str, default="", help="Save full results as JSON to this path")
    parser.add_argument("--skip-large", action="store_true", help="Skip large model (only run small)")
    parser.add_argument("--skip-small", action="store_true", help="Skip small model (only run large)")
    args = parser.parse_args()

    print(f"Initializing DB...")
    init_db()

    print(f"Selecting {args.limit} representative documents...")
    docs = select_sample(args.limit)

    large_label = os.path.basename(MODEL_LARGE)
    small_label = os.path.basename(MODEL_SMALL)

    results_large, time_large = [], 0.0
    results_small, time_small = [], 0.0

    if not args.skip_large:
        results_large, time_large = run_model(MODEL_LARGE, docs, f"LARGE: {large_label}")
    if not args.skip_small:
        results_small, time_small = run_model(MODEL_SMALL, docs, f"SMALL: {small_label}")

    if results_large or results_small:
        # Pad missing results
        if not results_large:
            results_large = [{"doc_id": d["id"], "predicted": None, "elapsed": 0, "error": "skipped"} for d in docs]
        if not results_small:
            results_small = [{"doc_id": d["id"], "predicted": None, "elapsed": 0, "error": "skipped"} for d in docs]

        comparison = compare(docs, results_large, results_small)
        print_report(len(docs), comparison, time_large, time_small, large_label, small_label)

        if args.output:
            out = {
                "large_model": MODEL_LARGE,
                "small_model": MODEL_SMALL,
                "n_docs": len(docs),
                "time_large": time_large,
                "time_small": time_small,
                "stats": comparison["stats"],
                "disagreements": comparison["disagreements"],
                "results_large": results_large,
                "results_small": results_small,
                "ground_truth": [
                    {"id": d["id"], "filename": d["filename"],
                     "sender": d["sender"], "document_type": d["document_type"],
                     "category": d["category"]}
                    for d in docs
                ],
            }
            # Convert non-serializable items
            out["stats"]["large_times"] = out["stats"]["large_times"]
            out["stats"]["small_times"] = out["stats"]["small_times"]
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print(f"Full results saved to: {args.output}")
    else:
        print("No results to compare.")


if __name__ == "__main__":
    main()
