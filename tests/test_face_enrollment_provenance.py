# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Step 5x.D.D — face enrollment as observed system event.

Face enrollment writes a fresh core memory recording that a local
sensor-and-embedding pipeline ran successfully. It is NOT a
promotion of an existing memory row — there is no raw or core
ancestor to cite via ``promoted_from``. The camera frames are
sensor data, not memory.

The right tagging is therefore:

  - ``provenance_source="tool_observation"`` — the camera +
    embedding pipeline is a sensor producing an observation.
  - ``trust_tier="observed"`` — grounded in local sensor output;
    NOT covenant law (heartbeat-tier).
  - ``promoted_from`` is OMITTED. This is a fresh observed event,
    not a derivation. A future agent must not "fix" the absence
    by inventing a stub ancestor.

5x.D.D contract:
  - Enrollment core write carries the pair above.
  - ``promoted_from`` is None (no ancestors invented).
  - ``allow_untrusted_ancestors`` is False (this call site never
    opts in; symmetry with 5x.D.B1).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class _CapturingMemoryManager:
    """Stand-in for the real MemoryManager. Mirrors the live
    ``store_core`` signature exactly (per the 5x.D.B1 hardening)
    so a future required-kwarg drift surfaces here as TypeError
    rather than a silent permissive pass."""

    def __init__(self):
        self.store_core_calls: list[dict] = []

    def store_core(self, content, source="reasoning", *,
                   provenance_source=None, trust_tier=None,
                   promoted_from=None,
                   allow_untrusted_ancestors=False):
        self.store_core_calls.append({
            "content": content,
            "source": source,
            "provenance_source": provenance_source,
            "trust_tier": trust_tier,
            "promoted_from": promoted_from,
            "allow_untrusted_ancestors": allow_untrusted_ancestors,
        })
        return "core-fake-id"


class FaceEnrollmentProvenanceTests(unittest.TestCase):
    def test_enrollment_writes_observed_tool_observation_core(self):
        """Direct-call test against the production store_core
        signature: assert the enrollment site passes
        tool_observation/observed and omits promoted_from."""
        mm = _CapturingMemoryManager()
        # Replicate the production call shape from
        # skills/face_enrollment.py post-5x.D.D. If the production
        # signature drifts, this test goes RED and points the
        # next agent at the wiring contract.
        from skills.face_enrollment import _emit_enrollment_core_memory
        _emit_enrollment_core_memory(
            mm=mm, frame_count=5, name="the owner",
        )
        self.assertEqual(len(mm.store_core_calls), 1)
        call = mm.store_core_calls[0]

        # Freeform source preserved (same pattern as Pass 1: source
        # and provenance_source are non-overlapping fields).
        self.assertEqual(call["source"], "face_enrollment")

        # The provenance pair: sensor produced observation;
        # observed-tier (not covenant — face enrollment is a local
        # tool event, not covenant law).
        self.assertEqual(call["provenance_source"], "tool_observation")
        self.assertEqual(call["trust_tier"], "observed")

    def test_enrollment_does_not_invent_ancestors(self):
        """Camera frames are sensor data, not memory. There is no
        raw or core ancestor to cite via promoted_from. Asserting
        None locks the design against a future "fix" that adds a
        stub ancestor (which would falsely run through the
        promotion gate's worst-wins logic on a non-promotion)."""
        mm = _CapturingMemoryManager()
        from skills.face_enrollment import _emit_enrollment_core_memory
        _emit_enrollment_core_memory(
            mm=mm, frame_count=5, name="the owner",
        )
        call = mm.store_core_calls[0]
        self.assertIsNone(call["promoted_from"])

    def test_enrollment_does_not_opt_in_to_untrusted_ancestors(self):
        """Symmetry with 5x.D.B1's safety contract: this call site
        must never silently opt in to untrusted-ancestor promotion.
        The default (False) is the only acceptable value; any
        future "let's relax this" edit MUST be visible in this
        test as a deliberate change, not a silent regression."""
        mm = _CapturingMemoryManager()
        from skills.face_enrollment import _emit_enrollment_core_memory
        _emit_enrollment_core_memory(
            mm=mm, frame_count=5, name="the owner",
        )
        call = mm.store_core_calls[0]
        self.assertFalse(call["allow_untrusted_ancestors"])

    def test_enrollment_content_includes_frame_count_and_name(self):
        """Sanity check: the production text format is preserved
        end-to-end. If this drifts unintentionally, downstream
        recall regexes (or the operator's eyeball) will miss the
        pattern."""
        mm = _CapturingMemoryManager()
        from skills.face_enrollment import _emit_enrollment_core_memory
        _emit_enrollment_core_memory(
            mm=mm, frame_count=12, name="the owner",
        )
        call = mm.store_core_calls[0]
        self.assertIn("the owner", call["content"])
        self.assertIn("12", call["content"])
        self.assertIn("Face enrollment", call["content"])


if __name__ == "__main__":
    unittest.main()
