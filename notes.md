# Notes

## Evaluation

### Boost behavior

Query: `"PDF shows as binary"`

**No component filter**
```
CS20270184  score=0.5419  [CA-DMS]     Document displaying as binary/octet-stream instead of PDF
CS20270163  score=0.3635  [BC-CCM-PRN] PDF documents opening in ECL Viewer instead of native PDF viewer
CS20270192  score=0.2222  [BC-SRV-ARL] User unable to execute archiving program - authorization error
```

**component="CA-DMS"** (+0.05 boost)
```
CS20270184  score=0.5919  [CA-DMS]     Document displaying as binary/octet-stream instead of PDF
CS20270163  score=0.3635  [BC-CCM-PRN] PDF documents opening in ECL Viewer instead of native PDF viewer
CS20270156  score=0.2329  [CA-DMS]     Content server returning 401 Unauthorized on document retrieval
```

CS20270156 (rank 4 without boost) displaces CS20270192 from top 3 after the +0.05 CA-DMS boost.
Requires k=10 fetch before boosting so candidates outside the initial top 3 can be promoted.

### Hit rates by boost (eval.json, 9 scoreable queries)

| boost | top-1 | top-3 |
|-------|-------|-------|
| 0.00  | 7/9 = 78% | 8/9 = 89% |
| 0.05  | 7/9 = 78% | 9/9 = 100% |
| 0.10  | 7/9 = 78% | 9/9 = 100% |

No-match baseline score: 0.128 (payroll query — well below any real match).

**Chosen: boost=0.05.** Top-3 improves from 89% → 100% vs no boost. Boost=0.10 gives identical
results, so 0.05 is preferred as the more conservative value.

The one persistent top-1 miss is query 4 (paraphrased migration): correct ticket CS20270215
lands at rank 2–3, displaced by CS20270228 at rank 1. No component is set on that query so
the boost cannot help; the two tickets are semantically close.

### Expanded eval set + index comparison (18 queries: 15 scoreable + 3 no-match)

eval.json updated: 3 verbatim real_wording queries rewritten as customer phrasings (type: customer),
8 new queries added (6 customer + 2 no-match), total 18.

#### Results — boost=0.05

| query | type | symptoms only | short_desc + symptoms |
|-------|------|--------------|----------------------|
| encrypted channel fails to start... | paraphrased | HIT  0.4459 | HIT  0.4689 |
| records reachable but portal link fails | paraphrased | HIT  0.2787 | MISS 0.3448 |
| attachment fires for most but not one type | paraphrased | HIT  0.3924 | HIT  0.4361 |
| transfer job twice creates duplicate files | paraphrased | MISS 0.3196 | MISS 0.3678 |
| archiving works manually, fails overnight | customer | HIT  0.7715 | HIT  0.6828 |
| PDFs open in SAP not my PDF reader | customer | HIT  0.6071 | HIT  0.6911 |
| saved PDF downloads as unknown file type | customer | HIT  0.6119 | HIT  0.6145 |
| user gets error can't run the job (vague) | vague | HIT  0.4200 | HIT  0.4649 |
| something wrong with opening documents (vague) | vague | MISS 0.4089 | MISS 0.4207 |
| content server rejects with auth error | customer | HIT  0.6935 | HIT  0.7126 |
| can't delete, forbidden, retention not expired | customer | HIT  0.8133 | HIT  0.8590 |
| archive uploads fail, SSL library not loading | customer | HIT  0.6924 | HIT  0.6966 |
| permissions error, colleague with same role can run | customer | HIT  0.7070 | HIT  0.8139 |
| moving to new archive, worried about duplicates | customer | HIT  0.5297 | HIT  0.5608 |
| portal link does nothing, fine inside SAP | customer | MISS 0.6177 | MISS 0.5655 |
| **top-1** | | **12/15 = 80%** | **11/15 = 73%** |

No-match scores:

| query | symptoms only | short_desc + symptoms |
|-------|--------------|----------------------|
| payroll calc wrong for part-time employees | 0.1280 | 0.1236 |
| user can't log in after password reset | 0.2458 | 0.3278 |
| goods receipt fails with wrong valuation class | 0.2472 | 0.2686 |

#### Threshold

**symptoms only:** no-match max=0.2472, hit min=0.2787, gap=0.031
Suggested threshold: **0.263** (midpoint).
At this threshold all 3 no-match queries are correctly suppressed.
Caveat: two misses score above the threshold (0.41, 0.62) — the system returns a
confident but wrong answer. The threshold only catches "nothing close"; it cannot
distinguish a wrong-but-plausible match from a right one.

**short_desc + symptoms:** no-match max=0.3278 (login query drifted up), hit min=0.4361.
The "user can't log in" query overlaps semantically with auth/permissions tickets,
inflating its no-match score and compressing the signal gap.

#### Verdict

**Keep symptoms only.** Adding short_description drops top-1 by 7 pp (80% → 73%), adds
a new miss (Q2 portal link), and contaminates the no-match band (login query rises to 0.33).
The hypothesis that combined text would fix Q4 (transfer job / migration) was not supported:
Q4 remains a miss on both indexes (0.32 vs 0.37). The vocabulary gap between "transfer job"
and "migration report" is too large for this embedding model.

Q15 — a second angle on CS20270215 using "moving documents to a new archive" — scores 0.53
and hits correctly on both indexes. The issue with Q4 is its specific wording, not the ticket.

## Multi-turn conversation runs (5 sessions via /chat endpoint)

### Conv 1 — detail accumulates across 3 messages

| Turn | Message | refreshed | system_type | component | already_tried |
|------|---------|-----------|-------------|-----------|---------------|
| 1 | "documents are not loading at all" | True | None | None | [] |
| 2 | "it is happening on our production system" | False | PROD | None | [] |
| 3 | "component BC-SRV-ARL" | True | PROD | BC-SRV-ARL | [] |

Turn 1 results (no boost):
- CS20270239  0.4295  Content server service alias not maintained - documents inaccessible
- CS20270142  0.3753  ArchiveLink document upload failing - SAPHTTP SSL error
- CS20270184  0.3406  Document displaying as binary/octet-stream instead of PDF

Turn 2 results (cached — PROD doesn't affect retrieval):
- same as turn 1

Turn 3 results (BC-SRV-ARL boost applied):
- CS20270239  0.4795 (+0.05)  Content server service alias not maintained
- CS20270142  0.4253 (+0.05)  ArchiveLink document upload failing - SAPHTTP SSL error
- CS20270184  0.3406          Document displaying as binary/octet-stream instead of PDF

### Conv 2 — nothing matches

| Turn | Message | refreshed | result |
|------|---------|-----------|--------|
| 1 | "payroll results are incorrect after the latest HR configuration change" | True | no similar ticket found |

Top score below 0.263 threshold — correctly suppressed.

### Conv 3 — PDF viewer, component added on second turn

| Turn | Message | refreshed | component |
|------|---------|-----------|-----------|
| 1 | "PDFs keep opening in the built-in viewer instead of Adobe" | True | None |
| 2 | "component BC-CCM-PRN" | True | BC-CCM-PRN |

Turn 1 results (no boost):
- CS20270163  0.5753  PDF documents opening in ECL Viewer instead of native PDF viewer
- CS20270184  0.5278  Document displaying as binary/octet-stream instead of PDF
- CS20270156  0.2684  Content server returning 401 Unauthorized on document retrieval

Turn 2 results (BC-CCM-PRN boost applied):
- CS20270163  0.6253 (+0.05)  PDF documents opening in ECL Viewer
- CS20270184  0.5278          Document displaying as binary/octet-stream instead of PDF
- CS20270156  0.2684          Content server returning 401 Unauthorized

### Conv 4 — auth error, already_tried does not trigger refresh

| Turn | Message | refreshed | already_tried |
|------|---------|-----------|---------------|
| 1 | "user gets permission denied running the archive report" | True | [] |
| 2 | "already tried checking with the basis team" | False | ["checking with the basis team"] |

Turn 1 results:
- CS20270192  0.6970  User unable to execute archiving program - authorization error
- CS20270228  0.3644  ArchiveLink entries not created when output job runs in background
- CS20270156  0.2794  Content server returning 401 Unauthorized on document retrieval

Turn 2 results: cached (identical) — already_tried correctly skipped re-search.

### Conv 5 — background job (bug found)

| Turn | Message | refreshed | symptoms | system_type |
|------|---------|-----------|----------|-------------|
| 1 | "archiving works fine when I test it but fails when scheduled overnight" | False | [] | non-PROD |
| 2 | "already checked SM37" | False | [] | non-PROD |

**Bug:** the word "test" in "when I test it" matched the `\btest\b` pattern in `_SYSTEM_RE`
and classified the message as `system_type: non-PROD`. The message was consumed as metadata
and never added to symptoms — no search was run either turn.

Fix needed: tighten `_SYSTEM_RE` so "test" only matches when used as a noun adjacent to
"system", "environment", or "client" (e.g. "test system", "test client"), not as a verb.
