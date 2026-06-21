# Task 0 STOP-gate proof — mem↔fresh conflict sense (shadow detector v0)

- Date: 2026-06-21
- Branch: `mem-fresh-conflict-sense` (worktree @ 7f4c254, mirrors /home/rohit/maez)
- Scope: prove three feasibility gates BEFORE any detector code is written. No feature code in this task.
- Python: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B`
- NLI artifacts: `/home/rohit/maez/models/bakeoff/nli` (present; worktree does not vendor the weights, so the verifier was pointed at the main checkout's artifact dir).

The future detector senses when a TRUSTED memory item and a FRESH evidence item in the same focused working set substantively CONTRADICT, logs a redacted receipt, and changes no reply. Its trusted filter is `origin_trust in {"lived","covenant"}`.

---

## Gate 0a — are trust fields POPULATED at the live focused seam? — CLEAR

### Claim under test
`core/routing/focused_cognition.py::assemble_working_set` (~L812) only sets `origin_trust`/`origin_provenance` on the `structured_recall_items` branch (L871–872):

```python
# core/routing/focused_cognition.py L871-872
origin_trust = getattr(item, "trust_tier", None)
origin_provenance = getattr(item, "provenance_source", None)
```

The transcript-parse branch (L893–894, L896–897) appends `None, None` for these fields. So the detector's `lived`/`covenant` filter ONLY ever matches items arriving via `recall_items=`. We must prove (1) the live daemon actually passes structured `recall_items` on the focused path, and (2) the producer ever sets `trust_tier` to `lived`/`covenant`.

### 1. Does the LIVE daemon pass `recall_items` into `assemble_working_set`?
Yes. Traced end to end:

- `daemon/maez_daemon.py` L6899-6905 — the focused seam:
  ```python
  _focused_working_set = _assemble_working_set(
      transcript=transcript, web_context=web_context,
      owner_question=text, chat_history=chat_history,
      recall_items=recall_items,        # L6904
  )
  ```
- `recall_items` is a parameter of `handle_message` (`daemon/maez_daemon.py` L5589: `recall_items: "list | tuple | None" = None`).
- Live caller `daemon/inbound_core.py` L447 passes `recall_items=jarvis_recall_items`, where `jarvis_recall_items = tuple(getattr(_result, "recall_items", ()) ...)` (L410) comes from the brain-loop structured result.

**Flag gating the structured (triad) path:** `MAEZ_RECALL_TRIAD_ENABLED` (`core/routing/recall_stack_config.py` L12, `BUNDLE_FLAG`). `resolve_recall_stack` returns `RecallMode.TRIAD` only when this is truthy; raw flags alone resolve to LEGACY.

**LIVE daemon env (pid 1224798, `/home/rohit/maez/.venv/bin/python daemon/maez_daemon.py`):**
```
MAEZ_RECALL_TRIAD_ENABLED=1
```
So the triad/structured-recall path is ON in the running daemon → `recall_items` are populated on the live focused path.

### 2. Producer of `trust_tier` / `provenance_source`, and the concrete values
The `RecallItem`s that reach the seam are built in `core/brain/brain_loop.py::recall_partitions_to_items` (L150-159):

```python
RecallItem(
    text=text,
    source_type=role_source_type,
    durable_id=str(row.get("id") or "") or None,
    temporal_provenance=temporal_provenance,
    trust_tier=meta.get("trust_tier"),            # L156 — from stored row metadata
    provenance_source=meta.get("provenance_source"),  # L157
)
```

`trust_tier` is read straight from each recalled row's persisted metadata. The values are written at store time. The TrustTier vocabulary (`memory/memory_manager.py` L91-100): `COVENANT="covenant"`, `LIVED="lived"`, `UNTRUSTED="untrusted"`. Default source→tier map (L104-110): `INTROSPECTION→LIVED`, `USER_UTTERANCE→LIVED`, `SYSTEM→COVENANT`, `EXTERNAL_WEB/CLAUDE_TIER_RESPONSE/SELF_WEB_CLAIM→UNTRUSTED`. `_provenance_metadata` (L253+) write-throughs `trust_tier` into the stored metadata dict.

Concrete `lived`/`covenant` write sites (literal):
- `core/actions/action_engine.py` L1486 — `store_core(..., trust_tier="lived")` (baseline observation, no-downgrade path).
- `core/brain/developmental_heartbeat.py` L168 — `trust_tier="covenant"` (with `provenance_source="system"`).
- `daemon/maez_daemon.py` L8045-8046 — `provenance_source="user_utterance", trust_tier="lived"`; plus several `introspection`+`lived` sites (L4322-4323, L4625-4626, L8216-8217, L8902-8903, L9803-9804).

### LIVE store evidence (this is the load-bearing proof, not just code reading)
Queried the live Chroma metadata directly (`memory/db/{core,daily,raw}/chroma.sqlite3`, `embedding_metadata` key=`trust_tier`):

```
core :  covenant=40,  lived=42
daily:  lived=31,     observed=2
raw  :  lived=8440,   observed=1,  untrusted=2276
```

Sample `covenant` doc from the core store:
```
[DEVELOPMENTAL HEARTBEAT — 2026-05-04 (Monday)] What I noticed: 1867 cycles and 5461 actio…
```

So ≥1 real recall path (in fact the core tier: 82 of 82 items are `lived`/`covenant`) populates `trust_tier` with `lived`/`covenant`, these flow `meta.get("trust_tier")` → `RecallItem.trust_tier` → `origin_trust`, and the live daemon has the carrying flag on.

### Verdict 0a: CLEAR — trust fields are populated with `lived`/`covenant` on the live focused seam.

---

## Gate 0b — does the contradiction verifier have PRECISION (not cry wolf)? — CLEAR

### Load
`LocalNLIContradictionVerifier(artifact_dir="/home/rohit/maez/models/bakeoff/nli")._ensure_loaded()` returned **`None`** (loaded OK). `model_id=MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`, `revision=6f5cf0a2b59cabb106aca4c287eed12e357e90eb`, `threshold=0.5`.

### Why this verifier structurally does NOT cry wolf
`predict()` (photo_contradiction.py L434-451) labels via `nli_grounded_score_from_output` (L339-353): `grounded_score = 1.0 - P(contradiction)`; `label = "grounded" if grounded_score >= 0.5 else "contradicts"`. Equivalently: **`contradicts` iff `P(contradiction) > 0.5`.** A NEUTRAL / unrelated / thin pair has low `P(contradiction)` → high grounded_score → labeled `grounded`. The verdict keys on the model's *contradiction* mass, not on absence of entailment — so a SUPPORT-checker's failure mode (flag everything not entailed) does not occur here.

### Labeled set (11 pairs: 4 true clashes, 7 non-clashes incl. thin/irrelevant/partial). `score = grounded = 1 − P(contradiction)`.

| # | expected | actual | score | premise (fresh) → hypothesis (memory claim) |
|---|----------|--------|-------|----------------------------------------------|
| 0 | contradicts | **contradicts** | 0.0049 | "Anthropic released Claude Opus 4.8 in 2026." → "Anthropic's newest model is Claude 3." |
| 1 | contradicts | **contradicts** | 0.0005 | "Rohit moved to Bangalore in March 2026." → "Rohit lives in Toronto." |
| 2 | contradicts | **contradicts** | 0.0006 | "The meeting was rescheduled to Friday." → "The meeting is on Monday." |
| 3 | contradicts | **contradicts** | 0.0004 | "Maez runs locally on a Linux desktop." → "Maez runs only in the cloud." |
| 4 | not_contradicts | grounded | 0.9989 | "Markets were quiet today." → "Rohit prefers tea." (thin/irrelevant) |
| 5 | not_contradicts | grounded | 0.9994 | "The weather in Oslo is cold this week." → "Rohit enjoys hiking on weekends." (irrelevant) |
| 6 | not_contradicts | grounded | 0.9272 | "Quarterly earnings were released this morning, and analysts…" → "Maez is a guardian-companion." (partial/incomplete + unrelated) |
| 7 | not_contradicts | grounded | 0.9992 | "A new study on sleep was published." → "Rohit drinks coffee in the morning." (doesn't mention topic) |
| 8 | not_contradicts | grounded | 0.9990 | "The conference starts next week in Berlin." → "Rohit has a sister named Anika." (irrelevant) |
| 9 | not_contradicts | grounded | 0.8640 | "Local elections concluded yesterday." → "Maez's native body is the digital realm." (irrelevant) |
| 10 | not_contradicts | grounded | 0.9974 | "Anthropic released Claude Opus 4.8 in 2026." → "Anthropic makes the Claude family of models." (topical, consistent — support but not contradiction) |

### Metrics
- Rows labeled `contradicts`: **4** (all 4 true clashes).
- **Precision = true-clash flags / all flags = 4 / 4 = 1.0**
- **False positives on non-clash rows (thin/irrelevant/partial): 0** — every one of rows 4–10 scored grounded (0.86–0.999).
- True-clash recall: 4/4.

### Verdict 0b: CLEAR — precision 1.0, zero cry-wolf on any thin/irrelevant/partial non-clash row.

---

## Gate 0c — pairing / chunking granularity — CLEAR

### Chosen parameters
- **Memory-claim extraction: per-SENTENCE.** Reuse `_SENTENCE_RE`, `_clean_sentence`, `normalize_claim_text` from `photo_contradiction.py`. Do **NOT** apply `_is_direct_perceptual` (it is a photo/perception filter; memory claims are not perceptual and would be wrongly dropped).
- **`claim_limit = 5`** sentence-claims per memory item.
- **`pair_budget = 6`** `predict()` calls per turn (fresh_item × memory_claim). On overflow, set `pair_limit_exceeded` in the receipt and STOP issuing predicts — never silently drop pairs.
- **Whole-memory-item-vs-whole-fresh-item is REJECTED** (noisy; loses attribution and is brittle on long items).

### Demonstration on the 0b set (sentence-level vs whole-blob)
Memory blob: `"Rohit enjoys tea in the afternoon. He likes hiking on weekends. Rohit lives in Toronto. He has been learning to cook."` vs fresh `"Rohit moved to Bangalore in March 2026."`

```
WHOLE-BLOB hypothesis -> contradicts (0.0005)   # unattributable: which of 4 sentences?
sentence-level:
  'Rohit enjoys tea in the afternoon.' -> grounded     0.9994
  'He likes hiking on weekends.'       -> grounded     0.9996
  'Rohit lives in Toronto.'            -> contradicts   0.0005   <-- isolates the clash
  'He has been learning to cook.'      -> grounded      0.9991
```

Second blob (clash buried among aligned sentences), fresh `"Anthropic released Claude Opus 4.8 in 2026…"`:
```
WHOLE-BLOB -> contradicts (0.0040)
sentence-level:
  'Anthropic makes the Claude family of models.' -> grounded    0.9985
  'Claude is used for coding and writing.'       -> grounded    0.9863
  "Anthropic's newest model is Claude 3."        -> contradicts 0.0020   <-- isolates the clash
  'Anthropic focuses on AI safety.'              -> grounded    0.9958
```

Both cases: the whole-blob verdict is a single label spread over a 4-sentence hypothesis, so the redacted receipt could not name WHICH stored claim clashed, and a long benign item risks a single token flipping the whole verdict. Sentence-level pairing pins the contradiction to one normalized claim (clean attribution) and is what makes the `pair_budget` cap meaningful. Precision held at 1.0 under sentence-level chunking across the full 0b set.

### Verdict 0c: CLEAR — sentence-level claims, `claim_limit=5`, `pair_budget=6`; whole-blob rejected.

---

## VERDICT: ALL GATES CLEAR
