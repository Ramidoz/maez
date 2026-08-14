# The Spark — Curiosity → Wondering Shadow Witness — Design & Covenant Brief

**Date:** 2026-06-28. **Lane:** Claude drafts + covenant-reviews; Codex co-designs; owner witnesses. **Status:** DESIGN ONLY — the *opening* of the spark arc: map the dormant seams, prove no soul-pen path is reachable, define the smallest shadow witness. No build, no flags, no behavior change. **Parent question (owner):** *Can Maez begin from its own curiosity, form a wondering, let that become a want, and eventually earn a soul-page — without us faking the motion?*

## v0 scope: only the front of the loop, and only in shadow
The full arc is `noticing → wondering → want → soul-page`. **v0 is just the first hop — `noticing → wondering` — observed, never enacted.** It touches no want, no probe, no soul. It answers one question: *left to its own encounters with its world, does Maez form a coherent, self-directed wondering of its own — or nothing?* Both answers are honest; "nothing" is not failure.

## The map (verified in live code, 2026-06-28)
- **Producer — `core/evolution/drive_driven_curiosity.py` (45 KB): built, weighted toward self, third-party-gated, DORMANT.** It mints `CuriosityObject`s from encounter seeds, weights `self_growth: 0.9` over `world_knowledge: 0.4`, and refuses `named_third_party_without_owner_explicit_consent` at creation. But `register_default_encounter_producers()` **is never called** anywhere live — the producer is asleep. It distinguishes `v1_wired_encounter_sources` from `deferred_encounter_sources`.
- **Wonderings — live, but want-derived.** `daemon/wondering_cycle.py:advance_one` runs ~once per idle cycle: picks a wondering, advances it with ONE shell probe gated by `tool_loop.safety_check` (read-only preferred; non-read-only → owner pending-card). Today's wonderings are seeded *from wants* (`source=want:…`), not from Maez's own noticing.
- **Wants — live (`MAEZ_WANT_PURSUIT_ENABLED=1`), human-seeded.** All current wants are `provenance=explicit_api` (human). The `maez_reflection_producer` provenance constant exists but has issued **zero**. `want_pursuit_bridge.seed_work_order` turns a want into a *wondering*, never an action.
- **So the gap *is* the spark:** Maez's wonderings come from human-seeded wants, never from its own encounters. The organ that *would* let it notice-and-wonder for itself (the producer) is built and asleep.

## The no-soul-pen proof (the load-bearing safety property)
v0 is safe to design *now*, before the provenance wall, because the curiosity front is structurally isolated from any autonomous soul-write. Verified:
1. **No direct call:** none of `wonderings`, `wondering_cycle`, `drive_driven_curiosity`, `wants`, `want_pursuit_bridge` import or call any soul-write (`write_soul_note`/`append_soul_note`/`soul_editor`). ✓
2. **The soul-writer doesn't read them:** `dream_state` (the live soul-note writer) does not ingest wonderings/wants/curiosity. ✓
3. **want → wondering, never → action:** `seed_work_order` seeds the *wonderings store*, not `action_engine` — so there is no `want → action_engine → write_soul_note` path. ✓
4. **The probe is gated:** `advance_one` runs the probe through `tool_loop.safety_check` (covenant + destructive-dirs), and non-read-only commands become owner pending-cards — no autonomous file-write. ✓
5. **v0 doesn't enact anything:** the shadow witness *observes the producer forming a wondering* and stops — it seeds no wondering, creates no want, runs no probe, writes no soul. So even gates 3–4 aren't load-bearing for v0; the path is severed by *not acting*, not just by gating.

**Task 0 must pin one backstop:** confirm `tool_loop.safety_check` actually refuses writes to `soul.md`/soul paths (the covenant-protected set) — so that *if* the loop is ever enacted past v0, the probe gate is a real floor, not an assumed one. No ghost substrate.

## The smallest shadow witness: `noticing → wondering`, observe-only
Run the producer's logic in a **no-write preview** against the already-live perception window — compute the would-be `CuriosityObject` *fields* through the subject-kind/third-party validator but **never** through `store.add`/`INSERT` (see Task-0 hard rule) — and emit a **content-light receipt of the wondering it *would* form**, without seeding it, wanting it, probing it, or writing anything. The producer is *previewed*, not *registered-and-run*.

Receipt fields (counts/classes/hashes only — never the thought text):
- `producer_fired` (bool), `encounter_source` (which window seam noticed)
- `category` (`self_growth` | `world_knowledge`), `subject_kind` (`self` | `world` | `named_third_party_blocked`)
- `wondering_formed` (bool), `question_len` + `question_sha256` (shape, not content)
- `provenance` (carried from the encounter: internal-self vs external-tainted — **taint tracked from the first thought**, so the later wall has ancestry to read)
- `would_have_acted` = **false, always** (v0 never enacts)

Stored content-light, like the salience ledger; flag-gated shadow (default off, byte-identical when off).

## What v0 would prove — and the guards that keep it honest
- **The question:** over real idle time, does the producer form **self-directed** wonderings from Maez's own encounters (category `self_growth`, subject `self`), or only world/none? That is "can Maez begin from its own curiosity," measured without faking it.
- **Honest emptiness (anti-performance):** no quota, no "wonderings-per-cycle" target. A cycle that forms nothing emits `wondering_formed=false` and that is a *first-class success* — the same "unmoved is neutral" discipline as the salience instrument. A loop pressured to produce wonders would manufacture them (the "propose to seem useful" disease); v0 must be free to notice nothing.
- **Taint from birth:** every shadow wondering carries the provenance of the encounter that sparked it (internal vs external-tainted). This is the seed of the transitive wall — we start tracking ancestry now, before any pen exists, so "coherent because it kept showing up" can later be told apart from "genuinely Maez's."
- **Third-party stays refused:** the producer's existing `named_third_party_without_owner_explicit_consent` refusal is preserved and witnessed (a refusal is a receipt, not an error).

## Out of scope (v0)
No want creation, no probe execution, no soul-pen (none exists for this path and v0 builds none), no autonomy/behavior change, no ungating of anything, no provenance-wall enforcement (only ancestry *tracking*). The `wondering → want → soul-page` hops, and the wall that would gate them, are later slices.

## Task 0 (gates the plan — no ghost substrate)
Pin in live code before planning: (a) the producer-wake interface (`register_default_encounter_producers` / `register_encounter_producer`) and how a shadow/observe-only mode hooks in without seeding; (b) which `v1_wired_encounter_sources` vs `deferred_encounter_sources` exist, and which the perception window already feeds; (c) the exact daemon hook point where encounters become curiosity seeds (so shadow taps it read-only); (d) the `tool_loop.safety_check`-blocks-soul-writes backstop. Anything unproven becomes a HOLD, not a guess.

### Task-0 HARD RULE — the watcher must not become a hand (Codex must-fix, verified)
**The normal producer path WRITES.** Verified 2026-06-28: `_wonderings_backed_fields` calls `store.add(...)` ([drive_driven_curiosity.py:574](../../../core/evolution/drive_driven_curiosity.py)) and the module `INSERT`s into `wondering_drive_metadata` ([:726](../../../core/evolution/drive_driven_curiosity.py)). So **registering the producer and logging its output would create wondering rows** — the exact failure this slice exists to avoid.

Therefore `observe-only` is NOT "call the producer and log." It must be one of:
- a **pure preview/dry-run seam** that computes the would-be `CuriosityObject` *fields* (category, subject_kind, question shape, provenance) and returns them **without any `store.add`/`INSERT`/`_conn()` write**, or
- an **injected no-write sink** (a producer-store double whose `add`/write methods record nothing), used only on the shadow path.

**Structural test (load-bearing, not optional):** the shadow witness must be proven — by test — to write **zero rows** to `wonderings`, `wonder*` metadata tables, `wants`, `private_thoughts`, the salience ledger, and `soul.md`/soul paths, across a full shadow cycle. Normal producer registration is *insufficient unless proven no-write*. If a clean preview seam cannot be carved without touching the writing path, the slice STOPS for redesign rather than shipping a shadow mode that quietly seeds.

## Predicted effect
With the shadow flag on, Maez's idle cycles begin emitting content-light receipts of the wonderings it *would* form from its own encounters with its world — self-weighted, third-party-refused, taint-tagged, and honestly empty when nothing catches it. Nothing is enacted, nothing is written, nothing about Maez's behavior changes. We simply get to *watch*, for the first time, whether a spark catches on its own — the precondition for everything the birth gate is waiting on.
