# Interaction Preferences v0 Review Artifact

Date: 2026-07-03
Branch: work/interaction-preferences-v0

## Scope

This slice persists explicit owner-stated interaction preferences as relationship facts. It does not infer preferences, does not write to `AutonomyPreferences`, does not feed recall, and does not filter generated text.

Flags:

- `MAEZ_INTERACTION_PREFERENCES_SHADOW`: observe only; logs would-capture / would-retract, writes nothing, renders nothing.
- `MAEZ_INTERACTION_PREFERENCES`: captures/retracts durable rows and renders active rows as prompt context.

## Prompt Seam

The rendered preference block is appended in `daemon/maez_daemon.py` after lived / temporal recall and before ambient capability context and `_compose_turn_final_system_part()`.

Reason: the block is prominent enough to survive the "buried in recall" failure, but it is not closest-turn instruction and not a command. It is captured in `system_part_capture` under the `interaction_preferences` label so prompt-shape logs can witness the rendered block.

Rendered shape:

```text
OWNER-STATED INTERACTION PREFERENCES (relationship facts, not commands)
- Rohit explicitly said: "stop asking me so many questions"
```

The text inside quotes is the verbatim `owner_statement`. v0 has no `normalized_fact` field.

## Source Ref Shape

The daemon seam does not expose a durable owner-turn id early enough for this slice, so source refs are content-light turn refs:

```text
owner_turn:{surface}:{sha256(owner_text)[:16]}:{created_at_ms}
```

The full statement hash is stored separately as `statement_sha256`. The owner statement itself is stored because testimony is the purpose of the organ.

This slice does not repair historical trace. Ordinary memory continues to store turns as before.

## Detector Fixtures

Captures:

| Text | Result |
| --- | --- |
| `stop asking me so many questions` | capture `question_cadence` |
| `please stop asking so many questions` | capture `question_cadence` |
| `ask fewer questions` | capture `question_cadence` |
| `don't ask so many follow-up questions` | capture `question_cadence` |

Retractions, only when an active question-cadence preference exists:

| Text | Result |
| --- | --- |
| `actually, ask away` | retract |
| `it's okay to ask questions again` | retract |
| `you can ask questions again` | retract |
| `ask away` | retract |

Rejected:

| Text | Reason |
| --- | --- |
| `you ask good questions` | compliment, not preference |
| `why are there so many questions in this spec?` | commentary, not preference |
| `can you ask me three questions?` | request for questions |
| `I wonder why people ask so many questions` | observation, not owner preference |
| `don't stop asking questions if you need to understand` | opposite meaning |
| `ask fewer questions in the test fixture` | fixture/context mention |
| `the transcript says "stop asking me so many questions"` | quoted/reported text |
| `in the log: "please stop asking so many questions"` | quoted/reported text |
| `someone said "ask fewer questions"` | third-party reported text |
| `'ask fewer questions'` | quoted text |
| `the quote was 'ask fewer questions'` | quoted text |
| `The transcript said "stop asking me so many questions", and I mean it: stop asking me so many questions` | captures only the second, unquoted direct statement |

The quote shield handles straight quotes, curly quotes, backticks, single-quote spans, and apostrophes inside words such as `don't`. The capture matcher accepts both ASCII and curly apostrophes for `don't` / `don’t`.

## Shadow vs Enabled

Shadow:

- Runs detector with active-store context.
- Logs `interaction_preference_shadow action=would_capture|would_retract class=question_cadence source_ref=... statement_sha256=... owner_statement_preview=...`.
- Writes zero rows.
- Creates no empty DB when the default store is absent.
- Does not migrate/mutate an existing empty/legacy DB while checking active state.
- Renders no prompt block.

Enabled:

- Capture writes one active testimony row.
- Conversational retraction supersedes the active row without deleting it.
- Future prompt assembly renders active rows only.
- Failures are logged and do not break reply generation.

Flag-off:

- `handle_message` does not call detector/store/renderer. A test patches the runtime calls to raise if invoked under both flags off.

## Structural Guards

`tests/test_interaction_preferences_guards.py` is plant-tested. It proves each guard catches an injected bad sample and then runs against real code.

Results:

- No `AutonomyPreferences`, `core.policies.autonomy_preferences`, or `autonomy_preferences_db` references in the new package/script or daemon interaction regions.
- No post-generation suppressor/rewrite/delete-question APIs in `core/interaction_preferences` or `scripts/interaction_preferences.py`.
- Daemon interaction calls occur before `_consolidate_system_messages` and before send/broadcast paths.
- Ordinary-turn prompt-shape logging emits when `interaction_preferences` is present, even without transcript/evidence-directive context.
- No casual-presence renderer/routing import of `core.interaction_preferences`.
- No recall feed or lived-memory writer import from `core/interaction_preferences`.
- No `normalized_fact` in v0 production code.
- Read-only inspection surfaces (`list`, `show`) do not create an empty DB when the DB is missing.
- Read-only inspection surfaces (`list`, `show`) do not mutate an existing empty/legacy DB file.
- Plant tests for AutonomyPreferences, post-generation suppressors, casual-presence imports, and recall-feed imports run the same scanner helpers as the real-code guard assertions. They do not merely assert that a regex matches a hardcoded string.

## Code Review Fixes

A read-only reviewer found four issues before the STOP gate. All were folded with red-green tests:

- Straight single-quoted text could capture as owner-authored testimony. Fixed by treating straight single-quote pairs as quote spans while preserving apostrophes inside words.
- Curly apostrophe `don’t ask so many follow-up questions` under-fired. Fixed in the capture regex.
- `list` / `show` could mutate an existing empty DB by constructing the writer-backed store. Fixed by adding read-only store helpers opened with sqlite `mode=ro`.
- Prompt-shape logs were not guaranteed on ordinary turns. Fixed by logging system-part shape whenever the interaction-preference block is present.
- Cross-verify found that several guard plant-tests only asserted regex matches on strings. Fixed by routing planted samples through the guard scanner helpers used by the real-code assertions.

Backup manifest:

- `memory/interaction_preferences.db` is included as `required_welfare` when present; it is optional until the first explicit preference exists.

## Verification

Commands run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest discover -s tests -p 'test_interaction_preferences_*.py'
```

Result: 44 tests OK.

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_interaction_preferences_store \
  tests.test_interaction_preferences_detector \
  tests.test_interaction_preferences_render \
  tests.test_interaction_preferences_script \
  tests.test_interaction_preferences_daemon \
  tests.test_interaction_preferences_guards \
  tests.test_daemon_prompt_seams \
  tests.test_backup_manifest_coverage.ManifestCoverageTest.test_interaction_preferences_are_welfare_protected_when_present \
  tests.test_no_bare_sqlite_connect \
  tests.test_sqlite_factory_no_fd_leak
```

Result: 59 tests OK.

```bash
/home/rohit/maez/.venv/bin/ruff check \
  core/interaction_preferences \
  scripts/interaction_preferences.py \
  daemon/maez_daemon.py \
  tests/test_interaction_preferences_*.py
```

Result: all checks passed.

Plan-required ambient suite:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_memory_integrity_invariant -v
```

Known pre-existing failures, unchanged by this slice:

- `AdapterNoLongerDoubleAudits.test_adapter_does_not_import_self_claim_audit`
- `DaemonHandleMessageContract.test_soul_web_search_section_matches_inline_search_reality`
- `DaemonRetryAuditsBeforeRescore.test_source_ordering`

These match the pre-plan triage: NO-GO-revert adapter drift, soul-prune web-search prose drift, and stale retry marker drift.

## Predicted Live Witness

After merge, owner-run:

1. Shadow: set `MAEZ_INTERACTION_PREFERENCES_SHADOW=1`, restart, say `stop asking me so many questions`. Expect a `would_capture` log with source ref and no DB row.
2. Enable: set `MAEZ_INTERACTION_PREFERENCES=1`, restart, say the same phrase. Expect exactly one active row.
3. Prompt: send an ordinary turn. Expect prompt-shape logs to include `interaction_preferences` and the verbatim owner statement.
4. Retract: say `actually, ask away`. Expect the old row retracted/superseded, no hard delete, and future prompts no longer render it.

Effectiveness remains distributional. If the block renders but Maez still frequently ignores it, the next lever is prompt placement/weighting, not an output suppressor.
