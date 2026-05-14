# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Generate a mechanical session snapshot.

Honours the long-standing memory rule: "End of every session,
generate logs/session_snapshot_latest.txt + dated copy in
logs/snapshots/." The rule was documented but no generator
existed; only a consumer (skills/web_interface.py:803
_parse_session_snapshot) and hand-written snapshots from prior
sessions.

What this is NOT:
  • Not a handoff doc. ``docs/handoffs/YYYY-MM-DD.md`` is the
    narrative artifact (manually written, "next-action recipe"
    shaped). The snapshot is the mechanical companion —
    auto-generated, parser-readable, time-stamped.
  • Not a backup. The Decision-22 backup framework
    (scripts/backup/) covers DBs and configs; the snapshot is a
    structural state report.
  • Not exhaustive — quote-redacted on the private stores
    (private_thoughts.db / inner_residue.db are COUNTED, never
    excerpted). secret_file paths from
    backup_state_manifest.json are skipped entirely.

Output format (matches the consumer parser at
skills/web_interface.py:767-903):

  Maez — session snapshot
  =======================

  BUILD: Sessions <label>
  DATE: <ISO date>
  AGENT: <agent identifier>

  ====
  WHAT CHANGED TODAY
  ====

  - bullet 1
  - bullet 2

  ====
  PRODUCTION STATE
  ====

  - bullet
  ...

  ====
  NEXT SESSION PRIORITIES
  ====

  - bullet
  ...

The parser reads the three named sections specifically; any
additional `====` sections are preserved in ``result["sections"]``
but not surfaced in the cockpit dashboard.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))


# ── git helpers ──────────────────────────────────────────────────


def _git(*args: str, cwd: Path | None = None) -> str:
    """Run a git command; return stdout. Failures raise."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd or _REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (rc={proc.returncode}): "
            f"{proc.stderr.strip()}"
        )
    return proc.stdout


def _commits_since(since_spec: str) -> list[dict]:
    """Return commits since ``since_spec`` as ``{sha, subject, author_date}``
    dicts, oldest first."""
    out = _git(
        "log",
        f"--since={since_spec}",
        "--pretty=format:%H|%ad|%an|%s",
        "--date=iso",
        "--reverse",
    )
    rows: list[dict] = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        sha, ad, an, subject = parts
        rows.append({
            "sha": sha[:9],
            "date": ad,
            "author": an,
            "subject": subject,
        })
    return rows


def _head_short() -> str:
    return _git("rev-parse", "--short", "HEAD").strip()


# ── test count (cheap, never runs the suite) ─────────────────────


def _test_count() -> int:
    """Count the number of test functions in tests/. Doesn't run
    them; just greps for ``def test_`` so the snapshot is cheap."""
    count = 0
    for p in (_REPO / "tests").rglob("test_*.py"):
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        count += sum(
            1 for line in content.splitlines()
            if line.lstrip().startswith("def test_")
        )
    return count


# ── daemon state ─────────────────────────────────────────────────


def _systemctl_pid(unit: str) -> str | None:
    try:
        out = subprocess.run(
            ["systemctl", "show", "-p", "MainPID", "--value", unit],
            capture_output=True, text=True, check=False, timeout=5,
        )
        if out.returncode != 0:
            return None
        pid = out.stdout.strip()
        return pid if pid and pid != "0" else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _systemctl_active(unit: str) -> bool:
    try:
        out = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True, text=True, check=False, timeout=5,
        )
        return out.stdout.strip() == "active"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


_TRACKED_UNITS = (
    "maez.service",
    "maez-web.service",
    "maez-watchdog.service",
    "maez-subscription-proxy.service",
    "llama-server.service",
)


def _service_state() -> list[str]:
    out = []
    for unit in _TRACKED_UNITS:
        active = _systemctl_active(unit)
        pid = _systemctl_pid(unit)
        marker = "active" if active else "inactive"
        if pid:
            out.append(f"{unit}: {marker} (PID {pid})")
        else:
            out.append(f"{unit}: {marker}")
    return out


# ── store row counts (private stores are COUNTED, never quoted) ──


_COUNT_QUERIES: tuple[tuple[str, str, str], ...] = (
    ("memory/lived_episodes.db", "episodes", "lived episodes"),
    ("memory/private_thoughts.db", "private_thoughts",
     "private thoughts (count only)"),
    ("memory/wonderings.db", "wonderings", "wonderings"),
    ("memory/inner_residue.db", "residue_events",
     "inner residue events (count only)"),
    ("memory/entity_index.db", "entities", "entity index entries"),
    ("memory/entity_index.db", "entity_mentions", "entity mentions"),
    ("memory/entity_index.db", "aliases", "entity aliases"),
    ("memory/fast_conversation_log.db", "fast_turns",
     "fast-conversation turns"),
)


def _store_counts() -> list[str]:
    out = []
    for rel_path, table, label in _COUNT_QUERIES:
        path = _REPO / rel_path
        if not path.exists():
            out.append(f"{label}: (db absent)")
            continue
        try:
            con = sqlite3.connect(str(path))
            n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            con.close()
            out.append(f"{label}: {n}")
        except sqlite3.Error as e:
            out.append(f"{label}: (count failed: {e})")
    return out


# ── what changed today (commits, formatted) ──────────────────────


def _what_changed_bullets(commits: list[dict]) -> list[str]:
    """One bullet per commit. Latest first for legibility."""
    bullets = []
    for c in reversed(commits):  # latest first
        bullets.append(
            f"{c['date'][:16]} — {c['sha']} ({c['author']}): "
            f"{c['subject']}"
        )
    return bullets


def _next_priorities_bullets() -> list[str]:
    """Static next-priorities pulled from in-repo signal anchors.
    Matches the long-standing convention: snapshots reflect what
    the next session should orient on, derived mechanically from
    git state + outstanding TODO markers, not from this script's
    judgement."""
    out = []
    # Most recent handoff doc, if any — the operator's stated
    # next-action.
    handoffs = sorted(
        (_REPO / "docs").glob("HANDOFF-*.md"), reverse=True,
    )
    if handoffs:
        out.append(
            f"Read latest handoff: docs/{handoffs[0].name}"
        )
    # Track A anchor.
    if (_REPO / "docs" / "TRACK_A.md").exists():
        out.append("Track A anchor: docs/TRACK_A.md")
    # Most recent in-flight session-snapshot.
    out.append(
        "Run the substrate observation greps from "
        "docs/handoffs/2026-05-01.md if present"
    )
    return out


# ── render ──────────────────────────────────────────────────────


_SNAP_HEADER = "Maez — session snapshot"


def _section(title: str, bullets: list[str]) -> list[str]:
    """Render a section in the parser-expected shape: paired
    ``====`` delimiters wrap the title; bullets follow with a
    leading dash. Blank line trail."""
    bar = "=" * 40
    out = [
        bar,
        title,
        bar,
        "",
    ]
    if bullets:
        for b in bullets:
            out.append(f"- {b}")
    else:
        out.append("- (none)")
    out.append("")
    return out


def render_snapshot(
    *,
    since: str = "12 hours ago",
    label: str | None = None,
    agent: str = "Claude",
) -> str:
    """Return the full snapshot text. Pure function; no I/O
    beyond git invocations + sqlite COUNT queries."""
    head = _head_short()
    commits = _commits_since(since)
    test_n = _test_count()
    services = _service_state()
    counts = _store_counts()

    # Header block: BUILD / DATE / AGENT lines come BEFORE the
    # first ``=`` divider so the consumer parser picks them up.
    # The parser at skills/web_interface.py:826-846 stops at the
    # first divider line; the reference 2026-04-25 snapshot
    # doesn't have machine-parseable metadata for this reason
    # (its "Session window: ..." style isn't ALL-CAPS).
    lines: list[str] = [
        _SNAP_HEADER,
        "",
        f"BUILD: Sessions {label or 'auto'}",
        f"DATE: {datetime.now(timezone.utc).date().isoformat()}",
        f"AGENT: {agent}",
        f"HEAD: {head}",
        f"COMMITS_SINCE: {since}",
        f"COMMIT_COUNT: {len(commits)}",
        f"TEST_FUNCTIONS: {test_n}",
        "",
    ]

    lines += _section(
        "WHAT CHANGED TODAY",
        _what_changed_bullets(commits),
    )
    lines += _section("PRODUCTION STATE", services + counts)
    lines += _section(
        "NEXT SESSION PRIORITIES",
        _next_priorities_bullets(),
    )
    return "\n".join(lines)


def write_snapshot(text: str, *, label: str | None = None) -> tuple[Path, Path]:
    """Write the snapshot to ``logs/session_snapshot_latest.txt``
    AND a dated copy in ``logs/snapshots/``. Returns the two
    paths.

    Filename uses second resolution (``%Y-%m-%d_%H%M%S``) so two
    runs within the same minute do not silently overwrite each
    other — preserving every dated copy is the memory-rule
    contract. On the rare second-collision case, append a
    monotonic suffix (``_2``, ``_3``, …) until a free name is
    found."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    suffix = f"_{label}" if label else ""
    snapshots_dir = _REPO / "logs" / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    base = snapshots_dir / f"session_snapshot_{stamp}{suffix}.txt"
    dated = base
    counter = 2
    while dated.exists():
        dated = snapshots_dir / (
            f"session_snapshot_{stamp}{suffix}_{counter}.txt"
        )
        counter += 1
    latest = _REPO / "logs" / "session_snapshot_latest.txt"
    dated.write_text(text)
    latest.write_text(text)
    return dated, latest


# ── CLI ─────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.generate_session_snapshot",
        description=(
            "Generate logs/session_snapshot_latest.txt + dated copy "
            "in logs/snapshots/. Mechanical state capture; a "
            "consumer at skills/web_interface.py:_parse_session_snapshot "
            "renders this in the cockpit. Distinct from the narrative "
            "docs/handoffs/*.md."
        ),
    )
    p.add_argument(
        "--since", default="12 hours ago",
        help="Git --since spec (default: '12 hours ago').",
    )
    p.add_argument(
        "--label", default=None,
        help="Optional suffix for the dated filename "
             "(e.g. 'end-of-day').",
    )
    p.add_argument(
        "--agent", default="Claude",
        help="Agent identifier baked into the AGENT: header.",
    )
    p.add_argument(
        "--print-only", action="store_true",
        help="Print to stdout only; do not write any file.",
    )
    p.add_argument(
        "--json", action="store_true",
        help="Emit JSON metadata (no snapshot text written).",
    )
    args = p.parse_args(argv)

    text = render_snapshot(
        since=args.since,
        label=args.label,
        agent=args.agent,
    )

    if args.json:
        meta = {
            "head": _head_short(),
            "commit_count": len(_commits_since(args.since)),
            "test_functions": _test_count(),
            "services": _service_state(),
            "store_counts": _store_counts(),
            "since": args.since,
        }
        print(json.dumps(meta, indent=2, sort_keys=True, default=str))
        return 0

    if args.print_only:
        print(text)
        return 0

    dated, latest = write_snapshot(text, label=args.label)
    print(f"wrote {dated}")
    print(f"wrote {latest}")
    return 0


__all__ = [
    "main",
    "render_snapshot",
    "write_snapshot",
]


if __name__ == "__main__":
    raise SystemExit(main())
