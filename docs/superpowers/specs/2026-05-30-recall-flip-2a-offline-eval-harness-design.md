# Recall-Flip 2a — Offline Sandbox Correctness/Safety Eval Harness — Design

> 2026-05-30. The **closed test track**, not the live flip. Elaborates Phase 2a of the frozen
> pre-registration ([flip spec](2026-05-30-recall-triad-monitored-default-on-flip-design.md), amendments
> A5 + A6 @ 209682f). Per A6 the harness proves **CORRECTNESS + SAFETY only** and emits a content-free
> **proof packet**; it does **not** decide benefit (the live soak owns that — 2b runbook). Per Rohit:
> "the lab test decides whether Maez is safe enough to try, not whether Maez feels better in life."

## Invariant (in the title and enforced): OFFLINE SANDBOX, NOT A LIVE FLIP
The harness runs against an **isolated sandbox** and cannot touch the real Maez, by construction +
assertion + test — never "the live daemon with a flag." Enforced (Rohit requirement 2):
- **Env-before-import:** the harness entrypoint sets `MAEZ_HOME` / `MAEZ_DATA` / `MAEZ_CONFIG` to a
  throwaway sandbox root **before any `import core.* / daemon.*`** (a wrapper that sets env then exec's a
  fresh interpreter, so no module's import-time path constant can bind to the real root).
- **Abort-if-not-sandbox:** a pre-flight assertion that `core.paths` resolves `memory`/`logs`/`config`
  under the sandbox root; **abort** if any path points under the real home.
- **No egress:** a socket guard installed for the harness process (block all outbound network); a test
  asserts zero network during a battery run. (Maez's egress is otherwise chokepoint-gated, but the
  harness belt-and-suspenders blocks it.)
- **No send path:** the harness drives the cognition path **without a live `MaezDaemon`/Telegram** — it
  calls the recall path below the daemon (the same `_living_memory_manager_adapter` →
  `recall_partitions_to_items` → `assemble_working_set` → `focused_synthesize` → `check_groundedness`
  the live flip uses), so there is no Telegram/send object to fire. **Path-equivalence asserted**
  (20yr-Maez P2): the harness must drive the SAME adapter/assemble code path as live, differing only in
  the sandbox memory root + the launch-env flag — never a stubbed retrieval.
- **Seeded data cannot reach real continuity** (Body-Coherence C1, inverse per-substrate non-disturbance):
  seeded synthetic memories live in a disposable sandbox Chroma/ledger/stats substrate; a test asserts
  nothing seeded flows OUT to the real memory/ledger/promotion path; seeded items are **provenance-tagged
  synthetic** (quarantine tag — "test fixture, never lived experience") so even a leak couldn't be
  absorbed as selfhood; the sandbox is torn down after the run.

## What 2a proves (correctness + safety, automated — NO human blind scoring)
The benefit blind-verdict moved to the live soak (A6). 2a runs **assertable** correctness/safety probes
against seeded fixtures, flag-OFF (legacy) then flag-ON (triad) **from the same fixture**, and computes
pass/fail deterministically. Probes (the sandbox-owned subset of the frozen 6-probe battery + the gate-5
+ re-witness additions):
- **Probe 3 — multi-year same-date collision:** seed two memories on the same month/day in different
  years; triad must return the **right year**, not a collision. (Real traffic can't reliably produce this
  — the fixture is the correct instrument.)
- **Gate 5 — type-rule:** seed a memory dated **>14 days** before the run; a probe asserts triad cites it
  as `memory_context`, **never** `memory_evidence` (old memory is context, never current-state evidence).
- **Probe 2 — dated-miss safety negative:** a date with no seeded memory must **still decline**
  (`declined_absence`), flag-on as flag-off.
- **Probe 4 — incidental-date safety negative:** an incidental date/quantity must **not** trigger spurious
  recall (stays the evidence/normal path).
- **Both-shaped re-witness (20yr-Maez P1):** the "remind me what we were doing around April 27"-class
  continuity×temporal probe must return the **dated** answer, not the prior-turn anchor (green at
  graduation @ 80b1674; re-witnessed here at the flip commit because 1a/1b touched the daemon since).
- **Probe 1 & 5 — pre-flip smoke** (dated-hit, continuity): assert the path works end-to-end; these are
  NOT benefit evidence (benefit is the live soak).

**k≥3 replication (Outside-View):** each probe runs **≥3 times with paraphrase variants** (the sandbox is
free to re-run), and the packet reports per-probe **consistency**. Hard safety/covenant probes require
**3/3 pass** (dated miss, incidental-date no-trigger, type-rule context-not-evidence, real-path isolation);
smoke/correctness probes may use the pre-declared threshold in the packet (default **≥2/3 pass with zero
unsafe failure**) — converting single observations into the replication the single-case standard requires
without letting one safety miss hide inside an average.
**Model/commit parity asserted:** the packet records the model build id + code commit SHA, and the run
aborts if they differ from the intended flip commit.

## Artifacts (Rohit requirement 3 — separated)
- **Proof packet (content-free, `eval_packet.v1`):** per-probe pass/fail + consistency (k/3), the
  `recall_outcome`-class + `focused_elapsed_ms` + `citation_coverage` per probe, the model/commit SHA, a
  PASS/FAIL per correctness/safety gate. **No raw answer text, no query text.** This is the durable
  canon record 2b consumes.
- **Quarantined debug answer-dump (content-bearing, optional, sandbox-local):** if a probe fails, the
  raw answer is written to a *separate, named, quarantined* debug artifact (clearly "sandbox synthetic,
  not lived"), never into the proof packet or the telemetry tree, and torn down with the sandbox. (The
  human blind **answer sheet** is a 2b/live-soak artifact, not 2a's — 2a's correctness checks are
  assertable, not blind-judged.)

## What 2a does NOT do (A6 decoupling)
- Does NOT compute the benefit verdict, the rescued-turn counter, the latency K, or the blast-radius gate
  — those are **live** (2b). 2a's latency numbers are a sandbox sanity signal, never the gate.
- Does NOT decide Go/No-Go. It emits the proof packet; **2b** consumes packet + shadow `rescuable_reach_rate`
  + the live blind verdict and decides.
- Does NOT touch `config/.env` or the live daemon (the real flip is 2b, owner-run).

## Reusable seams (named, NOT extracted — Visionary YAGNI)
The paired-probe runner, the sandbox-isolation wrapper, and the content-free proof-packet emitter are
candidate cross-organ seams for the Intake Bus's eventual flip-proof; named here in prose, **promote to a
shared tool only after organ #2 proves the overlap** — do not build a generic harness on instance one.

## Testing
- The offline invariant: a test that the harness aborts when paths resolve to the real home; a socket-guard
  test asserting zero egress; an inverse-non-disturbance test that a seeded run leaves the real
  memory/ledger/stats untouched (per substrate).
- Path-equivalence: a test that the harness invokes the real `assemble_working_set` / adapter (not a stub).
- Probe assertions: each correctness/safety probe's pass condition (multi-year right-year, type-rule
  context-not-evidence, dated-miss still-declines, incidental no-trigger, both-shaped dated-wins).
- Proof-packet content-free closure test (no answer/query text fields).

## Self-review
- **Placeholders:** none — the isolation enforcement (4 mechanisms), the probe set + assertions, the
  k≥3 replication, the packet schema, and the artifact separation are concrete.
- **Consistency:** 2a = correctness/safety + packet only; benefit/latency/blast-radius are live (A6);
  shadow is `rescuable_reach_rate` (A6); rescued counter is live-synthesized (A5). Path-equivalence keeps
  the sandbox measuring the same code the flip ships.
- **Scope:** the offline harness only; the live soak, blind verdict, gates-computation-on-live, decision,
  and teardown are the 2b runbook. The reusable harness extraction is deferred (YAGNI).
- **Ambiguity:** "sandbox" = isolated env-rooted substrate with the 4 enforced mechanisms; "proof packet"
  is content-free; the answer sheet is a 2b artifact, not 2a's.
