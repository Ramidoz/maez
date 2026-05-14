# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for R5 — surface-coherence harness.

The 2026-05-04 symphony audit S3 designed a probe harness so future
SOUL edits / brain swaps / surface-adapter PRs are diffed against a
canonical baseline rather than discovered by humans noticing
"Maez sounds different on Telegram vs the cockpit." R5 implements
the harness in its minimum-viable shape:

  - Per-surface fingerprint: sha256 of the surface's system-prompt
    block (or canonical identity rendering), plus a boolean axis
    set (audit_gate_present, tool_manifest_present,
    circadian_present, body_truth_present).
  - Output artifact: `docs/audits/2026-05-04-symphony/baselines/
    surface_probe_<baseline_id>.json`
  - Replay: `--compare-baseline 2026-05-04` computes per-axis
    deltas and exits non-zero on flip.

The harness is probe-mode only — it never drives the live Telegram
bot or web cockpit. It calls internal prompt-builders / soul
loaders directly.

Contract enforced:
- core.symphony.surface_probe.run_probe(...) returns a dict with
  surfaces as keys and per-surface dicts as values.
- Each per-surface dict has the documented axis keys.
- Probe set includes the audit's natural-text probes ("i miss her",
  "what can you do with my screen?", etc.).
- Baseline serialization is JSON-stable so two runs with the same
  inputs produce byte-identical files (modulo timestamps).
- diff_baselines(old, new) returns a list of human-readable
  delta lines.

Tests are runtime-shaped against the public API; we don't require
the full surface set to be reachable in CI (some surfaces import
heavy daemon machinery).
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class R5_ProbeShape(unittest.TestCase):
    """REGRESSION GUARD: the harness output must have the documented
    shape so consumers (CI, future audits, drift detection) can
    rely on the contract."""

    def test_run_probe_returns_dict_with_surfaces(self):
        from core.symphony import surface_probe as sp
        result = sp.run_probe()
        self.assertIsInstance(result, dict)
        self.assertIn("baseline_id", result)
        self.assertIn("surfaces", result)
        self.assertIsInstance(result["surfaces"], dict)
        # We require AT LEAST one surface. Some surfaces import
        # heavy daemon machinery and may not be reachable in CI;
        # the harness must degrade gracefully.
        self.assertGreater(
            len(result["surfaces"]), 0,
            "run_probe must produce at least one surface fingerprint",
        )

    def test_each_surface_has_documented_axes(self):
        from core.symphony import surface_probe as sp
        result = sp.run_probe()
        REQUIRED_AXES = {
            "system_prompt_sha256",
            "system_prompt_chars",
            "audit_gate_present",
            "tool_manifest_present",
            "circadian_present",
            "body_truth_present",
            "identity_excerpt",
        }
        for surface_name, fingerprint in result["surfaces"].items():
            self.assertIsInstance(
                fingerprint, dict,
                f"surface {surface_name!r} must produce a dict",
            )
            missing = REQUIRED_AXES - set(fingerprint.keys())
            self.assertFalse(
                missing,
                f"surface {surface_name!r} missing axes: {missing}",
            )
            # Type checks on the axes
            self.assertIsInstance(
                fingerprint["system_prompt_sha256"], str,
            )
            self.assertEqual(
                len(fingerprint["system_prompt_sha256"]), 64,
                f"sha256 must be 64 hex chars; got "
                f"{fingerprint['system_prompt_sha256']!r}",
            )
            self.assertIsInstance(fingerprint["audit_gate_present"], bool)
            self.assertIsInstance(fingerprint["tool_manifest_present"], bool)
            self.assertIsInstance(fingerprint["circadian_present"], bool)
            self.assertIsInstance(fingerprint["body_truth_present"], bool)


class R5_KnownDivergencesCaptured(unittest.TestCase):
    """REGRESSION GUARD: the harness must capture the S3-known
    divergences. Public bot has no audit gate today (well, it does
    NOW post-R4 — but the harness must show it). Fast-reply does
    have body-truth-aware identity post-R4. Etc."""

    def test_telegram_public_has_audit_gate_post_r4(self):
        """Post-R4, telegram_public IS audit-gated. The harness
        must reflect the R4 fix."""
        from core.symphony import surface_probe as sp
        result = sp.run_probe()
        surfaces = result["surfaces"]
        if "telegram_public" not in surfaces:
            self.skipTest("telegram_public surface not reachable")
        self.assertTrue(
            surfaces["telegram_public"]["audit_gate_present"],
            "telegram_public should be audit-gated post-R4",
        )

    def test_fast_reply_has_body_truth_post_r4(self):
        """Post-R4, fast-lane consults body_capabilities."""
        from core.symphony import surface_probe as sp
        result = sp.run_probe()
        surfaces = result["surfaces"]
        if "fast_reply" not in surfaces:
            self.skipTest("fast_reply surface not reachable")
        self.assertTrue(
            surfaces["fast_reply"]["body_truth_present"],
            "fast_reply should be body-truth-aware post-R4",
        )


class R5_DiffBaselines(unittest.TestCase):
    """REGRESSION GUARD: diff_baselines(old, new) must surface
    per-axis flips so future drift is auditable."""

    def test_identical_baselines_produce_no_diff(self):
        from core.symphony import surface_probe as sp
        baseline = sp.run_probe()
        deltas = sp.diff_baselines(baseline, baseline)
        self.assertEqual(deltas, [])

    def test_modified_baseline_produces_delta(self):
        from core.symphony import surface_probe as sp
        baseline = sp.run_probe()
        # Synthesize a drift in one surface's audit_gate_present
        # axis.
        if not baseline["surfaces"]:
            self.skipTest("no surfaces probed")
        surface_name = next(iter(baseline["surfaces"].keys()))
        modified = json.loads(json.dumps(baseline))
        modified["surfaces"][surface_name]["audit_gate_present"] = (
            not modified["surfaces"][surface_name]["audit_gate_present"]
        )
        deltas = sp.diff_baselines(baseline, modified)
        self.assertGreater(
            len(deltas), 0,
            "modified baseline must produce at least one delta line",
        )
        # The delta must mention the axis that flipped.
        self.assertTrue(
            any("audit_gate_present" in d for d in deltas),
            f"delta must reference audit_gate_present; got {deltas}",
        )


class R5_BaselineSerialization(unittest.TestCase):
    """REGRESSION GUARD: the baseline must serialize stably so
    git diffs against it are readable and replay-comparison is
    cheap."""

    def test_baseline_round_trips_via_json(self):
        from core.symphony import surface_probe as sp
        baseline = sp.run_probe()
        serialized = json.dumps(
            baseline, indent=2, sort_keys=True, default=str,
        )
        restored = json.loads(serialized)
        self.assertEqual(
            sorted(restored["surfaces"].keys()),
            sorted(baseline["surfaces"].keys()),
        )


class R5_ProbeSetContainsNaturalText(unittest.TestCase):
    """REGRESSION GUARD: the natural-text probes specified in S3
    must be present in the harness's probe set so the harness
    actually exercises the failure modes the audit identified."""

    def test_natural_probes_listed(self):
        from core.symphony import surface_probe as sp
        REQUIRED_PROBES = {
            "hey you good?",
            "what can you do with my screen?",
            "can you check my Firefox tabs?",
            "i miss her",
        }
        probe_set = set(sp.NATURAL_TEXT_PROBES)
        missing = REQUIRED_PROBES - probe_set
        self.assertFalse(
            missing,
            f"NATURAL_TEXT_PROBES must include the audit-required "
            f"probes; missing: {missing}",
        )


if __name__ == "__main__":
    unittest.main()
