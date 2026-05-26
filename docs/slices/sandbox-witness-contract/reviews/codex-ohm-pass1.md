# Codex Engineering Pass-1 — Ohm Seat

**Artifact:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.1 at `711d405`
**Verdict:** RATIFY-WITH-AMENDMENTS

## Findings

- [Major] `MAEZ_SUBSTRATE_ROOT` is not currently a real path override
  Section: I8 lines 100-106; W#8a lines 289-290
  Evidence: `core/infra/paths.py:49-78` recognizes `MAEZ_HOME`, `MAEZ_CONFIG`, `MAEZ_DATA`, `MAEZ_CACHE`; `rg MAEZ_SUBSTRATE_ROOT` finds only this spec/review text. Store helpers then derive from `memory_dir()` at `core/infra/paths.py:113-155`.
  Implementation risk: The child process can be launched with `MAEZ_SUBSTRATE_ROOT=/tmp/...` and still resolve live `memory/*.db`.
  Concrete failure mode: `MaintenanceProposals()` in re-verification opens live `memory/maintenance_proposals.db` via `paths.maintenance_proposals_db()` despite the sandbox-root env being set.
  Required fold: Define `MAEZ_SUBSTRATE_ROOT` at the path-helper layer, including precedence versus `MAEZ_HOME`, `MAEZ_DATA`, and store-specific overrides, or rename the contract to use existing env vars. Require a startup assertion in the re-verifier that every registered substrate path resolves under the scratch root before importing witness code.
  Test implication: W#8a must assert path resolution, not just env presence: spawn child with only `MAEZ_SUBSTRATE_ROOT`, import `core.paths`, instantiate representative stores, and prove resolved DB paths are scratch-prefixed.

- [Major] Import-time DB constants can freeze live paths before locus checks
  Section: I8 lines 100-106; SubstrateLocus lines 179-186; W#8/W#8a lines 289-290
  Evidence: `core/evolution/temperament.py:112-193` caches `DEFAULT_DB_PATH`; `core/evolution/subjective_duration.py:22` imports `TEMPERAMENT_DB_PATH`, then reads it at `core/evolution/subjective_duration.py:273-278`; `core/cognition/audit_log.py:80-193`, `core/decision/pending_cards.py:80-81`, `core/learning/consequence_memory.py:86-106`, and `core/memory/memory_scoring.py:68-170` all cache defaults at import time. Several open SQLite with `check_same_thread=False`.
  Implementation risk: Subprocess isolation is only strong if the child is exec-style and env is set before imports. A forked child or preloaded module can keep live paths and possibly live handles/module state.
  Concrete failure mode: Parent imports `temperament`; verifier forks; child has `DEFAULT_DB_PATH=/home/rohit/maez/memory/temperament.db`; re-verification reads or initializes live temperament despite `MAEZ_SUBSTRATE_ROOT`.
  Required fold: Specify exec-style subprocess launch (`subprocess.run`/fresh interpreter, `close_fds=True`, no inherited handles), env set before any Maez imports, and a re-verifier import discipline that refuses if known path constants resolve outside scratch.
  Test implication: Add W#8b or expand W#8a: pre-import a module in parent, launch verifier, and assert the child reports scratch paths and no inherited FD points at live `memory/*.db`, `*-wal`, or `*-shm`.

- [Major] `SubstrateLocus` coverage is too partial for actual substrate handles
  Section: SubstrateLocus lines 179-186; I8 lines 100-106; W#8 lines 289
  Evidence: v1.1 lists `LIVE_WONDERINGS`, `LIVE_TEMPERAMENT`, `LIVE_SUBJECTIVE_DURATION`, `LIVE_MAINTENANCE_PROPOSALS`, then ellipsis. Actual handle surfaces include `audit_log.db` (`core/cognition/audit_log.py:69-80`), `pending_cards.db` (`core/decision/pending_cards.py:70-81`), `entity_index.db` (`core/memory/entity_index.py:51-63`), `recall_stats.db` (`core/memory/memory_scoring.py:68-70`), `fabrication_log.db` (`core/learning/fabrication_memory.py:44-63`), `consequence_memory.db` (`core/learning/consequence_memory.py:66-86`), `action_trust.db` (`core/actions/action_engine.py:24-30`, `373-423`), plus self-dev/workshop DBs.
  Implementation risk: A closed enum with ellipsis becomes a partial denylist; unregistered live DBs bypass locus enforcement.
  Concrete failure mode: Re-verifier imports a reader that opens `AuditLog()` or `EntityIndex()`; because no locus exists for that handle, the registry does not classify it as `LIVE_*`, so W#8 passes while live state was touched.
  Required fold: Replace ellipsis with an explicit v1 registry: every DB/file path helper and every known hardcoded `memory/*.db` default maps to one `SubstrateLocus`; unregistered substrate opens refuse by default.
  Test implication: W#8 needs a static coverage test over `core.paths` helpers plus `rg`-discovered `memory/*.db` defaults, and a runtime monkeypatch around `sqlite3.connect`/store constructors that fails on any unregistered path.

- [Major] `DB_CURSOR = SELECT MAX(rowid)` is underspecified under multi-table and WAL concurrency
  Section: StalenessAnchorKind lines 145-161; I5 lines 78-82; W#5a lines 278-280
  Evidence: The spec names `SELECT MAX(rowid) on referenced live DBs`, but actual DBs are multi-table and append-only shapes vary. `maintenance_proposals` has one table today (`core/policies/maintenance_proposals.py:124-149`), while `wonderings` has `wonderings` and `wondering_probes` (`core/evolution/wonderings.py:175-205`), and WAL behavior is explicitly connection-scoped in existing tests (`tests/test_ledger_wal.py:13-21`, `91-102`).
  Implementation risk: Cursor comparison can miss writes to non-selected tables, read a stale snapshot, or define different cursors per implementer.
  Concrete failure mode: Witness captures `MAX(rowid)` from `wonderings`; live daemon appends `wondering_probes`; ratify-time cursor unchanged if implementation only checks the primary table, so stale witness ratifies.
  Required fold: Define a per-locus cursor function: exact tables, SQL, transaction mode, WAL checkpoint/snapshot semantics, missing-table behavior, and whether cursor is over live DB or scratch copy. Prefer a deterministic tuple such as `{table: max(rowid/count/last_updated)}` for each registered locus.
  Test implication: W#5a must append to a secondary table and to a concurrently open WAL writer, then prove stale detection fires from a fresh read-only connection.

- [Minor] Ratification-time cost model conflates anchor comparison, subprocess startup, and full re-execution
  Section: I5 lines 80-82; Lifecycle lines 222-228; Q2 lines 303-305; implementability split lines 297
  Evidence: v1.1 says anchor comparison is 10-50ms, but lifecycle says re-verification recomputes isolation, test outcomes, observed_effect, and staleness anchors. W#8* requires subprocess scaffolding.
  Implementation risk: Implementers may either re-run expensive tests at ratification time when only freshness check was intended, or only compare anchors when full attach-time re-verification was intended.
  Concrete failure mode: A proposal with a stale but previously passing worktree witness reaches ratification; implementation does only "witness exists" plus no full subprocess, missing changed artifacts.
  Required fold: Split operations explicitly: attach-time full subprocess re-verification; ratify-time freshness/locus check; optional full re-run policy. Name expected cost for each.
  Test implication: W#8a should count one subprocess for attach-time verification; W#5 should exercise ratify-time anchor comparison without rerunning the full RED suite unless the spec intentionally requires it.

## Open Questions

- Should store-specific overrides like `MAEZ_TEMPERAMENT_PATH`, `MAEZ_AUDIT_LOG_PATH`, and `MAEZ_CONSEQUENCE_MEMORY_DB` be forbidden inside witness subprocesses, or remapped through `MAEZ_SUBSTRATE_ROOT`?
- Is `DRY_RUN_OBSERVATION` allowed to read live DBs through read-only handles, or must it operate only on captured scratch snapshots? Current I8 says read-only live is allowed, but SubstrateLocus says re-verification handles only `SCRATCH_*`; that needs one implementable answer.

