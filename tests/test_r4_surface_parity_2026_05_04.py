# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for R4 — surface parity.

The 2026-05-04 symphony audit (S3 BLOCKERs B1/B2/B4, F2/F4, top-10
#2) found three surfaces emit Maez replies WITHOUT routing through
the honesty audit gate or with hand-coded identity strings that
diverge from the canonical Maez:

  - skills/telegram_public.py — LLM-generated reply at line 349
    sent without self_claim_audit / audit_assistant_text
  - skills/web_interface.py — /chat identity short-circuit at
    line 2625/2632 returns hand-written replies that bypass the
    main-path audit_assistant_text call (Codex-narrowed to
    early-return paths after retracting the broader F3)
  - core/infra/fast_prompt_builder.py — COMPACT_IDENTITY claims
    "perceive owner's environment via background sensors"
    unconditionally even when vision is retired (S1 F18)

R4 brings the load-bearing reply paths under the same audit rail
the daemon + Telegram-owner + CLI surfaces use, and makes the
fast-lane identity body-truth-aware.

Contract enforced by these tests:
- skills/telegram_public.py routes its LLM-generated reply through
  self_claim_audit (or the equivalent audit_assistant_text helper)
  before update.message.reply_text(reply).
- skills/web_interface.py /chat identity short-circuit calls
  audit_assistant_text(identity_reply, surface="web") before the
  return jsonify(...).
- core/infra/fast_prompt_builder.py COMPACT_IDENTITY is built from
  body_capabilities (or core.identity helpers) so the sensor claim
  reflects runtime truth — vision-off, calendar-broken, etc. show
  in the prompt rather than being asserted unconditionally.
- daemon/maez_daemon.py recent_action_context exception path is
  WARNING (not DEBUG), per Codex 2026-05-04 R3.5 hardening note.

Tests are source-pinned where the integration crosses module
boundaries (the surfaces themselves bring up live network /
LLM clients, not unit-testable in this slice).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class R4_TelegramPublicAudits(unittest.TestCase):
    """REGRESSION GUARD: telegram_public must route its LLM-
    generated reply through the self-claim audit before sending."""

    def test_telegram_public_imports_audit(self):
        path = REPO / "skills" / "telegram_public.py"
        src = path.read_text()
        self.assertTrue(
            "self_claim_audit" in src or "audit_assistant_text" in src,
            "telegram_public.py must import the self-claim audit "
            "helper to gate replies — S3 BLOCKER B2 from the "
            "symphony audit",
        )

    def test_telegram_public_audits_reply_before_send(self):
        """Source-pin: audit must precede the public reply send.

        The Telegram chokepoint slice routes public replies through
        `_public_reply_text(update, reply)` instead of direct
        `update.message.reply_text(reply)`. The R4 invariant remains:
        audit the post-LLM reply before the send boundary.
        """
        path = REPO / "skills" / "telegram_public.py"
        src = path.read_text()
        # Find the LLM-reply assembly + send block. The pattern we
        # require: audit_assistant_text or self_claim_audit.audit
        # appears in the same handler that calls reply_text(reply).
        # We assert the audit helper name is present AND a call to
        # it appears before the post-LLM reply_text line.
        import re
        send_match = re.search(r"await _public_reply_text\(update,\s*reply\)", src)
        self.assertIsNotNone(
            send_match,
            "expected the LLM-reply send shape "
            "`await _public_reply_text(update, reply)` to exist "
            "in telegram_public.py",
        )
        send_idx = send_match.start()
        before_send = src[:send_idx]
        self.assertTrue(
            "audit_assistant_text" in before_send
            or "self_claim_audit" in before_send,
            "audit gate must be called BEFORE reply_text(reply); "
            "no audit reference precedes the LLM-reply send",
        )


class R4_WebChatIdentityShortCircuitAudits(unittest.TestCase):
    """REGRESSION GUARD: /chat identity short-circuit early-return
    must route through audit_assistant_text. Codex narrowed F3 from
    BLOCKER (the main /chat path IS audited) to MAJOR (early-return
    paths bypass the audit) — this closes the narrowed finding."""

    def test_identity_short_circuit_audits_before_return(self):
        path = REPO / "skills" / "web_interface.py"
        src = path.read_text()
        # Locate the identity short-circuit block — it ends with
        # `return jsonify({"reply": identity_reply, ...})`.
        import re
        m = re.search(
            r"return jsonify\(\{\s*\"reply\":\s*identity_reply",
            src,
        )
        self.assertIsNotNone(
            m,
            "expected the identity-short-circuit return shape "
            "in web_interface.py",
        )
        # The audit call must appear BEFORE this return inside the
        # same enclosing function. We don't AST-walk; we just check
        # for an audit_assistant_text call within the 1500 chars
        # preceding the return (the short-circuit block is small).
        return_idx = m.start()
        slice_before = src[max(0, return_idx - 1500): return_idx]
        self.assertIn(
            "audit_assistant_text", slice_before,
            "/chat identity short-circuit must call "
            "audit_assistant_text on identity_reply before the "
            "return jsonify(...) — the early-return path was "
            "previously bypassing the main-path audit gate",
        )


class R4_FastPromptBodyTruthAware(unittest.TestCase):
    """REGRESSION GUARD: fast_prompt_builder.COMPACT_IDENTITY must
    be derived from body_capabilities (or core.identity helpers)
    rather than a hand-coded constant claiming unconditional
    perception. S1 F18: vision-off / calendar-broken state must be
    reflected in the fast-lane identity, not asserted away."""

    def test_compact_identity_consults_body_capabilities(self):
        path = REPO / "core" / "infra" / "fast_prompt_builder.py"
        src = path.read_text()
        # Either compact identity is now a function that consults
        # body_capabilities, OR the module imports body_capabilities
        # to render the identity dynamically. Either path closes the
        # finding.
        self.assertTrue(
            "body_capabilities" in src,
            "core/infra/fast_prompt_builder.py must reference "
            "body_capabilities so the COMPACT_IDENTITY adapts to "
            "runtime sensor reach (vision retired, calendar broken, "
            "etc.) instead of asserting unconditional perception",
        )

    def test_compact_identity_no_unconditional_sensor_claim(self):
        """Source-pin: the literal phrase 'perceive the owner's
        environment via background sensors' (which was the S1-F18
        unconditional claim) must NOT remain in the file as a
        hardcoded constant. Either it's been gated behind a runtime
        check, or rephrased."""
        path = REPO / "core" / "infra" / "fast_prompt_builder.py"
        src = path.read_text()
        # We allow the phrase to appear inside a function body where
        # it's conditionally rendered, but NOT as a module-level
        # constant string. The hardcoded COMPACT_IDENTITY assignment
        # must no longer contain the unconditional sensor sentence.
        import re
        const_match = re.search(
            r"COMPACT_IDENTITY\s*=\s*\(\s*[^)]*\)",
            src, re.DOTALL,
        )
        if const_match:
            const_body = const_match.group(0)
            self.assertNotIn(
                "perceive the owner's environment via background sensors",
                const_body,
                "S1 F18: the unconditional sensor claim must not "
                "remain in the COMPACT_IDENTITY constant — it must "
                "be conditionally rendered based on body_capabilities",
            )


class R4_IdentityReplyNoFalseBodyClaim(unittest.TestCase):
    """REGRESSION GUARD (Codex 2026-05-04 review of d99602e):
    skills/web_interface.py /chat identity short-circuit must NOT
    contain the unconditional 'perceive his world' claim.

    The audit wrapper is INSUFFICIENT for hand-written false
    claims because audit_assistant_text falls open under
    judge_unavailable / timeout, returning rewritten=False and
    leaving the false claim intact. Verified empirically. The
    structural fix is to never make the false claim in the source
    string itself.
    """

    def test_perceive_his_world_phrase_removed_from_source(self):
        path = REPO / "skills" / "web_interface.py"
        src = path.read_text()
        self.assertNotIn(
            "perceive his world",
            src,
            "skills/web_interface.py must NOT contain the literal "
            "'perceive his world' phrase — it is a false body "
            "claim under the daemon's actual runtime (DISPLAY=:1, "
            "X session unreachable). Audit wrapper does not save "
            "this; structural fix only.",
        )

    def test_render_identity_reply_under_daemon_env_omits_perception_claim(self):
        """Under daemon-equivalent env (DISPLAY=:1, X unreachable),
        the rendered identity_reply must NOT claim desktop / world
        / vision perception. Body-truth-aware rendering is the
        contract: only signals actually reachable from the calling
        process appear in the reply."""
        from skills.web_interface import _render_identity_reply
        from core.infra import body_capabilities as bc
        from unittest import mock

        # Simulate the daemon's environment: desktop NOT reachable,
        # brain reachable.
        fake_snap = {
            "binaries": {
                "wmctrl": False, "xdotool": True, "dbus-send": True,
                "git": True, "curl": True, "sudo": True, "apt-get": True,
            },
            "env": {
                "DISPLAY": ":1",
                "XAUTHORITY": "/run/user/1000/gdm/Xauthority",
                "DBUS_SESSION_BUS_ADDRESS": None,
                "WAYLAND_DISPLAY": None,
            },
            "services": {
                "brain_8080": True, "ollama_11434": False,
                "daemon_11435": True, "daemon_ws_11436": True,
                "web_11437": True, "proxy_11438": True,
            },
            "desktop_session_reachable": False,  # the load-bearing fact
            "sudo_passwordless": True,
            "probed_at": 0.0,
        }
        with mock.patch.object(bc, "body_capabilities",
                               return_value=fake_snap):
            reply_linked = _render_identity_reply(
                display="Friend", linked_user=True,
            )
            reply_guest = _render_identity_reply(
                display="Friend", linked_user=False,
            )
        for reply, label in [
            (reply_linked, "linked"),
            (reply_guest, "guest"),
        ]:
            self.assertNotIn(
                "perceive", reply.lower(),
                f"{label} identity_reply must not claim perception "
                f"under daemon env (desktop unreachable); got {reply!r}",
            )
            self.assertNotIn(
                "desktop", reply.lower(),
                f"{label} identity_reply must not name desktop "
                f"signal when desktop_session_reachable=False",
            )
            self.assertNotIn(
                "vision", reply.lower(),
                f"{label} identity_reply must not claim vision",
            )
            self.assertNotIn(
                "world", reply.lower(),
                f"{label} identity_reply must not claim 'perceive "
                f"his world'-class language",
            )

    def test_render_identity_reply_includes_signals_when_reachable(self):
        """When desktop IS reachable + brain reachable, the
        sensor clause may name those signals — but only those, not
        a blanket 'world' claim."""
        from skills.web_interface import _render_identity_reply
        from core.infra import body_capabilities as bc
        from unittest import mock

        fake_snap = {
            "binaries": {},
            "env": {
                "DISPLAY": ":0",
                "XAUTHORITY": "/run/user/1000/.Xauthority",
                "DBUS_SESSION_BUS_ADDRESS": None,
                "WAYLAND_DISPLAY": None,
            },
            "services": {"brain_8080": True},
            "desktop_session_reachable": True,
            "sudo_passwordless": True,
            "probed_at": 0.0,
        }
        with mock.patch.object(bc, "body_capabilities",
                               return_value=fake_snap):
            reply = _render_identity_reply(
                display="Owner", linked_user=True,
            )
        self.assertIn(
            "desktop", reply.lower(),
            "when desktop is actually reachable, the sensor "
            "clause should name it",
        )
        # Still no broad-perception claim — names a specific signal.
        self.assertNotIn(
            "world", reply.lower(),
        )


class R4_R35HardeningWarning(unittest.TestCase):
    """REGRESSION GUARD (Codex R3.5 review note 2026-05-04): the
    daemon's recent_action_context exception path must log at
    WARNING, not DEBUG. Silent failure of a grounding rail erases
    its purpose. Mirrors the cycle recall capture pattern in the
    same file (see commented `warning not debug` rationale)."""

    def test_recent_action_context_exception_logs_warning(self):
        path = REPO / "daemon" / "maez_daemon.py"
        src = path.read_text()
        # Locate the recent_action_context try/except block.
        import re
        m = re.search(
            r"from core\.decision import recent_action_context.*?except\s+Exception",
            src, re.DOTALL,
        )
        self.assertIsNotNone(
            m,
            "expected the recent_action_context try/except shape "
            "in daemon/maez_daemon.py",
        )
        block_start = m.start()
        # Look for the logger call within ~500 chars after the except
        # line.
        block = src[block_start: block_start + 1500]
        # Must contain logger.warning, not logger.debug as the
        # ONLY logger call inside this except block.
        self.assertIn(
            "logger.warning", block,
            "recent_action_context exception path must log at "
            "WARNING (not DEBUG) — the grounding rail's silent "
            "failure mode is what produced the 7-day F1 outage",
        )


if __name__ == "__main__":
    unittest.main()
