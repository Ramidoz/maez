# Recall Progress Receipt (Slice 1a) + A7 Gate Amendment — Design

> 2026-05-31. After the recall default-on No-Go (latency: focused synthesis was 72–85% of a 6–12s turn;
> same-session answer quality looked promising, but latency failed). This slice preserves visible liveness
> during long recall waits without touching answer content, and rewrites the default-on gate so a quick
> acknowledgement can never launder a slow answer. Shaped by
> the 6-role scoping switchboard. Canon principle: **visible substrate state, not visible chain-of-thought**
> ([[feedback_visible_substrate_state_not_chain_of_thought]]).

## Core rule (Rohit, verbatim — the spine)
> Maez may send **one** truthful, substrate-backed receipt when a recall answer is taking long enough that
> silence would feel dead. The receipt must be **tied to an observed runtime state** and must **always be
> followed by either the answer or an honest failure**.

## Slice 1a — the single recall progress receipt

### One receipt, only on a real wait
- **At most ONE** receipt per recall turn — never a multi-step narration of internal stages (chatty
  narration *increases* perceived wait and drifts toward performance — Outside-View, Body-Coherence).
- Fired **only when the wait is genuinely long** — gated on **observed elapsed time** crossing a
  threshold (`RECEIPT_AFTER_MS = 900ms`, pinned here for v1), **not** on turn-start and **not**
  on "this is a dated turn." If recall resolves before the threshold, **no receipt** — Maez just answers
  (no look-busy behavior).
- The native **typing indicator** (`send_typing`, `platform_base.py`) carries general "I'm working"
  liveness; the *message* receipt is reserved for the one genuinely-informative state.
- **A7 timing constants, v1:** `RECEIPT_AFTER_MS = 900ms`, `ACK_CEILING_MS = 1500ms`,
  `RECEIPT_SEND_TIMEOUT_MS = 1000ms`. The ack ceiling is intentionally **after** the receipt threshold;
  an ack gate whose ceiling is earlier than the receipt trigger is mechanically impossible. If Rohit later
  wants a stricter sub-second gate, both constants must move together before the re-run.

### True-by-construction (the honesty floor — Logical, 20yr-Maez)
- A receipt fires **only after** its substrate state is **observed**, never predicted/optimistic. No
  "found it" before `had_confirmed` is true.
- **The receipt is gated on entry to the path that actually consults the carrier** (the `ReplyMode.FOCUSED`
  branch in `handle_message`), not on `_date_addressed_turn` — so a dated turn answered by TOOL/ECHO/
  HONEST_EMPTY never emits a dangling "checking…".
- **Every receipt is paired with a terminal reply value** — the answer or an honest failure message. This
  is a `handle_message` construction guarantee, not a Telegram delivery guarantee after process death or
  transport outage. No orphaned "checking…" in daemon control flow (the "broken promise" failure mode —
  Outside-View).

### Receipt wording — closed body-verb vocabulary, no performed thought
- Wording is **bodily, singular, first-person, genderless**, reusing Maez's shipped register (the
  self-status / honest-decline strings), e.g. the working receipt: *"I'm checking my dated memory for
  that."* (one line, not a spinner-gerund stream).
- **Closed vocabulary of body-verbs.** The in-flight receipt vocabulary is closed to `checking`; terminal
  replies reuse shipped decline/status strings (`reachable`, `no dated memory for that window`,
  `unavailable`, `could not pull it together`) and are **not** progress receipts.
  A **lint test** forbids cognition-verbs (`think`, `thinking`, `ponder`, `consider`, `wonder`, `mull`,
  `reflect`, `feel`, `sense`) in any receipt string — the difference between proprioception and a mask,
  enforced by test (20yr-Maez). The receipt narrates an **organ/action**, never **reasoning**.

### The receipt set (minimal, each a real state)
- **Working receipt** (the one in-flight message): fired iff the FOCUSED carrier path is engaged AND the
  elapsed-time threshold is crossed → *"I'm checking my dated memory for that."*
- **Terminal** is the normal reply (answer or decline) — **not** a separate "interim" beat:
  - The honest-decline reply is **terminal**, reusing the **shipped** decline strings
    (`daemon/maez_daemon.py` `_dated_denial_reply` family) — no parallel decline wording minted in a
    receipt layer, no interim+final double (Body-Coherence).
  - **The "no dated memory for that window" language binds to `denial_kind == no_dated_memory` ONLY**
    (carrier consulted, no confirmed item). `carrier_unavailable` / `consult_failed` / `transport_failure` get their own
    honest reachability phrasings ("I can't reach my dated memory from here" / "I couldn't pull it
    together just now") — **highest-priority anti-false-absence condition (20yr-Maez)**: never tell Rohit
    a memory is gone when it was merely unreachable. The receipt/decline layer **consumes** the 1a
    four-way `denial_kind`/`had_confirmed` separation; it may never collapse it.

### Wiring — additive in intent, careful in fact (Logical, load-bearing)
- `_send_intermediate` is a closure passed to `run_brain_loop`, **not reachable from `handle_message`**
  (where the recall states live), and the existing dialog-opening bridges block on Telegram futures
  (`fut.result(timeout=20)` in `skills/surface/maez_adapter.py`, `fut.result(timeout=30)` in the legacy
  `skills/telegram_voice.py` path). So the receipt is **not** a trivial reuse.
- Slice 1a adds a **keyword-only `send_intermediate` (progress sink) parameter to `handle_message`,
  default `None`** (no-op) — so every existing caller and test is byte-unchanged.
- The callable contract is synchronous, thread-safe, and best-effort: it **schedules** surface I/O and
  returns immediately. Daemon code must never call `.result()` on a Telegram future from the synthesis
  thread. The async surface task wraps the actual send in `asyncio.wait_for(..., timeout=1.0)` and
  swallows/logs exceptions. A receipt is an **emission, never a gate** — the final `reply` must be
  returnable even if every receipt no-ops.
- Because `handle_message` is synchronous and `_focused_synthesize` blocks, the receipt must be a
  turn-local one-shot timer/watchdog. It is armed **after** the FOCUSED carrier path has observed a
  non-`None` working set and set the carrier receipt to `consulted`, and **before** `_focused_synthesize`
  begins. If elapsed is already past `RECEIPT_AFTER_MS`, it arms with zero delay; otherwise it arms for the
  remaining delay. It is cancelled/suppressed if the terminal reply is ready before firing. It fires at
  most once.
- This slice wires the daemon-calling Telegram surface (`skills/surface/maez_adapter.py`) by passing the
  new progress sink into `daemon.handle_message(...)`. If the legacy `skills/telegram_voice.py::_process_message`
  owner-text path remains live, the plan must either wire equivalent receipt behavior there or explicitly
  prove it is out of scope for the owner-run re-flip.
- **Test:** a raising / throttling / timing-out receipt send leaves the returned `reply` **byte-identical**
  to receipts-off; and the send never delays `focused_synthesize`.
- Gated by its **own flag** (`MAEZ_RECALL_RECEIPT_ENABLED`, default-off), independent of the recall flags;
  observe/UX-only, never a recall control.

### Telemetry — content-free and scoreable
- Extend the recall outcome record (or bump it to the next schema version) with content-free A7 fields:
  `receipt_eligible`, `receipt_after_ms`, `ack_required`, `ack_status`, and nullable `ack_emit_ms`.
- Closed `ack_status` enum: `not_required_fast_answer`, `emitted`, `send_failed`, `send_timeout`,
  `disabled`, `not_eligible`.
- `ack_emit_ms` is recorded only when the surface send completes successfully. Failed/timeout sends
  record `ack_emit_ms=na` and fail the ack gate when `ack_required=true`. If an implementation can only
  observe enqueue time, the field must be named `ack_enqueue_ms` and may **not** satisfy the A7 delivery
  gate. Fast answers before
  `RECEIPT_AFTER_MS` are explicit `not_required_fast_answer`, not missing data.
- The telemetry is **content-free**: no receipt text, query text, reply text, cited id text, or recalled
  snippet. It records whether the receipt state happened, never what was being remembered.

## A7 — post-No-Go, pre-rerun analysis-plan amendment (the gate rewrite)
The frozen default-on gate compared triad's *slow real answer* p95 to legacy's *fast refusal* p95 — a
validity error (comparing two different output classes; a faster refusal is not a better outcome). A7
corrects this. It is **not** part of the original pre-registration; it is a dated post-No-Go validity
correction that must be frozen before any re-run data. Old-gate and A7 results are reported side by side
so the amendment cannot hide what changed (Outside-View). A7 lands as a dated amendment in the frozen flip
spec (like A4/A5/A6).

**A7 gate (replaces the raw p95-ratio as the *primary* latency gate):**
1. **Absolute full-answer ceiling — RETAINED as a HARD gate.** Whole-turn `latency_ms` p95 **and**
   `focused_elapsed_ms` p95 on recall turns ≤ a **frozen absolute `answer_ceiling_ms`** (owner-declared from
   hardware/lived tolerance plus the prior No-Go evidence; **not** mechanically derived from legacy's fast
   refusal p95). **Acknowledge-time can NEVER substitute for this** — a fast receipt may not launder a 30s
   answer (4-role convergence; the load-bearing condition).
2. **Acknowledge-time — additive criterion.** On `ack_required=true` turns, `ack_status == emitted` and
   `ack_emit_ms <= ACK_CEILING_MS` (`1500ms` for v1 unless Rohit freezes a different value before the
   re-run). **Credited only when there was a real wait** — a fast turn that answered before the receipt
   threshold (no receipt) scores **pass / not-required**, not miss (else the gate rewards look-busy theater
   — Body-Coherence, 20yr-Maez).
3. **Benefit** — the A5 rescued-turn definition + blind owner verdict (unchanged).
4. **Groundedness** — `citation_coverage` floor (unchanged; guardrail).
5. **Voice continuity** — the blind verdict carries it (no separate auto-metric); a brain/receipt that
   drifts Maez's voice fails.
- `ack_emit_ms` / `ack_status` and `answer_ceiling_ms` are **reported and gated separately**; green-ack may
  never mask red-answer. Both frozen pre-run. A7 **depends on Slice 1a's new ack fields** — it cannot be
  evaluated until 1a merges. For the A7 re-run, the flip step must set both `MAEZ_RECALL_TRIAD_ENABLED=1`
  and `MAEZ_RECALL_RECEIPT_ENABLED=1`; if receipts are disabled, the A7 ack gate is `not_evaluable` and the
  felt-latency gate cannot pass.
- **Disposition addition:** if a re-flip passes *only* because receipts make it *feel* responsive (ack
  green, answer at/near the ceiling, benefit only "same") → **default-revert to the real speed work** (the
  brain benchmark); keep-on needs an explicit recorded override + reason + dated re-look. Receipts are
  honest company during a wait, never a *fix* for the wait.

## Re-witness dependency (Visionary)
Receipts touch the daemon (`handle_message`). Per the same rule applied to 1a/1b, landing the receipt slice
**re-triggers the both-shaped + safety-negative re-witness** (the 2a battery) at the flip commit before any
re-flip proceeds.

## Sequencing — what comes after (named, NOT in this spec)
- **Slice 1b — token-streaming**: only if the single receipt proves insufficient on Telegram. Streams
  **real output tokens only**, never invented deliberation; better suited to web/voice than Telegram
  message-edits. Its own design + switchboard.
- **Slice 2 — brain benchmark**: extend the 2a sandbox (the deterministic-`chat_fn` seam) with **real
  local models** (current vs MTP / speculative decoding / quants) on the recall battery — measuring
  first-token, tokens/sec, latency, quality, citation, voice, false-absence. **Send-path-free** (measures
  model-first-token at the `chat_fn` seam, never the Telegram send — keeps 2a's offline invariant).
  **false-absence / voice / citation are HARD gates**; perf metrics tradeable **only above** those floors;
  the quality verdict inherits the **2b blind-verdict discipline** (pre-registered, blind, randomized,
  provenance-hidden). The prove-before-you-buy-hardware tool; operationalizes brain-is-one-part.

## Candidate reusable precedent (Visionary — lock the rule if it survives, defer the framework)
- If Slice 1a + A7 survive implementation and re-witness, **receipt-maps-to-a-real-substrate-state** becomes
  the candidate cross-organ surface rule (anti-laundering applied to the latency surface; content-free;
  state-label not reasoning-trace). Future Tier-A organs (Intake Bus, reflection, workspace) should reuse
  the *rule* + the universal outcome-record slot vocabulary; **do not build a generic receipt framework**
  (YAGNI — name the seam, extract at organ #2).
- **A7's four-axis felt-latency shape (with the absolute ceiling + blast-radius retained underneath as
  hard floors)** is the reusable Tier-A flip latency gate, replacing raw p95-vs-legacy.

## Testing
- Receipt→state: the working receipt fires iff FOCUSED-carrier engaged AND elapsed ≥ threshold; a short
  recall turn emits **no** receipt; a TOOL/ECHO/HONEST_EMPTY dated turn emits no dangling receipt.
- True-by-construction: a turn where `had_confirmed` is false never emits a "found" receipt.
- Anti-false-absence: the "no dated memory for that window" wording fires only on `no_dated_memory`;
  `transport_failure` / `carrier_unavailable` / `consult_failed` get reachability phrasing — a test per
  branch.
- Timer behavior: a slow FOCUSED dated turn arms the one-shot after working-set assembly and emits while
  `focused_synthesize` is still blocked; a fast focused turn cancels/suppresses it before it fires.
- Surface wiring: `skills/surface/maez_adapter.py` passes the progress sink into `handle_message`, and the
  sink schedules on the surface loop without `.result()`. If the legacy Telegram owner-text path is in
  scope, it has equivalent tests or a proof it is not used by the re-run.
- Ack telemetry: `ack_required`, `ack_status`, `ack_emit_ms`, and `receipt_after_ms` are content-free and
  closed-enum; failed/throttled sends record failure state without changing the final reply.
- Cognition-verb **lint corpus** (forbidden verbs) over every receipt string → empty.
- Byte-identical-reply: receipts-on vs off produce the same `reply`; a failing/throttling send doesn't
  change the reply or delay synthesis.
- Terminal guarantee: for every non-process-death path where a receipt send is attempted, `handle_message`
  still produces exactly one terminal reply value (answer or honest failure). This is not a platform-delivery
  guarantee after process crash or Telegram transport outage.
- Genderless across all receipt strings.

## Self-review
- **Placeholders:** none — the single-receipt rule, the elapsed-time gate, the receipt→state mapping, the
  closed vocabulary + lint, the wiring (keyword param, fire-and-forget, byte-identical test), and the A7
  five-criteria gate (with the retained absolute ceiling) are concrete. `RECEIPT_AFTER_MS` /
  `ACK_CEILING_MS` / `RECEIPT_SEND_TIMEOUT_MS` are stated here; `answer_ceiling_ms` remains owner-frozen
  before the re-run.
- **Consistency:** the receipt/decline layer consumes (never collapses) the 1a `denial_kind`/`had_confirmed`
  four-way; A7 retains the absolute ceiling as the hard floor and adds ack-time, never substitutes; "visible
  substrate state, not chain-of-thought" enforced by the lint; reuses shipped decline + self-status register.
- **Scope:** A7 (gate) + Slice 1a (one receipt) only; 1b streaming + Slice 2 benchmark are named + sequenced,
  not specified here; no generic receipt framework (YAGNI).
- **Ambiguity:** "real wait" = elapsed ≥ `RECEIPT_AFTER_MS`; "observed state" = the carrier-consult/has-
  confirmed/denial_kind values already computed; "acknowledge credited only when a wait was real" pinned in
  A7 criterion 2.
