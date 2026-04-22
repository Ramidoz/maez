# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""self_dev_scheduler.py — periodic (non-commit-triggered) self-dev runs.

The post-commit hook (core.self_dev_hooks) catches regressions at
commit time. This scheduler catches standing issues — drift that
slipped past every earlier commit. Fires once per invocation,
picks ONE module not reviewed in the last N days, runs
review_module on it, persists the result.

Intended to be wired as a systemd timer that runs daily during
a low-use window (e.g. 04:30 local). Stays inside Maez's normal
budget by running exactly one review per tick — same quota cost
as 1/15th of the daily Claude cap.

Policy (all env-overridable):
  - MAEZ_SELF_DEV_SCHEDULED_MIN_AGE_HOURS  (default 168 = 7 days)
      Don't re-review a module last touched by a review within this
      window. Prevents churn on the same file.
  - MAEZ_SELF_DEV_SCHEDULED_PATHS          (default: "core,memory,skills,daemon")
      Comma-separated top-level dirs to scan for .py files.
  - MAEZ_SELF_DEV_SCHEDULED_MAX_BYTES      (default 40000)
      Skip modules larger than this — review_module times out on
      very large files. Caller can still invoke manually.
  - MAEZ_SELF_DEV_SCHEDULED_SKIP_GLOBS     (default includes __init__.py, tests/)
      Paths matching any of these skip patterns are never picked.

Failures are fail-safe: any exception logs and returns. The
scheduler never propagates errors to systemd (which would spam
the journal on a transient proxy outage).
"""
from __future__ import annotations

import argparse
import fnmatch
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maez.self_dev_scheduler")

_REPO_ROOT = Path("/home/rohit/maez")


# ── configuration ─────────────────────────────────────────────────────

def _min_age_seconds() -> float:
    hours = float(os.environ.get(
        "MAEZ_SELF_DEV_SCHEDULED_MIN_AGE_HOURS", "168",
    ))
    return hours * 3600.0


def _scan_roots() -> list[Path]:
    raw = os.environ.get(
        "MAEZ_SELF_DEV_SCHEDULED_PATHS", "core,memory,skills,daemon",
    )
    return [_REPO_ROOT / p.strip() for p in raw.split(",") if p.strip()]


def _max_bytes() -> int:
    return int(os.environ.get(
        "MAEZ_SELF_DEV_SCHEDULED_MAX_BYTES", "40000",
    ))


# Skip patterns use fnmatch against the repo-relative path.
_DEFAULT_SKIPS = (
    "**/__init__.py",
    "**/__main__.py",
    "tests/**",
    "**/test_*.py",
    "**/conftest.py",
    # Bulk data / vendored packages
    "training/**",
    "web/**",
    ".venv/**",
    "**/.venv/**",
    "**/venv/**",
    "**/__pycache__/**",
)


def _skip_globs() -> tuple[str, ...]:
    extra = os.environ.get("MAEZ_SELF_DEV_SCHEDULED_SKIP_GLOBS", "")
    extra_tuple = tuple(g.strip() for g in extra.split(",") if g.strip())
    return _DEFAULT_SKIPS + extra_tuple


def _matches_any(rel: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(rel, p) for p in patterns)


# ── candidate enumeration ─────────────────────────────────────────────

def enumerate_candidates() -> list[str]:
    """Return repo-relative paths of .py files eligible for scheduled
    review — under one of the scan roots, under the size cap, not
    matching any skip pattern."""
    cap = _max_bytes()
    skips = _skip_globs()
    out: list[str] = []
    for root in _scan_roots():
        if not root.is_dir():
            continue
        for p in root.rglob("*.py"):
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if size > cap or size < 200:  # also skip near-empty files
                continue
            rel = str(p.relative_to(_REPO_ROOT))
            if _matches_any(rel, skips):
                continue
            out.append(rel)
    out.sort()  # deterministic pick when ages tie
    return out


# ── age lookup (when was this path last reviewed?) ────────────────────

def _age_of_last_review(rel_path: str) -> Optional[float]:
    """Return seconds since the most recent review of `rel_path`, or
    None if never reviewed. Uses self_dev_persistence directly."""
    try:
        from core.self_dev_persistence import _connect
    except Exception as e:
        logger.warning("scheduler: can't load persistence: %s", e)
        return None
    try:
        with _connect() as con:
            # target_ref is "module:<rel>" for review_module and
            # "<git-ref>" for review. Match the module form directly.
            row = con.execute(
                "SELECT MAX(ts) FROM reviews WHERE target_ref = ?",
                (f"module:{rel_path}",),
            ).fetchone()
    except Exception as e:
        logger.warning("scheduler: age lookup failed: %s", e)
        return None
    if not row or row[0] is None:
        return None
    return time.time() - float(row[0])


# ── pick and run ──────────────────────────────────────────────────────

def pick_next(candidates: Optional[list[str]] = None) -> Optional[str]:
    """Return the repo-relative path of the next module to review, or
    None if every candidate was reviewed recently enough. Preference:
    never-reviewed modules first; otherwise, oldest.
    """
    if candidates is None:
        candidates = enumerate_candidates()
    if not candidates:
        return None
    min_age = _min_age_seconds()
    # (path, age_or_inf) tuples; inf = never reviewed
    ranked = []
    for p in candidates:
        age = _age_of_last_review(p)
        if age is None:
            age_val = float("inf")
        elif age < min_age:
            continue  # too recent — skip
        else:
            age_val = age
        ranked.append((age_val, p))
    if not ranked:
        return None
    # Highest age (inf wins, i.e. never-reviewed) first. Deterministic
    # tie-break via path name.
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return ranked[0][1]


def run_once(caller: str = "self_dev/scheduled") -> int:
    """Run one review cycle. Returns an exit code; never raises.

    0 = ran (whether or not review found anything)
    0 = also returned if nothing to review (successful idle)
    """
    try:
        candidates = enumerate_candidates()
        if not candidates:
            logger.info("scheduled: no candidate modules found")
            return 0
        picked = pick_next(candidates)
        if not picked:
            logger.info(
                "scheduled: all %d candidates reviewed within %.1fh — skipping",
                len(candidates), _min_age_seconds() / 3600.0,
            )
            return 0

        # Budget check. We don't want to consume Rohit's interactive
        # Claude Code budget on a timer when it's close to cap.
        try:
            from core import claude_tier
            b = claude_tier.budget()
            hourly_rem = b.get("claude", {}).get("hourly_remaining", 0)
            daily_rem = b.get("claude", {}).get("daily_remaining", 0)
            # Stricter than the commit-hook floors — scheduled runs
            # are truly "nice to have" and should yield aggressively.
            min_hourly = int(os.environ.get(
                "MAEZ_SELF_DEV_SCHEDULED_HOURLY_FLOOR", "5",
            ))
            min_daily = int(os.environ.get(
                "MAEZ_SELF_DEV_SCHEDULED_DAILY_FLOOR", "10",
            ))
            if hourly_rem < min_hourly:
                logger.info(
                    "scheduled: yield — hourly remaining %d < floor %d",
                    hourly_rem, min_hourly,
                )
                return 0
            if daily_rem < min_daily:
                logger.info(
                    "scheduled: yield — daily remaining %d < floor %d",
                    daily_rem, min_daily,
                )
                return 0
        except Exception as e:
            logger.info("scheduled: budget probe failed — yielding: %s", e)
            return 0

        logger.info("scheduled: reviewing %s", picked)
        try:
            from core.self_dev import review_module
            result = review_module(path=picked, persist=True, caller=caller)
        except Exception as e:
            logger.warning("scheduled: review_module failed for %s: %s",
                           picked, e)
            return 0

        counts = result.severity_counts()
        logger.info(
            "scheduled: review complete module=%s concerns=%d counts=%s "
            "tokens_in=%d tokens_out=%d",
            picked, len(result.concerns), counts,
            result.input_tokens, result.output_tokens,
        )

        # Surface notify-worthy concerns, same as the post-commit hook.
        try:
            from core.self_dev_hooks import _maybe_notify
            # The hook expects a git SHA for the header; pass a
            # scheduled-tick marker instead so the Telegram message
            # is honest about its source.
            _maybe_notify(f"scheduled:{picked}", result)
        except Exception as e:
            logger.debug("scheduled: notify wiring failed: %s", e)
        return 0
    except Exception as e:
        logger.warning("scheduled: unexpected error (swallowed): %s", e)
        return 0


# ── CLI ───────────────────────────────────────────────────────────────

def _cli_run(args) -> int:
    return run_once()


def _cli_pick(args) -> int:
    candidates = enumerate_candidates()
    picked = pick_next(candidates)
    print(f"candidates: {len(candidates)}")
    print(f"would pick: {picked or '(none — all recently reviewed or empty)'}")
    if args.verbose:
        print()
        print("all candidates (first 20):")
        for c in candidates[:20]:
            age = _age_of_last_review(c)
            age_str = ("never" if age is None
                        else f"{age / 3600:.1f}h ago")
            print(f"  {c:40s}  {age_str}")
    return 0


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m core.self_dev_scheduler",
        description="Periodic self-dev runner — one review per tick.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="Run one review cycle")
    r.set_defaults(func=_cli_run)
    pk = sub.add_parser("pick", help="Show what would be picked (no call)")
    pk.add_argument("-v", "--verbose", action="store_true")
    pk.set_defaults(func=_cli_pick)
    return p


if __name__ == "__main__":
    log_path = Path(os.environ.get(
        "MAEZ_SELF_DEV_SCHEDULER_LOG",
        "/home/rohit/maez/logs/self_dev_scheduler.log",
    ))
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
        )
    except Exception:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
    parser = _build_argparser()
    ns = parser.parse_args()
    sys.exit(ns.func(ns))
