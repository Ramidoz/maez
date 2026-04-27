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


class GetRecentDailyTests(unittest.TestCase):
    """``get_recent_daily(limit)`` was added 2026-04-27 to close the
    silent AttributeError gap in the lived-memory nightly job. Mirror
    of ``get_all_core``'s shape so the builder consumes both with no
    translation. Sort is newest-first by metadata timestamp, falling
    back to the daily-YYYY-MM-DD- id prefix."""

    def _mm_with_fake_daily(self, items):
        """Build a MemoryManager stub whose .daily collection returns
        the supplied items via Chroma's get/count contract."""

        class FakeDaily:
            def __init__(self, rows):
                self._rows = rows

            def count(self):
                return len(self._rows)

            def get(self, include=None):
                return {
                    "ids": [r["id"] for r in self._rows],
                    "documents": [r["content"] for r in self._rows],
                    "metadatas": [r["metadata"] for r in self._rows],
                }

        mm = _mm()
        mm.daily = FakeDaily(items)
        return mm

    def test_empty_collection_returns_empty_list(self):
        mm = self._mm_with_fake_daily([])
        self.assertEqual(mm.get_recent_daily(limit=5), [])

    def test_returns_newest_first_by_timestamp(self):
        items = [
            {
                "id": "daily-2026-04-22-aaa",
                "content": "older",
                "metadata": {"timestamp": "2026-04-22T08:00:00+00:00"},
            },
            {
                "id": "daily-2026-04-26-bbb",
                "content": "newer",
                "metadata": {"timestamp": "2026-04-26T08:00:00+00:00"},
            },
            {
                "id": "daily-2026-04-24-ccc",
                "content": "middle",
                "metadata": {"timestamp": "2026-04-24T08:00:00+00:00"},
            },
        ]
        mm = self._mm_with_fake_daily(items)
        out = mm.get_recent_daily(limit=10)
        self.assertEqual(
            [r["id"] for r in out],
            [
                "daily-2026-04-26-bbb",
                "daily-2026-04-24-ccc",
                "daily-2026-04-22-aaa",
            ],
        )
        self.assertEqual(out[0]["content"], "newer")

    def test_limit_caps_returned_count(self):
        items = [
            {
                "id": f"daily-2026-04-{day:02d}-x",
                "content": f"day {day}",
                "metadata": {"timestamp": f"2026-04-{day:02d}T08:00:00+00:00"},
            }
            for day in range(1, 11)
        ]
        mm = self._mm_with_fake_daily(items)
        self.assertEqual(len(mm.get_recent_daily(limit=3)), 3)

    def test_limit_zero_returns_empty(self):
        items = [
            {
                "id": "daily-2026-04-22-aaa",
                "content": "x",
                "metadata": {"timestamp": "2026-04-22T08:00:00+00:00"},
            }
        ]
        mm = self._mm_with_fake_daily(items)
        self.assertEqual(mm.get_recent_daily(limit=0), [])

    def test_falls_back_to_id_prefix_when_timestamp_missing(self):
        items = [
            {"id": "daily-2026-04-20-x", "content": "older", "metadata": {}},
            {"id": "daily-2026-04-26-x", "content": "newer", "metadata": {}},
        ]
        mm = self._mm_with_fake_daily(items)
        out = mm.get_recent_daily(limit=5)
        self.assertEqual(out[0]["id"], "daily-2026-04-26-x")
        self.assertEqual(out[1]["id"], "daily-2026-04-20-x")

    def test_shape_matches_get_all_core(self):
        items = [
            {
                "id": "daily-2026-04-26-x",
                "content": "summary text",
                "metadata": {"timestamp": "2026-04-26T08:00:00+00:00", "date": "2026-04-26"},
            }
        ]
        mm = self._mm_with_fake_daily(items)
        out = mm.get_recent_daily(limit=5)
        self.assertEqual(len(out), 1)
        row = out[0]
        # Same keys as get_all_core's output: id / content / metadata.
        self.assertEqual(set(row.keys()), {"id", "content", "metadata"})
        self.assertEqual(row["content"], "summary text")
        self.assertEqual(row["metadata"]["date"], "2026-04-26")


if __name__ == "__main__":
    unittest.main()
