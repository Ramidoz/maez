"""
scripts/bench_fast_reply_prototype.py — Session 11c benchmark.

End-to-end benchmark of the fast reply prototype against the perception cache.
Three scenarios:

  Scenario 1 — FRESH cache
    Both screen and system_state workers have published recent values.
    Expected: envelope/prompt build are sub-millisecond. Reply succeeds.

  Scenario 2 — STALE cache
    Workers stop refreshing; cached values age past their fresh threshold.
    Expected: reply STILL succeeds (degraded gracefully). Freshness flips to STALE.

  Scenario 3 — ERROR cache (one source hung, the other still fresh)
    Screen worker hangs; system_state worker keeps refreshing.
    Expected: reply still succeeds, screen marked ERROR with last good value
    preserved, system_state still FRESH. Prompt builder degrades gracefully.

For all three, the script:
  • Asserts the hot path made zero new perception calls (sys.modules check).
  • Reports envelope_build_ms / prompt_build_ms / model_call_ms / total_ms.
  • Reports screen_cache_age_ms / system_state_cache_age_ms / freshness states.
  • Uses an injected stub backend by default so the test is deterministic.
  • Optionally calls the real local Gemma backend with --real-backend.

  cd /home/rohit/maez
  source .venv/bin/activate
  python scripts/bench_fast_reply_prototype.py
  python scripts/bench_fast_reply_prototype.py --real-backend
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.perception_cache import PerceptionCache, FRESH, STALE, MISSING, ERROR
from core.perception_envelope import build_envelope
from core.fast_backend_local import BackendResult, BACKEND_NAME, is_available
from skills.fast_reply_prototype import (
    fast_reply,
    FastReplyResult,
    FORBIDDEN_HOT_PATH_IMPORTS,
    TurnRecord,
)
from skills.screen_cache_worker import ScreenCacheWorker, SOURCE_NAME as SCREEN_SRC
from skills.system_cache_worker import SystemCacheWorker, SOURCE_NAME as SYSTEM_SRC


# ── stub observations / snapshots ──────────────────────────────────────
class StubScreenObs:
    def __init__(self, activity: str = 'rohit reading code in editor') -> None:
        self.activity    = activity
        self.application = 'vscode'
        self.detail      = 'fast_reply_prototype.py'
        self.focus_level = 'deep_work'
        self.success     = True
        self.error       = ''
        self.timestamp   = time.time()


def stub_screen_observe():
    time.sleep(0.05)            # cheap, deterministic
    return StubScreenObs()


def hanging_screen_observe():
    time.sleep(999)
    return StubScreenObs(activity='never visible')


def stub_system_snapshot():
    time.sleep(0.02)
    return {
        'timestamp':  time.strftime('%Y-%m-%dT%H:%M:%S'),
        'cpu':  {'percent': 14.2},
        'ram':  {'percent': 38.7},
        'disk': {'percent': 46.0},
        'gpu':  {'utilization_pct': 8, 'temperature_c': 45},
    }


# ── stub backend ──────────────────────────────────────────────────────
def stub_backend_call(prompt_text: str, max_tokens: int, temperature: float) -> BackendResult:
    """Deterministic, no-op backend so the benchmark doesn't need Ollama running."""
    time.sleep(0.012)
    # Echo a tiny acknowledgement that includes the first perception line so
    # we can visually confirm the prompt actually carried perception data.
    perc_line = ''
    for line in prompt_text.splitlines():
        if line.lstrip().startswith('screen ') or line.lstrip().startswith('system_state '):
            perc_line = line.strip()
            break
    return BackendResult(
        success=True,
        text=f"[stub-reply] ack. perc_seen={perc_line!r}",
        backend_name='stub',
        model_call_ms=12,
        error=None,
        raw_status=200,
    )


# ── invariant check ───────────────────────────────────────────────────
def assert_no_sync_perception(label: str) -> None:
    """Hard fail if the hot path imported any forbidden perception module."""
    leaked = [m for m in FORBIDDEN_HOT_PATH_IMPORTS if m in sys.modules]
    if leaked:
        print(f"  !! INVARIANT VIOLATED in {label}: forbidden imports present: {leaked}")
        sys.exit(2)


# ── helpers ────────────────────────────────────────────────────────────
def banner(text: str) -> None:
    print()
    print("=" * 76)
    print(f"  {text}")
    print("=" * 76)


def print_metrics(label: str, result: FastReplyResult) -> None:
    m = result.metrics
    print(f"  [{label}]")
    print(f"     envelope_build_ms          = {m.envelope_build_ms}")
    print(f"     prompt_build_ms            = {m.prompt_build_ms}")
    print(f"     model_call_ms              = {m.model_call_ms}")
    print(f"     total_ms                   = {m.total_ms}")
    print(f"     screen_cache_age_ms        = {m.screen_cache_age_ms}   "
          f"freshness={m.screen_freshness}")
    print(f"     system_state_cache_age_ms  = {m.system_state_cache_age_ms}   "
          f"freshness={m.system_state_freshness}")
    print(f"     prompt_chars               = {m.prompt_chars}  truncated={m.prompt_truncated}")
    print(f"     used_perception            = {m.used_perception_sources}")
    print(f"     skipped_perception         = {m.skipped_perception_sources}")
    print(f"     backend_name               = {m.backend_name}  success={m.backend_success}")
    if m.retry_attempted:
        print(f"     retry_strategy             = {m.retry_strategy}")
        print(f"     retry_succeeded            = {m.retry_succeeded}")
        print(f"     retry_backend_name         = {m.retry_backend_name}")
    print(f"     reply_text                 = {result.reply_text[:120]!r}")
    if not result.success:
        print(f"     error                      = {result.error}")


def make_history() -> list[TurnRecord]:
    return [
        TurnRecord('user', "hey maez, how are things on the box right now?"),
        TurnRecord('maez', "Holding steady. Want me to flag anything specific?"),
        TurnRecord('user', "just check what i'm doing and confirm cpu is fine"),
    ]


# ── scenarios ──────────────────────────────────────────────────────────
def scenario_fresh(cache: PerceptionCache, use_real: bool) -> FastReplyResult:
    banner("SCENARIO 1 — FRESH cache (both workers active)")
    screen = ScreenCacheWorker(cache=cache, interval_s=0.4, observe_timeout_s=2.0,
                               fresh_ms=8_000, stale_ms=20_000,
                               observe_fn=stub_screen_observe)
    system = SystemCacheWorker(cache=cache, interval_s=0.3, snapshot_timeout_s=2.0,
                               fresh_ms=4_000, stale_ms=10_000,
                               snapshot_fn=stub_system_snapshot)
    screen.start(); system.start()
    time.sleep(0.9)              # let both populate at least once

    backend_call = None if use_real else stub_backend_call
    result = fast_reply(
        user_message="quick status — am i deep-working and is cpu okay?",
        history=make_history(),
        cache=cache,
        backend_call=backend_call,
    )
    screen.stop(); system.stop()
    print_metrics('FRESH', result)
    assert_no_sync_perception('FRESH')
    assert result.success, f"FRESH scenario should succeed, got error={result.error}"
    assert result.metrics.screen_freshness == FRESH, f"expected screen FRESH, got {result.metrics.screen_freshness}"
    assert result.metrics.system_state_freshness == FRESH, f"expected system_state FRESH, got {result.metrics.system_state_freshness}"
    return result


def scenario_stale(cache: PerceptionCache, use_real: bool) -> FastReplyResult:
    banner("SCENARIO 2 — STALE cache (workers stopped, values aged past fresh threshold)")
    screen = ScreenCacheWorker(cache=cache, interval_s=0.4, observe_timeout_s=2.0,
                               fresh_ms=400, stale_ms=10_000,    # very tight fresh window
                               observe_fn=stub_screen_observe)
    system = SystemCacheWorker(cache=cache, interval_s=0.3, snapshot_timeout_s=2.0,
                               fresh_ms=400, stale_ms=10_000,
                               snapshot_fn=stub_system_snapshot)
    screen.start(); system.start()
    time.sleep(0.9)              # populate
    screen.stop(); system.stop() # then stop refreshing
    time.sleep(1.2)              # let both age past 400ms fresh window

    backend_call = None if use_real else stub_backend_call
    result = fast_reply(
        user_message="status check please",
        history=make_history(),
        cache=cache,
        backend_call=backend_call,
    )
    print_metrics('STALE', result)
    assert_no_sync_perception('STALE')
    assert result.success, "STALE scenario should still produce a reply"
    assert result.metrics.screen_freshness == STALE, f"expected screen STALE, got {result.metrics.screen_freshness}"
    assert result.metrics.system_state_freshness == STALE, f"expected system_state STALE, got {result.metrics.system_state_freshness}"
    return result


def scenario_error(cache: PerceptionCache, use_real: bool) -> FastReplyResult:
    banner("SCENARIO 3 — ERROR on screen, FRESH on system_state")
    # Phase 1: populate both successfully so we have a last-good screen value.
    screen = ScreenCacheWorker(cache=cache, interval_s=0.4, observe_timeout_s=2.0,
                               fresh_ms=8_000, stale_ms=20_000,
                               observe_fn=stub_screen_observe)
    system = SystemCacheWorker(cache=cache, interval_s=0.3, snapshot_timeout_s=2.0,
                               fresh_ms=4_000, stale_ms=10_000,
                               snapshot_fn=stub_system_snapshot)
    screen.start(); system.start()
    time.sleep(0.9)
    screen.stop()                # stop the good screen worker

    # Phase 2: replace with a hanging screen worker. Wait for it to time out.
    hang = ScreenCacheWorker(cache=cache, interval_s=0.3, observe_timeout_s=1.0,
                             fresh_ms=8_000, stale_ms=20_000,
                             observe_fn=hanging_screen_observe)
    hang.start()
    time.sleep(2.0)              # let it time out at least once
    hang.stop()
    system.stop()

    backend_call = None if use_real else stub_backend_call
    result = fast_reply(
        user_message="reply even if a sensor is broken",
        history=make_history(),
        cache=cache,
        backend_call=backend_call,
    )
    print_metrics('ERROR', result)
    assert_no_sync_perception('ERROR')
    assert result.success, "ERROR scenario should still produce a reply"
    assert result.metrics.screen_freshness == ERROR, f"expected screen ERROR, got {result.metrics.screen_freshness}"
    assert result.envelope.screen.has_value, "screen should still have last good value"
    return result


def make_empty_then_real_stub():
    """Stub backend that returns success-with-empty on the first call and a
    real reply on the retry. Use this to exercise the empty-reply retry path
    in fast_reply_prototype without needing a thinking model."""
    state = {'calls': 0}
    def _call(prompt_text: str, max_tokens: int, temperature: float) -> BackendResult:
        state['calls'] += 1
        if state['calls'] == 1:
            return BackendResult(
                success=True,
                text='',                                # empty success
                backend_name='stub-empty',
                model_call_ms=8,
                error=None,
                raw_status=200,
            )
        # Retry call — return a long-enough visible reply
        return BackendResult(
            success=True,
            text='[stub-retry] visible reply produced after retry, calm and warm.',
            backend_name='stub-real',
            model_call_ms=14,
            error=None,
            raw_status=200,
        )
    return _call


def scenario_empty_reply_retry(cache: PerceptionCache) -> FastReplyResult:
    banner("SCENARIO 4 — empty-reply retry path")
    print("First backend call returns success=True with empty text. The retry path")
    print("should fire, get a visible reply on the second call, and metrics should")
    print("record retry_strategy=local_sharper, retry_succeeded=True.")

    screen = ScreenCacheWorker(cache=cache, interval_s=0.4, observe_timeout_s=2.0,
                               fresh_ms=8_000, stale_ms=20_000,
                               observe_fn=stub_screen_observe)
    system = SystemCacheWorker(cache=cache, interval_s=0.3, snapshot_timeout_s=2.0,
                               fresh_ms=4_000, stale_ms=10_000,
                               snapshot_fn=stub_system_snapshot)
    screen.start(); system.start()
    time.sleep(0.9)

    stub = make_empty_then_real_stub()
    result = fast_reply(
        user_message="please give me a short status",
        history=make_history(),
        cache=cache,
        backend_call=stub,
    )
    screen.stop(); system.stop()
    print_metrics('EMPTY-RETRY', result)
    assert_no_sync_perception('EMPTY-RETRY')
    assert result.success, f"retry path should still produce a reply, got error={result.error}"
    assert result.metrics.retry_attempted, "retry_attempted should be True"
    assert result.metrics.retry_reason == 'empty_success', \
        f"retry_reason should be 'empty_success', got {result.metrics.retry_reason!r}"
    assert result.metrics.retry_strategy == 'local_sharper', \
        f"retry_strategy should be 'local_sharper', got {result.metrics.retry_strategy!r}"
    assert result.metrics.retry_succeeded, "retry_succeeded should be True"
    assert '[stub-retry]' in result.reply_text, \
        f"reply should be the retry text, got {result.reply_text!r}"
    print()
    print("  ✓ retry fired on empty success")
    print("  ✓ visible reply produced on retry")
    print("  ✓ retry_* metrics populated")
    return result


def scenario_empty_reply_degraded(cache: PerceptionCache) -> FastReplyResult:
    banner("SCENARIO 5 — empty-reply retry exhausted → degraded fallback")
    print("Backend returns success=True with empty text on EVERY call. With local-only")
    print("policy (trust_scope='rohit') the retry path should land on the degraded")
    print("fallback message and still return success=True.")

    screen = ScreenCacheWorker(cache=cache, interval_s=0.4, observe_timeout_s=2.0,
                               fresh_ms=8_000, stale_ms=20_000,
                               observe_fn=stub_screen_observe)
    system = SystemCacheWorker(cache=cache, interval_s=0.3, snapshot_timeout_s=2.0,
                               fresh_ms=4_000, stale_ms=10_000,
                               snapshot_fn=stub_system_snapshot)
    screen.start(); system.start()
    time.sleep(0.9)

    def always_empty(prompt_text: str, max_tokens: int, temperature: float) -> BackendResult:
        return BackendResult(
            success=True, text='', backend_name='stub-always-empty',
            model_call_ms=6, error=None, raw_status=200,
        )

    result = fast_reply(
        user_message="quick question",
        history=make_history(),
        cache=cache,
        backend_call=always_empty,
    )
    screen.stop(); system.stop()
    print_metrics('EMPTY-DEGRADED', result)
    assert_no_sync_perception('EMPTY-DEGRADED')
    assert result.success, "degraded fallback path should still return success=True"
    assert result.metrics.retry_attempted, "retry_attempted should be True"
    assert result.metrics.retry_strategy == 'degraded_fallback', \
        f"retry_strategy should be 'degraded_fallback', got {result.metrics.retry_strategy!r}"
    assert not result.metrics.retry_succeeded, "retry_succeeded should be False"
    assert 'drafting attempt came back empty' in result.reply_text, \
        f"reply should be the degraded fallback text, got {result.reply_text!r}"
    print()
    print("  ✓ retry fired but failed visibility check")
    print("  ✓ degraded fallback message returned")
    print("  ✓ overall success preserved (no hard failure)")
    return result


def comparison_summary() -> None:
    banner("COMPARISON SUMMARY — fast lane vs synchronous-perception pattern")
    print("""
  Synchronous pattern (current slow daemon path):
    user_message
      → screen_perception.observe()    ~ 3000-30000 ms (Ollama vision)
      → core.perception.snapshot()     ~ 50-300 ms
      → build slow prompt + memory retrieval
      → backend.generate()             ~ 1500-8000 ms (gemma4 26b)
    Reply latency dominated by perception, often >10s before the model
    even starts generating.

  Fast lane pattern (this prototype):
    user_message
      → build_envelope(cache)          < 1 ms     (read-only cache)
      → build_fast_prompt(envelope)    < 1 ms     (deterministic string ops)
      → backend.generate()             ~ 12 ms (stub) | ~ 1500-3000 ms (real gemma4)
    Reply latency is dominated by the model call alone. Perception adds
    essentially zero — workers refresh in the background, the hot path
    only reads cached values, and stale/errored sources degrade gracefully
    instead of blocking.

  Invariant verified by every scenario:
    sys.modules contains NEITHER 'skills.screen_perception' NOR 'core.perception'
    after the fast_reply call. The hot path made zero synchronous perception
    calls, ever.
""")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--real-backend', action='store_true',
                    help='Call live Ollama gemma4:26b instead of the stub backend')
    args = ap.parse_args()

    use_real = args.real_backend
    if use_real:
        if not is_available():
            print("Ollama is not reachable on localhost:11434 — falling back to stub backend.")
            use_real = False
        else:
            print(f"Using real backend: {BACKEND_NAME}")

    cache_1 = PerceptionCache()
    cache_2 = PerceptionCache()
    cache_3 = PerceptionCache()
    cache_4 = PerceptionCache()
    cache_5 = PerceptionCache()
    scenario_fresh(cache_1, use_real)
    scenario_stale(cache_2, use_real)
    scenario_error(cache_3, use_real)
    # Empty-reply retry scenarios always use stub backends — they need
    # deterministic empty-success behavior, which a real model can't reliably
    # produce on demand. So they ignore --real-backend.
    scenario_empty_reply_retry(cache_4)
    scenario_empty_reply_degraded(cache_5)
    comparison_summary()
    print("Session 11c+11e benchmark complete.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
