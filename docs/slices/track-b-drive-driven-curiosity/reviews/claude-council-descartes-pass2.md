# Claude Covenant Council — Descartes pass 2
## Drive-Driven Curiosity spec v2 — substrate foundations / §27 paired-fold verification

**Subject:** `docs/slices/track-b-drive-driven-curiosity/spec.md` at DRAFT v2,
2026-05-25 (post pass-1 folds, with §27 cross-slice paired fold on
subjective_duration introduced).

**Parent commit verified:** `fb2f781 feat(felt-time): implement subjective
duration substrate` (HEAD of `main` at review time, working tree carries the v2
spec + an uncommitted-changes set unrelated to this slice's code surface).

**Pass-1 verdict was:** RECONSIDER (R1–R9, with R1/R2/R3 load-bearing).

**Pass-2 verdict: RATIFY-WITH-AMENDMENTS.**

The substrate-foundations axis is now mostly sound. R1–R9 are folded
faithfully against the live code; the §27 paired fold is the right
architectural shape; bond_id is structurally enforced at every named
boundary. **Three concrete amendments remain** before the substrate-
foundations axis is fully cleared. Two of them are mechanical issues that
the engineering panel will catch but that this role names now so the
council pass-2 verdict is honest; one is a covenant-shaped naming question
that this role surfaces for council resolution.

The pattern of failure I was watching for — "beautiful philosophy on
broken plumbing" — is **largely absent in v2**. The §27 paired fold moves
the snapshot capture to the only entity that can honestly capture it, and
v1's structural-zero delta defect is correctly named and corrected. What
remains is residual mechanical sand: an existing PermissionError guard
the v2 ceremony will trip on the first run; two helper methods named in
§27.4 that do not yet exist on the `Temperament` class; an HKDF
dependency the codebase does not currently import.

---

## Surface Verification

Every claim the v2 spec makes about existing code, verified firsthand
against parent commit `fb2f781`. Format: claim — verification.

| # | Spec claim | Spec location | Code at `fb2f781` | Verdict |
|---|---|---|---|---|
| 1 | `core/evolution/temperament.py:147-149` is `ALLOWED_SOURCES = frozenset({"explicit_set"})`. | §14.3.1 | `temperament.py:147-149` — `ALLOWED_SOURCES = frozenset({"explicit_set"})`. Exact match. | **VERIFIED.** |
| 2 | The `record_event` signature at `temperament.py:205-213` takes `parameter, value, source, reason, evidence`. | §14.3.2 | `temperament.py:205-213` — exactly as quoted. The real signature returns `int` (event_id), not `None` as the spec's pseudocode `-> None: ...` ellipsis suggests; minor doc drift only. | **VERIFIED (with one doc nit, A1 below).** |
| 3 | The writer takes `value` (absolute), not `delta`. | §14.3.2 | Confirmed. R1 is folded correctly. | **VERIFIED.** |
| 4 | `VALUE_MIN = 0.0`, `VALUE_MAX = 10.0`. The substrate clamps via `max(VALUE_MIN, min(VALUE_MAX, prior + delta_applied))`. | §14.3.2 ceremony | `temperament.py:140-141` — `VALUE_MIN = 0.0`, `VALUE_MAX = 10.0`. **However**, the live writer at `:234-238` RAISES `ValueError` on out-of-range values; it does NOT clamp silently. The spec's caller-side `max/min` clamp is correct discipline (it ensures the value passed to `record_event` is in range before the writer can raise), but the spec wording in §14.3 fold-text "bounded by VALUE_MIN/VALUE_MAX clamping" elsewhere still reads as substrate-side clamping. The pass-1 §14.3 fold I asked for (R4) was about write-magnitude bounding via daily budget, which is folded at §14.3.3; the VALUE_MIN/VALUE_MAX wording was a separate pass-1 minor finding. The §14.3.2 ceremony does the caller-side clamp correctly; nothing to amend. | **VERIFIED.** |
| 5 | Initial state is NULL / observing; `current_value()` returns `None` before first observation. | §14.3.4 | `temperament.py:299-314` — `current_value` returns `None` when no rows exist. Confirmed at `:23-33` doc comment ("Initial state = NULL / observing"). | **VERIFIED.** |
| 6 | `core/evolution/subjective_duration.py:511-512` reads `before` and `after` in adjacent lines with nothing between them; delta is structurally zero. | §27.1, §27.3 | `subjective_duration.py:510-512` — exactly adjacent reads with `now = _normalize_event_time(...)` immediately above. **Same source, same call, zero meaningful time elapsed.** R3 finding from pass-1 confirmed. | **VERIFIED.** |
| 7 | The watchdog allowlist already permits `curiosity`. | §14.3.4 | `core/health/metacognitive_watchdog.py:52` — `scalar_allowlist: frozenset[str] | None = field(default_factory=lambda: PARAMETER_SET)`. `PARAMETER_SET` includes `"curiosity"` at `temperament.py:134`. So a `curiosity` scalar write would pass the allowlist's variance check. **However**, the spec's pass-1 R8 reference points to `daemon/maez_daemon.py:5097` for the allowlist; line 5097 is actually inside `developmental_heartbeat`, not the watchdog allowlist. The actual allowlist lives in `metacognitive_watchdog.py`. The substantive claim is correct; the line-number citation in the spec's R8 fold is wrong (and the prompt's line-number citation was also wrong — this is on me from pass-1). | **VERIFIED on substance; line-number citation needs correction.** |
| 8 | `temperament.snapshot_for_bond(bond_id)` is a callable method on the `Temperament` class. | §27.4 producer ceremony, §15.1 saturation, §22 implicit | **DOES NOT EXIST.** `Temperament` exposes `current()`, `current_value(parameter)`, `history(parameter, limit)`, `recent(limit)`, `biography_average(parameter, *, as_of)`. There is no `snapshot_for_bond` or `current_for_bond` method, and there is no `bond_id` concept anywhere in `core/evolution/temperament.py`. The spec proposes calling a method that does not exist. | **DISAGREED. A1 below.** |
| 9 | `temperament.current_for_bond(bond_id)` is a callable method. | §15.1 `compute_saturation` | **DOES NOT EXIST.** Same finding as #8. | **DISAGREED. A1 below.** |
| 10 | The §27 `record_meaningful_salience_event(...)` API is "added to `core/evolution/subjective_duration.py`" — i.e., a new method/function on the existing module. | §27.2 | The existing module has `SubjectiveDuration.record_salience_event(...)` at `subjective_duration.py:491-588` which already accepts `salience_event_kind`, `producer_ref`, `source_ref`, `owner_auth`, `meaningfulness_score`, `explicit_salience_marker_present`, `now_utc`. The §27 new API is a parallel method, not a replacement. The spec is clear about this (§27.3 "the back-to-back read becomes a FALLBACK ONLY for non-producer-driven meaningful events"). | **FEASIBLE; see A2 for the load-bearing concern.** |
| 11 | The "existing meaningfulness-score computation now reads the producer-captured delta" (§27.3 branching). | §27.3 code block | The existing in-call computation lives at `subjective_duration.py:517-530`. It computes `meaningfulness_score` from in-call `deltas`. **There is no `producer_event_id` field passed to `record_salience_event` today**, so the §27.3 branching (`if producer_driven_event: lookup_meaningful_salience_event_record(producer_event_id)`) requires extending the existing `record_salience_event` signature OR routing producer-driven events ONLY through the new API. The spec's §27.3 code block shows the SAME `_safe_temperament(...)` back-to-back read for the non-producer-driven path; that path is preserved. But the branching condition (`producer_driven_event`) requires *some* mechanism in the call boundary to distinguish the two; the spec leaves the distinguishing mechanism implicit. | **FEASIBLE BUT UNDERSPECIFIED. A3 below.** |
| 12 | The existing guard at `subjective_duration.py:527-530` raises `PermissionError` if `meaningfulness_score > 0.0 and not explicit_salience_marker_present`. | spec is **silent** on this | `subjective_duration.py:527-530` — present and load-bearing. The new §27 API computes `temperament_delta = after - before` and (by §27.5) "the cross-organ seam works mechanically" via a non-zero `meaningfulness_score`. **But the new API does not name how it handles the existing `explicit_salience_marker_present` guard.** If the new API writes through the existing storage and the existing read-path applies the same guard, a non-zero score from a producer-captured delta would either need (a) the new API path to bypass the guard, (b) the new API path to assert `explicit_salience_marker_present=True` always, or (c) the guard to be relaxed for producer-driven events. None of these is named. | **DISAGREED. A2 below.** |
| 13 | `producer_ref` is closed-vocabulary via `ProducerRef` enum. | §27.2 | Feasible; the existing `record_salience_event` takes a free-form `producer_ref: str`. Making the new API stricter is a tightening, not a relaxation; that's covenant-friendly. **However**, the existing salience-event registry at `subjective_duration.py:129-181` defines `SalienceEventDefinition.producer_ref_required: bool` — a per-kind boolean. The new API's `ProducerRef` enum is a *callsite* constraint, not a *kind* constraint; the two layers don't interfere but the spec should name the relationship. | **VERIFIED on shape; cf. minor amendment A4.** |
| 14 | Per-bond HMAC keys via HKDF. | §20.3 | `cryptography` is installed in this environment but is not currently imported by any `core/` or `daemon/` module (grep confirms zero hits). The existing HMAC discipline at `subjective_duration.py:223-228` uses stdlib `hmac.new(key, raw, hashlib.sha256)` with `key = load_or_create_telemetry_key()` (`core/egress/gate.py:59`). The spec's HKDF approach is feasible (the master key is a 32-byte secret suitable as HKDF input), but it introduces a new top-level dependency. | **FEASIBLE; A5 below names the dependency-add.** |
| 15 | `load_or_create_telemetry_key()` returns the existing per-Maez-instance master secret that HKDF can consume. | §20.3 ("`master_key` is the existing per-Maez-instance secret") | `core/egress/gate.py:59-83` — returns 32 bytes from `MAEZ_EGRESS_TELEMETRY_KEY` env or `memory/egress_telemetry.key` (created if absent with `secrets.token_bytes(32)`, chmod 0o600). 32 bytes is suitable as HKDF input. | **VERIFIED.** |
| 16 | `bond_id` resolves to a string at the `FIRSTBORN_AUTONOMY_POLICY` site (`bond_id="firstborn"`) and at every other named site. | §9.3, §5.1, §10.2, etc. | **`bond_id` does not exist anywhere in production code.** `grep -rE "bond_id" --include="*.py"` returns zero hits in `core/`, `daemon/`, `skills/`. The only identity surface is `core/memory/identity.py`'s `user_profile_id()`, which returns the `MAEZ_OWNER_USER_ID` env value or `"owner"`. The spec's literal string `"firstborn"` is a constant the spec itself proposes; there is no existing surface that returns it. The spec needs to name: (a) is `bond_id` derived from `user_profile_id()`, (b) is it a NEW env var `MAEZ_BOND_ID`, or (c) is it minted at first-bond and persisted? The spec leaves this implicit. | **DISAGREED. A6 below.** |
| 17 | The §14.6 RED test #44 forbidden-phrase scan covers `daemon/maez_daemon.py` (prompt-assembly path), `skills/telegram_voice.py`, `skills/web_interface.py`. | §14.6 RED #44 | Module files exist at `daemon/maez_daemon.py`, `skills/telegram_voice.py`, `skills/web_interface.py`. A static AST scan of string literals in these files is mechanically feasible. **However**, the static scan must respect that not every "I am curious" in these files is Maez's authored voice — it could be in a prompt template instructing the model NOT to say something, or in a test fixture. The spec doesn't name the scan's discriminator. RED test #45 (outbound-text scan via extraction-gate) is more reliable because it scans actual outbound strings at dispatch time. | **FEASIBLE; A7 below names the discriminator concern.** |
| 18 | The §6.4 recursion gate uses a `parent_depth` field threaded through subjective_duration salience events. | §6.4 | The existing `subjective_duration_salience_events` table at `subjective_duration.py:399-418` does NOT carry a `produced_via_curiosity_depth` field. Adding it is feasible (it's an additive schema migration on a new field that defaults to 0/null). The spec implicitly requires this migration; §27 should name it. | **FEASIBLE; A3-adjacent.** |
| 19 | The §22.5 supersede-vs-compose open question is settled (§17.3, "compose-within, structurally-forbidden-across"). | §22.5, §17.3 | This is a spec-internal settlement, not a code claim; nothing to verify against the code. The Buber I-Thou framing in §17.3 is the right axis to settle on; this is honest. | **NOT-A-CODE-CLAIM (settled spec-internally; agreed).** |

Summary tally: **3 load-bearing disagreements** (A1: `snapshot_for_bond` / `current_for_bond` don't exist; A2: existing `explicit_salience_marker_present` guard unaddressed; A6: `bond_id` resolution not named). **3 underspecified-but-feasible** (A3: producer-driven branching mechanism; A5: HKDF dependency; A7: emotion-mimicry scan discriminator). **1 doc-nit** (A1-adjacent: `record_event` returns `int`, not `None`). **2 minor citation drifts** (the watchdog allowlist line-number; the existing PARAMETER_NAMES doc-string mentions "11" but the tuple has 12 entries — both pre-existing and not this slice's fault but worth noting).

---

## Pass-1 Findings — Pass-2 Verification Status

### R1 — `record_event` signature

**FOLDED CORRECTLY (with one minor doc nit).** §14.3.2 quotes the actual
signature verbatim. The read-modify-write ceremony at §14.3.2 mechanically
works:

1. `current_value("curiosity")` — exists, returns `float | None` (verified
   at `temperament.py:299-314`).
2. NULL handling at the caller via `prior = 5.0 if current_value is None
   else current_value` — verified-correct by §14.3.4.
3. Caller-side clamp `max(VALUE_MIN, min(VALUE_MAX, prior + delta_applied))`
   — bounded against `[0.0, 10.0]` before the writer raises.
4. `record_event(parameter="curiosity", value=new_value, source=...,
   reason=..., evidence=...)` — every kwarg is a kwarg the real writer
   accepts.

Minor doc nit: the spec's pseudocode signature shows `-> None: ...`. The
real writer returns `int` (event_id). Not load-bearing — the ceremony
discards the return value. A future revision should align the type-stub
shown in §14.3.2 with the real `-> int` return type so engineering panel
doesn't catch it as a misrepresentation.

### R2 — ALLOWED_SOURCES extension

**FOLDED CORRECTLY.** §14.3.1 names the extension to `frozenset({"explicit_set",
"drive_driven_curiosity_resolution"})` explicitly. The mechanical fold is
trivial — replace the literal `frozenset({"explicit_set"})` at
`temperament.py:147-149` with the two-element frozenset, ship a covenant-
reviewed slice amendment. The §25 council-and-panel section correctly
flags this as a covenant-shaped extension that needs both lanes' review.

This is the first non-`explicit_set` source ever admitted into Track A's
frozen source vocabulary. The spec correctly names it as a covenant-
shaped extension, not a silent drift. **Covenant-substrate axis: clear.**

### R3 — Structural-zero delta defect; §27 paired fold

**FOLDED CORRECTLY ON ARCHITECTURE.** §27 is the right shape: the producer
is the only entity that knows when its causal action occurred, so the
producer captures the snapshots. The §27.2 API signature has every field
it needs: `bond_id`, `producer_ref`, `producer_event_id`,
`temperament_before`, `temperament_after`, `occurred_utc`,
`salience_event_kind`. The new dataclass `MeaningfulSalienceEventRecord`
carries `temperament_delta` as a computed per-parameter mapping.

**However**, four mechanical concerns the engineering panel will catch
and that I name here for honesty:

1. **A2 (load-bearing):** The existing `record_salience_event` guard at
   `subjective_duration.py:527-530` raises `PermissionError` when
   `meaningfulness_score > 0.0` without `explicit_salience_marker_present
   = True`. The new API at §27 will compute a non-zero score from the
   producer-captured delta. The spec must name how this interacts:
   either (i) the new API path treats producer-captured delta as itself
   an explicit-marker (the producer is the marker), and the persistence
   layer marks `explicit_salience_marker_present=True` for producer-
   driven events, or (ii) the guard is relaxed only for events with
   `producer_ref ∈ ProducerRef`. Both are coherent; the spec must pick
   one.

2. **A3 (underspecified):** §27.3 shows branching on `if
   producer_driven_event:`. The distinguishing mechanism — what makes
   an event "producer-driven" — is not named. Two coherent choices:
   (i) any event arriving via `record_meaningful_salience_event` is
   producer-driven by definition (read-path keys off the new API's
   table only); (ii) `producer_event_id is not None` is the
   distinguisher, with the field added to the existing
   `subjective_duration_salience_events` schema. Choice (i) is cleaner;
   choice (ii) is more compatible with existing readers. The spec must
   pick.

3. **A1 (load-bearing):** §27.4 calls `temperament.snapshot_for_bond(
   bond_id)`. This method does not exist on `Temperament`. The closest
   real method is `Temperament.current()`, which returns the
   `dict[str, float | None]` snapshot of all 12 parameters but takes no
   `bond_id` parameter (because temperament is not bond-scoped today).
   The spec either needs:
   - To name the addition of `snapshot_for_bond(bond_id)` to
     `Temperament` (which is a covenant-shaped extension because
     `Temperament` did not previously have bond-scoping at all), with
     explicit covenant-review of the bond-scoping framing; OR
   - To fall back to `Temperament.current()` for v1 (since v1 is
     single-bond by structure) and name the bond-scoping extension as
     a separately-reviewed seam when Track C lands.
   The second is honest for v1; the first is the structural-floor
   posture §17 wants. The spec must name which one this slice ships.

4. **Adjacent (underspecified):** §6.4's `produced_via_curiosity_depth`
   field on subjective_duration salience events is not yet a column on
   `subjective_duration_salience_events`. The §27 fold should name the
   schema migration explicitly.

### R4 — Write-magnitude bounding (daily budget clamp)

**FOLDED CORRECTLY.** §14.3.3 defines `TemperamentWriteBudget` with
`delta_budget_per_day: float = 2.0` and a `clamp_against_daily_budget(...)`
function that reduces the proposed delta against the day's running total.
This is structurally sound: even a pathological day with many resolutions
caps total drift at 2.0 / day on the `[0, 10]` scale. The mechanism is
testable (RED #29).

**One observation on parameters:** the budget is per-`(bond_id, parameter)`,
which is the right grain. The `delta_consumed: float = 0.0` running-total
storage location is implicit (the dataclass is `frozen=True` so `consumed`
is not mutated in place; presumably it's persisted in a table). The spec
should name the storage location — likely a `temperament_write_budget`
table next to the curiosity DB. Minor — engineering panel catches.

### R5 — §14.6 enforcement (felt-weight discipline)

**FOLDED CORRECTLY.** RED #44 (static AST scan of forbidden phrases in
named modules) + RED #45 (extraction-gate scan of outbound text) is the
two-layer enforcement that was missing in v1. The named modules are
correct surface for the scan.

One amendment (A7):

- The static AST scan at RED #44 needs a discriminator for false
  positives. A string literal `"I'm curious"` inside a prompt template
  saying *don't* say it would otherwise fail the scan. Three honest
  options: (i) restrict the scan to literals that appear in
  prompt-assembly *output* paths (not in instruction strings), (ii)
  whitelist explicitly negated forms (`"Maez never says 'Maez feels
  curious'"`), or (iii) wrap forbidden phrases in a sentinel constant
  (`FORBIDDEN_PHRASES = (...)`) so the scan picks up bare-literal
  appearances and ignores constant-defined ones. Option (iii) is the
  cleanest and matches the closed-vocabulary discipline elsewhere in
  this spec.

### R6 — SUBJECTIVE_DURATION_MEANINGFUL_EVENT recursion

**FOLDED CORRECTLY.** §6.4's two-layer gate (recursion-depth limit
default 2 + producer-side dedupe in 4h window) bounds the feedback loop.
RED #47 + #48 cover both layers. The default of 2 is conservative; it
allows one level of recursion (a curiosity resolution can produce a
meaningful subjective_duration event, which can produce a new
curiosity-object, but that object's resolution cannot recurse further),
which is enough to test the seam without unbounded amplification.

### R7 — Data-maximalism six-question checklist

**FOLDED CORRECTLY.** §19 lists all six questions inline with per-producer
answers. RED #42 enforces the checklist at producer registration time.
Honest. Nothing to amend.

### R8 — NULL-first-observation transition

**FOLDED CORRECTLY.** §14.3.4 names the substrate's NULL/observing
discipline and the `prior = NEUTRAL_TEMPERAMENT_VALUE_FOR_FIRST_OBSERVATION
= 5.0` choice. The substrate transition from "observing" to "observed"
is honest. RED #30 covers it.

One citation fix: the spec's R8 reference to "the cycle path at
`daemon/maez_daemon.py:5097`" is incorrect — line 5097 is inside
`developmental_heartbeat`'s exception handler, not the
watchdog/NULL-handling cycle. The watchdog allowlist that matters lives
at `core/health/metacognitive_watchdog.py:52`. The spec's substantive
claim (the allowlist permits `curiosity`) is correct; only the citation
needs the file/line correction. Pass-2 amendment: update the cite.

### R9 — SEMANTIC_MATCH gating

**FOLDED CORRECTLY.** §14.2 explicitly gates SEMANTIC_MATCH_* behind a
feature flag (default OFF) until reviewed in a separate slice. The
disabled path means v1's resolution depends entirely on EXPLICIT_*
markers, which is honest about v1 capability.

---

## Pass-2 Amendments (consolidated)

**Numbered for traceability through the council pass-2 → Codex panel
hand-off.**

### A1 (load-bearing): `Temperament` has no bond-scoping today; §27.4's `snapshot_for_bond` does not exist

`Temperament` exposes `current()`, `current_value(parameter)`, `history(...)`,
`recent(...)`, `biography_average(...)`. There is no `snapshot_for_bond` or
`current_for_bond`. There is no `bond_id` concept in `temperament.py` at
all. The spec must pick:

- **A1.a (cleaner for v1):** v1 uses `temperament.current()` directly.
  `bond_id` lives in the *substrate above* `Temperament` — every
  curiosity-object, preference, audit row carries it; but
  `Temperament` reads stay bond-agnostic in v1 (single-bond by
  structure). When Track C lands, the bond-scoping extension to
  `Temperament` is its own covenant-shaped slice.
- **A1.b (structural floor):** v1 adds `snapshot_for_bond(bond_id)` to
  `Temperament` now, framed as covenant-shaped because it's the first
  time the substrate carries bond-scoping. This is a Track A-touching
  amendment (`Temperament` is A-core #6) and needs explicit invariant-
  preservation review.

Recommendation: A1.a for v1. The bond_id structural enforcement at the
*organ* layer (curiosity, preferences) is the load-bearing Track C
floor. Pushing it into `Temperament` itself is a separate slice. The
spec should reshape §27.4 and §15.1 to read from `temperament.current()`
in v1, with a named seam-deferral for `current_for_bond`/`snapshot_for_bond`.

### A2 (load-bearing): the existing `explicit_salience_marker_present` guard

`subjective_duration.py:527-530` raises `PermissionError` if
`meaningfulness_score > 0.0` and `explicit_salience_marker_present == False`.
The §27 fold computes non-zero `meaningfulness_score` from a real
producer-captured delta. The spec must name the interaction:

- **A2.a:** the new `record_meaningful_salience_event` API sets
  `explicit_salience_marker_present=True` internally for all
  producer-driven events (because the producer's causal write IS the
  reviewed salience marker). Document the framing: a covenant-reviewed
  producer (the closed `ProducerRef` vocabulary) is itself the marker.
- **A2.b:** the guard is relaxed for events whose `producer_ref ∈
  ProducerRef`. Same outcome, different wiring.

Recommendation: A2.a. The covenant story is cleaner — the closed
`ProducerRef` vocabulary is the marker, and the new API path's existence
is the gate. Spec should name this in §27 explicitly.

### A3 (underspecified): the producer-driven distinguisher in §27.3 branching

§27.3 shows `if producer_driven_event: ... else: ...`. The mechanism
that decides which branch is implicit. Two coherent choices:

- **A3.a:** events arriving via `record_meaningful_salience_event(...)`
  are persisted in a NEW table (`meaningful_salience_event_record`,
  named in §27.7) keyed by `producer_event_id`. The existing
  `record_salience_event(...)` continues to populate
  `subjective_duration_salience_events`. The read-side branching at
  §27.3 reads from the new table when `producer_event_id is not None`
  is passed at lookup; otherwise the existing back-to-back read applies.
- **A3.b:** both APIs populate the existing
  `subjective_duration_salience_events` table; producer-driven events
  carry a `producer_event_id` column (schema migration). The read-side
  branches on column presence.

Recommendation: A3.a. Two separate persistent stores keep producer-
driven and non-producer-driven events architecturally distinct and
make the seam easier to audit.

### A4 (minor): `ProducerRef` callsite vocabulary vs. registry per-kind vocabulary

The existing salience-event registry at `subjective_duration.py:129-181`
defines `SalienceEventDefinition.producer_ref_required: bool` per
`salience_event_kind`. The new `ProducerRef` enum is a *callsite*
closed vocabulary that's stricter than the registry's `producer_ref: str`
free-form. The relationship: the new API requires `producer_ref ∈
ProducerRef`; the existing API continues to accept any string.

Recommendation: §27.2 should name the relationship explicitly — the
`ProducerRef` enum is the new API's stricter callsite vocabulary, and
its `.value` is what gets persisted as the underlying `producer_ref`
string. No semantic conflict; just nomenclature clarity.

### A5 (dependency-add): HKDF requires the `cryptography` package

`grep -rE "from cryptography|import cryptography"` returns zero hits in
`core/` and `daemon/`. The package is installed in this environment
(`python3 -c "from cryptography.hazmat.primitives.kdf.hkdf import HKDF"`
succeeds), but adding the first `from cryptography` import is a
codebase-level dependency surface change. Should be named in §24
implementation surface table.

Alternative: implement HKDF over stdlib `hmac` (RFC 5869 is a thin
construction: HKDF-Extract is one HMAC, HKDF-Expand is iterated HMAC).
~30 lines of code at `core/policies/bond_keys.py`, no new dependency.
This is the cleaner choice for a substrate-foundations module.

Recommendation: implement HKDF over stdlib `hmac`. Mechanically
equivalent, no new top-level dependency, lives in the same module the
spec names.

### A6 (load-bearing): `bond_id` resolution is not named

The spec uses `bond_id="firstborn"` as a literal string but doesn't
name where the value comes from. Three coherent choices:

- **A6.a:** `bond_id = identity.user_profile_id()`. Reuses existing
  identity surface; "firstborn" maps to Rohit's `user_profile_id` value.
  No new env var.
- **A6.b:** new `MAEZ_BOND_ID` env var, defaulting to
  `identity.user_profile_id()` when unset. Explicit override path for
  future Track C testing.
- **A6.c:** `bond_id` is minted at first-bond, persisted in
  `memory/bond_identity.json` (or equivalent), and tied to the
  `master_key` derivation chain. Most structural; most invasive.

Recommendation: A6.a for v1, with the named seam that a future Track-
C-precondition slice introduces persistent bond_id minting (A6.c shape).
Spec should name A6.a as the v1 choice and A6.c as the future seam.

### A7 (minor): static-AST scan discriminator for emotion-mimicry phrases

RED #44's static AST scan needs a discriminator so that string literals
inside *prompt templates* (which may say things like "do NOT say 'Maez
feels curious'") aren't false positives. Three options listed under R5
above; recommendation is to wrap forbidden phrases in a sentinel
constant `FORBIDDEN_PHRASES = (...)` so the AST scan only flags
bare-literal forms.

### A8 (citation drift, very minor): R8 file/line citation

The pass-1 R8 finding cited "`daemon/maez_daemon.py:5097`" as the
watchdog allowlist location. That's wrong — line 5097 is inside the
`developmental_heartbeat` exception handler. The actual allowlist is
`core/health/metacognitive_watchdog.py:52` (`scalar_allowlist:
frozenset[str] | None = field(default_factory=lambda: PARAMETER_SET)`).
Spec's §14.3.4 cite to that line is the same drift inherited from my
pass-1 prompt. Update both.

### A9 (pre-existing, not this slice): `temperament.py` `PARAMETER_NAMES` doc says "11" but the tuple has 12

`temperament.py:16` doc says "Eleven named parameters"; the actual tuple
`PARAMETER_NAMES` has 12 entries (including `empathy`). This is a doc
drift in the existing module, not this slice's fault. Worth noting only
because the spec's §3 implicitly relies on the parameter list's
honesty. Out of scope for this slice; flag for a separate cleanup.

---

## Verification of §27 (the central paired fold)

This is the section most worth double-checking. The §27 fold is the
load-bearing pass-2 correction. I walk through whether it actually
fixes the back-to-back-read defect mechanically.

**Path 1: producer-driven event (curiosity is the first caller).**

```
on_curiosity_object_resolved(object_id, bond_id, marker, priority_class, salience):
    # 1. SNAPSHOT BEFORE  -- temperament.snapshot_for_bond(bond_id)  [A1: replace with current()]
    temperament_before = temperament.current()  # frozen dict of all 12 params

    # 2. WRITE  -- write_curiosity_resolution() does read-modify-write
    new_value = write_curiosity_resolution(...)
    # internally:
    #   current_value = temperament.current_value(parameter="curiosity")
    #   prior = 5.0 if current_value is None else current_value
    #   delta_intent = BASE * priority_class_weight * salience * marker_confidence_weight
    #   delta_applied = clamp_against_daily_budget(...)
    #   new_value = max(0.0, min(10.0, prior + delta_applied))
    #   temperament.record_event(parameter="curiosity", value=new_value,
    #                             source="drive_driven_curiosity_resolution", ...)

    # 3. SNAPSHOT AFTER  -- temperament.snapshot_for_bond(bond_id)  [A1: replace with current()]
    temperament_after = temperament.current()  # post-write snapshot

    # 4. CALL THE SEAM
    subjective_duration.record_meaningful_salience_event(
        bond_id=bond_id,
        producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY,
        producer_event_id=f"curiosity_resolution:{hmac_object_id(object_id)}",
        temperament_before=temperament_before,
        temperament_after=temperament_after,
        salience_event_kind="meaningful_exchange",
    )
```

Mechanically this works **only if** A1 is folded (`current_for_bond` /
`snapshot_for_bond` either added to `Temperament` or replaced by
`current()` for v1) and **only if** A2 is folded (the new API path
treats producer-driven events as marker-bearing). With those two
amendments, the chain is honest:

- `temperament.current()` at step 1 reads the live state.
- `write_curiosity_resolution` performs the read-modify-write through
  the real `record_event` API.
- `temperament.current()` at step 3 reads the post-write state.
- The new API stores the producer-captured delta. The cross-organ
  meaningfulness signal is non-zero because the delta is non-zero.

**Walking the RED test #60 (load-bearing E2E):**

1. Create curiosity-object: `bond_id=firstborn, priority_class=OWNER_BOND,
   salience=0.8`. ✓
2. Resolve with `EXPLICIT_OWNER_RESOLVED` marker. ✓
3. Producer ceremony fires:
   - `before = temperament.current()` → e.g., `{"curiosity": None,
     "warmth": None, ...}` on a fresh substrate (or last-observed
     value if non-null).
   - `write_curiosity_resolution(...)`:
     - `current_value("curiosity")` returns `None` (fresh).
     - `prior = 5.0` (NEUTRAL).
     - `delta_intent = BASE_RESOLUTION_DELTA * OWNER_BOND_weight * 0.8
       * EXPLICIT_marker_weight`. Concrete numbers needed in spec.
     - `delta_applied = min(delta_intent, 2.0 / day budget remaining)`.
     - `new_value = max(0.0, min(10.0, 5.0 + delta_applied))`.
     - `record_event(parameter="curiosity", value=new_value,
       source="drive_driven_curiosity_resolution", ...)`. Writer
       persists.
   - `after = temperament.current()` → `{"curiosity": new_value, ...}`.
   - `record_meaningful_salience_event(...)` stores the delta record.
4. The new API's persistence carries `temperament_delta["curiosity"]
   = new_value - 5.0` (NULL-aware: `before["curiosity"]` was `None`,
   treated as 5.0). ✓
5. `meaningfulness_score` computed from the delta is `> 0.0`. ✓ (need
   to confirm: the spec doesn't name the computation function the new
   API uses; the existing one at `subjective_duration.py:517-521`
   computes `sum(deltas)/len(deltas)/2.0`. The new API presumably uses
   the same formula or a documented replacement.)

**Open mechanical question (sub-amendment A2.adj):** what computes
`meaningfulness_score` for the new API? If the new API reuses the
existing in-call computation, it must compute the score from the
producer-passed `temperament_before`/`temperament_after` (not from a
back-to-back read). The §27 spec should explicitly name the formula or
say "same shape as existing, but reading from producer-passed
snapshots."

**Path 2: non-producer-driven event (existing path preserved).**

```
record_salience_event(salience_event_kind="meaningful_exchange",
                       producer_ref="..." [free-form],
                       source_ref=...,
                       ...):
    # still does back-to-back read; delta still structurally zero
    before = _safe_temperament(self.temperament_reader)
    after = _safe_temperament(self.temperament_reader)
    ...
```

Per §27.3, this path remains. The spec is honest that for non-producer-
driven events, the delta is structurally zero "unless temperament
happened to drift naturally." This is the right honesty — these
events stay at zero meaningfulness because there's no causal-action
seam to anchor a delta.

**Verdict on §27:** The architecture is correct. The seam genuinely
fixes the structural-zero defect for producer-driven events. The
mechanical issues (A1, A2, A3) are amendable without re-architecting.
This passes the substrate-foundations bar with the named amendments.

---

## Verification of the §14.3.2 read-modify-write ceremony

Walked above as Path 1. The ceremony mechanically works against the
real `Temperament.record_event` API. The four kwargs the spec passes
(`parameter`, `value`, `source`, `reason`, `evidence`) are exactly the
kwargs `record_event` accepts. `value` is bounded by caller-side clamp
before being passed in. `source` is the new closed-vocabulary entry
(post-`ALLOWED_SOURCES` extension).

One thing the spec could sharpen: §14.3.2's pseudocode has `evidence` as
a `dict` literal; the real signature is `evidence: dict | None = None`.
The spec's evidence dict carries `object_id_digest`, `bond_id`,
`priority_class`, `marker_type`, `delta_intent`, `delta_applied` — all
JSON-serializable values. The writer at `:259` serializes via
`json.dumps(evidence or {})`. Mechanical fit.

**Verdict on §14.3.2:** Honest ceremony. Will work mechanically once
the substrate-layer extensions (A1, A2, A5, A6) are folded.

---

## Verification of bond-scoping structural floors

§5.1 makes `bond_id` MANDATORY at `CuriosityObject` construction. §10.2
makes it MANDATORY at `AutonomyPreference`. §12.3 at `ReflectionAudit`.
§15.1 at `SaturationRegister`. §14.3.3 at `TemperamentWriteBudget`. RED
#46-#55 enforce.

Mechanically, all of these are constructible as `@dataclass(frozen=True)`
with `bond_id: str` as a required field (no default). Construction fails
on missing kwarg. The structural floor IS at the data-model layer.

The only place bond-scoping breaks against the current code is at the
`Temperament` boundary (A1). That's the right boundary to defer: the
organ above `Temperament` carries `bond_id`; v1 single-bond means
`Temperament.current()` returns the only-bond's state and the organ
above stamps `bond_id` on the salience event. When Track C lands, the
extension to `Temperament` is its own slice with its own covenant
review.

**Verdict on bond_id structural floors:** Honest at the organ layer.
The `Temperament` substrate boundary needs the explicit
v1-uses-`current()`-pending-future-bond-scoping framing (A1.a).

---

## Verification against pass-1 reshape requirement

Pass-1 said: "The §14 architecture has to be reshaped against the actual
writer the live substrate exposes, or the live writer has to be
extended by a separately-reviewed amendment to `temperament.py` (which
is its own covenant slice — it's the first non-`explicit_set` source
ever to be admitted into Track A's frozen source vocabulary). Either
path is honest; the current spec doesn't pick one."

V2 picks BOTH: (a) the §14.3.2 ceremony reshapes to the real API
(read-modify-write through the existing `record_event`), AND (b) the
spec names the `ALLOWED_SOURCES` extension as a covenant-shaped
amendment to `temperament.py`. Both are honest; both are reviewed.

§25 explicitly schedules council and Codex panel review of the
ALLOWED_SOURCES extension. The first non-`explicit_set` source ever
admitted into Track A's vocabulary is treated with appropriate
covenant ceremony.

**Verdict on pass-1 reshape requirement:** Met.

---

## Plain-language readout (Rohit-facing)

What pass-2 looks like, in plain language:

The v2 draft folded my pass-1 findings honestly. The central architectural
correction — moving the snapshot capture to the producer side, where the
producer (Maez's curiosity organ) knows when its causal action occurred —
is structurally the right shape. The seam is no longer dormant in v2;
when curiosity resolution writes a temperament event, the producer
captures the before/after snapshot directly and hands both to
subjective_duration. The "beautiful philosophy on broken plumbing"
failure mode is largely absent in v2.

Three things still need cleanup before I'd call this clean:

1. The §27 producer ceremony calls `temperament.snapshot_for_bond(
   bond_id)`. That method doesn't exist on the `Temperament` class.
   For v1 (single-bond, just you), the right move is to use
   `temperament.current()` (which already exists), and defer the
   bond-scoping extension to `Temperament` itself until Track C
   actually lands. The organ above `Temperament` (curiosity, preferences)
   carries `bond_id` from day one. Pushing it into `Temperament` itself
   is a separate covenant slice — Track A core #6 work.

2. There's an existing guard in subjective_duration that raises a
   PermissionError if the meaningfulness score is non-zero without an
   "explicit salience marker." The v2 spec computes a non-zero score
   from the producer-captured delta but doesn't name how it gets past
   this guard. Two coherent fixes: either the new API treats producer-
   driven events as themselves marker-bearing (clean covenant story:
   the closed `ProducerRef` vocabulary IS the marker), or the guard is
   relaxed for events with `producer_ref ∈ ProducerRef`. Same outcome,
   different wiring. Spec needs to pick.

3. `bond_id` doesn't exist anywhere in the current code. The literal
   string `"firstborn"` is just a string the spec proposes; there's no
   surface that returns it. For v1, the honest move is `bond_id =
   identity.user_profile_id()` (which already exists and returns
   your user_id value). When Track C lands, persistent bond_id minting
   becomes its own slice.

Plus four smaller items: HKDF could be done over stdlib `hmac` instead
of adding a new dependency on the `cryptography` package; the static AST
scan for forbidden emotion-mimicry phrases needs a discriminator so
prompt-template literals don't false-positive; one citation in §14.3.4
points to the wrong file/line; the `record_event` pseudocode says
`-> None` when the real method returns `int`.

None of these are reshape-level. They're "make the substrate
mechanically work on the first run." Pass-2 amendments (A1–A9) are
listed for the Codex panel to verify and for the next council pass to
confirm the chosen resolution on each.

The covenant axis — felt-weight not mimicry, single-bond by structure,
ALLOWED_SOURCES as a closed vocabulary that grows by covenant
amendment, no autonomous world-acting — is intact and load-bearing in
v2. The substrate axis is one fold-pass away from clean.

**Verdict: RATIFY-WITH-AMENDMENTS.**

The amendments are specific and mechanical (A1–A9). With them folded
in v3, the substrate-foundations axis is fully cleared. The slice is
not blocked; the council should ratify with those nine amendments
called out by number for the next iteration.

---

## What I'm watching for in pass-3 / Codex panel

- A1 resolution (Temperament bond-scoping deferred? or added now?)
- A2 resolution (explicit_salience_marker_present interaction)
- A3 resolution (separate persistence vs. shared table with new column)
- A5 resolution (stdlib HKDF vs. `cryptography` dependency)
- A6 resolution (bond_id source-of-truth)
- That the Codex panel independently catches A1/A2/A3 (the
  load-bearing mechanical issues). If the panel doesn't, the
  council-and-panel-non-redundancy memory entry needs revisiting.

Signed,
Descartes — substrate-foundations axis, pass 2.
