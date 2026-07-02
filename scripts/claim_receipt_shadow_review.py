"""Summarize content-light claim/receipt rail shadow logs."""
from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

_EVENT_RE = re.compile(
    r"claim_receipt_rail\s+surface=(?P<surface>\S+)\s+"
    r"action_type=(?P<action_type>\S+)\s+"
    r"pattern_id=(?P<pattern_id>\S+)\s+"
    r"receipt_present=(?P<receipt_present>\S+)\s+"
    r"tense_class=(?P<tense_class>\S+)\s+"
    r"mode=(?P<mode>\S+)\s+"
    r"redo_outcome=(?P<redo_outcome>\S+)"
)


def parse_lines(lines: list[str]) -> list[dict]:
    events = []
    for line in lines:
        match = _EVENT_RE.search(line)
        if not match:
            continue
        event = match.groupdict()
        event["receipt_present"] = event["receipt_present"] == "True"
        events.append(event)
    return events


def summarize(events: list[dict]) -> dict:
    catches = [
        event
        for event in events
        if event["redo_outcome"] != "excluded" and not event["receipt_present"]
    ]
    excluded = [event for event in events if event["redo_outcome"] == "excluded"]
    return {
        "event_count": len(events),
        "catch_count": len(catches),
        "tense_exclusion_count": len(excluded),
        "receipt_present_count": sum(1 for event in events if event["receipt_present"]),
        "pattern_counts": dict(Counter(event["pattern_id"] for event in catches)),
        "redo_counts": dict(Counter(event["redo_outcome"] for event in events)),
    }


def write_markdown(
    summary: dict,
    *,
    fabricated_probe_caught: bool,
    honest_1745_probe_clean: bool,
) -> str:
    lines = [
        "# Claim-Receipt Shadow Review",
        "",
        "## Gate",
        f"- fabricated turn MUST catch: {'PASS' if fabricated_probe_caught else 'FAIL'}",
        f"- receipted 17:45 turn MUST NOT catch: {'PASS' if honest_1745_probe_clean else 'FAIL'}",
        "",
        "## Summary",
        f"- event_count: {summary['event_count']}",
        f"- catch_count: {summary['catch_count']}",
        f"- tense_exclusion_count: {summary['tense_exclusion_count']}",
        f"- receipt_present_count: {summary['receipt_present_count']}",
        f"- pattern_counts: {summary['pattern_counts']}",
        f"- redo_counts: {summary['redo_counts']}",
        "",
        "## Review Note",
        "This artifact is content-light. It contains no full reply text.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fabricated-probe-caught", action="store_true")
    parser.add_argument("--honest-1745-probe-clean", action="store_true")
    args = parser.parse_args()

    events = parse_lines(Path(args.log).read_text(errors="replace").splitlines())
    markdown = write_markdown(
        summarize(events),
        fabricated_probe_caught=args.fabricated_probe_caught,
        honest_1745_probe_clean=args.honest_1745_probe_clean,
    )
    Path(args.out).write_text(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
