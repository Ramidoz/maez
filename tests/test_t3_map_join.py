# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The census→map join is exact (gate round 21, item A).

A map without a covers relation lets a deleted row silently shrink the
witness. This joins the DERIVED census to the map mechanically: every
memory_phase writer is either mapped to a T3 row, a ruled selftest site, or
this suite fails naming it.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CENSUS = json.loads(
    (REPO / "docs/superpowers/witness/theme2-s1-census.json").read_text())
MAP = json.loads(
    (REPO / "docs/superpowers/witness/theme2-s1-t3-map.json").read_text())


class CensusMapJoin(unittest.TestCase):

    def test_every_writer_is_mapped_or_ruled(self):
        covers = MAP["census_join"]["writers"]
        unmapped = []
        for w in CENSUS["memory_phase_writers"]:
            if w in covers:
                continue
            if "::@" in w:          # module-level selftest sites, ruled IN
                continue
            if "s1_census" in w:
                continue
            unmapped.append(w)
        self.assertEqual(unmapped, [],
                         "censused writers with no T3 map row:\n  "
                         + "\n  ".join(unmapped))

    def test_every_join_target_is_a_real_map_row(self):
        rows = ({e["consumer"] for e in MAP["stampers"]}
                | {r["consumer"] for r in MAP["readers_and_exemptions"]})
        dangling = [f"{w} -> {t}" for w, t
                    in MAP["census_join"]["writers"].items()
                    if t not in rows]
        self.assertEqual(dangling, [], "join names nonexistent rows")

    def test_every_join_key_is_a_real_census_construct(self):
        writers = set(CENSUS["memory_phase_writers"])
        stale = [w for w in MAP["census_join"]["writers"] if w not in writers]
        self.assertEqual(stale, [],
                         "join carries constructs the census no longer "
                         "finds — re-derive both:\n  " + "\n  ".join(stale))

    def test_every_censused_reader_is_mapped_or_ruled(self):
        covers = MAP["census_join"]["readers"]
        rows = ({e["consumer"] for e in MAP["stampers"]}
                | {r["consumer"] for r in MAP["readers_and_exemptions"]})
        problems = []
        for r in CENSUS["birth_meta_readers"]:
            target = covers.get(r)
            if target is None:
                problems.append(f"censused reader with no join: {r}")
            elif target not in rows and not target.startswith(("SELF", "OWNER-ONLY")):
                problems.append(f"join names a nonexistent row: {r} -> "
                                f"{target}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_reader_join_keys_are_current_census_constructs(self):
        readers = set(CENSUS["birth_meta_readers"])
        stale = [k for k in MAP["census_join"]["readers"] if k not in readers]
        self.assertEqual(stale, [],
                         "reader join carries constructs the census no "
                         "longer finds:\n  " + "\n  ".join(stale))

    # Gate round 23: deleting a reader row silently shrank the witness —
    # the join validated only the rows that REMAINED. The authoritative
    # membership is frozen here as exact sets; changing membership is a
    # deliberate two-file edit that this test forces into the open.
    EXPECTED_READERS = ['audit_log._initialize', 'eval.longmemeval.ingest_haystack', 'lean_idle_heartbeat.select_private_reader_thoughts', 'maez_daemon._birth_readiness (_birth_phase, _flag_state)', 's7_consultation_exemption.born_by_any_signal', 'source_awareness._should_skip_dir']
    EXPECTED_STAMPERS = ['audit_log.end_direct_edit_session', 'audit_log.log_direct_edit', 'audit_log.record', 'audit_log.start_direct_edit_session', 'ledger_writer.write_turn', 'memory_manager.store', 'memory_manager.store_core', 'memory_manager.store_telegram', 'private_thoughts._insert_thought (direct sink)', 'private_thoughts._insert_thought_on_connection (direct sink)', 'private_thoughts.insert_signal_in_transaction', 'private_thoughts.record_signal', 'private_thoughts.record_thought', 'span_planner.run_consolidation_pass']

    def test_map_membership_is_exact(self):
        self.assertEqual(
            sorted(r["consumer"] for r in MAP["readers_and_exemptions"]),
            self.EXPECTED_READERS,
            "reader/exemption membership changed — if deliberate, update "
            "BOTH the map and this frozen set")
        self.assertEqual(
            sorted(e["consumer"] for e in MAP["stampers"]),
            self.EXPECTED_STAMPERS,
            "stamper membership changed — same rule")

    def test_reader_rows_carry_entry_and_dormant(self):
        for row in MAP["readers_and_exemptions"]:
            self.assertTrue(row.get("entry"), row["consumer"])
            self.assertTrue(row.get("dormant"), row["consumer"])


if __name__ == "__main__":
    unittest.main()
