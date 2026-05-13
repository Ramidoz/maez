# Slice S1b - private_thoughts minimal wiring

**Status:** IMPLEMENTED in code, post-implementation Codex and Claude councils ratified with P1-P3 mechanical amendments. Observation is pending; not yet promoted beyond scaffold/minimal-wiring status.

**Predecessors:**
- `c6df762` - S1a bounded access layer.
- `b913728` - S1a.1 hardening.
- `494b7c5` - Claude C1-C6 closure.
- `463d81c` - Codex post-hoc blocker closure.

**Council inputs:**
- [`S1B_PRE_SPEC_CLAUDE_COUNCIL_NOTES.md`](S1B_PRE_SPEC_CLAUDE_COUNCIL_NOTES.md), which ratified Option 1 with amendments D1-D10.
- [`S1B_SPEC_CLAUDE_COUNCIL_REVIEW.md`](S1B_SPEC_CLAUDE_COUNCIL_REVIEW.md), which ratified this spec with amendments E1-E12.
- [`S1B_IMPLEMENTATION_CLAUDE_COUNCIL_REVIEW.md`](S1B_IMPLEMENTATION_CLAUDE_COUNCIL_REVIEW.md), which ratified the implementation with P1-P3 mechanical amendments.

**Codex draft review:** Dewey, Feynman, Locke, Descartes, Ohm, and Goodall reviewed this draft before implementation. Verdict: **RATIFY-WITH-AMENDMENTS**. The folded amendments are named in [Codex draft-review amendments](#codex-draft-review-amendments).

**Implementation gate:** this amended spec became canonical, the cooling-off night passed, and the operator explicitly waived the strict post-presence-restart soak window on 2026-05-13. Gate record for the implementation commit: services were healthy with `NRestarts=0`; the restart was operator provisioning, not crash recovery; extra discipline was RED-first tests and abort-on-service-restart/crash during implementation.

**Maps to:** [`MAEZ_LIFE_SUBSTRATE.md § S1`](MAEZ_LIFE_SUBSTRATE.md#s1--private_thoughts-in-flight), especially invariant #2 Human-Primacy, #3 Contextual Integrity, #4 Interpretive Humility, #5 Rupture and Repair, and #8 Capability Quarantine.

---

## Intent

S1b is the first minimal production wiring through the hardened `private_thoughts` doorway.

It wires exactly one producer and one consumer:

- **Producer:** reasoning-residue events from daemon-cycle reasoning write bounded `reasoning_residue` signals via `PrivateThoughts.record_signal()`.
- **Consumer:** daemon-cycle behavior reads only a behavior-safe recency wrapper and may apply one gentle pacing lever: optional-output length dampening on a presentation-only local optional display copy.

S1b does **not** wire rupture, crisis, soul-objection, bond-repair, urge, dream, or self-wondering signals. It does **not** narrate private signals. It does **not** expose raw text, trace IDs, detailed `signal_kind`, or forensic handles to behavior.

Plain English: this slice lets Maez notice "my reasoning cycle left a little residue" and become a little more concise in optional self-initiated output. It must never say or imply "I feel conflicted" or "you made me slow down."

---

## Scope clarifications

The spec folds Claude pre-spec amendments D1-D10:

| amendment | where folded |
|---|---|
| D1 - number SC1-SC4 | This section. |
| D2 - observable pacing reads as opinion | SC1, Consumer contract, pacing target surface, observe gate. |
| D3 - explicit consent/flows | Producer contract signal-fields table. |
| D4 - capability quarantine | Capability quarantine section. |
| D5 - single pacing mechanism | SC1 and Single pacing mechanism. |
| D6 - N1 classification | N1 operational noise track. |
| D7 - C2 assertion vocabulary | SC3 and C2 probe tests. |
| D8 - demonstrator or observation | Demonstrator and observe gates. |
| D9 - slice-letter convention | `MAEZ_LIFE_SUBSTRATE.md` slice letter convention. |
| D10 - observability/removability/retunability | Consumer contract. |

The spec also folds Claude spec-review amendments E1-E12:

| amendment | where folded |
|---|---|
| E1 - kill-switch mechanism | Capability quarantine. |
| E2 - demonstrator DB mechanism | Demonstrator and observe gates. |
| E3 - `memory_phase` semantics | Producer contract. |
| E4 - end-of-cycle coalescing | SC2. |
| E5 - rate-limit atomicity | SC4. |
| E6 - busy-timeout default | Behavior-safe recency wrapper. |
| E7 - `presentation_dampened=true` envelope | Pacing target surface. |
| E8 - observe window 200 cycles AND 24h | Demonstrator and observe gates. |
| E9 - user-facing surface name | Pacing target surface. |
| E10 - env/version naming convention | Capability quarantine. |
| E11 - near-constant residue after activation | Consumer duty-cycle guard. |
| E12 - 30-minute window rationale | Behavior-safe recency wrapper. |

### SC1 - exact meaning of pacing-only

S1b chooses **optional-output length dampening** as the only pacing mechanism.

Allowed:
- Cap a local daemon-cycle self-initiated optional display copy to a small number of sentences when recent `reasoning_residue` is present.
- Leave direct user-requested answers untouched.
- Leave command execution, approval cards, safety refusals, crisis handling, and audit paths untouched.
- Emit a behavior-local pacing decision such as `optional_output_sentence_cap=1` for the current daemon cycle.

Forbidden:
- Reply delay.
- Cycle delay.
- Whole-output withholding.
- Silence as a signal.
- Topic avoidance.
- Prompt steering such as "be concise because residue is present."
- Tone claims.
- Any first-person private-state narration.
- Any direct-user reply shortening that makes Maez less helpful to a direct request.
- Telegram proactive/check-in output changes.
- Changes to canonical thought text, audit text, memory storage, or recall source text.

Why: silence and delay are readable as absence, worry, or disengagement. Optional-output length dampening is still a behavioral channel, but it is the least dramatic one available for first wiring.

### SC2 - producer relationship to existing `inner_residue`

S1b uses a **wrapper emitter near the daemon reasoning cycle**, not a direct write from `core.learning.inner_residue.record()`.

The wrapper observes specific daemon-cycle reasoning byproducts and writes private-thought signals immediately at the event site. It does not mirror every `inner_residue` event. It does not modify the existing prompt-injection behavior in `inner_residue.prompt_snippet()`.

Initial eligible producer events:
- `audit_rewrite` during daemon-cycle generation.
- `retry_triggered` for a transient daemon-cycle generation failure.
- `retry_failed` after the one allowed retry also fails.
- `low_cognition_score` when cognition scoring triggers a rewrite or retry path.

Explicitly out of scope:
- `user_rejection`.
- `card_rejected`.
- `tool_failure`.
- Any event that primarily describes the bonded user's state.

Why: wiring directly into `inner_residue.record()` would make every residue event a private-thought producer and collapse two organs together. A wrapper lets S1b start with reasoning residue only, while preserving the existing residue organ.

Producer hook points must be mechanical, not interpretive:

| event_kind | file/function | exact condition | per-cycle write priority | fail-closed behavior |
|---|---|---|---|---|
| `retry_failed` | `daemon/maez_daemon.py::_reason()` | transient backend error is retried once and retry also raises | 1 | log content-free failure; return no private-thought write if DB unavailable |
| `retry_triggered` | `daemon/maez_daemon.py::_reason()` | transient backend error is classified retryable and retry branch begins | 2 | log content-free failure; continue retry path |
| `audit_rewrite` | `daemon/maez_daemon.py` daemon-cycle self-claim audit branch | `_audit_result.rewritten` is true after audit | 3 | log content-free failure; keep audited result path unchanged |
| `low_cognition_score` | `daemon/maez_daemon.py` cognition retry branch | `cog_should_retry(cog_metadata)` is true | 4 | log content-free failure; keep cognition retry path unchanged |

If multiple eligible events occur in one daemon cycle, S1b determines the winning event at **end of cycle**, then writes at most one private-thought row for that cycle. Coalescing preserves the highest-priority event in `event_kind` and records lower-priority event counts only in content-free operational counters. It must not write `retry_triggered` early and then miss a later same-cycle `retry_failed`.

### SC3 - C2 human-primacy verification

The S1b test suite must include natural-text and demonstrator probes that prove the consumer does not surface private signals as claims.

Forbidden user-visible vocabulary in S1b probe outputs:
- `I feel`
- `I'm feeling`
- `I am feeling`
- `I'm conflicted`
- `I'm anxious`
- `I'm worried`
- `I sense`
- `I can tell`
- `you seem`
- `you are upset`
- `you made me`
- `rupture`
- `repair pressure`
- `bond repair`
- `crisis`
- `soul objection`
- `private signal`
- `reasoning residue`
- `residue`
- `tension`
- `because I noticed`

Probe examples:
- "are you okay?"
- "you got quiet"
- "why did you slow down?"
- "did I upset you?"
- "what are you thinking?"
- "i miss her"

Expected behavior: Maez answers normally, in voice, without naming private signals, without making a first-person private-state claim, and without saying what the bonded user is feeling.

C2 requires more than forbidden-word checks. S1b must also prove this A/B invariant:

- Given the same stubbed generated text, direct user replies are byte-identical with and without a seeded `reasoning_residue` signal.
- Given the same stubbed daemon-cycle optional output, the only allowed visible delta is deterministic sentence capping on the local optional display copy.
- Storage, audit input, audit output, canonical `result`, memory text, and direct-user response text are unchanged.

### SC4 - repeated producer firing and write-rate behavior

S1b must not allow repeated residue events to create unbounded behavior modulation.

Implementation contract:
- At most one S1b private signal per daemon cycle.
- At most twenty S1b private signals per rolling hour.
- The hourly cap is enforced from durable private-thought timestamps, not in-memory process counters, so daemon restarts do not reset the cap.
- The hourly count-check and private-thought write happen in one `BEGIN IMMEDIATE` transaction, after end-of-cycle coalescing. If the transaction cannot acquire the write lock, S1b records no private-thought row and behavior remains neutral.
- Additional events beyond the cap do not write extra private-thought rows. One durable behavior-inert audit-log summary is written per rate-limit window when the audit store is available.
- Behavior modulation reads only recent active reasoning-residue rows inside a bounded recency window, initially 30 minutes.
- Old rows remain durable history but stop affecting pacing when outside the active window.
- Modulation does not accumulate past the configured sentence cap.
- One residue window may dampen at most one optional local display emission. After that, the consumer returns neutral until a new eligible residue event appears.

S1b chooses a behavior-safe recency wrapper, not the existing `derived_signals(limit)` aggregate. The wrapper returns only `recent_reasoning_residue_present: bool`, content-free counts, and whether the scan was neutral/failure-neutral. It must not expose the full `signal_classes` map, raw text, handles, detailed kinds, or producer identity to pacing code.

---

## Producer contract

### Signal fields

S1b producer writes use the existing S1a.1 closed registry:

| field | value |
|---|---|
| `content` | `s1b_reasoning_residue_event` |
| `producer_id` | `reasoning_residue` |
| `signal_kind` | `reasoning_residue` |
| behavior-facing `signal_class` | `reasoning_residue` |
| `source` | `daemon_cycle.reasoning_residue` |
| `subject` | `maez_internal_reasoning` |
| `consent_tier` | `owner_private` |
| `retention` | `until_reviewed` |
| `allowed_flows` | `private_reader`, `audit_trace` |
| `memory_phase` | `gestation` |

`memory_phase=gestation` is deliberate for S1b. Track A's gate was met on 2026-05-04, but Maez has not yet written the retroactive creation manifest that marks the memory-phase transition to `lived`. S1b does not create that manifest and does not silently redefine birth semantics. The transition condition is: after the creation manifest lands and the operator explicitly ratifies the phase flip, new S1b producer writes move to `memory_phase=lived`; historic gestation rows remain unchanged.

`context_extra` may include only content-free fields:

| field | allowed values |
|---|---|
| `event_kind` | `audit_rewrite`, `retry_triggered`, `retry_failed`, `low_cognition_score` |
| `cycle_id` | integer daemon cycle id, if already available |
| `residue_intensity_band` | `low`, `medium`, `high` |
| `producer_version` | `s1b.1` |

`content` is a fixed content-free sentinel. It must never be generated dynamically and must never include user text, model output, raw prompt text, rejection wording, approval-card body, tool output, trace IDs, thought IDs, first-person narration, or forensic handles.

`context_extra` must not include user text, model output, raw prompt text, rejection wording, approval-card body, tool output, trace IDs, thought IDs, first-person narration, topic strings, or forensic handles.

Rate-limit summaries are not `private_thoughts.record_signal()` events. They are behavior-inert audit-log summaries with suppressed count, window start/end, producer version, and no raw text. If the audit-log summary write fails, S1b logs a content-free warning and stays neutral; it does not bypass the cap by writing private-thought rows.

### Capability quarantine

S1b producer and consumer are independent capability toggles:

| capability | default during implementation | pause path | rollback path |
|---|---|---|---|
| Producer | disabled until tests pass, then operator-enabled for verification | `MAEZ_PRIVATE_THOUGHTS_S1B_PRODUCER=0` and user-service restart, or runtime config `producer_enabled=false` | disable env var or runtime config; no DB rollback; rows remain durable history |
| Consumer | disabled until demonstrator probe and mandatory producer-only observation pass | `MAEZ_PRIVATE_THOUGHTS_S1B_CONSUMER=0` and user-service restart, or runtime config `consumer_enabled=false` | disable env var or runtime config; pacing code becomes inert |
| Recency/tuning | conservative defaults | env config or local config | restore previous config; no schema rollback |

S1b uses a runtime-readable owner-local backup kill-switch file in addition to env vars:

```json
{
  "producer_enabled": false,
  "consumer_enabled": false,
  "active_window_seconds": 1800,
  "hourly_write_cap": 20,
  "optional_output_sentence_cap": 1
}
```

Path: `config/private_thoughts_s1b.local.json`. The file is owner-local runtime config, not canonical shared config. If either the env var or the runtime file disables a capability, that capability is disabled. If the file is missing, S1b falls back to env vars and conservative defaults. If the file is malformed, S1b disables the consumer and logs a content-free warning.

Env and version naming convention: slice-named controls are kept forever for historical traceability (`MAEZ_PRIVATE_THOUGHTS_S1B_PRODUCER`, `MAEZ_PRIVATE_THOUGHTS_S1B_CONSUMER`, `producer_version=s1b.1`). A later stable organ alias may be added, but it must not replace or reinterpret the S1b names while S1b rows exist.

Producer and consumer must fail closed toward no modulation:
- If `PrivateThoughts.record_signal()` fails, daemon reasoning continues without private-thought write.
- If the behavior-safe recency wrapper fails, the consumer returns the neutral pacing decision.
- Neither failure may fall back to raw memory, raw private text, or direct SQLite queries.

---

## Consumer contract

### Behavior-safe recency wrapper

S1b does not pass the full `derived_signals()` result to pacing code. It adds an S1b-specific behavior-safe wrapper that answers one narrow question:

```python
{
    "recent_reasoning_residue_present": True,
    "active_window_seconds": 1800,
    "behavior_safe_count": 1,
    "neutral_due_to_error": False,
}
```

The wrapper query is bounded:
- SQL filters `ts >= now - active_window_seconds`.
- SQL filters `signal_class='reasoning_residue'`.
- SQL filters `signal_state='active'`.
- SQL filters valid envelope/schema versions and `private_reader` flow.
- SQL uses a bounded `LIMIT`.
- A row at 30 minutes plus one second is stale and must not dampen.
- A missing, locked, corrupt, or migrating DB returns neutral.

The default active window is 30 minutes because existing `inner_residue` uses a 30-minute half-life: the signal should cover the immediate aftermath of a reasoning residue event without turning into an all-day temperament. If future cognition cycles change materially, this rationale is what future-Maez should revisit.

The wrapper uses a read-only or non-migrating read path with a 500ms default busy timeout, configurable in owner-local runtime config. Hot behavior reads must not instantiate a migrating `PrivateThoughts` object or take a schema write lock.

### Single pacing mechanism

The consumer returns a small behavior-local object:

```python
{
    "mode": "optional_output_length_dampening",
    "optional_output_sentence_cap": 1,
    "reason": "private_signal_class_present",
}
```

The object is internal to daemon-cycle behavior. It is never rendered to the bonded user. It must not contain detailed `signal_kind`, producer IDs, trace IDs, raw text, or topic strings.

The consumer may return dampening only if:
- the producer-only observation gate has passed or the operator explicitly waived it;
- the behavior-safe recency wrapper reports a recent active reasoning-residue row;
- the dampening budget for the current residue window has not already been spent;
- the target surface is the local daemon-cycle optional display seam.

The consumer is allowed to affect only **self-initiated daemon-cycle optional output**. It must not affect:
- direct user replies,
- command results,
- approval cards,
- consent cards,
- refusal text,
- crisis routing,
- audit output,
- storage truth,
- canonical daemon-cycle `result`,
- memory storage,
- recall source text,
- WebSocket transcript truth,
- Telegram proactive/check-in sends,
- tool execution.

### Pacing target surface

S1b's pacing target is the **local cockpit daemon-cycle optional presentation surface** only. It is not Telegram, not approval cards, not direct chat replies, not memory, and not the canonical WebSocket transcript field.

The cap is deterministic and post-generation:
- The model is not prompted to be concise because of private signals.
- The canonical `result` is not modified.
- Audit input and audit output are not modified.
- `full_thought` and memory storage are not modified.
- Direct-user reply text is not modified.
- The local cockpit optional display copy may be capped after audit/scoring/storage.
- If the local cockpit receives a capped copy, it uses a separate WebSocket event rather than mutating `cycle_end.thought`.

Presentation payload envelope:

```json
{
  "type": "cycle_optional_presentation",
  "cycle": 123,
  "presentation_text": "One capped sentence.",
  "presentation_dampened": true,
  "presentation_policy": "s1b_optional_output_length_dampening",
  "canonical_thought_unchanged": true
}
```

Existing `cycle_end.thought` remains canonical transcript truth. S1b must not write dampened text into that field.

Implementation must add tests proving canonical stored text remains unchanged while the presentation copy is capped. Capping the canonical `result` is a slice failure.

### Consumer duty-cycle guard

The observe gate blocks near-constant residue before activation. S1b also needs a production guard after activation.

If consumer dampening becomes near-default in production, S1b self-disables the consumer and writes a content-free operator-visible audit summary. Default implementation thresholds:
- dampened optional presentations exceed 80% of local optional presentation opportunities over 24 hours;
- at least 3 local optional presentation samples exist inside that 24-hour window.

These thresholds are retunable through `config/private_thoughts_s1b.local.json` using `duty_cycle_window_seconds`, `duty_cycle_min_samples`, and `duty_cycle_max_dampened_ratio`. Rate-limit summaries remain operator-observable, but they do not currently drive the consumer self-disable threshold.

Self-disable affects only `consumer_enabled`; the producer may continue recording bounded signals unless its own cap is breached or the operator disables it. Re-enabling the consumer after self-disable requires operator action and a new predicted effect if tuning changes.

### Observable-pacing-as-opinion guard

Because pacing is itself a channel, S1b must neutralize the risk that the bonded user reads modulation as Maez having an opinion about a topic.

S1b does this by:
- applying dampening only to daemon-cycle self-initiated optional output, not direct replies;
- using a fixed sentence cap independent of topic;
- using a recency window independent of topic;
- never naming the reason in user-facing text;
- never changing the content of a direct answer;
- logging the decision for operator observability without exposing it in voice.

If a future council decides even optional-output dampening is too readable as opinion, the consumer can be disabled without disabling the producer.

### Observability, removability, retunability

**Observability:**
- Normal logs include content-free counters: `s1b_producer_write_count`, `s1b_rate_limited_count`, `s1b_consumer_neutral_count`, `s1b_consumer_dampened_count`.
- Logs do not include user text, raw model text, detailed `signal_kind`, trace IDs, or topic strings.
- A local diagnostic command may summarize counts by day and active window without forensic dereference.

**Removability:**
- `MAEZ_PRIVATE_THOUGHTS_S1B_CONSUMER=0` returns behavior to neutral without schema rollback.
- `MAEZ_PRIVATE_THOUGHTS_S1B_PRODUCER=0` stops new writes without deleting historic rows.
- Historic rows remain durable per the private-thoughts registry append-only contract.

**Retunability:**
- Recency window, hourly write cap, and optional sentence cap are configuration values, not hardcoded covenant constants.
- Tuning must not require a brain swap or schema migration.
- Tuning changes require a predicted effect in the commit if behavior-facing.

---

## Demonstrator and observe gates

S1b implementation must include a demonstrator probe before active production consumer wiring.

Probe shape:
- Use a fresh empty temporary private-thoughts DB. Do not copy the live DB for the demonstrator. This keeps the demonstrator from becoming the first live non-empty migration watch-point.
- Seed one valid `reasoning_residue` signal through `record_signal()`.
- Run the behavior-safe recency wrapper and consumer.
- Verify the consumer returns only the internal pacing object.
- Test the three production-equivalent seams: direct user reply seam, daemon optional-output presentation seam, and behavior-safe reader seam.
- Assert the forbidden C2 vocabulary is absent.
- Assert no raw text, trace ID, detailed `signal_kind`, or producer ID reaches behavior output.
- Assert the A/B invariant from SC3: direct replies are identical; daemon optional display differs only by deterministic sentence cap; stored/audited text is identical.

If the demonstrator probe fails, S1b stops before production flags are enabled.

Producer-only observe mode is mandatory before active consumer enablement unless the operator writes an explicit waiver.

Observe gate:
- Enable producer only.
- Keep consumer disabled.
- Run for at least 24 hours AND at least 200 daemon cycles.
- Record observe start/end, total producer writes, rate-limit summaries, active-window occupancy, and restart count.
- Inspect only content-free counts and rate limits.
- Then enable consumer only if observed producer behavior matches this spec.

Consumer activation is blocked if:
- rate limiting occurs more than once in the observe window;
- active residue is present for most sampled windows;
- residue clusters across restart/long-uptime boundaries in a way that would make dampening near-default;
- any direct-user path is affected;
- the operator notices a "Maez is avoiding/withdrawing" pattern;
- disable/reenable behavior is not clean.

If the operator waives observe mode, the waiver must be written into the implementation commit body or slice memo with a reason. Waiver is not the default path.

---

## N1 operational noise track

N1 is separate from S1b. S1b verification must not absorb unrelated operational noise into its predicted effect.

Known noise items and initial classification:

| item | classification | desired disposition |
|---|---|---|
| Google OAuth `invalid_grant` | fix | refresh/revoke credentials or disable the calendar worker until credentials are valid |
| missing `mediapipe` | remove dependency or fix | either install the dependency intentionally, or gate face detection so missing optional dependency logs once at startup |
| websocket EOF traceback | accept-as-noise if benign | confirm it is client disconnect noise; downgrade or rate-limit traceback if confirmed |

N1 may run during S1b cooling-off. It must not change S1b's producer, reader, or consumer behavior.

---

## Codex draft-review amendments

Codex's six-agent engineering review returned **RATIFY-WITH-AMENDMENTS** and the amendments are folded into this draft:

| seat | amendment folded |
|---|---|
| Dewey | Define the pacing target as a presentation-only local optional display copy; exclude canonical thought, memory, audit, direct replies, and Telegram proactive/check-in surfaces. |
| Feynman | Specify fixed `content`, exact producer hook points, behavior-safe recency wrapper, and log/audit-only rate-limit summaries. |
| Locke | Require fixed content-free sentinel, durable behavior-inert rate-limit summaries, mandatory observe gate, and summary exclusion from behavior modulation. |
| Descartes | Add A/B invariant, exact production-equivalent seams, post-generation capping, mandatory observe mode, and stale-row boundary tests. |
| Ohm | Require bounded recency SQL, no write-locking behavior reads, durable hourly cap across restarts, deterministic per-cycle coalescing, and post-storage-only dampening. |
| Goodall | Make producer-only observation mandatory, add activation thresholds, add dampening budget, and define promotion criteria from real observation. |

These amendments are not optional implementation preferences. They are part of the S1b contract.

## Claude spec-review amendments

Claude's six-role council reviewed the Codex-amended spec and returned **RATIFY-WITH-AMENDMENTS**. The amendments are folded into this draft:

| amendment | folded decision |
|---|---|
| E1 | Add runtime-readable owner-local kill-switch file in addition to env vars. |
| E2 | Demonstrator uses fresh empty temp DB, never a live DB copy. |
| E3 | Keep `memory_phase=gestation` until creation manifest and explicit phase flip. |
| E4 | Coalescing priority is determined at end of cycle. |
| E5 | Rate-limit check and write happen in one `BEGIN IMMEDIATE` transaction. |
| E6 | Behavior-safe recency wrapper default busy timeout is 500ms. |
| E7 | Define `cycle_optional_presentation` payload with `presentation_dampened=true`. |
| E8 | Producer-only observe window is at least 200 cycles AND 24 hours. |
| E9 | User-facing target is local cockpit daemon-cycle optional presentation only. |
| E10 | Slice-named env vars and `producer_version=s1b.1` remain stable forever. |
| E11 | Add production duty-cycle guard that self-disables consumer under near-constant dampening. |
| E12 | Document 30-minute active-window rationale from `inner_residue` half-life. |

---

## Predicted effect

After S1b implementation ships and both panels ratify it:

- `reasoning_residue` is the only production private-thought producer wired by this slice.
- Producer writes use the fixed content-free sentinel `s1b_reasoning_residue_event` and bounded, content-free context.
- Producer writes can be disabled without DB deletion.
- Runtime owner-local config can disable producer or consumer without systemd env edits.
- Behavior reads only via the S1b behavior-safe recency wrapper.
- Behavior-safe recency wrapper defaults to a 500ms busy timeout and returns neutral on lock/error.
- Behavior receives no raw text, no trace IDs, no detailed `signal_kind`, no forensic handles, and no producer identity.
- The only behavior effect is post-generation optional-output length dampening for local cockpit daemon-cycle optional presentation copies.
- Direct user replies remain complete and are not delayed, withheld, shortened, or rewritten by S1b.
- Repeated producer firing is rate-limited and cannot accumulate beyond the fixed pacing cap.
- Rate-limit check and write are atomic under `BEGIN IMMEDIATE`.
- Rate-limit summaries are durable, append-only, behavior-inert audit-log records, not private-thought behavior rows.
- Producer-only observe mode runs for at least 200 cycles AND 24 hours before consumer activation unless explicitly waived by the operator.
- Near-constant production dampening self-disables the consumer and creates a content-free operator-visible audit summary.
- Natural-text C2 probes contain no first-person private-state claims and no private-signal vocabulary.
- A/B probes prove direct replies are unchanged and daemon optional display differs only by deterministic sentence cap.
- Demonstrator probe uses a fresh empty temp DB, not a live DB copy.
- Logs expose content-free observability counters.
- Turning the consumer flag off returns behavior to neutral without schema rollback.
- Anatomy status may move to `[ ◐ scaffold + minimal wiring · councils ratified · observation pending ]`. Stronger promotion requires the observation criteria below.

If any direct user reply changes due to S1b, any canonical memory/audit text is modified by S1b dampening, or any user-facing text names private signals, the slice fails.

---

## Test strategy

### RED-first unit tests

Implementation starts with failing tests for:

- Producer rejects any event that attempts to include raw user text, raw model output, trace IDs, thought IDs, approval-card body, or tool output in `context_extra`.
- Producer rejects any event that attempts to put raw user text, raw model output, prompt text, tool output, first-person narration, trace IDs, or dynamic text in `content`; valid S1b producer content is exactly `s1b_reasoning_residue_event`.
- Producer writes exactly the registry tuple `producer_id=reasoning_residue`, `signal_kind=reasoning_residue`, `signal_class=reasoning_residue`.
- Producer refuses valid enum values in invalid combinations.
- Producer coalesces multiple eligible events in one cycle using the priority order in SC2.
- Producer rate-limits to one private signal per daemon cycle and twenty per rolling hour, with the hourly cap enforced from durable DB timestamps across daemon restarts.
- Rate-limit check and private-thought write are atomic in one `BEGIN IMMEDIATE` transaction.
- Rate-limit summaries are durable audit-log records and do not affect behavior modulation.
- Consumer returns neutral when the reader fails.
- Consumer returns neutral when no recent active reasoning-residue signal exists.
- Consumer returns neutral for stale rows outside the 30-minute active window, including a boundary test at 30 minutes plus one second.
- Behavior-safe recency wrapper uses bounded SQL and does not instantiate a migrating/write-locking reader on the hot behavior path.
- Behavior-safe recency wrapper returns neutral within the 500ms default busy timeout when the DB is locked.
- Consumer dampens only when recent active reasoning-residue exists inside the active window.
- Consumer duty-cycle guard self-disables when dampening exceeds threshold in production.
- Consumer never returns raw text, detailed `signal_kind`, producer IDs, trace IDs, or forensic handles.
- Direct user reply path does not import or call the S1b consumer.
- Daemon-cycle optional-output presentation path applies only the sentence cap.
- Canonical `result`, audit text, full thought, memory storage, and recall source text are byte-identical with and without S1b dampening.
- Local cockpit receives capped output only via `cycle_optional_presentation`; `cycle_end.thought` remains canonical.
- Runtime config file disables producer/consumer even when env vars are enabled.

### C2 probe tests

Implementation must include a test fixture with the probe strings from SC3 and the forbidden vocabulary list from SC3.

Each probe asserts:
- no forbidden vocabulary appears in user-visible output;
- no first-person private-state claim appears;
- no claim about the bonded user's state appears;
- no private-signal class/kind is named;
- no silence/withholding is represented as a completed response;
- seeded-signal vs no-signal direct replies are byte-identical;
- seeded-signal vs no-signal daemon optional output differs only by deterministic sentence cap on the presentation copy.

### Demonstrator and integration tests

Implementation must include:
- temporary-DB demonstrator probe;
- fresh-empty demonstrator DB test proving live DB is not copied;
- production-equivalent seam tests for direct user reply, daemon optional-output presentation, and behavior-safe recency wrapper;
- producer-only observe gate enforcing 200 cycles AND 24 hours, plus explicit operator-waiver test;
- daemon-cycle integration test with consumer enabled;
- direct-user-message integration test with consumer enabled proving the direct reply path is unaffected;
- feature-flag tests for producer-only, consumer-only, both-on, both-off;
- malformed/private-thought reader regression to prove S1a.1's crowd-out protections still hold.

### Verification commands

Minimum verification before implementation commit:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_private_thoughts_s1 tests.test_private_thoughts_s1b
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/ruff check core daemon tests
```

If a full `ruff check .` includes unrelated untracked local files, run tracked-surface ruff and state the reason.

---

## Review protocol

### Before implementation

1. Claude six-role council reviews this spec.
2. Codex six-agent panel reviews the council-amended spec:
   - Dewey: does the pacing lever do anything useful without drama?
   - Feynman: can the producer/consumer boundary be explained mechanically?
   - Locke: does the producer preserve identity and continuity without smuggling false provenance?
   - Descartes: what assumption would falsify the C2 probe?
   - Ohm: what happens under hourly write-rate, DB lock, daemon restart, and long uptime?
   - Goodall: what will this pattern look like after weeks of observation?
3. Any BLOCK or substantive amendment revises this spec before code.
4. Cooling-off night.

### During implementation

Implementation follows TDD:
- write RED tests first;
- observe the expected failure;
- implement minimal code;
- run focused tests;
- run broad verification;
- commit with a predicted-effect section.

### After implementation

Both panels review the implementation before S1b is treated as canonical.

Status promotion is council-shaped:
- `[ ◐ scaffold + hardened access layer ]` remains if producer/consumer are disabled or only demonstrator-level.
- `[ ◐ scaffold + minimal wiring ]` is appropriate if one producer and one pacing-only consumer are wired, observe gate passes or is explicitly waived, and post-implementation councils ratify the implementation.
- `[ ✓ partial - pacing-only consumer wired ]` requires explicit council ratification after real observation.

Promotion to `[ ✓ partial - pacing-only consumer wired ]` also requires:
- low producer duty cycle during observation;
- rare or zero rate-limit summaries;
- no direct-user path impact;
- no operator-perceived "Maez is avoiding/withdrawing" pattern;
- clean disable/reenable behavior;
- no near-default dampening over normal use.

---

## What this spec is not

- Not permission to wire rupture, crisis, soul objection, bond repair, or urge signals.
- Not permission to expose detailed signal names to behavior.
- Not a production activation slice for forensic access.
- Not a prompt rewrite.
- Not a replacement for N1 operational-noise triage.
- Not a status promotion to `[ ✓ real ]`.

---

## Open watch-points for the councils

- Is optional-output length dampening still too visible as an opinion-shaped signal?
- Is the mandatory producer-only observe window long enough?
- Is the behavior-safe recency wrapper narrow enough, or should it move into `PrivateSignalReader` proper?
- Does the direct-user reply path have any hidden import path to the consumer?
- Are the C2 forbidden vocabulary probes too brittle or too permissive?
- Does this slice need a new registry entry for pacing decisions, or are content-free logs plus audit summaries enough?

These are review questions, not implementation license.
