# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Phase 7 reflection-synthesis contract (ADR 0019).

Generative-Agents-style synthesis: pull recent low-level memories
(episodes + raw entries), ask an LLM to draw a small number of
high-level inferences, store each inference as a new episode with
``source_kind="reflection"`` and source_memory_ids citing the
inputs the inference was drawn from.

The LLM is injected as a callable so tests run deterministically
without touching llama-server. The store layer is exercised through
:class:`core.memory.episodes.EpisodeStore` against a temp DB —
reflections are episodes, lived_recall picks them up for free.

Contracts pinned here:

- `synthesize_reflections` accepts recent episodes + raw, returns
  ``list[Reflection]`` capped at ``max_reflections``.
- Every reflection cites at least one source_memory_id (ADR 0019
  evidence requirement carries through).
- Empty input → empty output (no LLM call).
- Malformed LLM output → empty list (fail-open, never raise).
- ``persist_reflections`` writes each reflection as an episode with
  ``source_kind="reflection"`` and the cited source_memory_ids.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _episode(eid: str, title: str, summary: str, mem_ids: list[str]) -> dict:
    return {
        "id": eid,
        "title": title,
        "summary": summary,
        "source_memory_ids": mem_ids,
        "source_kind": "core",
        "created_at": "2026-04-27T12:00:00+00:00",
    }


def _raw(mid: str, content: str) -> dict:
    return {"id": mid, "content": content, "metadata": {"timestamp": "2026-04-27T12:00:00+00:00"}}


class SynthesizeShape(unittest.TestCase):
    def test_returns_empty_when_no_inputs(self):
        from core.memory.reflection import synthesize_reflections

        called = {"n": 0}

        def _stub(_prompt: str) -> str:
            called["n"] += 1
            return "[]"

        out = synthesize_reflections(
            recent_episodes=[],
            recent_raw=[],
            llm_call=_stub,
        )
        self.assertEqual(out, [])
        # No LLM call when there's no signal — saves a wasteful round-trip.
        self.assertEqual(called["n"], 0)

    def test_caps_at_max_reflections(self):
        from core.memory.reflection import synthesize_reflections

        eps = [
            _episode(f"ep-{i}", f"title {i}", f"summary {i}", [f"core-{i}"])
            for i in range(8)
        ]

        def _stub(_prompt: str) -> str:
            # Return more than the cap — the function must still cap.
            return (
                '[{"reflection": "obs A", "evidence": ["core-0", "core-1"]},'
                ' {"reflection": "obs B", "evidence": ["core-2"]},'
                ' {"reflection": "obs C", "evidence": ["core-3"]},'
                ' {"reflection": "obs D", "evidence": ["core-4"]},'
                ' {"reflection": "obs E", "evidence": ["core-5"]}]'
            )

        out = synthesize_reflections(
            recent_episodes=eps,
            recent_raw=[],
            llm_call=_stub,
            max_reflections=3,
        )
        self.assertEqual(len(out), 3)

    def test_each_reflection_cites_at_least_one_evidence_id(self):
        from core.memory.reflection import synthesize_reflections

        eps = [_episode("ep-1", "t", "s", ["core-X"])]

        def _stub(_prompt: str) -> str:
            return '[{"reflection": "owner cares about truth", "evidence": ["core-X"]}]'

        out = synthesize_reflections(
            recent_episodes=eps,
            recent_raw=[],
            llm_call=_stub,
        )
        self.assertEqual(len(out), 1)
        self.assertGreaterEqual(len(out[0].source_memory_ids), 1)

    def test_drops_reflections_with_no_evidence(self):
        """No-evidence reflections are fabrication-shaped — ADR 0019
        says every claim cites its source. Drop, don't store."""
        from core.memory.reflection import synthesize_reflections

        eps = [_episode("ep-1", "t", "s", ["core-X"])]

        def _stub(_prompt: str) -> str:
            return (
                '[{"reflection": "valid", "evidence": ["core-X"]},'
                ' {"reflection": "no evidence claim", "evidence": []}]'
            )

        out = synthesize_reflections(
            recent_episodes=eps,
            recent_raw=[],
            llm_call=_stub,
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].text, "valid")

    def test_malformed_llm_output_returns_empty(self):
        from core.memory.reflection import synthesize_reflections

        eps = [_episode("ep-1", "t", "s", ["core-X"])]

        def _stub(_prompt: str) -> str:
            return "not JSON, just rambling thoughts"

        out = synthesize_reflections(
            recent_episodes=eps,
            recent_raw=[],
            llm_call=_stub,
        )
        # Fail-open. No reflection is better than a garbage one.
        self.assertEqual(out, [])

    def test_llm_exception_returns_empty(self):
        from core.memory.reflection import synthesize_reflections

        eps = [_episode("ep-1", "t", "s", ["core-X"])]

        def _stub(_prompt: str) -> str:
            raise RuntimeError("simulated llama-server timeout")

        out = synthesize_reflections(
            recent_episodes=eps,
            recent_raw=[],
            llm_call=_stub,
        )
        # Same fail-open contract as the rest of lived memory.
        self.assertEqual(out, [])


class PersistShape(unittest.TestCase):
    """``persist_reflections`` writes each reflection as a new episode
    with ``source_kind="reflection"`` so lived_recall picks them up
    through the existing read path (no recall code change needed)."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._db = self._tmp.name

    def tearDown(self):
        try:
            os.unlink(self._db)
        except OSError:
            pass

    def test_persist_writes_reflection_episodes(self):
        from core.memory.reflection import Reflection, persist_reflections
        from core.memory.episodes import EpisodeStore

        store = EpisodeStore(self._db)
        refls = [
            Reflection(
                text="The owner consistently prioritizes truth over speed",
                source_memory_ids=["core-A", "core-B"],
            ),
            Reflection(
                text="Maez tends to over-claim infrastructure facts",
                source_memory_ids=["ep-001"],
            ),
        ]
        ids = persist_reflections(refls, episode_store=store)
        self.assertEqual(len(ids), 2)
        # Reflections must round-trip out of the store with their
        # distinguishing source_kind so callers can filter them.
        active = store.list_active()
        kinds = {ep["source_kind"] for ep in active}
        self.assertEqual(kinds, {"reflection"})
        summaries = {ep["summary"] for ep in active}
        self.assertIn("The owner consistently prioritizes truth over speed", summaries)
        # Title carries the reflection text so the lived_recall brief
        # formatter (which renders titles, not summaries) shows the
        # actual observation rather than a generic "reflection" label.
        titles = {ep["title"] for ep in active}
        self.assertTrue(
            any("truth over speed" in t for t in titles),
            f"reflection title must surface the text; got {titles!r}",
        )

    def test_persist_skips_no_evidence(self):
        from core.memory.reflection import Reflection, persist_reflections
        from core.memory.episodes import EpisodeStore

        store = EpisodeStore(self._db)
        # An empty source_memory_ids list violates ADR 0019. Skip rather
        # than raise — reflections are best-effort, not load-bearing.
        refls = [Reflection(text="bad", source_memory_ids=[])]
        ids = persist_reflections(refls, episode_store=store)
        self.assertEqual(ids, [])
        self.assertEqual(store.list_active(), [])


if __name__ == "__main__":
    unittest.main()
