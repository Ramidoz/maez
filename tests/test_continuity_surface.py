import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


def _snapshot(model: str = "model-a") -> dict:
    return {
        "base_model": model,
        "soul_base_hash": "a" * 64,
        "soul_local_hash": "b" * 64,
        "frame_text_hash": "c" * 64,
        "policy_hash": "d" * 64,
        "self_card_applied": True,
    }


def _seed_run(store, run_id: str, ts: str, model: str, distance: float) -> None:
    store.record_run(
        snapshot=_snapshot(model),
        embedder_id="fake-minilm:3",
        battery_version="v0",
        run_id=run_id,
        ts=ts,
        answers=[
            {
                "question_id": "attention",
                "answer_text": f"answer-{run_id}",
                "dist_short": distance,
                "dist_mid": distance,
                "dist_long": distance,
            }
        ],
    )


class ContinuitySurfaceTests(unittest.TestCase):
    def test_show_is_disabled_when_flag_is_off(self):
        from scripts import continuity_fingerprint

        with mock.patch.dict(os.environ, {"MAEZ_CONTINUITY_FINGERPRINT": "0"}):
            rendered = continuity_fingerprint.render(["show"])

        self.assertIn("disabled", rendered)

    def test_show_renders_third_person_verdict_and_era(self):
        from core.continuity_fingerprint.store import ContinuityStore
        from scripts import continuity_fingerprint

        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            os.environ, {"MAEZ_CONTINUITY_FINGERPRINT": "1"}
        ):
            store = ContinuityStore(Path(td) / "continuity_fingerprint.db")
            _seed_run(store, "before-1", "2026-07-03T10:00:00Z", "model-a", 0.1)
            _seed_run(store, "before-2", "2026-07-03T10:01:00Z", "model-a", 0.1)
            _seed_run(store, "after-1", "2026-07-03T10:10:00Z", "model-b", 0.1)
            _seed_run(store, "after-2", "2026-07-03T10:11:00Z", "model-b", 0.1)
            swap_ts = datetime(2026, 7, 3, 10, 5, tzinfo=timezone.utc).timestamp()

            rendered = continuity_fingerprint.render(
                ["show"],
                store=store,
                swap_timestamps=[swap_ts],
            )

        self.assertIn("continuity fingerprint", rendered)
        self.assertIn("era=v0|fake-minilm:3", rendered)
        self.assertIn("embedder_id=fake-minilm:3", rendered)
        self.assertIn("continuity_survived", rendered)
        lowered = rendered.lower()
        for banned in ("i have", "i am", "i've", "my continuity"):
            self.assertNotIn(banned, lowered)

    def test_run_subcommand_delegates_to_sampler_when_enabled(self):
        from scripts import continuity_fingerprint

        sampler_fn = mock.Mock(return_value={"status": "recorded", "run_id": "r1", "answers": 6})
        with mock.patch.dict(os.environ, {"MAEZ_CONTINUITY_FINGERPRINT": "1"}):
            rendered = continuity_fingerprint.render(["run"], sampler_fn=sampler_fn)

        sampler_fn.assert_called_once_with()
        self.assertIn("recorded", rendered)
        self.assertIn("r1", rendered)


if __name__ == "__main__":
    unittest.main()
