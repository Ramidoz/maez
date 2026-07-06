# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Phase 5.A — smoke-import every core module, both legacy and
subpackage paths. Fast regression net for the Phase 3 shim strategy
and future refactors.

For each module, we verify:
  1. The legacy `core.<name>` path imports without raising.
  2. The new `core.<subpkg>.<name>` path imports without raising.
  3. Both paths resolve to the same module object (the sys.modules
     alias trick actually worked).

This file is deliberately broad and shallow — one test method per
module. Behavioral tests for the modules that actually deserve them
live in their own test_<module>.py files (Phase 5.B). The goal here
is: a bad import or shim regression cannot slip through CI.
"""
from __future__ import annotations

import importlib
import unittest


# Map: (legacy_path, new_path).
# Grouped by subpackage for readability.
_MAP: list[tuple[str, str]] = [
    # --- safety ---
    ("core.context_safety",      "core.safety.context_safety"),
    ("core.self_claim_audit",    "core.safety.self_claim_audit"),
    ("core.owner_trust",         "core.safety.owner_trust"),
    ("core.injection_patterns",  "core.safety.injection_patterns"),
    ("core.cloud_redactor",      "core.safety.cloud_redactor"),

    # --- learning ---
    ("core.consequence_memory",  "core.learning.consequence_memory"),
    ("core.fabrication_memory",  "core.learning.fabrication_memory"),
    ("core.inner_residue",       "core.learning.inner_residue"),
    ("core.error_classifier",    "core.learning.error_classifier"),

    # --- decision ---
    ("core.decision_pipeline",   "core.decision.decision_pipeline"),
    ("core.pending_cards",       "core.decision.pending_cards"),
    ("core.approval_sessions",   "core.decision.approval_sessions"),
    ("core.proposal_lookup",     "core.decision.proposal_lookup"),

    # --- cognition ---
    ("core.cognition_quality",   "core.cognition.cognition_quality"),
    ("core.audit",               "core.cognition.audit"),
    ("core.audit_log",           "core.cognition.audit_log"),
    ("core.grounding_judge",     "core.cognition.grounding_judge"),
    ("core.quality_telemetry",   "core.cognition.quality_telemetry"),
    ("core.observability",       "core.cognition.observability"),

    # --- actions ---
    ("core.action_engine",       "core.actions.action_engine"),
    ("core.action_classifier",   "core.actions.action_classifier"),
    ("core.tool_loop",           "core.actions.tool_loop"),
    ("core.command_decomposer",  "core.actions.command_decomposer"),
    ("core.destructive_snapshot", "core.actions.destructive_snapshot"),

    # --- evolution ---
    ("core.soul_editor",         "core.evolution.soul_editor"),
    ("core.soul_invariants",     "core.evolution.soul_invariants"),
    ("core.soul_loader",         "core.evolution.soul_loader"),
    ("core.wants",               "core.evolution.wants"),
    ("core.will_i",              "core.evolution.will_i"),
    ("core.temperament",         "core.evolution.temperament"),
    ("core.wonderings",          "core.evolution.wonderings"),
    ("core.dream_state",         "core.evolution.dream_state"),

    # --- brain ---
    ("core.brain_loop",             "core.brain.brain_loop"),
    ("core.conversation_controller", "core.brain.conversation_controller"),

    # --- memory / perception / identity ---
    ("core.perception",          "core.memory.perception"),
    ("core.perception_cache",    "core.memory.perception_cache"),
    ("core.perception_envelope", "core.memory.perception_envelope"),
    ("core.ambient",             "core.memory.ambient"),
    ("core.ambient_format",      "core.memory.ambient_format"),
    ("core.memory_scoring",      "core.memory.memory_scoring"),
    ("core.continuity",          "core.memory.continuity"),
    ("core.identity",            "core.memory.identity"),
    ("core.identity_ledger",     "core.memory.identity_ledger"),
    ("core.source_awareness",    "core.memory.source_awareness"),

    # --- routing ---
    ("core.model_config",        "core.routing.model_config"),
    ("core.llm_client",          "core.routing.llm_client"),
    ("core.fast_backend_cloud",  "core.routing.fast_backend_cloud"),
    ("core.fast_backend_local",  "core.routing.fast_backend_local"),
    ("core.fast_backend_router", "core.routing.fast_backend_router"),
    ("core.context_compressor",  "core.routing.context_compressor"),
    ("core.claude_tier",         "core.routing.claude_tier"),

    # --- self_dev ---
    ("core.self_dev_hooks",        "core.self_dev.hooks"),
    ("core.self_dev_persistence",  "core.self_dev.persistence"),
    ("core.self_dev_scheduler",    "core.self_dev.scheduler"),
    ("core.workshop",              "core.self_dev.workshop"),

    # --- infra ---
    ("core.paths",                 "core.infra.paths"),
    ("core.capability_registry",   "core.infra.capability_registry"),
    ("core.self_model",            "core.infra.self_model"),
    ("core.public_user_shaping",   "core.infra.public_user_shaping"),
    ("core.private_thoughts",      "core.infra.private_thoughts"),
    ("core.install_recipes",       "core.infra.install_recipes"),
    ("core.builder_mode_capture",  "core.infra.builder_mode_capture"),
    ("core.builder_mode_perception", "core.infra.builder_mode_perception"),
    ("core.fast_prompt_builder",   "core.infra.fast_prompt_builder"),
    ("core.fast_reply_audit",      "core.infra.fast_reply_audit"),
    ("core.fast_reply_schema",     "core.infra.fast_reply_schema"),
    ("core.fast_conversation_log", "core.infra.fast_conversation_log"),
]


# self_dev itself is special: its content became core/self_dev/__init__.py,
# so it imports directly as `core.self_dev` — no shim/subpath pair.
_SELF_DEV_DIRECT = "core.self_dev"


class ShimSmokeTests(unittest.TestCase):
    """Every legacy import path must yield the same object as the new path.

    This is a regression net for the Phase 3 subpackage move: if a future
    refactor drops a shim, renames a module, or breaks the sys.modules
    alias trick, exactly one of these sub-tests will fail and point at
    the offending pair.
    """

    def test_every_pair_resolves_to_same_module(self):
        failures: list[str] = []
        for legacy, new in _MAP:
            with self.subTest(legacy=legacy, new=new):
                try:
                    lm = importlib.import_module(legacy)
                    nm = importlib.import_module(new)
                except Exception as e:
                    failures.append(f"{legacy} ↔ {new}: import raised {e!r}")
                    continue
                if lm is not nm:
                    failures.append(
                        f"{legacy} ({lm!r}) is not {new} ({nm!r}) "
                        f"— sys.modules alias broken"
                    )
        self.assertEqual(
            failures, [],
            "Shim resolution broke:\n  - " + "\n  - ".join(failures),
        )

    def test_self_dev_package_imports(self):
        """core.self_dev is a package (not a shim) — verify it resolves
        and exposes the public CLI builder + one known function."""
        mod = importlib.import_module(_SELF_DEV_DIRECT)
        self.assertTrue(callable(getattr(mod, "_build_argparser", None)),
                        "core.self_dev._build_argparser should be callable")
        self.assertTrue(callable(getattr(mod, "review", None)),
                        "core.self_dev.review should be callable")

    def test_core_paths_public_surface(self):
        """paths.py is load-bearing across every other module; verify its
        public helpers are all callable (catches accidental deletion)."""
        from core import paths
        for name in ("home", "config_dir", "data_dir", "memory_dir",
                     "logs_dir", "identity_file", "soul_base_path",
                     "soul_local_path", "ensure_dirs", "describe"):
            with self.subTest(helper=name):
                self.assertTrue(
                    callable(getattr(paths, name, None)),
                    f"core.paths.{name} should be callable",
                )

    def test_identity_public_surface(self):
        """identity.py gained git_handle / telegram_user_id / machine_profile
        in Phase 2 — verify they're still callable from both paths."""
        from core import identity as a
        from core.memory import identity as b
        self.assertIs(a, b)
        for name in ("display_name", "user_profile_id", "git_handle",
                     "telegram_user_id", "machine_profile", "home_coords",
                     "timezone", "jarvis_tier", "signal_ingest",
                     "proactive_messages", "describe"):
            with self.subTest(helper=name):
                self.assertTrue(
                    callable(getattr(a, name, None)),
                    f"core.identity.{name} should be callable",
                )


if __name__ == "__main__":
    unittest.main()
