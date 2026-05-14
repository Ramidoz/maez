# Master findings — Maez audit (2026-04-22)

> Consolidated from 10 subsystem + 2 cross-cutting agent reports.
> Every finding here is linked back to its subsystem file for the full context (code quote, fix, references).

## Top-line

- Total findings: **85** across 12 reports
- By severity: **12 blocker, 23 major, 28 minor, 22 nit**
- Baseline: HEAD `9197bba`, 519 tests passing, all 5 services active
- Per-subsystem health scorecard: see the table below
- Note: X1 (tests) and X2 (docs) findings are cross-cutting; some X1 entries reference the same root bugs as subsystem reports but surface them as *test-coverage* gaps rather than code bugs. They are listed once under X1 to honor the `_INDEX.md` authoritative totals, not re-attributed to the subsystem.

## Subsystem health scorecard

| Subsystem | Blocker | Major | Minor | Nit | Overall |
|---|---:|---:|---:|---:|---|
| 10 Model + fast-path + support | 2 | 3 | 3 | 2 | 🔴 critical |
| X1 Test coverage | 2 | 5 | 6 | 4 | 🔴 critical |
| X2 Documentation | 2 | 3 | 4 | 2 | 🔴 critical |
| 02 Decision pipeline | 1 | 2 | 3 | 2 | 🟠 needs work |
| 05 Cognition + grounding | 1 | 2 | 2 | 1 | 🟠 needs work |
| 06 Action engine + tool loop | 1 | 2 | 2 | 1 | 🟠 needs work |
| 07 Evolution | 1 | 2 | 2 | 1 | 🟠 needs work (test gap CRITICAL) |
| 01 Brain loop | 1 | 2 | 2 | 3 | 🟠 needs work |
| 09 Learning (consequence/fab/residue) | 1 | 2 | 0 | 2 | 🟠 needs work |
| 04 Memory + recall | 0 | 0 | 2 | 2 | 🟡 mostly clean |
| 03 Safety layer | 0 | 0 | 2 | 2 | 🟡 mostly clean |
| 08 New stack (self-dev/proxy/workshop) | 0 | 0 | 0 | 0 | 🟢 clean |

## Top 20 things to fix first

Ranked by severity + blast radius + ease of fix.

### 1. 01-B1 — Bare `self` reference in module-level `run_brain_loop` retry path
**File:** `core/brain_loop.py:880-881`
**Subsystem:** Brain loop
**Severity:** blocker
**Why it's here:** NameError crashes a production code path every time the retry-intent regex matches. Blast radius = every conversation turn that invokes recovery. Trivial fix.
**Full context:** see `docs/audits/2026-04-22/01_brain_loop.md` → `blocker` section

### 2. 09-B1 — Token-filter asymmetry silently loses consequence retrieval
**File:** `core/consequence_memory.py:290`
**Subsystem:** Learning
**Severity:** blocker
**Why it's here:** Query side applies `.isalnum()`, haystack doesn't — any hyphenated/underscored token (`git-push`, `my_script.py`) never matches. Degrades the entire mistake-memory loop silently. One-line fix.
**Full context:** `09_learning.md` → `blocker` section

### 3. 07-B1 — soul_loader append race drops dream proposals
**File:** `core/soul_loader.py:119`
**Subsystem:** Evolution
**Severity:** blocker
**Why it's here:** Read outside lock, write inside lock → concurrent dream-applies overwrite each other. Silent data loss on Maez's own evolution artifacts. Directly violates "never delete Maez memory."
**Full context:** `07_evolution.md` → `blocker` section

### 4. 02-B1 — Will-I post-approval refusal leaves card in inconsistent terminal state
**File:** `core/decision_pipeline.py:905-912`
**Subsystem:** Decision pipeline
**Severity:** blocker
**Why it's here:** Will-I fires after mark_running → card DENIED → execution proceeds → mark_failed raises CardStoreError uncaught. Crashes action-engine path on a non-rare code path.
**Full context:** `02_decision_pipeline.md` → `blocker` section

### 5. 06-B1 — Command decomposer backtick escape bypasses classification
**File:** `core/command_decomposer.py:214-226`
**Subsystem:** Actions
**Severity:** blocker
**Why it's here:** `echo \`id\` | rm -rf /` parses as one malformed substitution, pipeline not decomposed, destructive lane evaded. Security-critical parser gap.
**Full context:** `06_actions.md` → `blocker` section

### 6. 05-B1 — cognition_quality ring-buffer corruption on exception
**File:** `core/cognition_quality.py:365`
**Subsystem:** Cognition
**Severity:** blocker
**Why it's here:** One classify() exception freezes _recent_topics for hours; fixation detection + behavior policy operate on stale state. No audit trail for the corruption.
**Full context:** `05_cognition.md` → `blocker` section

### 7. 10-B1 — fast_backend_router silent fallback loses guest-tier policy
**File:** `core/fast_backend_router.py:219`
**Subsystem:** Model/Support
**Severity:** blocker
**Why it's here:** Policy-denied vs availability-failed share the same backend=None signal; guest requesting cloud can slip through on a transient local probe failure. Cloud leak risk.
**Full context:** `10_model_and_support.md` → `blocker` section

### 8. 09-M1 — fabrication_memory sqlite connections never closed
**File:** `core/fabrication_memory.py:98,131,188,216`
**Subsystem:** Learning
**Severity:** major
**Why it's here:** FD leak on every call; consequence_memory already has the fix pattern. Certain daemon crash over hours.
**Full context:** `09_learning.md` → `major` section

### 9. 09-M2 — inner_residue sqlite connections never closed
**File:** `core/inner_residue.py:102,130,155`
**Subsystem:** Learning
**Severity:** major
**Why it's here:** Same FD leak; called every cycle turn so the leak rate is worst in the codebase. Identical fix pattern as 09-M1.
**Full context:** `09_learning.md` → `major` section

### 10. 10-B2 — private_thoughts hardcoded fallback path breaks on relocation
**File:** `core/private_thoughts.py:110-113`
**Subsystem:** Model/Support
**Severity:** blocker
**Why it's here:** paths.py exists but isn't used; fallback assumes core/ is two dirs under maez home. Breaks MAEZ_HOME portability for sensitive private-thoughts store.
**Full context:** `10_model_and_support.md` → `blocker` section

### 11. 05-M1 — audit_log.record() no explicit commit, silent write loss
**File:** `core/audit_log.py:283`
**Subsystem:** Cognition
**Severity:** major
**Why it's here:** Request_id returned even if INSERT rolled back. Downstream record_outcome() silently succeeds on a non-row. Audit-layer invariant violation.
**Full context:** `05_cognition.md` → `major` section

### 12. 06-M1 — destructive_snapshot return value ignored; silent partial backups
**File:** `core/action_engine.py:677-712`
**Subsystem:** Actions
**Severity:** major
**Why it's here:** snapshot() can return partial `errors` list without raising — `git reset --hard` can execute with half-backed-up files. No rollback path.
**Full context:** `06_actions.md` → `major` section

### 13. 06-M2 — tool_loop.is_read_only vs action_classifier Lane-0 divergence
**File:** `core/tool_loop.py:165-201`
**Subsystem:** Actions
**Severity:** major
**Why it's here:** Daemon auto-exec gate uses binary allowlist; classifier uses deny-bad-patterns. Two sources of truth for "safe to auto-execute." Semantic drift = untracked bypasses.
**Full context:** `06_actions.md` → `major` section

### 14. 07-M2 — dream_state schema migration missing explicit commit
**File:** `core/dream_state.py:141-186`
**Subsystem:** Evolution
**Severity:** major
**Why it's here:** Relies on context manager implicit commit across ALTER TABLE chain. Fragile if any ALTER raises mid-chain.
**Full context:** `07_evolution.md` → `major` section

### 15. 05-M2 — quality_telemetry build_rollup crashes on any parse failure
**File:** `core/quality_telemetry.py:321`
**Subsystem:** Cognition
**Severity:** major
**Why it's here:** Cockpit goes dark on transient log-read error; violates "never raises" promise. audit_log.stats() already has the graceful-degradation pattern to copy.
**Full context:** `05_cognition.md` → `major` section

### 16. 05-M3 — quality_telemetry unguarded db.close() when connect() fails
**File:** `core/quality_telemetry.py:268-270`
**Subsystem:** Cognition
**Severity:** major
**Why it's here:** NameError in finally masks original connect failure. Pattern repeats in multiple files; fix is 1 line (`db = None` pre-try).
**Full context:** `05_cognition.md` → `major` section

### 17. 01-M2 — brain_loop retry-context sqlite relative-path + no timeout
**File:** `core/brain_loop.py:881-893`
**Subsystem:** Brain loop
**Severity:** major
**Why it's here:** Co-located with blocker 01-B1; must be fixed in the same commit. Relative path hits wrong DB from executor thread.
**Full context:** `01_brain_loop.md` → `major` section

### 18. 07-M1 — temperament.py NaN in log output
**File:** `core/temperament.py:254`
**Subsystem:** Evolution
**Severity:** major
**Why it's here:** "nan" literal poisons log-parsing tools for every first-event temperament write. Cheap to fix.
**Full context:** `07_evolution.md` → `major` section

### 19. 10-M3 — capability_registry hardcoded `/home/rohit/maez`
**File:** `core/capability_registry.py:41`
**Subsystem:** Model/Support
**Severity:** major
**Why it's here:** describe() reports stale grounded facts if MAEZ_HOME is set. Used by guest-scope replies — wrong-owner leak potential.
**Full context:** `10_model_and_support.md` → `major` section

### 20. 02-M2 — Dialog-routed approval _SyntheticCls drops audit_request_id
**File:** `core/decision_pipeline.py:851`
**Subsystem:** Decision pipeline
**Severity:** major
**Why it's here:** Fragile implicit contract: future refactor that reads cls.audit_request_id silently records under wrong audit row. Defense-in-depth fix.
**Full context:** `02_decision_pipeline.md` → `major` section

## All findings, severity-sorted

### blocker (12 total)

#### 01-B1 — `core/brain_loop.py:880-881` — Bare `self` in module-level retry path
**Subsystem:** Brain loop · **File:** `core/brain_loop.py:880-881`
**Short version:** NameError in `run_brain_loop` retry block; `self` undefined in module-scope function.
**Full detail:** `01_brain_loop.md` → `blocker`

#### 02-B1 — `core/decision_pipeline.py:905-912` — Will-I post-approval leaves card inconsistent
**Subsystem:** Decision pipeline · **File:** `core/decision_pipeline.py:905-912`
**Short version:** Will-I denies card after mark_running; execution still proceeds; mark_failed raises uncaught CardStoreError.
**Full detail:** `02_decision_pipeline.md` → `blocker`

#### 05-B1 — `core/cognition_quality.py:365` — Ring-buffer state loss on exception
**Subsystem:** Cognition · **File:** `core/cognition_quality.py:365`
**Short version:** classify() raises → ring buffers never updated → fixation/behavior policy runs on stale state silently.
**Full detail:** `05_cognition.md` → `blocker`

#### 06-B1 — `core/command_decomposer.py:214-226` — Backtick escape bypasses decomposition
**Subsystem:** Actions · **File:** `core/command_decomposer.py:214-226`
**Short version:** Escaped backticks (\`...\`) inside substitution parsing break pipeline splitting; destructive lanes evaded.
**Full detail:** `06_actions.md` → `blocker`

#### 07-B1 — `core/soul_loader.py:119` — append_to_local race (read outside lock)
**Subsystem:** Evolution · **File:** `core/soul_loader.py:119`
**Short version:** Two concurrent dream applies overwrite each other → silent soul.local.md truncation + lost proposals.
**Full detail:** `07_evolution.md` → `blocker`

#### 09-B1 — `core/consequence_memory.py:290` — Token filter asymmetry
**Subsystem:** Learning · **File:** `core/consequence_memory.py:290`
**Short version:** Query applies `.isalnum()`, haystack doesn't; hyphen/underscore tokens unretrievable.
**Full detail:** `09_learning.md` → `blocker`

#### 10-B1 — `core/fast_backend_router.py:219` — Silent fallback loses policy differentiation
**Subsystem:** Model/Support · **File:** `core/fast_backend_router.py:219`
**Short version:** Policy-denied vs availability-failed indistinguishable; guest cloud requests can slip through on transient local probe failure.
**Full detail:** `10_model_and_support.md` → `blocker`

#### 10-B2 — `core/private_thoughts.py:110-113` — Hardcoded path fallback
**Subsystem:** Model/Support · **File:** `core/private_thoughts.py:110-113`
**Short version:** `parent.parent / "memory"` fallback breaks on relocation despite paths.py existing.
**Full detail:** `10_model_and_support.md` → `blocker`

#### X1-B1 — `tests/test_brain_loop.py` — Real-DB pollution risk
**Subsystem:** Tests · **File:** `tests/test_brain_loop.py`
**Short version:** Daemon-level state may load live DBs at import; no MAEZ_PENDING_CARDS_DB-style override.
**Full detail:** `X1_tests.md` → `blocker`

#### X1-B2 — `tests/test_decision_pipeline.py:124` — Audit log path collision under parallel
**Subsystem:** Tests · **File:** `tests/test_decision_pipeline.py:124`
**Short version:** tmpdir audit.db + WAL cleanup missing; fragile against future pytest -n.
**Full detail:** `X1_tests.md` → `blocker`

#### X2-B1 — `docs/ARCHITECTURE.md:70-88` — Hardcoded `/home/rohit/maez` in user-facing doc
**Subsystem:** Documentation · **File:** `docs/ARCHITECTURE.md:70-88`
**Short version:** Signals non-portability to newcomers; no MAEZ_HOME caveat.
**Full detail:** `X2_documentation.md` → `blocker`

#### X2-B2 — `docs/TRACK_A.md:92-94` — Acceptance gate definition unclear
**Subsystem:** Documentation · **File:** `docs/TRACK_A.md:92-94`
**Short version:** Cites eight-point check without inline summary; ambiguous vs. Decision 1 "developmental readiness" framing.
**Full detail:** `X2_documentation.md` → `blocker`

### major (23 total)

#### 01-M1 — `core/brain_loop.py:265` n/a — `consequence_memory.py:265-314` short-token filter gap
**Subsystem:** Brain loop · **File:** `core/consequence_memory.py:290`
**Short version:** `len(t) > 2` filter silently eliminates cd/rm/ls short-command retrieval (see also 09-B1 for matching blocker).
**Full detail:** `01_brain_loop.md` → `major`

#### 01-M2 — `core/brain_loop.py:881-893` — Retry-context sqlite relative-path + no timeout
**Subsystem:** Brain loop · **File:** `core/brain_loop.py:881-893`
**Short version:** Relative `"memory/audit_log.db"` hits wrong file from executor thread cwd; no connection timeout.
**Full detail:** `01_brain_loop.md` → `major`

#### 02-M1 — `core/decision_pipeline.py:1006-1030` — consequence_memory silent-fail on card deny
**Subsystem:** Decision pipeline · **File:** `core/decision_pipeline.py:1006-1030`
**Short version:** Broad `except Exception: pass` hides consequence_memory failures; learning loop silently skipped.
**Full detail:** `02_decision_pipeline.md` → `major`

#### 02-M2 — `core/decision_pipeline.py:851` — Dialog-routed approval drops audit_request_id
**Subsystem:** Decision pipeline · **File:** `core/decision_pipeline.py:851`
**Short version:** _SyntheticCls has no audit_request_id; fragile implicit dependency on card.audit_request_id.
**Full detail:** `02_decision_pipeline.md` → `major`

#### 05-M1 — `core/audit_log.py:283` — record() missing explicit commit
**Subsystem:** Cognition · **File:** `core/audit_log.py:283`
**Short version:** request_id returned even on silent rollback; record_outcome() succeeds against non-row.
**Full detail:** `05_cognition.md` → `major`

#### 05-M2 — `core/quality_telemetry.py:321` — build_rollup crashes on any sub-parse error
**Subsystem:** Cognition · **File:** `core/quality_telemetry.py:321`
**Short version:** No per-source try/except; cockpit goes dark on transient log issue.
**Full detail:** `05_cognition.md` → `major`

#### 05-M3 — `core/quality_telemetry.py:268-270` — Unguarded db.close() in finally
**Subsystem:** Cognition · **File:** `core/quality_telemetry.py:268-270`
**Short version:** NameError in finally when connect() raises; masks root cause.
**Full detail:** `05_cognition.md` → `major`

#### 06-M1 — `core/action_engine.py:677-712` — destructive_snapshot return ignored
**Subsystem:** Actions · **File:** `core/action_engine.py:677-712`
**Short version:** Silent `errors` list never checked; commands execute over partial backups.
**Full detail:** `06_actions.md` → `major`

#### 06-M2 — `core/tool_loop.py:165-201` — is_read_only ↔ action_classifier Lane-0 divergence
**Subsystem:** Actions · **File:** `core/tool_loop.py:165-201`
**Short version:** Two sources of truth for "safe to auto-execute"; allowlist vs deny-patterns.
**Full detail:** `06_actions.md` → `major`

#### 07-M1 — `core/temperament.py:254` — `float("nan")` in log output
**Subsystem:** Evolution · **File:** `core/temperament.py:254`
**Short version:** Literal "nan" appears in logs for first-event writes; should be "NULL".
**Full detail:** `07_evolution.md` → `major`

#### 07-M2 — `core/dream_state.py:141-186` — Schema migration missing explicit commit
**Subsystem:** Evolution · **File:** `core/dream_state.py:141-186`
**Short version:** Relies on context manager implicit commit across ALTER TABLE chain.
**Full detail:** `07_evolution.md` → `major`

#### 09-M1 — `core/fabrication_memory.py:98,131,188,216` — Connection leak
**Subsystem:** Learning · **File:** `core/fabrication_memory.py:98,131,188,216`
**Short version:** sqlite3 connections never closed; needs contextlib.closing like consequence_memory.
**Full detail:** `09_learning.md` → `major`

#### 09-M2 — `core/inner_residue.py:102,130,155` — Connection leak
**Subsystem:** Learning · **File:** `core/inner_residue.py:102,130,155`
**Short version:** Same sqlite3 leak; called every cycle turn (highest rate in codebase).
**Full detail:** `09_learning.md` → `major`

#### 10-M1 — `core/llm_client.py:59` — Legacy alias doc ambiguity
**Subsystem:** Model/Support · **File:** `core/llm_client.py:59`
**Short version:** "Legacy override" comment doesn't match actual priority (PRIMARY_MODEL wins).
**Full detail:** `10_model_and_support.md` → `major`

#### 10-M2 — `core/fast_backend_local.py:74-82` — is_available() inconsistent backend awareness
**Subsystem:** Model/Support · **File:** `core/fast_backend_local.py:74-82`
**Short version:** active_backend() called only on llamacpp branch; Ollama fallback hardcoded.
**Full detail:** `10_model_and_support.md` → `major`

#### 10-M3 — `core/capability_registry.py:41` — Hardcoded `_MAEZ_HOME`
**Subsystem:** Model/Support · **File:** `core/capability_registry.py:41`
**Short version:** describe() reports stale grounded facts when MAEZ_HOME differs from /home/rohit/maez.
**Full detail:** `10_model_and_support.md` → `major`

#### X1-M1 — Evolution subsystem — Zero tests for 6/9 modules
**Subsystem:** Tests · **File:** tests/ (missing test_soul_loader/editor/wants/will_i/temperament/dream_state)
**Short version:** soul_loader race (07-B1) would have been caught by any concurrent append test.
**Full detail:** `X1_tests.md` → `major`

#### X1-M2 — command_decomposer + action_classifier untested
**Subsystem:** Tests · **File:** tests/ (missing)
**Short version:** 06-B1 parser blocker and 06-M2 classifier divergence are both unverified.
**Full detail:** `X1_tests.md` → `major`

#### X1-M3 — fast_backend_router + fast_backend_local untested
**Subsystem:** Tests · **File:** tests/ (missing)
**Short version:** 10-B1 policy-gating blocker has no coverage.
**Full detail:** `X1_tests.md` → `major`

#### X1-M4 — test_consequence_memory.py doesn't test token-filter bug
**Subsystem:** Tests · **File:** `tests/test_consequence_memory.py`
**Short version:** 09-B1 would be caught by one hyphenated-token assertion.
**Full detail:** `X1_tests.md` → `major`

#### X1-M5 — test_fabrication_memory + test_inner_residue — leaks unverified
**Subsystem:** Tests · **File:** tests/
**Short version:** No stress test exposes 09-M1/M2 FD exhaustion.
**Full detail:** `X1_tests.md` → `major`

#### X2-M1 — `docs/birth_book/README.md:33` — Birth-event activation drift
**Subsystem:** Documentation
**Short version:** Birth Book exclusion mechanism vs. GESTATION_MEMORY_PROTOCOL memory-phase mechanism describe different triggers.
**Full detail:** `X2_documentation.md` → `major`

#### X2-M2 — `BETA_ARCHITECTURE_DECISIONS.md:70-94` — Revocation-URL mechanism unimplemented
**Subsystem:** Documentation
**Short version:** Tier 2 consent claims "revocation URL + 24-hour SLA"; no code implements it. Covenant-breach risk for beta participants.
**Full detail:** `X2_documentation.md` → `major`

#### X2-M3 — `BETA_ARCHITECTURE_DECISIONS.md:22-58` — Sovereignty framing vs. objective gate mismatch
**Subsystem:** Documentation
**Short version:** Decision 1's "developmental readiness" prose clashes with TRACK_A's objective eight-point gate.
**Full detail:** `X2_documentation.md` → `major`

### minor (28 total)

#### 01-m1 — `core/brain_loop.py:208-209` — Off-by-one in stderr truncation. `01_brain_loop.md` → minor
#### 01-m2 — `core/conversation_controller.py:876-881` — Broad pipeline_getter except. `01_brain_loop.md` → minor
#### 02-m1 — `core/pending_cards.py:299-303` — Silent ALTER TABLE migration. `02_decision_pipeline.md` → minor
#### 02-m2 — `core/decision_pipeline.py:593` — Undefined `logger` in _will_i_check. `02_decision_pipeline.md` → minor
#### 02-m3 — `core/proposal_lookup.py:49,74` — Hardcoded 1.5s sqlite timeout. `02_decision_pipeline.md` → minor
#### 03-m1 — `core/owner_trust.py:150` — Double-space bypasses rm-rf fragment match. `03_safety.md` → minor
#### 03-m2 — `core/injection_patterns.py:177-179` — Base64 threshold (40) too high. `03_safety.md` → minor
#### 04-m1 — `core/memory_manager.py:216-232` — Timestamp tzinfo assumption silent fallback. `04_memory.md` → minor
#### 04-m2 — `core/memory_manager.py:786` — mmr_rerank call unguarded. `04_memory.md` → minor
#### 05-m1 — `core/cognition_quality.py:261-262` — Redundant 'vague' label logic. `05_cognition.md` → minor
#### 05-m2 — `core/audit.py:537-542` — Fragile string-coerced lane check. `05_cognition.md` → minor
#### 06-m1 — `core/command_decomposer.py:183-199` — Missing double-quote state tracking. `06_actions.md` → minor
#### 06-m2 — `core/action_engine.py:827-842` — Weaker secondary covenant gate. `06_actions.md` → minor
#### 07-m1 — `core/wondering_cycle.py:243-250` — `acquired` variable semantics muddled. `07_evolution.md` → minor
#### 07-m2 — `core/temperament.py:1-20` — Docstring says "eleven" but list is twelve. `07_evolution.md` → minor
#### 10-m1 — `core/context_compressor.py:55` — Env vars not in model_config. `10_model_and_support.md` → minor
#### 10-m2 — `core/fast_conversation_log.py:45` — Hardcoded DB path. `10_model_and_support.md` → minor
#### 10-m3 — `core/fast_reply_audit.py:60` — Hardcoded audit path. `10_model_and_support.md` → minor
#### X1-m1 — tool_loop regex bypass unverified. `X1_tests.md` → minor
#### X1-m2 — pending_cards will-I race not tested. `X1_tests.md` → minor
#### X1-m3 — test_self_dev real-DB pollution risk. `X1_tests.md` → minor
#### X1-m4 — approval_sessions integration untested. `X1_tests.md` → minor
#### X1-m5 — quality_telemetry graceful-degradation untested. `X1_tests.md` → minor
#### X1-m6 — cognition_quality ring-buffer recovery untested. `X1_tests.md` → minor
#### X2-m1 — audit index lacks cross-refs to missing design docs. `X2_documentation.md` → minor
#### X2-m2 — subscription_proxy README routing priority buried. `X2_documentation.md` → minor
#### X2-m3 — BETA_READINESS_THRESHOLD missing Decision 1 xref. `X2_documentation.md` → minor
#### X2-m4 — docs/followups has no README/index. `X2_documentation.md` → minor

### nit (22 total)

#### 01-n1 — `core/brain_loop.py:252-253` — Redundant imports inside function. `01_brain_loop.md` → nit
#### 01-n2 — `core/conversation_controller.py:1130-1133` — Defensive getattr clarity. `01_brain_loop.md` → nit
#### 01-n3 — `core/brain_loop.py:659` — recovery_seed type hint missing. `01_brain_loop.md` → nit
#### 02-n1 — `core/pending_cards.py:253` — Unnecessary inline default. `02_decision_pipeline.md` → nit
#### 02-n2 — `core/decision_pipeline.py:268` — plain_english silent discard on validation. `02_decision_pipeline.md` → nit
#### 03-n1 — `core/self_claim_audit.py:388-390` — Docstring doesn't list all modes. `03_safety.md` → nit
#### 03-n2 — `core/context_safety.py:114-134` — "Never raises" invariant needs clarification. `03_safety.md` → nit
#### 04-n1 — `core/continuity.py:76` — Global `_mode_override` init order. `04_memory.md` → nit
#### 04-n2 — `core/memory_scoring.py:416` — Half-life constant lacks evidence trail. `04_memory.md` → nit
#### 05-n1 — `core/observability.py:74-78` — Silent Langfuse host fallback. `05_cognition.md` → nit
#### 06-n1 — `core/tool_loop.py:147-159` — `_ALWAYS_MUTATING` regex lacks descriptor/no-space handling. `06_actions.md` → nit
#### 07-n1 — `core/soul_invariants.py:99-105` — Regex word-boundary hygiene. `07_evolution.md` → nit
#### 09-n1 — `core/consequence_memory.py:170-175` — Unnecessary sorted() on frozenset. `09_learning.md` → nit
#### 09-n2 — `core/error_classifier.py:210,217` — Redundant isinstance + name check. `09_learning.md` → nit
#### 10-n1 — `core/fast_reply_schema.py:201` — Whitelist lacks OWASP citation. `10_model_and_support.md` → nit
#### 10-n2 — `core/public_user_shaping.py:70-90` — Intentional duplication not DRY. `10_model_and_support.md` → nit
#### X1-n1 — Test files lack blocker-citation docstrings. `X1_tests.md` → nit
#### X1-n2 — pytest vs unittest style inconsistency. `X1_tests.md` → nit
#### X1-n3 — Test imports use `from core.X` (Phase 3 fragility). `X1_tests.md` → nit
#### X1-n4 — No pytest-timeout decorator. `X1_tests.md` → nit
#### X2-n1 — Competing "read first" claims in README vs TRACK_A vs ARCHITECTURE. `X2_documentation.md` → nit
#### X2-n2 — docs/governance/ lacks README. `X2_documentation.md` → nit

## Cross-subsystem patterns

The most load-bearing section. Patterns a single-subsystem agent cannot see:

### Pattern 1 — sqlite3 connection lifetime discipline

Review 261a8db flagged sqlite context managers not closing connections. Fix pattern = `contextlib.closing(_ensure_db())`. Application state:

- ✓ **fixed:** consequence_memory.py (181, 212, 239, 327), pending_cards.py (via `with` + commit), self_dev_persistence.py (context managers + commit)
- ✗ **missed fix:** `fabrication_memory.py` (09-M1), `inner_residue.py` (09-M2)
- ✗ **different bug, same family:** `quality_telemetry.py:268-270` (05-M3) — db used in finally without pre-init
- ✗ **no commit, silent loss:** `audit_log.py:283` (05-M1), `dream_state.py:141-186` (07-M2)

Recommendation: one sweep commit standardizing every sqlite call site on `contextlib.closing() + explicit commit`.

### Pattern 2 — Fail-open / "never raises" invariant drift

Multiple modules promise "never raises" in docstrings but don't deliver:

- `cognition_quality.score_and_classify` (05-B1) — ring buffer corrupts on exception
- `quality_telemetry.build_rollup` (05-M2) — any sub-parse error propagates
- `context_safety.scan` (03-n2) — conditional on `str()` coercion succeeding
- `memory_manager._query_collection` indirectly (04-m2) — mmr_rerank import guard doesn't cover call failure
- `audit_log.record` (05-M1) — contract is fail-closed but behavior is fail-silent

Recommendation: audit every module docstring claiming "never raises"; make the invariant structural (wrapped in try/except with guaranteed fallback), not documentary.

### Pattern 3 — Silent `except Exception: pass` sites

Masks root causes. Full list from subsystem reports:

- `core/decision_pipeline.py:302,360,533,626,1003,1029` (consequence_memory record-on-deny swallowed — 02-M1)
- `core/conversation_controller.py:876-881` (pipeline_getter — 01-m2)
- `core/quality_telemetry.py:264,270` (fab snapshot — 05-M3)
- `core/soul_loader.py:119-120` (file-read guard — part of 07-B1 race)
- `core/memory_manager.py` `_age_hours_from_iso` returns 0.0 on any parse failure, silently disabling stale-number penalty (04-m1)

Recommendation: standardize on `except Exception as e: logger.debug(...)` for non-recoverable paths; reserve bare `pass` for truly idempotent no-ops with a `# noqa: intentional` comment.

### Pattern 4 — Hardcoded `/home/rohit/maez` paths

7+ files with hardcoded paths despite `core/paths.py` existing:

- `core/capability_registry.py:41` (10-M3, major — user-visible)
- `core/private_thoughts.py:110-113` (10-B2, blocker — fallback only)
- `core/fast_conversation_log.py:45` (10-m2, minor)
- `core/fast_reply_audit.py:60` (10-m3, minor)
- `core/self_model.py:37-39` (flagged in 10's coverage notes, 3 constants)
- `core/builder_mode_capture.py` (indirect via audit_log)
- `docs/ARCHITECTURE.md:70-88` (X2-B1, user-facing doc)

Recommendation: defer fixing to **Phase 2 "De-Rohit-ify"** migration sweep per the user memory pointer. Do NOT bundle into Phase 1.G — scope creep risk.

### Pattern 5 — Doc-vs-behavior drift

Specific mismatches between documentation and implementation:

- `ARCHITECTURE.md:70-88` promises portability; 7 files hardcode paths (X2-B1)
- `BETA_ARCHITECTURE_DECISIONS.md` Decision 2 describes revocation URLs that don't exist (X2-M2)
- Decision 1 "developmental readiness" vs. TRACK_A "eight-point gate" (X2-M3)
- `birth_book/README.md` vs. `GESTATION_MEMORY_PROTOCOL.md` disagree on Birth Book activation (X2-M1)
- `cognition_quality.py:349` docstring "never raises" vs. ring-buffer corruption (05-B1)
- `self_claim_audit.py:335-343` docstring doesn't list all AuditResult modes (03-n1)
- `temperament.py:3` says "Eleven named parameters"; actual count 12 (07-m2)
- `llm_client.py:52-59` calls MAEZ_LLAMACPP_MODEL "legacy override" but code treats it as secondary (10-M1)

### Pattern 6 — Test coverage concentrated on high-visibility modules; Evolution critically gapped

Evolution subsystem has **6 of 9 modules entirely untested** including soul_loader which contains the 07-B1 race blocker. Actions and Model/Support have **2 and 6+ untested modules** respectively, each containing a blocker. The X1 audit calls this a CRITICAL systemic risk. Pattern: the highest-churn modules (2026-04-20+ era) disproportionately lack tests.

## Recommendations for Phase 1.G (fix-now application)

Grouped into reviewable commit batches:

### Batch A — "sqlite resource management + commits"
Themes: connection lifecycle, atomic writes.
**Findings:** 09-M1 (fabrication_memory), 09-M2 (inner_residue), 05-M3 (quality_telemetry finally block), 05-M1 (audit_log commit), 07-M2 (dream_state migration commit).
**Test updates:** add FD-stress test; add audit_log INSERT-failure test.

### Batch B — "card state & will-I race"
Themes: decision pipeline correctness; atomic state transitions.
**Findings:** 02-B1 (will-I post-approval race), 02-M1 (consequence_memory silent-fail), 02-M2 (dialog _SyntheticCls audit_request_id), 02-m2 (undefined logger), 05-B1 (cognition_quality ring buffer).
**Test updates:** add will-I race regression test (X1-m2); ring-buffer recovery test (X1-m6).

### Batch C — "brain loop + retrieval correctness"
Themes: NameError crashes + retrieval gaps.
**Findings:** 01-B1 (bare self), 01-M2 (relative path + timeout), 01-M1 / 09-B1 (consequence_memory token filter — both fixed in one line change), 01-m1 (stderr truncation order).
**Test updates:** add hyphen-token retrieval test (X1-M4).

### Batch D — "action/command safety"
Themes: parser correctness, snapshot integrity, Lane-0 unification.
**Findings:** 06-B1 (backtick escape), 06-M1 (snapshot errors ignored), 06-M2 (tool_loop vs classifier divergence), 06-m1 (double-quote state), 03-m1 (owner_trust spaces).
**Test updates:** create test_command_decomposer.py + test_action_classifier.py (X1-M2).

### Batch E — "routing policy correctness + critical path hardening"
Themes: model routing policy, soul race.
**Findings:** 10-B1 (silent routing fallback), 10-B2 (private_thoughts fallback — move to paths.py), 10-M2 (fast_backend_local is_available), 07-B1 (soul_loader race), 07-M1 (temperament NaN log).
**Test updates:** create test_fast_backend_router.py (X1-M3); create test_soul_loader.py (X1-M1).

### Batch F — "documentation triage (fix-now subset only)"
Themes: doc-vs-behavior drift that misleads beta participants.
**Findings:** X2-B1 (portability note in ARCHITECTURE.md), X2-B2 (acceptance gate summary in TRACK_A.md), X2-M2 (revocation-URL disclaimer in Decision 2).
**Defer:** X2-M1, X2-M3, X2-m*, X2-n* — absorbed into Phase 6 doc coverage.

## Items to explicitly defer to later phases

- **All `/home/rohit/maez` hardcoded-path findings except 10-B2 fallback** — batched into Phase 2 "De-Rohit-ify." Includes 10-M3, 10-m2, 10-m3, self_model.py refs. Rationale: atomic migration via paths.py is cleaner than scattered edits in Phase 1.G.
- **Test-coverage backfill beyond the blocker-regression tests in Batches A-E** — Phase 5. Includes X1-n1 through X1-n4, evolution test writeup beyond soul_loader, and fast_reply_* suite.
- **Subsystem design docs** (9 missing) — Phase 6. X2-m1 and the X2 "coverage gaps" section.
- **Nit-level findings** not clustering into a theme — deferred. 22 nits total; none reopens a blocker.
- **Governance polish** (X2-n2 governance README, X2-M1 birth-book xref) — Phase 6.
- **Minor doc cross-references** (X2-m2, X2-m3, X2-m4, X2-n1) — Phase 6 launch polish.

Reason: scope discipline. Phase 1.G covers blockers + high-leverage majors; Phase 2 handles de-Rohit-ify; Phase 5/6 close the test + doc gaps.

---

**Footnote on counts:** This consolidation reports 12 blockers / 23 majors / 28 minors / 22 nits = 85 total, matching `_INDEX.md` authoritative totals exactly. 01-M1 and 09-B1 describe the same underlying `consequence_memory.py:290` bug from two lenses (major from brain_loop's caller perspective, blocker from learning's module-owner perspective) and are counted once each per subsystem in the index; they share a single fix in Batch C.
