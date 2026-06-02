# Test-Hermeticity (maez.log) v0 — Design

**Date:** 2026-06-02
**Status:** Draft under review (owner review pending before plan/Codex)
**Scope (narrow, owner-set):** *Stop tests from writing to the production `logs/maez.log`.* The body's real diary and the rehearsal must not be the same notebook — so that reflection/dream/atlas work can trust live telemetry. Live daemon logging unchanged.

---

## 1. Root cause (confirmed)

`daemon/maez_daemon.py:2267-2275` attaches a `RotatingFileHandler(LOG_PATH=logs/maez.log)` to the `maez` logger (`logging.getLogger("maez")`, :2249) **at module import** — not inside a function. So importing the daemon (e.g. a test's `from daemon.maez_daemon import _run_reflection_synthesis_nightly`) opens the production log, and the `maez.*` child loggers propagate up to it. The 2026-06-02 sleep-organ stock-take saw this directly: test runs wrote `reflection_synthesis`, `consolidation_telemetry`, and `Daily consolidation stored … 7 chars` lines into the live log, producing two false alarms (a "reflection firing while dormant" scare and a "consolidation produces garbage" scare — both were test pollution; the real organs are healthy).

The `stream_handler` at :2277-2281 is stderr-only (harmless). The :8643 handler is also stderr. So **2267-2275 is the sole import-time `maez.log` writer.**

---

## 2. The change (Approach 1 — test-mode guard; live byte-identical)

**Env var:** `MAEZ_DISABLE_FILE_LOG=1`.

1. **Guard the file handler** in `daemon/maez_daemon.py` — wrap only the create+attach (2267-2275) so it is skipped when the env var is set:

```python
if not (os.environ.get("MAEZ_DISABLE_FILE_LOG", "") or "").strip():
    file_handler = _logging_handlers.RotatingFileHandler(
        LOG_PATH, maxBytes=50 * 1024 * 1024, backupCount=10,
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(file_handler)
```

The `stream_handler` (stderr) stays **unconditional** — telemetry remains visible during test debugging (the "speak on stage" channel). `os` is already imported in the daemon.

2. **Set the env in the test harness** — `tests/__init__.py` adds one line, matching the existing `setdefault` pattern it already uses for `MAEZ_ROUTING_OBSERVATION_DB_PATH`:

```python
os.environ.setdefault("MAEZ_DISABLE_FILE_LOG", "1")
```

This runs at test-package import — before any test module imports the daemon — so the guard sees it. `setdefault` means a developer can still opt back into file logging by exporting the var explicitly.

**Live daemon:** env unset → the file handler attaches exactly as today. No deferral, no move, byte-identical live behavior. No risk of a missed entrypoint dropping live logging (the reason Approach 2 / defer-to-`main()` was rejected).

---

## 3. Tests

In a new `tests/test_log_hermeticity.py` (runs under the test harness, so `MAEZ_DISABLE_FILE_LOG=1` is already set):

1. **Mechanism test:** after `import daemon.maez_daemon`, assert no handler on `logging.getLogger("maez")` has `getattr(h, "baseFilename", None) == str(LOG_PATH)`. (Pins that the file handler is absent in test mode.)
2. **Outcome test (load-bearing):** snapshot `logs/maez.log` `(st_size, st_mtime_ns)`; drive `_run_reflection_synthesis_nightly(SimpleNamespace(lived_episodes=_FakeEpisodeStore()), llm_call=lambda *a, **k: "[]", artifact_dir=<temp>)` with `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1`; assert the production `logs/maez.log` is **unchanged** (same size + mtime). If the log file doesn't exist, assert it still doesn't after. This proves the *outcome* — tests don't touch the real diary — not just the handler config.

(Reuse `_FakeEpisodeStore`/`SimpleNamespace` from `tests/test_reflection_dry_run_wiring.py`.)

---

## 4. Unchanged

- Live daemon logging (file + stderr) when `MAEZ_DISABLE_FILE_LOG` is unset — byte-identical.
- The `stream_handler` (stderr) in all modes.
- Rotation config, formatter, logger names, propagation.
- All organ behavior — this is logging plumbing only.

---

## 5. Non-goals

- NOT deferring logging setup into `main()` (Approach 2 — rejected: risks a missed live entrypoint silently dropping file logging).
- NOT a temp-file redirect for test logs (disable entirely; stderr remains — no new temp-log surface for tests to depend on).
- NOT touching other file loggers (`core/actions/action_engine.py` `ACTIONS_LOG`, `core/self_dev` `basicConfig`) — different files, out of scope; this slice is the `maez.log` leak that caused the false alarms.
- NOT changing live daemon behavior in any way when the env var is absent.
- NOT a guarantee for bare-script test invocation (`python tests/foo.py` without the package) — the harness convention is `.venv/bin/python -m unittest`, which imports `tests/__init__.py` first. (Minor caveat, documented.)
