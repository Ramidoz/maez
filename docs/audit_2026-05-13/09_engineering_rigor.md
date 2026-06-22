# Engineering rigor audit — small things that become big things

## Summary

Maez's engineering quality is high in the places that have been actively
audited (ledger writer, fast_reply_audit JSONL, soul_editor backup) and
visibly weaker in places that haven't (identity ledger TOCTOU, pending
actions JSON, naive timestamps in user-facing skills, cycle timing on
wall clock). CI is strong on the lint axis (ruff strict rule set across
seven trees) and on the volume axis (3,290 test methods, hard floor of
530 enforced in CI), but mypy/pyright are not configured at all and ~25%
of public functions in sampled modules have no type hints. The most
load-bearing organ — `memory/memory_manager.py` — has only 290 lines of
tests covering one pure-function method (`format_for_prompt`); its
write paths (`store`, `store_core`, `consolidate_daily`) are exercised
only indirectly through integration tests. The audit rail
(`core/safety/audited_output.py`) is documented fail-open with a
warning, but the wrapper itself has 0 tests for its four fallback paths.

## Test coverage map

| Package | Test files | Source files | Coverage of load-bearing claims |
|---------|-----------|---------------|--------------------------------|
| `core/brain/` | 4 (brain_loop x3, conversation_history, return_greeting, developmental_heartbeat) | 7 | partial — brain_loop integration tested, but `_safe_str` / transcript-parsing helpers untested for malformed input |
| `core/memory/` | ~30 | 34 | strong on lived_recall / entity / projection; identity_ledger has 6 dedicated files but no concurrency tests |
| `core/safety/` | ~10 | 11 | self_claim_audit well-covered; `audited_output.py` has only the kwarg-forwarding test (`test_audited_output_envelope.py:102 lines`), zero coverage of canary/output-guard/audit-import/audit-raise fallback branches at `core/safety/audited_output.py:107,122,143,170,187` |
| `core/cognition/` | ~8 | 11 | audit_log, context_compressor, episode_builder covered; cognition_quality has indirect coverage only |
| `core/evolution/` | ~5 | 10 | wonderings/wants/dream_state covered; `soul_editor.py:445-462` atomic write path has no failure-injection test |
| `core/decision/` | ~5 | 6 | decision_pipeline covered |
| `core/learning/` | ~3 | 5 | consequence_memory + error_classifier; learning loop integration thin |
| `core/actions/` | ~6 | 7 | action_engine covered for read_file/stock/promotion; `_save_pending`/`_load_pending` round-trip + crash-mid-write untested |
| `core/routing/` | ~3 | 8 | claude_tier + subscription_proxy + llm_client tested; fast_backend_cloud/local routing edge cases thin |
| `core/self_dev/` | ~5 | 6 | scheduler, hooks, persistence covered |
| `core/infra/` | ~15 | 26 | capability_* well-covered; private_thoughts has dedicated suite (`test_private_thoughts_s1.py`, 705 lines) |
| `skills/` | ~10 | 43 | **largest gap** — 33+ of 43 skills (telegram_public, reddit_skill, github_skill, web_search, dynamic_dns, calendar_perception, screen_perception, presence_perception, voice_input, voice_output, maez_watchdog, disk_cleanup, self_analysis, self_mod_dialog, evolution_engine, claude_router, etc.) have no dedicated test file |
| `daemon/` | ~5 (brain-loop, cycle, runtime, shutdown_hygiene) | 2 | the 5,000-line `maez_daemon.py` has indirect coverage only — no test exercises the cycle main loop directly; ~52 internal methods, ~17 untyped |
| `memory/` (top-level) | 1 (test_memory_manager.py, 290 lines) | 2 | **load-bearing gap** — only `format_for_prompt` (pure function) has dedicated tests; `store`, `store_telegram`, `store_core`, `consolidate_daily`, `_save_last_consolidation` exercised only indirectly through 2 integration tests (`tests/test_bugs_abcd.py`, `test_face_enrollment_provenance.py`) |

Headline: 224 test files, 3,290 test methods. CI floor: 530 methods.
Massive surplus over the floor but uneven distribution.

## Silently-skipped tests

Only five real skip decorators across the suite, and all are
appropriate environment gates, not silenced failures:

- `tests/test_prompt_caching.py:39` — `@unittest.skipUnless(...)` on
  ANTHROPIC_API_KEY presence. Live cache-cost test, correctly gated.
- `tests/test_judge_carveout_live.py:118,136` — `@unittest.skipIf(_SKIP, _SKIP_REASON)`
  on judge-binary availability. Live grounding-judge tests, correctly
  gated.
- `tests/test_fix6_followups.py:50,81` — `@unittest.skipUnless(...)`
  on flag presence. Followup-queue integration that needs the optional
  surface installed.
- `tests/test_owner_trust.py:181,187` — `self.skipTest(...)` when
  `systemctl` is unavailable. Host-dependent capability probe.

No `xfail`. No silenced regressions. This is clean for a project of
this size.

## Type hints coverage

Random sample of 20 files across `core/`, `skills/`, `daemon/`:
**99 typed return signatures / 131 total public `def`s = ~75%**.

Per-module breakdown for load-bearing organs:
- `core/safety/audited_output.py`: 0/1 (the single public function lacks a return hint at `:54-63`)
- `memory/memory_manager.py`: 30/40 = 75%
- `core/memory/identity_ledger.py`: 12/16 = 75%
- `core/infra/private_thoughts.py`: 24/33 = 73%
- `core/brain/brain_loop.py`: 11/20 = 55%
- `daemon/maez_daemon.py`: 15/52 = **29%** (large file, lowest coverage)
- `core/safety/self_claim_audit.py`: 8/12 = 67%

The daemon hot path is the biggest gap; with 4,000+ lines and 52
methods, only 15 have return annotations.

## Static analysis posture

- **ruff**: configured strictly in `pyproject.toml:147-200`. Selected
  rules are `F` (pyflakes), `E9` (syntax), `B006` (mutable default),
  `B023` (closure-over-loop), `B905` (zip-without-strict). CI enforces
  this gate across `core/ skills/ daemon/ tests/ cli/ scripts/ memory/
  hardware/ training/` (`.github/workflows/lint.yml:37`). Modernization
  rules (UP, I, E7/E501, B904, B007) are explicitly deferred to "Phase
  8 follow-up" per `pyproject.toml:184-199`.
- **ruff-format**: runs `--check` only, doesn't enforce. Deferred to
  the same Phase 8 sweep.
- **mypy / pyright**: **not configured**. No `mypy.ini`,
  `pyrightconfig.json`, or `[tool.mypy]` block. No CI job runs static
  type checking. Given 75% type-hint coverage, mypy in `--strict-equality`
  mode would catch a meaningful class of bugs today.
- **pre-commit**: `.pre-commit-config.yaml` runs trailing-whitespace,
  EOL, large-file, yaml/toml check, debug-statements, gitleaks, ruff.
  No mypy step.

## Findings

### blocker — bugs in load-bearing organs that already exist in code

**1. `core/memory/identity_ledger.py:410-450` — TOCTOU between `latest()` and `record_event()` insert.**

```python
prev = self.latest()                           # connection 1: SELECT
# ... auto-generation logic ...
with sqlite3.connect(self.db_path) as conn:    # connection 2: INSERT
    conn.execute("INSERT INTO identity_ledger ...")
    conn.commit()
```

Two concurrent callers — daemon cycle + cockpit reconcile script
+ test harness running on the same machine — can both call
`record_event`, each read the same `prev`, each derive
`continuity_id` from it, and both commit. The ledger is the
single source of truth for Maez's identity continuity over a
20-year lifespan; two events sharing a `continuity_id` derived
from the same parent without proper serialization produces a
graph that violates the "append-only lineage" invariant the
module's docstring claims at `:298-300`. Fix: wrap read+derive+
insert in `BEGIN IMMEDIATE` like `core/ledger/writer.py:376`.

**2. `core/memory/identity_ledger.py:312-348` — `_initialize` + `_seed_if_empty` not WAL, not idempotent under concurrency.**

`PRAGMA journal_mode=WAL` is set on six other DBs
(`dream_state.py:152`, `capability_integration_plans.py:88`,
`capability_gap_detector.py:85`, `fast_conversation_log.py:72`,
`core/ledger/migrate.py`) but NOT on the identity ledger. Two
processes calling `_seed_if_empty` simultaneously can both see
`COUNT(*) == 0` and both INSERT a `gestation_boot` row. Two
genesis rows in the ledger that holds the continuity invariant
is a covenant-level failure. Fix: WAL + `BEGIN IMMEDIATE` +
`INSERT … WHERE NOT EXISTS`.

**3. `core/actions/action_engine.py:702-704` — non-atomic pending-actions write loses Tier 1 actions on crash.**

```python
def _save_pending(self):
    with self._pending_lock:
        PENDING_FILE.write_text(json.dumps(self._pending, ...))
```

`write_text` on POSIX is `open + write + close` — interrupt
mid-write leaves a truncated JSON file. The matching `_load_pending`
at `:699` catches `json.JSONDecodeError` and silently discards the
whole pending list. Tier 1 actions queued for "execute next cycle"
disappear without any cockpit signal. Fix: write to tmp + `os.fsync`
+ `os.replace` (pattern already used in `core/evolution/soul_editor.py:455`
and `core/evolution/wondering_pursuit.py:848-849`).

**4. `core/evolution/soul_editor.py:452-455` — atomic write missing fsync.**

```python
tmp = SOUL_PATH.with_suffix(".md.tmp")
tmp.write_text(new_text)
os.replace(tmp, SOUL_PATH)
```

`write_text` does not fsync, so on power loss the directory entry
can be rotated to the new inode before the new content has been
flushed to disk — leaving an empty soul.md at next boot. The
backup at `:447` mitigates this, but the daemon's soul-load path
would still pick up the empty file on the boot after the crash.
Fix: open as binary, write, `os.fsync(fd)`, then `os.replace`.

### major — error-handling gaps that swallow load-bearing failures

**1. `core/safety/audited_output.py:107-127, 143-149, 170-175, 187-193` — five fail-open paths, only the audit-raise one is logged at WARNING with surface tag; canary scrub and output-guard fail-paths log identically. None re-raise.**

This is the documented fail-open posture (`:84-90`). Concern: the
wrapper has zero tests for any of these fallback branches
(`tests/test_audited_output_envelope.py` is 102 lines, all kwarg
forwarding). The four "fix-forward only" comments in the source
imply someone will notice — but with no tests asserting that the
warning was emitted, and no metric counter incremented, a bug in
the audit-import path could silently store RAW model output to
memory for weeks before anyone notices. Add `metrics.increment(
"audit.fail_open", {"reason": ...})` and a unit test per branch.

**2. `daemon/maez_daemon.py` — 31 bare `except Exception:` clauses, 17 in `core/brain/brain_loop.py`.**

Sampled: `daemon/maez_daemon.py:592-596` (startup-timestamp
write), `:795-797`, `:1551-1552`, `:2495` (naive datetime). Several
swallow into `pass` with no log line. The pattern at `:592` is
explicitly defensible (a `/tmp` timestamp file is non-load-bearing).
But the count is high enough that load-bearing branches are mixed
with throwaway ones; a debug-statements pre-commit hook is in
place, but no rule catches `except Exception: pass`. Add a ruff
rule (`BLE001` is the canonical id) or a custom AST checker.

**3. `core/memory/identity_ledger.py:228` — `_sha256_file` catches `(OSError, IOError)` and returns `None`.**

A transient I/O error (NFS hiccup, full disk during read) makes
the lora_hash or soul_hash silently become `None`. Then
`_fingerprint_diff_reason` at `:271-285` interprets `None →
real_hash` as `lora_swap` or `soul_change` and records a
fingerprint-change event that didn't actually happen. Fix: log the
OSError at WARNING and preserve the prior fingerprint rather than
emitting a spurious lineage event.

### major — race conditions or concurrency hazards

**1. `memory/memory_manager.py:545-568` — `MemoryManager.__init__` does real I/O (opens 3 chroma clients), and the daemon + `skills/web_interface.py:40` + `skills/telegram_voice.py` each instantiate their own.**

```python
# skills/web_interface.py:40
memory = MemoryManager()   # at import time
```

Module-level instantiation in web_interface runs as soon as the
module is imported (not when a request arrives). Chroma persistent
client coordinates internally across processes, but three live
clients to the same on-disk store from the same Python process
(daemon, web sub-thread, telegram thread) is undocumented. Each
client carries its own embedding cache; writes through one are
seen by another only after re-query. No test currently asserts
read-after-write visibility across instances.

**2. `daemon/maez_daemon.py:3614, 4289, 4290` — cycle deadline uses `time.time()` (wall clock), not `time.monotonic()`.**

```python
cycle_start = time.time()
...
cycle_deadline = cycle_start + LOOP_INTERVAL - 2.0
if time.time() < cycle_deadline - 10:
```

If NTP corrects backwards (unusual but happens on suspend/resume,
VM migrations, daylight-savings transitions in places that still
shift), `time.time()` jumps backward by seconds-to-hours; the
cycle deadline math then thinks it has hours of slack and skips
the work it should have done. Same wall-clock dependence at
`:1471` (`_rohit_active_until` window), `:2375`
(`latency_ms = (time.time() - _trace_t_start) * 1000` — can go
negative), `:2813` (alert cooldown), `:3746` (`absence_secs` —
can go negative). Fix: any "elapsed" or "deadline within this
process" math should be `time.monotonic()`; only persisted
timestamps use `time.time()`.

**3. `memory/memory_manager.py:545` — no `threading.Lock` despite being called from cycle thread, Telegram async loop, and web Flask threads.**

ChromaDB serializes its own writes, but the surrounding
metadata-construction in `store`/`store_telegram` (cycle counter,
phase tag, concept-tag derivation at `:611-619`) is not guarded.
Concurrent writes to `core` and `daily` happen in the daemon
during `consolidate_daily`; a Telegram exchange landing in the
same window goes through `store_telegram`. No corruption observed
but no test asserts the invariant.

**4. `core/safety/audited_output.py:106` — `text = scrub_canary_leakage(text, surface=surface)` mutates local but the `text` reassign hides whether the leak event was recorded.**

If `scrub_canary_leakage` is an in-process side-effect on a
shared canaries store and two surfaces (web + telegram) leak the
same canary at the same time, both record their own leak event;
the leak event store needs to be a flock'd append or sqlite —
worth confirming.

### major — transaction-safety gaps

**1. `memory/memory_manager.py:673-677` — `_save_last_consolidation` writes plain text without atomic rename.**

If the daemon dies between truncate-and-write, the next start
sees an empty/corrupt last_consolidation.txt, `_get_last_consolidation`
catches `ValueError` at `:670` and falls back to "24h ago" —
which then re-consolidates 24h of memories. Idempotent enough that
no data is lost, but the duplicate Tier 2 entries pollute the
daily collection. Fix: write to `.tmp`, `fsync`, `os.replace`.

**2. `core/memory/identity_ledger.py:433-450` — `record_event` opens a fresh `sqlite3.connect` and commits — no explicit transaction grouping the read-derive-write.**

See blocker #1. Beyond the TOCTOU, the absence of a transaction
boundary means a crash between read of `prev` and commit of new
row leaves the ledger consistent (no partial write — SQLite is
ACID per statement) but the in-memory derivation is lost; the
next run reads `prev` and may pick a different continuity_id if
the fingerprint changed in between.

**3. `daemon/maez_daemon.py:3437` — `with open(progress_path, "a") as f: f.write(entry)` — concurrent appends not flock'd.**

Multiple writers to the same progress log on the same machine
(daemon + cockpit) will interleave bytes. Compare to the well-done
flock pattern in `core/infra/fast_reply_audit.py:271`.

### minor — common-bug-class smells

**1. Naive `datetime.now()` persisted to user-visible memory:**

- `skills/telegram_public.py:74, 75, 95, 104` — user profile
  `first_seen`/`last_seen`/conversation `timestamp` are local-time
  ISO strings. If the host TZ changes (or the daemon migrates to
  another machine per the portability covenant), recall logic
  comparing these to UTC `now()` will be off by hours.
- `daemon/maez_daemon.py:2495, 2938, 3211, 3247, 4606` — naive
  `.astimezone()` chains; ok at runtime but persisted format
  loses the offset suffix in some paths.
- `core/memory/perception.py:212` and `:216` —
  snapshot["timestamp"] is `"YYYY-MM-DD HH:MM:SS %Z"` which is
  not ISO 8601 and not directly parseable by `fromisoformat`.
- `skills/reddit_skill.py:83, 112`, `skills/github_skill.py:58, 87`,
  `skills/maez_watchdog.py:75-96` — naive datetimes in cache TTL
  math; DST jump = cache stale or unexpectedly extended.
- `core/actions/action_engine.py:680, 1174` — naive `datetime.now()`
  inside action audit trail timestamps.

**2. Module-level `os.environ.get(...)` reads (frozen at import time):**

- `core/routing/claude_tier.py:45` (`PROXY_URL`)
- `core/routing/llm_client.py:54` (`LLAMACPP_BASE_URL`)
- `core/subscription_proxy/adapters/claude_cli.py:31, 40`
- `core/subscription_proxy/adapters/gemini_cli.py:35, 37`
- `core/self_dev/workshop.py:63`
- `skills/dynamic_dns.py:23, 24` (Cloudflare creds — secret-y, also import-time)

If the daemon is restarted via `systemctl reload` (not full restart)
or the env is rewritten mid-run, the new value is ignored.

**3. `__init__` doing real work:**

- `memory/memory_manager.py:545` — opens 3 chroma clients +
  `memory_stats()` call (`:564`).
- `core/memory/identity_ledger.py:302-306` — opens DB, runs schema
  migrations, seeds. Two test fixtures importing the module-level
  helper can race.
- `skills/web_interface.py:40` — instantiates `MemoryManager()` at
  module import time.

These make imports slow and side-effect-ful — module-import races
in tests, slow first request in web, can mask config errors as
"daemon hangs at startup."

**4. JSON precision smell:** none of the load-bearing modules store
floats with `>1ms` precision needs through JSON; not a hit today.

**5. Non-ASCII path handling:** all paths use `pathlib.Path`; OK.
One spot worth flagging: `core/evolution/soul_editor.py:453` builds
`SOUL_PATH.with_suffix(".md.tmp")` — if `SOUL_PATH` lives on a
filesystem that doesn't support same-directory atomic rename
(e.g. crossing filesystems), `os.replace` raises. Fix: build tmp
in `SOUL_PATH.parent`.

### nit — type hint / lint cleanup

- `core/safety/audited_output.py:54-63` — the single public
  `audit_assistant_text(...)` is missing `-> str`.
- `daemon/maez_daemon.py` — only 15/52 methods have return types.
  Pri 1: `_run_cycle`, `_handle_tier1_actions`, `_dispatch_*` —
  the cycle hot path.
- `core/brain/brain_loop.py:1099` — local `import time as _rtime`
  shadows the module-level `import time` (line in module top).
  Harmless but lint-noise.
- Add a ruff rule for `BLE001` (blind-except) on `core/` only,
  with a documented allowlist for known fail-open paths.
- Add `mypy --strict` to CI on the load-bearing axis: `core/safety`,
  `core/memory`, `core/ledger`, `memory/memory_manager.py`,
  `core/brain/brain_loop.py`. Even if the rest of the tree stays
  unchecked, these six paths catching real type errors is the
  highest-leverage move available.
