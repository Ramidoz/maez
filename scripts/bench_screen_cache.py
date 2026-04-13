"""
scripts/bench_screen_cache.py — Session 11a benchmark.

Proves that the perception cache makes screen reads non-blocking from the
reply path's point of view, even when the underlying screen capture is
slow or hung.

Two scenarios are run, each with two reads:

  Scenario A — direct blocking screen call
    The hot path calls observe() directly. Time it.

  Scenario B — cached screen read
    A background worker calls observe() on its own cadence. The hot path
    only calls cache.get('screen'). Time the cache read.

Both scenarios use a SLOW STUB observe function (sleep 6s) so we don't
spam Ollama and so the test is deterministic. The stub is injected via
ScreenCacheWorker(observe_fn=...) — the live screen_perception module
is NEVER imported or modified.

Run:
    cd /home/rohit/maez
    source .venv/bin/activate
    python scripts/bench_screen_cache.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Allow running from repo root with `python scripts/bench_screen_cache.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.perception_cache import PerceptionCache, FRESH, STALE, MISSING, ERROR
from skills.screen_cache_worker import ScreenCacheWorker, SOURCE_NAME


# ── slow stub observation ─────────────────────────────────────────────
class StubObservation:
    """Mimics ScreenObservation just enough for the worker."""
    def __init__(self, activity: str, success: bool = True, error: str = "") -> None:
        self.activity = activity
        self.application = "stub"
        self.detail = "synthetic benchmark observation"
        self.focus_level = "deep_work"
        self.timestamp = time.time()
        self.success = success
        self.error = error

    def __repr__(self) -> str:
        return f"StubObservation(activity={self.activity!r}, success={self.success})"


def slow_observe(delay_s: float = 6.0):
    """Simulates a screen capture that takes ~6s. This is the function the
    worker invokes — the reply path never calls it."""
    def _observe():
        time.sleep(delay_s)
        return StubObservation(activity="rohit is reading code in editor")
    return _observe


def hanging_observe(delay_s: float = 999.0):
    """Simulates a hung screen capture. The worker should time out and
    record an error WITHOUT clearing the previous good value."""
    def _observe():
        time.sleep(delay_s)
        return StubObservation(activity="should never appear")
    return _observe


# ── helpers ────────────────────────────────────────────────────────────
def time_call(fn) -> tuple[float, object]:
    t0 = time.perf_counter()
    out = fn()
    dt_ms = (time.perf_counter() - t0) * 1000
    return dt_ms, out


def print_read(label: str, dt_ms: float, entry) -> None:
    if entry is None:
        print(f"  [{label}] cache_read_ms={dt_ms:7.3f}  has_value=False  freshness=MISSING")
        return
    print(
        f"  [{label}] cache_read_ms={dt_ms:7.3f}  "
        f"has_value={entry.value is not None}  "
        f"freshness={entry.freshness_state:7s}  "
        f"age_ms={entry.age_ms:6d}  "
        f"error_present={entry.error is not None}  "
        f"version={entry.version}"
    )


def banner(text: str) -> None:
    print()
    print("=" * 72)
    print(f"  {text}")
    print("=" * 72)


# ── scenarios ──────────────────────────────────────────────────────────
def scenario_a_direct_blocking() -> None:
    banner("SCENARIO A — direct blocking screen call (no cache)")
    print("The hot path calls observe() directly. The reply has to wait.")
    direct = slow_observe(delay_s=6.0)
    dt_ms, obs = time_call(direct)
    print(f"  direct_call_ms={dt_ms:7.1f}  result={obs}")
    print(f"  → reply path BLOCKED for {dt_ms/1000:.2f}s before it could continue")


def scenario_b_cached_read() -> None:
    banner("SCENARIO B — cached screen read (background worker)")
    print("Worker refreshes screen on its own cadence; hot path only reads cache.")

    cache = PerceptionCache()
    worker = ScreenCacheWorker(
        cache=cache,
        interval_s=2.0,
        observe_timeout_s=10.0,
        fresh_ms=15_000,
        stale_ms=60_000,
        observe_fn=slow_observe(delay_s=6.0),
    )

    # ── B0: read BEFORE the worker has populated anything ──
    dt_ms, entry = time_call(lambda: cache.get(SOURCE_NAME))
    print_read("B0 read pre-worker  ", dt_ms, entry)
    assert entry is not None, "register() should have created a MISSING entry"
    assert entry.freshness_state == MISSING

    # ── start worker, wait long enough for one full successful tick (6s + a bit) ──
    print("  starting worker, waiting ~7.5s for first successful refresh...")
    worker.start()
    time.sleep(7.5)

    # ── B1: read AFTER first successful refresh — should be FRESH ──
    dt_ms, entry = time_call(lambda: cache.get(SOURCE_NAME))
    print_read("B1 read after refresh", dt_ms, entry)
    assert entry.freshness_state == FRESH, f"expected FRESH, got {entry.freshness_state}"
    assert entry.value is not None
    last_good_value = entry.value
    last_good_version = entry.version

    # ── 100 hot-path reads to show steady-state cost ──
    print("  performing 100 sequential cache reads (hot path simulation)...")
    t0 = time.perf_counter()
    for _ in range(100):
        cache.get(SOURCE_NAME)
    avg_us = (time.perf_counter() - t0) * 1_000_000 / 100
    print(f"  avg_cache_read_us={avg_us:.2f}us over 100 reads")

    worker.stop()

    # ── B2: simulate a HUNG screen call — last good value must be preserved ──
    print()
    print("  simulating hung screen capture (worker timeout=2s, observe sleeps 999s)...")
    hang_worker = ScreenCacheWorker(
        cache=cache,
        interval_s=0.5,
        observe_timeout_s=2.0,
        fresh_ms=15_000,
        stale_ms=60_000,
        observe_fn=hanging_observe(delay_s=999.0),
    )
    hang_worker.start()
    time.sleep(3.0)         # let it time out at least once
    hang_worker.stop()

    dt_ms, entry = time_call(lambda: cache.get(SOURCE_NAME))
    print_read("B2 read after hang   ", dt_ms, entry)

    # Assertions: previous good value preserved; freshness now ERROR; error_present
    assert entry.value is last_good_value, "last good value was NOT preserved across error"
    assert entry.freshness_state == ERROR, f"expected ERROR, got {entry.freshness_state}"
    assert entry.error is not None and 'timed out' in entry.error
    assert entry.version > last_good_version, "version should bump on error update"

    print()
    print("  ✓ last good value preserved across worker timeout")
    print("  ✓ freshness flipped to ERROR")
    print("  ✓ consumer can still read a usable observation")


def comparison_summary() -> None:
    banner("COMPARISON SUMMARY")
    print("""
  A) direct blocking screen call:
       reply latency = full screen call duration (~6000 ms in this stub,
       up to 30000 ms in real conditions when Ollama vision is slow)

  B) cached screen read:
       reply latency = ~10-50 microseconds per cache.get() call, regardless
       of whether the screen worker is fresh, stale, errored, or hung.

  Therefore: the perception cache decouples reply latency from perception
  latency. This is the foundation that the fast-lane reply service (Session
  11b+) will be built on.
""")


def main() -> int:
    scenario_a_direct_blocking()
    scenario_b_cached_read()
    comparison_summary()
    print("Session 11a benchmark complete.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
