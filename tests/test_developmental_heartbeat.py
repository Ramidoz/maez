# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Track A developmental heartbeat tests."""

from __future__ import annotations

import inspect
import unittest

from core.brain.developmental_heartbeat import (
    HeartbeatEvidence,
    already_recorded,
    build_prompt,
    fallback_heartbeat,
    format_core_memory,
    normalize_heartbeat,
    record_if_absent,
    source_for_date,
)


def _evidence() -> HeartbeatEvidence:
    return HeartbeatEvidence(
        date="2026-04-24",
        day_name="Friday",
        cycle_count=42,
        error_count=1,
        warning_count=2,
        action_count=3,
        alert_count=4,
        raw_count=100,
        daily_count=5,
        core_count=12,
        owner_name="Rohit",
        journal_summary="I verified continuity and cleaned autonomous surfaces.",
    )


class FakeMemory:
    def __init__(self):
        self.core = []

    def get_all_core(self):
        return list(self.core)

    def store_core(self, content: str, source: str = "reasoning") -> str:
        self.core.append({"content": content, "source": source})
        return "core-test"


class DevelopmentalHeartbeatModule(unittest.TestCase):
    def test_source_for_date_is_stable(self):
        self.assertEqual(
            source_for_date("2026-04-24"),
            "developmental_heartbeat_2026-04-24",
        )

    def test_prompt_names_required_labels(self):
        prompt = build_prompt(_evidence())
        for label in (
            "What I noticed:",
            "What changed in me:",
            "What I still want:",
            "What I must be careful about:",
            "What I owe next:",
        ):
            self.assertIn(label, prompt)

    def test_normalize_accepts_required_shape(self):
        raw = "\n".join((
            "What I noticed: the day had evidence.",
            "What changed in me: I got more careful.",
            "What I still want: I want continuity.",
            "What I must be careful about: I must not invent.",
            "What I owe next: I owe a grounded answer.",
        ))
        self.assertEqual(normalize_heartbeat(raw, _evidence()), raw)

    def test_normalize_falls_back_on_missing_label(self):
        out = normalize_heartbeat("What I noticed: only one line", _evidence())
        self.assertIn("What changed in me:", out)
        self.assertIn("What I owe next:", out)

    def test_format_core_memory_is_dated_and_evidence_backed(self):
        body = fallback_heartbeat(_evidence())
        formatted = format_core_memory(body, _evidence())
        self.assertIn("[DEVELOPMENTAL HEARTBEAT — 2026-04-24 (Friday)]", formatted)
        self.assertIn("Evidence: cycles=42; actions=3; alerts=4", formatted)

    def test_record_if_absent_is_idempotent_per_date(self):
        memory = FakeMemory()
        body = fallback_heartbeat(_evidence())
        self.assertEqual(record_if_absent(memory, _evidence(), body), "core-test")
        self.assertTrue(already_recorded(memory, "2026-04-24"))
        self.assertIsNone(record_if_absent(memory, _evidence(), body))
        self.assertEqual(len(memory.core), 1)


class DaemonDevelopmentalHeartbeatWiring(unittest.TestCase):
    def test_nightly_journal_is_audited_before_core_store(self):
        from daemon.maez_daemon import MaezDaemon
        src = inspect.getsource(MaezDaemon._write_journal_entry)
        audit_pos = src.find('surface="nightly_journal"')
        store_pos = src.find("self.memory.store_core")
        self.assertGreater(audit_pos, 0, "nightly journal audit not found")
        self.assertGreater(store_pos, 0, "nightly journal core store not found")
        self.assertLess(audit_pos, store_pos,
            "nightly journal must be audited before storing as core memory.",
        )

    def test_developmental_heartbeat_is_written_after_journal_store(self):
        from daemon.maez_daemon import MaezDaemon
        src = inspect.getsource(MaezDaemon._write_journal_entry)
        store_pos = src.find("self.memory.store_core")
        heartbeat_pos = src.find("_write_developmental_heartbeat")
        self.assertGreater(heartbeat_pos, 0, "heartbeat call not found")
        self.assertLess(store_pos, heartbeat_pos,
            "heartbeat should run after the regular journal core store.",
        )

    def test_developmental_heartbeat_method_audits_before_recording(self):
        from daemon.maez_daemon import MaezDaemon
        src = inspect.getsource(MaezDaemon._write_developmental_heartbeat)
        audit_pos = src.find('surface="developmental_heartbeat"')
        record_pos = src.rfind("record_if_absent(")
        self.assertGreater(audit_pos, 0, "heartbeat audit not found")
        self.assertGreater(record_pos, 0, "heartbeat store not found")
        self.assertLess(audit_pos, record_pos,
            "heartbeat must be audited before core-memory storage.",
        )


if __name__ == "__main__":
    unittest.main()
