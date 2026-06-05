# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Generic body-row lookup for Intake Bus idempotency."""

from __future__ import annotations

import unittest
from unittest import mock

from memory.memory_manager import MemoryManager


def _mm_with_raw(raw):
    mm = MemoryManager.__new__(MemoryManager)
    mm.raw = raw
    return mm


class BodyRowLookupTests(unittest.TestCase):
    def test_honors_the_passed_origin_class(self):
        raw = mock.Mock()
        raw.get.return_value = {
            "ids": ["row-A", "row-B"],
            "metadatas": [
                {"egress_origin_class": "owner_account_context"},
                {"egress_origin_class": "memory"},
            ],
        }
        memory = _mm_with_raw(raw)

        self.assertEqual(
            memory.body_row_id_by_source_ref("ref", egress_origin_class="memory"),
            "row-B",
        )
        self.assertEqual(
            memory.body_row_id_by_source_ref(
                "ref", egress_origin_class="owner_account_context"
            ),
            "row-A",
        )

    def test_absent_returns_none(self):
        raw = mock.Mock()
        raw.get.return_value = {"ids": [], "metadatas": []}
        memory = _mm_with_raw(raw)

        self.assertIsNone(
            memory.body_row_id_by_source_ref("ref", egress_origin_class="memory")
        )

    def test_empty_source_ref_returns_none_without_querying(self):
        raw = mock.Mock()
        memory = _mm_with_raw(raw)

        self.assertIsNone(
            memory.body_row_id_by_source_ref("", egress_origin_class="memory")
        )
        raw.get.assert_not_called()

    def test_backend_error_raises_not_launders_to_absent(self):
        raw = mock.Mock()
        raw.get.side_effect = RuntimeError("chroma down")
        memory = _mm_with_raw(raw)

        with self.assertRaises(RuntimeError):
            memory.body_row_id_by_source_ref("ref", egress_origin_class="memory")

    def test_owner_account_wrapper_still_resolves_owner_rows(self):
        raw = mock.Mock()
        raw.get.return_value = {
            "ids": ["row-A"],
            "metadatas": [{"egress_origin_class": "owner_account_context"}],
        }
        memory = _mm_with_raw(raw)

        self.assertEqual(memory.owner_account_row_id_by_source_ref("ref"), "row-A")


if __name__ == "__main__":
    unittest.main()
