from db.connection import get_conn
from collections import Counter
import re as _re

class QualityService:
    def find_duplicates(self, min_score: int = 60):
        """Find probable duplicate document pairs using exact hash, SimHash, and metadata matching.
        Returns pairs sorted by confidence score descending."""
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT id, file_path, filename, sender, date, document_type, content_hash, sim_hash "
                "FROM documents WHERE status IN ('ok', 'review') ORDER BY id"
            ).fetchall()

        docs = [dict(r) for r in rows]
        pairs = {}

        hash_groups: dict = {}
        for doc in docs:
            h = doc.get("content_hash")
            if h:
                hash_groups.setdefault(h, []).append(doc)
        for h, group in hash_groups.items():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    key = (min(a["id"], b["id"]), max(a["id"], b["id"]))
                    pairs[key] = {"doc_a": a, "doc_b": b, "score": 100, "reason": "Identischer Inhalt (Hash-Match)"}

        sim_docs = [d for d in docs if d.get("sim_hash")]
        NUM_BANDS, BITS_PER_BAND = 8, 8
        lsh_buckets: dict = {}
        for doc in sim_docs:
            h = doc["sim_hash"]
            for band in range(NUM_BANDS):
                band_val = (h >> (band * BITS_PER_BAND)) & ((1 << BITS_PER_BAND) - 1)
                bucket_key = (band, band_val)
                lsh_buckets.setdefault(bucket_key, []).append(doc)
        candidate_pairs: set = set()
        for bucket_docs in lsh_buckets.values():
            if len(bucket_docs) < 2:
                continue
            for i in range(len(bucket_docs)):
                for j in range(i + 1, len(bucket_docs)):
                    a, b = bucket_docs[i], bucket_docs[j]
                    candidate_pairs.add((min(a["id"], b["id"]), max(a["id"], b["id"])))
        id_to_doc = {d["id"]: d for d in sim_docs}
        for cand_key in candidate_pairs:
            if cand_key in pairs:
                continue
            a = id_to_doc[cand_key[0]]
            b = id_to_doc[cand_key[1]]
            dist = bin(a["sim_hash"] ^ b["sim_hash"]).count("1")
            score = round((1.0 - dist / 64) * 100)
            if score >= 80:
                pairs[cand_key] = {"doc_a": a, "doc_b": b, "score": score, "reason": f"Ähnlicher Text ({score}% Übereinstimmung)"}

        from itertools import combinations
        meta_docs = [d for d in docs if d.get("sender") and d.get("date") and d.get("document_type")]
        meta_groups: dict = {}
        for doc in meta_docs:
            mk = (doc["sender"].strip().lower(), doc["date"][:10] if doc["date"] else "", doc["document_type"].strip().lower())
            meta_groups.setdefault(mk, []).append(doc)
        for mk, group in meta_groups.items():
            for a, b in combinations(group, 2):
                key = (min(a["id"], b["id"]), max(a["id"], b["id"]))
                if key in pairs:
                    continue
                pairs[key] = {"doc_a": a, "doc_b": b, "score": 70, "reason": f"Gleicher Absender, Datum & Typ ({a['sender']} / {a['date'][:10] if a['date'] else '?'} / {a['document_type']})"}

        result = [p for p in pairs.values() if p["score"] >= min_score]
        result.sort(key=lambda p: p["score"], reverse=True)
        return {"total": len(result), "pairs": result}

    def duplicates_count(self, min_score: int = 90):
        """Lightweight endpoint: returns count of near-duplicate pairs."""
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT id, sim_hash FROM documents "
                "WHERE sim_hash IS NOT NULL AND sim_hash != 0 AND status IN ('ok', 'review')"
            ).fetchall()
        docs = [(r["id"], r["sim_hash"]) for r in rows]
        if not docs:
            return {"count": 0}

        NUM_BANDS, BITS = 8, 8
        buckets: dict = {}
        for doc_id, h in docs:
            for band in range(NUM_BANDS):
                key = (band, (h >> (band * BITS)) & 0xFF)
                buckets.setdefault(key, []).append((doc_id, h))

        seen: set = set()
        count = 0
        for candidates in buckets.values():
            for i in range(len(candidates)):
                for j in range(i + 1, len(candidates)):
                    aid, ah = candidates[i]
                    bid, bh = candidates[j]
                    pair = (min(aid, bid), max(aid, bid))
                    if pair in seen:
                        continue
                    seen.add(pair)
                    dist = bin(ah ^ bh).count("1")
                    if round((1.0 - dist / 64) * 100) >= min_score:
                        count += 1
        return {"count": count}

    def validation_report(self, min_docs: int = 2):
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT id, filename, sender, date, document_type, category, file_path "
                "FROM documents WHERE status IN ('ok', 'review') AND sender IS NOT NULL AND sender != '' "
                "ORDER BY sender, document_type, date"
            ).fetchall()

        docs = [dict(r) for r in rows]
        groups: dict = {}
        for doc in docs:
            key = ((doc["sender"] or "").strip(), (doc["document_type"] or "").strip())
            if not key[0]:
                continue
            groups.setdefault(key, []).append(doc)

        result = []
        for (sender, doc_type), members in groups.items():
            if len(members) < min_docs:
                continue

            issues = []
            categories = Counter(d["category"] for d in members if d.get("category"))
            if len(categories) > 1:
                dominant = categories.most_common(1)[0][0]
                outliers = [d for d in members if d.get("category") and d["category"] != dominant]
                issues.append({
                    "type": "inconsistent_category",
                    "message": f"Kategorie inkonsistent: meist '{dominant}', aber {len(outliers)} Dokument(e) abweichend",
                    "dominant": dominant,
                    "outliers": [{"id": d["id"], "filename": d["filename"], "category": d["category"], "date": d["date"]} for d in outliers],
                })

            months = []
            for d in members:
                raw = d.get("date") or ""
                m = _re.search(r'(\d{4})-(\d{2})', raw)
                if m:
                    months.append((int(m.group(1)), int(m.group(2)), d))

            if len(months) >= 3:
                months.sort(key=lambda x: (x[0], x[1]))
                month_set = set((y, mo) for y, mo, _ in months)
                first_y, first_mo = months[0][0], months[0][1]
                last_y, last_mo = months[-1][0], months[-1][1]
                total_months = (last_y - first_y) * 12 + (last_mo - first_mo) + 1
                if len(month_set) >= 3 and len(month_set) / total_months >= 0.5:
                    missing = []
                    y, mo = first_y, first_mo
                    while (y, mo) <= (last_y, last_mo):
                        if (y, mo) not in month_set:
                            missing.append(f"{y}-{mo:02d}")
                        mo += 1
                        if mo > 12:
                            mo = 1
                            y += 1
                    if missing:
                        issues.append({
                            "type": "missing_months",
                            "message": f"Mögliche Lücken in monatlicher Serie: {', '.join(missing[:6])}{'…' if len(missing) > 6 else ''}",
                            "missing_months": missing,
                        })

            if not issues:
                continue

            result.append({
                "sender": sender,
                "document_type": doc_type,
                "category": members[0].get("category"),
                "count": len(members),
                "date_range": f"{months[0][0]}-{months[0][1]:02d} – {months[-1][0]}-{months[-1][1]:02d}" if len(months) >= 2 else "",
                "issues": issues,
                "members": [{"id": d["id"], "filename": d["filename"], "date": d["date"], "category": d["category"]} for d in members]
            })

        return {"total_groups": len(result), "groups": result}

quality_service = QualityService()