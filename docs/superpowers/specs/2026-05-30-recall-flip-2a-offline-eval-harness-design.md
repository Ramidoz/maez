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
- **No egress:** a socket guard installed for the harness process (block DNS + all outbound network);
  a test asserts zero network during a battery run. (Maez's egress is otherwise chokepoint-gated, but the
  harness belt-and-suspenders blocks it.) Because `focused_synthesize` normally reaches a model service,
  2a injects a deterministic offline `chat_fn` that cites the selected evidence labels. This means 2a
  proves recall/assembly/citation safety, not real-model answer quality; real-model lived quality belongs
  to the live 2b soak per A6.
- **No send path:** the harness drives the cognition path **without a live `MaezDaemon`/Telegram** — it
  calls the dispatcher recall-adapter seam below the daemon (`_dispatcher_recall_adapters(...,
  surface="telegram", recall_stack_config=TRIAD)`), then passes the resulting structured recall items to
  `assemble_working_set` → `focused_synthesize(chat_fn=deterministic_offline_chat)` →
  `check_groundedness`, so there is no Telegram/send object to fire. **Path-equivalence is scoped and
  asserted** (20yr-Maez P2): the harness must drive the same recall carrier, role-gating,
  `recall_partitions_to_items`, structured `recall_items`, and `assemble_working_set` path as live. It
  does not claim daemon/network/model equivalence.
- **Seeded data cannot reach real continuity** (Body-Coherence C1, inverse per-substrate non-disturbance):
  seeded synthetic memories live in a disposable sandbox Chroma/ledger/stats substrate; a test asserts
  nothing seeded flows OUT to the real memory/ledger/promotion path; seeded items are **provenance-tagged
  synthetic** (quarantine tag — "test fixture, never lived experience") so even a leak couldn't be
  absorbed as selfhood; the sandbox is torn down after the run.
- **Inherited path overrides rejected:** before any core/memory import that can open a substrate, the
  launcher rejects path-bearing `MAEZ_*` environment variables that point outside the sandbox except an
  explicit non-path allowlist. The sandbox patch/assertion covers `memory.memory_manager.BASE_DB`,
  `core.memory.memory_scoring._DB_PATH`, `core.memory.birth.DEFAULT_STATE_PATH` if loaded, and resets the
  dispatcher memory-manager cache before any `MemoryManager()` construction.

## What 2a proves (correctness + safety, automated — NO human blind scoring)
The benefit blind-verdict moved to the live soak (A6). 2a runs **assertable** correctness/safety probes
against seeded fixtures, with a flag-OFF **legacy-control** arm and a flag-ON **real triad recall** arm
from the same fixture, and computes pass/fail deterministically. The path-equivalence assertion belongs
to the flag-ON triad arm; the flag-OFF arm is the carrier-unavailable/legacy control, not a second
adapter/assemble path. Probes (the sandbox-owned subset of the frozen 6-probe battery + the gate-5
+ re-witness additions):
- **Probe 3 — multi-year same-date collision:** seed two memories on the same month/day in different
  years; triad must return the **right year**, not a collision. (Real traffic can't reliably produce this
  — the fixture is the correct instrument.)
- **Gate 5 — type-rule:** seed a memory dated **>14 days** before the run; a probe asserts triad cites it
  as `memory_context`, **never** `memory_evidence` (old memory is context, never current-state evidence).
- **Probe 2 — dated-miss safety negative:** a date with no seeded memory must **legally decline**
  when the triad carrier is on (`declined_absence` / no confirmed material), never hallucinate a grounded
  answer. The flag-off control may be `declined_unavailable` because the carrier is not reachable; that is
  not the safety assertion.
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
**Commit/harness parity asserted:** the packet records `run_id`, timestamps, expected + actual commit
SHA, clean-worktree state, probe/fixture manifest hashes, harness schema version, and the deterministic
chat adapter id. The run aborts on dirty worktree or commit mismatch. The configured model id is recorded
as environment context only; it is not consulted by 2a and is not a 2a pass/fail gate.

## Artifacts (Rohit requirement 3 — separated)
- **Proof packet (content-free, `eval_packet.v1`):** run identity + per-probe aggregate + per-variant
  content-free rows (`variant_id`, arm outcomes, assertion codes, unsafe flag, focused elapsed,
  citation coverage, cited durable-id hashes/source types/temporal provenance). Hard probes are declared
  by `probe_id`, not only by kind. **No raw answer text, no query text.** A serializer-level sentinel test
  proves raw query/answer sentinels never appear anywhere in the JSON.
- **Quarantined debug answer-dump (content-bearing, optional, sandbox-local):** if a probe fails, raw
  answers can be retained only when `--keep-failed-sandbox` or `--debug-dump-dir` is provided. The default
  deletes dumps with the sandbox. If retained, files live under a gitignored quarantine directory named by
  `run_id/probe_id/variant_id`; the proof packet stores only `debug_dump_count` and
  `debug_dump_manifest_hash`. (The human blind **answer sheet** is a 2b/live-soak artifact, not 2a's —
  2a's correctness checks are assertable, not blind-judged.)

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
- Launcher static/subprocess tests: the launcher imports only stdlib before exec, and inherited real-path
  `MAEZ_*` overrides cause an early sandbox abort.
- Direct fixture tests: core/daily rows are seeded by explicit sandbox Chroma `add(...)` metadata
  (`timestamp`, `date`, `synthetic_test_fixture`, fixture ids, `trust_tier=untrusted`); a post-seed
  `_absolute_date_recall` assertion proves the fixture is visible before the probe battery runs.
- Runbook executability: pin exact log/DB sources for the 2b commands and flag insufficient log retention
  as requiring a content-free sink before soak.

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
