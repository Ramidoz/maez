"""Phase 2 commit A: the turn-sequence store. Gate-inherited REDs."""

from __future__ import annotations

import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from core.brain import conversation_turn_seq as cts

_ON = {"MAEZ_ACTION_LANE_SHADOW": "1", "MAEZ_ACTION_LANE_ENABLED": ""}
_OFF = {"MAEZ_ACTION_LANE_SHADOW": "", "MAEZ_ACTION_LANE_ENABLED": ""}


class _TempDir:
    def __enter__(self):
        self._td = tempfile.TemporaryDirectory(prefix="turnseq_")
        self._patch = mock.patch.object(
            cts, "_db_path",
            lambda: Path(self._td.name) / "conversation_turn_seq.db",
        )
        self._patch.start()
        return Path(self._td.name)

    def __exit__(self, *a):
        self._patch.stop()
        self._td.cleanup()


class TurnSeqTests(unittest.TestCase):
    def test_same_event_retried_returns_same_seq(self):
        with _TempDir(), mock.patch.dict(os.environ, _ON):
            a = cts.advance_and_get("telegram_surface", "c1", "update:100")
            b = cts.advance_and_get("telegram_surface", "c1", "update:100")
            self.assertEqual(a, 1)
            self.assertEqual(b, 1)  # idempotent: no double count
            self.assertEqual(cts.current_seq("telegram_surface", "c1"), 1)

    def test_distinct_events_get_distinct_serialized_seqs(self):
        with _TempDir(), mock.patch.dict(os.environ, _ON):
            seqs = [
                cts.advance_and_get("telegram_surface", "c1", f"update:{i}")
                for i in range(5)
            ]
            self.assertEqual(seqs, [1, 2, 3, 4, 5])

    def test_conversations_are_independently_scoped(self):
        with _TempDir(), mock.patch.dict(os.environ, _ON):
            self.assertEqual(
                cts.advance_and_get("telegram_surface", "c1", "update:1"), 1
            )
            self.assertEqual(
                cts.advance_and_get("telegram_surface", "c2", "update:1"), 1
            )
            self.assertEqual(
                cts.advance_and_get("web_owner", "c1", "update:1"), 1
            )

    def test_source_tagged_identities_do_not_alias(self):
        with _TempDir(), mock.patch.dict(os.environ, _ON):
            a = cts.advance_and_get("telegram_surface", "c1", "update:7")
            b = cts.advance_and_get("telegram_surface", "c1", "message:7")
            self.assertEqual((a, b), (1, 2))  # different namespaces

    def test_flags_off_leaves_filesystem_untouched(self):
        with _TempDir() as root, mock.patch.dict(os.environ, _OFF):
            out = cts.advance_and_get("telegram_surface", "c1", "update:1")
            self.assertIsNone(out)
            self.assertIsNone(cts.current_seq("telegram_surface", "c1"))
            self.assertEqual(list(root.iterdir()), [])  # NO database

    def test_concurrent_distinct_events_serialize_without_loss(self):
        with _TempDir(), mock.patch.dict(os.environ, _ON):
            results: list[int] = []
            lock = threading.Lock()

            def _hit(i: int) -> None:
                seq = cts.advance_and_get(
                    "telegram_surface", "c1", f"update:{i}"
                )
                with lock:
                    results.append(seq)

            threads = [
                threading.Thread(target=_hit, args=(i,)) for i in range(8)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(sorted(results), [1, 2, 3, 4, 5, 6, 7, 8])

    def test_blank_inputs_yield_none_not_rows(self):
        with _TempDir() as root, mock.patch.dict(os.environ, _ON):
            self.assertIsNone(cts.advance_and_get("", "c1", "update:1"))
            self.assertIsNone(cts.advance_and_get("t", "", "update:1"))
            self.assertIsNone(cts.advance_and_get("t", "c1", ""))
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
