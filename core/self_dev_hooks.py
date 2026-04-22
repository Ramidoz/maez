# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""self_dev_hooks.py — autonomous trigger policy for self-dev reviews.

Today the review primitive (core.self_dev.review) runs only when
someone types `python -m core.self_dev review`. This module's job
is to decide, from a machine event (a git commit landing), whether
Claude should be consulted about it — and if so, to fire the review
asynchronously so nothing user-visible is blocked.

Hierarchy:

    .git/hooks/post-commit              ← thin shell wrapper, backgrounds
         ↓ (disowned python -m core.self_dev_hooks run <sha>)
    core.self_dev_hooks.run_post_commit ← policy + orchestrator
         ↓ if policy says yes
    core.self_dev.review(persist=True)
         ↓
    self_dev.db (concerns queue)

Design principles:

  1. Never block the commit. The shell wrapper backgrounds us; we
     run disowned. Even a total hang in this module cannot stall
     Rohit's next git operation.
  2. Yield to owner. If the Claude subscription budget is close to
     saturation, we skip. Rohit's own interactive Claude Code
     sessions take priority over automatic reviews.
  3. Fail-safe. Any exception from policy checks or the review call
     is caught, logged, and never surfaced to the commit flow.
  4. Observable. Every firing decision lands in
     logs/self_dev_hooks.log with enough context to audit.
  5. Opt-in. No auto-install. Rohit runs scripts/install-post-commit-hook.sh
     explicitly; the hook file lives under .git/hooks and can be
     removed or disabled at any time.
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maez.self_dev_hooks")


# ── tunables (env-overridable) ────────────────────────────────────────

# Hourly remaining below this → yield to owner, skip review.
# Example: cap is 10/hr, threshold 3 means we skip if only 2 calls
# remain in the hour. Keeps headroom for Rohit's interactive use.
_HOURLY_YIELD_FLOOR = int(
    os.environ.get("MAEZ_SELF_DEV_HOURLY_FLOOR", "3"),
)
_DAILY_YIELD_FLOOR = int(
    os.environ.get("MAEZ_SELF_DEV_DAILY_FLOOR", "5"),
)

# Upper bound on total diff size for auto-review. Very large commits
# (merges, vendor drops, bulk generations) usually aren't worth the
# quota — too large to context, too noisy to critique. Manual
# invocation still works past this cap.
_MAX_AUTO_REVIEW_DIFF_CHARS = int(
    os.environ.get("MAEZ_SELF_DEV_MAX_AUTO_DIFF_CHARS", "80000"),
)

# Files whose diff we won't count toward the size budget — lock files,
# generated code, etc. Listed here because git diff will still include
# them; we just compute a 'significant' size after filtering. Additions
# should be conservative — exclude only files that reliably contain no
# reviewable semantic change.
_BORING_FILE_PATTERNS = (
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "go.sum",
    ".lock",
)

_REPO_ROOT = Path("/home/rohit/maez")


# ── policy result ─────────────────────────────────────────────────────

@dataclass
class PolicyDecision:
    should_review: bool
    reason: str
    diff_chars: int = 0
    hourly_remaining: Optional[int] = None
    daily_remaining: Optional[int] = None


# ── git helpers ───────────────────────────────────────────────────────

def _git(args: list[str], timeout: float = 5.0) -> str:
    """Run a git command and return stdout. Raises on non-zero exit."""
    out = subprocess.run(
        ["git", "-C", str(_REPO_ROOT)] + args,
        capture_output=True, text=True, timeout=timeout, check=True,
    )
    return out.stdout


def _commit_diff_sizes(sha: str) -> tuple[int, int]:
    """Return (total_chars, significant_chars). `significant` excludes
    matching patterns in _BORING_FILE_PATTERNS."""
    try:
        raw = _git(["show", "--no-color", "--no-ext-diff", sha])
    except Exception:
        return (0, 0)
    total = len(raw)

    # Compute significant size by walking the diff and subtracting
    # boring-file blocks. Simple hand-rolled parser — git's machine-
    # readable modes don't give us per-file content.
    significant = 0
    current_file = ""
    keep_block = True
    for line in raw.splitlines(keepends=True):
        if line.startswith("diff --git "):
            # Extract the b-path (post-rename destination)
            # Format: diff --git a/path b/path
            parts = line.strip().split()
            current_file = parts[-1][2:] if len(parts) >= 4 else ""
            keep_block = not any(
                p in current_file for p in _BORING_FILE_PATTERNS
            )
        if keep_block:
            significant += len(line)
    return (total, significant)


def _resolve_sha(ref: str = "HEAD") -> Optional[str]:
    """Resolve a ref to a full commit SHA, or None on error."""
    try:
        return _git(["rev-parse", ref]).strip()
    except Exception:
        return None


# ── policy ────────────────────────────────────────────────────────────

def decide(sha: str) -> PolicyDecision:
    """Apply the should-we-review policy to a commit SHA. Deterministic
    (given clock-time-invariant inputs); caller must trust the decision
    or override via manual invocation."""
    # 1. Does the commit exist?
    resolved = _resolve_sha(sha)
    if not resolved:
        return PolicyDecision(
            should_review=False,
            reason=f"unresolved sha: {sha!r}",
        )

    # 2. Is any of the diff worth reviewing?
    total_chars, sig_chars = _commit_diff_sizes(resolved)
    if sig_chars == 0:
        return PolicyDecision(
            should_review=False,
            reason="empty / boring-only diff",
            diff_chars=total_chars,
        )
    if sig_chars > _MAX_AUTO_REVIEW_DIFF_CHARS:
        return PolicyDecision(
            should_review=False,
            reason=(
                f"diff exceeds auto-review cap "
                f"({sig_chars} > {_MAX_AUTO_REVIEW_DIFF_CHARS} chars). "
                f"Run manually if wanted."
            ),
            diff_chars=total_chars,
        )

    # 3. Is the subscription budget healthy enough to borrow from?
    # Fail-closed: if the proxy/budget check errors, we yield.
    try:
        from core import claude_tier
        b = claude_tier.budget()
    except Exception as e:
        return PolicyDecision(
            should_review=False,
            reason=f"proxy budget unreachable: {e}",
            diff_chars=total_chars,
        )
    claude_b = b.get("claude") or {}
    hourly = claude_b.get("hourly_remaining", 0)
    daily = claude_b.get("daily_remaining", 0)
    if hourly < _HOURLY_YIELD_FLOOR:
        return PolicyDecision(
            should_review=False,
            reason=(
                f"yield: hourly budget {hourly} < floor "
                f"{_HOURLY_YIELD_FLOOR}"
            ),
            diff_chars=total_chars,
            hourly_remaining=hourly, daily_remaining=daily,
        )
    if daily < _DAILY_YIELD_FLOOR:
        return PolicyDecision(
            should_review=False,
            reason=(
                f"yield: daily budget {daily} < floor "
                f"{_DAILY_YIELD_FLOOR}"
            ),
            diff_chars=total_chars,
            hourly_remaining=hourly, daily_remaining=daily,
        )

    return PolicyDecision(
        should_review=True,
        reason="policy pass",
        diff_chars=total_chars,
        hourly_remaining=hourly, daily_remaining=daily,
    )


# ── orchestrator ──────────────────────────────────────────────────────

def run_post_commit(sha: str, *, caller: str = "self_dev/post-commit") -> int:
    """Called by the git post-commit hook (via `python -m
    core.self_dev_hooks run <sha>`). Returns an exit code; 0 means
    the hook completed (whether or not a review was actually run).
    A non-zero exit from this function does NOT propagate back to
    the commit — we're already backgrounded."""
    decision = decide(sha)
    logger.info(
        "post-commit sha=%s decision=%s reason=%s diff_chars=%d "
        "hourly_rem=%s daily_rem=%s",
        sha[:12],
        "REVIEW" if decision.should_review else "SKIP",
        decision.reason,
        decision.diff_chars,
        decision.hourly_remaining, decision.daily_remaining,
    )
    if not decision.should_review:
        return 0

    # Fire the review. Failures are caught and logged but not raised
    # — the hook must not die on a transient backend problem.
    try:
        from core.self_dev import review
        result = review(
            target_ref=sha,
            model=os.environ.get("MAEZ_SELF_DEV_MODEL", "sonnet"),
            persist=True,
            caller=caller,
        )
    except Exception as e:
        logger.warning("post-commit review failed for %s: %s", sha[:12], e)
        return 0

    counts = result.severity_counts()
    logger.info(
        "post-commit review complete sha=%s concerns=%d counts=%s "
        "tokens_in=%d tokens_out=%d",
        sha[:12], len(result.concerns), counts,
        result.input_tokens, result.output_tokens,
    )
    return 0


# ── git hook script generation ────────────────────────────────────────

_HOOK_SCRIPT_TEMPLATE = """#!/bin/sh
# Maez self-dev post-commit hook — installed by
# scripts/install-post-commit-hook.sh. Background + disown so this
# never blocks a commit. Edit or delete this file freely; re-running
# the install script overwrites it.

set -e
SHA="$(git rev-parse HEAD)"

# Disowned background invocation. All output goes to a dedicated log
# so the hook can't pollute the terminal where the commit was made.
(
  cd "{repo_root}"
  "{python_bin}" -m core.self_dev_hooks run "$SHA" \\
    >> "{log_path}" 2>&1
) < /dev/null > /dev/null 2>&1 &
disown 2>/dev/null || true

exit 0
"""


def render_hook_script(
    *,
    python_bin: str = "/home/rohit/maez/.venv/bin/python3",
    repo_root: str = str(_REPO_ROOT),
    log_path: str = "/home/rohit/maez/logs/self_dev_hooks.log",
) -> str:
    """Return the shell script body for .git/hooks/post-commit."""
    return _HOOK_SCRIPT_TEMPLATE.format(
        python_bin=python_bin,
        repo_root=repo_root,
        log_path=log_path,
    )


# ── CLI ───────────────────────────────────────────────────────────────

def _cli_run(args) -> int:
    return run_post_commit(args.sha)


def _cli_decide(args) -> int:
    d = decide(args.sha)
    print(f"should_review: {d.should_review}")
    print(f"reason:        {d.reason}")
    print(f"diff_chars:    {d.diff_chars}")
    print(f"hourly_rem:    {d.hourly_remaining}")
    print(f"daily_rem:     {d.daily_remaining}")
    return 0 if d.should_review else 1


def _cli_render_hook(args) -> int:
    print(render_hook_script())
    return 0


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m core.self_dev_hooks",
        description="Self-dev autonomous trigger policy + hook.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Run the post-commit orchestrator")
    r.add_argument("sha", help="commit SHA to process")
    r.set_defaults(func=_cli_run)

    d = sub.add_parser("decide", help="Dry-run the policy (no review)")
    d.add_argument("sha", nargs="?", default="HEAD")
    d.set_defaults(func=_cli_decide)

    h = sub.add_parser(
        "render-hook",
        help="Emit the shell body for .git/hooks/post-commit",
    )
    h.set_defaults(func=_cli_render_hook)

    return p


if __name__ == "__main__":
    # Log config targets the dedicated hook log so disowned runs are
    # auditable. Falls back to stderr if the log path is unwritable.
    log_path = Path(os.environ.get(
        "MAEZ_SELF_DEV_HOOK_LOG",
        "/home/rohit/maez/logs/self_dev_hooks.log",
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
