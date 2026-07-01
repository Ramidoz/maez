from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_CANDIDATE_RE = re.compile(
    r"living_recall_candidate id=(?P<id>\S+) "
    r"base_distance=(?P<base>[0-9.]+) "
    r"recency_factor=(?P<recency>[0-9.]+) "
    r"effective_distance=(?P<effective>[0-9.]+) "
    r"shadow_promotion=(?P<promotion>None|[0-9.]+)"
    r"(?: kind=(?P<kind>\S+) type_weight=(?P<type_weight>[0-9.]+))?"
)

_FLOOR_RE = re.compile(
    r"recall_floor_shadow floor=(?P<floor>[0-9.]+) "
    r"raw_n=(?P<raw_n>\d+) raw_would_drop=(?P<raw_drop>\d+) "
    r"daily_n=(?P<daily_n>\d+) daily_would_drop=(?P<daily_drop>\d+) "
    r"would_empty=(?P<would_empty>True|False|true|false) "
    r"actuated=(?P<actuated>True|False|true|false)"
)


def parse_living_candidate(line: str) -> dict | None:
    match = _CANDIDATE_RE.search(line)
    if match is None:
        return None
    promotion = match.group("promotion")
    type_weight = match.group("type_weight")
    return {
        "id": match.group("id"),
        "base_distance": float(match.group("base")),
        "recency_factor": float(match.group("recency")),
        "effective_distance": float(match.group("effective")),
        "shadow_promotion": None if promotion == "None" else float(promotion),
        "kind": match.group("kind"),
        "type_weight": None if type_weight is None else float(type_weight),
    }


def parse_floor_shadow(line: str) -> dict | None:
    match = _FLOOR_RE.search(line)
    if match is None:
        return None
    return {
        "floor": float(match.group("floor")),
        "raw_n": int(match.group("raw_n")),
        "raw_would_drop": int(match.group("raw_drop")),
        "daily_n": int(match.group("daily_n")),
        "daily_would_drop": int(match.group("daily_drop")),
        "would_empty": match.group("would_empty").lower() == "true",
        "actuated": match.group("actuated").lower() == "true",
    }


def summarize_logs(path: Path) -> dict:
    candidates: list[dict] = []
    floors: list[dict] = []
    if path.exists():
        for line in path.read_text(errors="replace").splitlines():
            candidate = parse_living_candidate(line)
            if candidate is not None:
                candidates.append(candidate)
            floor = parse_floor_shadow(line)
            if floor is not None:
                floors.append(floor)

    distances = [row["base_distance"] for row in candidates]
    kinded = [row for row in candidates if row.get("kind") is not None]
    unknown = [row for row in kinded if row.get("kind") == "unknown"]
    reflections = [
        row for row in kinded if row.get("kind") in {"reflection", "maez_self"}
    ]
    return {
        "candidate_count": len(candidates),
        "kinded_candidate_count": len(kinded),
        "floor_receipt_count": len(floors),
        "base_distance_median": median(distances) if distances else None,
        "base_distance_min": min(distances) if distances else None,
        "base_distance_max": max(distances) if distances else None,
        "floor_would_empty_count": sum(1 for row in floors if row["would_empty"]),
        "unknown_share": (len(unknown) / len(kinded)) if kinded else None,
        "reflection_share": (len(reflections) / len(kinded)) if kinded else None,
    }


def probe_live_candidate_kinds(queries: list[str], *, manager=None) -> list[dict]:
    if not queries:
        return []

    from memory.memory_manager import (
        MemoryManager,
        _RECALL_RELEVANCE_FLOOR_DEFAULT,
        _passes_recall_floor,
        _recall_candidate_kind,
    )

    if manager is None:
        manager = MemoryManager()

    rows: list[dict] = []
    for query in queries:
        evidence, context = manager.recall_for_telegram_living(
            query,
            record_recalls=False,
        )
        for partition_name, partition in (
            ("evidence", evidence),
            ("context", context),
        ):
            for tier in ("daily", "raw"):
                for mem in partition.get(tier, []) or []:
                    dist = mem.get("distance")
                    rows.append({
                        "source": "live_probe",
                        "query": query,
                        "partition": partition_name,
                        "tier": tier,
                        "id": str(mem.get("id", ""))[:16],
                        "distance": (
                            float(dist) if isinstance(dist, (int, float)) else None
                        ),
                        "kind": _recall_candidate_kind(mem),
                        "would_drop": not _passes_recall_floor(
                            mem,
                            floor=_RECALL_RELEVANCE_FLOOR_DEFAULT,
                        ),
                    })
    return rows


def summarize_replay_rows(rows: list[dict]) -> dict:
    total = len(rows)
    drops = [row for row in rows if row.get("would_drop")]
    unknown = [row for row in rows if row.get("kind") == "unknown"]
    reflection_drops = [
        row for row in drops if row.get("kind") in {"reflection", "maez_self"}
    ]
    relational_kept = [
        row
        for row in rows
        if row.get("kind") == "telegram_exchange" and not row.get("would_drop")
    ]
    return {
        "candidate_count": total,
        "drop_count": len(drops),
        "unknown_share": (len(unknown) / total) if total else 0.0,
        "reflection_drop_share": (
            len(reflection_drops) / len(drops) if drops else 0.0
        ),
        "relational_kept_count": len(relational_kept),
        "review_status": "review_required" if total else "no_replay_rows",
        "sample_dropped": drops[:20],
    }


def write_markdown(
    path: Path,
    log_summary: dict,
    live_probe_summary: dict,
    replay_jsonl_summary: dict,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Recall Quality Shadow Review",
        "",
        "## Log Summary",
        "",
        "```json",
        json.dumps(log_summary, indent=2, sort_keys=True),
        "```",
        "",
        "## Live Probe Summary",
        "",
        "```json",
        json.dumps(live_probe_summary, indent=2, sort_keys=True),
        "```",
        "",
        "## Replay JSONL Summary",
        "",
        "```json",
        json.dumps(replay_jsonl_summary, indent=2, sort_keys=True),
        "```",
        "",
        "## Owner Review Gate",
        "",
        "- PASS only if dropped candidates are visibly low-relevance noise.",
        "- PASS only if unknown_share shows type damping is not a silent no-op.",
        "- HOLD if on-point relational context appears in the dropped sample.",
        "- HOLD if floor_would_empty_count suggests likely answer starvation.",
    ]
    path.write_text("\n".join(lines) + "\n")


def _read_replay_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(errors="replace").splitlines():
        if line.strip():
            row = json.loads(line)
            row["source"] = "replay_jsonl"
            rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="logs/maez.log")
    parser.add_argument("--replay-jsonl", default="")
    parser.add_argument("--probe-query", action="append", default=[])
    parser.add_argument(
        "--out",
        default="docs/proof/2026-07-01-recall-quality-shadow-review.md",
    )
    args = parser.parse_args(argv)

    replay_rows: list[dict] = []
    if args.replay_jsonl:
        replay_rows.extend(_read_replay_jsonl(Path(args.replay_jsonl)))
    live_probe_rows = probe_live_candidate_kinds(args.probe_query)

    write_markdown(
        Path(args.out),
        summarize_logs(Path(args.log)),
        summarize_replay_rows(live_probe_rows),
        summarize_replay_rows(replay_rows),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
