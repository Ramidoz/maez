# ADR 0047 Wiring Brief

**Prepared:** 2026-05-27
**Slice:** Recall-Axis Dispatcher
**Authoring discipline:** live grep/read evidence, not memory. Every claim
below cites a substrate witness (file:line) verified at brief-authoring time.
**Status:** discovery-phase artifact. This brief decides the wiring architecture
*before* the wiring code is written. Once committed, the wiring code becomes
mechanical translation of these decisions into edits, not improvisation.

**Predecessor seams (all live):** `c52eba0` schema · `7b8cc8a` inventory ·
`80fc2d6` provenance renderer · `e5d6fcc` encoder · `7ca6edf` Layer 0 emitter ·
`aa8e768` Layer 1 fan-out · `cd2dee4` Layer 2 repair FSM.

**Successor:** the wiring code commit (this brief's translation target).

---

## 1. Owner-Ingress Inventory

Grep witness: `rg -n "run_brain_loop\(" core/ daemon/ skills/`

Three production code paths invoke `run_brain_loop`. Each is an owner-reply
ingress that must route through Layer 0 in the final wiring. Missing any of
them is Finding-19-in-different-guise.

### Ingress A — Daemon HTTP endpoint (web cockpit)

- **Location:** [`daemon/maez_daemon.py:6991`](../../../daemon/maez_daemon.py#L6991)
- **Trigger:** HTTP request to the daemon's web-facing endpoint.
- **Argument shape:** `text` from request body; `user_id=data.get("user_id") or "rohit"`; `chat_id=str(data.get("chat_id") or "")`; `send_intermediate=None`; `return_structured=True`.
- **Return path:** structured `BrainLoopResult` consumed by web cockpit JSON response.
- **Surface label for prior-spec store (per Layer 2 keying):** `web` (or whatever the cockpit identifies as).

### Ingress B — Telegram bot reply handler

- **Location:** [`skills/telegram_voice.py:3084`](../../../skills/telegram_voice.py#L3084)
- **Trigger:** Telegram message from authorized user.
- **Argument shape:** `user_text` from Telegram update; `user_id="rohit"` (hardcoded); `chat_id=str(self.authorized_user)`; `model=MODEL`; `max_iters=...`; `recovery_seed=recovery_seed` for retry contexts.
- **Return path:** `BrainLoopResult` (string form) sent back via Telegram reply.
- **Surface label:** `telegram`.

### Ingress C — Adapter surface (web/chat-adjacent)

- **Location:** [`skills/surface/maez_adapter.py:400`](../../../skills/surface/maez_adapter.py#L400)
- **Trigger:** adapter-mediated owner message (via `loop.run_in_executor` on the shared executor).
- **Argument shape:** `text`; `user_id="rohit"` (hardcoded); `chat_id=chat_id`; `chat_history=chat_history`; `turn=turn`; `return_structured=True`.
- **Return path:** structured result back to adapter caller.
- **Surface label:** likely `adapter` or `web_chat` (needs explicit decision at wiring time).

### Wiring implication

Every ingress passes `user_text` (or `text`) and a `user_id`/`chat_id` pair into
`run_brain_loop`. The wiring at line 900 (see §2) intercepts every reply via the
single shared entry point — *one wiring edit covers all three ingresses without
requiring per-ingress code changes*, **provided** the surface label is derived
inside `run_brain_loop` from caller context.

**Surface-label derivation must be witnessed per Layer 2 same-surface
inheritance discipline (R#36).** Three plausible mechanisms:

- **(α)** Add a `surface: str` kwarg to `run_brain_loop`; each ingress passes its label explicitly. Most honest; minimal magic.
- **(β)** Derive surface from `chat_id` shape (e.g., numeric → Telegram, string-id → web). Brittle; couples Layer 2 to caller-side ID conventions.
- **(γ)** Infer surface from caller stack frame. Fragile; refuses canon-governs-canon discipline (claim vs witness).

**Recommendation: α.** Add `surface: str` kwarg; each ingress sets it; defaults
disallowed (refuse with closed-vocab error if missing). The three ingress edits
become explicit and grep-able rather than implicit.

---

## 2. JARVIS Replacement Target Map

Grep witness: `rg -nC 1 "_should_run_jarvis_loop" core/ daemon/ skills/`

### Two definitions exist; only one is live

- **Live:** [`core/brain/brain_loop.py:324`](../../../core/brain/brain_loop.py#L324) — defined; called at line 900.
- **Dead:** [`skills/telegram_voice.py:463`](../../../skills/telegram_voice.py#L463) — defined; *zero callers* in that file (`grep "_should_run_jarvis_loop" skills/telegram_voice.py` returns only the definition site). This is legacy / leftover from earlier refactoring.

### Live-call site

[`core/brain/brain_loop.py:900`](../../../core/brain/brain_loop.py#L900):

```python
if recovery_seed is None and not _should_run_jarvis_loop(user_text):
    return _empty()
```

Reads: *"if this is a fresh user turn AND the JARVIS classifier says don't
run the loop, return empty."* The gate exits `run_brain_loop` early; no
dispatcher work happens beyond it.

### Replacement target

This single line at 900 is the replacement target. Per Codex pass-1 Batch 8 +
ADR 0047 D1 (full replacement, not wrap): the wiring code replaces the gate
with the Layer 0 → Layer 2 → Layer 1 pipeline. The JARVIS regexes
(`_CONVERSATIONAL_RE`, `_SYSTEM_NOUN_RE`, `_CONVERSATIONAL_SHAPE_RE`,
`_is_conversational_intent`, `_should_run_jarvis_loop`) become Layer 0
*evidence* (signals fed into spec construction) rather than a downstream
gate.

### Dead-copy cleanup

The `skills/telegram_voice.py:463` dead copy should be removed as part of the
wiring seam OR queued as a small cleanup commit. Leaving it risks future
agents touching the dead copy thinking it's load-bearing. Not blocking the
wiring; should be flagged.

### Recovery seed bypass preserved

The existing `recovery_seed is None and ...` clause must be preserved in the
wiring replacement. When `recovery_seed` is set (Session 11z Part 3
autonomous pivot fix), the gate is bypassed — the "user message" is
synthetic and the loop is running in recovery mode. The dispatcher pipeline
must not run for recovery contexts; recovery uses its own framing
(`_run_jarvis_recovery()`).

---

## 3. External-Source Handling Decision

Grep witness: `rg -n "web_search\|fetch_url" core/brain/ daemon/ skills/`
returns no hits in the core ingress paths. External fetch happens *inside*
the JARVIS loop's tool-execution path (TOOL_CALL actions like
`web_search`, `fetch_url`).

### The three options (from yesterday's framing)

- **(a)** External fetch as a sibling component to Layer 1, dispatched in parallel by the wiring layer.
- **(b)** External fetch wired directly into brain_loop after Layer 1 completes.
- **(c)** Defer external-source consumption from this seam; emit-and-ignore for now; queue as next seam.

### Decision: (c) — defer

**Rationale:**

- Layer 1's substrate-only scope is canon-bound. Tangling external fetch into the wiring seam violates that scope.
- Existing JARVIS tool-execution path already handles `web_search` / `fetch_url`. Until the dispatcher's wiring proves out on substrate-only routing, the JARVIS path can continue to handle external fetches as it does today — composition spec emits `external_sources` but the wiring layer leaves them unconsumed for v1.
- (c) is the most discipline-conservative. It produces a smaller wiring seam, easier to validate, with the external-source consumption deferred as its own slice that can be designed without wiring-commit pressure.
- (a) would introduce a new code surface (sibling external-fetch component) during the wiring seam — exactly the kind of architectural decision that should not be improvised under wiring pressure.

### Implication

For v1 wiring: Layer 0 emits `CompositionSpec` with `external_sources` populated when relevant; Layer 1 fans out only over `substrate_sources`; the existing JARVIS tool-execution path (called only when `_should_run_jarvis_loop`'s replacement decides tools are needed) handles external fetches as it does today.

Once observation proves Layer 0/1/2 are reliable, a follow-up slice introduces a real `external_fetch_dispatcher` component that consumes `CompositionSpec.external_sources` per the v1.3 closed error-class taxonomy. That slice has its own brief.

### Reserved sources discipline preserved

`LIVED_GRAPH`, `WEB_FAST_TURNS`, `FRONTIER_CONSULT` remain reserved per the
inventory module's `RESERVED_SOURCES` (line 26 of
`core/dispatcher/inventory.py`). The wiring does not change this; reserved
sources never execute regardless of which path takes them.

---

## 4. Fallback Flag Spec

### Mechanism

- **Env var:** `MAEZ_DISPATCHER_ENABLED`
- **Default value:** `0` (disabled by default for the first observation window)
- **Truthy values:** `1`, `true`, `True`, `yes` (case-insensitive)
- **Read at:** `run_brain_loop` entry, before the JARVIS gate (or its replacement) is consulted.
- **Effect when enabled:** Layer 0 → Layer 2 → Layer 1 pipeline runs in place of `_should_run_jarvis_loop`.
- **Effect when disabled:** existing `_should_run_jarvis_loop` gate runs (current behavior).

### Direction of the flag

Opt-in (default disabled) is more conservative for a seam that changes live
reply behavior. The first observation window runs with the flag enabled
explicitly by the operator; once the dispatcher proves reliable under real
traffic, a follow-up commit flips the default to enabled and the flag
becomes `MAEZ_DISPATCHER_DISABLED=1` opt-out.

### Reversibility discipline

The flag is the *single reversibility mechanism*. No alternative kill-switch
should be introduced — multiple kill-switches dilute the witness of which
one was used. One flag, one mechanism, witnessable in the cognition log
(see §5).

### Recovery-seed contexts

The flag is consulted only for fresh user turns (`recovery_seed is None`).
Recovery contexts bypass both the JARVIS gate and the dispatcher pipeline,
as today.

---

## 5. Telemetry Shape

Existing telemetry: `core/brain/brain_loop.py:142` declares
`logger = logging.getLogger(__name__)`. Existing log destinations:
`logs/cognition.log` and `logs/actions.log` (verified via `ls logs/`).

### Telemetry emissions

The wiring seam emits the following structured log records via the existing
`logger` surface (level `INFO` unless otherwise noted):

| Event | Fields | Purpose |
|---|---|---|
| `dispatcher_path_entry` | `surface`, `bond_id`, `chat_id`, `flag_state` (enabled/disabled), `recovery_seed_present` | One per `run_brain_loop` call; witnesses which path ran |
| `dispatcher_layer0_emit` | `surface`, `bond_id`, `composition_hint`, `provenance_framing`, `inventory_witness`, `substrate_source_count`, `external_source_count`, `elapsed_ms` | One per Layer 0 emission; D13 budget enforcement watches `elapsed_ms` |
| `dispatcher_layer0_budget_breach` (level `WARNING`) | `surface`, `elapsed_ms`, `budget_ms`, `cold_or_warm` | Emitted when Layer 0 exceeds D13 budget |
| `dispatcher_layer2_repair` | `surface`, `bond_id`, `result` (`unchanged`/`repaired`/`refused`), `refusal_reason` if refused | One per Layer 2 invocation on detected repair shape |
| `dispatcher_layer1_branch` | `surface`, `source`, `outcome` (`rows`/`empty_with_reason`/`timeout`/`error`/`reserved_skip`), `row_count`, `elapsed_ms` | One per Layer 1 branch result |
| `dispatcher_layer1_fanout` | `surface`, `fanout_generation_id`, `branch_count`, `seal_state` (`clean`/`partial_failure`/`global_timeout`), `total_elapsed_ms` | One per Layer 1 aggregate; witnesses seal identity |
| `dispatcher_path_exit` | `surface`, `bond_id`, `chat_id`, `path_taken` (`dispatcher`/`jarvis_fallback`/`recovery_seed`), `total_elapsed_ms` | One per `run_brain_loop` call; mirrors entry record |

### Emission target

`logs/cognition.log` via existing `logger.info(...)` / `logger.warning(...)`
calls. No new log file. Format consistent with existing `brain_loop`
emissions (key-value pairs via `%s`-style positional args, matching the
established pattern at lines 1149, 1176, 1292, 1387).

### What telemetry does NOT do

- Does not write to `actions.log` (that's tool-execution territory).
- Does not write to a new dispatcher-specific log file (one log surface,
  consistent with existing brain_loop emissions).
- Does not emit raw owner text (privacy discipline; bond_id and chat_id only).
- Does not emit composition spec contents beyond the named fields (the spec
  is read-time substrate; raw spec dumps could carry private content).

### D13 budget enforcement

`dispatcher_layer0_budget_breach` is the witness for D13 violations.
Per-emission `elapsed_ms` is captured with `time.monotonic()` deltas around
each layer's invocation. Budget thresholds (50ms warm / 150ms cold) come
from D13; "warm" vs "cold" detected by inventory cache state.

---

## 6. Probe Plan

### Natural-text probe corpus

Drawn from Finding 19's runtime evidence and v1.4's R#1a witnessed-turn
discipline:

| # | Probe | Expected dispatcher behavior |
|---|---|---|
| 1 | `Check Reddit then` | Layer 0 emits hybrid spec with `REDDIT_SOURCE`; Layer 1 fans out to Reddit substrate; renderer produces seam-marked output |
| 2 | `Just let me know what's going on in Reddit in localllama` | Same as #1; r/LocalLLaMA-tagged rows surfaced |
| 3 | `What's going on on Reddit?` | Same as #1 |
| 4 | `You have access to Reddit data` | Layer 0 detects content-anchor; emits substrate-only or hybrid spec; does NOT route to JARVIS web_search |
| 5 | `What were we talking about last evening?` | Layer 0 emits `TELEGRAM_TEMPORAL` substrate; Layer 1 fans out; temporal recall surfaced |
| 6 | `Search r/LocalLLaMA right now` | Layer 0 detects explicit-fetch signal; emits `FRESH_ONLY` framing; external fetch routed via existing JARVIS path |
| 7 | `Really?` (after a prior temporal recall question) | Layer 2 detects repair shape; inherits prior temporal spec; Layer 1 runs against inherited spec |
| 8 | `Are you sure?` (after a non-temporal question) | Layer 2 detects repair shape; finds no temporal prior; refuses with `NO_PRIOR_SPEC` OR returns unchanged spec depending on definition |

### Baseline run (dispatcher disabled)

1. Set `MAEZ_DISPATCHER_ENABLED=0` (or unset).
2. Restart `maez.service`.
3. Send probes 1-8 via Telegram or daemon HTTP endpoint.
4. Capture `logs/cognition.log` and `logs/actions.log` during the run.
5. Expected: probes 1-4 route to JARVIS → external `web_search` (reproducing Finding 19's substrate-bypass).

### After run (dispatcher enabled)

1. Set `MAEZ_DISPATCHER_ENABLED=1`.
2. Restart `maez.service`.
3. Send the same probes 1-8.
4. Capture `logs/cognition.log` and `logs/actions.log` during the run.
5. Expected: probes 1-5 emit `dispatcher_layer0_emit` records with `REDDIT_SOURCE` / `TELEGRAM_TEMPORAL` in substrate_sources; Layer 1 fan-out logs show Reddit/Telegram substrate consultation; renderer produces seam-marked output.

### Witness diff

The closure of Finding 19 is witnessable as a diff:

- **Baseline:** `actions.log` shows `web_search` / `fetch_url` for probes 1-4; no Reddit substrate consultation.
- **After:** `cognition.log` shows `dispatcher_layer1_branch` for `REDDIT_SOURCE` with row_count > 0; `actions.log` shows no `web_search` for probes 1-4.

The substrate witness governs claim: if the after-run still shows Reddit substrate bypass, the wiring did not close Finding 19; if it shows Reddit substrate consultation, the closure is mechanically verifiable.

### Probe corpus location

Probe phrases recorded at: `docs/slices/recall-axis-dispatcher/probes/witnessed_turn_corpus.txt` (created at probe-plan implementation time). Each probe phrase committed durably so future regression tests can replay them.

---

## Wiring Code Translation Targets

Each section above translates into one or more wiring-code commits:

1. **§1 Ingress wiring:** add `surface: str` kwarg to `run_brain_loop`; each of the three ingresses (daemon/maez_daemon.py:6991, skills/telegram_voice.py:3084, skills/surface/maez_adapter.py:400) passes its label explicitly.
2. **§2 Gate replacement:** at `core/brain/brain_loop.py:900`, replace `_should_run_jarvis_loop(user_text)` check with the dispatcher pipeline (Layer 0 → Layer 2 → Layer 1) when flag enabled; preserve `recovery_seed` bypass; keep JARVIS regexes as Layer 0 *evidence* (not gate).
3. **§3 External-source deferral:** confirmed; no code change in this seam beyond emitting `external_sources` in the spec.
4. **§4 Flag implementation:** read `MAEZ_DISPATCHER_ENABLED` env var at `run_brain_loop` entry; branch to dispatcher or JARVIS gate based on flag state.
5. **§5 Telemetry:** emit the seven event records via `logger.info` / `logger.warning` at the named call sites.
6. **§6 Probe corpus + observation:** commit the probe corpus to disk; run baseline before wiring lands; run after-run after wiring lands; record witness diff.

The wiring-code commit (or commit chain) should reference this brief and
honor each section's decision. Mid-commit decisions about which ingress to
wire, which gate to replace, how external-sources flow, what flag to use,
how telemetry emits, or which probes to run — those are out of scope for
the wiring code. The brief decided them.

---

## Dead-Code Cleanup (queued, not blocking)

`skills/telegram_voice.py:463` defines a `_should_run_jarvis_loop` function
that has zero callers in the file. It's leftover from earlier refactoring.
Remove as a small commit either alongside the wiring seam or after, but
not via the wiring commit itself (different responsibility).

---

## Discipline Reminders

- **Canon-governs-canon (ADR 0044):** every wiring claim must match the substrate. The brief is written from live grep/read evidence; the wiring code must honor the brief's decisions.
- **Seam-vs-slice (memory canon):** the wiring code is a capability seam that changes live reply behavior. Cooling-off applies between this brief and the wiring code; the brief is planning, the wiring is implementation. Same-day defensible only if the wiring closes a review-named trapdoor narrowly — this brief is the review surface.
- **Reversibility (operator-judgment):** the fallback flag is the single mechanism. Don't introduce alternatives.
- **Floor accounting (memory canon):** the wiring commit must report broad-suite floor by exact method-level name. Existing 2 known failures expected; any new failures must be flagged as regressions, not silently absorbed.

---

*Wiring brief v1 — 2026-05-27. Author: Claude under Rohit dispatch. Live grep/read evidence anchored at brief-authoring time:*
- *`rg -n "_should_run_jarvis_loop" core/ daemon/ skills/`*
- *`rg -n "run_brain_loop\(" core/ daemon/ skills/`*
- *`rg -n "web_search|fetch_url" core/brain/ daemon/ skills/`*
- *`sed -n '870,910p' core/brain/brain_loop.py`*
- *`sed -n '460,485p' skills/telegram_voice.py`*
- *`sed -n '6985,6998p' daemon/maez_daemon.py`*
- *`sed -n '390,410p' skills/surface/maez_adapter.py`*

*Next: this brief commits; cooling-off applies before the wiring code; the
wiring commit (or commit chain) honors the brief's decisions mechanically.*
