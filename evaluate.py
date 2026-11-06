import json
import faiss
from sentence_transformers import SentenceTransformer

with open("tickets.json", encoding="utf-8") as f:
    tickets = json.load(f)

with open("eval.json", encoding="utf-8") as f:
    evals = json.load(f)

model = SentenceTransformer("all-MiniLM-L6-v2")

# Index A: symptoms only
idx_symp = faiss.IndexFlatIP(384)
idx_symp.add(model.encode([t["symptoms"] for t in tickets], normalize_embeddings=True))

# Index B: short_description + symptoms
idx_comb = faiss.IndexFlatIP(384)
idx_comb.add(model.encode(
    [t["short_description"] + " " + t["symptoms"] for t in tickets],
    normalize_embeddings=True,
))


def search(query, faiss_index, component=None, boost=0.05):
    qvec = model.encode([query], normalize_embeddings=True)
    scores, ids = faiss_index.search(qvec, 10)
    results = []
    for s, i in zip(scores[0], ids[0]):
        s = float(s)
        if component and tickets[i]["component"] == component:
            s += boost
        results.append((s, int(i)))
    results.sort(reverse=True)
    return results[:3]


def run(label, faiss_index):
    print(f"\n{'='*68}")
    print(f"  {label}")
    print(f"{'='*68}")

    scoreable = [q for q in evals if q["expected_case"] is not None]
    no_match  = [q for q in evals if q["expected_case"] is None]

    hits, hit_scores, miss_scores = 0, [], []

    for q in scoreable:
        res        = search(q["query"], faiss_index, q.get("component"))
        top_case   = tickets[res[0][1]]["case_number"]
        top_score  = res[0][0]
        ok         = top_case == q["expected_case"]
        hits      += ok
        tag        = "HIT " if ok else "MISS"
        (hit_scores if ok else miss_scores).append(top_score)
        print(f"  [{tag}]  {top_score:.4f}  {q['type']:13s}  {q['query'][:52]}")

    n = len(scoreable)
    print(f"\n  top-1: {hits}/{n} = {hits/n:.0%}")

    nm_scores = []
    print()
    for q in no_match:
        res       = search(q["query"], faiss_index, q.get("component"))
        top_score = res[0][0]
        nm_scores.append(top_score)
        print(f"  [no-match]  {top_score:.4f}  {q['query'][:52]}")

    all_real = sorted(hit_scores + miss_scores)
    threshold = round((max(nm_scores) + min(hit_scores)) / 2, 3)
    print(f"\n  hit scores:      min={min(hit_scores):.4f}  max={max(hit_scores):.4f}")
    print(f"  miss scores:     {[round(s, 4) for s in miss_scores]}")
    print(f"  no-match scores: {[round(s, 4) for s in nm_scores]}")
    print(f"  -> threshold:    {threshold}  (midpoint of max no-match and min hit)")

    return hits, n, hit_scores, miss_scores, nm_scores


print("\nRunning on 18-query eval set (15 scoreable + 3 no-match), boost=0.05")
h1, n1, hs1, ms1, nm1 = run("symptoms only", idx_symp)
h2, n2, hs2, ms2, nm2 = run("short_description + symptoms", idx_comb)

print(f"\n{'='*68}")
print(f"  Summary")
print(f"{'='*68}")
print(f"  symptoms only          top-1: {h1}/{n1} = {h1/n1:.0%}")
print(f"  short_desc + symptoms  top-1: {h2}/{n2} = {h2/n2:.0%}")
