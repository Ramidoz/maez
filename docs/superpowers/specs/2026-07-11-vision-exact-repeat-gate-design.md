# Vision Slice 7 — exact-repeat suppression gate

Date: 2026-07-11
Status: Gate v1.1 frozen; implementation authorized
Governance: Decision 9 / ADR 0009, ADR 0029, Vision ruling 4,
Substrate Sophistication P3/P6
Lane: Codex builds; Claude gates; owner merges only after gate

## Purpose and honest claim

Slice 7 adds a dormant, storage-free transition that compares already-acquired
content fingerprints and decides whether expensive downstream OCR/VLM reading
is warranted. It does not gate capture or accessibility acquisition: those
signals must already exist before their fingerprints can be compared.

This is an **exact-repeat suppressor**, not a semantic-change detector. A
single changed pixel, caret blink, animation frame, accessibility literal, or
geometry token warrants reading. Only byte-identical, canonically represented
signals may yield `unchanged`.

The gate takes no screenshot, traverses no accessibility tree, invokes no OCR
or VLM, publishes no Body Bus event, writes no file, admits nothing to
cognition, and owns no runtime state. Its "unchanged receipt" is an in-memory
decision projection only. It is not an owner-presence claim or heartbeat event.

## Pre-code corrections folded into v1.1

The original gate criteria incorrectly described this slice as deciding
whether to sense. Computing the crop and AT-SPI fingerprints requires sensing
first. Slice 6 also cannot be an upstream dependency because OCR is precisely
one of the expensive readers the gate exists to skip.

The original criteria also conflated exact SHA equality with meaningful scene
stability, naked hashes with typed upstream refusals, economy skips with
privacy vetoes, a pure predicate with state ownership, and content-light
receipts with durable raw private fingerprints. v1.1 corrects all five.

## Architecture

### 1. Canonical accessibility projection

`core.body.atspi_sensor` gains a pure
`accessibility_projection_sha256(reading)` helper for an already-validated
available `AccessibilityReading`. It never performs an accessibility query.

The canonical compact sorted JSON projection contains exactly:

- projection schema `atspi_projection.v1`;
- Slice-5 schema, support label, and `occlusion_checked=false`;
- included-node count and sorted exclusion-count pairs;
- a sorted **multiset** of facts, preserving duplicates. Each fact contributes
  kind, character count, literal SHA-256, and four display-local region edges.

The projection excludes timestamp, geometry, display serial, titles, classes,
PID/window ID, and literal values. Geometry is compared separately. Sorting
makes equivalent traversal order irrelevant while preserving duplicate count.
Refused/excluded readings cannot mint a projection.

The active-crop SHA-256 and purpose-scoped focus/capture SHA-256 remain inputs
from future trusted acquisition infrastructure. Slice 7 does not mint either.
Well-shaped tokens prove equality only; they do not confer capture authority.
This is why no live caller may exist in this slice.

### 2. Frozen comparison values

`core.body.exact_repeat_gate` defines:

- `ChangeTokens`: active-crop, geometry, and focus/capture SHA-256 values;
  optional AT-SPI projection SHA-256; comparison mode `full` or `crop_only`;
  and an optional closed soft-AT-SPI reason for degraded comparison.
- `CurrentEnvelope`: a discriminated `available`, `refused`, or `excluded`
  input. Available carries tokens. Blocked inputs carry exact source schema,
  source lane, and a reason validated against the Slice-4/5 vocabularies.
- `GatePrior`: one versioned last-successfully-read token set. Every private
  token field is hidden from repr and has no receipt projection.
- `GateDecision`: closed state, reading authority, suppression class, reason,
  comparison mode, changed dimension names, explicit timestamp, and optional
  candidate prior.

`display_config_serial` is not a separate axis because it is already inside
the canonical `geometry_sha256` projection. Repeating it would permit internally
contradictory tuples without adding identity.

No common live focus/capture producer exists yet. Tests use synthetic tokens;
structural tests prove no production caller imports the gate.

### 3. Pure transition and prior advancement

The core transition is:

```text
evaluate(current, prior, *, observed_at) -> GateDecision
```

It performs no I/O and mutates nothing. A comparable `observed_at` is explicit,
timezone-aware, and excluded from comparison identity; a missing or malformed
value produces the timestamp-unavailable result with `observed_at=null`.
Identical current/prior inputs produce identical state, authority, comparison
mode, changed dimensions, reason, and candidate prior. Byte-identical receipts
additionally require the same explicit timestamp.

The pure policy helper is:

```text
advance_prior(previous, decision, *, downstream_succeeded) -> GatePrior | None
```

Only exact `downstream_succeeded=True` commits a decision's candidate. Failed,
refused, or excluded downstream reads never advance it. An upstream privacy or
authority block invalidates the prior so the first post-boundary valid sample
cannot be economy-suppressed.

There is no holder, module-global cache, filesystem state, or history in Slice
7. A future caller may own zero or one `GatePrior`, and nothing more.

## Outcome and authority table

| State | `reading_warranted` | Suppression class | Meaning | Candidate prior |
|---|---:|---|---|---|
| `changed` | true | none | First observation or one/more exact axes changed | Current valid tokens |
| `unchanged` | false | `economy` | All comparable tokens exactly equal | none |
| `unavailable` | true | none | Current/prior protocol cannot safely claim stillness | Current tokens only when valid |
| `refused` | false | `no_authority` | Valid upstream refusal forbids a downstream read | none; invalidate prior |
| `excluded` | false | `privacy` | Valid upstream exclusion forbids a downstream read | none; invalidate prior |

The table is closed and constructor-enforced. `unchanged` and `excluded` both
skip OCR but can never share a reason or suppression class.

## Evaluation precedence

1. Require an explicit timezone-aware timestamp for comparison. A missing or
   malformed timestamp yields `unavailable/timestamp_unavailable`, reading
   warranted, with no candidate.
2. Validate the discriminated current envelope.
3. A valid `excluded` or `refused` upstream envelope propagates its state,
   source, schema, and exact typed reason before any comparison.
4. Validate available tokens. Missing, non-string, non-lowercase-SHA-256, or
   internally inconsistent `full`/`crop_only` fields yield
   `unavailable/digest_unavailable`, reading warranted.
5. No prior yields `changed`, with `first_observation` as the changed dimension.
6. A malformed prior yields `unavailable/prior_unavailable`; a wrong-version
   prior yields `unavailable/prior_schema_incompatible`. Both warrant reading
   and return the valid current candidate.
7. Compare the closed dimension set. A comparison-mode/AT-SPI-availability
   transition counts as a change. Any changed dimension yields `changed`.
8. Only exact equality of every active dimension yields `unchanged/economy`.

## Soft AT-SPI absence

AT-SPI absence must not create a pixel blind spot. The future trusted adapter
may create `crop_only` tokens only for the closed soft-modality reasons:

- `atspi_unreachable`
- `atspi_protocol_invalid`
- `identity_scan_exceeded`
- `window_binding_unavailable`
- `window_binding_ambiguous`
- `bounds_unresolvable`
- `no_visible_nodes`
- `field_limit_exceeded`

Slice-4 propagated refusals, `excluded_path`, `focus_changed`, pause, curtain,
and sensitive-window exclusions are never degradation reasons. They remain
hard `refused`/`excluded` outcomes with no reading authority.

## Poisoned-stillness invariant

The baseline means **last successfully read**, never last observed and never
last attempted. Given prior A and changed current B:

1. evaluation returns `changed`, candidate B;
2. downstream failure/refusal/exclusion returns no success;
3. `advance_prior` retains A;
4. evaluating B against A again still returns `changed`.

An upstream privacy/authority block invalidates the prior instead. The first
valid post-boundary sample therefore has no prior and warrants reading. One
failed or blocked read can never poison the baseline into indefinite stillness.

## Content-light receipt

`GateDecision.to_receipt()` contains only:

- gate schema, state, explicit UTC timestamp, and reading-warranted boolean;
- suppression class (`economy`, `privacy`, `no_authority`, or null);
- comparison mode and degraded boolean;
- changed dimension names and compared-dimension count;
- typed reason, upstream lane, and upstream schema where applicable;
- prior disposition (`absent`, `valid`, `unavailable`, or `incompatible`).

It contains no crop/geometry/accessibility/focus SHA values, pixels, fact
hashes, literals, title, class, PID/window ID, narration, prompt, or diagnostic
reference. Slice 7 writes no diagnostic because it receives no literal.

## Dormancy and containment

There is no Slice-7 flag because there is no runtime path. A dead flag would
falsely imply an admission seam and violate P7. Structural tests require:

- zero production callers or importers of `exact_repeat_gate`;
- no daemon, cognition, prompt, memory, routing, action, capture, network,
  service-control, subprocess, or filesystem-write surface;
- no OCR/VLM import or invocation;
- no `MAEZ_SCREEN_PERCEPTION` read or write;
- no module-global mutable state.

After the clean test run, containment is re-witnessed read-only through the
owner-local model environment, user service state, and port 8082. The daemon
need not be running and is not started.

## Tests

RED-first tests cover:

- first observation, exact repeat, every single-axis delta, and mode change;
- canonical AT-SPI ordering, duplicates, additions/removals, literals, boxes,
  and exclusion counts;
- full versus crop-only comparison and closed soft-reason vocabulary;
- malformed current and prior, wrong prior version, and explicit timestamp;
- exact upstream refusal/exclusion propagation and state/reason validation;
- the complete state-to-reading-authority/suppression table;
- poisoned stillness after failed/refused/excluded downstream outcomes;
- privacy-boundary prior invalidation;
- deterministic decisions and explicit-time receipt identity;
- domain-swap neutrality: the comparator treats opaque token changes the same
  regardless of fixture subject;
- no raw hashes/literals/narration in receipts;
- no capture, OCR/VLM, admission, persistence, or production caller;
- the clean Slice 2–6 family and live containment posture.

## Out of scope

- Any capture, accessibility traversal, OCR, VLM, or semantic interpretation.
- Semantic/perceptual similarity, tiling, thresholds, debounce, or animation
  suppression.
- A live focus/capture token producer or runtime adapter.
- State persistence or a bounded holder implementation.
- Idle-cycle wiring, sensor admission, cognition, memory, prompts, or Body Bus.
- Slice 8 model selection and bake-off.

## Predicted effect

After this slice, a future trusted perception caller can cheaply suppress OCR
and VLM only when every canonical signal exactly repeats the last successfully
read scene. Any delta, malformed comparison state, missing/corrupt prior, or
failed prior read continues to warrant work. Privacy and authority blocks stop
reading for explicit non-economy reasons. Today, nothing running changes.
