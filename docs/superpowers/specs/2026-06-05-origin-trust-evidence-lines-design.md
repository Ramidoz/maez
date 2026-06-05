# Origin-Trust Evidence Lines — Design

**Date:** 2026-06-05
**Status:** DRAFT for owner review → Codex implements / Claude reviews; owner runs the live witness.
**Builds on:** the existing recency/source-**authority** evidence axis in `core/routing/focused_cognition.py` (`_AUTHORITY_LABEL`, `_render_evidence_lines`, the citation instruction — already live); the `TrustTier` provenance system in `memory/memory_manager.py` (`COVENANT/LIVED/OBSERVED/UNTRUSTED`); the **Intake Bus v0** ([[project_intake_bus_v0]]), which stamps `trust_tier` at admission so recalled memories carry it in metadata. The 2026-05-30 "continuity classifier + trust-tier evidence" slice built the **authority** axis + the continuity classifier (`c2ae550`); this slice builds the **origin-trust** axis it did not.

## 0. Why

Two distinct axes describe a piece of evidence the brain reasons over:
- **Recency / source authority** (already rendered): *is this current-state, recalled memory, recent dialogue, or external web?* — answers "is this now or past?"
- **Origin trust** (this slice): *where does this evidence sit on Maez's trust spine — `COVENANT/LIVED/OBSERVED/UNTRUSTED`?* — answers "how trustworthy is its origin?"

Today every recalled item reads as `recalled memory — past authority` regardless of origin, so a covenant self-belief, a lived interaction, an **observed account fact (the GitHub repo count)**, and an untrusted web scrape are indistinguishable to the brain. The bus now assigns that origin-trust honestly at admission; this slice **surfaces it** so the brain can weight an observed/tool fact as an external observation, never as Maez's lived self. This is the direct, designed payoff of the intake-bus doorway.

## 1. The render (what the brain sees)

**Strict label map** (`_ORIGIN_TRUST_LABEL`, `trust_tier` value → display label) — disambiguates the `observed` collision (source-type "observed (fresh)" ≠ origin `observed`):

| `trust_tier` | rendered label |
|---|---|
| `covenant` | `covenant` |
| `lived` | `lived` |
| `observed` | `observed/tool` |
| `untrusted` | `untrusted` |

**Render rule** — append `· origin trust: <label>` to an evidence line **only** when the item carries a tier the strict map knows:

```
[E1] recalled memory — past authority · origin trust: observed/tool
     GitHub reports 7 public repositories on the owner's profile
```

**Fail-closed, three absence/unknown cases (none renders a tier, but they differ):**
- **`trust_tier is None`** (legacy/untiered: fresh items, pre-bus memories) → **omit silently** (expected; absence ≠ untrusted — never label it `untrusted`).
- **`trust_tier` is an unknown non-`None` value** (typo, or a new tier added without updating the map) → **omit + logged warning + a unit test that fails**. An unknown value must never leak to the brain as `origin trust: banana`. Only the fixed map renders.
- **No origin-trust on non-recalled items** (fresh perception, dialogue, web) that carry no stamped tier → omit.

**`[E#]` token byte-identical.** The suffix lives in the authority-parenthetical region, never in the `[E#]` label, so `check_groundedness` (keys on `local_label`, `focused_cognition.py:~595`) is unaffected. This keeps a trust-label slice from becoming a citation-system slice.

## 2. The brain instruction

Add a distinct `_ORIGIN_TRUST_INSTRUCTION`, appended to the focused-synthesis system block alongside the existing authority instruction. (The existing constant is named `_TRUST_TIER_INSTRUCTION` but is actually the *authority* instruction; **the rename is a parked cleanup, not done here** — no churn.) Content:

> Each `[E#]` may also carry `origin trust:` — where the evidence's origin sits on Maez's trust spine. **covenant** = Maez's own core self/values; **lived** = real lived interaction with the owner; **observed/tool** = an external tool/account observation (true about the source, **not** Maez's lived self); **untrusted** = unverified/external, hedge it.
> - If `origin trust` is **present**, use it as the origin-trust signal.
> - If **absent**, treat the item as **untiered legacy/unstamped evidence** — not covenant/lived, and not untrusted.
> - **Never promote `observed/tool` into Maez's lived selfhood.**

## 3. The threading (data flow + footprint)

```
bus stamps trust_tier at admission  →  raw memory metadata
   →  recall partitions carry it per row in metadata
   →  brain_loop.recall_partitions_to_items reads meta["trust_tier"] while the row metadata is still in hand
   →  layer1.RecallItem.trust_tier        (NEW field, default None)
   →  passed through merge.py on RenderedTurn.recall_items (NO transform there)
   →  focused_cognition.assemble_working_set reads getattr(item, "trust_tier") → raw_items tuple (one new element) → EvidenceItem.origin_trust   (NEW field, default None)
   →  _render_evidence_lines appends the suffix when the strict map knows the tier
```

**Three files (the honest footprint — verified against the live path, not a static trace):**
- `core/dispatcher/layer1.py` — add `trust_tier: str | None = None` to `RecallItem`; include it in `to_dict()` (where items are serialized).
- `core/brain/brain_loop.py` — in `recall_partitions_to_items`, read `meta.get("trust_tier")` and set it on the built `RecallItem`. **This is the room where the recalled row's metadata is still attached to the structured item** — reading it here, not in `focused_cognition` after the shape is flattened, is the no-tag-then-flatten discipline. `merge.py:146` only passes the already-built `RecallItem`s through on `RenderedTurn.recall_items`; it is **not** the builder.
- `core/routing/focused_cognition.py` — read `getattr(item, "trust_tier", None)` off the structured recall items, thread it through the `raw_items` tuple to a new `EvidenceItem.origin_trust`, render the suffix (strict map), add `_ORIGIN_TRUST_INSTRUCTION`. **No `EvidenceItemSeed` change** — the structured items the organ consumes are `RecallItem`s, read duck-typed (`EvidenceItemSeed` is a different, internal dialogue-anchor seed).

**Structured vs transcript path (correctly scoped, no overreach):**
- **Structured `recall_items` path** (the modern path; where the GitHub fact flows) — carries origin-trust via the seed.
- **Legacy `<RECALLED tier="raw">` transcript path** — that `tier` is a *storage* tier, not `TrustTier`; this path **gracefully omits** origin-trust (absent → no segment, consistent with the omit rule). Stamping `trust_tier` onto the `<RECALLED>` renderer is a **future follow-up, out of this slice**.

## 4. Flag

**No new flag.** The render lives inside the focused organ, gated by the existing focused-cognition flag. The `brain_loop`/`RecallItem` tier-population is inert when focused cognition is off (it attaches a field nothing reads). Rollback is the existing flag.

## 5. Tests

**Unit (hermetic, RED-first):**
- `brain_loop.recall_partitions_to_items`: a recalled row with `meta["trust_tier"]="observed"` → built `RecallItem.trust_tier == "observed"`; absent metadata → `None`.
- render: `origin_trust="observed"` → line contains `· origin trust: observed/tool`; `covenant`/`lived`/`untrusted` → their labels; `None` → **no** segment.
- **unknown value:** `origin_trust="banana"` → **no** segment **and** a warning is logged (the fail-closed guard; this test failing on a leak is the point).
- `[E#]` tokens byte-identical with and without the suffix; `check_groundedness` coverage ≥ pre-change baseline.
- the assembled system block contains `_ORIGIN_TRUST_INSTRUCTION`'s three rules.
- acceptance: a recalled `observed` memory renders `recalled memory — past authority` **and** `· origin trust: observed/tool` (both axes, no collision).

**Live integration witness (the load-bearing proof — real path, not synthetic):**
- A **real GitHub-`observed` memory row** (stored the way the bus stamps it) → **real `brain_loop.recall_partitions_to_items` `RecallItem` build** → **real `focused_cognition` render** → the rendered working-set text contains `· origin trust: observed/tool`. **No synthetic `EvidenceItem`/`RecallItem`; no daemon-live Telegram turn required** — the proof is the actual recall-partition → `RecallItem` → focused-render path with the real memory row. (Owner may additionally run a daemon-live turn, but the required witness is this real-path integration test.)
- Run the full `.venv/bin/python -B -m unittest discover` before done (schema-pin lesson); cross-lane review apples-to-apples in the asset-rich checkout ([[feedback_worktree_floor_confound]]).

## 6. Acceptance rules

1. `_ORIGIN_TRUST_LABEL` is the strict 4-entry map; only those render.
2. Render appends `· origin trust: <label>` iff the item's `trust_tier` is in the map; `None` → omit silently; unknown non-`None` → omit + logged warning (covered by a failing-on-leak test).
3. Absence is rendered as untiered (omitted), **never** as `untrusted`.
4. `[E#]` tokens byte-identical; groundedness coverage not reduced.
5. `_ORIGIN_TRUST_INSTRUCTION` present with the three rules + tier glosses; `observed/tool` never to be promoted into lived selfhood.
6. `RecallItem.trust_tier` populated in `brain_loop.recall_partitions_to_items` from memory metadata (and in `layer1.RecallItem.to_dict`); threaded to `EvidenceItem.origin_trust` in `focused_cognition`.
7. The legacy transcript path omits origin-trust (no false signal from `tier="raw"`).
8. No new flag; the `RecallItem`/`brain_loop` tier-population is inert when focused cognition is off (it attaches a field nothing reads).
9. The live integration witness passes: real GitHub-`observed` row → real merge→focused render → `· origin trust: observed/tool`.
10. Full suite green (zero new failures, apples-to-apples vs main); no bus-tier-assignment change; no `_TRUST_TIER_INSTRUCTION` rename; no transcript-path change.

## 7. Scope

**In:** `RecallItem.trust_tier` (`layer1.py`) + its population in `brain_loop.recall_partitions_to_items` + `to_dict`; `EvidenceItem.origin_trust` (`focused_cognition.py`); the strict label map + fail-closed render; `_ORIGIN_TRUST_INSTRUCTION`; unit tests + the real-path integration witness.
**Out:** transcript-path (`<RECALLED>`) origin-trust; renaming `_TRUST_TIER_INSTRUCTION`; the cycle-recall consumer (`core/memory/cycle_recall_context.py`); any change to how the bus assigns tiers; any new flag; new tier values.

## 8. Lane

Codex implements the three files + unit tests / Claude reviews / owner runs the live-path witness. Cross-lane verification mandatory ([[feedback_cross_lane_verification_mandatory]]); the `[E#]`-byte-identical + groundedness-coverage bar is the primary review anchor.
