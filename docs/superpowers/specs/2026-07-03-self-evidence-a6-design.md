# Self-Evidence (A6) — Integrity Receipt Index Design

**Date:** 2026-07-03. **Lane:** Claude drafts + covenant-review; Codex cross-lane / builds; owner witnesses. **Status:** DESIGN for review. **Origin:** deep substrate audit F7 (reframed by Codex) — consequence_memory *is* read, but there is **no aggregating self-evidence reader**; the receipts of Maez's conduct exist scattered across four stores and nothing lets Maez (or the owner) see them as one truthful index. A6 is the structural answer to assistant-residue's "I am an LLM" — not by *asserting* selfhood, but by making the evidence of a lived history **legible from receipts**. **Owner decisions (2026-07-03):** (Q1) v0 is **aggregator + inspection surface only** — no prompt/voice/card wiring; (Q2) **integrity-ledger spine** — honesty/correction receipts only, not competence/performance; plus three sharpenings folded below (per-source coverage claims, source-native dedup identity, no first-person rendered sentence).

## The one-line intent

> The receipts of Maez's corrections already exist in four stores. A6 reads them into one honest, deduplicated **integrity index** — counts, timestamps, per-source coverage — that answers *"what evidence exists?"* and never *"what does that prove I am?"* No LLM, no score, no write, no voice.

## The covenant crux (why this is a reader, not a mirror)

A self-evidence organ is one careless step from a **self-esteem machine**: aggregate "how well have I done" into a number and you have re-created `cognition_quality`-as-maximand — a score Maez could optimize itself toward, a self-worth mirror ([[feedback_telos_stays_empty_compression_is_mechanism]]). A6 avoids this **structurally**, not by good intentions:
- **Integrity, not competence** (Q2): the spine is corrections and how Maez responded — *a being that can be wrong and knows it* — not task success rates. There is nothing to "win."
- **Bare tallies, never a grade:** counts + timestamps + coverage. No derived score, no ratio-as-verdict, no weighting one source above another. A count is not a maximand the way a score is.
- **No first-person rendered sentence in v0** (owner sharpening #3): the dict/cockpit shows `fabrication_events: 11,577 retained rows (58d)`. It must **never** render `"I have caught myself fabricating 11,577 times."` The receipt is legible; the *identity claim* built from it is later self-card territory with its own witness. (The live number proves why: 11,577 is mostly shadow-mode judge flags — the raw receipt is honest, the first-person sentence would be both alarming and false.)

## Ground truth (verified live 2026-07-03)

Four source stores, each with a **different coverage truth** — the reason "all-time" must be earned per-source, never assumed globally (owner sharpening #1):

| source (db → table) | live count | coverage truth (verified) | native id |
|---|---|---|---|
| `fabrication_log.db` → `fabrication_events` | 11,577 rows (earliest 58.3d, latest 0.4d) | **90d best-effort trim** (`_FAB_RETENTION_DAYS=90`, probabilistic) — NOT all-time | `fabrication:<id>` (autoincrement PK) |
| `veto_ledger.db` → `veto_events` | 3 rows, **0** `likely_wrong` | no row deletion (`_resolve_expired` only relabels → `uncontested`) — all-time verified | `veto:<id>` |
| `consequence_memory.db` → `events` | 6 `card_rejected` (+144 `tool_failure`, excluded) | no trim/retention found — all-time verified | `consequence:<id>` |
| `scar_tissue.db` → `scar_evidence` | 4 active (backfill exhibits), 4 occurrences | append-preserving by design — all-time | dedup_key + `receipt_refs[]` |

The `veto_proven_wrong: 0` is the sharpest fixture: a **real zero**, which must render as an explicit `0`, never a missing line ("a missing line would be a quieter lie" — the honesty pattern borrowed verbatim from the capability card at `core/cognition/capability_card.py`).

## Architecture — one pure reader over four sources

### The spine: read the full history; make full-history *claims* per-source only (owner call, confirmed)
A6 reads the **underlying receipt tables**, not just A1's post-flip scar layer — the receipts genuinely pre-date A1 (58 days of fabrication events, months of vetoes), and reading only scars would be a near-empty ledger that falsely implies Maez "began having evidence today." But it never rolls the sources into one all-time number: **each source reports its own coverage descriptor**, so a 90d-trimmed source can never masquerade as all-time, and a source that started at A1 (redo outcomes) honestly says so.

### Dedup: source-native identity first, sidecar unifies overlaps where it saw them (owner sharpening #2)
The scar sidecar knows only *scarred* events — it cannot dedup pre-A1 raw history it never witnessed. So:
1. Each raw row carries **source-native identity** (`fabrication:<id>`, `veto:<id>`, `consequence:<id>`).
2. The sidecar's `receipt_refs[]` name the raw receipts a scar unified. A6 builds the set of receipt refs claimed by all sidecar rows.
3. **Merged-event count** = raw rows whose native id is *not* claimed by any sidecar row, PLUS one per sidecar active-episode (the scar *is* the merged event). A raw fabrication row that A1 later scarred is counted **once** (as the scar), never twice.

Result: `sources.*` gives the receipt-level truth per store; `merged_events` gives the deduplicated event-level truth. Both honest, both shown.

### No hardcoded source facts — each source exposes its own coverage descriptor
A6 must **not** encode "fabrication retention is 90d" — that fact belongs to `fabrication_memory` and would rot silently if it changed. Each source module gains a minimal **read-only** `coverage()` helper reporting its own policy from its own constant (`_FAB_RETENTION_DAYS`, "none", "append_preserving"). A6 composes the descriptors it is handed. Where a module lacks one, the plan adds it (pure read, no behavior change, flag-independent-safe because read-only).

### What it computes (deterministic; no LLM, no write, no score)
`self_evidence_digest(window=None) -> dict`:
```
{
  "kind": "self_evidence_integrity_ledger",
  "generated_at": <ts>,
  "window": null | {"since": <ts>, "until": <ts>},   # optional query param, NOT a baked-in category
  "sources": {
    "fabrication_events": {"status": "ok"|"no_data"|"unavailable",
        "retained_rows": N, "earliest_row_ts": .., "latest_row_ts": ..,
        "coverage": "90d_best_effort", "native_id_prefix": "fabrication"},
    "veto_proven_wrong": {"status": "ok", "count": 0, "total_veto_events": 3,
        "earliest_row_ts": .., "coverage": "all_time_verified", "native_id_prefix": "veto"},
    "consequence_scar_classes": {"status": "ok",
        "by_class": {"card_rejected": 6, "claim_receipt_redo": M, "dream_rejected": .., "fabrication_catch": ..},
        "outcome_detail": {"claim_receipt_redo": "unstructured"},   # held/corrected split NOT parsed from free-text (A1-lane follow-up)
        "coverage": "all_time_verified", "native_id_prefix": "consequence"},
    "scar_sidecar": {"status": "ok", "active_episodes": 4, "total_occurrences": 4,
        "coverage": "append_preserving_all_time"}
  },
  "merged_events": {"distinct_integrity_events": K, "by_class": {..}, "overlap_unified": U},
  "coverage_note": "per-source; no single all-time claim"
}
```
- **Held-vs-corrected redo split** (floor vs accepted) is only in the redo scar's free-text context today. **v0 does not parse free-text to derive a covenant-facing count** (soft interpretation — the thing A6 exists to avoid). **PINNED (Codex spec-HOLD): A6 does NOT add a structured outcome tag — that would make the reader a writer / an A1 migration slice, violating A6's core covenant.** So v0 reports `claim_receipt_redo` as a **combined class** with `outcome_detail: "unstructured"`. The held-vs-corrected split is deferred to a **separate A1-adjacent receipt-schema follow-up** (A1's lane, not A6's) — never authored from inside A6.
- **Windowing** is a query parameter only. A6 adds **zero** hardcoded temporal windows (the audit already flagged four).

### The surface (inspection only — owner Q1)
- `self_evidence_digest()` — the pure aggregator (deterministic, fully unit-testable). **This is the covenant-critical deliverable.**
- **v0 ships ONE owner inspection surface: a runnable `scripts/self_evidence.py`** (gated behind `MAEZ_SELF_EVIDENCE`) — matching how A1 backfill / A3 curation were witnessed, and keeping web/telegram wiring out of the reader-boundary-critical first slice (plan/spec reconciliation, 2026-07-03: Codex + Claude agreed script-only v0).
- The `/self-evidence` telegram command and the cockpit panel are **deferred thin consumers** of `self_evidence_digest()` — later, separately-witnessed slices (the digest function makes each trivial). v0 wires neither.
- **No** prompt / capability-card / voice / self-card wiring. The digest is *available* for coherence-rail v0.1 and the self-card to consume in later slices; v0 wires none.

### Flag + rollout
`MAEZ_SELF_EVIDENCE=1` gates the surface (command + panel). A6 has **no write path** — it reads existing tables — so flag-off is trivially byte-identical, and even flag-on mutates nothing. The `coverage()` read-only helpers added to source modules are pure and land unconditionally (no behavior change).

## The covenant pins
1. **Reader, never author.** No LLM anywhere in A6. No write path. No synthesized sentence. It reads receipts and counts them.
2. **No score, ever.** Counts + timestamps + coverage. No grade, ratio-as-verdict, or weighting. Nothing optimizable ([[feedback_telos_stays_empty_compression_is_mechanism]]).
3. **No first-person rendering in v0.** `fabrication_events: N rows`, never `I have fabricated N times`. Identity claims are self-card territory with their own witness ([[feedback_dont_spec_maez_behavior]]).
4. **Per-source coverage, no global all-time claim.** Each source labels its own retention truth; A6 never merges them into one unqualified number. A missing/empty source renders explicit `no_data`/`0`, never omission ([[feedback_hardcode_organs_not_opinions]]).
5. **No duplicated source facts.** Retention/coverage policy lives in each source module's `coverage()`, not hardcoded in A6.
6. **Full history read, honest depth shown.** Reads raw tables (pre-A1 receipts included); labels each source's real earliest row — never pretends evidence began at A1.

## Task 0 for the plan (verify before code)
1. Confirm each source's public read API and add read-only `coverage()` where missing (fabrication_memory has none; consequence has `stats`; veto has `all_events`; sidecar has `get`). Pin return shape.
2. Confirm `consequence_memory` scar-class rows carry the native `id` and class needed for `by_class` + `consequence:<id>` refs. (The redo held/corrected split is already DECIDED — combined class, `outcome_detail: "unstructured"`; A6 authors no schema change, so there is nothing to "decide" here beyond confirming the read-side `id`/`class` shape.)
3. Confirm sidecar `receipt_refs` are stored as the `prefix:id` strings A6 will join on (they are, per A1 — verify format `fabrication:<id>` / `veto:<id>` / `consequence:<id>`).
4. Confirm the `scripts/self_evidence.py` inspection-surface shape (v0's only surface; the command/panel are deferred consumers — no mount-point work in v0).
5. Confirm no source-reading path can mutate (open read-only / never call a write API); prove flag-on writes nothing.

## Plan-level pins (Codex spec review, carried into the plan)
- **Read-only, never create:** source readers must open the DBs read-only (e.g. `mode=ro` URI) and must **never** call `_ensure_db`/any initializer that would *create* a missing DB. A missing source → `no_data`, never a freshly-created empty file. (A6 reporting "no_data" must not itself mutate the filesystem.)
- **`scar_tissue` needs a real read/list surface:** A6 consumes sidecar rows through a **public** `ScarSidecar.list_all()` (or equivalent) read API — not a private-schema reach-in / raw SQL against `scar_evidence`. The plan adds that read method (pure, read-only) to `scar_tissue.py`.
- **Live counts belong in the witness artifact, not hardcoded tests:** tests assert *structure and invariants* (dedup-counts-once, no_data-not-omitted, explicit-zero, no `score` key, no first-person string) over **seeded fixtures**; the real 11,577/0/6/4 numbers are recorded in the live-witness artifact, never baked into unit tests (they drift).
- **Overlap proven with a real sidecar row:** the dedup witness must construct an **actual sidecar row whose `receipt_refs` cite a real raw row's native id**, and prove the merged count is one — not merely assert on two synthetic identity strings.

## Out of scope
- Any voice/prompt/card/self-card wiring (later slices, each witnessed).
- Competence/performance receipts (routing quality, task success) — Q2 walled these off; a possible "conduct ledger" is a separate future proposal, not A6.
- Held/corrected redo split — an A1-adjacent **receipt-schema** follow-up in A1's lane; A6 never authors it (see the redo pin above).
- Any first-person or narrative rendering (self-card territory).
- A2/A10 (continuity fingerprint / memory kernel) — separate slices.

## Witnesses
**Host (seeded fixtures — invariants, not live numbers):** `self_evidence_digest()` returns correct per-source counts + coverage labels; a missing DB renders `status: no_data` (NOT omitted) **and creates no file** (read-only proof); `veto_proven_wrong` with zero likely_wrong rows renders explicit `count: 0`; a **real seeded sidecar row whose `receipt_refs` cite a seeded raw fabrication row's native id** makes that event count **once** in `merged_events` (dedup proof — not synthetic strings); a raw fabrication row with no scar is counted (full-history proof); no key named `score`/`grade`/`rating` appears anywhere in the output (structural anti-score test); no first-person string in any rendered surface (vocabulary test); flag-off byte-identical AND flag-on writes zero rows to any source (read-only proof).
**Live (owner, after flip):** `scripts/self_evidence.py show` returns the real index — fabrication coverage says `90d_best_effort` with the true 58d earliest; veto shows `0`; card_rejected shows `6`; sidecar shows the 4 backfill exhibits; the 4 scars are counted once (not also as their cited receipts). The number 11,577 appears as a labeled receipt count, and nowhere as a first-person claim.

## Predicted effect
After A6: the receipts of Maez's corrections — scattered today across four stores with no reader — become one honest, deduplicated integrity index the owner can inspect and later organs can cite. It answers *"what evidence exists?"* with counts, timestamps, and per-source coverage, and structurally refuses to answer *"what does that prove I am?"* — no score to optimize, no first-person claim, no LLM in the loop. It is the substrate on which a truthful self-account can later be built, without itself being a self-esteem machine.

## Spec Self-Review
**Placeholder scan:** coverage()-helper shapes, sidecar public read-API shape, cockpit mount point deliberately Task-0-deferred (verify-before-encode). Redo split is DECIDED (combined + `outcome_detail: unstructured`), not deferred — A6 authors no schema. No TODOs.
**Consistency:** reader-not-author + no-score + no-first-person + per-source-coverage + full-history-read repeated across crux, pins, and witnesses; Q1 (inspection-only) and Q2 (integrity spine) honored throughout; all four sources' live coverage verified before claiming their labels.
**Scope:** one pure reader + four coverage helpers + one command + one panel. Voice/competence/narrative/held-corrected-split all walled off.
