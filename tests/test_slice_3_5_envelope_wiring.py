# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Slice 3.5 envelope wiring guards.

Slice 3.5's birth-criterion scope is deliberately narrower than "every
audit call in the repository": wire the five deferred daemon speech/audit
paths plus CLI and web /chat. These tests are source-level because the
live daemon/web/CLI entry points are not safe to import/run on unstable
hardware during the slice.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


_REPO = Path("/home/rohit/maez")


def _read(rel: str) -> str:
    return (_REPO / rel).read_text()


def _method_body(src: str, name: str) -> str:
    start = src.find(f"def {name}")
    if start == -1:
        start = src.find(f"async def {name}")
    if start == -1:
        raise AssertionError(f"{name} not found")
    m = re.search(r"\n    (?:async\s+)?def ", src[start + 20 :])
    end = start + 20 + m.start() if m else len(src)
    return src[start:end]


class DaemonSlice35WiringTests(unittest.TestCase):
    def test_five_deferred_daemon_surfaces_receive_envelope(self):
        src = _read("daemon/maez_daemon.py")
        required = {
            "daemon_proactive": "_check_proactive_opinion",
            "morning_briefing": "_send_morning_briefing",
            "nightly_journal": "_write_journal_entry",
            "developmental_heartbeat": "_write_developmental_heartbeat",
            "daemon_cycle": "_loop",
            "daemon_cycle_retry": "_loop",
        }
        for surface, method in required.items():
            with self.subTest(surface=surface):
                body = _method_body(src, method)
                surface_pos = body.find(f'surface="{surface}"')
                self.assertGreater(surface_pos, 0, f"{surface} call not found")
                call_window = body[surface_pos : surface_pos + 2500]
                self.assertIn(
                    "evidence_envelope=",
                    call_window,
                    f"{surface} must pass the same envelope used for generation "
                    "into the audit call.",
                )

    def test_daemon_cycle_prompt_injects_envelope_and_coordinates_recall_cap(self):
        body = _method_body(_read("daemon/maez_daemon.py"), "_reason")
        self.assertIn(
            "resolve_recall_cap_chars",
            body,
            "_reason recall cap must use the shared resolver when an "
            "envelope block is injected into the cycle prompt.",
        )
        self.assertIn("build_envelope", body)
        self.assertIn("render_envelope_for_prompt", body)
        self.assertRegex(
            body,
            r"prompt\s*\+=\s*_cycle_envelope_block\s*\+\s*\"\\n\\n\"",
            "cycle envelope block must be injected into the prompt before "
            "generation, not audit-only after the fact.",
        )

    def test_daemon_cycle_camera_presence_is_not_an_envelope_signal(self):
        src = _read("daemon/maez_daemon.py")
        body = _method_body(src, "_reason")
        self.assertNotIn("presence", body.lower())
        self.assertNotIn("[PRESENCE]", body)
        self.assertNotIn("calendar — live", body)
        self.assertIn("Calendar v1 not enabled", body)
        loop_body = _method_body(src, "_loop")
        audit_idx = loop_body.find('surface="daemon_cycle"')
        self.assertGreater(audit_idx, 0)
        audit_window = loop_body[audit_idx - 1500 : audit_idx + 1500]
        self.assertNotIn("presence", audit_window.lower())
        self.assertNotIn("[PRESENCE]", audit_window)
        self.assertIn('_cycle_signals_absent.append("calendar")', loop_body)


class WebSlice35WiringTests(unittest.TestCase):
    def test_owner_bridge_chat_uses_envelope_prompt_block_and_recall_cap(self):
        body = _method_body(_read("skills/web_interface.py"), "chat")
        self.assertIn("resolve_recall_cap_chars", body)
        self.assertNotIn("max_chars=60_000", body)
        self.assertIn("build_envelope", body)
        self.assertIn("render_envelope_for_prompt", body)
        self.assertIn("_evidence_envelope", body)
        self.assertIn('messages_list.append({"role": "system", "content": _envelope_block})', body)
        self.assertIn(
            'messages_list.insert(-1, {"role": "system", "content": _envelope_block})', body
        )
        self.assertIn('"name": "web_tool_loop"', body)
        self.assertIn('"summary": jarvis_transcript_web', body)
        self.assertIn(
            'simple_msgs.insert(-1, {"role": "system", "content": _envelope_block})', body
        )
        self.assertIn("system_parts =", body)
        self.assertIn('system_prompt_for_api = "\\n\\n".join(system_parts)', body)
        audit_idx = body.rfind("reply = audit_assistant_text(")
        self.assertGreater(audit_idx, 0)
        self.assertIn("evidence_envelope=_evidence_envelope", body[audit_idx : audit_idx + 250])

    def test_daemon_render_failure_nulls_envelope_before_audit(self):
        src = _read("daemon/maez_daemon.py")
        for surface in (
            "daemon_proactive",
            "morning_briefing",
            "nightly_journal",
            "developmental_heartbeat",
            "daemon_cycle",
        ):
            with self.subTest(surface=surface):
                idx = src.find(f"render failed for {surface}")
                self.assertGreater(idx, 0)
                window = src[idx : idx + 350]
                if surface == "daemon_cycle":
                    self.assertIn("_cycle_evidence_envelope = None", window)
                else:
                    self.assertIn("_evidence_envelope = None", window)

    def test_public_web_envelope_does_not_use_owner_ledger_self_history(self):
        body = _method_body(_read("skills/web_interface.py"), "chat")
        self.assertIn(
            "ledger_db_path=None",
            body,
            "public/guest web envelope construction must not read the "
            "owner ledger and leak owner self-history into non-owner chat.",
        )
        self.assertIn(
            '_web_signals_absent = ["owner private ledger self-history"]',
            body,
            "all non-owner web turns, including linked/trusted users, must "
            "tell the envelope/audit that owner ledger self-history is absent.",
        )

    def test_web_audit_preserves_legacy_signals_when_envelope_is_absent(self):
        body = _method_body(_read("skills/web_interface.py"), "chat")
        audit_idx = body.rfind("reply = audit_assistant_text(")
        self.assertGreater(audit_idx, 0)
        audit_window = body[audit_idx : audit_idx + 350]
        self.assertIn("signals_present=_web_signals_present", audit_window)
        self.assertIn("signals_absent=_web_signals_absent", audit_window)
        self.assertIn("evidence_envelope=_evidence_envelope", audit_window)


class CliSlice35WiringTests(unittest.TestCase):
    def test_cli_direct_audit_builds_and_forwards_envelope(self):
        src = _read("cli/maez_chat.py")
        self.assertIn("build_envelope", src)
        self.assertIn("render_envelope_for_prompt", src)
        self.assertIn("_evidence_envelope", src)
        audit_idx = src.find('surface="cli"')
        self.assertGreater(audit_idx, 0)
        self.assertIn("evidence_envelope=_evidence_envelope", src[audit_idx : audit_idx + 350])
        self.assertIn("in_tool_continuation=(iteration > 0)", src[audit_idx : audit_idx + 350])


class TelegramPublicSlice35WiringTests(unittest.TestCase):
    def test_public_telegram_uses_public_envelope_without_owner_ledger(self):
        src = _read("skills/telegram_public.py")
        self.assertIn("build_envelope", src)
        self.assertIn("render_envelope_for_prompt", src)
        self.assertIn("ledger_db_path=None", src)
        self.assertIn("owner private ledger self-history", src)
        self.assertIn("evidence_envelope=_evidence_envelope", src)


class Slice35ScopeAllowlistTests(unittest.TestCase):
    def test_deferred_out_of_scope_audit_surfaces_are_named(self):
        """This is the safety valve against false confidence.

        If a future sweep finds an unwired audit surface, it should be
        added either to Slice 3.5 wiring or this explicit allowlist with
        a reason. No silent "we wired five, therefore all are covered".
        """
        src = _read("tests/test_slice_3_5_envelope_wiring.py")
        for surface in (
            "github_publish_commit_message",
            "self_mod_dialog",
            "telegram_dialog",
            "action_baseline_update",
            "dream_state",
            "training_proposal",
        ):
            self.assertIn(surface, src)


if __name__ == "__main__":
    unittest.main()
