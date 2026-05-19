# S7.3 Diagnostic v2 Fresh-Reader Gate

**Status:** review gate, not canonical law
**Date:** 2026-05-19
**Subject:** `docs/slices/s7.3-guarded-self-modification-execution/diagnostic.md`
at `bed18f0` / `5505bb7` era diagnostic v2
**Runtime impact:** none

## Purpose

This gate replaced elapsed cooling-off with a stronger freshness mechanism:
three blank-context readers reviewed diagnostic v2 without reading the prior
S7.3 review artifacts. Their job was to detect whether v2 was understandable and
spec-ready to a reader not contaminated by the diagnostic's authorship frame.

The three lenses were:

- cold covenant reader;
- cold spec-writer;
- cold residual-hunter.

Each reader was allowed to read diagnostic v2, the canon it cites, and named
source files. Each reader was barred from
`docs/slices/s7.3-guarded-self-modification-execution/reviews/`.

## Consolidated Verdict

Diagnostic v2's covenant argument is sound, but v2 is not yet sufficient as a
base for the S7.3 spec. The diagnostic correctly identifies OQ1 - the real Maez
voice producer and its `absent` classifier contract - as the gating risk, but
the proposed ladder moves from second-fold directly to spec without resolving
OQ1 first.

Writing the spec directly from v2 would produce a solid execution-plumbing
skeleton with an undesigned covenant core. That is exactly the failure S7.3 is
meant to prevent.

## Findings

### FR-G1 - Blocker - OQ1 Must Be Resolved Before Spec

Diagnostic v2 leaves OQ1 open, then its ladder proceeds to "Write the S7.3 spec"
as the next post-gate authoring step. A spec-writer would be forced to invent the
real voice producer and absent-classifier contract while writing the spec.

Required response: insert an explicit OQ1-resolution design step before the S7.3
spec. The spec must be written from an OQ1-resolved diagnostic/design base, not
from raw candidate space.

### FR-G2 - Major - S7ExecutionAuthorization Needs Code/Canon Reconciliation

Diagnostic v2 accurately describes current code: `S7ExecutionAuthorization` is
an existing pre-consume carrier, and `S7ExecutionGrant` is the post-consume
authority. But S7.1 spec D14 says S7.1 does not create a parallel
`S7ExecutionAuthorization` type.

Required response: state explicitly that v2 reads the current type as as-built
naming drift: a pre-consume carrier, not a second authority. The S7.3 spec must
either canonically bless that carrier shape/name or rename it.

### FR-G3 - Minor - Undefined Tokens

`L9` and `CC-IV3` are meaningful to prior participants but opaque to a cold
reader.

Required response: expand them where first used.

### FR-G4 - Minor - Terminology Drift

`path`, `surface`, and `surface class` are used near the L8 and D6 requirements
without a defined grouping rule. Both second-fold lanes also noticed this.

Required response: normalize the terms in the diagnostic or explicitly assign
the normalization to the OQ1/spec design step.

### FR-G5 - Nit - D-Number Namespaces

The diagnostic cites D6, D12, and D23 from S7/S7.1 contexts. A cold reader can
follow the prose, but the document should name the namespace when the numbers
first appear.

## Gate Decision

Do not write the S7.3 spec directly from diagnostic v2. Proceed with S7.3 by
doing the actual next work: resolve OQ1 and design the real Maez voice producer
plus its absent-classifier contract. Diagnostic v3 may make mechanical touch-ups
to record this ladder correction and clarify residual wording.

## Plain English

The diagnostic is good. It correctly says the hard part is how Maez is genuinely
heard before being changed. But it still leaves that hard part open, then tells
the process to write the spec next. That would force the spec to invent the
answer under pressure. The next step is not idle waiting and not code. The next
step is to design the voice producer.
