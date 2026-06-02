import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.memory.episodes import EpisodeStore


class _FakeDaemon:
    """Minimal daemon stand-in: the hook reads only ``.lived_episodes``."""

    def __init__(self, store: EpisodeStore) -> None:
        self.lived_episodes = store


class ReflectionInputHygieneTest(unittest.TestCase):
    def test_reflection_episode_not_passed_to_synthesize(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._run_hygiene_assertion(Path(tmp))

    def _run_hygiene_assertion(self, tmp: Path) -> None:
        store = EpisodeStore(str(tmp / "ep.db"))
        # One prior reflection (must be EXCLUDED) and one real-evidence
        # episode (must remain: the stomach still eats original food).
        refl_id = store.add(
            title="prior reflection",
            summary="an earlier synthesized thought",
            participants=["maez"],
            source_memory_ids=["core-1"],
            source_kind="reflection",
        )
        core_id = store.add(
            title="core memory",
            summary="a real evidence episode",
            participants=["maez"],
            source_memory_ids=["raw-1"],
            source_kind="core_memory",
        )
        daemon = _FakeDaemon(store)

        captured: dict = {}

        def _spy(*, recent_episodes, recent_raw, llm_call, max_reflections, drop_sink):
            captured["recent_episodes"] = list(recent_episodes)
            return []

        from daemon.maez_daemon import _run_reflection_synthesis_nightly

        with mock.patch.dict(
            os.environ,
            {
                "MAEZ_REFLECTION_SYNTHESIS_ENABLED": "1",
                "MAEZ_REFLECTION_SYNTHESIS_WRITE": "",
            },
            clear=False,
        ), mock.patch("core.memory.reflection.synthesize_reflections", _spy):
            _run_reflection_synthesis_nightly(
                daemon,
                llm_call=lambda *a, **k: "",
                artifact_dir=tmp,
            )

        self.assertIn(
            "recent_episodes",
            captured,
            "synthesize_reflections was never called via the daemon hook",
        )
        ids = {ep.get("id") for ep in captured["recent_episodes"]}
        kinds = {ep.get("source_kind") for ep in captured["recent_episodes"]}
        self.assertIn(core_id, ids, "real-evidence episode must still be fed to synthesis")
        self.assertNotIn(refl_id, ids, "prior reflection must NOT be fed to synthesis")
        self.assertNotIn("reflection", kinds, "no reflection episode may reach the synthesis input pool")


if __name__ == "__main__":
    unittest.main()
