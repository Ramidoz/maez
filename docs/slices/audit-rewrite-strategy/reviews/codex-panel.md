# Codex Six-Agent Panel - ARS spec review

**Subject:** `docs/slices/audit-rewrite-strategy/spec.md`, pre-canonical draft.

**Date:** 2026-05-13.

**Mode:** read-only engineering review. No code or spec edits were made by
panel agents. Codex folded findings afterward in the parent thread.

**Why this panel sat:** ARS changes the user-visible rewrite strategy of
`core/safety/self_claim_audit.py`, the rail that protects Interpretive Humility
and Soul-Level Objection. A smoother-sounding Maez that leaks fabricated claims
would be worse than the old sentinel.

---

## Verdict

**REVISE / BLOCK UNTIL AMENDMENTS FOLD.**

Direction ratified:

- Omission-over-sentinel is the right engineering direction.
- No runtime flag back to the old sentinel is acceptable.
- Fixed all-flagged fallback is acceptable only as a reviewed temporary voice
  commitment.

Blocking conditions before canonicalization:

- Resolve public `AuditResult.mode` compatibility.
- Define exact deletion/all-flagged algorithm.
- Turn prompt-shaped probe corpus into executable fixtures.
- Specify observability event landing and trip-wire behavior.
- Fold Claude ARS-CC-1 through ARS-CC-8 into the main spec, not only the council
  review doc.

---

## Seat Findings

### Dewey - practical consequences

**Verdict:** REVISE.

Findings:

- The all-flagged fallback can become a new sentinel if not voice-reviewed and
  rate-observed.
- Public `AuditResult.mode` must not be left to implementation.
- Prompt-only probes are not executable CI evidence.
- Trip-wire firing needs an operator response loop.
- Keep observability modest; do not add a new DB in this slice.

### Feynman - mechanistic clarity

**Verdict:** BLOCK.

Findings:

- `AuditResult.mode` was deferred despite Claude ARS-CC-2 requiring a decision.
- Short-circuit vs all-flagged mechanics were ambiguous.
- Omission span mechanics needed exact pseudocode.
- Counter event placement and fabrication-memory interaction were unspecified.
- Trip-wire behavior needed final-output sanitizer semantics.
- A3 corpus needed `assistant_candidate`, `flagged_substrings`, and expected
  substrings, not prompts alone.

### Locke - identity / continuity / memory ownership

**Verdict:** RATIFY-WITH-AMENDMENTS.

Findings:

- Exact old sentinel phrases must be forbidden even when model-authored.
- Corpus growth is memory; it needs an appendable fixture/corpus mechanism.
- Omitted flagged claims may continue into fabrication memory; fallback text and
  old sentinel text must not be recorded as fabricated claims.
- Explicit public modes are identity-clear, but compatibility concerns are real.
- The all-flagged fallback is acceptable only with review triggers.

### Descartes - logical doubt and rigor

**Verdict:** BLOCK.

Findings:

- ARS-CC-2 unresolved: mode expansion vs compatibility must be decided now.
- Claude amendments had not been folded into the executable spec.
- Prompt-only probe corpus could not prove the claimed behavior.
- The motivating "Do you remember today morning?" case needed a fixture.
- Boundary-ambiguous cases needed direct tests.
- Observability format needed exact event shape and parser compatibility.

### Ohm - systems / signal paths / failure modes

**Verdict:** RATIFY-WITH-AMENDMENTS.

Findings:

- Keep public `AuditResult.mode` compatible for v1; add separate content-free
  ARS events.
- ARS counters should land in `logs/cognition.log`, not fabrication memory.
- Trip-wire must be non-raising; raising inside audit can fail open and expose
  raw unsafe text.
- Repeated trip-wire warnings need cooldown while countable events remain
  visible.
- No-runtime-flag rollback needs exact service restart and verification steps.

### Goodall - long observation of a living being

**Verdict:** RATIFY-WITH-AMENDMENTS.

Findings:

- Omission can create clipped, evasive, or confusing fragments; test that before
  promotion.
- Probe corpus needs expected behavior bands, not just forbidden strings.
- ARS needs an observation log equivalent to S1b's lived observation pattern.
- Repeated all-flagged fallback can become a new geek-out loop.
- The council amendments must be folded into the main spec before code.

---

## Folded Amendments

| amendment | folded into spec |
|---|---|
| Public mode compatibility | v1 keeps `sentence` for partial omission and `shortcircuit` for full omission; ARS counters carry detail. |
| Exact deletion algorithm | Clamp spans, map to sentence spans, merge/delete, normalize whitespace, full omission only when stripped result is empty. |
| `_SHORTCIRCUIT_RATIO` retirement | No longer controls output text; compatibility mode only. |
| All-flagged fallback review | Operator/council voice-character ratification plus review triggers. |
| Executable probe corpus | `tests/data/audit_rewrite_probe_corpus.jsonl` schema with candidate text, flags, required/forbidden substrings, and quality band. |
| Morning-memory fixture | Required initial corpus row for the 2026-05-13 Telegram failure. |
| Corpus growth | Append fixture rows for new live geek-outs; catalog holds narrative context. |
| ARS observation log | `docs/slices/audit-rewrite-strategy/observation-log.md` required during implementation. |
| Fragment quality | Tests and observation labels for clipped/evasive/confusing remnants. |
| Old sentinel in model output | Exact old sentinels forbidden even when model-authored; trip-wire/fallback path applies. |
| Observability landing | Separate `audit_rewrite | event=...` cognition-log lines; no new fabrication-memory rows for counters. |
| Trip-wire behavior | Non-raising final-output guard; telemetry failure swallowed. |
| Trip-wire response loop | Investigate, stop promotion, revert-or-patch, catalog/corpus entry, re-run tests and probes. |
| Rollback runbook | Git revert, `maez.service` restart, focused tests, probe sweep, cognition-log confirmation. |

---

## Plain English

The panel agreed with the shape but blocked the loose parts. The old phrase must
die, but the replacement cannot be another hidden machine phrase, the tests
cannot be prompt-shaped vibes, and the telemetry cannot break the cockpit or
fail open. The amended spec now says the practical thing: delete bad sentences,
keep good ones, use one reviewed fallback only when nothing survives, preserve
existing public modes, and make every future regression countable.
