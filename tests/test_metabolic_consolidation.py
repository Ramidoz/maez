import unittest
from datetime import datetime, timezone
from unittest import mock


class _FakeRawCollection:
    def __init__(self, rows):
        self._rows = list(rows)

    def count(self):
        return len(self._rows)

    def get(self, *, limit=None, offset=None, ids=None, include=None):
        if ids is not None:
            wanted = set(ids)
            rows = [row for row in self._rows if row["id"] in wanted]
        else:
            rows = list(self._rows)
            if offset:
                rows = rows[offset:]
            if limit is not None:
                rows = rows[:limit]
        return {
            "ids": [row["id"] for row in rows],
            "documents": [row["document"] for row in rows],
            "metadatas": [row["metadata"] for row in rows],
        }


class _FakeDailyCollection:
    def __init__(self):
        self.add_calls = []

    def add(self, *, ids, documents, metadatas):
        self.add_calls.append(
            {"ids": ids, "documents": documents, "metadatas": metadatas}
        )


def _row(row_id, content, **metadata):
    return {
        "id": row_id,
        "document": content,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle": 1,
            "type": "reasoning",
            **metadata,
        },
    }


def _manager_with_rows(rows):
    from memory.memory_manager import MemoryManager

    manager = MemoryManager.__new__(MemoryManager)
    manager.raw = _FakeRawCollection(rows)
    manager.daily = _FakeDailyCollection()
    manager._get_last_consolidation = lambda: datetime(
        2026, 1, 1, tzinfo=timezone.utc
    )
    manager._save_last_consolidation = lambda: None
    return manager


class QuietDayStubTests(unittest.TestCase):
    def test_quiet_day_produces_deterministic_stub_no_llm(self):
        from memory.memory_manager import build_quiet_day_stub

        stub = build_quiet_day_stub(
            cycles=2847,
            alerts=0,
            owner_interactions=0,
            uptime_h=23.8,
            date_label="2026-07-02",
        )
        self.assertIn("Quiet day", stub["text"])
        self.assertIn("2,847 cycles", stub["text"])
        self.assertEqual(stub["metadata"]["type"], "quiet_day_stub")
        self.assertNotEqual(stub["metadata"]["type"], "daily_consolidation")

    def test_consolidation_selects_on_reason_field_not_tier(self):
        from memory.memory_manager import _select_metabolic_consolidation_rows

        rows = [
            {
                "id": "a",
                "metadata": {
                    "metabolic_durable_reason": "owner_interaction",
                    "trust_tier": "self_observed",
                },
            },
            {"id": "b", "metadata": {"trust_tier": "self_observed"}},
            {
                "id": "c",
                "metadata": {
                    "metabolic_durable_reason": "alert",
                    "trust_tier": "lived",
                },
            },
        ]
        picked = _select_metabolic_consolidation_rows(rows)
        self.assertEqual([row["id"] for row in picked], ["a", "c"])

    def test_flag_on_quiet_day_writes_stub_without_llm(self):
        import memory.memory_manager as mm_mod

        manager = _manager_with_rows(
            [
                _row("quiet-1", "ordinary cycle"),
                _row("quiet-2", "another ordinary cycle"),
            ]
        )

        def _raise_if_called(*, memory_texts, soul, logger_):
            raise AssertionError("quiet day must not call the LLM consolidator")

        with (
            mock.patch.dict("os.environ", {"MAEZ_METABOLIC_MEMORY": "1"}),
            mock.patch.object(mm_mod, "_consolidate_with_chunking", _raise_if_called),
        ):
            summary = manager.consolidate_daily()

        self.assertIn("Quiet day", summary)
        self.assertEqual(len(manager.daily.add_calls), 1)
        call = manager.daily.add_calls[0]
        self.assertEqual(call["documents"], [summary])
        meta = call["metadatas"][0]
        self.assertEqual(meta["type"], "quiet_day_stub")
        self.assertEqual(meta["provenance_source"], "introspection")
        self.assertEqual(meta["trust_tier"], "self_observed")

    def test_flag_off_quiet_rows_still_use_existing_llm_path(self):
        import memory.memory_manager as mm_mod

        manager = _manager_with_rows([_row("quiet-1", "ordinary cycle")])

        def _summary(*, memory_texts, soul, logger_):
            return "LLM SUMMARY"

        with (
            mock.patch.dict("os.environ", {"MAEZ_METABOLIC_MEMORY": "0"}),
            mock.patch.object(mm_mod, "_consolidate_with_chunking", _summary),
        ):
            summary = manager.consolidate_daily()

        self.assertEqual(summary, "LLM SUMMARY")
        self.assertEqual(manager.daily.add_calls[-1]["documents"], ["LLM SUMMARY"])
        self.assertEqual(
            manager.daily.add_calls[-1]["metadatas"][0]["type"],
            "daily_consolidation",
        )
