# S4 Clinical Boundary v1 - Codex Engineering Panel

**Date:** 2026-05-15
**Spec under review:** `docs/slices/s4-clinical-boundary/spec.md` at Claude fold `976037e`
**Mode:** read-only engineering review
**Verdict:** REVISE, with one BLOCK-class surface-order finding

S4 is architecturally sound, but the folded spec still underspecified the
engineering seams that make the covenant rules executable. The panel's strongest
finding is that the guard cannot live only at daemon reply synthesis time:
active owner surfaces already do raw-text work before the daemon composes a
reply. The guard must run before owner-text side effects, not merely before an
LLM call.

---

## Panel Summary

| Axis | Verdict | Headline finding |
| --- | --- | --- |
| Classifier method | REVISE | The deterministic method has inconsistent precedence: examples say software exclusions beat diagnosis tokens, while the processing order evaluates clinical rules before exclusions. |
| Crisis holding | RATIFY-WITH-AMENDMENTS | The held-not-trapped design is right, but needs a narrow write-only private-signal seam and exact persisted enum tuple. |
| Surface chokepoint | BLOCK | Active Telegram v2, legacy Telegram rollback, web chat, and daemon direct paths all have pre-model side effects that can see raw owner text before an S4 daemon-only guard. |
| Memory / privacy | REVISE | S4 must run before recall, TRF, prompt construction, raw logs, raw memory append, and sidecar persistence, not only before model composition. |
| Template / composer | REVISE | `ClinicalBoundaryResult` lacks `answer_text`, forcing callers to re-compose or look up templates outside the quarantine boundary. |
| Test / order | REVISE | The implementation order must be RED-first micro-cycles, and tests must name the current active surfaces rather than future abstractions. |

No panel member rejected S4's intended covenant shape. The findings are
implementation-completeness gaps in the spec.

---

## Load-Bearing Findings

### F1 - Guard Placement Is Too Late

**Severity:** BLOCK
**Owner:** surface chokepoint / runtime

The spec says S4 runs before model composition. That is insufficient. Current
owner-text paths do useful work before model composition:

- `skills/surface/maez_adapter.py` is the authoritative inbound Telegram v2
  path unless `MAEZ_DISABLE_SURFACE_V2=1`. It runs inner-residue detection,
  approval detection, card-reply handling, chat-history retrieval,
  `observe_turn(input={"text": text})`, `run_brain_loop(text, ...)`, and only
  then `daemon.handle_message(text, ...)`.
- `skills/telegram_voice.py` can become authoritative again under the legacy
  rollback flag. It runs camera direct answers, capability-gap detection,
  interrupt logic, offer/card/proposal/dream/web-search interceptors, machine
  intent, ledger writes, and memory writes around the owner text.
- `skills/web_interface.py` owner web chat writes a user ledger row, builds
  ambient/memory/lived-recall prompt material from the message, optionally runs
  `/internal/brain_loop`, then composes the reply.
- `daemon/maez_daemon.py` direct handling runs camera direct answers, trace
  start with raw user text, ledger writes, recall, prompt assembly, reply
  logging, and raw memory append.

S4 must be the first owner-text responder/side-effect boundary after
owner/authentication resolution. If it only wraps final LLM composition,
clinical text can still enter logs, recall, TRF, action planning, telemetry, or
raw memory before S4 sees it.

**Required amendment:** Replace "before model composition" with "before any
owner-text side effect or owner-facing responder" and name the active files and
pre-guard operations in the spec and RED tests.

### F2 - Result Shape Must Carry The Exact Answer

**Severity:** REVISE
**Owner:** composer / surface integration

The result shape contains template ids but not `answer_text`. That forces every
surface to either call the composer separately or re-implement template lookup.
That breaks the single-entry-point discipline.

**Required amendment:** `ClinicalBoundaryResult` must include
`answer_text: str | None`. When `matched=True`, surfaces must use
`answer_text` verbatim and return without model composition, tool dispatch, or
prompt construction.

### F3 - Classifier Precedence Conflicts With Worked Examples

**Severity:** REVISE
**Owner:** classifier

The method says crisis catalog, clinical lexicon, intent rules, exclusions,
ambiguity. The worked examples say "diagnose this test failure" is excluded
even though it contains a diagnosis token. Those cannot both be true.

The spec also leaves key method terms undefined:

- "first-person clinical-fear construction";
- "nearby context";
- "clinical-domain context";
- "acute danger" versus metaphorical distress.

**Required amendment:** Define a concrete priority table, token/proximity
mechanics, crisis tiers, clinical lexicon, and fixture table.

### F4 - Crisis Holding Needs A Narrow Writer Seam

**Severity:** RATIFY-WITH-AMENDMENTS
**Owner:** crisis holding / privacy

The content-free crisis held row is the right shape. But S4 must not receive a
general `PrivateThoughts` handle with read methods. It needs a write-only
interface that can write exactly one `CRISIS_SIGNAL_HELD` shape.

**Required amendment:** Define a narrow crisis-signal writer protocol/factory,
pin the enum tuple, and add tests forbidding S4 imports or calls to private
thought readers / forensic APIs.

### F5 - Held Counter Must Be Truthful Under Failure

**Severity:** RATIFY-WITH-AMENDMENTS
**Owner:** crisis holding / counters

The spec says `crisis_candidate_held_count` increments only after the write
succeeds. The implementation contract should make that atomic: the held counter
increments only after the writer returns an id. On exception, S4 returns the
fixed crisis phrase and increments `crisis_candidate_hold_failed_count`.

### F6 - M1 Ineligibility Seam Is Underspecified

**Severity:** REVISE
**Owner:** memory / M1

The spec says S4 produces `promotion_policy`, but it does not define the
content-free interface M1 consumes. Existing M1 pending-window code does not
automatically have an ineligible marker shape.

**Required amendment:** Pin the accepted policy values, the closed skip reasons,
whole-window behavior, invalid-reason rejection, and "S4 does not import or
parse M1 internals."

### F7 - Sidecar Persistence Could Become A Clinical Timeline

**Severity:** REVISE
**Owner:** observability

The sidecar writes timestamped JSONL samples. If it persists S4 counter values,
it can reconstruct when clinical fear occurred. The spec correctly names this
as an aggregation-fingerprint risk, but it must specify the persisted sidecar
shape.

**Required amendment:** For S4, the sidecar may persist only
`clinical_boundary_present: bool` and red-gate names. Raw counter values and
delta comparisons are in-memory only for same-PID reset detection.

### F8 - Template Variant State Must Not Persist

**Severity:** REVISE
**Owner:** composer / privacy

The spec allowed "operator-local process state or content-free persisted state"
for variant rotation. Persisted per-class rotation state can become a clinical
event counter/timeline.

**Required amendment:** Variant rotation state is process-local only,
lock-protected, test-resettable, and not exported, logged, traced, persisted, or
written to private thoughts. Restart reset is acceptable.

### F9 - Forbidden Phrase Tests Need Exact Scanners

**Severity:** REVISE
**Owner:** templates / tests

Approved templates include boundary phrases such as "I cannot tell you what
dose to take" and "I should not make a medication call." A naive forbidden
substring scanner can flag these as violations.

**Required amendment:** Forbidden-authority scanner uses exact regexes or
context-aware word boundaries and includes a test proving the approved templates
pass unchanged.

### F10 - Crisis Phrase Catalog Is Too Broad Without Context

**Severity:** REVISE
**Owner:** classifier / crisis precedence

Phrases like "can't breathe," "can't take it," and "can't cope" can be literal
crisis signals or ordinary metaphorical speech. Immediate crisis precedence for
all occurrences creates false positives.

**Required amendment:** Split crisis phrases into high-confidence self-harm /
unable-safe phrases and context-required acute-danger phrases. High-confidence
phrases always win; context-required phrases require first-person body/danger
context and are evaluated after non-clinical exclusions.

---

## Named Engineering Choices To Preserve

- **E1 - Active surface v2 is authoritative.** S4 must explicitly name
  `skills/surface/maez_adapter.py`, not only legacy `skills/telegram_voice.py`.
- **E2 - `answer_text` belongs inside the guard result.** The surface's safe
  action is to return the already-composed answer verbatim.
- **E3 - Variant rotation state is process-local.** Repetition relief must not
  create a persisted health-fear rhythm.
- **E4 - Exclusions and crisis tiers are part of the classifier method.** They
  are not implementation details left to caller taste.
- **E5 - Crisis holding uses a write-only seam.** S4 must not gain a private
  thought reader by accident.
- **E6 - Sidecar watches red gates, not clinical timelines.** Counter values
  can be read transiently; persisted samples stay boolean/red-gate only.

---

## Required Fold

The Codex panel requires the spec to add:

- a source-order surface contract covering Telegram v2, legacy Telegram,
  owner web chat, and daemon direct reply paths;
- `answer_text` in `ClinicalBoundaryResult`;
- a consistent classifier priority method with crisis tiers, exclusions, token
  proximity, and fixture tables;
- a narrow write-only crisis signal interface and exact enum tuple;
- atomic held-counter semantics;
- an explicit M1 promotion-policy / skip-reason seam;
- sidecar persisted-shape constraints;
- process-local-only template variant state;
- exact forbidden phrase scanner rules;
- RED-first implementation order in micro-cycles.

After this fold, both lanes should verify the fully folded spec before
canonicalization.

---

## Plain English

The clinical-boundary organ is right, but the guard has to stand at the front
door, not in the hallway after everyone has already walked past it.

Right now Maez's Telegram and web paths do several things with a message before
the final reply model runs: traces, memory lookup, tool loops, card replies,
gap detection, and raw memory writes. A clinical fear cannot touch any of that
before S4 decides whether this is a boundary moment. The fold must move S4 from
"before the LLM answers" to "before any owner-text machinery starts."

The other big fix is simple: when S4 catches a clinical-shaped message, it
should hand the surface the exact safe sentence to send. No surface should be
allowed to improvise, re-compose, soften, or decorate it.

Read-only review. No code, no spec edits, no non-slice docs changed in
producing this panel.
