# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""A3 witness over the FROZEN BIRTH SURFACE.

Tests the surface that will exist at birth — NOT every historical
handler. The frozen surface (owner-ratified 2026-08-28,
docs/superpowers/specs/2026-08-28-birth-gate-FROZEN.md):

  conversation plane      natural language via run_inbound_turn
  core recovery plane     /login /status /cancel /pending /disk /git
                          /adapter_status /rollback_adapter
  privileged maintenance  /builder_enter /builder_exit

Everything else on the legacy command surface is OUTSIDE the birth
surface and must NOT become permanent ledger anatomy.

The operator plane is closed as a CLASS at the single registration
point, not hand-patched into ten implementations. No LLM is in the
path: these are substrate interactions recorded through the A3 seam.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from core.infra.sqlite_runtime import has_wal_reset_fix
from core.ledger import migrate, owner

_needs_writer = unittest.skipUnless(
    has_wal_reset_fix(), "needs LD_LIBRARY_PATH=vendor/sqlite/lib"
)
_PROBE_ROOT = "/var/tmp"


def _rows(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(
            "SELECT * FROM turns WHERE turn_id != 'genesis' ORDER BY chain_position")]
    finally:
        con.close()


class _Msg:
    def __init__(self, text):
        self.text = text


class _User:
    id = 1


class _Update:
    def __init__(self, text):
        self.message = _Msg(text)
        self.effective_user = _User()
        self.effective_chat = None


class TheFrozenSurfaceIsExactlyWhatWasRuled(unittest.TestCase):
    def test_the_operator_set_is_the_ruled_ten(self):
        from skills.telegram_voice import BIRTH_ENABLED_OPERATOR_COMMANDS as S

        self.assertEqual(
            set(S),
            {"login", "status", "cancel", "pending", "disk", "git",
             "adapter_status", "rollback_adapter",
             "builder_enter", "builder_exit"},
            "the birth-enabled operator surface CHANGED. It was frozen by "
            "owner ruling on measured evidence; widening it silently adds "
            "permanent ledger anatomy for a surface meant to retire.",
        )

    def test_every_command_registration_passes_through_the_gate(self):
        """Structural: no handler may be registered un-gated.

        This is the class closure. A future command wired directly to
        add_handler would bypass operator recording entirely.
        """
        import re

        src = (Path(__file__).resolve().parent.parent
               / "skills" / "telegram_voice.py").read_text()
        raw = re.findall(r'CommandHandler\("([a-z_]+)",\s*self\.', src)
        self.assertEqual(
            raw, [],
            f"{len(raw)} command(s) registered WITHOUT the operator gate: "
            f"{raw}. Every CommandHandler must go through "
            "_maybe_operator_recorded so the frozen set decides.",
        )

    def test_commands_outside_the_surface_are_not_wrapped(self):
        """Out-of-surface commands must stay untouched, not become anatomy."""
        from skills import telegram_voice as tv

        sentinel = object()
        self.assertIs(
            tv._maybe_operator_recorded("apply_dream", sentinel), sentinel,
            "a command OUTSIDE the birth surface was wrapped for "
            "recording — it is meant to migrate or retire",
        )
        self.assertIsNot(
            tv._maybe_operator_recorded("status", sentinel), sentinel,
            "a birth-enabled command was NOT wrapped",
        )


class NoUnadjudicatedBirthEnabledSurface(unittest.TestCase):
    """THE STRUCTURAL GUARD.

    A birth-enabled owner-facing surface may not be introduced without
    falling into exactly one of three adjudicated classes:

      1. LIVED-RECORD — it routes through ``run_inbound_turn`` and
         inherits the conversation plane's closures;
      2. OPERATOR-RECORDED — it is in the frozen operator set and is
         wrapped at the registration gate;
      3. OWNER-RULED NON-LIVED — explicitly excluded from the birth
         surface by ruling, so it migrates or retires and must never
         become permanent ledger anatomy.

    The guard is two-sided: an unadjudicated surface fails, and so does
    a phantom entry naming something that no longer exists.
    """

    #: Class 1 — inherits the conversation plane.
    LIVED_RECORD_ENTRYPOINTS = {
        "daemon/inbound_core.py::run_inbound_turn",
    }

    #: Class 3 — ruled OUT of the birth surface (migrate or retire).
    #: These are the legacy commands the owner ruled outside the frozen
    #: surface on 2026-08-28. Being on this list is a commitment that
    #: they do NOT survive birth as commands.
    OWNER_RULED_NON_LIVED = {
        "approve", "promote", "trust", "approve_cleanup",
        "approve_evolution", "reject_evolution", "help", "analyze",
        "proposals", "show", "apply", "reject", "dreams", "apply_dream",
        "reject_dream", "edit_proposals", "show_edit", "apply_edit",
        "reject_edit", "train_proposals", "show_train", "approve_train",
        "reject_train", "evolution_log",
    }

    def _registered_commands(self) -> set[str]:
        import re

        src = (Path(__file__).resolve().parent.parent
               / "skills" / "telegram_voice.py").read_text()
        return set(re.findall(r'CommandHandler\("([a-z_]+)"', src))

    def test_every_registered_command_is_adjudicated(self):
        from skills.telegram_voice import BIRTH_ENABLED_OPERATOR_COMMANDS

        registered = self._registered_commands()
        adjudicated = set(BIRTH_ENABLED_OPERATOR_COMMANDS) | self.OWNER_RULED_NON_LIVED
        missing = registered - adjudicated
        self.assertFalse(
            missing,
            f"UNADJUDICATED OWNER-FACING SURFACE: {sorted(missing)}. A new "
            "command was registered without deciding whether it is "
            "birth-enabled (operator-recorded) or ruled out of the birth "
            "surface. Every owner-facing surface must be one of the three "
            "adjudicated classes before it can ship.",
        )

    def test_the_adjudication_lists_have_no_phantoms(self):
        """Two-sided: a name that no longer exists must not linger."""
        from skills.telegram_voice import BIRTH_ENABLED_OPERATOR_COMMANDS

        registered = self._registered_commands()
        phantom_ops = set(BIRTH_ENABLED_OPERATOR_COMMANDS) - registered
        self.assertFalse(
            phantom_ops,
            f"the frozen operator set names commands that are no longer "
            f"registered: {sorted(phantom_ops)}",
        )
        phantom_out = self.OWNER_RULED_NON_LIVED - registered
        self.assertFalse(
            phantom_out,
            f"the ruled-out list names commands that no longer exist: "
            f"{sorted(phantom_out)} — retirement happened without "
            "updating the adjudication",
        )

    def test_the_two_classes_do_not_overlap(self):
        from skills.telegram_voice import BIRTH_ENABLED_OPERATOR_COMMANDS

        overlap = set(BIRTH_ENABLED_OPERATOR_COMMANDS) & self.OWNER_RULED_NON_LIVED
        self.assertFalse(
            overlap,
            f"{sorted(overlap)} is both birth-enabled AND ruled out",
        )

    def test_the_conversation_plane_entrypoint_still_records(self):
        """Class 1 must keep inheriting the closures."""
        src = (Path(__file__).resolve().parent.parent
               / "daemon" / "inbound_core.py").read_text()
        for name in ("record_owner_message", "record_organ_event"):
            self.assertIn(
                name, src,
                f"{name} left run_inbound_turn — the conversation plane "
                "no longer inherits the lived-record boundary",
            )


class OperatorExchangesLeaveTypedEvidence(unittest.TestCase):
    @_needs_writer
    def test_an_operator_command_records_input_and_acknowledgement(self):
        from skills import telegram_voice as tv

        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            env = {
                "MAEZ_LEDGER_DB_PATH": str(db),
                "MAEZ_LEDGER_WRITES": "1",
                "MAEZ_PRIVATE_THOUGHTS_PATH": str(Path(tmp) / "pt.db"),
                "MAEZ_DATA": str(Path(tmp) / "data"),
            }

            async def _fake_handler(update, context):
                await tv._reply_text(update, "Maez Status\nCPU: 3%")

            wrapped = tv._maybe_operator_recorded("status", _fake_handler)

            with mock.patch.dict(os.environ, env, clear=False), \
                    mock.patch.object(tv, "call_telegram_method_async",
                                      mock.AsyncMock(return_value=None)):
                owner.claim_ownership(str(db))
                try:
                    asyncio.run(wrapped(_Update("/status"), None))
                finally:
                    owner._reset_for_tests()
            rows = _rows(db)

        self.assertEqual(
            len(rows), 2,
            f"the operator exchange must enter as owner input + "
            f"acknowledgement; got {[r['turn_kind'] for r in rows]}",
        )
        owner_row, ack = rows
        self.assertEqual(owner_row["turn_kind"], "user_message")
        self.assertEqual(owner_row["raw_text"], "/status")
        self.assertEqual(ack["turn_kind"], "system_event")
        self.assertEqual(ack["event_origin"], "operator_command:status")
        self.assertIn("CPU: 3%", ack["raw_text"])
        self.assertEqual(
            ack["parent_turn_id"], owner_row["turn_id"],
            "the acknowledgement must hang off the owner's input",
        )

    @_needs_writer
    def test_the_command_still_runs_when_recording_fails(self):
        """Recovery posture: biography must never gate the action."""
        from skills import telegram_voice as tv

        ran = []

        async def _fake_handler(update, context):
            ran.append(True)
            await tv._reply_text(update, "rolled back")

        wrapped = tv._maybe_operator_recorded("rollback_adapter", _fake_handler)

        with mock.patch.object(
            tv, "_record_operator_exchange",
            side_effect=RuntimeError("ledger is wedged"),
        ), mock.patch.object(
            tv, "call_telegram_method_async", mock.AsyncMock(return_value=None)
        ):
            asyncio.run(wrapped(_Update("/rollback_adapter"), None))

        self.assertEqual(
            ran, [True],
            "a wedged ledger prevented a RECOVERY command from running — "
            "the action must proceed and the biography fail loudly",
        )

    def test_recording_never_touches_cognition(self):
        """Ruled: operator events are substrate, never LLM."""
        import ast
        import inspect

        from skills import telegram_voice as tv

        src = inspect.getsource(tv._record_operator_exchange)
        called = {
            getattr(n.func, "attr", getattr(n.func, "id", ""))
            for n in ast.walk(ast.parse(src.strip()))
            if isinstance(n, ast.Call)
        }
        forbidden = {"chat", "generate", "generate_response", "run_brain_loop",
                     "synthesize", "audit"}
        self.assertFalse(
            called & forbidden,
            f"operator recording reached cognition via "
            f"{sorted(called & forbidden)}",
        )

    @_needs_writer
    def test_flag_dormant_leaves_zero_residue(self):
        from skills import telegram_voice as tv

        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            before = db.stat().st_size

            async def _fake_handler(update, context):
                await tv._reply_text(update, "ok")

            wrapped = tv._maybe_operator_recorded("disk", _fake_handler)
            env = {
                "MAEZ_LEDGER_DB_PATH": str(db),
                "MAEZ_PRIVATE_THOUGHTS_PATH": str(Path(tmp) / "pt.db"),
                "MAEZ_DATA": str(Path(tmp) / "data"),
            }
            with mock.patch.dict(os.environ, env, clear=False), \
                    mock.patch.object(tv, "call_telegram_method_async",
                                      mock.AsyncMock(return_value=None)):
                os.environ.pop("MAEZ_LEDGER_WRITES", None)
                asyncio.run(wrapped(_Update("/disk"), None))

            self.assertEqual(db.stat().st_size, before, "db bytes moved")
            self.assertFalse(
                (Path(tmp) / "ledger_spool").exists()
                or list(Path(tmp).glob("*.deadletter.*")),
                "a dormant operator command left residue",
            )


if __name__ == "__main__":
    unittest.main()
