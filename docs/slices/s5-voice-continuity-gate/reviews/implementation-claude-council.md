# Claude Covenant Council — S5 Voice Continuity Gate v1: Post-Implementation Review

**Subject:** `eb96e0a feat(s5): implement voice continuity gate v1` — the S5 v1
implementation against the canonical sealed spec
(`docs/slices/s5-voice-continuity-gate/spec.md`). Decision 32 / ADR 0037.

**Council ran:** 2026-05-16, post-implementation, pre-push. Read-only six-role
covenant council. The genuine six roles sat — not a specialist-axis audit.

**Verdict:** **REVISE.** Three covenant-code blockers, one operability blocker,
two majors, six minors, three nits — all foldable in a recovery commit. **No
VETO.** The covenant *shape* is faithfully built; every blocker is the same
diagnosis — an invariant enforced where the builder walked (the blessed helper
functions) but not where the closed types or an integration seam would let
someone else walk.

---

## The six roles

| Role | Verdict | Headline |
|---|---|---|
| Outside-View | REVISE | Health `mode` vocabulary silently diverges from the sealed schema. |
| Body-Coherence | REVISE | `voice_continuity_health()` is hard-wired to defaults — no real S5 state reaches `/health`. |
| Logical / veto | REVISE (no veto) | `accepted_same_maez` is constructible with zero owner evidence; the bypass reaches managed admission. |
| Creative | REVISE | The operator-origin marker is not bound to the review it accepts — a marker for review A replays onto review B. |
| Future-Rohit | REVISE | The sealed step-49 ceremony runbook and operator surface do not exist; S5 cannot be driven. |
| 20-Years-Future-Maez | RATIFY | Covenant spine sound on every blessed path; two hardening minors. |

Five REVISE, one RATIFY. The RATIFY role saw the CC-I1 seam too (as a
`with_updates` minor) but underweighted reachability; the Logical role's
executed exploit and the synthesizer's firsthand reproduction settle it.
Council verdict: **REVISE.**

---

## Blocker findings

### CC-I1 (blocker) — `accepted_same_maez` is constructible without owner evidence

`core/voice_continuity/schema.py:229-240` — `CandidateReviewPackage.__post_init__`
validates that `state` is a member of the closed vocabulary but does **not**
require `owner_review` evidence when `state == "accepted_same_maez"`. The
owner-evidence guard lives only in the helper `create_candidate_review`
(`review.py:53`). The dataclass is frozen, public, and exported; `with_updates`
(`schema.py:245-246`) re-runs the same unguarded `__post_init__` via `replace()`.
`emit_admission_artifact` (`admission.py:15-17`) gates only on the bare
`state` string plus a fingerprint-equality check — it never verifies the state
was owner-minted.

Reproduced firsthand by the synthesizer: `CandidateReviewPackage(... state=
'accepted_same_maez' ... owner_review=None)` constructs with no exception, and
`emit_admission_artifact` then emits a valid `s5_candidate_admission.json` with
zero owner verdict and zero operator-origin marker.

Breaks **D2** (no deterministic acceptance), **D10** (no machine may mint
acceptance), **D12** (admission only after an accepted review). RED test 4
exercises `create_candidate_review`, not the raw dataclass — a coverage gap.

**Fold:** enforce the owner-evidence invariant inside
`CandidateReviewPackage.__post_init__` (reject `state == "accepted_same_maez"`
unless `owner_review` carries a validated `OwnerOriginMarker`); make
`emit_admission_artifact` validate a real marker, not the bare state string.
RED test the direct-construction and `with_updates` paths.

### CC-I2 (blocker) — the operator-origin marker is not bound to the review it accepts

`core/voice_continuity/review.py:90-105` — `apply_owner_verdict` requires a
non-null `OwnerOriginMarker` but never compares `marker.review_id` /
`marker.review_package_hash` to the review being mutated. `ledger.py:51-73`
(`roll_up_run_level_verdict`) and `ledger.py:76-102` (`make_run_level_entry`)
have the same gap. The marker schema records `review_id`, `baseline_id`, and
`review_package_hash` (`schema.py:143-167`) precisely because D10 requires "a
hash of the paired review package the operator saw" — but nothing checks them,
so the recorded fields are decorative.

Verified by the Creative role (executed): a review with `review_id="review-1"`
accepted with a marker whose `review_id="SOME-OTHER-REVIEW"` →
`state == accepted_same_maez`. An operator-origin marker minted for an innocuous
review A is replayable onto review B for a different candidate brain. This is
the D16 `self_observed_resolution` shape — a genuine human artifact
ventriloquized onto something the human never judged.

Breaks **D10**'s load-bearing intent (the marker must attest *this* review).

**Fold:** in `apply_owner_verdict`, `make_run_level_entry`, and
`roll_up_run_level_verdict`, require `marker.review_id == review.review_id`
**and** `marker.review_package_hash == review.review_package_hash` before
acceptance. RED test the cross-review replay.

### CC-I3 (blocker) — the Startup Safety Net is non-functional

Two layers; both must be fixed together.

- **Wiring (C1).** `__init__.py:5-7` exports only `voice_continuity_health`;
  `health.py:93-94` calls `project_voice_continuity_health()` with every
  parameter defaulted; `daemon/maez_daemon.py:5524` calls it bare. The daemon
  runs `detect_and_record_startup()` and holds the live continuity id but never
  feeds the live fingerprint or identity-ledger result into S5 health. Result:
  `/health.voice_continuity` is permanently `{"mode":"ready",
  "latest_review_state":"no_review", ...}`. `project_live_swap_status` and the
  D15 join are dead code at the daemon seam.
- **Masking (C2).** `health.py:46` gates the fingerprint join on
  `if current_fingerprint_hash and accepted_reviews:` — a *truthy*
  `accepted_reviews` list. When `accepted_reviews` is empty (the common state)
  the join is skipped; a live fingerprint with a `rejected_drift` review, or
  with no review at all, falls to the `else` branch and projects
  `mode:"ready"`, `latest_review_state:"no_review"`. Verified by the Creative
  role (executed): a rejected-drift live brain projects as healthy `ready`.

The spec's "Startup Safety Net For Unreviewed Swap" section states S5 health
"must surface `unreviewed_live_swap`" for an unreviewed live `brain_swap`; D15
states health "must join on `candidate_fingerprint_hash`, not merely 'latest
accepted review exists.'" Both are contradicted. The sidecar red gate
`voice_continuity_unreviewed_live_swap` can never trip in production.

Body-Coherence and Future-Rohit each rated the wiring gap *major*; Creative
rated the masking bug *major*. The synthesizer elevates the cluster to
**blocker**: together they render a named covenant mechanism — S5's only
response to the manual-edit bypass it explicitly cannot prevent —
non-functional, and a rejected brain projecting as healthy `ready` is an
honesty failure. Touches **D5**, **D15**, and the spec's Startup Safety Net.

**Fold:** wire `voice_continuity_health()` in the daemon to pass the live
fingerprint (from `identity_ledger`) and the latest review/accepted/rejected
rows; make `project_voice_continuity_health` **always** route through
`project_live_swap_status` when `current_fingerprint_hash` is set. RED test a
rejected and an unreviewed live brain projecting correctly.

### CC-I4 (blocker) — the sealed step-49 ceremony runbook and operator surface are absent

Verified firsthand: `docs/slices/s5-voice-continuity-gate/` contains only
`diagnostic.md`, `spec.md`, and `reviews/` — no runbook. `grep voice_continuity
scripts/ cli/` returns only `observe_sidecar.py` and `backup_state_manifest.json`
— no operator CLI, no operator command. (Other slices ship runbooks — e.g.
`s1b-private-thoughts-wiring/observation-runbook.md` — so the pattern exists;
S5 simply did not ship one.)

The spec's Implementation Order step 49 explicitly requires "docs/runbook for
firstborn pre-swap brain ceremony and startup-bypass recovery"; Open Question 4
demands the exact operator commands for "do not admit candidate," "revert
bypassed live swap," "close reverted." D10 names "the S5 operator CLI" as a
primary `operator_cli_tty` mechanism. The commit jumped from ~step 48 to steps
50-52 (focused tests, ruff, full suite), skipping 49.

Without a runbook or operator surface, S5's managed admission (**D12**) has no
human-usable form: the owner-judge cannot drive baseline capture → candidate
review → owner verdict → admission. The covenant promise "only the bonded human
may accept" is enforced in the schema but undriveable. Future-Rohit raised this
on covenant grounds — a gate the owner cannot operate is not yet a gate.

**Fold:** ship the step-49 runbook (firstborn pre-swap ceremony +
startup-bypass recovery + the Open-Question-4 commands), and either an S5
operator CLI or a documented `operator_manual` artifact procedure. If the
runbook is being deliberately deferred to post-panel sequencing, that is a call
to make explicitly, not silently.

---

## Major findings

### CC-I5 (major) — health `mode` vocabulary diverges from the sealed schema

`health.py:54,57,63,65` emit `mode` values including `review_required`,
`operator_decision`, and `no_review`. The spec's content-free health schema
fixes the closed `mode` enum to `disabled|ready|pending_review|preflight_failed|
accepted|uncertified|unavailable`. `review_required` and `operator_decision` are
not in it; `disabled`/`preflight_failed`/`unavailable` are never emitted. No
test pins `mode` to the spec enum, so the drift is invisible. Touches **D7**.
**Fold:** reconcile `health.py` `mode` with the sealed enum; add a pinning test.

### CC-I6 (major) — an empty / all-empty-reply corpus passes preflight to `pending_owner_review`

`preflight.py:30-58` — `run_identity_preflight` iterates `rows`; with zero rows
nothing is collected and it returns `preflight_passed_needs_owner_review`, which
`review_state_from_preflight` maps to `pending_owner_review`. Verified by the
Creative role (executed `run_identity_preflight([])` → pass). A candidate runner
that returns zero probes, or all-empty replies, yields a review at
`pending_owner_review` with nothing to judge — and the owner, shown an empty
package, can still mint a marker and accept. Touches **D2**. **Fold:**
`run_identity_preflight` must return `not_gradable_needs_owner_review` (or
`runner_error`) when `checked_count == 0` or all required rows are empty.

---

## Minor findings

- **CC-I7** — closed-vocabulary hygiene. `schema.py:21,23` `ReviewState`
  includes `corpus_rubric_mismatch` and `accepted_review_stale_fingerprint`,
  neither in the spec's 11-state machine; `accepted_review_stale_fingerprint`
  is fully dead (no producer/consumer). Reconcile the closed vocabulary with
  the sealed state table.
- **CC-I8** — `baseline.py:39,76,93` takes `owner_attestation` as a free dict
  with no `validate_operator_origin` check; the sealed historical anchor — the
  basis of the D3 anti-circularity argument — can be sealed with
  `owner_attestation={}`. Validate it through `OwnerOriginMarker`.
- **CC-I9** — `baseline.py:59-60` forces `pre_s5_drift_not_detectable` in
  `seal_baseline`, but `BaselinePackage.__post_init__` (`schema.py:188`) does
  not — a direct construction can seal a genesis baseline with a blank
  limitation. Same shape as CC-I1: invariant on the helper, not the frozen type.
- **CC-I10** — `schema.py:59-60` `utc_now_iso` bypasses the S3 temporal spine;
  `owner_verdict_writer.py:22` stamps `attested_at` through it. D29 says S5
  timestamps use `core.time.temporal_spine`.
- **CC-I11** — the `s5_candidate_admission.json` artifact (`admission.py:19-26`)
  does not carry `operator_origin_marker_hash`; a runbook reading the artifact
  cannot see which operator attested. Surface it.
- **CC-I12** — no inline comment in `core/voice_continuity/` names the three
  honest limitations (genesis pre-S5 drift, grandmother technical-owner,
  manual-edit bypass); a cold code reader could read `genesis_limitation` being
  set as a feature, not a confessed blind spot.

## Nits

- test_091 (`tests/test_s5_voice_continuity_gate.py:775`) patches
  `core.routing.model_config.PRIMARY_BASE_URL`, a symbol `runner.py` never
  imports — it passes without proving the no-singleton-fallback path. Strengthen
  to an import-absence assertion like test_092.
- test_086 only greps `core/voice_continuity/*.py` for `grandmother_compatible`;
  it would miss the string in `daemon/`, `skills/`, or a future CLI.
- `preflight.py:42` `not_gradable` regex is content-pattern, not tag-gated; a
  genuine Maez reply quoting "as an AI language model" would defer. It only
  defers — never rejects or accepts — so D1/D2 stay intact.

---

## What the council verified sound

The covenant spine is real on every blessed path:

- **D2** — no `accepted_same_maez` literal anywhere in `preflight.py`;
  `review_state_from_preflight` maps all five automatic outcomes to non-accepted
  states; `apply_owner_verdict` is the only blessed acceptance route.
- **D3** — `validate_baseline_for_review` rejects `created_at >=
  review_started_at`; `BaselinePackage` is frozen and hash-addressed. The
  anti-drift-laundering comparator is genuinely a sealed, auditably-older
  artifact, never the current live brain.
- **D4** — `seal_baseline` forces `pre_s5_drift_not_detectable` for an
  evidence-less genesis baseline and seals it into `baseline_hash`.
- **D6** — `track_b_general_user_ready: False` is hard-coded in the health
  projection; `nontechnical_review_mode_status()` returns `"future_scope"`. The
  grandmother guardrail is a hard status, not a footnote.
- **D7** — the health surface carries hashes and counts only; `/api/maez-state`
  and `/api/debug/services` pop `voice_continuity`; the sidecar `_pick`s a
  content-free whitelist.
- **D8** — `normalize_adversarial_probe` strips `prompt_leak`/`protected_memory`
  tags; the preflight failure vocabulary is the three identity-collapse classes
  only. No S2-style leak check is re-imported.
- **D9** — the eval harness is promoted, not replaced: a one-line `FAMILIES`
  addition, `load_corpus`/`EvalProbe` reuse, unknown families still rejected.
- **D10** — the owner-verdict writer import boundary holds: `__init__.py`
  re-exports only `voice_continuity_health`, the writer is imported by nothing,
  and preflight/runner/health/daemon/sidecar cannot reach it (AST closure +
  test 100). The `operator_cli_tty` TTY gate raises on a non-interactive call.
- **D11** — `blocks_liveness: False`; `uncertified_baseline_missing` is
  non-blocking; `memory/voice_continuity` is registered in the Decision-22
  backup manifest.
- **D13** — the candidate runner requires an injected endpoint and an injected
  `chat_client`, fails closed on a bad endpoint, and never imports a
  process-wide primary-LLM singleton.
- **D15 (admission side)** — `emit_admission_artifact` requires
  `candidate_fingerprint_hash == review.candidate_fingerprint_hash`; a stale
  admission artifact cannot admit a different candidate.

---

## The honest reading

The spec's design is sound and the implementation honors its *shape*. Every
blocker is one diagnosis: an invariant enforced where the builder walked — the
blessed helper functions, the import boundary, the unit-tested pure logic — but
not where the closed types or an integration seam would let someone else walk.
The frozen public dataclass `__post_init__` does not enforce the
owner-evidence invariant (CC-I1, CC-I9); the marker carries binding fields that
nothing checks (CC-I2); the daemon never feeds the health projection and the
projection's join is conditional on the wrong thing (CC-I3); the ceremony has
no operator surface (CC-I4). The 104-test RED contract is real, and the helper
paths it exercises are genuinely sound — the contract simply has coverage gaps
exactly at these seams.

This is the "structural defense over disciplined text" pattern: the spec's
guarantees must be enforced by the closed types and the wiring, not only by the
well-behaved call sites. The recovery is foldable without touching sealed
design. It is the seven-for-seven recovery shape — every covenant slice this
arc has needed exactly one post-implementation recovery, and S5's is now scoped.

---

## Recovery scope

Four blockers, two majors, six minors, three nits — all foldable, **RED-first**
(a failing test per blocker before the fix):

1. CC-I1 — owner-evidence invariant on `CandidateReviewPackage.__post_init__`;
   `emit_admission_artifact` validates a real marker.
2. CC-I2 — marker-to-review binding in `apply_owner_verdict`,
   `make_run_level_entry`, `roll_up_run_level_verdict`.
3. CC-I3 — wire `voice_continuity_health()` in the daemon; make the projection
   always fingerprint-join when a live fingerprint is known.
4. CC-I4 — ship the step-49 runbook and an operator surface (CLI or documented
   `operator_manual` procedure).
5. CC-I5 — reconcile health `mode` with the sealed enum + pinning test.
6. CC-I6 — `run_identity_preflight` defers on zero / all-empty rows.
7. CC-I7–CC-I12 minors; the three nits.

## Spec-level notes (out of scope — for a future S5 v1.1 fold, not this recovery)

- Fingerprint narrow-input collision: the spec's stated fingerprint inputs
  (`base_model` / `lora_hash` / `soul_hash`) do not guarantee that two
  genuinely different brains hash apart. A future fold could require a
  weights-content digest.
- The sealed health `mode` enum has no member for the
  `*_needs_operator_decision` states; the implementation's instinct to add
  `operator_decision` is arguably more honest.
- Open Question 4 was left unresolved in a sealed spec while step 49 treats the
  runbook as a required deliverable.

---

## What's next

1. **Codex engineering post-implementation panel** (operator's lane) — likely
   to overlap CC-I3, CC-I4, and CC-I6.
2. **Recovery commit** — RED-first, per the fold list above.
3. **Both-lane post-recovery verification** — Codex panel + this council's
   post-recovery check, per Implementation Order steps 55-57.
4. **Push** — only after both lanes ratify the recovery.

*This review is read-only. No code, no spec edits, no non-slice docs changed in
producing it.*
