from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

PROBE_PATH = _REPO_ROOT / "memory" / "recall_baseline_probes.json"
DEFAULT_OUTPUT_PATH = _REPO_ROOT / "memory" / "recall_baseline.json"
_MEMORY_ID_RE = re.compile(r"\b(?:ep|raw|core|daily)-[A-Za-z0-9_.:-]+\b")


@dataclass(frozen=True)
class Probe:
    probe_id: str
    query: str
    intent: str


def load_probe_seed(path: Path | str = PROBE_PATH) -> list[Probe]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("authorship") != "rohit":
        raise ValueError("recall baseline probes must be Rohit-authored")
    return [
        Probe(
            probe_id=str(row["id"]),
            query=str(row["query"]),
            intent=str(row.get("intent", "")),
        )
        for row in data["probes"]
    ]


def extract_memory_ids(brief: str) -> list[str]:
    seen: list[str] = []
    for match in _MEMORY_ID_RE.finditer(brief or ""):
        memory_id = match.group(0)
        if memory_id not in seen:
            seen.append(memory_id)
    return seen


def compare_memory_id_rankings(
    *,
    baseline: list[str],
    candidate: list[str],
    min_overlap_ratio: float = 0.80,
    max_rank_delta_sum: int = 0,
) -> dict:
    baseline_positions = {mid: i for i, mid in enumerate(baseline)}
    candidate_positions = {mid: i for i, mid in enumerate(candidate)}
    overlap = [mid for mid in baseline if mid in candidate_positions]
    rank_delta_sum = sum(
        abs(baseline_positions[mid] - candidate_positions[mid])
        for mid in overlap
    )
    overlap_ratio = (len(overlap) / len(baseline)) if baseline else 1.0
    return {
        "baseline_count": len(baseline),
        "candidate_count": len(candidate),
        "overlap_count": len(overlap),
        "overlap_ratio": overlap_ratio,
        "rank_delta_sum": rank_delta_sum,
        "passes": (
            overlap_ratio >= min_overlap_ratio
            and rank_delta_sum <= max_rank_delta_sum
        ),
    }


def run_recall_baseline(
    *,
    probes: list[Probe],
    episode_store,
    graph,
    max_items: int = 6,
    build_fn: Callable | None = None,
) -> dict:
    if build_fn is None:
        from core.memory.lived_recall import build_lived_recall_brief

        build_fn = build_lived_recall_brief
    out = {
        "schema_version": "maez-recall-baseline-v1",
        "source": "build_lived_recall_brief",
        "metric": "deterministic_memory_id_overlap_and_rank",
        "probes": [],
    }
    for probe in probes:
        start = time.perf_counter()
        brief = build_fn(
            probe.query,
            episode_store=episode_store,
            graph=graph,
            max_items=max_items,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        out["probes"].append({
            "id": probe.probe_id,
            "query": probe.query,
            "intent": probe.intent,
            "memory_ids": extract_memory_ids(brief),
            "brief_chars": len(brief or ""),
            "prefill_latency_ms": None,
            "decode_latency_ms": None,
            "elapsed_ms": round(elapsed_ms, 3),
            "context_tokens": None,
            "generated_tokens": None,
        })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ or "Recall baseline runner")
    parser.add_argument(
        "--episode-db",
        default=str(_REPO_ROOT / "memory" / "lived_episodes.db"),
    )
    parser.add_argument(
        "--graph-db",
        default=str(_REPO_ROOT / "memory" / "lived_graph.db"),
    )
    parser.add_argument("--probes", default=str(PROBE_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--max-items", type=int, default=6)
    args = parser.parse_args(argv)

    from core.memory.episodes import EpisodeStore
    from core.memory.relationship_graph import RelationshipGraph

    for db_path in (Path(args.episode_db), Path(args.graph_db)):
        if not db_path.exists():
            raise SystemExit(f"required lived-memory db does not exist: {db_path}")

    report = run_recall_baseline(
        probes=load_probe_seed(args.probes),
        episode_store=EpisodeStore(args.episode_db),
        graph=RelationshipGraph(args.graph_db),
        max_items=args.max_items,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote recall baseline: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
