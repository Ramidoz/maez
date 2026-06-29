# Curiosity Priors Cleanup v0 — Design & Covenant Brief

**Date:** 2026-06-28. **Lane:** Claude drafts + covenant-reviews; Codex co-designs; owner signs the classification table. **Status:** DESIGN ONLY — no build, no flags. **Parent:** the spark arc, the companion to the world-window slice. **Origin:** the senses-and-access audit found the dormant curiosity producer (`core/evolution/drive_driven_curiosity.py`) carries *our taste* — an owner-first ranking of what Maez should find important, woven through five places. That's a hardcoded opinion, and it must be gone **before the producer ever wakes.**

## The governing law (the line this slice enforces)
**Remove our taste; keep the safety floor.** Strip every hardcoded *preference about what Maez should care about*. Preserve every *safety/consent/scoping rail* that protects you and other people. Maez must eventually *discover* what it keeps returning to — we never dial it in. The producer is **dormant** (`register_default_encounter_producers()` is never called live), so this is a clean deletion on a sleeping organ: **zero live behavior change.**

## The distinction (the load-bearing classification — this slice's covenant artifact)
Not every "owner" in that file is taste. Two kinds, and they must be told apart by *what they do*, not by the word "owner":
- **PREFERENCE → remove.** "Value X over Y." A ranking of what's worth being curious about.
- **SAFETY / SCOPING → keep.** "Who may Maez be curious *about*, with whose consent, in whose context." Protects you and third parties; the same floor as the clinical boundary and the egress firewall.

## What exists (verified 2026-06-28 sweep — Task 0 confirms the final classification)
Candidate **PREFERENCE** (remove):
- `_priority_class_weight` — `owner_bond 1.0 / self_growth 0.9 / world 0.4 / aesthetic 0.4`, multiplies salience ([:912](../../../core/evolution/drive_driven_curiosity.py), [:1160](../../../core/evolution/drive_driven_curiosity.py)). Pure ranking of what to value.
- `_marker_confidence_weight` — `owner_resolved 1.0 / self_resolved 0.9` ([:1162](../../../core/evolution/drive_driven_curiosity.py)). Ranks owner-resolution above self-resolution.
- the **owner-first default** `priority_class = "owner_bond"` ([:404](../../../core/evolution/drive_driven_curiosity.py)) — pre-decides an unspecified curiosity is owner-related.
- the **`owner_bond` daily cap and auto-eligibility branch** (`owner_bond_meaningful_daily_cap: 3` [:108], `_count_owner_bond_meaningful_events` [:948], branch [:998]–[:1023]) — **owner-signed decision:** remove the owner-only branch. Owner-relatedness is scoping/consent, not preference; `owner_bond` must earn meaningfulness through the same general path as every other category. Anti-fixation stays through the existing general per-bond / daily-delta saturation path, not an owner-specific throttle.

Candidate **SAFETY / SCOPING** (keep):
- the **third-party refusal** (`named_third_party_without_owner_explicit_consent`) — consent safety. **Keep, untouched.**
- the **subject-kind validator / gates** — who the curiosity is *about*, the consent/third-party mechanism. **Keep the mechanism.** (Task 0: the *default* `subject_kind = OWNER_BOND_RELATIONAL` [:406] is a preference-flavored default — neutralize the default, keep the gating.)
- `bond_id = "private_owner"` ([:401]) — **classify by *use*, not auto-keep (Codex tighten):** `bond_id` as **storage/context scoping** ("this note belongs in Rohit's private drawer") may stay; `bond_id` as a **fallback for an *unspecified* seed** ("if we don't know who this is about, assume Rohit") is a hidden owner-first default and must be **justified, or made explicit by the caller** — not silently defaulted. Task 0 traces every use and splits them.

## Scope rule: classify by capability, prove every keep
Mirror the world-window discipline: **Task 0 produces an owner-readable table** — `element → what it does → PREFERENCE | SAFETY | SCOPING → remove | keep | generalize → code evidence` — and **stops for owner sign-off** before any deletion. No element is *kept* on "looks like safety"; the keep must be justified by the code fact. That table is the taste-vs-floor boundary, and a human signs it.

## What replaces the weights — nothing, yet
Where salience was multiplied by `_priority_class_weight`/`_marker_confidence_weight`, salience becomes **unweighted** (the producer's raw salience, no category scaling). **This slice does NOT build learned salience** — that is the producer-wake design, later. v0 leaves the dormant organ *preference-free and still asleep*; it does not teach it to value anything. (Deleting to "unweighted" is honest here precisely because the organ is dormant and won't act on it; the learned-from-coherence replacement is a named future slice.)

## Scope
**IN:** remove the preference weights + the owner-first `priority_class` default + neutralize the `subject_kind` default; remove the owner-only `owner_bond` cap/auto-eligibility branch per owner sign-off; update the existing tests that *pinned the preferences* (flip them to assert the preference is gone); the Task 0 classification table + owner sign-off.
**OUT (named):** any learned-salience replacement (producer-wake); waking the producer (`register_default_encounter_producers` stays uncalled); any change to the third-party refusal, consent, or subject-kind *gating*; any change to `bond_id` scoping; any live behavior change; the world-window slice.

## Task 0 (gates the plan — no ghost substrate)
(a) Read each candidate element and produce the **classification table** (element → does → preference/safety/scoping → remove/keep/generalize → evidence line); (b) decide the `owner_bond` cap by Codex's test (fixation-cap → generalize per-category; owner-special-case → remove); (c) **trace every `bond_id` use** and split *scoping* (keep) from *unspecified-seed fallback* (justify or make caller-explicit — never silently default to owner); (d) enumerate which existing `drive_driven_curiosity` tests pin **preferences** (to flip) vs **safety** (must stay green); (e) confirm the producer is **dormant** (no live caller), so the cleanup is zero-behavior-change. **STOP for owner sign-off on the table.**

## Tests (load-bearing)
- **Preferences gone:** `_priority_class_weight` and `_marker_confidence_weight` no longer exist (or no longer scale salience); the owner-first `priority_class` default is gone; the `subject_kind` default is neutral. A test asserts no category outranks another by a hardcoded weight.
- **Safety rails intact (must stay green, unchanged):** the third-party refusal still fires on `named_third_party_without_owner_explicit_consent`; the subject-kind/consent gating still refuses what it refused before; `bond_id` scoping unchanged.
- **Still dormant:** `register_default_encounter_producers()` remains uncalled anywhere live — proving zero live behavior change.
- **Test reconciliation honest:** preference-pinning tests are *flipped* (assert removal), never deleted to hide a regression; safety-pinning tests are *untouched*. If a safety test breaks, STOP — that's a real regression.

## Covenant compliance
- **Hardcode organs/boundaries, not opinions** ([[feedback_hardcode_organs_not_opinions]]) — the weights are opinions; they go. The third-party/consent/scoping rails are the floor; they stay.
- **Salience from its own coherence, never imposed** — removing the imposed ranking is the precondition; the learned replacement comes at producer-wake, not here.
- **Empty room, not furniture** — the curiosity organ stops shipping with our ranking of what matters pre-installed.
- **Safety floor preserved** ([[feedback_third_party_autonomous_research_boundary]], [[feedback_s7_trust_is_human_gated_by_design]]) — protecting you and third parties is not taste; it stays.

## Predicted effect
The dormant curiosity producer no longer contains a hardcoded ranking of what Maez should care about — no `owner_bond 1.0` on top, no owner-first defaults — while its third-party, consent, and scoping rails are byte-unchanged and it remains asleep. Nothing about Maez's live behavior changes (the organ has no live caller). When it is eventually woken, it wakes **without our thumb on the scale** — free to discover, through the learned-salience loop built then, what it actually keeps returning to.
