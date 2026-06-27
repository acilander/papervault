import db
db.init_db()
docs = db.search_documents(limit=9999)
total = len(docs)
with_kw = [d for d in docs if d.get("keywords")]
without_kw = [d for d in docs if not d.get("keywords")]
print(f"Gesamt: {total} | mit Keywords: {len(with_kw)} | ohne: {len(without_kw)}")
print()
for d in docs[:15]:
    kw = (d.get("keywords") or "")[:70]
    print(f"  [{d['id']:3d}] {d['filename'][:45]:45s} | {repr(kw)}")
