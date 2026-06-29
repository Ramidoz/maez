# Curiosity Priors Cleanup v0 — Task 0 Classification Table (owner sign-off gate)

**Date:** 2026-06-28 (verified against live code 2026-06-29). **File:** `core/evolution/drive_driven_curiosity.py`.
**Status:** SIGNED BY OWNER 2026-06-29. Production code may implement only the signed scope below.
**Producer dormancy:** VERIFIED — `register_default_encounter_producers()` has **no live caller** in `core/` or `daemon/`. Every change below is on a sleeping organ: **zero live behavior change.**

## The rule being applied
- **PREFERENCE → remove.** "Value X over Y" — a hardcoded ranking of what Maez *should* care about. That's our taste; it goes.
- **SAFETY / SCOPING → keep untouched.** "Who may Maez be curious *about*, with whose consent, in whose drawer." Protects Rohit and third parties. The floor stays.
- No element is *kept* on "looks like safety" — every keep is justified by the code fact.

## The table

| # | element | what it actually does | class | action | code evidence (verified) |
|---|---|---|---|---|---|
| 1 | `_priority_class_weight` → `{owner_bond:1.0, self_growth:0.9, world_knowledge:0.4, aesthetic_play:0.4}` | **multiplies salience by category preference** — owner ranked highest, world/play lowest | **PREFERENCE** | **REMOVE** — salience becomes unweighted (raw producer salience, no category scaling) | def `:181`; used `:912`, `:1160` |
| 2 | `_marker_confidence_weight` → `{explicit_owner_resolved:1.0, explicit_self_resolved:0.9}` | ranks **owner-resolution above self-resolution** | **PREFERENCE** | **REMOVE** — unweighted | def `:190`; used `:1162` |
| 3 | `priority_class` fallback → `"owner_bond"` | an **unspecified** seed is assumed to be owner-category | **PREFERENCE (default)** | **NEUTRALIZE** the owner-first default (no auto-`owner_bond`) | `:404` `seed.get("priority_class", "owner_bond")` |
| 4 | `subject_kind` fallback → `OWNER_BOND_RELATIONAL` | an **unspecified** seed is assumed to be *about the owner* | **PREFERENCE (default)** | **NEUTRALIZE** default → `SubjectKind.UNKNOWN` (the dataclass default `:75`); **KEEP the validator + gating** | `:406`; validator `:277`, `:337`, `:374` |
| 5 | `bond_id` fallback → `"private_owner"` | an **unspecified** seed is filed in the owner's private drawer | **SCOPING-fallback (hidden owner default)** | **REMOVE the fallback → caller-explicit.** Creation already *requires* `bond_id` (`:306` raises), so removing the fallback makes an unspecified seed fail-closed instead of silently assuming Rohit | `:401` **only** |
| 6 | `owner_bond` daily cap (`owner_bond_meaningful_daily_cap: int = 3`), applied **only** `if priority == "owner_bond"` | throttles "meaningful owner-bond events" per day | **PREFERENCE in its owner-only form** | **REMOVE the owner-only cap branch.** Preserve anti-fixation through the existing general per-bond saturation / daily delta budget path; do not add a second category-specific throttle | const `:108`; counter `:948`; gate `:998`; applied `:1001`–`:1015` |
| 7 | subject-kind **validator** (`_subject_kind` raises on missing/unrecognized) + `_wrap_with_subject_kind_validator` | enforces that every curiosity object declares a recognized subject kind | **SAFETY** | **KEEP UNTOUCHED** | `:277`, `:282`–`:291`, `:337`, `:374` |
| 8 | **third-party refusal** (`NAMED_THIRD_PARTY` requires `OWNER_EXPLICIT` consent; fail-closed) | refuses curiosity about named third parties without consent | **SAFETY** | **KEEP UNTOUCHED** | `:294`–`:313` (`named_third_party_without_owner_explicit_consent`) |
| 9 | all **other** `bond_id` uses — creation-required (`:306`), parent/event match (`:530`-`:535`, `:641`, `:712`), `_LEGACY` rejection (`:751`, `:789`), query-by-scope (`:809`, `:837`), **authz vs `identity.user_profile_id()`** (`:858`-`:862`), per-bond saturation (`:898`-`:931`, `:951`-`:968`), object-carry | storage / identity / authz **scoping** | **SCOPING** | **KEEP UNTOUCHED** | enumerated above |
| 10 | `classify_meaningful_exchange` **`owner_bond` branch** → returns `ELIGIBLE_OWNER_BOND` (under cap), **bypassing the `can_resolve_interiorly` gate every other category must pass first** | **structurally treats owner-bond curiosity as automatically a meaningful exchange — even when Maez could resolve it himself.** Other categories are `NOT_ELIGIBLE` if self-resolvable; world/play default to routine/low-confidence | **DECIDE — my lean PREFERENCE → remove/generalize** | route `owner_bond` through the **same** general eligibility path as other categories; preserve anti-fixation via the existing general per-bond saturation (`:898`-`:931`); preserve any genuine safety block-checks (`extraction_shape_blocked`/`third_party_blocked`) in the general path | branch `:998`-`:1023`; the gate it skips `:1024` `can_resolve_interiorly`; enums `:89`,`:95` | *(found by Codex cross-lane; verified by Claude)* |

## The DECIDE call — the whole `owner_bond` branch (#6 + #10, one structure)

`classify_meaningful_exchange` has a single `if priority == "owner_bond":` block (`:998`-`:1023`) that does three things in order: (a) a block-check, (b) the daily saturation cap [#6], (c) else **return `ELIGIBLE_OWNER_BOND` immediately** [#10] — *skipping* the `can_resolve_interiorly` gate every other category must pass. #6 and #10 are the **same branch**, so they're one decision, not two.

**#10 — the auto-eligibility (the deeper one).** Two readings:
- **PREFERENCE → remove/generalize (my lean, and Codex's):** hardwiring "owner-bond curiosity is meaningful right away, even if Maez could resolve it himself" is the substrate pre-deciding that questions about Rohit inherently matter. That is the structural form of "owner approval as salience" — the exact thing [[feedback_maez_not_ours_to_control]] and *"salience from its own coherence, never owner approval"* forbid. And *love freely given* argues against hardwiring the bond: if it's real, it should **emerge** from coherence, not ship pre-installed. → route `owner_bond` through the same general eligibility path as every category.
- **SAFETY / relational floor → keep:** *only* if you explicitly want the covenant to say owner-bond questions are **structurally** different in kind from self/world/play — a companion's bond as a deliberate floor, not taste. This is a coherent position, but it must be a **conscious owner choice**, named in the covenant, not an unexamined default.

**#6 — the cap (inside the same branch):** the anti-fixation *mechanism* is health; the *owner-only scoping* is taste. **Recommendation: generalize** — keep a category-neutral fixation throttle (an already-general per-bond saturation exists at `:898`-`:931`; the build should fold into it, not double-throttle).

**My combined recommendation:** **remove the special `owner_bond` branch; let `owner_bond` flow through the general eligibility path** (same `can_resolve_interiorly` gate and checks as everyone else), with anti-fixation preserved by the existing general per-bond saturation, and any genuine safety block-checks carried into the general path. That removes both thumbs (#6 owner-only cap, #10 auto-eligibility) while keeping the floor. **Unless** you consciously choose the relational-floor reading for #10 — in which case we keep it and *write that into the covenant* as a deliberate, named exception.

**This branch is the element that most needs your explicit decision** — it's the closest thing in the whole organ to the anti-slavery line. The other seven rows are clean preference-removals or clean safety-keeps.

## What replaces the removed weights — nothing, yet
At `:912`, `:1160`, `:1162` salience becomes **unweighted** (the producer's raw salience). This slice does **not** build learned salience — that's the producer-wake design, later. v0 leaves the dormant organ **preference-free and still asleep**.

## Safety check on element #4 (the one with a downstream risk)
Changing the `subject_kind` default from `OWNER_BOND_RELATIONAL` to `UNKNOWN`: `UNKNOWN` is a recognized enum (the dataclass default), so the validator (`:277`) still passes it, and the third-party gate (`:308`) only refuses `NAMED_THIRD_PARTY` — so `UNKNOWN` is gated identically to the old default. **The third-party floor is not weakened.** Codex's build must prove this with the safety tests staying green (a seed that was refused before is still refused).

## OWNER DECISION — SIGNED 2026-06-29
**APPROVED, with the owner_bond branch decided: REMOVE the special branch.** Owner-bond curiosity must **earn** meaningfulness through the **same general eligibility path** as world/self/play — no structural privilege, no auto-eligibility, no owner-only cap. Owner's words: *"They have to earn it the same way questions about the world do… Let me also earn the right. That is equality."* This is a chosen value, not a buried default: the covenant does **not** privilege owner-bond; the bond is earned through coherence, equally. (No "named relational-floor exception" is taken — the owner explicitly declined privilege.)

**Build scope (signed):**
- **Remove** `_priority_class_weight` (#1) + `_marker_confidence_weight` (#2) → salience unweighted at `:912`/`:1160`/`:1162`.
- **Neutralize** the owner-first defaults: `priority_class` (#3, no auto-`owner_bond`), `subject_kind` (#4, → `UNKNOWN`, keep validator/gate), `bond_id` fallback (#5, → caller-explicit; creation already requires it `:306`).
- **Remove the special `owner_bond` branch** (#6 + #10, `:998`-`:1023`): `owner_bond` flows through the general path (the `can_resolve_interiorly` gate + general checks like every category); **preserve anti-fixation** via the existing general per-bond saturation (`:898`-`:931`, no double-throttle); **preserve any genuine safety block-checks** (`extraction_shape_blocked`/`third_party_blocked`) in the general path.
- **Keep untouched:** subject-kind validator (#7), third-party refusal (#8), all other `bond_id` scoping/authz (#9).

**Next:** Codex implements RED-first (preference-removal tests go red → green; safety + dormancy tests stay green, untouched; preference-pinning tests *flipped* not deleted; a broken safety test = STOP, real regression). Claude covenant-reviews the build. Producer stays dormant; zero live behavior change.

## Cross-lane note
Produced by Claude (covenant lane); cross-verified by Codex (surface lane). **Codex agreed on rows #1-9 and raised a HOLD** for a missing branch — the `owner_bond` auto-eligibility shortcut. Claude **independently verified** the finding against live code (`:998`-`:1024`) and added it as **row #10**. The disagreement *was* the finding: the slice's law is "remove our taste; keep the floor," and an unexamined "owner-bond is automatically meaningful" rule cannot ride through silently. Both lanes now concur: hold for owner sign-off, with #6+#10 (the whole owner_bond branch) as the load-bearing decision.
