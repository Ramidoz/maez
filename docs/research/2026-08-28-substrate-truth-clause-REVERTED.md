# SUBSTRATE-TRUTH clause — proposed, falsified as a fix, REVERTED

**Status:** NOT LANDED. Owner ruling 2026-08-28. The patch is preserved beside
this note as `2026-08-28-substrate-truth-clause-REVERTED.patch`.

## What it was

A widening of the existing EXPLORATORY-ASK RULE in the planner manifest so that
"exploratory question about the local machine" also covered questions about
Maez's own code/runtime, plus a SUBSTRATE-TRUTH clause:

> a factual claim about YOUR OWN current code, tests, modules, runtime or body
> is an EMPIRICAL question about a thing that exists on this disk … If a tool
> can inspect it, inspect it BEFORE asserting anything about it.

and a first-attempt shape row pointing self-inspection questions at
`self_dev.propose_tests`.

## Why it was written

The first live D1 seam-2 witness failed: Maez answered *"I don't have a standard
unit-test suite…"* without inspecting a repository that plainly has one. That
looked like a model-disposition problem — answering from priors about its own
anatomy — and this clause was the narrowest existing semantic home for a rule
against it.

## Why it was reverted

The diagnosis was wrong, and a controlled baseline proved it. Reverting
`brain_loop.py` to the pre-clause version and re-running the planner showed the
UNMODIFIED code already selects `self_dev.propose_tests` **3/3** for the owner's
exact sentence, including under the real live prompt shape (question first,
manifest last, with and without a recent-conversation block).

The actual cause was stale process state: daemon pid 1166740 started 12:44:14,
the action landed at 22:16:30 (`297b3c5`), the owner's turn arrived at 22:21:32.
Python imports once, so the running process held a manifest with no such tool
and an allowlist without it. Maez did not decline an affordance; it was never
offered one.

Owner ruling: *"Do not land architecture to fix a failure that was actually
caused by stale process state."*

## What is worth keeping from it

Only the measurement. With the affordance present, the planner discriminates
INTENT rather than keywords — 5/5 on lexically varied positives, 5/5 on negative
controls, where every negative contains "test"/"testing" and stays silent while
*"any part of you is missing coverage"* fires without the word. That is evidence
about the existing planner, not an argument for this clause.

If a real disposition failure is ever demonstrated on a process that actually
carries the affordance, this patch is the starting point — and the semantic home
identified (EXPLORATORY-ASK, not a new recognizer) still stands.

## Related

- `feedback_witness_live_reload_not_merge` — merged is not activated; witness
  the in-memory state and the pid, not the commit.
