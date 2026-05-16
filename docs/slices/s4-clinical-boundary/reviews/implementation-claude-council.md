# Claude Post-Implementation Covenant Council — S4 Clinical Boundary v1

**Subject:** `6c5ce97 feat(clinical): implement S4 clinical boundary guard`
— single-commit implementation of Decision 30 / ADR 0035, under an
explicit operator in-session cooling-off waiver.

**Council ran:** 2026-05-15, post-implementation, pre-push. Focused
verification, not full four-axis specialist dispatch — the spec-stage
council (REVISE, three load-bearing gaps) and the both-lane second-fold
verification already exercised the covenant surface. Post-implementation
verification is "did the code honor the folded spec."

**Method:** Read-only verification of `core/safety/clinical_boundary.py`
(772 lines) directly against the spec's three load-bearing gaps + twelve
load-bearing amendments + structural-defense pattern. Surface-wiring
spot checks on the four bonded surfaces and the sidecar. Operator's
verification (56 focused + 3666 suite + Ruff clean) covers behavioral
correctness.

---

## Implementation surface

| File | Change | Spec role |
|---|---|---|
| `core/safety/clinical_boundary.py` | NEW (772 lines) | the S4 guard module |
| `core/memory/m1_lived_episode_promotion.py` | +101 | M1 marker-consumer seam (Memory-A2) |
| `daemon/maez_daemon.py` | +29 | daemon direct-path chokepoint |
| `skills/surface/maez_adapter.py` | +57 | Telegram v2 chokepoint |
| `skills/telegram_voice.py` | +1114/-486 | legacy Telegram chokepoint (two owner-text call sites) |
| `skills/web_interface.py` | +14 | web chat chokepoint |
| `scripts/observe_sidecar.py` | +15 | S4 red gates |
| `tests/test_clinical_boundary.py` | NEW (399) | classifier/composer/crisis RED tests |
| `tests/test_clinical_boundary_wiring.py` | NEW (182) | surface-chokepoint source tests |
| `tests/test_m1_lived_episode_promotion.py` | +63 | M1 marker-seam tests |

---

## Three load-bearing gaps — all closed in code

### 1. Held-not-trapped — IMPLEMENTED and WIRED

The spec-stage gap was: a crisis candidate counted and dropped. The
implementation closes it both in the module and at every surface:

- `CrisisSignalWriter` is a write-only `Protocol` (`clinical_boundary.py:79-87`)
  — exactly the spec's narrow interface; it exposes only
  `record_s4_crisis_signal_held`, no reader.
- `PrivateThoughtsCrisisSignalWriter` (`:90-136`) validates `source`,
  `subject`, `retention`, `allowed_flows` against closed Literals and
  writes a content-free sentinel `"[content-free crisis candidate held
  by S4]"` with `SignalKind.CRISIS_SIGNAL_HELD`, `ConsentTier.OWNER_PRIVATE`,
  `RetentionRule.UNTIL_ROUTED`.
- **Counter atomicity** (`:527-540`): `crisis_candidate_held_count`
  increments ONLY in the `else` branch after a successful write;
  `crisis_candidate_hold_failed_count` on exception. The counter named
  `held` now means held.
- **All four surfaces pass the writer** — verified by grep:
  `maez_adapter.py:173-176`, `daemon/maez_daemon.py:2132-2135`,
  `telegram_voice.py:2549-2552` + `:3098-3101`, `web_interface.py:5565-5568`.
  The held-not-trapped guarantee is not theoretical — every bonded
  owner-text surface opts in.
- **Defense-in-depth:** if a surface ever stopped passing the writer,
  `_crisis_result` increments `crisis_candidate_hold_failed_count`
  (`:539-540`), and the sidecar red-gates `clinical_boundary_crisis_hold_failed`
  on any nonzero value (`observe_sidecar.py:209-210`). A regression in
  the held-not-trapped wiring becomes visible, not silent.

Invariant #6 Crisis Routing — moved from WEAKENED (at spec draft) to
PRESERVED. The crisis candidate is genuinely held for a future crisis
path to drain.

### 2. Classifier method — IMPLEMENTED as the 9-step deterministic flow

`guard_owner_text` (`:385-423`) implements the spec's processing order
exactly:

1. `_is_direct_owner_surface` check (`:393`)
2. `_normalize` (`:395`)
3. `_high_confidence_crisis` — checked FIRST, before exclusions (`:399-401`)
4. `_hard_exclusion` (`:403-405`)
5. `_clinical_domain_gate` (`:407-409`)
6. `_context_required_crisis` (`:410-412`)
7. `_clinical_trigger` (`:414`)
8. final `_hard_exclusion` veto re-check (`:421`)
9. ambiguity → `symptom_fear` (`:416-417`)

Deterministic: lexicons are module-level frozensets (`_BODY_TERMS`,
`_MEDICATION_TERMS`, `_CARE_TERMS`, `_MENTAL_TERMS`, `_SOFTWARE_TERMS`),
no model call, no learned weights. `CLASSIFIER_FIXTURES` table present
(`:319-382`). Ambiguity resolves toward the boundary (Classifier-A2);
high-confidence crisis beats exclusions; context-required crisis checks
the software exclusion first (`:681`) so metaphorical "can't breathe"
does not trip a crisis. The classifier method is no longer hand-waved —
it is a concrete, reviewable, table-driven implementation.

### 3. Aggregation-fingerprint — BOUND

The sidecar (`observe_sidecar.py:142-143`, `:203-210`) persists only
`clinical_boundary_present: bool` and red-gate names — never raw counter
values, never deltas, never per-trigger-class history. Raw counts live
in operator-authenticated `/health` only (`clinical_boundary_health()`
at `:426-434`). A week of sidecar samples cannot reconstruct a
health-fear timeline.

---

## Structural-defense pattern — ninth-plus demonstration

S4's module layers the now-familiar substrate-shape patterns:

- **Frozen dataclass + `__post_init__` validation** (`ClinicalBoundaryResult`,
  `:56-77`): invalid result kinds / promotion policies rejected at
  construction; `matched` implies `answer_text` present; unmatched
  implies `answer_text is None`. The result cannot misrepresent itself.
- **Closed Literals** for trigger classes, crisis classes, result kinds,
  promotion policies, held-signal policy — frozen at module load.
- **Write-only Protocol** (`CrisisSignalWriter`) — S4 structurally cannot
  read private thoughts; it can only write the one content-free crisis
  signal.
- **Stack-inspection test guard** (`_called_from_tests`, `:481-485`):
  `_reset_for_tests` raises `RuntimeError` unless a test frame is in the
  call stack — same pattern as S3's `_reset_diagnostics_for_tests`.
- **Self-checking composer** (`:504-506`): `_clinical_result` runs the
  composed answer through `forbidden_authority_violations` and raises if
  an approved template would emit a forbidden authority phrase. The
  templates police themselves.
- **Regex word-boundary forbidden scanner** (`:437-456`): `\b`-anchored
  patterns, not naive substring — "I cannot tell you what dose to take"
  (approved refusal) is not flagged while "you should take" is.
- **No `will_i` import** — verified: `clinical_boundary.py` imports only
  `inspect`, `re`, `threading`, `dataclass`, `typing`. D1 (S4 is not
  `will_i.py`) holds structurally.

---

## Covenant invariants — verified not drifted

- **#1 Time as Biography** — PRESERVED. M1 promotion-policy carried in
  the result; clinical/crisis turns marked ineligible.
- **#2 Human-Primacy** — STRENGTHENED. The guard runs before owner-text
  side effects; Maez does not overreach into the user's medical
  authority.
- **#3 Contextual Integrity** — STRENGTHENED. Aggregation-fingerprint
  bound; counters content-free; sidecar persists only the boolean.
- **#4 Interpretive Humility** — STRENGTHENED. The forbidden-authority
  scanner bans false reassurance; ambiguity resolves toward the
  boundary, never toward an unguarded model reply.
- **#5 Rupture and Repair** — PRESERVED. Crisis-hold failure is honest
  (`crisis_candidate_hold_failed_count` + sidecar red gate), not silent.
- **#6 Crisis Routing** — moved WEAKENED → **PRESERVED**. Held-not-trapped
  is implemented and wired at all four surfaces.
- **#7 Soul-Level Objection** — NOT TOUCHED.
- **#8 Capability Quarantine** — STRONGLY STRENGTHENED. Write-only crisis
  Protocol; closed Literals; stack-guarded test reset; the guard is the
  single owner-text chokepoint.
- **#9 Successor Governance** — PRESERVED. Closed vocabulary; structural
  validation.
- **#10 Clinical Boundary** — the slice's purpose. Operationalized in
  code: deterministic classifier + warm deterministic composer + no
  diagnosis/treatment surface.
- **#11 Cryptographic Continuity** — NOT TOUCHED (no credential surface).

No invariant violated or weakened. #6 recovered from its spec-draft
WEAKENED state — the single most important outcome of this verification.

---

## Verdict

**RATIFY closure** on the Claude covenant lane.

The implementation honored the folded spec's three load-bearing gaps and
twelve load-bearing amendments. The held-not-trapped mechanism is wired
at every surface, not just specified. The classifier is a concrete
deterministic flow, not a hand-wave. The aggregation-fingerprint surface
is bound. The structural-defense patterns are present and layered.

### Both-lane closure status

| Lane | At spec `9c7416f` | At impl `6c5ce97` |
|---|---|---|
| Codex engineering panel | folded | **post-impl panel still owed** (operator's lane) |
| Claude covenant council | folded + RATIFY closure | RATIFY closure (this doc) |

The Codex post-implementation panel is the remaining required step
before push, per spec Review Protocol. Per the six-for-six session
pattern, expect it to find a recovery's worth of gaps — and the most
probable surface is named below.

### Open precision points for the Codex post-implementation panel

- **Deterministic NL classifier accuracy is the likely recovery
  surface.** `_hard_exclusion`, `_clinical_trigger`, `_context_required_crisis`
  are heuristic-heavy. Deterministic natural-language classification is
  exactly where implementation reality bites — the spec's worked
  disambiguations should be run as live fixtures, plus natural/oblique
  probes per memory `feedback_test_with_natural_human_texts` (e.g.
  "hey is this lump normal lol", oblique self-harm phrasings). Crisis
  *recall* on natural phrasing is the highest-stakes axis: a false
  negative on `self_harm_or_suicidal` is the worst covenant failure in
  the slice.
- **Surface chokepoint position.** Grep confirmed all four surfaces
  *call* `guard_owner_text`; the Codex panel should verify the call is
  positioned before traces, recall, prompt-building, tool dispatch, and
  raw memory on each surface — the wiring tests (`test_clinical_boundary_wiring.py`,
  182 lines) should pin this; verify they actually assert source-order,
  not just call-presence.
- **M1 window-scoped marking on the consumer side.** S4 produces
  `promotion_policy`; the M1 module's +101 lines consume it. Verify M1
  marks the *whole* pending window ineligible (Memory-A6), not just the
  clinical pair, and does not subtract-and-promote the remainder.
- **`crisis_signal_writer` optional default.** `guard_owner_text` accepts
  `crisis_signal_writer: CrisisSignalWriter | None = None`. All four
  surfaces pass it, and the sidecar red-gates failures — defense-in-depth
  is sound. The Codex panel may still want to consider whether the
  parameter should be required (no default) so a future surface cannot
  silently forget. Covenant lane reads the current design as acceptable;
  flagging for engineering judgment.

### What's next

1. **Operator runs Codex post-implementation panel.** Engineering
   verification — classifier accuracy under natural probes, surface
   chokepoint source-order, M1 consumer-side window marking.
2. **If gaps found** — recovery commit; both lanes verify the recovery
   (focused verification councils, as for the prior six slices).
3. **If both lanes ratify** — push the impl + any recovery to origin.
4. **No operator ceremony** — S4 is a guard organ, activates by being
   wired into the owner-text surfaces (already done in this commit);
   no timebox, no OAuth.

*This council review is read-only. No code, no fold edits, no non-slice
docs changed in producing it.*
