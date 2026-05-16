# S5 Voice Continuity Gate v1 - Codex Post-Implementation Engineering Panel

**Date:** 2026-05-16
**Implementation under review:** `eb96e0a` plus recovery commits through `310663d`
**Mode:** post-implementation engineering review after covenant recovery-2
**Verdict:** RATIFY-WITH-RECOVERY, pending final verification and covenant
check on the engineering recovery delta

S5's implementation now has the covenant shape the spec requires: accepted
brain swaps require the owner-verdict path, operator-origin markers are bound to
one review package, the startup safety net is wired into daemon health, non
`brain_swap` identity events are out of v1 scope, and the runbook exists.

The engineering lane found one remaining runtime integration gap: the pure
health projection could reason over accepted/rejected reviews, but the live
`voice_continuity_health()` wrapper did not load the runtime S5 artifacts that
prove those reviews. That meant an accepted planned brain swap could still
project as `unreviewed_live_swap` after startup.

---

## Panel Summary

| Axis | Verdict | Finding |
| --- | --- | --- |
| Acceptance construction | RATIFY | `accepted_same_maez` now requires the `apply_owner_verdict` door; forged direct construction and `with_updates` are blocked. |
| Owner marker binding | RATIFY | Review id, baseline id, and review package hash are bound unconditionally before accepted roll-up. |
| Startup safety net | REVISE | The wrapper detected live brain swaps but did not load accepted/rejected runtime artifacts before projection. |
| Identity-event scope | RATIFY | Health ignores non-`brain_swap` latest identity events, preserving S5 v1 scope. |
| Runbook / operator surface | RATIFY-WITH-AMENDMENT | The runbook is usable; it needed one honest limitation sentence for raw in-process mutation. |
| Health privacy | RATIFY | Projection remains content-free: hashes, ids, enum states, and counters only. |

---

## Findings And Recovery

### C1 - Live Health Did Not Load Runtime Admission / Review Artifacts

**Severity:** HIGH
**Owner:** health / storage integration

The spec's D15 requires accepted health projection to join on the current live
`candidate_fingerprint_hash`, not merely on "latest accepted review exists."
The implementation had the correct pure function:
`project_voice_continuity_health(..., accepted_reviews=..., rejected_reviews=...)`.

But the live daemon wrapper, `voice_continuity_health()`, read only the latest
identity-ledger fingerprint and passed no accepted or rejected rows. A planned
brain swap with a valid `s5_candidate_admission.json` would therefore still
surface as `unreviewed_live_swap` after startup. The tests exercised the pure
projection, not the live artifact-loading path.

**Recovery:** add content-free storage readers for:

- `memory/voice_continuity/admissions/*.json` admission artifacts, projected as
  `{review_id, candidate_fingerprint_hash}` rows using
  `admitted_fingerprint_hash`;
- `memory/voice_continuity/reviews/*.json` rejected review artifacts, projected
  as `{review_id, candidate_fingerprint_hash}` rows when `state` is
  `rejected_drift`.

`voice_continuity_health()` now loads those rows before projecting the current
live `brain_swap` fingerprint.

RED coverage:

- `test_098h_startup_safety_net_loads_matching_admission_artifact`
- `test_098i_startup_safety_net_does_not_accept_stale_admission_artifact`
- `test_098j_startup_safety_net_loads_rejected_review_artifact`

### C2 - Runbook Did Not Name Raw In-Process Mutation Limitation

**Severity:** LOW
**Owner:** operator honesty

The covenant round-2 verification correctly conceded that raw in-process
mutation of frozen instances, such as `object.__setattr__`, is the same
privileged bypass class as manual root edits to `/etc/maez/model.env`: S5 v1
cannot prevent it, only gate the normal managed API path and detect live startup
drift where it reaches health.

**Recovery:** add the limitation to the runbook's Scope and Limitations section.

RED coverage:

- `test_105d_operator_runbook_names_raw_in_process_mutation_limitation`

---

## Ratified Surfaces

- The accepted-state token and module-qualified `apply_owner_verdict` stack
  check block direct accepted construction.
- `roll_up_run_level_verdict` binds owner-origin markers unconditionally.
- Non-`brain_swap` identity events do not trigger S5 v1 health alarms.
- Admission artifacts remain content-free and fingerprint-bound.
- Rejected live fingerprints project `preflight_failed`, not accepted.
- Baseline-missing / Decision-22 posture remains non-blocking.

---

## Panel Outcome After Recovery

**RATIFY-WITH-RECOVERY.** The engineering recovery keeps the S5 covenant shape
intact and makes the startup safety net operational in both directions: an
unreviewed live brain is flagged, and a legitimately accepted live brain is
recognized only when the current fingerprint matches a runtime admission
artifact.

Because this review produced an additional recovery delta after the covenant
round-2 ratification on `310663d`, the remaining close step is fresh verification
on the final tree and covenant confirmation that the storage-reader recovery
introduces no framing drift.

Plain English: the gate could already shout when a new brain appeared without
papers. The engineering gap was that it could not read the papers when they did
exist, so even an approved swap could look unapproved after restart. The fix
teaches the health check to read only the safe parts of the papers: which review
id approved which fingerprint. No transcripts, no owner notes, no voice content.
