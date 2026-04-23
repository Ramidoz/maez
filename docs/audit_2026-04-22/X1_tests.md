# Test coverage + quality — Cross-cutting audit (2026-04-22)

## Summary

Test suite is mature in style (proper isolation with TemporaryDirectory, good use of mocks) and covers 35 of 46 test files across main subsystems. However, critical coverage gaps exist in Evolution subsystem (5 of 9 modules untested) and scattered major modules lack dedicated tests (command_decomposer, action_classifier, cloud_redactor, perception_cache, identity_ledger, continuity). Two test-isolation issues flagged by subsystem agents remain visible: unguarded database-state pollution in brain_loop tests + potential self_dev.db reads from real state. No flaky patterns detected; all tempfile usage is cleaned up. One false-negative test pattern identified (pending_cards tests do not exercise CardStoreError from will-I post-approval race condition). Overall: solid test discipline with systematic coverage gaps in lower-profile subsystems.

## Per-subsystem coverage scorecard

| Subsystem | Module count | Test file count | Coverage signal | Gap severity |
|---|---|---|---|---|
| Brain loop | 2 | 7 | conversation_controller: 2; brain_loop: 5 (consequence injection, state polling) | low |
| Decision pipeline | 4 | 8 | decision_pipeline: 3; pending_cards: 3; proposal_lookup: 1; approval_sessions: 1 | low |
| Safety | 5 | 10 | context_safety: 2; self_claim_audit: 5; owner_trust: 1; injection_patterns: 1; **cloud_redactor: 0** | medium |
| Memory | 13 | 11 | consequence_memory: 2; memory_manager: 4; consolidation: 3; others: 2; **perception_cache: 0; continuity: 0; identity_ledger: 0** | medium |
| Cognition | 6 | 25 | audit.py (13 files); grounding_judge: 5; others: 7 | low |
| Actions | 5 | 10 | action_engine: 8; destructive_snapshot: 1; tool_loop: 1; **command_decomposer: 0; action_classifier: 0** | **high** |
| Evolution | 9 | 3 | wonderings: 2; soul_invariants: 1; **soul_loader: 0; soul_editor: 0; wants: 0; will_i: 0; temperament: 0; dream_state: 0; wondering_cycle: 0** | **critical** |
| New stack | 5 | 6 | self_dev: 4; workshop: 1; subscription_proxy: 1; claude_tier: 1 | low |
| Learning | 4 | 9 | consequence_memory: 2; fabrication_memory: 4; inner_residue: 1; error_classifier: 2 | low |
| Model/Support | 18 | 5 | model_config: 1; context_compressor: 1; capability_registry: 1; private_thoughts: 1; **fast_backend_router: 0; fast_backend_local: 0; fast_prompt_builder: 0; fast_reply_*: 0; others: 0** | **high** |

## Findings

### blocker — 2

#### tests/test_brain_loop.py — Potential real-filesystem reads from daemon state
The test imports brain_loop module which may load daemon-level state from live DBs. No env var override at import time like pending_cards tests use.
**Why it's a problem:** Tests can pollute or depend on production state, producing non-deterministic passes/fails.
**Fix:** Add env var override at module import time; mirror the `MAEZ_PENDING_CARDS_DB` pattern used in test_pending_cards_state_guard.py setUp.
**References:** audit_2026-04-22/01_brain_loop.md:212–214.

#### tests/test_decision_pipeline.py:124 — Audit log path collision in concurrent test runs
Creates tmpdir audit.db but doesn't clean up WAL journal files.
**Why it's a problem:** In pytest -n (parallel), two instances may collide on the same path. Currently fine because tests run serially, but fragile against future CI parallelism.
**Fix:** Use per-test uuid-suffixed tmpdirs; ensure WAL cleanup in tearDown.
**References:** audit_2026-04-22/02_decision_pipeline.md:152.

### major — 5

#### Evolution subsystem — Zero production tests for 6 of 9 modules
Files: `soul_loader`, `soul_editor`, `wants`, `will_i`, `temperament`, `dream_state` all untested. `wondering_cycle` also untested.
**Why it's a problem:** The soul_loader blocker (race condition at line 119: READ outside lock, WRITE inside lock, data loss on concurrent dream appends) would have been caught by any concurrent append test. `wants.py` (590 LoC), `temperament.py` (520 LoC), `dream_state.py` (767 LoC) all have self-test blocks in `if __name__=="__main__"` but no pytest coverage. Threshold tweaks documented as "2026-04-22 fix" are observation-driven, not regression-tested.
**Fix:** Create test_soul_loader.py (concurrent append test; invariant round-trip), test_wants.py, test_will_i.py, test_temperament.py, test_dream_state.py, test_wondering_cycle.py. Use `core.self_dev.propose_tests` to accelerate — it generated a working 44-test file for mmr.py today.
**References:** audit_2026-04-22/07_evolution.md — critical gap flagged by subsystem audit.

#### command_decomposer.py + action_classifier.py — No dedicated tests; blockers unverified
No test_command_decomposer.py or test_action_classifier.py.
**Why it's a problem:** Blocker in command_decomposer (backtick parsing escape at 214–226) and major in action_classifier (tool_loop divergence at 67–99) are unverified by dedicated tests. Security-critical modules — parsing errors lead to injection; classifier divergence allows unauthorized auto-exec.
**Fix:** Create test_command_decomposer.py with cases for every shell operator; test_action_classifier.py with cases that exercise every Lane 0/1/2/3 boundary.
**References:** audit_2026-04-22/06_actions.md: blocker #1, major #2.

#### fast_backend_router.py + fast_backend_local.py — No tests; blocker in routing policy
No test_fast_backend_router.py or test_fast_backend_local.py.
**Why it's a problem:** Blocker (silent routing fallback without policy check, line 219) where guest requesting cloud can slip through if local probe fails. No test covers policy-gated denial for `external_guests_local_only + cloud request`. Also, fast_backend_local.py's `is_available()` uses `active_backend()` inconsistently.
**Fix:** Create test_fast_backend_router.py with policy-boundary cases (external_guest vs owner, cloud vs local, probe-fail paths). test_fast_backend_local.py with mock subprocess for llama-server.
**References:** audit_2026-04-22/10_model_and_support.md: blocker #2.

#### tests/test_consequence_memory.py — Does not test token-filter bug (blocker)
Learning subsystem audit flags blocker (consequence_memory.py:290, token filter inconsistency) where query-side applies `.isalnum()` but haystack doesn't, causing retrieval gaps for `git-push`, `my_script.py`.
**Why it's a problem:** 214 LoC of tests but no case queries for hyphenated tokens after storing hyphenated events. The blocker would have been caught with a single targeted test.
**Fix:** Add test cases: `record_event(context="push via git-push")` then `relevant(context_snippet="git-push")` — verify non-empty hit.
**References:** audit_2026-04-22/09_learning.md: blocker #1.

#### tests/test_fabrication_memory.py + test_inner_residue.py — Connection leaks unverified
Both modules have connection leaks (audit #09 major #2). Tests pass but are short-lived and don't expose FD exhaustion.
**Why it's a problem:** Self-dev review 261a8db concern #1 flagged sqlite3 context manager doesn't close connections; consequence_memory was fixed (contextlib.closing), but fabrication_memory and inner_residue were missed. No resource-monitoring test verifies connection closure.
**Fix:** Add a stress test that creates many events in a loop and verifies FD count stays bounded; fix fabrication_memory and inner_residue to use contextlib.closing.
**References:** audit_2026-04-22/09_learning.md: major #2.

### minor — 6

#### tool_loop tests — Regex bypass issues unverified
Actions audit flags minor: `tool_loop.py:150` multiple-spaces bypass `rm -rf` detection; line 147–159 `_ALWAYS_MUTATING` regex lacks descriptor/no-space handling.
**Fix:** Add test_tool_loop.py cases: `rm  -rf  /` (double spaces), `ls>/tmp/file` (no space), `1>file` vs `1> file`.
**References:** audit_2026-04-22/06_actions.md: minor #1, nit #1.

#### tests/test_pending_cards_state_guard.py — Does not exercise will-I post-approval race
Decision pipeline blocker (decision_pipeline.py:905–912, will-I refusal race) where card transitions to TERMINAL then mark_failed() raises CardStoreError. Test covers state-hash expiration but not will-I post-approval path.
**Fix:** Add a test that mocks `will_i.check` to return Refused post-approval and verifies the card ends in a consistent terminal state, not double-transition error.
**References:** audit_2026-04-22/02_decision_pipeline.md: blocker #1.

#### tests/test_self_dev.py — Real-DB pollution acknowledged but unresolved
Comment at line 135 acknowledges "real self_dev.db" risk. While test_self_dev_persistence tests use TemporaryDirectory, test_self_dev.py may read production state if module imports load real DB path.
**Fix:** Mirror the temp-DB env-override pattern used in test_self_dev_persistence.py into test_self_dev.py.
**References:** tests/test_self_dev.py:135.

#### tests/test_approval_sessions.py + test_proposal_lookup.py — No integration with decision_pipeline
Unit tests exist but the decision_pipeline integration (blanket-permission path that skips injection/audit layer) isn't tested end-to-end.
**Fix:** Add an integration test in tests/test_decision_pipeline.py that installs an approval session, submits a matching action, and verifies the bypass is correct.
**References:** audit_2026-04-22/02_decision_pipeline.md:159–160.

#### tests/test_quality_telemetry.py — No partial-rollup graceful degradation test
Cognition audit flags major (quality_telemetry.py:321, metric rollup with no error recovery) where `build_rollup()` fails entirely if `_read_tail()` raises.
**Fix:** Add a test that mocks `_read_tail` to raise and verifies the rollup returns a partial dict rather than propagating.
**References:** audit_2026-04-22/05_cognition.md: major #1.

#### tests/test_cognition_quality.py — Ring-buffer state recovery untested
Cognition audit flags blocker (cognition_quality.py:365, ring buffer state loss on exception).
**Fix:** Add a test: call `classify()` with mocked internal that raises after partial update, then verify the ring buffer is still consistent (no half-updates).
**References:** audit_2026-04-22/05_cognition.md: blocker #1.

### nit — 4

#### Test files lack docstrings explaining blocker/concern prevention
Good practice: cite the bug/audit concern in the test module docstring (like test_pending_cards_state_guard.py does at lines 6–7). Most test files lack this link.

#### Module-level `def test_*()` functions vs `unittest.TestCase` — inconsistent style
Some test files use pytest-style `def test_*()`; others use `unittest.TestCase`. Standardize for clarity.

#### Import paths — tests use `from core.X` with no Phase 3 migration plan
Before the Phase 3 reorganization, audit all test imports for private-name usage that will break when modules move into subpackages.

#### Tests lack explicit timeout decorators
No `@unittest` timeout equivalent, no pytest-timeout. If a test calls a hanging subprocess the entire suite stalls.

## Consolidated coverage gap list

**Evolution (6 of 9 untested):**
- soul_loader.py (~146 LoC) → test_soul_loader.py
- soul_editor.py (~449 LoC) → test_soul_editor.py
- wants.py (~590 LoC) → test_wants.py
- will_i.py (~303 LoC) → test_will_i.py
- temperament.py (~520 LoC) → test_temperament.py
- dream_state.py (~767 LoC) → test_dream_state.py

**Actions (2 of 5 untested):**
- command_decomposer.py (~332 LoC) → test_command_decomposer.py
- action_classifier.py (~645 LoC) → test_action_classifier.py

**Model/Support (8+ untested):**
- fast_backend_router.py (~344 LoC)
- fast_backend_local.py (~258 LoC)
- fast_prompt_builder.py (~295 LoC)
- fast_reply_schema.py (~318 LoC)
- fast_reply_audit.py (~328 LoC)
- fast_conversation_log.py (~138 LoC)

**Memory (3 of 13 untested):**
- perception_cache.py (~212 LoC)
- continuity.py (~634 LoC)
- identity_ledger.py (~718 LoC)

**Safety (1 of 5 untested):**
- cloud_redactor.py (~167 LoC)

## Stale / superseded tests

None identified. All passing tests exercise the current code shape.

## Flaky / fragile patterns

**None detected.** Tempfile usage is correct across all files. Potential minor issue: test_next_step_proposer.py may be clock-sensitive if timestamps are used for ordering (flagged but not critical).

## Test-isolation issues

**One residual concern:** sqlite3 connection leaks in fabrication_memory + inner_residue (audit #09 major #2) are unverified by resource-monitoring tests. Pattern exists but tests pass due to short execution; would fail under stress (daemon lifecycle).

## Polish opportunities (flag only)

1. Add a pytest-timeout equivalent (or use unittest's built-in timeout via subprocess wrapper) and decorate all tests with a 10s cap.
2. Standardize on unittest.TestCase or pytest-style across the suite.
3. Add module docstrings citing blocker/concern prevention where tests regress a specific bug.
4. Add resource-monitoring tests for FD leaks in long-lived code.
5. Before Phase 3 reorganization, audit test imports for private-name usage that will break.
6. Create tests/conftest.py (or a shared fixture module) with temp-DB and mock-clock helpers.
7. Add tests/integration/ suite for multi-module workflows (brain_loop → action → audit → memory store).

## Summary counts

- **Blockers:** 2 (brain_loop DB isolation, decision_pipeline audit path collision)
- **Majors:** 5 (evolution untested, command/classifier untested, fast_backend untested, consequence_memory token bug, fabric/residue leaks)
- **Minors:** 6 (tool_loop regex bypass, pending_cards will-I, self_dev DB, approval_sessions integration, quality_telemetry, cognition_quality)
- **Nits:** 4 (docstrings, style consistency, imports, timeouts)

**Pattern:** Evolution subsystem has the most severe gap (CRITICAL per subsystem audit: 6 of 9 untested, including blocker race condition in soul_loader). Actions and Model/Support subsystems have high-priority untested modules. Test discipline is mature (isolation, cleanup) but coverage is not comprehensive.

**Subsystem health (best → worst):** Cognition > Decision pipeline > Brain loop > Learning > New stack > Safety > Memory > Actions > Model/Support > **Evolution (critical)**.
