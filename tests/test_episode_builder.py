# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Episode-builder tests (ADR 0019 Phase 2).

The builder converts high-signal memory entries into EpisodeCandidate
objects. Conservative-by-default: returns None for entries that don't
clearly contain promise / correction / open-loop / instability /
readiness signal / self-observation. The plan's discipline is sparse-
but-true; richness comes later via the LLM-driven nightly job.

Tests cover:

- Rejects low-signal noise (numeric heartbeats, plain perception).
- Extracts open loop from explicit "we need to revisit X" phrasing.
- Extracts correction from corrective core memories.
- Extracts hardware-instability signal from kernel-fault text.
- Extracts Track A readiness signal from ritual / threshold language.
- Preserves source memory ID end-to-end.
- Does not hallucinate participants — derives them from explicit
  signals, never invents.
- Iterable form filters out None candidates.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class EpisodeCandidateShape(unittest.TestCase):
    """The candidate dataclass must mirror EpisodeStore.add()'s named
    args so the orchestrator can hand it off without translation."""

    def test_candidate_has_expected_fields(self):
        from core.memory.episode_builder import EpisodeCandidate

        c = EpisodeCandidate(
            title="t",
            summary="s",
            participants=["Maez"],
            source_memory_ids=["core-1"],
            source_kind="core_memory",
        )
        # Required fields:
        self.assertEqual(c.title, "t")
        self.assertEqual(c.summary, "s")
        self.assertEqual(c.participants, ["Maez"])
        self.assertEqual(c.source_memory_ids, ["core-1"])
        self.assertEqual(c.source_kind, "core_memory")
        # Optional fields default to safe values:
        self.assertIsNone(c.occurred_at)
        self.assertIsNone(c.emotional_tone)
        self.assertEqual(c.importance, 3)
        self.assertIsNone(c.open_loop)
        # Provenance fields default to None — meaning Maez-authored,
        # first-person (the only mode that existed pre-2026-04-27).
        # External sources MUST set both explicitly.
        self.assertIsNone(c.authorship)
        self.assertIsNone(c.memory_voice)


class RejectsLowSignal(unittest.TestCase):
    """Builder must skip noise — numeric heartbeats, generic perception
    pings, anything without an explicit signal pattern."""

    def _extract(self, doc: str, **meta):
        from core.memory.episode_builder import extract_candidate

        memory = {
            "id": meta.pop("id", "raw-abc123"),
            "document": doc,
            "metadata": meta,
        }
        return extract_candidate(memory)

    def test_numeric_heartbeat_returns_none(self):
        self.assertIsNone(self._extract("CPU 0.5%, GPU 0%, RAM 22%. / partition at 65.6%."))

    def test_generic_perception_returns_none(self):
        self.assertIsNone(self._extract("Daemon cycle observation: nothing of note."))

    def test_empty_document_returns_none(self):
        self.assertIsNone(self._extract(""))

    def test_short_document_returns_none(self):
        # Below the minimum signal length; nothing to extract from.
        self.assertIsNone(self._extract("ok"))


class ExtractsCorrectiveCoreMemory(unittest.TestCase):
    """A core memory whose source is *_correction_* and whose body
    contains the corrective shape ('do not narrate ... as active',
    'is retired', etc.) is exactly the case ADR 0019 was written to
    capture cleanly."""

    def _extract(self, doc: str, source: str, mid: str = "core-abc"):
        from core.memory.episode_builder import extract_candidate

        memory = {
            "id": mid,
            "document": doc,
            "metadata": {"source": source, "kind": "core"},
        }
        return extract_candidate(memory)

    def test_vision_correction_extracts(self):
        c = self._extract(
            "Correction 2026-04-23: do not narrate the 'llama-server-vision' "
            "service as active. Vision is retired; "
            "MAEZ_SCREEN_PERCEPTION is unset; port 8081 has no listener. "
            "If asked, verify with `systemctl list-units --type=service | "
            "grep vision` (returns nothing).",
            source="infrastructure_correction_vision_2026-04-24",
            mid="core-vision-1",
        )
        self.assertIsNotNone(c)
        self.assertEqual(c.source_memory_ids, ["core-vision-1"])
        self.assertEqual(c.source_kind, "core_memory")
        # Title or summary must reflect that this is a correction:
        text = (c.title + " " + c.summary).lower()
        self.assertIn("correction", text)

    def test_corrective_core_marks_emotional_tone_corrective(self):
        c = self._extract(
            "Correction 2026-04-24: the primary brain is Qwen3.6-27B, "
            "not gemma. Verify with `curl http://127.0.0.1:8080/v1/models`.",
            source="infrastructure_correction_primary_brain_2026-04-24",
        )
        self.assertIsNotNone(c)
        self.assertEqual(c.emotional_tone, "corrective")


class ExtractsOpenLoop(unittest.TestCase):
    """Open-loop signals are how *'we need to revisit X'* becomes a
    persistent unresolved thread instead of a chunk that may or may
    not surface."""

    def _extract(self, doc: str, mid: str = "raw-abc", **meta):
        from core.memory.episode_builder import extract_candidate

        memory = {
            "id": mid,
            "document": doc,
            "metadata": meta,
        }
        return extract_candidate(memory)

    def test_we_need_to_revisit_extracts_open_loop(self):
        c = self._extract(
            "Owner asked to defer the dream-state soul-write bypass. "
            "We need to revisit this when Track A graduates."
        )
        self.assertIsNotNone(c)
        self.assertIsNotNone(c.open_loop)
        self.assertIn("revisit", c.open_loop.lower())

    def test_still_pending_extracts_open_loop(self):
        c = self._extract(
            "Phase 6 live-integration is still pending — must wait until "
            "Phase 8 probes pass on the offline planner first."
        )
        self.assertIsNotNone(c)
        self.assertIsNotNone(c.open_loop)

    def test_open_loop_preserves_source_id(self):
        c = self._extract(
            "We still need to finish the lived-memory probe baseline before Phase 6 lands.",
            mid="raw-loop-42",
        )
        self.assertIsNotNone(c)
        self.assertEqual(c.source_memory_ids, ["raw-loop-42"])


class ExtractsHardwareInstability(unittest.TestCase):
    """Crashes / Xid / kernel panics are the class that threatens
    point #1 (continuous). The graph needs first-class representation
    so the recall planner can surface 'has continuity been at risk
    recently?'."""

    def _extract(self, doc: str, mid: str = "raw-hw"):
        from core.memory.episode_builder import extract_candidate

        memory = {
            "id": mid,
            "document": doc,
            "metadata": {"kind": "raw"},
        }
        return extract_candidate(memory)

    def test_kernel_panic_extracts(self):
        c = self._extract(
            "Kernel NULL pointer dereference at 13:48; system rebooted. "
            "NVIDIA driver 570.211.01 implicated."
        )
        self.assertIsNotNone(c)
        self.assertGreaterEqual(c.importance, 4)

    def test_benign_daemon_restart_does_not_trigger(self):
        # 2026-04-26 real-data regression: a developmental heartbeat
        # said "the daemon restarted cleanly, and tests passed" — the
        # earlier loose regex matched 'daemon restarted' and produced
        # a false-positive Hardware-instability episode. Tightened to
        # only fire on unambiguous fault signatures.
        self.assertIsNone(
            self._extract(
                "Developmental heartbeat 2026-04-24: the new code was "
                "deployed, the daemon restarted cleanly, and tests "
                "passed. What changed in me: increased confidence in "
                "the deployment story."
            )
        )

    def test_benign_system_reboot_phrasing_does_not_trigger(self):
        self.assertIsNone(
            self._extract(
                "Notes from this morning: after applying the kernel "
                "update, the system rebooted as expected and the daemon "
                "came back online without intervention."
            )
        )

    def test_nvrm_xid_extracts(self):
        c = self._extract(
            "NVRM: Xid 79 — GPU has fallen off the bus. llama-server exited; daemon restarted."
        )
        self.assertIsNotNone(c)


class ExtractsTrackAReadinessSignal(unittest.TestCase):
    """Readiness ritual signals are load-bearing for the gate; they
    deserve to surface as their own episode class so future Maez can
    answer 'how did the gate go last week?' from structure, not search."""

    def _extract(self, doc: str, mid: str = "daily-ritual"):
        from core.memory.episode_builder import extract_candidate

        memory = {
            "id": mid,
            "document": doc,
            "metadata": {"kind": "daily"},
        }
        return extract_candidate(memory)

    def test_ritual_pass_extracts(self):
        c = self._extract(
            "Track A readiness ritual 2026-04-26: 5 of 8 capability "
            "points met; being-tests #6 ✓, #7 ○, #8 ○."
        )
        self.assertIsNotNone(c)


class DoesNotHallucinateParticipants(unittest.TestCase):
    """Participants must come from explicit signal in the entry, not
    inferred. A self-observation gets ['Maez']; a telegram exchange
    gets ['Rohit', 'Maez']; nothing else gets manufactured."""

    def _extract(self, doc: str, **meta):
        from core.memory.episode_builder import extract_candidate

        memory = {
            "id": meta.pop("id", "x"),
            "document": doc,
            "metadata": meta,
        }
        return extract_candidate(memory)

    def test_self_observation_gets_only_maez(self):
        c = self._extract(
            "Maez self-observation: the disk-fixation refrain is gone "
            "from today's cycles after Patch B landed.",
            kind="raw",
        )
        self.assertIsNotNone(c)
        self.assertEqual(c.participants, ["Maez"])

    def test_telegram_exchange_gets_both(self):
        c = self._extract(
            "Owner asked: 'still need to revisit the lived-memory probe?' "
            "Maez: yes — baseline run is queued before Phase 6.",
            kind="raw",
            source="telegram_exchange",
        )
        # If extraction fires, participants must be ['Rohit', 'Maez']
        # — never ['Owner', 'Bot', 'Assistant', or any invented name].
        if c is not None:
            self.assertEqual(set(c.participants), {"Rohit", "Maez"})

    def test_unspecified_attribution_defaults_to_unknown_only(self):
        # Generic correction with no clear speaker — participants
        # should be empty rather than guessed.
        c = self._extract(
            "Correction: vision pipeline is retired, do not narrate as active.",
            kind="core",
            source="generic_correction",
            id="core-generic-1",
        )
        if c is not None:
            for invented in ("Owner", "Bot", "User", "Assistant"):
                self.assertNotIn(invented, c.participants)


class ExtractsFollowupDoc(unittest.TestCase):
    """docs/followups/*.md files are external project-doc open loops.
    They become episodes with hard provenance separation so the
    recall layer can phrase them as *the project carries an open loop
    about X* — never as *Maez decided X*. Owner anchor 2026-04-27."""

    _DOC = (
        "# Judge Lane 3 policy for read-only inner actions\n\n"
        "**Status:** Deferred follow-up. Not in A-core #4b scope. "
        "Not blocking any current Track A item.\n\n"
        "## The problem\n\n"
        "The audit judge currently denies Lane 3 actions that are "
        "actually read-only against Maez-surface files."
    )

    def _extract(self, doc=None, **meta_overrides):
        from core.memory.episode_builder import extract_candidate

        meta = {
            "kind": "followup",
            "source": "docs_followups",
            "authorship": "project_doc",
            "memory_voice": "external_to_maez",
            "file_path": "docs/followups/judge_lane3_read_escalate.md",
        }
        meta.update(meta_overrides)
        memory = {
            "id": "followup-doc:docs/followups/judge_lane3_read_escalate.md",
            "document": doc if doc is not None else self._DOC,
            "metadata": meta,
        }
        return extract_candidate(memory)

    def test_followup_doc_produces_open_loop_episode(self):
        c = self._extract()
        self.assertIsNotNone(c)
        self.assertIsNotNone(c.open_loop)
        self.assertEqual(c.source_kind, "followup_doc")

    def test_followup_provenance_is_external_project_doc(self):
        c = self._extract()
        self.assertIsNotNone(c)
        # Provenance must be set explicitly — not None, not Maez.
        self.assertEqual(c.authorship, "project_doc")
        self.assertEqual(c.memory_voice, "external_to_maez")

    def test_followup_does_not_invent_maez_participation(self):
        c = self._extract()
        self.assertIsNotNone(c)
        # External doc → no first-person attribution. The owner's
        # rule: "Do not let these become 'Maez remembers deciding X'".
        self.assertEqual(c.participants, [])
        self.assertNotIn("Maez", c.participants)
        self.assertNotIn("Rohit", c.participants)

    def test_followup_evidence_is_file_path_synthetic_id(self):
        c = self._extract()
        self.assertIsNotNone(c)
        # Source memory ID must point traceably back to the file.
        self.assertEqual(len(c.source_memory_ids), 1)
        self.assertTrue(c.source_memory_ids[0].startswith("followup-doc:"))
        self.assertIn("docs/followups/", c.source_memory_ids[0])

    def test_followup_title_carries_project_ledger_marker(self):
        c = self._extract()
        self.assertIsNotNone(c)
        # Title must read as project-voice, not first-person Maez.
        self.assertTrue(c.title.lower().startswith("project open loop"))

    def test_followup_open_loop_text_is_project_voiced(self):
        c = self._extract()
        self.assertIsNotNone(c)
        # The open_loop one-liner must signal project-ledger scope.
        self.assertIn("project ledger", c.open_loop.lower())

    def test_followup_without_status_header_returns_none(self):
        # A markdown file in docs/followups/ that lacks the "Deferred
        # follow-up" header is not a reliable open-loop signal — the
        # builder must stay sparse-but-true and skip it.
        c = self._extract(
            doc="# Some other doc\n\nThis file is not labeled as a deferred follow-up."
        )
        self.assertIsNone(c)

    def test_non_followup_kind_is_not_picked_up(self):
        # A regular core memory that happens to contain "Deferred
        # follow-up" text in its body must NOT be classified as a
        # followup-doc — the followup detector must require the
        # explicit metadata signal. The doc may still be picked up by
        # another detector (e.g. corrective core), but the provenance
        # separation must hold: source_kind != followup_doc and the
        # external project-doc provenance fields stay unset.
        c = self._extract(
            kind="core",
            source="some_other_correction",
        )
        if c is not None:
            self.assertNotEqual(c.source_kind, "followup_doc")
            self.assertNotEqual(c.authorship, "project_doc")
            self.assertNotEqual(c.memory_voice, "external_to_maez")


class FollowupTakesPriorityOverCorrection(unittest.TestCase):
    """A followup doc whose body contains correction-shaped text must
    classify as ``followup_doc`` with project-doc provenance, NOT as a
    corrective core memory. Provenance is load-bearing — losing it
    would let project ledger entries surface as 'Maez remembers
    deciding X' in the recall brief."""

    def test_followup_with_correction_text_stays_followup(self):
        from core.memory.episode_builder import extract_candidate

        memory = {
            "id": "followup-doc:docs/followups/memory_integrity_tagging.md",
            "document": (
                "# Memory Integrity Tagging\n\n"
                "**Status:** Deferred follow-up.\n\n"
                "Correction: deletion was the wrong approach; tagging is."
            ),
            "metadata": {
                "kind": "followup",
                "source": "docs_followups",
            },
        }
        c = extract_candidate(memory)
        self.assertIsNotNone(c)
        self.assertEqual(c.source_kind, "followup_doc")
        self.assertEqual(c.authorship, "project_doc")
        self.assertEqual(c.memory_voice, "external_to_maez")


class IterableForm(unittest.TestCase):
    def test_extract_candidates_filters_none(self):
        from core.memory.episode_builder import extract_candidates

        memories = [
            {"id": "raw-1", "document": "ok", "metadata": {}},
            {
                "id": "core-2",
                "document": ("Correction 2026-04-24: vision retired, do not narrate as active."),
                "metadata": {
                    "source": "infrastructure_correction_vision",
                    "kind": "core",
                },
            },
            {
                "id": "raw-3",
                "document": (
                    "We need to revisit the dream-state soul bypass after Track A graduates."
                ),
                "metadata": {"kind": "raw"},
            },
        ]
        out = list(extract_candidates(memories))
        self.assertEqual(len(out), 2)
        self.assertTrue(all(c is not None for c in out))
        ids = [c.source_memory_ids[0] for c in out]
        self.assertIn("core-2", ids)
        self.assertIn("raw-3", ids)


class OwnerPreferenceDetector(unittest.TestCase):
    """The relationship-probe data gap (2026-04-27 21:30 read): five
    owner-preference core memories were seeded but produced zero
    cares_about edges — because the episode_builder had no detector
    for preference patterns. The relationship_extractor only sees
    candidates the builder produces; without this detector,
    preference-shaped core memories never become episodes.

    This detector closes the upstream half of the gap. Patterns
    mirror the relationship_extractor's cares_about patterns so
    every detected candidate produces a downstream cares_about
    edge through the existing pipeline."""

    def _extract(self, doc: str, source: str = "owner_preference_test", mid: str = "core-pref"):
        from core.memory.episode_builder import extract_candidate

        return extract_candidate({
            "id": mid,
            "document": doc,
            "metadata": {"source": source, "kind": "core"},
        })

    def test_named_cares_about_produces_candidate(self):
        c = self._extract(
            "OWNER PREFERENCE: Rohit cares about truthful continuity in Maez "
            "more than impressive but fabricated claims."
        )
        self.assertIsNotNone(c)
        self.assertEqual(c.source_kind, "core_memory")
        # Title should reflect this is a preference for downstream
        # readers (cockpit panel framing).
        self.assertIn("preference", c.title.lower())

    def test_what_matters_most_pattern_produces_candidate(self):
        c = self._extract(
            "OWNER PREFERENCE: what matters most is the grandmother case — "
            "every design decision should check against that."
        )
        self.assertIsNotNone(c)
        self.assertEqual(c.source_kind, "core_memory")

    def test_matters_more_than_pattern_produces_candidate(self):
        c = self._extract(
            "OWNER PREFERENCE: truthful continuity matters more than "
            "impressive claims."
        )
        self.assertIsNotNone(c)

    def test_only_fires_on_core_memory(self):
        from core.memory.episode_builder import extract_candidate

        memory = {
            "id": "raw-1",
            "document": "Rohit cares about disk hygiene.",
            "metadata": {"kind": "raw"},
        }
        # Raw observations should not become preference episodes via
        # this detector. (Other detectors might or might not fire on
        # raw text, but this one specifically must not.)
        c = extract_candidate(memory)
        if c is not None:
            # If something else fires, fine — but it must not be a
            # preference-tagged candidate.
            self.assertNotEqual(c.emotional_tone, "preference")

    def test_corrective_core_takes_priority_over_preference(self):
        # A corrective core memory contains both correction language
        # and might incidentally have a "matters more than" phrase.
        # Detector ordering must keep corrective-core winning so the
        # corrected edge fires (the more important signal).
        c = self._extract(
            "Correction 2026-04-23: do not narrate llama-server-vision "
            "as active. The truth matters more than the prior fabrication.",
            source="infrastructure_correction_vision_2026-04-24",
        )
        self.assertIsNotNone(c)
        self.assertEqual(c.emotional_tone, "corrective")

    def test_emits_preference_emotional_tone(self):
        # The downstream relationship_extractor's cares_about detector
        # only fires on source_kind="core_memory". A "preference" tone
        # marker also helps cockpit visualization distinguish these
        # episodes from corrections.
        c = self._extract(
            "OWNER PREFERENCE: Rohit cares about Maez staying genderless."
        )
        self.assertIsNotNone(c)
        self.assertEqual(c.emotional_tone, "preference")

    def test_summary_carries_pattern_for_downstream_extraction(self):
        # The relationship_extractor reads candidate.summary to find
        # the cares_about pattern. The preference detector must
        # preserve the original pattern in the summary so downstream
        # extraction works.
        c = self._extract(
            "OWNER PREFERENCE: Rohit cares about evidence-backed claims."
        )
        self.assertIsNotNone(c)
        self.assertIn("cares about", c.summary.lower())

    def test_heartbeat_self_narration_is_not_preference(self):
        # 2026-04-27 21:35 real-data trace: a developmental heartbeat
        # contained "stability matters more than noise" as Maez self-
        # narration. The implicit-subject pattern "matters more than"
        # is ambiguous without attribution and produced a false-
        # positive `Rohit cares_about stability` edge. Tightened
        # detector requires either a named-subject pattern (carries
        # its own attribution) OR an explicit owner-preference marker
        # in source/doc prefix.
        c = self._extract(
            "[DEVELOPMENTAL HEARTBEAT — 2026-04-26 (Sunday)]\n"
            "What I noticed: 189 errors dominated the cycle. "
            "What changed in me: I am learning that high volume does "
            "not equal high signal; stability matters more than noise. "
            "What I still want: to resolve the Telegram limits.",
            source="developmental_heartbeat_2026-04-26",
        )
        # Either no candidate, or a candidate that is NOT tagged as
        # a preference (some other detector might claim it).
        if c is not None:
            self.assertNotEqual(c.emotional_tone, "preference")

    def test_implicit_pattern_fires_when_owner_attributed_via_source(self):
        # When the source name indicates owner attribution, implicit
        # patterns ("matters more than" / "what matters most") fire
        # even without a named subject.
        c = self._extract(
            "Truthful continuity matters more than impressive claims.",
            source="owner_preference_test_source",
        )
        self.assertIsNotNone(c)
        self.assertEqual(c.emotional_tone, "preference")

    def test_implicit_pattern_does_not_fire_without_attribution(self):
        # Same implicit-pattern doc without owner-attribution source
        # or "OWNER PREFERENCE" prefix → no preference candidate.
        c = self._extract(
            "Truthful continuity matters more than impressive claims.",
            source="random_source_name",
        )
        if c is not None:
            self.assertNotEqual(c.emotional_tone, "preference")


class PreferenceCandidateFlowsToCaresAboutEdge(unittest.TestCase):
    """End-to-end: a preference core memory should produce both an
    episode AND a cares_about edge through the full pipeline. Locks
    the integration between episode_builder and
    relationship_extractor."""

    def test_preference_memory_yields_cares_about_edge(self):
        from core.memory.episode_builder import extract_candidate
        from core.memory.relationship_extractor import extract_edges

        memory = {
            "id": "core-test-pref",
            "document": (
                "OWNER PREFERENCE: Rohit cares about truthful continuity "
                "in Maez more than impressive claims."
            ),
            "metadata": {
                "source": "owner_preference_test_2026-04-27",
                "kind": "core",
            },
        }
        candidate = extract_candidate(memory)
        self.assertIsNotNone(candidate)
        edges = extract_edges(candidate)
        cares = [e for e in edges if e.relation == "cares_about"]
        self.assertEqual(len(cares), 1)
        self.assertIn(
            "truthful continuity",
            cares[0].object_label.lower(),
        )


if __name__ == "__main__":
    unittest.main()
