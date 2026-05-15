# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""self_dev.py — Maez proposes improvements to its own code via the
Claude subscription.

Initial primitive: `review(target_ref)`. Given a git range (single commit
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
from pathlib import Path

from core.infra.secrets import sanitize_env
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

_MODULE_REVIEW_SYSTEM_PROMPT = """You are reviewing a Python module on \
behalf of Maez, an always-on local AI daemon. You are being invoked \
by Maez itself via its subscription proxy — treat this as a \
peer-review of code Maez (together with Claude Code) authored over \
time. The module has been in the codebase long enough to accumulate \
drift; your job is to find standing issues the commit-time review \
missed.

Review priorities, in order:

1. Dead or unreachable code: functions with zero callers inside \
   this module and no obvious public-API exposure (not imported \
   elsewhere by name, not a CLI entry, not a __main__ block). \
   Defensive fallback branches that can't be reached given the \
   module's own invariants.
2. Docstring rot: docstrings that describe behavior the code no \
   longer implements, that reference removed functions, or that \
   assert invariants the body violates.
3. Accumulated bugs: correctness issues that slipped past earlier \
   review — off-by-ones, swallowed exceptions, resources not \
   closed on error paths, silent fallback to None where the \
   caller expects a value.
4. Invariant drift: conditions the module's docstring or top-level \
   comments promise that the current code doesn't enforce.

DO NOT raise as concerns:
- Style / formatting.
- "Could be more extensible" without a concrete near-term caller.
- Missing tests (separate task).
- Generally useful features that could be added.
- Re-wordings of docstrings that are already correct.
- Functions used ONLY by test code — those are valid entry points.

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
module is clean to your eyes. Do not invent concerns to fill space.
"""


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

try:
    from core import paths as _paths
    _REPO_ROOT = str(_paths.home())
except Exception:
    _REPO_ROOT = str(Path(__file__).resolve().parents[2])

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
    # self-dev meta-review on e41a2db (concern #2): use Popen so we
    # can actively kill the child on timeout. subprocess.run leaves
    # the process orphaned on TimeoutExpired, which can hold git
    # index locks for subsequent calls in the same session.
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
            env=sanitize_env(),
        )
        try:
            stdout, stderr = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.communicate(timeout=2)
            except Exception:
                pass
            raise RuntimeError(f"git timed out resolving {target_ref!r}")
        if proc.returncode != 0:
            raise RuntimeError(
                f"git failed for ref {target_ref!r}: {(stderr or '')[:400]}"
            )
    except FileNotFoundError:
        raise RuntimeError("git binary not found on PATH")
    return stdout


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
    persist: bool = True,
    caller: str = "self_dev/review",
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
        persist        — if False, skip writing to self_dev.db (useful
                         for dry-run / testing).
        caller         — attribution string stored with the review
                         record; flows into the subscription_proxy
                         trajectory log for per-consumer slicing.

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
            caller=caller,
        )
    except claude_tier.ClaudeTierError as e:
        raise RuntimeError(f"review call failed: {e}")

    overall, concerns, parse_err = _parse_response(tr.reply)
    result = ReviewResult(
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

    # Persist is advisory — a failed write logs a warning but never
    # propagates. The in-memory ReviewResult is always what's returned.
    if persist:
        try:
            from core.self_dev_persistence import store_review
            store_review(result, caller=caller)
        except Exception as _pe:
            logger.warning("self_dev: persist failed (continuing): %s", _pe)

    return result


# ── test proposal — generates code, not feedback ─────────────────────

_TEST_PROPOSAL_SYSTEM_PROMPT = """You are proposing pytest/unittest \
test code for a Python module on behalf of Maez, an always-on local \
AI daemon.

Context you must respect:
- Maez uses Python's stdlib unittest (not pytest). Target imports \
  look like `import unittest`, `from unittest import mock`.
- Tests live under tests/ with filenames test_<modulename>.py.
- Tests are fully offline. Any filesystem, network, or subprocess \
  call MUST be mocked. Any sqlite use MUST route through a temporary \
  directory fixture (see tests/test_self_dev_persistence.py for the \
  pattern — MAEZ_*_DB env patch + importlib.reload).
- Tests must not require a running Claude proxy or a live daemon.

Your deliverable is a single Python test file. Respond ONLY with \
valid JSON in this shape, no prose before or after:

{
  "target_module": "path/relative/to/repo",
  "test_path":     "tests/test_<modulename>.py",
  "rationale":     "one-paragraph summary of what these tests cover \
and what they deliberately skip",
  "test_code":     "<complete Python source for the test file>"
}

The test_code field must be a self-contained file that runs under \
`python -m unittest tests.test_<modulename>`. It should include the \
license header, module docstring, imports, and `if __name__ == \
'__main__': unittest.main()` tail matching other test files in this \
repo. Reference tests/test_claude_tier.py or tests/test_self_dev.py \
as style exemplars.

Do NOT invent API that doesn't exist in the module. If the module \
is too thin or too glue-heavy to test meaningfully, return \
test_code: '' and rationale: 'module is not a useful unit-test \
target because <reason>'. Empty test_code is a valid, honest \
response.
"""


@dataclass
class TestProposal:
    """Output of propose_tests() — a complete test-file proposal ready
    to be written to disk (once approved) or reviewed.

    test_code may be empty — Claude refused because the module isn't
    a meaningful unit-test target. rationale explains why.
    """
    target_module: str
    test_path: str
    rationale: str
    test_code: str
    model_used: str
    input_tokens: int
    output_tokens: int
    raw_text: str = ""
    parse_error: str = ""

    def is_empty(self) -> bool:
        return not self.test_code.strip()


def _parse_test_proposal(raw: str) -> TestProposal:
    """Extract the TestProposal JSON envelope from a Claude response.
    Forgiving parser — same strategy as _parse_response."""
    block = _extract_json_block(raw)
    if not block:
        return TestProposal(
            target_module="", test_path="", rationale=raw.strip()[:400],
            test_code="", model_used="", input_tokens=0, output_tokens=0,
            raw_text=raw,
            parse_error="no JSON object found in response",
        )
    try:
        data = json.loads(block)
    except json.JSONDecodeError as e:
        return TestProposal(
            target_module="", test_path="", rationale=raw.strip()[:400],
            test_code="", model_used="", input_tokens=0, output_tokens=0,
            raw_text=raw,
            parse_error=f"JSON decode failed: {e}",
        )
    return TestProposal(
        target_module=str(data.get("target_module") or "").strip(),
        test_path=str(data.get("test_path") or "").strip(),
        rationale=str(data.get("rationale") or "").strip(),
        test_code=str(data.get("test_code") or ""),
        model_used="",  # filled by caller from TierReply
        input_tokens=0, output_tokens=0,
        raw_text=raw,
    )


def propose_tests(
    *,
    path: str,
    model: str = "sonnet",
    max_module_chars: int = 40000,
    caller: str = "self_dev/propose_tests",
) -> TestProposal:
    """Ask Claude to write unittest code for a module. Returns a
    TestProposal; the caller decides whether to write the file to
    disk (dry-run by default at the CLI layer).

    Deliberately not persisted: the test file itself is the artifact,
    and --write already puts it on disk. A future commit may add a
    proposals table if/when we want queue-style triage.
    """
    import os as _os
    from pathlib import Path as _Path

    p = _Path(path)
    if not p.is_absolute():
        p = _Path(_REPO_ROOT) / p
    if not p.exists() or not p.is_file():
        raise RuntimeError(f"propose_tests: no such file: {p}")

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"propose_tests: read failed: {e}")

    truncated_note = ""
    if len(content) > max_module_chars:
        truncated_note = (
            f"\n\n[NOTE: module truncated from {len(content)} to "
            f"{max_module_chars} chars; test coverage will be partial.]"
        )
        content = content[:max_module_chars]

    rel = _os.path.relpath(str(p), _REPO_ROOT)
    user_prompt = (
        f"Propose unittest tests for this module: `{rel}`\n\n"
        f"```python\n{content}\n```{truncated_note}"
    )

    try:
        tr = claude_tier.call(
            prompt=user_prompt,
            system_prompt=_TEST_PROPOSAL_SYSTEM_PROMPT,
            model=model,
            caller=caller,
            # Test generation emits more tokens than review. Give it
            # extra time before timing out.
            timeout_s=300.0,
        )
    except claude_tier.ClaudeTierError as e:
        raise RuntimeError(f"propose_tests call failed: {e}")

    proposal = _parse_test_proposal(tr.reply)
    proposal.model_used = tr.model_used
    proposal.input_tokens = tr.input_tokens
    proposal.output_tokens = tr.output_tokens
    # Auto-fill target_module if Claude left it blank but we know it
    if not proposal.target_module:
        proposal.target_module = rel
    return proposal


# ── module review (standing issues vs review's diff-time regressions) ─

def review_module(
    *,
    path: str,
    model: str = "sonnet",
    max_chars: int = 60000,
    persist: bool = True,
    caller: str = "self_dev/review_module",
) -> ReviewResult:
    """Ask Claude to review a whole Python module for standing issues
    (dead code, docstring rot, accumulated bugs, invariant drift).

    Complementary to review(): review() catches regressions a commit
    introduces; review_module() catches issues that slipped through
    every earlier commit. Target long-lived modules where drift has
    had time to accumulate.

    Args:
        path      — repo-relative or absolute path to the .py file.
        model     — any model the proxy can route.
        max_chars — truncate if longer. Most real modules fit under
                    this; the largest files in maez are ~5k lines
                    ~200k chars, which will be truncated. Manual
                    invocation on a truncated review is still useful
                    for the head of the module.
        persist   — if False, skip writing to self_dev.db (useful
                    for dry-run / testing).
        caller    — attribution string stored with the review record;
                    flows into the subscription_proxy trajectory log.

    Raises RuntimeError on git/tier failures (same contract as review).
    """
    import os
    from pathlib import Path

    p = Path(path)
    if not p.is_absolute():
        p = Path(_REPO_ROOT) / p
    if not p.exists():
        raise RuntimeError(f"review_module: no such file: {p}")
    if not p.is_file():
        raise RuntimeError(f"review_module: not a file: {p}")

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"review_module: read failed: {e}")

    size = len(content)
    truncated_note = ""
    if size > max_chars:
        truncated_note = (
            f"\n\n[NOTE: module truncated from {size} to {max_chars} "
            f"chars. Reviewing only the head.]"
        )
        content = content[:max_chars]

    # Present as a fenced python block with the relative path in the
    # header so Claude anchors concerns to that file in responses.
    rel = os.path.relpath(str(p), _REPO_ROOT)
    user_prompt = (
        f"Review this Python module: `{rel}`\n\n"
        f"```python\n{content}\n```{truncated_note}"
    )

    try:
        tr = claude_tier.call(
            prompt=user_prompt,
            system_prompt=_MODULE_REVIEW_SYSTEM_PROMPT,
            model=model,
            caller=caller,
            # Module reviews can emit long structured responses —
            # multiple concerns with rationales. 180s (tier default)
            # has timed out on ~40k-char modules. 300s matches the
            # propose_tests override and comfortably fits Sonnet's
            # observed response time on long-form prompts.
            timeout_s=300.0,
        )
    except claude_tier.ClaudeTierError as e:
        raise RuntimeError(f"module review call failed: {e}")

    overall, concerns, parse_err = _parse_response(tr.reply)
    # Coerce any empty-file field into the relative module path so
    # the concern is queryable by file — Claude sometimes omits it
    # when the path is obvious from context.
    for c in concerns:
        if not c.file:
            c.file = rel
    result = ReviewResult(
        target_ref=f"module:{rel}",
        diff_size_chars=size,
        overall=overall,
        concerns=concerns,
        model_used=tr.model_used,
        input_tokens=tr.input_tokens,
        output_tokens=tr.output_tokens,
        raw_text=tr.reply,
        parse_error=parse_err,
    )

    if persist:
        try:
            from core.self_dev_persistence import store_review
            store_review(result, caller=caller)
        except Exception as _pe:
            logger.warning("self_dev: persist failed (continuing): %s", _pe)

    return result


# ── CLI ───────────────────────────────────────────────────────────────

def _cli_review(args) -> int:
    try:
        result = review(
            target_ref=args.ref,
            model=args.model,
            persist=not args.no_persist,
        )
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


def _cli_propose_tests(args) -> int:
    try:
        p = propose_tests(path=args.path, model=args.model)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(asdict(p), indent=2))
        return 0

    print(f"Test proposal: {p.target_module}")
    print(f"Destination : {p.test_path}")
    print(f"Model       : {p.model_used}  "
          f"(tokens in/out: {p.input_tokens}/{p.output_tokens})")
    if p.parse_error:
        print(f"!! parse error: {p.parse_error}")
        print("-- raw response (truncated) --")
        print(p.raw_text[:1200])
        return 1
    print()
    print("Rationale:")
    print(f"  {p.rationale}")
    print()
    if p.is_empty():
        print("(Claude declined to propose tests — see rationale)")
        return 0

    if args.write:
        # T1.8 (2026-05-04 audit) — covenant gate. Refuse to write
        # without an explicit `--i-have-reviewed-the-diff` ack;
        # print the proposed test code so the operator can read it
        # and re-run with both flags. Self-dev cannot land code on
        # disk autonomously even at the operator's request — the
        # diff-review step is the rail.
        if not getattr(args, "i_have_reviewed_the_diff", False):
            print(
                "-- proposed test code (covenant gate; "
                "--write requires --i-have-reviewed-the-diff) --",
                file=sys.stderr,
            )
            for line in p.test_code.splitlines():
                print(f"  {line}")
            print(
                "\nrefuse: --write requires "
                "--i-have-reviewed-the-diff. Read the diff above "
                "and re-run with both flags to commit.",
                file=sys.stderr,
            )
            return 4
        import os as _os
        dest = p.test_path or f"tests/test_{_os.path.basename(p.target_module).replace('.py','')}.py"
        # self-dev meta-review on e41a2db (concern #1): use the
        # module-level _REPO_ROOT constant rather than a hardcoded
        # literal so test fixtures / repo relocations are honored.
        dest_abs = dest if _os.path.isabs(dest) else _os.path.join(
            _REPO_ROOT, dest,
        )
        if _os.path.exists(dest_abs) and not args.force:
            print(f"refuse: {dest_abs} already exists (--force to overwrite)",
                  file=sys.stderr)
            return 3
        _os.makedirs(_os.path.dirname(dest_abs), exist_ok=True)
        with open(dest_abs, "w") as f:
            f.write(p.test_code)
        print(f"written: {dest_abs} ({len(p.test_code)} chars)")
        print("Next: run it before trusting it —")
        try:
            from core.paths import home as _maez_home
            _repo = str(_maez_home())
        except Exception:
            _repo = _REPO_ROOT
        print(f"  cd {_repo} && "
              f".venv/bin/python3 -m unittest "
              f"{dest.replace('/', '.').replace('.py', '')}")
        return 0

    # Dry-run: show first 80 lines of the proposed test code
    print("-- proposed test code (dry-run; pass --write to save) --")
    lines = p.test_code.splitlines()
    for line in lines[:80]:
        print(f"  {line}")
    if len(lines) > 80:
        print(f"  … ({len(lines) - 80} more lines)")
    return 0


def _cli_review_module(args) -> int:
    try:
        result = review_module(
            path=args.path, model=args.model,
            persist=not args.no_persist,
        )
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(asdict(result), indent=2))
        return 0
    print(f"Module review: {result.target_ref}")
    print(f"Model        : {result.model_used}  "
          f"(tokens in/out: {result.input_tokens}/{result.output_tokens})")
    print(f"Size         : {result.diff_size_chars} chars")
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


def _cli_history(args) -> int:
    """Print the most recent N reviews (header only, no concerns)."""
    from core.self_dev_persistence import list_reviews
    import datetime as _dt
    rows = list_reviews(limit=args.limit)
    if not rows:
        print("(no reviews recorded)")
        return 0
    print(f"{'id':>4}  {'when':19s}  {'ref':24s}  "
          f"{'model':28s}  toks  overall")
    for r in rows:
        ts = _dt.datetime.fromtimestamp(r.ts).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{r.id:>4}  {ts:19s}  {r.target_ref[:24]:24s}  "
              f"{r.model_used[:28]:28s}  {r.input_tokens:>4}  "
              f"{r.overall[:80]}")
    return 0


def _cli_concerns(args) -> int:
    """List concerns with filters."""
    from core.self_dev_persistence import list_concerns
    status = None if args.status == "any" else args.status
    sev = None if args.severity == "any" else args.severity
    rows = list_concerns(status=status, severity_at_least=sev,
                          limit=args.limit)
    if not rows:
        print("(no matching concerns)")
        return 0
    print(f"{'id':>5}  {'sev':8s}  {'status':9s}  {'file:line':40s}  text")
    for c in rows:
        loc = f"{c.file}:{c.line}" if c.line else c.file
        print(f"{c.id:>5}  {c.severity:8s}  {c.status:9s}  "
              f"{loc[:40]:40s}  {c.text[:100]}")
    return 0


def _cli_resolve(args) -> int:
    """Transition a concern to a terminal state."""
    from core.self_dev_persistence import set_concern_status
    ok = set_concern_status(args.id, args.state, notes=args.notes)
    if not ok:
        print(f"concern #{args.id} not found or DB error", file=sys.stderr)
        return 2
    print(f"concern #{args.id} → {args.state}")
    if args.notes:
        print(f"  notes: {args.notes}")
    return 0


def _cli_stats(args) -> int:
    from core.self_dev_persistence import stats
    import json as _json
    s = stats(window_hours=args.window_hours)
    print(_json.dumps(s, indent=2))
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
    r.add_argument("--no-persist", action="store_true",
                    help="don't write this review to self_dev.db")
    r.set_defaults(func=_cli_review)

    rm = sub.add_parser(
        "review-module",
        help="Review a whole .py module for standing issues",
    )
    rm.add_argument("path", help="path to a Python module")
    rm.add_argument("--model", default="sonnet",
                     help="model name (default: sonnet)")
    rm.add_argument("--json", action="store_true",
                     help="emit raw JSON result")
    rm.add_argument("--no-persist", action="store_true",
                     help="don't write this review to self_dev.db")
    rm.set_defaults(func=_cli_review_module)

    pt = sub.add_parser(
        "propose-tests",
        help="Have Claude draft a unittest file for a module",
    )
    pt.add_argument("path", help="module to generate tests for")
    pt.add_argument("--model", default="sonnet",
                     help="model name (default: sonnet)")
    pt.add_argument("--json", action="store_true",
                     help="emit raw JSON result")
    pt.add_argument("--write", action="store_true",
                     help="write the proposed test file to disk "
                          "(dry-run by default, prints preview)")
    # T1.8 (2026-05-04 audit) — covenant gate. --write must be
    # paired with --i-have-reviewed-the-diff so generated test code
    # cannot land on disk without an explicit ack from the operator
    # that they've actually read the proposal. Run --write once
    # without this flag to print the diff; re-run with both flags
    # to commit.
    pt.add_argument(
        "--i-have-reviewed-the-diff",
        action="store_true",
        dest="i_have_reviewed_the_diff",
        help=(
            "Required co-flag for --write. Without it, --write "
            "prints the proposed test code and refuses to write. "
            "Re-run with this flag after reading the diff."
        ),
    )
    pt.add_argument("--force", action="store_true",
                     help="overwrite destination if it exists "
                          "(only relevant with --write)")
    pt.set_defaults(func=_cli_propose_tests)

    h = sub.add_parser("history", help="List recent reviews")
    h.add_argument("--limit", type=int, default=10)
    h.set_defaults(func=_cli_history)

    c = sub.add_parser("concerns", help="List concerns with filters")
    c.add_argument(
        "--status", default="open",
        choices=["any", "open", "resolved", "wont_fix", "rejected"],
        help="filter by concern status (default: open)",
    )
    c.add_argument(
        "--severity", default="any",
        choices=["any", "blocker", "major", "minor", "nit"],
        help="include concerns of this severity or higher",
    )
    c.add_argument("--limit", type=int, default=20)
    c.set_defaults(func=_cli_concerns)

    res = sub.add_parser("resolve", help="Transition a concern's state")
    res.add_argument("id", type=int, help="concern id")
    res.add_argument(
        "state", choices=["open", "resolved", "wont_fix", "rejected"],
        help="new state",
    )
    res.add_argument("--notes", default=None,
                      help="optional notes attached to the transition")
    res.set_defaults(func=_cli_resolve)

    st = sub.add_parser("stats", help="Usage + concern-bucket stats")
    st.add_argument("--window-hours", type=int, default=None,
                     help="restrict to trailing N hours (default: all time)")
    st.set_defaults(func=_cli_stats)

    return p


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = _build_argparser()
    ns = parser.parse_args()
    sys.exit(ns.func(ns))
