# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Runtime self-truth sweep — Commit 6 of the 2026-04-23 audit repair pass.

Invariant guarded here:

    The codebase no longer carries hardcoded "gemma-4-26b" /
    "gemma4:26b" / "llama-server-vision" strings as live runtime
    defaults. Those labels were current months ago; they're stale now.
    Where env-override indirection already existed, the DEFAULT is
    updated to track the current primary model config. Where a
    hardcoded literal existed, it's replaced with a read from
    core.routing.model_config.

Critical identity-ledger invariant also guarded here: future ledger
rows record the ACTUAL current base model at creation time, not a
stale fallback. An instance born on Qwen3.6-27B must not be stamped
"gemma-4-26b" in its covenant ledger.

Scope
-----
Stale labels CHANGED (live runtime defaults):
  skills/self_mod_dialog.py         (3 MAEZ_SELF_MOD_*_MODEL defaults)
  skills/card_reply_classifier.py   (MAEZ_AUDIT_MODEL default)
  core/cognition/audit.py           (2 × MAEZ_AUDIT_MODEL default)
  core/memory/identity_ledger.py    (MAEZ_LLAMACPP_MODEL default)
  core/evolution/dream_state.py     (MODEL constant)
  core/memory/continuity.py         (chat() model= literal)
  core/brain/conversation_controller.py (default param)
  core/routing/llm_client.py        (generate() default param)
  cli/maez_chat.py                  ("llama-server-vision.service" in /status)
  skills/web_interface.py           (JOURNAL_SERVICES tuple)

Stale labels KEPT with a legacy-label comment (covenant protection):
  config/policies.yaml              (protected_{processes,services})
  core/actions/action_engine.py     (service_name denylist)

Out of scope:
  core/routing/fast_backend_local.py — routing decision (retire or
    retune as an Ollama-backend fallback), deferred.
  Test fixtures / benchmark corpora — intentional historical values.
  Comments documenting past sessions — historical record, not
    runtime-facing.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class GemmaLiteralsNotDefaultsAnymore(unittest.TestCase):
    """No live runtime path should have a hardcoded gemma string."""

    def _assert_no_literal(self, relpath: str, literal: str,
                           allowed_contexts: tuple[str, ...] = ()):
        """Read relpath, scan for literal. Fail unless every occurrence
        is within an allowed context (comment prefix, docstring, legacy
        label, etc.)."""
        src = (_REPO / relpath).read_text()
        offending = []
        for i, line in enumerate(src.splitlines(), 1):
            if literal not in line:
                continue
            stripped = line.strip()
            if any(ctx in line for ctx in allowed_contexts):
                continue
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            offending.append(f"{relpath}:{i}: {line!r}")
        self.assertFalse(
            offending,
            f"{relpath} still carries live '{literal}' literal:\n"
            + "\n".join(offending),
        )

    def test_self_mod_dialog_no_gemma_default(self):
        self._assert_no_literal("skills/self_mod_dialog.py", "gemma-4-26b")

    def test_card_reply_classifier_no_gemma_default(self):
        self._assert_no_literal(
            "skills/card_reply_classifier.py", "gemma-4-26b",
        )

    def test_cognition_audit_no_gemma_default(self):
        self._assert_no_literal(
            "core/cognition/audit.py", "gemma-4-26b",
        )

    def test_identity_ledger_no_gemma_in_live_fingerprint(self):
        """The compute_identity_fingerprint function body must not
        carry a 'gemma-4-26b' fallback. Test-fixture code inside
        the module's `__main__` block is allowed to reference the
        string — that's deliberate historical data for the brain-
        swap detector test."""
        src = (_REPO / "core" / "memory" / "identity_ledger.py").read_text()
        # Find the function body
        fn_start = src.find("def compute_identity_fingerprint")
        self.assertNotEqual(fn_start, -1)
        # End at the next top-level def or class
        import re as _re
        m = _re.search(r"\ndef |\nclass ", src[fn_start + 30:])
        end = (fn_start + 30 + m.start()) if m else len(src)
        body = src[fn_start:end]
        # The fallback literal in the body is the regression; inline
        # docstring text mentioning historical fallback is allowed
        # as long as it's in a triple-quoted block.
        for i, line in enumerate(body.splitlines(), 1):
            stripped = line.strip()
            if "gemma-4-26b" not in line:
                continue
            # Allow comment/docstring lines, allow "stale fallback" note
            if stripped.startswith("#") or "stale fallback" in line:
                continue
            if stripped.startswith('"') or stripped.startswith("'"):
                continue
            self.fail(
                "compute_identity_fingerprint body still contains a "
                f"live 'gemma-4-26b' literal at line {i}: {line!r}"
            )

    def test_identity_ledger_fingerprint_uses_served_model_alias(self):
        """The identity ledger must fingerprint the brain Maez is
        actually serving, not a stale configured/requested label."""
        from core.memory import identity_ledger as il

        with (
            mock.patch.dict(
                os.environ,
                {"MAEZ_LLAMACPP_MODEL": "stale-requested-label"},
                clear=False,
            ),
            mock.patch.object(
                il,
                "served_model_alias",
                return_value="qwen36-27b-mtp",
                create=True,
            ) as served,
        ):
            fp = il.compute_identity_fingerprint(soul_path=Path("/missing-soul"))

        self.assertEqual(fp["base_model"], "qwen36-27b-mtp")
        served.assert_called_once_with(
            default="stale-requested-label",
            timeout_s=0.25,
        )

    def test_identity_ledger_falls_back_when_served_model_is_unknown(self):
        """A transient `/props` failure must not stamp a false
        `llamacpp:unknown` brain swap into the continuity ledger."""
        from core.memory import identity_ledger as il

        with (
            mock.patch.dict(
                os.environ,
                {"MAEZ_LLAMACPP_MODEL": "configured-label"},
                clear=False,
            ),
            mock.patch.object(
                il,
                "served_model_alias",
                return_value="llamacpp:unknown",
                create=True,
            ) as served,
        ):
            fp = il.compute_identity_fingerprint(soul_path=Path("/missing-soul"))

        self.assertEqual(fp["base_model"], "configured-label")
        served.assert_called_once_with(
            default="configured-label",
            timeout_s=0.25,
        )

    def test_startup_detector_records_served_model_alias_swap(self):
        """A served brain swap must be ledger-visible even when the
        configured/requested model label stays unchanged."""
        from core.memory import identity_ledger as il

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "identity_ledger.db"
            with (
                mock.patch.dict(
                    os.environ,
                    {"MAEZ_LLAMACPP_MODEL": "same-requested-label"},
                    clear=False,
                ),
                mock.patch.object(
                    il,
                    "served_model_alias",
                    return_value="old-served",
                    create=True,
                ),
            ):
                ledger = il.IdentityLedger(db_path=db)

            with (
                mock.patch.dict(
                    os.environ,
                    {"MAEZ_LLAMACPP_MODEL": "same-requested-label"},
                    clear=False,
                ),
                mock.patch.object(
                    il,
                    "served_model_alias",
                    return_value="new-served",
                    create=True,
                ),
            ):
                _cid, wrote = il.detect_and_record_startup(ledger)

            latest = ledger.latest()

        self.assertTrue(wrote)
        self.assertEqual(latest["event_type"], "brain_swap")
        self.assertEqual(latest["fingerprint"]["base_model"], "new-served")
        self.assertIn("base_model old-served -> new-served", latest["reason"])

    def test_dream_state_model_constant(self):
        """core/evolution/dream_state.py::MODEL must now be sourced
        from core.model_config, not a literal string."""
        src = (_REPO / "core" / "evolution" / "dream_state.py").read_text()
        self.assertNotIn('MODEL = "gemma4:26b"', src)
        self.assertIn(
            "from core.model_config import PRIMARY_MODEL as MODEL",
            src,
            "dream_state.MODEL must alias PRIMARY_MODEL from the "
            "current model config — not a hardcoded string.",
        )

    def test_continuity_chat_uses_primary(self):
        src = (_REPO / "core" / "memory" / "continuity.py").read_text()
        self.assertNotIn("model='gemma4:26b'", src)
        self.assertNotIn('model="gemma4:26b"', src)
        self.assertIn("_PRIMARY_MODEL", src,
                      "continuity must route its chat() call through "
                      "_PRIMARY_MODEL.")

    def test_conversation_controller_default_param(self):
        src = (_REPO / "core" / "brain" / "conversation_controller.py").read_text()
        self.assertNotIn('model: str = "gemma4:26b"', src)
        self.assertIn("_DEFAULT_MODEL", src,
                      "conversation_controller default must derive "
                      "from PRIMARY_MODEL.")

    def test_llm_client_generate_default_param(self):
        src = (_REPO / "core" / "routing" / "llm_client.py").read_text()
        # The former default `model: str = 'gemma4:26b'` is gone; the
        # new shape is `model: Optional[str] = None` with a runtime
        # fallback to _PRIMARY_MODEL inside the function body.
        self.assertNotIn("model: str = 'gemma4:26b'", src)
        self.assertIn("model = _PRIMARY_MODEL", src,
                      "llm_client.generate must fall back to "
                      "_PRIMARY_MODEL when the caller doesn't pass "
                      "model=.")


class VisionSurfacesClaimNothingActive(unittest.TestCase):
    """cli/web status surfaces must not list llama-server-vision as active."""

    def test_cli_status_drops_vision_service(self):
        src = (_REPO / "cli" / "maez_chat.py").read_text()
        # Find the svcs = [...] block after the svc_active helper
        svcs_start = src.find("svcs = [")
        self.assertNotEqual(svcs_start, -1)
        svcs_end = src.find("]", svcs_start)
        block = src[svcs_start:svcs_end]
        self.assertNotIn("llama-server-vision", block,
                         "CLI /status must not list the retired "
                         "llama-server-vision service.")

    def test_web_journal_drops_vision_service(self):
        src = (_REPO / "skills" / "web_interface.py").read_text()
        journal_start = src.find("JOURNAL_SERVICES = (")
        self.assertNotEqual(journal_start, -1)
        journal_end = src.find(")", journal_start)
        block = src[journal_start:journal_end]
        self.assertNotIn("llama-server-vision", block,
                         "web JOURNAL_SERVICES must not list the "
                         "retired llama-server-vision service.")


class LegacyLabelsKeptForCovenantProtection(unittest.TestCase):
    """policies.yaml + action_engine.py KEEP the llama-server-vision
    label as a defensive covenant guard, not because the service is
    active. Assert the labels are tagged as legacy-for-protection."""

    def test_policies_yaml_has_legacy_comment(self):
        src = (_REPO / "config" / "policies.yaml").read_text()
        # "legacy label" appears in a comment near the protected
        # lists after this commit.
        self.assertIn("legacy", src.lower(),
                      "policies.yaml must mark retained stale labels "
                      "as 'legacy' so future reviewers understand "
                      "they're covenant protection, not active claims.")

    def test_action_engine_has_legacy_comment(self):
        """Anchor on the actual list entry (not the first textual
        mention — my own explainer comment uses the same quoted
        literal). Scan a wider window around ALL occurrences and
        require at least one is within 500 chars of a legacy/retired
        note."""
        src = (_REPO / "core" / "actions" / "action_engine.py").read_text()
        literal = '"llama-server-vision"'
        positions = []
        i = 0
        while True:
            j = src.find(literal, i)
            if j == -1:
                break
            positions.append(j)
            i = j + 1
        self.assertTrue(positions,
                        "action_engine must reference "
                        "llama-server-vision at all (protection gate).")
        ok = False
        for p in positions:
            window = src[max(0, p - 500):p + 500].lower()
            if "legacy" in window or "retired" in window:
                ok = True
                break
        self.assertTrue(
            ok,
            "At least one action_engine reference to llama-server-"
            "vision must be tagged as legacy/retired in a nearby "
            "comment so the stale name is explicitly kept as "
            "forward-compatible protection.",
        )


if __name__ == "__main__":
    unittest.main()
