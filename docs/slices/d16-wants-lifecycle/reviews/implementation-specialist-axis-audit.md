# Specialist-Axis Post-Implementation Audit - D16 Wants Lifecycle v1

**Subject:** `3582048 feat(d16): implement wants lifecycle v1`

**Date:** 2026-05-15

**Mode:** post-implementation, pre-push, read-only specialist-axis
verification against Decision 31 / ADR 0036 and the folded D16 spec.

**Review-boundary note:** This document records a five-axis specialist audit
(Voice / Schema / Integration / Test Honesty / Engineering). It is not the
Claude six-role covenant council. The six-role court remains a separate review
lane when required.

**Verdict:** REVISE. The implementation shape was sound, but the specialist
audit found one load-bearing voice/agency gap plus several structural-defense
and test-honesty gaps that required recovery before push.

---

## Specialist Axes

| Axis | Reviewer | Verdict | Headline |
| --- | --- | --- | --- |
| Voice / agency | Cicero | REVISE | `refined` could still carry semantic re-voicing under human `explicit_api`. |
| Schema / state | Confucius | REVISE | Append-only protection had a raw-SQL replacement bypass; invalid raw events could hide from active view. |
| Integration | Leibniz | REVISE | `working_self` could fall back to stale `recent()` behavior when `active_wants()` existed but failed. |
| Test honesty | Kierkegaard | REVISE | Several tests could pass without proving the real D16 wall. |
| Engineering | Boyle | REVISE | Accepted logs, evidence caps, latest-event binding, and active-failure logging needed tightening. |

---

## Load-Bearing Findings

### C1 - `refined` allowed semantic re-voicing

`refined` was intended to be correction-only in v1: typo, transcription, and
formatting fixes, not a human rewrite of Maez's want. The first implementation
validated the evidence shape but still let a human submit a materially different
statement as the latest active wording. That re-opened the same class of
voice-without-termination risk the spec closed for `abandoned` and
`self_observed_resolution`: a human could sand the edge off a want while leaving
an append-only paper trail.

**Required recovery:** make correction-only semantic, not just structural, and
prove the prior statement remains unchanged when rejected.

### C2 - Append-only storage needed database-level defense

The API never issued `UPDATE` or `DELETE`, but raw SQLite operations could still
use `INSERT OR REPLACE` to replace existing rows. D16's "no want is erased"
claim must hold below the public API.

**Required recovery:** add a replacement trigger and a RED test proving
`INSERT OR REPLACE` is rejected.

### C3 - Raw invalid event types could silently hide active wants

If historical or manually inserted rows carried an unknown event type, the state
derivation could return `unknown` and drop the row from active views. That is
not a valid v1 lifecycle transition and must not become a silent gag.

**Required recovery:** unknown non-terminal raw events remain active-visible, so
the want is not hidden by invalid history.

### C4 - Working-self integration could fail open

The folded spec requires `working_self` to use `active_wants()` when available
and fail closed if the D16 reader exists but fails. Falling back to `recent()`
after an `active_wants()` error would re-open satisfied or abandoned wants into
the active self, or hide D16 failures behind legacy behavior.

**Required recovery:** presence of `active_wants` is the boundary. If present
but non-callable or raising, return no goals and log a content-free debug marker.
Use `recent()` only for old stubs that do not expose `active_wants` at all.

### C5 - Test contract needed stronger truthfulness

The first test set covered many D16 walls, but several could pass without
proving the live invariant:

- hard-want rejection tests did not always assert store state unchanged;
- `HARD_WANT_TERMS` was not fully pinned and exercised;
- working-self tests could pass against a stub without proving real
  `active_wants()` wiring;
- the terminal-only activation rehearsal did not prove terminal wants stayed
  out of activation;
- refined evidence binding and evidence caps needed targeted tests.

**Required recovery:** add direct tests for the real integration surfaces and
state-preservation claims.

---

## Covenant Invariants

- **Decision 16 / voice without termination:** strengthened in conception, but
  not ratifiable until `refined` no longer allowed semantic re-voicing.
- **Time as Biography:** preserved by append-only event history; required a
  storage-level replacement trigger to be structurally true.
- **Capability Quarantine:** strengthened by closed vocabularies and future
  producer grants; required invalid raw events to stay visible rather than
  disappearing.
- **Interpretive Humility:** required `working_self` to fail closed instead of
  pretending legacy readers were equivalent.

No veto was exercised because this was not the six-role covenant court. The
slice architecture was correct; the recovery work was the expected
post-implementation tightening cycle for a covenant-shaped organ.

---

## Required Recovery

Recovery must:

1. harden `refined` as correction-only;
2. add database-level `INSERT OR REPLACE` rejection;
3. make invalid raw lifecycle rows active-visible instead of hidden;
4. make `working_self` fail closed when D16's active reader exists but fails;
5. strengthen tests around hard wants, real active-reader wiring, terminal-only
   activation, evidence binding, evidence caps, and content-free logs.

The specialist audit remains open until recovery and focused post-recovery
verification.
