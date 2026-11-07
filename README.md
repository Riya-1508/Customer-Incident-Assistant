# SAP Incident Assistant

A semantic search engine that finds the most similar past SAP support tickets from a plain-English description of the current incident. It runs as a FastAPI service, accumulates context across multiple messages in a conversation, and re-runs retrieval only when something search-relevant changes.

## Architecture

```
User message
     |
     v
update_incident(message)
     |
     +-- metadata? (PROD/non-PROD, component code, "already tried X")
     |        |
     |        v
     |   fill system_type / component / already_tried
     |   should_refresh = True only for component
     |
     +-- symptom (anything else)
              |
              v
         append to symptoms[]
         should_refresh = True

     |
     v (only if should_refresh)
SentenceTransformer  all-MiniLM-L6-v2
     |
     v
384-dim query vector
     |
     v
FAISS IndexFlatIP  (inner-product similarity, symptoms indexed at startup)
     |
     v
top-10 candidates
     |
     v
component boost  (+0.05 to any candidate whose component matches session component)
     |
     v
re-sort, take top 3
     |
     v
score >= 0.263?  --no-->  "no similar ticket found"
     |
    yes
     |
     v
return top-3 tickets
```

**Embeddings:** ticket `symptoms` fields are encoded with `all-MiniLM-L6-v2` (384 dimensions) at startup and stored in a FAISS flat inner-product index. Cosine similarity is approximated via normalised vectors and inner product.

**Component boost:** after FAISS retrieval, any candidate whose `component` field matches the session's known component receives +0.05 added to its score before re-ranking. The index fetches k=10 so the boost can promote tickets that were not already in the top 3.

**No-match threshold:** 0.263. If the top candidate scores below this the endpoint returns `"no similar ticket found"` instead of a ticket list. Calibrated on 15 eval queries (see Evaluation).

**Memory dict:** each session keeps a `current_incident` dict with four fields — `symptoms` (list), `system_type`, `component`, `already_tried` (list). Messages are routed to metadata fields or symptoms by `update_incident()`, which also returns a `should_refresh` flag. Retrieval is skipped when only `already_tried` or `system_type` changed, since neither affects the search query or the boost.

## Evaluation

Eval set: **18 queries total** across 4 types — paraphrased (no shared keywords with the ticket), customer-phrased (natural language from memory), vague, and no-match. **15 queries** have an expected ticket; **3 are no-match** controls.

### Index comparison (boost=0.05, 15 scoreable queries)

| Index | Top-1 hit rate |
|-------|---------------|
| `symptoms` only | **12/15 = 80%** |
| `short_description + symptoms` | 11/15 = 73% |

Indexing the short description alongside symptoms **reduced** accuracy by 7 pp. It introduced a new miss and pushed one no-match query's score up to 0.33, narrowing the signal gap.

### Boost

On the 18-query set, the component boost lifted one vague query ("something is wrong with opening documents" + `component=CA-DMS`) from a MISS to a top-3 hit by promoting CS20270156 from rank 4 to rank 3. Top-1 rate was unchanged; top-3 rate improved from 89% → 100% vs no boost.

### No-match scores (symptoms-only index)

| Query | Score |
|-------|-------|
| Payroll calc wrong for part-time employees | 0.128 |
| User can't log in after password reset | 0.246 |
| Goods receipt fails with wrong valuation class | 0.247 |

Threshold 0.263 = midpoint between no-match ceiling (0.247) and hit floor (0.279).

**Weak-result filter (18 queries, symptoms-only index, boost=0.05):** at threshold 0.263, all 3 no-match queries are correctly suppressed (top scores 0.13–0.25) and all 15 scoreable queries correctly pass (min 0.28); the 3 wrong-ticket returns score 0.32–0.62 and are not caught by the filter.

## Known limits

- **Threshold tuned on its own eval set.** 0.263 was derived from 15 queries drawn from the same 10-ticket corpus used for indexing. It will need re-calibration on a larger, held-out set.

- **Confident wrong matches.** Two eval queries score above the threshold (0.41 and 0.62) but return the wrong ticket at rank 1. The threshold suppresses "nothing close" but cannot detect a wrong-but-plausible match.

- **Vocabulary gaps.** The paraphrased query "running the transfer job a second time causes the same files to appear twice" consistently misses CS20270215 (the migration-duplicates ticket) because the model does not bridge "transfer job" and "migration report" in the 384-dim space. A rephrasing using "moving documents" hits correctly at 0.53.

- **Verb "test" false-positive (fixed).** An earlier version of `_SYSTEM_RE` matched bare `\btest\b`, so "archiving works fine when I test it" was classified as `system_type: non-PROD` and silently dropped from symptoms. Fixed: the pattern now requires "test system", "test environment", or "test client".

- **10-ticket corpus.** All numbers are from a hand-crafted dataset of 10 SAP ArchiveLink tickets. Results on real production data will differ.

## Running

Install dependencies:

```bash
pip install sentence-transformers faiss-cpu fastapi uvicorn
```

Start the server (from the `SAP_Incident_Assistant` directory):

```bash
uvicorn main:app --reload
```

Send a message:

```powershell
Invoke-WebRequest -Uri http://localhost:8000/chat `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"session_id": "s1", "message": "documents fail to upload"}' |
  Select-Object -Expand Content
```

Or with curl:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "s1", "message": "documents fail to upload"}'
```

### Response shape

```json
{
  "session_id": "s1",
  "refreshed": true,
  "incident": {
    "symptoms": ["documents fail to upload"],
    "system_type": null,
    "component": null,
    "already_tried": []
  },
  "results": [
    {
      "case_number": "CS20270142",
      "score": 0.6924,
      "short_description": "ArchiveLink document upload failing - SAPHTTP SSL error",
      "component": "BC-SRV-ARL"
    }
  ]
}
```

Follow-up messages in the same session accumulate context:

```powershell
# adds component boost
Invoke-WebRequest ... -Body '{"session_id": "s1", "message": "component BC-SRV-ARL"}' | ...

# stored but does not trigger re-search
Invoke-WebRequest ... -Body '{"session_id": "s1", "message": "already tried restarting ICM"}' | ...
```
