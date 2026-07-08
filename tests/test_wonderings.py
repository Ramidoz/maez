# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for the exploratory-mind primitives.

Covers:
  - extract_shell_commands + is_read_only gates
  - Wonderings round-trip (add / pick / record / resolve / block)
  - validate_learning evidence rules
"""
from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from core.tool_loop import (
    extract_shell_commands, is_read_only, safety_check,
)
from core.wonderings import (
    Wonderings, validate_learning,
    LEARNING_NO_OUTPUT, LEARNING_SYNTH_BLOCKED, LEARNING_SYNTH_TIMEOUT,
    DEFERRAL_BLOCK_THRESHOLD,
)


class ToolLoopGates(unittest.TestCase):
    def test_extract_single_bash_block(self):
        txt = "run this:\n```bash\nps aux\n```\n"
        self.assertEqual(extract_shell_commands(txt), ["ps aux"])

    def test_extract_dedup(self):
        txt = "```bash\nls\n```\nagain:\n```sh\nls\n```"
        self.assertEqual(extract_shell_commands(txt), ["ls"])

    def test_read_only_accepts_basic(self):
        self.assertTrue(is_read_only("ps aux"))
        self.assertTrue(is_read_only("ls -la /tmp"))
        self.assertTrue(is_read_only("systemctl is-active maez"))
        self.assertTrue(is_read_only("ps aux | head -5"))
        self.assertTrue(is_read_only("grep foo /var/log/syslog | wc -l"))

    def test_read_only_rejects_mutating(self):
        self.assertFalse(is_read_only("sudo ls"))
        self.assertFalse(is_read_only("echo hi > /tmp/x"))
        self.assertFalse(is_read_only("cat $(which bash)"))
        self.assertFalse(is_read_only("echo `date`"))
        self.assertFalse(is_read_only("ls | bash"))
        self.assertFalse(is_read_only("sed -i 's/a/b/' foo.txt"))
        self.assertFalse(is_read_only("ps aux | grep foo | xargs kill"))

    def test_safety_blocks_rm_rf_system(self):
        self.assertIsNotNone(safety_check("rm -rf /etc/something"))
        self.assertIsNotNone(safety_check("rm -rf /"))
        self.assertIsNotNone(safety_check("rm -rf /home"))

    def test_safety_allows_tmp_rm(self):
        self.assertIsNone(safety_check("rm -rf /tmp/build-scratch"))
        self.assertIsNone(safety_check("rm -rf ./scratch"))

    def test_safety_blocks_continuous_commands(self):
        blocked = [
            "nvidia-smi --query-gpu=temperature.gpu --format=csv -l 1",
            "nvidia-smi -l1",
            "nvidia-smi --loop=1",
            "nvidia-smi -lms 500",
            "tail -f logs/maez.log",
            "tail -F logs/maez.log",
            "journalctl --follow -u maez",
            "journalctl -fu maez",
            "watch systemctl status maez",
            "ps aux && watch nvidia-smi",
        ]
        for cmd in blocked:
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(safety_check(cmd))

    def test_safety_allows_finite_nvidia_smi_probe(self):
        self.assertIsNone(safety_check(
            "nvidia-smi --query-gpu=temperature.gpu,memory.used "
            "--format=csv,noheader"
        ))


class LearningValidation(unittest.TestCase):
    def test_empty_output_accepts_sentinel(self):
        self.assertTrue(validate_learning(LEARNING_NO_OUTPUT, "", "", 0))

    def test_empty_output_rejects_invention(self):
        self.assertFalse(validate_learning("the system is fine", "", "", 0))

    def test_token_overlap_accepts(self):
        self.assertTrue(validate_learning(
            "systemd service running as active",
            "systemd[1]: service active running", "", 0,
        ))

    def test_token_overlap_rejects_invention(self):
        self.assertFalse(validate_learning(
            "disk is at fifteen percent usage",
            "RGB zones detected on device", "", 0,
        ))

    def test_fabrication_verbs_rejected(self):
        self.assertFalse(validate_learning(
            "I've noted systemd is active",
            "systemd active running", "", 0,
        ))
        self.assertFalse(validate_learning(
            "manifest has been updated with systemd status",
            "systemd active running", "", 0,
        ))

    def test_stderr_counts_as_evidence(self):
        self.assertTrue(validate_learning(
            "permission denied on maez log",
            "", "permission denied: maez.log", 1,
        ))


class WonderingsRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.store = Wonderings(db_path=Path(self.tmp.name))

    def tearDown(self):
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_add_and_pick(self):
        wid = self.store.add("does the thing work?", source="test")
        self.assertGreater(wid, 0)
        picked = self.store.pick_next()
        self.assertEqual(picked["id"], wid)
        self.assertEqual(picked["status"], "open")

    def test_add_with_citations_rolls_back_when_sidecar_insert_fails(self):
        real_conn = self.store._conn

        class SidecarFailingConnection:
            def __init__(self, inner):
                self._inner = inner

            def execute(self, sql, *args, **kwargs):
                if "INSERT INTO wondering_citations" in " ".join(sql.split()):
                    raise RuntimeError("forced sidecar insert failure")
                return self._inner.execute(sql, *args, **kwargs)

            def __getattr__(self, name):
                return getattr(self._inner, name)

        @contextmanager
        def failing_conn():
            with real_conn() as c:
                yield SidecarFailingConnection(c)

        self.store._conn = failing_conn
        try:
            with self.assertRaisesRegex(RuntimeError, "forced sidecar"):
                self.store.add_with_citations(
                    "what did the day leave unresolved?",
                    source="digestion",
                    row_citations=[
                        {"turn_id": "turn-1", "chain_position": 1},
                    ],
                    taint_labels=["self_generated"],
                    receipt_id="receipt-1",
                    bond_id="bond-a",
                )
        finally:
            self.store._conn = real_conn

        self.assertEqual(self.store.list_all(), [])
        with real_conn() as c:
            count = c.execute(
                "SELECT COUNT(*) FROM wondering_citations"
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_add_with_citations_round_trips_sidecar_exactly(self):
        row_citations = [
            {"turn_id": "turn-1", "chain_position": 7},
            {"turn_id": "turn-2", "chain_position": 8},
        ]
        taint_labels = ["self_generated", "tool_output"]

        wid = self.store.add_with_citations(
            "what pattern should Maez keep sitting with?",
            source="digestion",
            row_citations=row_citations,
            taint_labels=taint_labels,
            receipt_id="receipt-42",
            bond_id="bond-a",
        )

        got = self.store.get(wid)
        self.assertEqual(got["source"], "digestion")
        self.assertEqual(got["bond_id"], "bond-a")
        citations = self.store.citations_for(wid)
        self.assertEqual(citations["wondering_id"], wid)
        self.assertEqual(citations["row_citations"], row_citations)
        self.assertEqual(citations["taint_labels"], taint_labels)
        self.assertEqual(citations["receipt_id"], "receipt-42")

    def test_digestion_wondering_without_sidecar_is_invalid(self):
        wid = self.store.add("uncited digestion question", source="digestion")

        with self.assertRaises(ValueError) as caught:
            self.store.assert_citation_integrity()

        self.assertEqual(getattr(caught.exception, "wondering_ids", None), [wid])

    def test_existing_add_callers_do_not_need_sidecar(self):
        wid = self.store.add("manual question", source="manual")

        self.assertIsNone(self.store.citations_for(wid))
        self.store.assert_citation_integrity()
        self.assertEqual(self.store.get(wid)["question"], "manual question")

    def test_add_with_citations_rejects_unknown_taint_label(self):
        with self.assertRaisesRegex(ValueError, "unknown taint labels"):
            self.store.add_with_citations(
                "bad taint",
                source="digestion",
                row_citations=[{"turn_id": "turn-1"}],
                taint_labels=["not_from_s1"],
                receipt_id="receipt-bad",
            )

    def test_add_with_citations_rejects_capped_citation_summaries(self):
        capped_payloads = [
            ["turn-1", ",+3"],
            ["turn-1,turn-2,+3"],
            [{"turn_id": "turn-1", "summary": "+3 more"}],
        ]
        for row_citations in capped_payloads:
            with self.subTest(row_citations=row_citations):
                with self.assertRaisesRegex(ValueError, "complete"):
                    self.store.add_with_citations(
                        "capped citations",
                        source="digestion",
                        row_citations=row_citations,
                        taint_labels=["self_generated"],
                        receipt_id="receipt-capped",
                    )

    def test_add_with_citations_requires_non_empty_row_citation_list(self):
        invalid_payloads = [None, [], {}, "turn-1"]
        for row_citations in invalid_payloads:
            with self.subTest(row_citations=row_citations):
                with self.assertRaisesRegex(ValueError, "non-empty list"):
                    self.store.add_with_citations(
                        "bad citations",
                        source="digestion",
                        row_citations=row_citations,
                        taint_labels=["self_generated"],
                        receipt_id="receipt-empty",
                    )

    def test_add_with_citations_requires_each_citation_to_name_turn_id(self):
        invalid_payloads = [
            [""],
            [{}],
            [{"chain_position": 1}],
            [{"turn_id": ""}],
        ]
        for row_citations in invalid_payloads:
            with self.subTest(row_citations=row_citations):
                with self.assertRaisesRegex(ValueError, "turn_id"):
                    self.store.add_with_citations(
                        "unnamed citations",
                        source="digestion",
                        row_citations=row_citations,
                        taint_labels=["self_generated"],
                        receipt_id="receipt-unnamed",
                    )

    def test_record_probe_flips_open_to_active(self):
        wid = self.store.add("q", source="test")
        self.store.record_probe(
            wid, cmd="ps aux", stdout="USER PID", stderr="", rc=0,
            learning="ps showed processes", evidence_tied=True,
        )
        got = self.store.get(wid)
        self.assertEqual(got["status"], "active")
        self.assertEqual(got["advance_count"], 1)
        self.assertEqual(got["deferral_count"], 0)

    def test_deferrals_trigger_block(self):
        wid = self.store.add("q", source="test")
        for _ in range(DEFERRAL_BLOCK_THRESHOLD):
            self.store.record_probe(
                wid, cmd="sudo x", stdout="", stderr="",
                rc=0, learning=LEARNING_SYNTH_BLOCKED,
                evidence_tied=False, deferred=True,
            )
        self.assertTrue(self.store.should_block(wid))
        self.store.mark_blocked(wid, pending_card_id=42)
        got = self.store.get(wid)
        self.assertEqual(got["status"], "blocked_pending_approval")
        self.assertEqual(got["pending_card_id"], 42)
        # pick_next must skip blocked
        self.assertIsNone(self.store.pick_next())

    def test_unblock_from_card_resumes_active(self):
        wid = self.store.add("q", source="test")
        for _ in range(DEFERRAL_BLOCK_THRESHOLD):
            self.store.record_probe(
                wid, cmd="sudo x", stdout="", stderr="",
                rc=0, learning=LEARNING_SYNTH_BLOCKED,
                evidence_tied=False, deferred=True,
            )
        self.store.mark_blocked(wid, pending_card_id=7)
        self.store.unblock_from_card(
            wid, stdout="real output here", stderr="", rc=0,
            learning="real output here shows it", evidence_tied=True,
        )
        got = self.store.get(wid)
        self.assertEqual(got["status"], "active")
        self.assertEqual(got["deferral_count"], 0)
        self.assertIsNone(got["pending_card_id"])
        # The most recent probe is no longer deferred
        probes = self.store.recent_probes(wid, limit=5)
        self.assertEqual(probes[0]["deferred"], 0)
        self.assertEqual(probes[0]["evidence_tied"], 1)

    def test_synth_sentinels_are_distinct(self):
        self.assertNotEqual(LEARNING_SYNTH_TIMEOUT, LEARNING_SYNTH_BLOCKED)
        self.assertNotEqual(LEARNING_SYNTH_TIMEOUT, LEARNING_NO_OUTPUT)
        # Neither status marker should be accepted as a real learning,
        # even if evidence is present. Validation treats them as text
        # with no token overlap against concrete evidence.
        self.assertFalse(validate_learning(
            LEARNING_SYNTH_TIMEOUT, "real stdout tokens", "", 0,
        ))
        self.assertFalse(validate_learning(
            LEARNING_SYNTH_BLOCKED, "real stdout tokens", "", 0,
        ))

    def test_stats_buckets_mixed_rows(self):
        wid = self.store.add("q", source="test")
        # One real tied advance
        self.store.record_probe(
            wid, cmd="ps aux", stdout="USER PID bash", stderr="", rc=0,
            learning="ps showed bash and user",
            evidence_tied=True, deferred=False,
        )
        # One real invalidated advance (synth ran, validation failed)
        self.store.record_probe(
            wid, cmd="ls /tmp", stdout="file.txt", stderr="", rc=0,
            learning=LEARNING_SYNTH_BLOCKED,
            evidence_tied=False, deferred=False,
        )
        # One timeout (synth never ran this cycle)
        self.store.record_probe(
            wid, cmd="du -sh /", stdout="1G /", stderr="", rc=0,
            learning=LEARNING_SYNTH_TIMEOUT,
            evidence_tied=False, deferred=False,
        )
        # One deferred placeholder (safety or card queued — not drift)
        self.store.record_probe(
            wid, cmd="sudo foo", stdout="", stderr="", rc=0,
            learning=LEARNING_SYNTH_BLOCKED,
            evidence_tied=False, deferred=True,
        )
        # One no-output real probe
        self.store.record_probe(
            wid, cmd="true", stdout="", stderr="", rc=0,
            learning=LEARNING_NO_OUTPUT,
            evidence_tied=True, deferred=False,
        )
        s = self.store.stats(window_seconds=3600)
        self.assertEqual(s["probes"], 5)
        self.assertEqual(s["tied"], 2)            # ps + true
        self.assertEqual(s["invalidated"], 1)     # ls only — NOT the deferred one
        self.assertEqual(s["timeout"], 1)         # du
        self.assertEqual(s["deferred"], 1)        # sudo
        self.assertEqual(s["no_output"], 1)       # true

    def test_resolve_and_abandon_remove_from_pick(self):
        w1 = self.store.add("resolved q", source="test")
        w2 = self.store.add("abandoned q", source="test")
        self.store.resolve(w1, "answered")
        self.store.abandon(w2, "no way")
        self.assertIsNone(self.store.pick_next())
        self.assertEqual(self.store.get(w1)["status"], "resolved")
        self.assertEqual(self.store.get(w2)["status"], "abandoned")


if __name__ == "__main__":
    unittest.main()
