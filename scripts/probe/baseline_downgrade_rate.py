# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""5x.F.B operational watch — baseline_update downgrade rate.

The `5x.F.B` rule on `_do_update_baseline` (commit `bc6baa6`)
emits a structured log line every time the action fires:

    baseline_update provenance downgraded=<bool> \\
        untrusted_count=N recall_count=M

This script reads either ``journalctl`` (production daemon) or a
file (for replay / archive analysis), parses those lines, and
reports the three-region breakdown that determines whether the
rule lives, works, or needs a precision pass.

The decision tree (per the F.B operational watch in the handoff):

  ≤5%  fired → rule is dormant safety; no action.
  5–40% fired → real protection; watch ergonomics.
  ≥40%  fired → rule is over-aggressive; future precision slice.

Day-1 post-deploy is the most informative — a dramatically off
rate (zero or constant) signals a wiring assumption that didn't
match production reality.

Read-only. Reads the actions log; never writes.

CLI::

    .venv/bin/python scripts/probe/baseline_downgrade_rate.py
        # Reads `journalctl -u maez.service --since '24 hours ago'`

    .venv/bin/python scripts/probe/baseline_downgrade_rate.py \\
        --since '7 days ago'

    .venv/bin/python scripts/probe/baseline_downgrade_rate.py \\
        --file logs/actions.log

    .venv/bin/python scripts/probe/baseline_downgrade_rate.py \\
        --json   # machine-readable output for cockpit / next agent
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# Match the F.B log line emitted at action_engine.py via
# `action_logger.info("baseline_update provenance downgraded=%s
#  untrusted_count=%d recall_count=%d", ...)`. Robust to surrounding
# log-prefix noise (timestamps, level tags, journalctl headers).
_LINE_PATTERN = re.compile(
    r"baseline_update provenance "
    r"downgraded=(?P<downgraded>True|False) "
    r"untrusted_count=(?P<untrusted>\d+) "
    r"recall_count=(?P<recall>\d+)"
)

# Three-region thresholds (per the F.B handoff decision tree).
# Bounds are inclusive lower / exclusive upper for the working band.
_DORMANT_MAX = 0.05
_AGGRESSIVE_MIN = 0.40


@dataclass
class Stats:
    total: int
    downgraded: int
    untrusted_count_sum: int
    recall_count_sum: int
    # M1+M2: count of literal-substring matches for the F.B log
    # marker, regardless of whether the strict regex parsed them.
    # If `candidate_line_count > total`, the strict regex missed
    # something — likely a future log-format change. Without this
    # field, a parser regression looks identical to a quiet daemon
    # (both produce total=0 / region=no_data) and a confident
    # "rule fine" verdict misleads the operator. Surfacing the
    # delta is the seatbelt.
    candidate_line_count: int = 0

    @property
    def downgrade_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.downgraded / self.total

    @property
    def avg_untrusted_per_call(self) -> float:
        if self.total == 0:
            return 0.0
        return self.untrusted_count_sum / self.total

    @property
    def avg_recall_per_call(self) -> float:
        if self.total == 0:
            return 0.0
        return self.recall_count_sum / self.total

    def region(self) -> str:
        if self.total == 0:
            return "no_data"
        rate = self.downgrade_rate
        if rate <= _DORMANT_MAX:
            return "dormant"
        if rate >= _AGGRESSIVE_MIN:
            return "aggressive"
        return "working"


def _read_journalctl(since: str) -> str:
    """Read maez.service journal output. Returns the raw stdout.
    Falls open: returns "" + warns on stderr if journalctl is
    unavailable (running outside systemd, no permission, etc.)."""
    try:
        proc = subprocess.run(
            [
                "journalctl",
                "-u", "maez.service",
                "--since", since,
                "--no-pager",
            ],
            capture_output=True, text=True, timeout=30.0,
        )
    except FileNotFoundError:
        print(
            "warning: `journalctl` not available; pass --file to "
            "read a log file directly", file=sys.stderr,
        )
        return ""
    except subprocess.TimeoutExpired:
        print("warning: journalctl timed out", file=sys.stderr)
        return ""
    if proc.returncode != 0:
        print(
            f"warning: journalctl exited {proc.returncode}; "
            f"stderr: {proc.stderr.strip()}",
            file=sys.stderr,
        )
        # Still try the (possibly partial) stdout.
    return proc.stdout


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"warning: could not read {path}: {exc}", file=sys.stderr)
        return ""


def parse_lines(text: str) -> Stats:
    """Extract every F.B log line from the input text and aggregate
    the counters. Returns zeroed Stats if no matches found.

    Also counts literal-substring candidate lines (lines containing
    the F.B marker even if the strict regex didn't parse them) so a
    future log-format drift surfaces as a parser/candidate delta
    rather than a confident-but-wrong "no_data" verdict."""
    total = 0
    downgraded = 0
    untrusted_sum = 0
    recall_sum = 0
    for match in _LINE_PATTERN.finditer(text):
        total += 1
        if match.group("downgraded") == "True":
            downgraded += 1
        untrusted_sum += int(match.group("untrusted"))
        recall_sum += int(match.group("recall"))
    # Coarse count: lines containing the F.B marker substring.
    # Robust to surrounding format (timestamps, levels, locale).
    candidate_count = sum(
        1 for line in text.splitlines()
        if "baseline_update provenance" in line
    )
    return Stats(
        total=total,
        downgraded=downgraded,
        untrusted_count_sum=untrusted_sum,
        recall_count_sum=recall_sum,
        candidate_line_count=candidate_count,
    )


def parse_recall_count_distribution(text: str) -> dict[int, int]:
    """Bonus signal: distribution of `recall_count` values across
    every F.B fire. Helps an operator distinguish 'cycle bag is
    chronically empty' (signal that wiring isn't right) from
    'cycle bag fills, but never has untrusted' (signal the rule is
    correctly dormant)."""
    counter: Counter[int] = Counter()
    for match in _LINE_PATTERN.finditer(text):
        counter[int(match.group("recall"))] += 1
    return dict(sorted(counter.items()))


def _format_human(stats: Stats, recall_dist: dict[int, int],
                  source: str) -> str:
    lines = [
        "=== 5x.F.B BASELINE_UPDATE DOWNGRADE RATE ===",
        f"source:               {source}",
        f"total fires:          {stats.total}",
        f"candidate lines:      {stats.candidate_line_count}",
    ]
    # M1+M2 guard: surface parser-vs-candidate drift loudly. If
    # the marker substring appears but the strict regex parsed
    # nothing, the log format changed and the verdict below is
    # meaningless. Show the warning ABOVE the verdict so an
    # operator sees it before drawing a conclusion.
    if (stats.candidate_line_count > 0 and stats.total == 0):
        lines.extend([
            "",
            "WARNING: log-format drift detected.",
            f"  Found {stats.candidate_line_count} line(s) "
            "containing 'baseline_update provenance' but the "
            "strict regex parsed zero. The F.B log format may "
            "have changed; this CLI's verdict is unreliable "
            "until the parser is updated. Investigate before "
            "trusting any downgrade-rate claim from this run.",
        ])
        return "\n".join(lines)
    if stats.total == 0:
        lines.append("")
        lines.append(
            "no `baseline_update provenance` lines found.\n"
            "either the daemon hasn't fired update_baseline since "
            "the source window started, or F.B's log line wasn't "
            "emitted (wiring regression -- investigate). Try "
            "`--since '7 days ago'` to widen the window before "
            "assuming wiring regression."
        )
        return "\n".join(lines)
    lines.extend([
        f"downgrades:           {stats.downgraded}",
        f"downgrade rate:       {stats.downgrade_rate:.1%}",
        f"avg untrusted/call:   {stats.avg_untrusted_per_call:.2f}",
        f"avg recall/call:      {stats.avg_recall_per_call:.2f}",
        "",
        "recall_count distribution:",
    ])
    for recall_count, n in recall_dist.items():
        bar = "#" * min(40, n)
        lines.append(f"  recall_count={recall_count:>3}  n={n:>4}  {bar}")
    region = stats.region()
    region_label = {
        "dormant": "DORMANT (<=5%) -- rule is silent safety; no action",
        "working":
            "WORKING (5-40%) -- real protection; watch ergonomics",
        "aggressive":
            "AGGRESSIVE (>=40%) -- over-firing; future precision "
            "slice may relax the rule using this log as input data",
        "no_data": "NO DATA",
    }[region]
    lines.extend([
        "",
        f"verdict: {region_label}",
    ])
    if region == "dormant" and stats.avg_recall_per_call < 0.5:
        # Threshold of 0.5: recall_for_cycle returns at minimum
        # ~3 entries in a working daemon-cycle path, so an avg
        # below 0.5 strongly implies most fires came from
        # non-daemon contexts (chat handler / GUI / direct API)
        # where the bag is empty. Quiet legitimate periods produce
        # few fires at all, not many fires with empty bags, so
        # false alarms are unlikely. Don't tune blindly.
        lines.append(
            "  CAVEAT: avg recall/call is near-zero -- most fires "
            "happened with no recall context (likely non-daemon "
            "context paths). Per F.B's documented limitation, "
            "those fall through cleanly. Investigate if you "
            "expected daemon-cycle calls."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "").strip().splitlines()[0]
        if (__doc__ or "").strip()
        else "5x.F.B operational watch CLI",
    )
    src = ap.add_mutually_exclusive_group()
    src.add_argument(
        "--since", default="24 hours ago",
        help="journalctl --since window (default: '24 hours ago')",
    )
    src.add_argument(
        "--file", type=Path,
        help="read a log file instead of journalctl",
    )
    ap.add_argument(
        "--json", action="store_true",
        help="emit machine-readable JSON instead of human-readable",
    )
    args = ap.parse_args(argv)

    if args.file:
        text = _read_file(args.file)
        source = str(args.file)
    else:
        text = _read_journalctl(args.since)
        source = f"journalctl -u maez.service --since '{args.since}'"

    stats = parse_lines(text)
    recall_dist = parse_recall_count_distribution(text)

    if args.json:
        payload = {
            "source": source,
            **asdict(stats),
            "downgrade_rate": stats.downgrade_rate,
            "avg_untrusted_per_call": stats.avg_untrusted_per_call,
            "avg_recall_per_call": stats.avg_recall_per_call,
            "region": stats.region(),
            "recall_count_distribution": recall_dist,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_format_human(stats, recall_dist, source))
    return 0


if __name__ == "__main__":
    sys.exit(main())
