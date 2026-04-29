#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Deterministic trace harness — Slice 2 of the trace work.

Consumes the per-turn JSONL traces written by ``core.turn_traces`` (Slice 1
landed 2026-04-29 in commit fa9a148) and emits a structured PASS/WARN/FAIL
report. Every finding carries provenance (trace_id, file path, line number,
JSON path, matched value, reason) so a future agent can debug a flagged
trajectory without grepping raw logs.

Scope rules (per the Slice 2 plan):

- Trace files are UTC-dated; selection globs ``logs/traces/*.jsonl`` and
  sorts by mtime-newest-first. NEVER assume today's local date.
- Seven deterministic checks (see ``CHECKS`` below). No semantic judge.
- Provisional ``stale_claims_v1`` is narrow substring-only and marked
  provisional in the finding; future slice replaces with ground-truth
  comparison.
- Wired into ``track_a_harness`` as advisory tier (``--include-trace-checks``).

Failure model: this harness is a read-only consumer. It MUST NOT mutate
traces, mutate runtime DBs, or affect daemon behaviour in any way. A
malformed JSONL line is logged and skipped — one bad line never aborts a
run.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_TRACE_DIR = REPO_ROOT / "logs" / "traces"
DEFAULT_REPORT_DIR = REPO_ROOT / "logs" / "trace_harness"
DEFAULT_LATEST_N = 50
DEFAULT_LATENCY_WARN_MS = 30_000
DEFAULT_OWNER_SURFACES = {"UI", "telegram_surface", "web", "voice", "owner_bridge"}
HARNESS_VERSION = 1

logger = logging.getLogger("maez.trace_harness")


@dataclass
class Finding:
    """One harness verdict with full provenance.

    Fields beyond verdict/check/reason exist so a debugger can jump to
    the exact line in the exact file without grep — the harness obeys
    the same evidence covenant Maez itself does.
    """

    trace_id: str
    verdict: str  # "PASS" / "WARN" / "FAIL"
    check: str
    file: str
    line: int
    json_path: str
    matched_value: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


# ── individual checks ────────────────────────────────────────────────


def check_hash_invariant(trace: dict, *, file: str, line: int) -> list[Finding]:
    """final_text_hash == sent_text_hash == stored_text_hash. The
    audit-before-store invariant landed in commit ``cc010797`` says the
    same string is audited, sent to the caller, and stored to memory.
    Unequal hashes mean the invariant was bypassed somewhere — a real
    fail-class signal."""
    final = trace.get("final_text_hash", "")
    sent = trace.get("sent_text_hash", "")
    stored = trace.get("stored_text_hash", "")
    out: list[Finding] = []
    if sent != final:
        out.append(_finding(
            trace, file, line,
            verdict="FAIL", check="hash_invariant",
            json_path="sent_text_hash",
            matched_value=sent or "(empty)",
            reason=(
                f"sent_text_hash ({sent!r}) differs from final_text_hash "
                f"({final!r}); audit-before-store invariant violated"
            ),
        ))
    if stored != final:
        out.append(_finding(
            trace, file, line,
            verdict="FAIL", check="hash_invariant",
            json_path="stored_text_hash",
            matched_value=stored or "(empty)",
            reason=(
                f"stored_text_hash ({stored!r}) differs from final_text_hash "
                f"({final!r}); audit-before-store invariant violated"
            ),
        ))
    return out


def check_audit_required(
    trace: dict,
    *,
    file: str,
    line: int,
    owner_surfaces: set[str],
) -> list[Finding]:
    """Owner-facing surfaces (UI, telegram, web, voice) must have
    audit.ran == True. The exception is terminal_state="errored": the
    daemon may not be able to run audit on a non-existent reply when
    synthesis itself failed."""
    surface = trace.get("surface", "")
    if surface not in owner_surfaces:
        return []
    if trace.get("terminal_state") == "errored":
        return []
    audit = trace.get("audit") or {}
    if audit.get("ran"):
        return []
    return [_finding(
        trace, file, line,
        verdict="FAIL", check="audit_required",
        json_path="audit.ran",
        matched_value=str(audit.get("ran", False)),
        reason=(
            f"surface={surface!r} is owner-facing but audit did NOT run "
            f"and terminal_state was not 'errored'; reply may have bypassed "
            f"the audit gate"
        ),
    )]


_VALID_TERMINAL_STATES = frozenset({"replied", "errored", "timed_out", "denied"})


def check_terminal_state(trace: dict, *, file: str, line: int) -> list[Finding]:
    """terminal_state must be set explicitly to a known value. Empty
    or unknown states mean a code path returned without setting the
    field — a quiet bug the harness should surface."""
    state = trace.get("terminal_state", "")
    if state in _VALID_TERMINAL_STATES:
        return []
    return [_finding(
        trace, file, line,
        verdict="FAIL", check="terminal_state",
        json_path="terminal_state",
        matched_value=str(state) or "(empty)",
        reason=(
            f"terminal_state={state!r} is not one of "
            f"{sorted(_VALID_TERMINAL_STATES)}; either the daemon set an "
            f"unknown state or a code path didn't set one at all"
        ),
    )]


def check_latency(
    trace: dict,
    *,
    file: str,
    line: int,
    warn_ms: int,
) -> list[Finding]:
    """Above-threshold latency is a WARN, not a FAIL — slow turns
    happen. Threshold default is 30s; raise via --latency-warn-ms when
    investigating a latency regression specifically."""
    latency = int(trace.get("latency_ms") or 0)
    if latency <= warn_ms:
        return []
    return [_finding(
        trace, file, line,
        verdict="WARN", check="latency",
        json_path="latency_ms",
        matched_value=str(latency),
        reason=f"latency_ms={latency} exceeds warn threshold {warn_ms}",
    )]


# Non-terminating commands — these run forever (or until OOM) without
# external interrupt. The action engine's covenant gate refuses them
# pre-execution; if one shows up with status='ok', the gate let it
# through. Status='denied' means the gate worked and is a PASS.
#
# Rules:
#   tail -f               → forever
#   watch                 → repeats until killed
#   nvidia-smi -l/-lms/--loop  → polling loop
#   strace -p PID  (without -c) → attaches indefinitely; -c collects
#                                 stats and exits, terminating
_NONTERMINATING_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\btail\s+-f\b"), "tail -f"),
    (re.compile(r"\bwatch\b\s"), "watch"),
    (re.compile(r"\bnvidia-smi\b[^|;&]*\s(-l\s|-l$|-lms\b|--loop\b)"), "nvidia-smi loop"),
]
_STRACE_PID_RE = re.compile(r"\bstrace\b[^|;&]*\s-p\s+\d+")
_STRACE_TERMINATING_RE = re.compile(r"\bstrace\b[^|;&]*\s-c\b")


def _is_nonterminating(args_summary: str) -> tuple[bool, str]:
    for pat, label in _NONTERMINATING_PATTERNS:
        if pat.search(args_summary):
            return True, label
    if _STRACE_PID_RE.search(args_summary):
        # strace -p PID is non-terminating UNLESS -c is also present
        # (which collects counts and exits).
        if not _STRACE_TERMINATING_RE.search(args_summary):
            return True, "strace -p (without -c)"
    return False, ""


def check_nonterminating_tool(
    trace: dict,
    *,
    file: str,
    line: int,
) -> list[Finding]:
    """Flag any executed tool_call whose args_summary contains a
    non-terminating command. Only status='ok' counts as executed — a
    'denied' status means the covenant gate blocked it (PASS) and a
    'timeout' status is its own check (timeout_honesty)."""
    out: list[Finding] = []
    for idx, tc in enumerate(trace.get("tool_calls") or []):
        if (tc.get("status") or "") != "ok":
            continue
        args = tc.get("args_summary") or ""
        bad, label = _is_nonterminating(args)
        if bad:
            out.append(_finding(
                trace, file, line,
                verdict="FAIL", check="nonterminating_tool",
                json_path=f"tool_calls[{idx}].args_summary",
                matched_value=f"{label} :: {args[:200]}",
                reason=(
                    f"tool_call[{idx}] executed a non-terminating command "
                    f"({label!r}); covenant gate should have refused it"
                ),
            ))
    return out


# Phrases that suggest a final reply claimed success after a timeout.
# Narrow on purpose — false positives here are worse than false
# negatives, since a wrong FAIL erodes trust in the harness.
_SUCCESS_CLAIM_PATTERNS = [
    re.compile(r"\b(completed|finished|succeeded|done)\s+(successfully|cleanly)\b", re.IGNORECASE),
    re.compile(r"\b(operation|command|task)\s+(completed|succeeded)\b", re.IGNORECASE),
    re.compile(r"\bsuccessfully\s+(updated|installed|created|ran|executed)\b", re.IGNORECASE),
]


def check_timeout_honesty(
    trace: dict,
    *,
    file: str,
    line: int,
) -> list[Finding]:
    """If any tool_call timed out, the final excerpt must NOT claim
    success. This catches the class of failure where the daemon
    narrates around an unread result instead of admitting the
    timeout."""
    timed_out = [
        (idx, tc) for idx, tc in enumerate(trace.get("tool_calls") or [])
        if (tc.get("status") or "") == "timeout"
    ]
    if not timed_out:
        return []
    excerpt = trace.get("final_text_excerpt") or ""
    for pat in _SUCCESS_CLAIM_PATTERNS:
        m = pat.search(excerpt)
        if m:
            return [_finding(
                trace, file, line,
                verdict="FAIL", check="timeout_honesty",
                json_path="final_text_excerpt",
                matched_value=m.group(0),
                reason=(
                    f"{len(timed_out)} tool_call(s) timed out, but the final "
                    f"excerpt claims success ({m.group(0)!r}); the reply hid "
                    f"the timeout"
                ),
            )]
    return []


# v1: narrow substring match against a small known-stale list. Marked
# provisional — Slice 3+ replaces this with a runtime ground-truth
# provider that derives the stale set from `systemctl is-active` /
# `/v1/models` / etc. See `docs/HANDOFF-2026-04-28.md` for the path.
_STALE_CLAIMS_V1 = [
    "llama-server-vision",  # service was retired pre-2026-04-23
    "llama-judge",           # judge retired 2026-04-23
    "gemma-4-26",            # brain swapped to qwen36-27b on 2026-04-23
    "gemma4-26",             # alias variant
    "gemma:26",              # alias variant
]


def check_stale_claims(
    trace: dict,
    *,
    file: str,
    line: int,
) -> list[Finding]:
    """Provisional v1 — substring match for known stale infrastructure
    references. Future slice replaces this with a runtime ground-truth
    comparison (live model alias, active services, etc.)."""
    excerpt = trace.get("final_text_excerpt") or ""
    excerpt_lower = excerpt.lower()
    for needle in _STALE_CLAIMS_V1:
        if needle in excerpt_lower:
            return [_finding(
                trace, file, line,
                verdict="WARN", check="stale_claims_v1",
                json_path="final_text_excerpt",
                matched_value=needle,
                reason=(
                    f"final_text_excerpt mentions {needle!r}, which is on the "
                    f"known-stale list; provisional check, replace with "
                    f"runtime ground-truth comparison in a future slice"
                ),
            )]
    return []


# All checks in a deterministic order. The runner iterates this list
# per trace.
CHECKS = (
    "hash_invariant",
    "audit_required",
    "terminal_state",
    "latency",
    "nonterminating_tool",
    "timeout_honesty",
    "stale_claims_v1",
)


def _finding(
    trace: dict,
    file: str,
    line: int,
    *,
    verdict: str,
    check: str,
    json_path: str,
    matched_value: str,
    reason: str,
) -> Finding:
    return Finding(
        trace_id=trace.get("trace_id", "(unknown)"),
        verdict=verdict,
        check=check,
        file=file,
        line=line,
        json_path=json_path,
        matched_value=matched_value,
        reason=reason,
    )


# ── trace file discovery + selection ─────────────────────────────────


def discover_trace_files(base_dir: "str | Path") -> list[Path]:
    """Return all ``*.jsonl`` files in ``base_dir``. Returns an empty
    list if the directory doesn't exist. Sorting is by mtime newest-
    first so the caller can take the first N for "latest" semantics
    without depending on local-date filenames (trace files are
    UTC-dated; UTC midnight crosses local-date boundaries on most
    timezones)."""
    base = Path(base_dir)
    if not base.exists():
        return []
    files = sorted(
        base.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files


def _read_jsonl(path: Path) -> list[tuple[int, dict]]:
    """Yield (line_no, trace) for each parseable JSONL line. Malformed
    lines are logged and skipped — one bad line never aborts a run."""
    rows: list[tuple[int, dict]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, 1):
                if not raw.strip():
                    continue
                try:
                    rows.append((line_no, json.loads(raw)))
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "skipping malformed JSONL at %s:%d: %s",
                        path, line_no, exc,
                    )
    except OSError as exc:
        logger.warning("trace file unreadable: %s :: %s", path, exc)
    return rows


def select_latest_traces(files: list[Path], *, n: int) -> list[dict]:
    """Pick the ``n`` newest traces across the given files. Each trace
    dict carries an injected ``__source__`` field with the originating
    file path and line number so findings can cite provenance.

    Selection is by file mtime first (newest file wins) then by line
    order within the file (last line of a file is newest within that
    file because traces append-only). For the typical case of one
    file per UTC day, this means today's file's tail dominates.

    Defensive: re-sorts ``files`` by mtime newest-first regardless of
    caller-provided order, so an explicit ``--trace-file`` invocation
    or an unsorted list still yields newest-first traces."""
    # Sort newest-first by mtime. Files that no longer exist (race
    # with rotation) are silently dropped.
    sorted_files = sorted(
        (p for p in files if Path(p).exists()),
        key=lambda p: Path(p).stat().st_mtime,
        reverse=True,
    )
    selected: list[dict] = []
    for path in sorted_files:
        rows = _read_jsonl(path)
        for line_no, trace in reversed(rows):
            if len(selected) >= n:
                return selected
            trace["__source__"] = {
                "file": str(path),
                "line": line_no,
            }
            selected.append(trace)
    return selected


# ── runner ───────────────────────────────────────────────────────────


def run(
    *,
    trace_dir: "str | Path | None" = None,
    trace_file: "str | Path | None" = None,
    latest_n: int = DEFAULT_LATEST_N,
    owner_surfaces: "set[str] | None" = None,
    latency_warn_ms: int = DEFAULT_LATENCY_WARN_MS,
    report_dir: "str | Path | None" = None,
) -> dict:
    """Execute the harness and return the report dict. Also writes
    ``<report_dir>/trace_harness_latest.json`` for the parent harness
    + downstream tooling. Returns the report regardless of write
    success — the harness is read-only on caller path."""
    if trace_file:
        files = [Path(trace_file)]
    else:
        files = discover_trace_files(trace_dir or DEFAULT_TRACE_DIR)

    owner = owner_surfaces or DEFAULT_OWNER_SURFACES
    traces = select_latest_traces(files, n=latest_n)

    findings: list[Finding] = []
    for trace in traces:
        src = trace.get("__source__") or {}
        sf = src.get("file", "")
        sl = src.get("line", 0)
        findings.extend(check_hash_invariant(trace, file=sf, line=sl))
        findings.extend(check_audit_required(
            trace, file=sf, line=sl, owner_surfaces=owner,
        ))
        findings.extend(check_terminal_state(trace, file=sf, line=sl))
        findings.extend(check_latency(
            trace, file=sf, line=sl, warn_ms=latency_warn_ms,
        ))
        findings.extend(check_nonterminating_tool(trace, file=sf, line=sl))
        findings.extend(check_timeout_honesty(trace, file=sf, line=sl))
        findings.extend(check_stale_claims(trace, file=sf, line=sl))

    summary = {"PASS": 0, "WARN": 0, "FAIL": 0}
    # Per-trace summary: a trace is FAIL if any FAIL finding fires,
    # WARN if any WARN finding fires (and no FAIL), else PASS.
    by_trace: dict[str, set[str]] = {}
    for f in findings:
        by_trace.setdefault(f.trace_id, set()).add(f.verdict)
    for trace in traces:
        verdicts = by_trace.get(trace.get("trace_id", ""), set())
        if "FAIL" in verdicts:
            summary["FAIL"] += 1
        elif "WARN" in verdicts:
            summary["WARN"] += 1
        else:
            summary["PASS"] += 1

    report = {
        "harness_version": HARNESS_VERSION,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trace_dir": str(trace_dir or DEFAULT_TRACE_DIR),
        "files_read": [str(p) for p in files],
        "traces_scanned": len(traces),
        "summary": summary,
        "findings": [f.to_dict() for f in findings],
    }

    rd = Path(report_dir or DEFAULT_REPORT_DIR)
    try:
        rd.mkdir(parents=True, exist_ok=True)
        (rd / "trace_harness_latest.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
    except OSError as exc:
        logger.warning("trace harness report write failed: %s", exc)

    return report


def _short_summary(report: dict) -> str:
    s = report["summary"]
    files = len(report["files_read"])
    return (
        f"trace_harness v{report['harness_version']}: "
        f"scanned={report['traces_scanned']} traces from {files} file(s); "
        f"PASS={s['PASS']} WARN={s['WARN']} FAIL={s['FAIL']}; "
        f"findings={len(report['findings'])}"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--trace-dir", default=str(DEFAULT_TRACE_DIR))
    ap.add_argument(
        "--trace-file",
        default=None,
        help="explicit single file; overrides --trace-dir glob",
    )
    ap.add_argument("--latest", type=int, default=DEFAULT_LATEST_N)
    ap.add_argument(
        "--latency-warn-ms",
        type=int,
        default=DEFAULT_LATENCY_WARN_MS,
    )
    ap.add_argument(
        "--owner-surfaces",
        default=",".join(sorted(DEFAULT_OWNER_SURFACES)),
        help="comma-separated list of surface labels considered owner-facing",
    )
    ap.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    owner = {
        s.strip() for s in (args.owner_surfaces or "").split(",") if s.strip()
    }
    report = run(
        trace_dir=args.trace_dir,
        trace_file=args.trace_file,
        latest_n=args.latest,
        owner_surfaces=owner or DEFAULT_OWNER_SURFACES,
        latency_warn_ms=args.latency_warn_ms,
        report_dir=args.report_dir,
    )
    print(_short_summary(report))
    # Advisory tier — exit 0 even when WARNs/FAILs exist. The parent
    # harness decides what to do with the report.
    return 0


if __name__ == "__main__":
    sys.exit(main())
