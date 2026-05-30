# Recall-Stack Bundle Resolver — Codex Six-Agent Engineering Pass

**Date:** 2026-05-30
**Branch:** `recall-stack-bundle-resolver`
**Base:** `ffe85ef`
**Purpose:** pre-code Codex engineering pass for the recall-stack bundle resolver slice.

## Verdict

All six roles accepted the one-bundle resolver shape, but all six converged on
the same structural amendment: **selected focused mode is not enough to mean the
dated recall carrier was consulted**.

Plain English: walking toward the memory shelf is not the same as opening it.
Maez may only say "I don't have a dated memory" after the shelf actually opened
and produced a working set/status.

## Findings Folded Before Code

### Dewey

- Keep the one-bundle switch. It improves operator reality by making partial
  triad launch impossible.
- Amend carrier consultation: focused mode can be selected while assembly later
  raises or returns no usable working set.
- Make env tests hermetic so witness/default-on shell state cannot pollute
  assertions.
- Expand migration search to `tests/` as well as `docs/` and `scripts/`.

**Fold:** implement `consulted` only after focused assembly returns a working
set/status; write hermetic env helpers in new tests; update existing test
fixtures as part of the affected tasks.

### Feynman

- Split "selected" from "consulted".
- Reconcile the spec's once-per-turn claim with code that would otherwise call
  the resolver repeatedly.
- Fix telemetry tests to listen to the actual daemon logger.

**Fold:** resolve the recall stack once inside `handle_message` and `run_brain_loop`
turns, pass that config into local helper calls, and use `maez`/the daemon logger
in telemetry assertions.

### Locke

- Memory absence is an owned claim. If focused assembly fails before memory is
  examined, absence wording would be false ownership.

**Fold:** path-unavailable wording is used for no consultation or consultation
failure; absence wording is legal only for a completed consultation with no
confirmed dated item.

### Descartes

- Helper-only denial tests are insufficient; daemon wiring must prove the real
  fallback uses the consultation fact.
- The five production raw read sites are correctly identified.

**Fold:** add daemon-shaped denial tests for assembly failure and successful
working-set consultation, in addition to helper tests.

### Ohm

- Avoid "two reads, two realities" in one turn.
- Startup telemetry belongs after daemon logging is configured, next to existing
  activation startup posture.

**Fold:** keep helper defaults for unit tests, but thread one resolved config
through daemon/brain turn decisions.

### Goodall

- The receipt must remain understandable to future maintainers.
- Add turn-level dated-denial telemetry, not only startup posture.

**Fold:** add a structured `dated_recall_denial` log with mode/reason, receipt,
confirmed state, and reply kind.

## Resulting Amendments

1. `carrier_available` remains config-level and means "triad enabled".
2. `_recall_carrier_consulted` becomes a turn-local execution fact set only
   after focused assembly returns a non-`None` working set/status for the dated
   turn.
3. `_recall_carrier_receipt` distinguishes `not_consulted`, `consulted`, and
   `consult_failed` for logging and reply selection.
4. Resolver config is captured once per daemon/brain turn and passed to local
   helper calls where both decisions occur in the same turn.
5. New tests are hermetic around all four recall flags.
6. Raw-flag migration explicitly searches `tests/`, `docs/`, and `scripts/`.

