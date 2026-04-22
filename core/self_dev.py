# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""self_dev.py — Maez proposes improvements to its own code via the
Claude subscription.

Initial primitive: `review(git_ref)`. Given a git range (single commit
or commit range), asks Claude to critique the diff and return a
structured list of concerns. No autonomous triggers yet — the caller
decides when to invoke. No persistence yet — results print to stdout
or are consumed programmatically. No evolution-candidate wiring yet —
that lands once the review output is validated against real commits.

This is the *foundation* of the self-dev loop envisioned in the
memory's "Maez is the agent of its own evolution" feedback. Hierarchy
of upcoming modules:

    core/self_dev.py           ← this file: primitives
    core/self_dev_hooks.py     ← trigger logic (builder_mode, budget, timing)
    core/self_dev_candidates.py ← persistence + evolution_engine wiring
    skills/self_dev_skill.py   ← Telegram surface (approve/reject reviews)

Why this file and not a package: keeping everything together until the
shape settles. Refactor into a package the moment it gets bigger than
~400 lines or grows a second distinct task type.

Usage:
    from core.self_dev import review
    result = review(target_ref="HEAD~1..HEAD")
    for c in result.concerns:
        print(c.severity, c.file, c.line, c.text)

    # or from a shell
    python -m core.self_dev review HEAD~1..HEAD
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from typing import Optional

from core import claude_tier

logger = logging.getLogger("maez.self_dev")

# ── prompt templates ──────────────────────────────────────────────────
#
# The review prompt is deliberately opinionated about Maez's *house
# style*: no speculative refactors, no premature abstractions, no
# backwards-compat concerns for unreleased code. This keeps Claude
# from suggesting "improvements" that Rohit would reject anyway.
#
# We ask for a JSON envelope because the subscription proxy doesn't
# currently pass through --json-schema, so we rely on the model
# producing valid JSON. If parsing fails we fall back to treating
# the raw text as a single overall concern (see _parse_response).

_REVIEW_SYSTEM_PROMPT = """You are reviewing a git diff on behalf of \
Maez, an always-on local AI daemon written in Python. You are being \
invoked by Maez itself via its subscription proxy — treat this as a \
peer-review of work Maez (together with Claude Code) authored.

Review priorities, in order:

1. Correctness bugs: off-by-one, wrong exception types, unclosed \
   resources, race conditions, wrong default values, argument shadowing.
2. Grounding/honesty violations: code that fabricates status or \
   claims results without evidence, that hides failures, that \
   swallows exceptions silently.
3. Safety: anything that could corrupt memory/dbs, exfiltrate data, \
   bypass safety gates, or elevate privileges.
4. Anti-patterns specific to this codebase: speculative refactors, \
   new abstractions without callers, backwards-compat shims for \
   unreleased features, auto-added error handlers wrapping lines \
   that can't fail, doc comments that just restate the code.

DO NOT raise as concerns:
- Style/formatting opinions.
- "Could be more extensible" musings without a concrete near-term caller.
- Test coverage gaps (a separate task will handle that).
- Rewording a comment that's already correct.

Respond ONLY with valid JSON in this shape, no prose before or after:

{
  "overall": "one-sentence summary verdict",
  "concerns": [
    {
      "file": "path/relative/to/repo",
      "line": <integer line number or null>,
      "severity": "blocker" | "major" | "minor" | "nit",
      "text": "the specific concern, one paragraph max",
      "suggestion": "optional concrete fix or 'null'"
    }
  ]
}

An empty concerns array is a valid, useful response — it means the \
diff is clean to your eyes. Do not invent concerns to fill space.
"""


# ── data types ────────────────────────────────────────────────────────

@dataclass
class Concern:
    file: str
    line: Optional[int]
    severity: str  # blocker | major | minor | nit
    text: str
    suggestion: Optional[str] = None


@dataclass
class ReviewResult:
    """Structured output of a review call. `raw_text` is always the
    model's raw response (for debugging / trajectory inspection).
    `parse_error` is non-empty when JSON parsing failed and the
    concerns list is a fallback."""
    target_ref: str
    diff_size_chars: int
    overall: str
    concerns: list[Concern] = field(default_factory=list)
    model_used: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    raw_text: str = ""
    parse_error: str = ""

    def severity_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self.concerns:
            counts[c.severity] = counts.get(c.severity, 0) + 1
        return counts


# ── git plumbing ──────────────────────────────────────────────────────

_REPO_ROOT = "/home/rohit/maez"

# Single-commit refs like "HEAD", "abc1234", "main" — accept `show`
# diff. Ranges like "HEAD~1..HEAD" — accept `diff` between endpoints.
_RANGE_RE = re.compile(r"\.\.+")


def _git_diff(target_ref: str) -> str:
    """Return the textual diff for `target_ref`. Range refs use
    `git diff A..B`; single refs use `git show`."""
    is_range = bool(_RANGE_RE.search(target_ref))
    if is_range:
        cmd = ["git", "-C", _REPO_ROOT, "diff", "--no-color",
               "--no-ext-diff", target_ref]
    else:
        cmd = ["git", "-C", _REPO_ROOT, "show", "--no-color",
               "--no-ext-diff", target_ref]
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"git failed for ref {target_ref!r}: {e.stderr[:400]}"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"git timed out resolving {target_ref!r}")
    return out.stdout


# ── JSON response parsing ─────────────────────────────────────────────
#
# Claude will usually return clean JSON, but "usually" isn't "always".
# We do a forgiving extract: find the outermost {...} block, parse
# that; if that fails, stuff the raw text into an "overall" field
# with a parse_error marker.

def _extract_json_block(text: str) -> Optional[str]:
    """Return the largest top-level JSON object substring from text,
    or None if no balanced {...} found. Forgiving to leading/trailing
    prose even though the prompt forbids it."""
    first = text.find("{")
    if first < 0:
        return None
    # Walk and match braces so we don't trip on braces inside strings.
    depth = 0
    in_str = False
    esc = False
    for i in range(first, len(text)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[first:i + 1]
    return None


def _parse_response(raw: str) -> tuple[str, list[Concern], str]:
    """Return (overall, concerns, parse_error). On any failure,
    parse_error is non-empty and the raw text is kept as `overall`
    so the caller can still surface something useful."""
    block = _extract_json_block(raw)
    if not block:
        return (
            raw.strip()[:400] or "(no response)",
            [],
            "no JSON object found in response",
        )
    try:
        data = json.loads(block)
    except json.JSONDecodeError as e:
        return (
            raw.strip()[:400],
            [],
            f"JSON decode failed: {e}",
        )
    overall = str(data.get("overall") or "").strip()
    raw_concerns = data.get("concerns") or []
    if not isinstance(raw_concerns, list):
        return overall, [], "concerns field was not a list"
    concerns: list[Concern] = []
    for i, c in enumerate(raw_concerns):
        if not isinstance(c, dict):
            continue
        file_ = str(c.get("file") or "").strip()
        line = c.get("line")
        try:
            line_i = int(line) if line is not None else None
        except (TypeError, ValueError):
            line_i = None
        sev = str(c.get("severity") or "minor").strip().lower()
        if sev not in ("blocker", "major", "minor", "nit"):
            sev = "minor"
        text = str(c.get("text") or "").strip()
        sug = c.get("suggestion")
        sug_s = str(sug).strip() if sug and str(sug).strip() != "null" else None
        if not text:
            continue
        concerns.append(Concern(
            file=file_, line=line_i, severity=sev, text=text,
            suggestion=sug_s,
        ))
    return overall, concerns, ""


# ── the primitive ─────────────────────────────────────────────────────

def review(
    *,
    target_ref: str = "HEAD",
    model: str = "sonnet",
    diff_char_cap: int = 60000,
) -> ReviewResult:
    """Ask Claude to review a git ref.

    Args:
        target_ref     — a git commit id, branch, ref, or A..B range.
                         Default: the current HEAD commit.
        model          — any model the proxy can route. "sonnet"/"opus"
                         are the common choices for review work.
        diff_char_cap  — truncate the diff to this many chars before
                         sending. Prevents a large merge commit from
                         blowing the prompt context.

    Returns:
        ReviewResult with structured concerns. Never raises on a
        legitimate empty diff or empty concerns list — just returns
        a result with `overall` describing the state.

    Raises:
        RuntimeError — on git or claude_tier failures (unreachable
                       proxy, budget cap, adapter error). Caller
                       decides whether to retry or skip.
    """
    diff = _git_diff(target_ref)
    diff_size = len(diff)
    if not diff.strip():
        return ReviewResult(
            target_ref=target_ref, diff_size_chars=0,
            overall="(empty diff — nothing to review)",
            concerns=[], model_used="(not called)",
        )

    truncated_note = ""
    if len(diff) > diff_char_cap:
        truncated_note = (
            f"\n\n[NOTE: diff truncated from {len(diff)} to "
            f"{diff_char_cap} chars for context budget]"
        )
        diff = diff[:diff_char_cap]

    user_prompt = (
        f"Review this git diff for `{target_ref}`:\n\n"
        f"```diff\n{diff}\n```{truncated_note}"
    )

    try:
        tr = claude_tier.call(
            prompt=user_prompt,
            system_prompt=_REVIEW_SYSTEM_PROMPT,
            model=model,
            caller="self_dev/review",
        )
    except claude_tier.ClaudeTierError as e:
        raise RuntimeError(f"review call failed: {e}")

    overall, concerns, parse_err = _parse_response(tr.reply)
    return ReviewResult(
        target_ref=target_ref,
        diff_size_chars=diff_size,
        overall=overall,
        concerns=concerns,
        model_used=tr.model_used,
        input_tokens=tr.input_tokens,
        output_tokens=tr.output_tokens,
        raw_text=tr.reply,
        parse_error=parse_err,
    )


# ── CLI ───────────────────────────────────────────────────────────────

def _cli_review(args) -> int:
    try:
        result = review(target_ref=args.ref, model=args.model)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.json:
        out = asdict(result)
        print(json.dumps(out, indent=2))
        return 0

    # Human-readable output
    print(f"Review: {result.target_ref}")
    print(f"Model : {result.model_used}  "
          f"(tokens in/out: {result.input_tokens}/{result.output_tokens})")
    print(f"Diff  : {result.diff_size_chars} chars")
    print()
    print("Overall:")
    print(f"  {result.overall}")
    print()
    if result.parse_error:
        print(f"!! parse error: {result.parse_error}")
        print("-- raw response --")
        print(result.raw_text[:800])
        return 1
    counts = result.severity_counts()
    if not result.concerns:
        print("No concerns raised.")
        return 0
    print(f"Concerns ({len(result.concerns)}): "
          + ", ".join(f"{k}:{v}" for k, v in counts.items()))
    print()
    for i, c in enumerate(result.concerns, 1):
        loc = f"{c.file}:{c.line}" if c.line else c.file
        print(f"  [{c.severity}] #{i}  {loc}")
        print(f"    {c.text}")
        if c.suggestion:
            print(f"    → {c.suggestion}")
        print()
    return 0


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m core.self_dev",
        description="Maez self-development primitives (Claude-backed).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("review", help="Review a git ref with Claude")
    r.add_argument("ref", nargs="?", default="HEAD",
                    help="git ref or range (default: HEAD)")
    r.add_argument("--model", default="sonnet",
                    help="model name (default: sonnet)")
    r.add_argument("--json", action="store_true",
                    help="emit raw JSON result instead of human-readable")
    r.set_defaults(func=_cli_review)
    return p


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = _build_argparser()
    ns = parser.parse_args()
    sys.exit(ns.func(ns))
