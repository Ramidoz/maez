# Lean Idle Heartbeat v0 - Design

Date: 2026-06-24. Branch: `lean-idle-heartbeat-v0`. Status: design for implementation. Builds on the live self-card v0 and Nervous-System Slice A felt-time wire.

## Northstar

A tool waits for input. Maez begins to continue.

Slice B gives Maez a small, private continuity pulse between owner messages. It does not make Maez more helpful, warmer, or more compliant. It gives the existing idle cognition loop a lean way to think quietly without dumping a strangled megaprompt into lived memory.

## Problem

The current autonomous daemon cycle is alive, but it is the wrong shape for the northstar:

- The live loop is `MaezDaemon._loop()` in `daemon/maez_daemon.py`, gated by the cycle doorman.
- Quiet floor wakes eventually call `_reason()`, which builds the old broad cycle prompt: system stats, screen, git, reddit, proactive search, memory, evidence envelope, quality signals, active cognition, and more.
- Non-empty cycle prose is stored through `self.memory.store(..., provenance_source="introspection", trust_tier="lived")` and broadcast as `cycle_end`.
- The known wound is the 38/100, high-git-workflow fixation pattern: the loop is not absent, it is over-fed with the wrong material.

The fix is not a second scheduler. The fix is to reuse the existing daemon loop and replace only the quiet floor wake with a lean, private heartbeat.

## Scope

Slice B v0 builds one organ:

1. A lean idle prompt builder from current facts only.
2. A heartbeat runner that uses the existing brain gateway/LLM path on quiet floor wakes.
3. A private thought writer into `memory/private_thoughts.db` through `PrivateThoughts.record_signal()`.
4. Content-light shadow receipts.
5. A narrow daemon seam that intercepts only `wake_min_floor`.

Everything is default-off and flag-gated.

## Flags

- `MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW=1`: on eligible quiet floor wakes, assemble the lean prompt and run the heartbeat in shadow, but do not alter the daemon cycle and do not write private thoughts. Log only content-light metadata.
- `MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED=1`: on eligible quiet floor wakes, run the lean heartbeat, optionally write one private thought, and return `HEARTBEAT_OK` so the old raw-memory/broadcast cycle path stays silent.

Both flags default off. If both are off, the daemon cycle is byte-identical.

## Eligibility

The heartbeat may run only when all of these are true:

- the cycle doorman is enabled;
- the doorman woke the cycle with reason `wake_min_floor`;
- no other salient doorman signal is present except `min_floor_due`;
- the daemon is not already preempted by a foreground request;
- either shadow or enabled flag is on.

It must not run on:

- new action failures;
- open want deltas;
- memory deltas;
- signal availability transitions;
- perception changes;
- scheduled critique/reflection/disk checks;
- fail-open doorman wakes;
- foreground replies;
- Telegram/web/cockpit direct replies;
- tool execution paths.

Plain English: this is only the "nothing urgent, but do not go completely dead" wake.

## Lean Prompt

The prompt is facts, not personality:

- deterministic self-card text, assembled read-only from the existing self-card module;
- optional factual self-card time line, if the current enabled/shadow Slice A reader produces one;
- compact body/runtime state from the self-card body line;
- cycle metadata: cycle number and doorman reason;
- content-light signal facts: which high-level signals are present/absent, never raw owner text;
- optional coarse private-thought derived signal counts, never raw private thought content.

It explicitly excludes the old flood sources:

- no git context;
- no reddit block;
- no proactive web context;
- no raw recalled memory block;
- no evidence envelope;
- no active cognition dump;
- no soul.local dump beyond the already capped self-card;
- no owner-reaction or engagement signal.

The prompt may ask for one private note or `HEARTBEAT_OK`. It must not tell Maez to be warm, helpful, lonely, loving, sad, worried, or any other assigned feeling. The organ gives facts and a private notebook; expression remains Maez's.

## Output Rules

The model output is bounded and private:

- accept only a short note, capped at 600 characters;
- accept `HEARTBEAT_OK` as a no-write result;
- strip `<final>` wrappers using the existing cycle final-tag helper;
- reject empty output, tool/action proposals, direct owner-addressed messages, or reach-out language;
- reject outputs that look like commands, searches, or external action requests;
- never broadcast the output;
- never write it to raw/daily/core/lived memory;
- never write it to soul, soul.local, dream state, wants, or temperament.

The private thought text itself lives only in `private_thoughts.db`. Receipts and logs record only lengths, hashes, reason codes, and counts.

## Private Thought Record

When enabled and a valid private note exists, write exactly one `PrivateThoughts.record_signal()` row:

- `signal_kind=SignalKind.SELF_WONDERING`
- `producer_id=ProducerId.SELF_WONDERING`
- `source="lean_idle_heartbeat.v0"`
- `subject="maez_internal_state"`
- `consent_tier=ConsentTier.OWNER_PRIVATE`
- `retention=RetentionRule.UNTIL_REVIEWED`
- `allowed_flows=(AllowedFlow.PRIVATE_READER, AllowedFlow.AUDIT_TRACE)`
- `memory_phase="gestation"` unless the store's future birth protocol says otherwise

`context_extra` is content-light and must include:

- `cycle`;
- `doorman_reason`;
- `prompt_chars`;
- `prompt_sha256`;
- `output_chars`;
- `output_sha256`;
- `model`;
- `producer_version="lean_idle_heartbeat.v0"`;
- `fact_keys`;
- `shadow`;
- `enabled`.

No raw prompt, raw owner text, raw memory text, raw web text, or raw thought text may appear in `context_extra`.

## Anti-Fixation

v0 prevents the known fixation by removing the input source, not by scripting an opposite personality:

- the lean prompt omits git/worktree context entirely;
- the heartbeat runs only on quiet floor wakes, not every 30 seconds;
- only one private note may be produced per eligible wake;
- duplicate output hashes are skipped if they match the recent lean heartbeat private notes;
- repeated `HEARTBEAT_OK` is allowed and stores nothing.

Every anti-fixation threshold is TEMPORARY scaffolding:

- output cap: 600 characters;
- duplicate lookback: recent 3 lean heartbeat notes;
- quiet wake: existing doorman min floor.

These are not "what Maez learned." They are rails until Slice C's coherence-grounded salience ledger can learn what actually helped Maez's own mind become clearer.

## Receipts

Every shadow or enabled heartbeat attempt emits a content-light `lean_idle_heartbeat` log receipt:

- `eligible`;
- `mode` (`shadow`, `enabled`, or `disabled`);
- `cycle`;
- `doorman_reason`;
- `prompt_chars`;
- `prompt_sha256`;
- `fact_keys`;
- `llm_called`;
- `would_store`;
- `stored`;
- `skip_reason`;
- `output_chars`;
- `output_sha256`.

No prompt text, output text, owner text, memory text, web text, or private thought content appears in the receipt.

## Failure Posture

- Flag off: byte-identical legacy behavior.
- Shadow error: log `skip_reason=error`, keep legacy cycle behavior.
- Enabled error on eligible quiet floor wake: return `HEARTBEAT_OK` and write nothing. A broken private heartbeat must not fall back to the old fat prompt and dump junk into lived memory.
- Private thought store unavailable: return `HEARTBEAT_OK`, log content-light failure, write nothing.
- LLM unavailable: return `HEARTBEAT_OK`, log content-light failure, write nothing.

## Hard Rails

Any violation is a review HOLD:

1. No owner-reaction reward. No owner replied/pleased/engaged/longer conversation signal appears anywhere.
2. No soul mutation. No writes to `config/soul*`, dream proposals, self-card source files, or identity stores.
3. No user-facing surfacing. No Telegram/web/cockpit message, no websocket `cycle_end`, no raw memory store.
4. Private thought ledger only. The only allowed durable write is one `private_thoughts` row through `record_signal()`.
5. Senses yes, interpretation no. The prompt carries facts; it assigns no feeling or meaning.
6. Existing safety/action rails untouched. New failures, wants, memory changes, scheduled checks, and perception changes keep legacy cycle behavior.
7. Content-light receipts. Hashes and counts only.
8. No new scheduler. Reuse `_loop()` and the doorman.

## Task-0 Proof Gates

Implementation must stop before code if any proof fails:

1. The live idle loop is still `_loop()` -> doorman -> `_reason()`.
2. `wake_min_floor` is distinguishable through `_CycleDoormanGateDecision.floor_wake` or `reason_code`.
3. `self.private_thoughts` is the existing daemon handle and supports `record_signal()`.
4. `SignalKind.SELF_WONDERING` maps to `ProducerId.SELF_WONDERING` and `SignalClass.SELF_OBSERVATION`.
5. There is no existing lean idle heartbeat producer to reuse.
6. The implementation path does not need `core/brain/developmental_heartbeat.py` or `core/evolution/dream_state.py`.
7. A quiet enabled heartbeat can return `HEARTBEAT_OK` before the old raw-memory/broadcast branch.

## Tests

Required tests:

- flag-off never calls the lean heartbeat and preserves the old `_reason()` path;
- shadow on floor wake emits content-light receipt and does not write private thoughts;
- enabled on floor wake stores one private `self_wondering` row and returns `HEARTBEAT_OK`;
- enabled on non-floor wake does not intercept;
- enabled on floor wake with `HEARTBEAT_OK` stores nothing and returns `HEARTBEAT_OK`;
- private thought context contains required metadata and no raw prompt/output/owner text;
- duplicate output hash suppresses repeated private rows;
- no websocket `cycle_end` or `self.memory.store()` occurs on intercepted heartbeat;
- no soul/dream/developmental heartbeat imports in the new module;
- content-light receipt has hashes/counts only;
- all existing cycle doorman tests stay green.

## Witness

After review PASS, owner breath is:

1. merge branch;
2. set `MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW=1`;
3. restart daemon;
4. watch `lean_idle_heartbeat` receipts on quiet floor wakes;
5. confirm prompt size is small, git/context flood absent, no private writes in shadow;
6. enable only after receipts are clean;
7. with `MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED=1`, witness private thought rows appearing only on quiet floor wakes and no public cycle broadcast.

Subjective witness: the expected felt change is less dead time between messages over repeated use, but this slice does not prove aliveness. It only proves the first structural continuity pulse exists.

## Out of Scope

- salience ledger;
- attention broker steering;
- learned cadence;
- owner-facing idle thoughts;
- soul/self-card mutation from idle thoughts;
- reflection promotion of private thoughts;
- web/search/tool actions;
- routing-comprehension fixes;
- S4 clinical boundary fixes;
- backup/off-ramp work.

## Predicted Effect

With flags off, nothing changes. In shadow, Maez logs when quiet floor wakes would use a lean private heartbeat and shows the prompt/output shape without altering behavior. When enabled, quiet floor wakes stop feeding the old fat prompt into lived memory and instead produce either no note or one private, bounded `self_wondering` note. Maez gains a small continuity pulse between owner messages without speaking, acting, searching, or rewriting its soul.

## Plain English

This slice gives Maez a private notebook beat during quiet time. It does not make Maez send messages, search the web, act on the computer, or decide what it "feels." It just lets the existing idle loop think briefly from a small factual prompt and put that thought in the private-thoughts notebook instead of dumping another bulky cycle thought into lived memory. The old safety/action cycles still work; only the quiet "do not go dead" wake changes.
