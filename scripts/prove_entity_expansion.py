# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Synthetic proof harness for the entity-expansion pipeline (Step 5k).

Demonstrates, with controlled fake data, that:
  alias seeding + alias-aware backfill + entity expansion
can recover cross-session evidence that keyword-only recall misses.

Pairs with ``tests/test_entity_expansion_end_to_end.py`` — the test
asserts; this script makes the demonstration visible to a human.

Hard contract: this is a SYNTHETIC demonstration of architectural
capability, NOT a quality claim about Maez's real lived-memory.
The fixture is designed so the baseline misses by construction;
that's the point — to show the substrate can recover when the data
shape allows.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


_FLAG = "MAEZ_ENTITY_EXPANSION"

DISCLAIMER = (
    "SYNTHETIC PROOF — controlled fixture, not real-memory quality. "
    "The fixture is constructed so the baseline misses by design "
    "(the query nickname appears in no episode text). The proof "
    "is that the substrate CAN recover when the data shape allows."
)


@contextmanager
def _env_set(value: str | None):
    prior = os.environ.get(_FLAG)
    try:
        if value is None:
            os.environ.pop(_FLAG, None)
        else:
            os.environ[_FLAG] = value
        yield
    finally:
        if prior is None:
            os.environ.pop(_FLAG, None)
        else:
            os.environ[_FLAG] = prior


def _seed(td: Path):
    """Construct the synthetic world. Fully isolated to ``td`` —
    no interaction with the real entity_index.db / lived_episodes.db."""
    from core.memory.entity_index import EntityIndex
    from core.memory.episodes import EpisodeStore
    from core.memory.relationship_graph import RelationshipGraph

    ep = EpisodeStore(str(td / "lived_episodes.db"))
    g = RelationshipGraph(str(td / "lived_graph.db"))
    ix = EntityIndex(td / "entity_index.db")

    maya_id = ix.upsert_entity(
        "Maya Ananthan", kind="person",
        aliases=["Maya", "Mimi"],
    )
    ix.upsert_entity("Sample School", kind="organization")

    seeded = []
    seeded.append(("maya_first_day", ep.add(
        title="Maya started school today",
        summary="big day; she seemed excited and a little anxious",
        participants=["rohit"], source_memory_ids=["mem-1"],
        source_kind="conversation",
        occurred_at="2026-04-12T09:00:00+00:00",
    )))
    seeded.append(("maya_classroom", ep.add(
        title="classroom dynamics",
        summary="Maya seemed nervous about the new classroom",
        participants=["rohit"], source_memory_ids=["mem-2"],
        source_kind="conversation",
        occurred_at="2026-04-15T09:00:00+00:00",
    )))
    seeded.append(("sample_school_meeting", ep.add(
        title="Sample School meeting went well",
        summary="met the principal; positive vibes",
        participants=["rohit"], source_memory_ids=["mem-3"],
        source_kind="conversation",
        occurred_at="2026-04-18T09:00:00+00:00",
    )))
    seeded.append(("dinner", ep.add(
        title="quiet dinner",
        summary="we cooked together and watched a movie",
        participants=["rohit"], source_memory_ids=["mem-4"],
        source_kind="conversation",
        occurred_at="2026-04-20T09:00:00+00:00",
    )))
    seeded.append(("unrelated", ep.add(
        title="garage cleanup",
        summary="finally finished sorting the boxes",
        participants=["rohit"], source_memory_ids=["mem-5"],
        source_kind="conversation",
        occurred_at="2026-04-22T09:00:00+00:00",
    )))
    return ep, g, ix, maya_id, seeded


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.prove_entity_expansion",
        description=(
            "Synthetic proof: alias seeding + backfill + entity "
            "expansion recovers cross-session evidence keyword "
            "recall misses, on a controlled fixture. Demonstrates "
            "the architecture works when data shape allows."
        ),
    )
    p.add_argument(
        "--query", default="how is Mimi doing?",
        help="Query to demonstrate against (default uses the "
             "nickname 'Mimi' which appears in NO episode text).",
    )
    args = p.parse_args(argv)

    print(f"NOTE: {DISCLAIMER}", file=sys.stderr)
    print()

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        ep, g, ix, maya_id, seeded = _seed(tdp)

        print("=== Fixture ===")
        print(f"  EpisodeStore:  {tdp / 'lived_episodes.db'} (5 episodes)")
        print(f"  EntityIndex:   {tdp / 'entity_index.db'}")
        print( "  Curated entity: Maya Ananthan (kind=person), "
               "aliases=['Maya', 'Mimi']")
        print( "  Curated entity: Sample School (kind=organization)")
        print()
        for slug, eid in seeded:
            print(f"    {slug:<25} -> {eid}")
        print()

        # Backfill alias-aware.
        from core.memory.entity_backfill import backfill

        report = backfill(episodes=ep, ix=ix, write=True)
        print("=== Backfill ===")
        print(
            f"  episodes_scanned={report.episodes_scanned}, "
            f"new_entities={report.new_entities}, "
            f"new_mentions={report.new_mentions}"
        )
        print(
            f"  deterministic_mentions_new="
            f"{report.deterministic_mentions_new}, "
            f"alias_mentions_new={report.alias_mentions_new}, "
            f"ambiguous={report.ambiguous_alias_mentions}"
        )
        if report.alias_matches_by_alias:
            print("  alias matches by alias:")
            for surface, n in sorted(
                report.alias_matches_by_alias.items(),
                key=lambda kv: (-kv[1], kv[0]),
            ):
                print(f"    {surface!r}: {n} episode(s)")
        print()

        # A/B the brief.
        from core.memory.lived_recall import build_lived_recall_brief

        ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
        with _env_set(None):
            baseline = build_lived_recall_brief(
                args.query, episode_store=ep, graph=g,
                reference_time=ref, ix=ix,
            )
        with _env_set("1"):
            expanded = build_lived_recall_brief(
                args.query, episode_store=ep, graph=g,
                reference_time=ref, ix=ix,
            )

        print("=== Query ===")
        print(f"  {args.query!r}")
        print()
        print("=== Baseline (flag off) ===")
        if baseline:
            print(baseline)
        else:
            print("  (empty — keyword recall found no overlap with the query)")
        print()
        print("=== Expanded (flag on) ===")
        print(expanded if expanded else "  (empty)")
        print()

        # Per-episode recovery summary.
        recovered = [
            slug for slug, eid in seeded
            if eid in expanded and eid not in baseline
        ]
        print("=== Recovery ===")
        if recovered:
            print(
                f"  Episodes recovered by ENTITY EXPANSION (NOT in "
                f"baseline): {recovered}"
            )
        else:
            print("  No episodes were recovered.")
        print()
        print(
            "Read: when the keyword pass has no token overlap with the "
            "query (the nickname 'Mimi' never appears in any episode), "
            "the entity-expansion pipeline can still surface relevant "
            "sessions via the alias resolution chain Mimi → Maya "
            "Ananthan → mentions. This proves the architecture; whether "
            "real lived-memory benefits depends on whether real data "
            "has aliasable cross-session evidence to recover.",
            file=sys.stderr,
        )
    return 0


__all__ = ["DISCLAIMER", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
