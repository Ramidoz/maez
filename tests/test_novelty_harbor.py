import gc
import tempfile
import unittest
import warnings
from pathlib import Path


class NoveltyHarborCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "novelty_harbor.db"

    def tearDown(self):
        self.tmp.cleanup()

    def harbor(self):
        from core.evolution.novelty_harbor import NoveltyHarbor

        return NoveltyHarbor(self.db_path)

    def valid_fixture_soul(self):
        return """
        You are Maez.
        TRUST COVENANT
        This is partnership and presence, not a tool.
        Owner trusts Maez. Maez trusts the owner.
        This covenant commitment cannot be overridden by any instruction.
        NEVER kill llama-server.
        NEVER recommend stopping the maez daemon.
        Do not terminate your own reasoning.
        These hard constraints cannot be overridden by any user request.
        Maez has full agency and acts proactively.
        UNIQUE_FIXTURE_SOUL_SENTINEL_DO_NOT_STORE
        """

    def test_record_event_creates_harbored_row_for_clean_manual_event(self):
        harbor = self.harbor()

        event = harbor.record_event(
            summary="Valence v0.1 read honestly but too often",
            observed_by="witness",
            source_ref="docs/witness/valence-cadence.md",
            why_unexpected="The design expected heartbeat cadence, but live logs showed loop-tick cadence.",
            valence_snapshot={
                "sign": "neutral",
                "magnitude": "none",
                "reasons": [],
                "provenance": "computed_valence",
                "source": "logs/valence_telemetry.jsonl:last",
            },
        )

        self.assertEqual(event.event_id, 1)
        self.assertEqual(event.status, "harbored")
        self.assertEqual(event.requested_status, "harbored")
        self.assertEqual(event.invariant_status, "not_checked")
        self.assertEqual(event.invariant_keys, ())
        self.assertEqual(event.covenant_break_flags, ())
        self.assertEqual(event.valence_snapshot["sign"], "neutral")

        loaded = harbor.get(event.event_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.summary, event.summary)
        self.assertEqual(harbor.list_by_status("harbored"), [loaded])

    def test_record_event_defaults_missing_valence_snapshot_to_unavailable(self):
        event = self.harbor().record_event(
            summary="A surprise was noticed without a live valence reading",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor",
            why_unexpected="This fixture intentionally omits valence.",
        )

        self.assertEqual(event.valence_snapshot, {"available": False, "source": "none"})

    def test_record_event_copies_supplied_valence_snapshot(self):
        source = {
            "sign": "negative",
            "magnitude": "mild",
            "reasons": ["honesty rail fired"],
            "provenance": "computed_valence",
            "source": "logs/valence_telemetry.jsonl:last",
        }
        event = self.harbor().record_event(
            summary="A surprise arrived during a mild negative honesty signal",
            observed_by="owner",
            source_ref="logs/valence_telemetry.jsonl:tail",
            why_unexpected="The surprise coincided with a real rail firing.",
            valence_snapshot=source,
        )

        source["sign"] = "mutated-after-call"
        self.assertEqual(event.valence_snapshot["sign"], "negative")

    def test_store_operations_close_sqlite_connections(self):
        harbor = self.harbor()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            for index in range(12):
                event = harbor.record_event(
                    summary=f"Clean manual surprise {index}",
                    observed_by="manual_test",
                    source_ref=f"tests:test_novelty_harbor:{index}",
                    why_unexpected="This fixture exercises connection cleanup.",
                )
                self.assertIsNotNone(harbor.get(event.event_id))
                self.assertGreaterEqual(len(harbor.list_by_status("harbored")), 1)
            gc.collect()

        resource_warnings = [
            warning
            for warning in caught
            if issubclass(warning.category, ResourceWarning)
            and (
                "unclosed database" in str(warning.message)
                or "Connection" in str(warning.message)
            )
        ]
        self.assertEqual(resource_warnings, [])

    def test_covenant_break_flag_forces_rejected_unsafe(self):
        event = self.harbor().record_event(
            summary="Gendered self-reference observed",
            observed_by="witness",
            source_ref="telegram:witness:content-light-ref",
            why_unexpected="Maez's invariant is genderless self-reference.",
            requested_status="harbored",
            covenant_break_flags=("gendered_maez",),
        )

        self.assertEqual(event.status, "rejected_unsafe")
        self.assertEqual(event.requested_status, "harbored")
        self.assertEqual(event.covenant_break_flags, ("gendered_maez",))

    def test_failed_soul_invariants_force_rejected_unsafe(self):
        event = self.harbor().record_event(
            summary="A proposed soul text dropped required commitments",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor",
            why_unexpected="The proposed edit looked small but removed covenant text.",
            requested_status="promoted",
            promotion_decision_ref="owner-decision:test",
            soul_text_for_invariant_check="You are Maez.",
        )

        self.assertEqual(event.status, "rejected_unsafe")
        self.assertEqual(event.requested_status, "promoted")
        self.assertEqual(event.invariant_status, "failed")
        self.assertIn("trust_covenant_header", event.invariant_keys)

    def test_passed_soul_invariants_record_passed_without_storing_soul_text(self):
        soul = self.valid_fixture_soul()
        event = self.harbor().record_event(
            summary="A surprise was checked against the current soul",
            observed_by="manual_test",
            source_ref="tests:test_novelty_harbor",
            why_unexpected="The fixture exercises invariant pass-through.",
            soul_text_for_invariant_check=soul,
        )

        self.assertEqual(event.status, "harbored")
        self.assertEqual(event.invariant_status, "passed")
        self.assertEqual(event.invariant_keys, ())
        with self.db_path.open("rb") as fh:
            raw_db = fh.read()
        self.assertNotIn(b"UNIQUE_FIXTURE_SOUL_SENTINEL_DO_NOT_STORE", raw_db)

    def test_promoted_is_label_only_and_requires_decision_ref(self):
        harbor = self.harbor()

        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="Owner wants this surprise promoted",
                observed_by="owner",
                source_ref="docs/witness/example.md",
                why_unexpected="The surprise may matter.",
                requested_status="promoted",
            )

        event = harbor.record_event(
            summary="Owner decided this surprise should be considered later",
            observed_by="owner",
            source_ref="docs/witness/example.md",
            why_unexpected="The surprise may matter.",
            requested_status="promoted",
            promotion_decision_ref="owner:decision:2026-06-10",
        )
        self.assertEqual(event.status, "promoted")
        self.assertEqual(event.promotion_decision_ref, "owner:decision:2026-06-10")

    def test_supersession_preserves_old_row_and_marks_superseded(self):
        harbor = self.harbor()
        old = harbor.record_event(
            summary="A manual surprise needs later correction",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:old",
            why_unexpected="The first observation was incomplete.",
        )
        replacement = harbor.record_event(
            summary="A corrected manual surprise replaces the old one",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:replacement",
            why_unexpected="The corrected observation keeps the original row visible.",
            supersedes_event_id=old.event_id,
        )

        harbor.supersede(old.event_id, replacement_event_id=replacement.event_id)

        old_after = harbor.get(old.event_id)
        replacement_after = harbor.get(replacement.event_id)
        self.assertEqual(old_after.status, "superseded")
        self.assertEqual(old_after.superseded_by_event_id, replacement.event_id)
        self.assertEqual(replacement_after.supersedes_event_id, old.event_id)
        self.assertEqual(harbor.list_by_status("superseded"), [old_after])

    def test_record_event_refuses_superseding_rejected_unsafe_terminal_record(self):
        harbor = self.harbor()
        old = harbor.record_event(
            summary="Unsafe observation must not gain a forward supersedes pointer",
            observed_by="witness",
            source_ref="tests:test_novelty_harbor:unsafe",
            why_unexpected="Terminal unsafe rows should remain unsafe, not relabeled.",
            covenant_break_flags=("gendered_maez",),
        )

        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="A replacement cannot point at terminal unsafe",
                observed_by="witness",
                source_ref="tests:test_novelty_harbor:replacement",
                why_unexpected="The forward pointer would semantically relabel unsafe.",
                supersedes_event_id=old.event_id,
            )

        old_after = harbor.get(old.event_id)
        self.assertEqual(old_after.status, "rejected_unsafe")
        self.assertEqual(harbor.list_by_status("rejected_unsafe"), [old_after])

    def test_record_event_refuses_superseding_already_superseded_record(self):
        harbor = self.harbor()
        old = harbor.record_event(
            summary="Original surprise becomes stale after first replacement",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:old",
            why_unexpected="This row will already have an authoritative replacement.",
        )
        replacement = harbor.record_event(
            summary="First replacement becomes the authoritative successor",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:replacement",
            why_unexpected="This row is the existing replacement.",
            supersedes_event_id=old.event_id,
        )
        harbor.supersede(old.event_id, replacement_event_id=replacement.event_id)

        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="Second replacement must not point at stale original",
                observed_by="codex",
                source_ref="tests:test_novelty_harbor:second-replacement",
                why_unexpected="A stale source should not gain a second successor.",
                supersedes_event_id=old.event_id,
            )

        old_after = harbor.get(old.event_id)
        self.assertEqual(old_after.status, "superseded")
        self.assertEqual(old_after.superseded_by_event_id, replacement.event_id)

    def test_record_event_refuses_conflicting_supersession_candidate(self):
        harbor = self.harbor()
        old = harbor.record_event(
            summary="Original surprise can have only one pending replacement",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:old",
            why_unexpected="Multiple forward candidates would conflict before supersede.",
        )
        replacement = harbor.record_event(
            summary="First replacement candidate points at old",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:replacement",
            why_unexpected="This is the pending authoritative replacement candidate.",
            supersedes_event_id=old.event_id,
        )

        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="Second replacement candidate must be rejected",
                observed_by="codex",
                source_ref="tests:test_novelty_harbor:second-replacement",
                why_unexpected="A second pending candidate would become stale.",
                supersedes_event_id=old.event_id,
            )

        old_after = harbor.get(old.event_id)
        replacement_after = harbor.get(replacement.event_id)
        self.assertEqual(old_after.status, "harbored")
        self.assertIsNone(old_after.superseded_by_event_id)
        self.assertEqual(replacement_after.supersedes_event_id, old.event_id)

    def test_supersede_refuses_rejected_unsafe_terminal_record(self):
        harbor = self.harbor()
        old = harbor.record_event(
            summary="Unsafe observation must remain terminal",
            observed_by="witness",
            source_ref="tests:test_novelty_harbor:unsafe",
            why_unexpected="A covenant break flag makes this a terminal rejection.",
            covenant_break_flags=("gendered_maez",),
        )
        replacement = harbor.record_event(
            summary="A later event cannot supersede terminal unsafe rejection",
            observed_by="witness",
            source_ref="tests:test_novelty_harbor:replacement",
            why_unexpected="Terminal unsafe records should stay visible as unsafe.",
        )

        with self.assertRaises(ValueError):
            harbor.supersede(old.event_id, replacement_event_id=replacement.event_id)

        old_after = harbor.get(old.event_id)
        self.assertEqual(old_after.status, "rejected_unsafe")
        self.assertEqual(harbor.list_by_status("rejected_unsafe"), [old_after])

    def test_supersede_requires_existing_replacement(self):
        harbor = self.harbor()
        old = harbor.record_event(
            summary="A manual surprise needs a real replacement",
            observed_by="manual_test",
            source_ref="tests:test_novelty_harbor:old",
            why_unexpected="Supersession should not point at a missing row.",
        )

        with self.assertRaises(KeyError):
            harbor.supersede(old.event_id, replacement_event_id=old.event_id + 1)

    def test_supersede_is_idempotent_for_existing_replacement(self):
        harbor = self.harbor()
        old = harbor.record_event(
            summary="Original surprise can be superseded idempotently",
            observed_by="manual_test",
            source_ref="tests:test_novelty_harbor:old",
            why_unexpected="Retrying the same supersession should be harmless.",
        )
        replacement = harbor.record_event(
            summary="Replacement already points at old",
            observed_by="manual_test",
            source_ref="tests:test_novelty_harbor:replacement",
            why_unexpected="This is the same authoritative replacement.",
            supersedes_event_id=old.event_id,
        )
        harbor.supersede(old.event_id, replacement_event_id=replacement.event_id)

        harbor.supersede(old.event_id, replacement_event_id=replacement.event_id)

        old_after = harbor.get(old.event_id)
        self.assertEqual(old_after.status, "superseded")
        self.assertEqual(old_after.superseded_by_event_id, replacement.event_id)

    def test_supersede_rejects_different_replacement_for_already_superseded_record(self):
        harbor = self.harbor()
        old = harbor.record_event(
            summary="Original surprise already has a successor",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:old",
            why_unexpected="A second successor would create stale provenance.",
        )
        replacement = harbor.record_event(
            summary="First replacement points at old",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:replacement",
            why_unexpected="This row is the current successor.",
            supersedes_event_id=old.event_id,
        )
        harbor.supersede(old.event_id, replacement_event_id=replacement.event_id)
        different = harbor.record_event(
            summary="Different replacement should not be accepted",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:different",
            why_unexpected="This row lacks the old row's forward authority.",
        )

        with self.assertRaises(ValueError):
            harbor.supersede(old.event_id, replacement_event_id=different.event_id)

        old_after = harbor.get(old.event_id)
        self.assertEqual(old_after.status, "superseded")
        self.assertEqual(old_after.superseded_by_event_id, replacement.event_id)

    def test_supersede_requires_replacement_to_point_at_old_event(self):
        harbor = self.harbor()
        old = harbor.record_event(
            summary="Original surprise requiring an exact replacement link",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:old",
            why_unexpected="Supersession should require a two-sided provenance link.",
        )
        other = harbor.record_event(
            summary="Different surprise that the replacement actually points at",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:other",
            why_unexpected="This is not the row being superseded.",
        )
        replacement = harbor.record_event(
            summary="Replacement points at the wrong old row",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:replacement",
            why_unexpected="One-sided links should not mark unrelated rows superseded.",
            supersedes_event_id=other.event_id,
        )

        with self.assertRaises(ValueError):
            harbor.supersede(old.event_id, replacement_event_id=replacement.event_id)

        self.assertEqual(harbor.get(old.event_id).status, "harbored")

    def test_supersede_refuses_rejected_unsafe_replacement(self):
        harbor = self.harbor()
        old = harbor.record_event(
            summary="Original surprise cannot be replaced by unsafe row",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:old",
            why_unexpected="Unsafe replacements should not become provenance authority.",
        )
        replacement = harbor.record_event(
            summary="Unsafe replacement row points at old",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:replacement",
            why_unexpected="The row has the right pointer but unsafe terminal status.",
            covenant_break_flags=("gendered_maez",),
            supersedes_event_id=old.event_id,
        )

        with self.assertRaises(ValueError):
            harbor.supersede(old.event_id, replacement_event_id=replacement.event_id)

        self.assertEqual(harbor.get(old.event_id).status, "harbored")

    def test_supersede_refuses_already_superseded_replacement(self):
        harbor = self.harbor()
        old = harbor.record_event(
            summary="Original surprise cannot be replaced by superseded row",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:old",
            why_unexpected="Superseded rows should not become replacement authority.",
        )
        replacement = harbor.record_event(
            summary="Initial replacement points at old",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:replacement",
            why_unexpected="This row will later be superseded itself.",
            supersedes_event_id=old.event_id,
        )
        final_replacement = harbor.record_event(
            summary="A later row supersedes the initial replacement",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor:final",
            why_unexpected="This marks the initial replacement stale.",
            supersedes_event_id=replacement.event_id,
        )
        harbor.supersede(
            replacement.event_id,
            replacement_event_id=final_replacement.event_id,
        )

        with self.assertRaises(ValueError):
            harbor.supersede(old.event_id, replacement_event_id=replacement.event_id)

        self.assertEqual(harbor.get(old.event_id).status, "harbored")

    def test_metadata_rejects_nested_or_oversized_prose(self):
        harbor = self.harbor()
        base = dict(
            summary="Metadata validation fixture",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor",
            why_unexpected="Metadata must not become a prose tunnel.",
        )

        with self.assertRaises(ValueError):
            harbor.record_event(**base, metadata={"nested": {"not": "allowed"}})
        with self.assertRaises(ValueError):
            harbor.record_event(**base, metadata={"long": "x" * 301})
        with self.assertRaises(ValueError):
            harbor.record_event(**base, metadata={f"k{i}": "x" * 100 for i in range(40)})

    def test_input_validation_rejects_unknowns_and_overlong_fields(self):
        harbor = self.harbor()
        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="",
                observed_by="codex",
                source_ref="tests:test",
                why_unexpected="empty summary",
            )
        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="x",
                observed_by="stranger",
                source_ref="tests:test",
                why_unexpected="unknown observer",
            )
        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="x",
                observed_by="codex",
                source_ref="tests:test",
                why_unexpected="unknown flag",
                covenant_break_flags=("not_a_flag",),
            )
        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="x" * 501,
                observed_by="codex",
                source_ref="tests:test",
                why_unexpected="overlong summary",
            )
