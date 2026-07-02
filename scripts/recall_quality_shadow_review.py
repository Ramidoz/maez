from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_PROBE_QUERIES = (
    "how are you",
    "what did you do",
    "what patterns do you notice",
)

RELATIONAL_KINDS = {"telegram_exchange"}

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

_TYPE_FLOOR_CANDIDATE_RE = re.compile(
    r"recall_type_floor_candidate tier=(?P<tier>\S+) "
    r"id=(?P<id>\S+) kind=(?P<kind>\S+) "
    r"distance=(?P<distance>[0-9.inf]+) "
    r"applied_floor=(?P<applied_floor>[0-9.]+) "
    r"(?:base_floor=(?P<base_floor>[0-9.]+) )?"
    r"would_drop=(?P<would_drop>True|False|true|false) "
    r"query_memory_ask=(?P<query_memory_ask>True|False|true|false) "
    r"retained=(?P<retained>True|False|true|false)"
)

_TYPE_FLOOR_SHADOW_RE = re.compile(
    r"recall_type_floor_shadow base_floor=(?P<base_floor>[0-9.]+) "
    r"self_digest_floor=(?P<self_digest_floor>[0-9.]+) "
    r"query_memory_ask=(?P<query_memory_ask>True|False|true|false) "
    r"candidate_count=(?P<candidate_count>\d+) "
    r"would_drop=(?P<would_drop>\d+) "
    r"dropped_self_digest=(?P<dropped_self_digest>\d+) "
    r"fallback_rescue_kind=(?P<fallback_rescue_kind>\S+) "
    r"actuated=(?P<actuated>True|False|true|false)"
)

_CONTEXT_FLOOR_CANDIDATE_RE = re.compile(
    r"recall_context_floor_candidate tier=(?P<tier>\S+) "
    r"id=(?P<id>\S+) kind=(?P<kind>\S+) "
    r"distance=(?P<distance>[0-9.inf]+) "
    r"applied_floor=(?P<applied_floor>pass|[0-9.]+) "
    r"base_floor=(?P<base_floor>[0-9.]+) "
    r"casual_floor=(?P<casual_floor>[0-9.]+) "
    r"would_drop=(?P<would_drop>True|False|true|false) "
    r"query_memory_ask=(?P<query_memory_ask>True|False|true|false) "
    r"retained=(?P<retained>True|False|true|false) "
    r"preview=(?P<preview>.*)"
)

_CONTEXT_FLOOR_SHADOW_RE = re.compile(
    r"recall_context_floor_shadow base_floor=(?P<base_floor>[0-9.]+) "
    r"casual_floor=(?P<casual_floor>[0-9.]+) "
    r"query_memory_ask=(?P<query_memory_ask>True|False|true|false) "
    r"candidate_count=(?P<candidate_count>\d+) "
    r"would_drop=(?P<would_drop>\d+) "
    r"fallback_rescue_kind=(?P<fallback_rescue_kind>\S+) "
    r"fallback_rescue_id=(?P<fallback_rescue_id>\S+) "
    r"actuated=(?P<actuated>True|False|true|false)"
)


def _bool_text(value: str) -> bool:
    return value.lower() == "true"


def _none_text(value: str) -> str | None:
    return None if value == "None" else value


def _floor_text(value: str) -> float | None:
    return None if value == "pass" else float(value)


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


def parse_type_floor_candidate(line: str) -> dict | None:
    match = _TYPE_FLOOR_CANDIDATE_RE.search(line)
    if match is None:
        return None
    return {
        "tier": match.group("tier"),
        "id": match.group("id"),
        "kind": match.group("kind"),
        "distance": float(match.group("distance")),
        "applied_floor": float(match.group("applied_floor")),
        "base_floor": (
            None
            if match.group("base_floor") is None
            else float(match.group("base_floor"))
        ),
        "would_drop": _bool_text(match.group("would_drop")),
        "query_memory_ask": _bool_text(match.group("query_memory_ask")),
        "retained": _bool_text(match.group("retained")),
    }


def parse_type_floor_shadow(line: str) -> dict | None:
    match = _TYPE_FLOOR_SHADOW_RE.search(line)
    if match is None:
        return None
    return {
        "base_floor": float(match.group("base_floor")),
        "self_digest_floor": float(match.group("self_digest_floor")),
        "query_memory_ask": _bool_text(match.group("query_memory_ask")),
        "candidate_count": int(match.group("candidate_count")),
        "would_drop": int(match.group("would_drop")),
        "dropped_self_digest": int(match.group("dropped_self_digest")),
        "fallback_rescue_kind": _none_text(match.group("fallback_rescue_kind")),
        "actuated": _bool_text(match.group("actuated")),
    }


def parse_context_floor_candidate(line: str) -> dict | None:
    match = _CONTEXT_FLOOR_CANDIDATE_RE.search(line)
    if match is None:
        return None
    return {
        "tier": match.group("tier"),
        "id": match.group("id"),
        "kind": match.group("kind"),
        "distance": float(match.group("distance")),
        "applied_floor": _floor_text(match.group("applied_floor")),
        "base_floor": float(match.group("base_floor")),
        "casual_floor": float(match.group("casual_floor")),
        "would_drop": _bool_text(match.group("would_drop")),
        "query_memory_ask": _bool_text(match.group("query_memory_ask")),
        "retained": _bool_text(match.group("retained")),
        "preview": match.group("preview"),
    }


def parse_context_floor_shadow(line: str) -> dict | None:
    match = _CONTEXT_FLOOR_SHADOW_RE.search(line)
    if match is None:
        return None
    return {
        "base_floor": float(match.group("base_floor")),
        "casual_floor": float(match.group("casual_floor")),
        "query_memory_ask": _bool_text(match.group("query_memory_ask")),
        "candidate_count": int(match.group("candidate_count")),
        "would_drop": int(match.group("would_drop")),
        "fallback_rescue_kind": _none_text(match.group("fallback_rescue_kind")),
        "fallback_rescue_id": _none_text(match.group("fallback_rescue_id")),
        "actuated": _bool_text(match.group("actuated")),
    }


def summarize_type_floor_rows(rows: list[dict]) -> dict:
    casual_self_digest = [
        row
        for row in rows
        if row.get("kind") == "self_digest" and not row.get("query_memory_ask")
    ]
    memory_self_digest = [
        row
        for row in rows
        if row.get("kind") == "self_digest" and row.get("query_memory_ask")
    ]
    casual_drops = [row for row in casual_self_digest if row.get("would_drop")]
    casual_resurrected = [
        row for row in casual_drops if row.get("retained")
    ]
    memory_drops = [row for row in memory_self_digest if row.get("would_drop")]
    memory_tightened = [
        row
        for row in memory_self_digest
        if row.get("base_floor") is not None
        and row.get("applied_floor", 0.0) < row["base_floor"]
    ]
    memory_kept = [row for row in memory_self_digest if row.get("retained")]
    return {
        "candidate_count": len(rows),
        "self_digest_candidate_count": len(casual_self_digest) + len(memory_self_digest),
        "casual_self_digest_drop_count": len(casual_drops),
        "casual_self_digest_resurrected_count": len(casual_resurrected),
        "memory_ask_self_digest_drop_count": len(memory_drops),
        "memory_ask_self_digest_tightened_count": len(memory_tightened),
        "memory_ask_self_digest_kept_count": len(memory_kept),
        "review_status": "review_required" if rows else "no_type_floor_rows",
        "sample_casual_drops": casual_drops[:20],
        "sample_memory_ask_drops": memory_drops[:20],
        "sample_memory_ask_tightened": memory_tightened[:20],
    }


def summarize_context_floor_rows(rows: list[dict]) -> dict:
    casual = [row for row in rows if not row.get("query_memory_ask")]
    memory_ask = [row for row in rows if row.get("query_memory_ask")]
    casual_drops = [row for row in casual if row.get("would_drop")]
    casual_drop_by_kind = Counter(row.get("kind", "unknown") for row in casual_drops)
    relational_tightened = [
        row
        for row in casual_drops
        if row.get("tier") in {"raw", "daily"}
        and row.get("kind") in RELATIONAL_KINDS
    ]
    core_candidates = [row for row in casual if row.get("tier") == "core"]
    core_drops = [row for row in casual_drops if row.get("tier") == "core"]
    core_pass_through = [
        row for row in core_candidates if row.get("applied_floor") is None
    ]
    memory_tightened = [
        row
        for row in memory_ask
        if row.get("applied_floor") is not None
        and row.get("base_floor") is not None
        and row["applied_floor"] < row["base_floor"]
    ]
    memory_kept = [row for row in memory_ask if row.get("retained")]
    return {
        "candidate_count": len(rows),
        "casual_drop_count": len(casual_drops),
        "casual_drop_by_kind": dict(sorted(casual_drop_by_kind.items())),
        "casual_relational_tightened_count": len(relational_tightened),
        "core_candidate_count": len(core_candidates),
        "core_drop_count": len(core_drops),
        "core_pass_through_count": len(core_pass_through),
        "memory_ask_tightened_count": len(memory_tightened),
        "memory_ask_kept_count": len(memory_kept),
        "review_status": "review_required" if rows else "no_context_floor_rows",
        "sample_casual_drops": casual_drops[:20],
        "sample_relational_tightened": relational_tightened[:20],
        "sample_core_drops": core_drops[:20],
        "sample_core_pass_through": core_pass_through[:20],
        "sample_memory_ask_tightened": memory_tightened[:20],
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
    type_floor_candidates: list[dict] = []
    type_floor_shadows: list[dict] = []
    context_floor_candidates: list[dict] = []
    context_floor_shadows: list[dict] = []
    if path.exists():
        for line in path.read_text(errors="replace").splitlines():
            candidate = parse_living_candidate(line)
            if candidate is not None:
                candidates.append(candidate)
            floor = parse_floor_shadow(line)
            if floor is not None:
                floors.append(floor)
            type_candidate = parse_type_floor_candidate(line)
            if type_candidate is not None:
                type_floor_candidates.append(type_candidate)
            type_shadow = parse_type_floor_shadow(line)
            if type_shadow is not None:
                type_floor_shadows.append(type_shadow)
            context_candidate = parse_context_floor_candidate(line)
            if context_candidate is not None:
                context_floor_candidates.append(context_candidate)
            context_shadow = parse_context_floor_shadow(line)
            if context_shadow is not None:
                context_floor_shadows.append(context_shadow)

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
        "type_floor_candidate_count": len(type_floor_candidates),
        "type_floor_shadow_count": len(type_floor_shadows),
        "type_floor_summary": summarize_type_floor_rows(type_floor_candidates),
        "context_floor_candidate_count": len(context_floor_candidates),
        "context_floor_shadow_count": len(context_floor_shadows),
        "context_floor_summary": summarize_context_floor_rows(
            context_floor_candidates
        ),
    }


def _content_preview(value: object, *, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


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
                        "preview": _content_preview(mem.get("content", "")),
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


class _CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.INFO)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


def probe_live_type_floor_rows(queries: list[str], *, manager=None) -> list[dict]:
    if not queries:
        return []

    from memory.memory_manager import MemoryManager

    if manager is None:
        manager = MemoryManager()

    old_env = {
        name: os.environ.get(name)
        for name in (
            "MAEZ_RECALL_FLOOR_SHADOW",
            "MAEZ_RECALL_FLOOR_ENABLED",
            "MAEZ_RECALL_TYPE_FLOOR_SHADOW",
            "MAEZ_RECALL_TYPE_FLOOR_ENABLED",
        )
    }
    os.environ["MAEZ_RECALL_FLOOR_SHADOW"] = "1"
    os.environ["MAEZ_RECALL_FLOOR_ENABLED"] = "1"
    os.environ["MAEZ_RECALL_TYPE_FLOOR_SHADOW"] = "1"
    os.environ["MAEZ_RECALL_TYPE_FLOOR_ENABLED"] = "0"

    logger = logging.getLogger("maez")
    old_level = logger.level
    logger.setLevel(logging.INFO)
    handler = _CaptureHandler()
    logger.addHandler(handler)
    try:
        rows: list[dict] = []
        for query in queries:
            start = len(handler.lines)
            manager.recall_for_telegram_living(query, record_recalls=False)
            for line in handler.lines[start:]:
                row = parse_type_floor_candidate(line)
                if row is not None:
                    row["source"] = "live_type_floor_probe"
                    row["query"] = query
                    rows.append(row)
        return rows
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
        for name, value in old_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def probe_live_context_floor_rows(queries: list[str], *, manager=None) -> list[dict]:
    if not queries:
        return []

    from memory.memory_manager import MemoryManager

    if manager is None:
        manager = MemoryManager()

    old_env = {
        name: os.environ.get(name)
        for name in (
            "MAEZ_RECALL_FLOOR_SHADOW",
            "MAEZ_RECALL_FLOOR_ENABLED",
            "MAEZ_RECALL_CONTEXT_FLOOR_SHADOW",
            "MAEZ_RECALL_CONTEXT_FLOOR_ENABLED",
        )
    }
    os.environ["MAEZ_RECALL_FLOOR_SHADOW"] = "1"
    os.environ["MAEZ_RECALL_FLOOR_ENABLED"] = "1"
    os.environ["MAEZ_RECALL_CONTEXT_FLOOR_SHADOW"] = "1"
    os.environ["MAEZ_RECALL_CONTEXT_FLOOR_ENABLED"] = "0"

    logger = logging.getLogger("maez")
    old_level = logger.level
    logger.setLevel(logging.INFO)
    handler = _CaptureHandler()
    logger.addHandler(handler)
    try:
        rows: list[dict] = []
        for query in queries:
            start = len(handler.lines)
            manager.recall_for_telegram_living(query, record_recalls=False)
            for line in handler.lines[start:]:
                row = parse_context_floor_candidate(line)
                if row is not None:
                    row["source"] = "live_context_floor_probe"
                    row["query"] = query
                    rows.append(row)
        return rows
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
        for name, value in old_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


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


def _probe_queries_from_args(args_probe_query: list[str] | None) -> list[str]:
    if args_probe_query:
        return list(args_probe_query)
    return list(DEFAULT_PROBE_QUERIES)


def write_markdown(
    path: Path,
    log_summary: dict,
    live_probe_summary: dict,
    context_floor_summary: dict,
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
        "## Context Floor Summary",
        "",
        "```json",
        json.dumps(context_floor_summary, indent=2, sort_keys=True),
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
        "- PASS v0.2 only if casual_drop_count > 0.",
        "- PASS v0.2 only if casual_relational_tightened_count == 0, "
        "or every relational sample is owner-reviewed as off-point.",
        "- PASS v0.2 only if core_drop_count == 0.",
        "- PASS v0.2 only if core_pass_through_count == core_candidate_count.",
        "- PASS v0.2 only if memory_ask_tightened_count == 0.",
        "- PASS v0.2 only if memory_ask_kept_count > 0.",
        "- HOLD if fallback rescue is not best_by_distance.",
        "- HOLD if reflection_bonus_shadow telemetry is absent on meta-query probes.",
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
    live_probe_rows = probe_live_candidate_kinds(
        _probe_queries_from_args(args.probe_query)
    )
    live_context_floor_rows = probe_live_context_floor_rows(
        _probe_queries_from_args(args.probe_query)
    )

    write_markdown(
        Path(args.out),
        summarize_logs(Path(args.log)),
        summarize_replay_rows(live_probe_rows),
        summarize_context_floor_rows(live_context_floor_rows),
        summarize_replay_rows(replay_rows),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
