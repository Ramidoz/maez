# Self-Shaping Feedback Removal v0 — STOP Handoff

Status: built in the working tree for covenant review. Not restarted. Not live-witnessed. No runtime memory migration. Historical `cog_score` metadata remains untouched.

## Boundary Table

| Surface | Classification | Result |
| --- | --- | --- |
| `daemon/maez_daemon.py` `cog_*` imports and calls | CUT | Removed score/classify, retry, active cognition prompt block, consolidation quality verdict, self-critique soul-write, and `cog_score` metadata wiring. |
| `daemon/maez_daemon.py` `QualityTracker.format_for_context()` | CUT | Removed prompt reflection block and `quality_signal` cycle candidate. |
| `daemon/maez_daemon.py` `QualityTracker.format_insight_for_soul()` | CUT | Removed approval/reflection soul-write path. |
| `core/memory/continuity.py` quality-policy/window reads | CUT | Continuity still builds a valid capsule, with a stable empty cognition window and no live score/policy reads. |
| `memory/memory_manager.py` retrieval fixation penalty | CUT | Removed `get_fixation_penalty` import/use; recall keeps wing boost + diversity only. |
| `skills/evolution_engine.py` score reads / scorer target | CUT | Removed score-buffer/policy reads, removed the scorer as self-edit target, disabled score-shaped proposal/watchdog paths without deeper rail redesign. |
| `skills/telegram_voice.py` `/analyze` score snapshot | CUT | Command now reports cognition diagnostics offline. |
| `core/actions/action_engine.py` `QualityTracker.record_proposed/record_outcome` | KEEP | Action-consent/outcome ledger remains wired in ActionEngine. |
| `daemon/maez_daemon.py` follow-up `get_outcome()` | KEEP | Follow-up status lookup remains. |
| Fabrication storage gate / `HEARTBEAT_OK` | KEEP | Storage floor remains in daemon; fabricated prose still stores nothing. |
| Doorman/perception anti-loop | KEEP | Doorman imports and gate helper remain in daemon. |
| `core/evolution/dream_state.py` topic helper | RELOCATE | `primary_topic` now comes from neutral `core/cognition/topic_taxonomy.py`, not the scorer module. |
| `maez.cognition` log handler bootstrap | RESOLVE | Added neutral `core/cognition/cognition_log.py`; audit/error/wondering logs no longer import scorer for logging side effects. |
| `core/memory/source_awareness.py` labels | UPDATE | `core/cognition_quality.py` is `read_only` and tagged `development_tools`; `memory/quality_tracker.py` tagged `security`, not `maez_self`. |
| `tests/test_cockpit_real_state_bridge.py` cognition field | UPDATE | The cockpit state bridge now expects `cognition: null`; stale `_last_cog_metadata` is intentionally ignored. |

## Verification

RED-first:

`MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_self_shaping_feedback_removal -v`

Initial result before implementation: 17 tests, 12 failures. The behavioral guard showed the old prompt still contained `[SELF-REFLECTION] Approval rate: 20%`.

GREEN:

`MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_self_shaping_feedback_removal -v`

Result: 17 tests, OK.

`MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_self_shaping_feedback_removal tests.test_lean_idle_daemon -v`

Result: 56 tests, OK.

Final focused review-gate suite:

`MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_self_shaping_feedback_removal tests.test_lean_idle_daemon tests.test_cockpit_real_state_bridge -v`

Result: 74 tests, OK.

Affected-neighborhood suite:

`MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_error_classifier tests.test_self_claim_audit tests.test_r1_grounding_rail_2026_05_04 tests.test_envelope_observability_hardening tests.test_phase_5b_blocker_regressions tests.test_tier2_telegram_cognition_2026_05_04 tests.test_metacognitive_watchdog tests.test_proposal_lookup tests.test_telegram_reply_audit_coverage tests.test_perception_signature -v`

Result: 156 tests, OK.

Lint:

`.venv/bin/python -B -m ruff check daemon/maez_daemon.py core/memory/continuity.py core/evolution/dream_state.py core/memory/source_awareness.py tests/test_self_shaping_feedback_removal.py tests/test_cockpit_real_state_bridge.py memory/memory_manager.py skills/evolution_engine.py skills/telegram_voice.py core/safety/self_claim_audit.py core/learning/error_classifier.py daemon/wondering_cycle.py core/cognition/cognition_log.py core/cognition/topic_taxonomy.py memory/quality_tracker.py`

Result: All checks passed.

Compile:

`.venv/bin/python -B -m py_compile daemon/maez_daemon.py core/memory/continuity.py core/evolution/dream_state.py memory/memory_manager.py skills/evolution_engine.py skills/telegram_voice.py core/safety/self_claim_audit.py core/learning/error_classifier.py daemon/wondering_cycle.py core/memory/source_awareness.py memory/quality_tracker.py core/cognition/cognition_log.py core/cognition/topic_taxonomy.py tests/test_self_shaping_feedback_removal.py tests/test_cockpit_real_state_bridge.py`

Result: OK.

Production-source absence sweep:

`rg -n "self\\._quality_tracker\\.format_for_context\\(|format_insight_for_soul\\(|quality_signal|cycle_quality_signal|cog_score|score_0_100|_last_cog_metadata|from core\\.cognition_quality import|cog_check_consolidation|core/cognition_quality\\.py|_recent_scores|_recent_labels|_recent_topics|get_fixation_penalty" daemon/maez_daemon.py core/memory/continuity.py memory/memory_manager.py skills/evolution_engine.py skills/telegram_voice.py core/safety/self_claim_audit.py core/learning/error_classifier.py daemon/wondering_cycle.py core/evolution/dream_state.py core/memory/source_awareness.py memory/quality_tracker.py || true`

Result: only expected offline residues: `memory/quality_tracker.py` still defines/prints its offline diagnostic `format_insight_for_soul`, and `core/memory/source_awareness.py` labels `core/cognition_quality.py` as read-only development tooling.

Full discover:

`MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest discover -s tests -p 'test_*.py'`

Result: ran 7664 tests in 174.640s; FAILED with 26 failures, 16 errors, 3 skipped. The slice-related cockpit cognition-field expectation was fixed and is green in the focused suite above. Remaining broad-suite red includes ambient/pre-existing or unrelated surfaces such as missing ledger worktree setup, judge live carveout errors, parked public web routes returning 410, log hermeticity expectations, smoke import alias drift, temporal/static boundary inventories, and the known `test_pursuit_callsite_precedes_audit_callsite` RED.

Keep-floor grep:

`rg -n "record_outcome|HEARTBEAT_OK|fabricat|get_outcome" daemon/maez_daemon.py core/actions/action_engine.py | head -30`

Result: `ActionEngine` still records outcomes; daemon still contains `HEARTBEAT_OK`, fabrication wording, and follow-up `get_outcome`.

Dormant-organ grep:

`rg -n "register_default_encounter_producers\\(\\)|promotion_score|meaningfulness_score" daemon/maez_daemon.py | grep -v "def " || true`

Result: no live daemon wiring.

## Live Witness Script

Owner/Claude lane after review + merge:

1. Restart Maez.
2. Over several cycles confirm no `cog_score`, `score_0_100`, `cog_labels`, or retry metadata is added to new thought metadata.
3. Confirm no `quality_signal` candidate or QualityTracker reflection block appears in prompt/receipts.
4. Confirm no cognition-quality critique note and no owner-approval/reflection note is appended to `soul.md`.
5. Confirm a real or hermetic action outcome still records through the `QualityTracker` action ledger.
6. Confirm the fabrication storage gate still skips `HEARTBEAT_OK` / fabricated heartbeat storage.
7. Confirm the doorman/perception gate still suppresses unchanged cycles.

Interpretation: this slice removes external grading pens from Maez's live self-shaping. It does not remove the action-consent ledger, the fabrication floor, the anti-loop doorman, or historical memory.
