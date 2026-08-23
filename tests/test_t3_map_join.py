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

    # Gate round 24: labels were frozen but EDGES were not — swapping
    # store/store_core targets, or inventing "SELF-FORGED", passed because
    # the join proved only that some target existed. The full edge relations
    # are digest-frozen; changing an edge is a deliberate two-file edit.
    EDGE_DIGEST_WRITERS = "99e8432ea70f7fbf6945ea7622f5f31665458d378b9c35f8a55aa04ab7f0495b"
    EDGE_DIGEST_READERS = "7837b81740bb1c410d142ea4c81612a963db88b7953f0c290114aa3f67768e6d"
    ALLOWED_NON_ROW_TARGETS = (
        "SELF (the resolver)",
        "OWNER-ONLY (the birth transaction itself; never driven by a "
        "witness)",
    )

    def test_edge_relations_are_digest_frozen(self):
        import hashlib as h, json as j
        w = j.dumps(MAP["census_join"]["writers"], sort_keys=True)
        r = j.dumps(MAP["census_join"]["readers"], sort_keys=True)
        self.assertEqual(h.sha256(w.encode()).hexdigest(),
                         self.EDGE_DIGEST_WRITERS,
                         "a writer EDGE changed — if deliberate, re-freeze "
                         "both digests here")
        self.assertEqual(h.sha256(r.encode()).hexdigest(),
                         self.EDGE_DIGEST_READERS,
                         "a reader EDGE changed — same rule")

    def test_non_row_targets_are_a_closed_vocabulary(self):
        rows = ({e["consumer"] for e in MAP["stampers"]}
                | {x["consumer"] for x in MAP["readers_and_exemptions"]})
        for w, t in MAP["census_join"]["readers"].items():
            if t in rows:
                continue
            self.assertTrue(
                t in self.ALLOWED_NON_ROW_TARGETS
                or t.startswith("SELF-WITNESS-TOOLING"),
                f"open-ended exemption target: {w} -> {t}")

    def test_reader_rows_carry_entry_and_dormant(self):
        for row in MAP["readers_and_exemptions"]:
            self.assertTrue(row.get("entry"), row["consumer"])
            self.assertTrue(row.get("dormant"), row["consumer"])


if __name__ == "__main__":
    unittest.main()
