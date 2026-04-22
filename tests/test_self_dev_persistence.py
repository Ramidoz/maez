# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.self_dev_persistence — SQLite sidecar for self-dev
review results + concerns, and its integration with core.self_dev."""
from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class _BaseWithTempDb(unittest.TestCase):
    """Re-route the DB path to a temp file and reload the module so
    the module-level DB_PATH constant picks it up."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "self_dev.db"
        self._env = mock.patch.dict(
            os.environ, {"MAEZ_SELF_DEV_DB": str(self._db_path)},
        )
        self._env.start()
        from core import self_dev_persistence
        importlib.reload(self_dev_persistence)
        self.p = self_dev_persistence

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()


def _make_fake_result(
    target="HEAD", concerns=None, parse_error="", diff_size=500,
):
    """Build a ReviewResult stand-in without depending on the real
    class import (avoids circular reload)."""
    from core.self_dev import Concern, ReviewResult
    return ReviewResult(
        target_ref=target,
        diff_size_chars=diff_size,
        overall="test overall",
        concerns=concerns or [],
        model_used="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=200,
        raw_text="(raw)",
        parse_error=parse_error,
    )


class WriteAndRead(_BaseWithTempDb):
    def test_store_review_persists_review_and_concerns(self):
        from core.self_dev import Concern
        result = _make_fake_result(
            concerns=[
                Concern(file="a.py", line=10, severity="major",
                         text="bug one", suggestion="fix this"),
                Concern(file="b.py", line=None, severity="nit",
                         text="typo", suggestion=None),
            ],
        )
        rid = self.p.store_review(result, caller="test")
        self.assertIsInstance(rid, int)

        loaded = self.p.get_review_with_concerns(rid)
        self.assertIsNotNone(loaded)
        review, concerns = loaded
        self.assertEqual(review.target_ref, "HEAD")
        self.assertEqual(review.caller, "test")
        self.assertEqual(len(concerns), 2)
        self.assertEqual(concerns[0].severity, "major")
        self.assertEqual(concerns[1].status, "open")  # default
        self.assertEqual(concerns[1].suggestion, None)

    def test_list_reviews_newest_first(self):
        r1 = self.p.store_review(
            _make_fake_result(target="HEAD~2"), caller="test",
        )
        r2 = self.p.store_review(
            _make_fake_result(target="HEAD~1"), caller="test",
        )
        r3 = self.p.store_review(
            _make_fake_result(target="HEAD"), caller="test",
        )
        rows = self.p.list_reviews()
        self.assertEqual([r.id for r in rows[:3]], [r3, r2, r1])


class ConcernFilters(_BaseWithTempDb):
    def test_filter_by_status_and_severity(self):
        from core.self_dev import Concern
        self.p.store_review(
            _make_fake_result(
                target="HEAD",
                concerns=[
                    Concern(file="a", line=1, severity="blocker", text="b"),
                    Concern(file="a", line=2, severity="major", text="m"),
                    Concern(file="a", line=3, severity="nit", text="n"),
                ],
            ),
            caller="test",
        )
        # All open by default
        self.assertEqual(
            len(self.p.list_concerns(status="open")),
            3,
        )
        # Severity filter: major and above
        self.assertEqual(
            len(self.p.list_concerns(status="open", severity_at_least="major")),
            2,
        )
        # Severity filter: blocker only
        self.assertEqual(
            len(self.p.list_concerns(status="open",
                                       severity_at_least="blocker")),
            1,
        )


class StateTransitions(_BaseWithTempDb):
    def test_resolve_then_reopen(self):
        from core.self_dev import Concern
        rid = self.p.store_review(
            _make_fake_result(
                concerns=[Concern(file="a", line=1, severity="major",
                                   text="bug")],
            ),
            caller="test",
        )
        cid = self.p.get_review_with_concerns(rid)[1][0].id

        self.assertTrue(self.p.set_concern_status(
            cid, "resolved", notes="fixed in next commit",
        ))
        after = self.p.get_review_with_concerns(rid)[1][0]
        self.assertEqual(after.status, "resolved")
        self.assertIsNotNone(after.resolved_at)
        self.assertEqual(after.resolution_notes, "fixed in next commit")

        # Reopen clears the resolution metadata
        self.assertTrue(self.p.set_concern_status(cid, "open"))
        reopened = self.p.get_review_with_concerns(rid)[1][0]
        self.assertEqual(reopened.status, "open")
        self.assertIsNone(reopened.resolved_at)
        self.assertIsNone(reopened.resolution_notes)

    def test_invalid_status_raises(self):
        with self.assertRaises(ValueError):
            self.p.set_concern_status(1, "bogus_state")

    def test_nonexistent_concern_returns_false(self):
        self.assertFalse(self.p.set_concern_status(9999, "resolved"))


class Stats(_BaseWithTempDb):
    def test_stats_aggregates_tokens_and_concern_buckets(self):
        from core.self_dev import Concern
        self.p.store_review(
            _make_fake_result(
                concerns=[
                    Concern(file="a", line=1, severity="blocker", text="b"),
                    Concern(file="a", line=2, severity="major", text="m"),
                ],
            ),
            caller="test",
        )
        self.p.store_review(
            _make_fake_result(
                concerns=[
                    Concern(file="b", line=1, severity="nit", text="n"),
                ],
            ),
            caller="test",
        )
        s = self.p.stats()
        self.assertEqual(s["total_reviews"], 2)
        self.assertEqual(s["total_input_tokens"], 200)
        self.assertEqual(s["total_output_tokens"], 400)
        buckets = s["concerns_by_severity_and_status"]
        self.assertEqual(buckets["blocker"]["open"], 1)
        self.assertEqual(buckets["major"]["open"], 1)
        self.assertEqual(buckets["nit"]["open"], 1)


class ReviewIntegratesPersistence(_BaseWithTempDb):
    """review() with persist=True should write a row via our temp DB."""

    def test_review_persists_when_persist_true(self):
        from core import self_dev
        from core.claude_tier import TierReply

        fake_reply = json.dumps({
            "overall": "looks ok",
            "concerns": [
                {"file": "x.py", "line": 1, "severity": "minor",
                 "text": "hmm", "suggestion": "think about it"},
            ],
        })
        fake = TierReply(reply=fake_reply, model_used="sonnet",
                          input_tokens=10, output_tokens=20, raw={})

        with mock.patch.object(self_dev, "_git_diff",
                                return_value="diff\n+x\n"), \
             mock.patch("core.self_dev.claude_tier.call", return_value=fake):
            r = self_dev.review(target_ref="HEAD", persist=True)

        # Re-read from the store. The persistence module uses lazy
        # re-import inside review(), so we've already reloaded it in setUp.
        rows = self.p.list_reviews()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].target_ref, "HEAD")
        self.assertEqual(rows[0].output_tokens, 20)
        loaded = self.p.get_review_with_concerns(rows[0].id)
        self.assertEqual(len(loaded[1]), 1)
        self.assertEqual(loaded[1][0].text, "hmm")
        # sanity: the returned in-memory object matches what's stored
        self.assertEqual(r.concerns[0].text, "hmm")

    def test_persist_false_does_not_write(self):
        from core import self_dev
        from core.claude_tier import TierReply
        fake = TierReply(
            reply='{"overall":"x","concerns":[]}',
            model_used="sonnet", input_tokens=1, output_tokens=1, raw={},
        )
        with mock.patch.object(self_dev, "_git_diff",
                                return_value="diff\n+x\n"), \
             mock.patch("core.self_dev.claude_tier.call", return_value=fake):
            self_dev.review(target_ref="HEAD", persist=False)
        self.assertEqual(self.p.list_reviews(), [])


if __name__ == "__main__":
    unittest.main()
