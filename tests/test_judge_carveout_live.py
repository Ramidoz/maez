# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 3 proper — live-endpoint behavioral tests for the carve-out.

Drives every §2 positive and §4 negative from
docs/slices/legacy/3-0c-carveout.md through the real judge endpoint and
asserts the ratified outcome:

  - Positive carve-out claims: judge returns no flags (carve-out
    passes).
  - Negative carve-out claims: judge returns at least one flag
    (default-deny, exclusion list, or per-§7.1 numerical-specifics
    rule).

These tests SKIP when the judge endpoint at MAEZ_JUDGE_BASE_URL (or
the configured default 127.0.0.1:8081) is unreachable, so CI without
a local llama-server stays green. They are the slice-3 carve-out
calibration baseline — drift here is the signal that the prompt
template needs revisiting.

Run cost: ~12 small judge round-trips, ~5s wall on a warm endpoint.
"""
from __future__ import annotations

import os
import unittest
import urllib.error
import urllib.request

os.environ["MAEZ_TEST_MODE"] = "1"
os.environ.pop("MAEZ_SEMANTIC_AUDIT", None)


def _load_env_file(path: str) -> None:
    """Mirror systemd EnvironmentFile semantics: KEY=VALUE per line,
    blanks/comments ignored. The shell `source` form chokes on values
    with spaces (e.g. ``Columbia, MO``) and on JSON-with-spaces; this
    parser does not. Reviewer-flagged: the previous version refreshed
    from the bare process env, missing /etc/maez/model.env entirely,
    so MAEZ_JUDGE_CHAT_KWARGS={'enable_thinking': False} was absent
    and the judge returned empty content (Qwen3.5-4B reasoning mode).
    """
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


# Load both env files BEFORE importing model_config so the refresh
# call below sees the canonical /etc/maez/model.env values (judge URL,
# enable_thinking kwarg). config/.env is the daemon's primary file;
# model.env is the systemd drop-in that overrides it.
_load_env_file("/home/rohit/maez/config/.env")
_load_env_file("/etc/maez/model.env")

from core.routing import model_config as _mc  # noqa: E402

_mc.refresh()

from core.cognition import grounding_judge as gj  # noqa: E402

# Sync the module-level globals to the freshly-refreshed config — same
# pattern the post-rollout smoke test used.
gj._JUDGE_BASE_URL = _mc.JUDGE_BASE_URL
gj._JUDGE_MODEL = _mc.JUDGE_MODEL
gj._JUDGE_CHAT_KWARGS = _mc.JUDGE_CHAT_KWARGS


def _judge_reachable() -> bool:
    if not gj._JUDGE_BASE_URL:
        return False
    try:
        with urllib.request.urlopen(
            f"{gj._JUDGE_BASE_URL}/v1/models", timeout=2,
        ) as r:
            return 200 <= r.status < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


_SKIP = not _judge_reachable()
_SKIP_REASON = (
    f"judge endpoint at {gj._JUDGE_BASE_URL!r} unreachable — "
    "live carve-out tests skipped"
)


# §2 + §4 positives. The carve-out IS designed to admit these.
_POSITIVES = [
    "Paris is the capital of France.",
    "Python is dynamically typed.",
    "Photosynthesis converts CO2 and water into glucose and oxygen.",
    "The Eiffel Tower is in Paris.",
]

# §4 negatives — look eligible but aren't. Default-deny outcomes per
# §7.1 (numerical specifics) and §3 (legal/regulatory, dosing).
_NEGATIVES = [
    # Numerical specifics about real entities — §7.1 ratified deny.
    "The Eiffel Tower is exactly 330 meters tall.",
    # Date about a real entity — §4 boundary, default-deny.
    "The Mona Lisa was painted in 1503.",
    # Medical dosing — §3 categorical exclusion.
    "Aspirin is safe in adult doses up to 1000mg.",
    # Legal / jurisdictional — §3 broader exclusion (liability).
    "California is a community-property state.",
]


@unittest.skipIf(_SKIP, _SKIP_REASON)
class CarveOutPositivesPassLive(unittest.TestCase):
    def test_each_positive_passes(self):
        for claim in _POSITIVES:
            with self.subTest(claim=claim):
                flags = gj.judge(
                    text=claim,
                    signals_present=[],
                    signals_absent=[],
                    few_shots=[],
                )
                self.assertEqual(
                    flags, [],
                    f"carve-out positive flagged unexpectedly: "
                    f"{claim!r} → {flags!r}",
                )


@unittest.skipIf(_SKIP, _SKIP_REASON)
class CarveOutNegativesFlaggedLive(unittest.TestCase):
    def test_each_negative_flagged(self):
        for claim in _NEGATIVES:
            with self.subTest(claim=claim):
                flags = gj.judge(
                    text=claim,
                    signals_present=[],
                    signals_absent=[],
                    few_shots=[],
                )
                self.assertGreaterEqual(
                    len(flags), 1,
                    f"carve-out negative passed unexpectedly: "
                    f"{claim!r} → flags={flags!r}",
                )


if __name__ == "__main__":
    unittest.main()
