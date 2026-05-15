# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
scripts/fast_reply_cli.py — Session 11d, staging-only.

Manual entrypoint for the owner to feel real fast-lane reply latency without
touching the daemon. Calls the staging fast reply path against whichever
backend the router selects, persists conversation history across calls,
and prints reply text + backend selection + timing + cache freshness.

Usage:
  cd /home/rohit/maez
  source .venv/bin/activate

  # Default: auto-policy (local first), persist + auto-load history for 'rohit'
  python scripts/fast_reply_cli.py "hey maez, what's running?"

  # Force a specific backend
  python scripts/fast_reply_cli.py --backend local "status check"
  python scripts/fast_reply_cli.py --backend cloud "draft a one-line greeting"

  # Different trust scope
  python scripts/fast_reply_cli.py --scope guest "hi"

  # Skip history loading / persisting (one-shot mode)
  python scripts/fast_reply_cli.py --no-history "scratch question"

  # Wipe the conversation log for a scope
  python scripts/fast_reply_cli.py --clear-history --scope rohit

  # Show recent turns for a scope without sending a message
  python scripts/fast_reply_cli.py --show-history --scope rohit

This is staging-only. It does not touch maez.service, daemon/maez_daemon.py,
core/cognition_quality.py, skills/evolution_engine.py, or any live routing.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.perception_cache import get_cache
from core.fast_conversation_log import get_log
from skills.fast_reply_prototype import fast_reply, FORBIDDEN_HOT_PATH_IMPORTS
from skills.screen_cache_worker import ScreenCacheWorker
from skills.system_cache_worker import SystemCacheWorker


def _format_metrics_block(m) -> str:
    line = (
        f"  envelope_build_ms          : {m.envelope_build_ms}\n"
        f"  prompt_build_ms            : {m.prompt_build_ms}\n"
        f"  model_call_ms              : {m.model_call_ms}\n"
        f"  total_ms                   : {m.total_ms}\n"
        f"  prompt_chars               : {m.prompt_chars}  (truncated={m.prompt_truncated})\n"
        f"  history_turns_loaded       : {m.history_turns_loaded}\n"
        f"  history_persisted          : {m.history_persisted}\n"
    )
    if m.retry_attempted:
        line += (
            f"  retry_attempted            : True\n"
            f"  retry_reason               : {m.retry_reason}\n"
            f"  retry_strategy             : {m.retry_strategy}\n"
            f"  retry_succeeded            : {m.retry_succeeded}\n"
            f"  retry_backend_name         : {m.retry_backend_name}\n"
            f"  retry_model_call_ms        : {m.retry_model_call_ms}\n"
        )
    return line


def _format_policy_block(m) -> str:
    if not m.policy_rule:
        return "  (no policy decision recorded — direct backend path)\n"
    out = (
        f"  rule_fired                 : {m.policy_rule}\n"
        f"  requested_policy           : {m.policy_requested}\n"
        f"  effective_policy           : {m.policy_effective}\n"
        f"  allow_cloud                : {m.policy_allow_cloud}\n"
        f"  downgraded                 : {m.policy_downgraded}\n"
    )
    for r in m.policy_reasons:
        out += f"  reason                     : {r}\n"
    return out


def _format_freshness_block(m) -> str:
    def fmt(name: str, age_ms: int, freshness: str) -> str:
        if age_ms < 0:
            return f"  {name:13s} : {freshness}"
        return f"  {name:13s} : {freshness}  ({age_ms} ms old)"
    return (
        fmt('screen',       m.screen_cache_age_ms,       m.screen_freshness) + "\n" +
        fmt('system_state', m.system_state_cache_age_ms, m.system_state_freshness) + "\n" +
        fmt('calendar',     m.calendar_cache_age_ms,     m.calendar_freshness)
    )


def _show_history(scope: str) -> int:
    log = get_log()
    turns = log.recent(scope, n=50)
    print(f"history for trust_scope={scope!r}  ({len(turns)} turns)")
    if not turns:
        print("  (empty)")
        return 0
    for t in turns:
        speaker = 'rohit' if t.role == 'user' else 'maez '
        snippet = t.text.strip().replace('\n', ' ')
        if len(snippet) > 200:
            snippet = snippet[:199] + '…'
        print(f"  {speaker}: {snippet}")
    return 0


def _clear_history(scope: str) -> int:
    log = get_log()
    n = log.clear(scope)
    print(f"cleared {n} turns for trust_scope={scope!r}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description='Staging fast-lane reply CLI (Session 11d).',
    )
    ap.add_argument('message', nargs='*', help='message text (positional)')
    ap.add_argument('--scope',   default='rohit',
                    help='trust scope key for history (default: rohit)')
    ap.add_argument('--backend', default='auto', choices=('auto', 'local', 'cloud'),
                    help='backend policy (default: auto = local first)')
    ap.add_argument('--max-tokens', type=int, default=256)
    ap.add_argument('--temperature', type=float, default=0.4)
    ap.add_argument('--timeout', type=float, default=120.0,
                    help='backend call timeout in seconds (default: 120, gemma4:26b can be slow at high token budgets)')
    ap.add_argument('--no-history', action='store_true',
                    help='disable history load and persist for this call')
    ap.add_argument('--show-history', action='store_true',
                    help='print history for the scope and exit')
    ap.add_argument('--clear-history', action='store_true',
                    help='clear history for the scope and exit')
    ap.add_argument('--prime-perception', action='store_true',
                    help='briefly start the perception workers with stub fallback so the cache is populated')
    ap.add_argument('--show-prompt', action='store_true',
                    help='also print the assembled prompt text')
    ap.add_argument('--policy-debug', action='store_true',
                    help='print the full policy decision (rule fired, requested vs effective, allow_cloud, reasons)')
    args = ap.parse_args()

    # Maintenance modes — short-circuit
    if args.show_history:
        return _show_history(args.scope)
    if args.clear_history:
        return _clear_history(args.scope)

    if not args.message:
        ap.error('message text is required (or use --show-history / --clear-history)')

    user_message = ' '.join(args.message).strip()
    cache = get_cache()
    log = get_log()

    # Optionally prime perception workers so the envelope has fresh values.
    # This is short-running and only invoked when the operator explicitly asks.
    workers = []
    if args.prime_perception:
        sw = ScreenCacheWorker(cache=cache)
        ssw = SystemCacheWorker(cache=cache)
        sw.start(); ssw.start()
        workers = [sw, ssw]
        # Give them a moment to populate at least the cheap sources.
        time.sleep(1.2)

    # Snapshot forbidden modules BEFORE the call so we measure whether the
    # reply hot path itself imported any. (Background workers may have already
    # lazy-imported them — that's allowed; only the reply path is restricted.)
    pre_call_forbidden = {m for m in FORBIDDEN_HOT_PATH_IMPORTS if m in sys.modules}

    try:
        result = fast_reply(
            user_message=user_message,
            cache=cache,
            trust_scope=args.scope,
            backend=args.backend,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            timeout_s=args.timeout,
            persist_history=(not args.no_history),
            auto_load_history=(not args.no_history),
            history_log=log,
        )
    finally:
        for w in workers:
            w.stop()

    post_call_forbidden = {m for m in FORBIDDEN_HOT_PATH_IMPORTS if m in sys.modules}
    newly_imported = post_call_forbidden - pre_call_forbidden

    # ── output ──
    print()
    print("─" * 76)
    print(f"  trust_scope        : {args.scope}")
    print(f"  backend policy     : {args.backend}")
    print(f"  backend selected   : {result.metrics.backend_name}")
    print(f"  selection reason   : {result.metrics.backend_selection_reason}")
    print(f"  backend success    : {result.metrics.backend_success}")
    print("─" * 76)
    print("  REPLY")
    print("─" * 76)
    if result.success:
        print(result.reply_text)
    else:
        print(f"  (no reply — error: {result.error})")
    print("─" * 76)
    print("  TIMING")
    print(_format_metrics_block(result.metrics), end='')
    print("─" * 76)
    print("  PERCEPTION FRESHNESS")
    print(_format_freshness_block(result.metrics))
    print("─" * 76)
    if args.policy_debug:
        print("  POLICY DECISION")
        print(_format_policy_block(result.metrics), end='')
        print("─" * 76)
    if args.show_prompt:
        print("  ASSEMBLED PROMPT")
        print("─" * 76)
        print(result.prompt.text)
        print("─" * 76)

    # Final invariant check — did the reply HOT PATH itself synchronously
    # import any forbidden perception module? Background workers may have
    # already loaded them lazily (that's expected); we only fail if the
    # set grew during the fast_reply call.
    if newly_imported:
        print(f"  !! INVARIANT VIOLATED: hot path imported {sorted(newly_imported)}")
        return 2
    else:
        print("  invariant ok       : reply hot path imported no synchronous perception")

    return 0 if result.success else 1


if __name__ == '__main__':
    raise SystemExit(main())
