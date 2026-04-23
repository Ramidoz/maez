# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Tests for memory.memory_manager.format_for_prompt — age-relative framing.

Contract (2026-04-21): on top of the retrieval-truth attribution contract,
recalled entries must also be prefixed with age-relative language so the LLM
cannot mistake stored content as live. The block opens with a PAST
OBSERVATIONS header making the past-ness explicit at the first token.
"""

import os
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.memory_manager import MemoryManager  # noqa: E402


def _mm():
    # format_for_prompt is a pure method over `recalled` — we don't need
    # a real DB. Instantiate without calling __init__ to avoid spinning
    # up chroma collections.
    return MemoryManager.__new__(MemoryManager)


class FormatForPromptAgeFramingTests(unittest.TestCase):
    def test_format_for_prompt_prefixes_age_relative(self):
        mm = _mm()
        two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                {
                    "id": "raw-a",
                    "content": "cpu temperature spiked to 82C",
                    "metadata": {
                        "timestamp": two_hours_ago.isoformat(),
                        "cycle": 42,
                    },
                }
            ],
        }
        out = mm.format_for_prompt(recalled)
        self.assertTrue(
            "2 hours ago" in out or "2h ago" in out,
            f"expected age-relative '2 hours ago' or '2h ago' in output; got:\n{out}",
        )

    def test_format_for_prompt_has_past_framing_header(self):
        mm = _mm()
        recalled = {
            "core": [{"id": "c1", "content": "i am Maez"}],
            "daily": [],
            "raw": [],
        }
        out = mm.format_for_prompt(recalled)
        self.assertIn("PAST OBSERVATIONS", out)
        # Header must appear near the top (before the content)
        self.assertLess(out.index("PAST OBSERVATIONS"), out.index("i am Maez"))

    def test_format_for_prompt_handles_missing_timestamp(self):
        mm = _mm()
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                {
                    "id": "raw-notime",
                    "content": "something happened",
                    "metadata": {"cycle": 7},  # no timestamp
                }
            ],
        }
        # Must not raise
        out = mm.format_for_prompt(recalled)
        self.assertTrue(
            "earlier" in out.lower() or "previously" in out.lower(),
            f"expected fallback 'earlier'/'previously' for missing timestamp; got:\n{out}",
        )

    def test_format_for_prompt_handles_empty_recalled(self):
        mm = _mm()
        out = mm.format_for_prompt({"core": [], "daily": [], "raw": []})
        self.assertEqual(out, "")

    def test_format_for_prompt_handles_unix_float_timestamp(self):
        mm = _mm()
        ts = time.time() - (3 * 24 * 3600)  # 3 days ago
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                {
                    "id": "raw-b",
                    "content": "disk usage at 91%",
                    "metadata": {"timestamp": ts, "cycle": 100},
                }
            ],
        }
        out = mm.format_for_prompt(recalled)
        self.assertTrue(
            "3 days ago" in out or "3d ago" in out,
            f"expected '3 days ago' or '3d ago' for unix-float ts; got:\n{out}",
        )


if __name__ == "__main__":
    unittest.main()
