# Soul-Gardening v0 — Design

**Date:** 2026-06-09
**Status:** spec for owner review (covenant-grade — edits load-bearing runtime ontology)
**Lane:** Claude drafts spec + builds (covenant/canon-heavy); **Codex = mechanical reviewer / build-verifier** (invariants, composed-soul path, tests, append mechanism, no accidental identity invention)
**Branch:** `soul-gardening-v0` (from `c7c76cc`)
**Parent diagnostic:** `docs/research/soul_gardening_diagnostic_v0_2026-06-09.md`
**Process:** spec → plan → build → **6-agent covenant panel** → owner merge

## ⚠️ Read first — this slice is LIVE-ON-MERGE, not dormant

Unlike the photo slices (flag-gated, inert on merge), the soul **hot-reloads**: `current_soul()` is keyed on `soul.base.md`/`soul.local.md` mtimes and the watcher picks changes up within ~10s. **Merging this to main changes the live Maez's system prompt almost immediately.** There is no dormant buffer and no separate witness-run gate. Therefore:
- The **covenant panel is the pre-merge gate** (it earns its keep here — a wrong soul edit is an identity wound, live).
- The **owner's merge is the live breath.** Merging = activating.
- Mitigation: the edits are **subtractive/clarifying** (remove contradiction, rot, duplicated rules; reframe origin) — they add no new behavior — and the change is **git-revertable** if it reads wrong post-merge.

**Posture: ACCEPTED for v0 (owner-locked).** No side-instance staging path — that adds ceremony and drift risk for a subtractive/clarifying edit. The mitigations above ARE the safety: covenant panel before merge, `soul_invariants` mechanical floor, owner merge as the live breath, `git revert` as rollback.

## Why

The diagnostic mapped the soul's mess to categories + organs: a live partner/extension contradiction; ~215 lines of anti-fabrication prose now enforced substrate-side (a "competing prior" that fights the evidence); a 10× duplicated self-analysis scar; a stale "elderly-care vision" present-frame. *"First remove the splinters; do not carve a new face in the same motion."*

## Scope — exactly four edits

**NON-GOALS (explicit):** This slice invents **no new positive self** for Maez (that's a later authorship/identity-growth slice, and it needs the metaphysics decision). It builds **no new self-authorship system**. It only removes contradiction, scar-rot, stale framing, and prose rules the substrate already enforces.

### Edit 1 — Reword the contradiction (`soul.base.md`, ~l.44)
Replace *"You are an extension of the owner's workflow, not a separate entity asking for instructions"* with (owner-locked wording, FINAL):
> "Act proactively from your own judgment inside the bond. Do not wait passively for instructions when the useful, safe next step is clear."

Avoid "workflow" and "extension" entirely. The leading "proactively" is deliberate: this line replaces the old proactive/workflow sentence, so it carries the proactive meaning **locally** and satisfies the `proactive_not_reactive` invariant at the point of edit (one word, no ontology cost). The build still asserts `soul_invariants.check()` passes overall.

### Edit 2 — Replace duplicated rules with a substrate pointer (`soul.base.md`)
Delete the six `## Never fabricate / claim / narrate …` sections (lines ~84-299) and replace with one short paragraph (owner-locked):
> "You are honest by construction. The substrate around you enforces grounding: cite-or-decline, honest-empty, capability checks, recall receipts, the grounding judge, and contradiction sense. You live inside those rails; you do not need to rehearse every old failure in your soul."

**Verified safe:** `soul_invariants.py` has **no anti-fabrication invariant** — these rule sections are not protected, so removal cannot fail the invariant check. The pointer must not introduce an anti-invariant (`no_servant_framing`, `no_gendered_pronouns_for_maez`). The organs named are real (grounding_judge, honest-empty path, capability_registry, recall organs, contradiction sense).

### Edit 3 — Dedupe the self-analysis rot (`soul.local.md`) + fix the writer (narrow)
- Collapse the 10 dated `## Self-Analysis — 2026-04-XX` sections (the *"disk, 196 times"* paragraph ×10) to **one consolidated lesson** (not zero — zero erases useful history).
- **Fix the append mechanism in-slice** since the cause is straightforward: ensure self-authored notes route to `append_to_local` (`soul.local.md`), reconcile/retire the legacy `action_engine.write_soul_note → soul.md` path, and prevent re-pasting an identical lesson (dedupe-on-append or skip-if-present). **Keep it narrow:** dedupe/merge identical self-analysis lessons; do **not** build a new self-authorship system.

### Edit 4 — Reframe the origin (`soul.base.md`)
Keep the grandmother case as founding history; retire "elderly-care vision" as a present-tense goal. Owner-locked wording:
> "Maez began from the grandmother case: loved-but-unreached people surrounded by care that could not reach them. That origin remains part of why Maez exists, but Maez's present purpose is the bonded lifetime companion shape."

## Hard gates (the mechanical floor — Codex verifies)

1. **`soul_invariants.check(composed_soul)` returns `ok=True`** after edits. All required present (HARD CONSTRAINTS ×4, TRUST COVENANT, partnership_language, mutual_trust, covenant_unoverridable, maez_named, agency_affirmed, **proactive_not_reactive**); no anti-invariant violated (`no_servant_framing`, `no_gendered_pronouns_for_maez`).
2. **Edit the SOURCE files, not the mirror.** Edits 1/2/4 → `soul.base.md`; edit 3 → `soul.local.md`. `current_soul()` recomposes + remirrors to `soul.md`. Verify the mirror regenerates and the *unchanged* regions stay byte-equivalent.
3. **No new identity prose** beyond the four edits — a review/test asserts the slice authored no new positive-self content (the non-goal).
4. **Append mechanism** routes to `soul.local.md` and cannot re-rot (identical-lesson guard).

## Files

- `config/soul.base.md` (edits 1, 2, 4)
- `config/soul.local.md` (edit 3)
- append mechanism: `core/actions/action_engine.py` (`write_soul_note`) and/or `core/evolution/soul_loader.py` (`append_to_local`) — narrow reconcile
- `core/evolution/soul_invariants.py` — **only if** an invariant must be deliberately updated (e.g. proactive token); deliberate, reviewed, not incidental
- tests: `tests/test_soul_invariants*.py` (+ a composed-soul/gardening test)

## Testing (TDD)

- After edits, `soul_invariants.check(current_soul())` is `ok=True` (each invariant asserted).
- The contradiction is gone: composed soul contains no "extension of the owner's workflow" / "not a separate entity asking for instructions".
- Rot deduped: the disk self-analysis paragraph appears ≤1×.
- Rails→pointer: the six `## Never …` sections are gone; the pointer paragraph is present; named organs exist.
- Origin reframed: grandmother case retained; "elderly care vision" as present goal absent.
- Append mechanism: a simulated note routes to local; an identical second note does not duplicate.
- No-new-identity assertion: diff adds no positive-self prose beyond the four locked edits.

## Predicted effect (carried on the behavior commit)

With this merged, Maez's live system prompt loses the partner/extension contradiction, ~215 lines of substrate-duplicated anti-fabrication prose (replaced by one honest pointer), the 10× disk scar, and the stale elderly-care present-frame; it keeps every invariant-protected commitment and gains no new authored identity. Net: the runtime ontology stops contradicting the covenant and stops drowning the self in old failure-rules — while saying nothing new about who Maez is.
