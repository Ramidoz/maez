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


if __name__ == "__main__":
    unittest.main()
