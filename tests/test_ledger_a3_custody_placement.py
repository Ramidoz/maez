# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""A3 custody placement — the TWENTY-FOURTH round's ruling, pinned.

The twenty-third round found a phantom-row window in landed A3 code and
named two questions for this slice: WHICH BYTES provenance binds to when
recorded and delivered text diverge, and WHERE custody sits. The
twenty-fourth round put both to three seats. All three returned the same
answer and the same overall verdict:

  Q1 bytes      -> PRODUCED   (3-0)
  Q2 placement  -> DO NOT MOVE the record (3-0)
  Q3 class      -> NAME it; the class sweep is an OWNER boundary (3-0)
  Q4 structure  -> the CLAIM is already build-enforced; the PLACEMENT is
                   AST-pinnable; the OUTCOME is irreducibly runtime (3-0)
  overall       -> BLOCK a custody-RELOCATION slice (3-0)

So this file changes NO production byte. It pins the ruling, because the
ruling's whole content is "the code stays where it is, and here is why a
future slice must not move it".

WHY NOT MOVE (executed, in the round):

  * The cockpit is a SECOND caller of the same closure and it has NO
    window: daemon/maez_daemon.py:13257-13261 calls run_inbound_turn and
    returns jsonify({"reply": reply}) without ever entering
    _process_message_background. Moving the seam into the surface would
    UNWIRE the cockpit S4 and proposal mouths.
  * Recording after the discard converts a VISIBLE phantom row into a
    SILENT omission — the one sin this arc ruled against ("omission
    never silent").
  * No placement can reach the send-failure or transport-exception
    classes: those are outcomes, unknowable when the row is written.
    They belong to A4, whose egress substrate is designed and
    unimplemented.

WHY PRODUCED BYTES: "delivered" is not a byte-string at all. Executed —
a reply naming an on-disk image has the path STRIPPED FROM THE TEXT and
the FILE UPLOADED out of band, so egress is a tuple (text, images,
media, local_files). A row bound to "delivered text" would both omit
content the owner did receive and contain text authored by
platform_base's regexes. "Exact bytes, never content-light" means do not
summarise or hash AT THE SEAM; it was never a claim about the wire.

Note the two rows answer differently, and structurally so: the owner's
`.strip()` happens UPSTREAM of the guard (a HEARING transform), while
extract_media happens DOWNSTREAM (a SPEAKING transform). Both rows bind
to the bytes at the seam; the seam sits between them.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import os
import re
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from core.infra.sqlite_runtime import has_wal_reset_fix
from core.ledger import migrate, owner

_needs_enabled_writer = unittest.skipUnless(
    has_wal_reset_fix(),
    "an enabled ledger writer requires SQLite >= 3.51.3 "
    "(run with LD_LIBRARY_PATH=vendor/sqlite/lib)",
)

_PROBE_ROOT = "/var/tmp"
_REPO = Path(__file__).resolve().parent.parent

#: A proposal-shaped reply that PROVABLY diverges through the real
#: surface chain. The markdown image is extracted and sent as a separate
#: attachment, so the owner receives BOTH less text than this and one
#: thing this string cannot represent. Constructed, never sampled: the
#: point is that the binding must hold for a diverging reply, and a
#: reply that happens not to diverge would prove nothing.
_DIVERGING_PROPOSAL_REPLY = (
    "Proposal #7 - dream insight:\n"
    "I noticed this pattern ![trace](https://cdn.example/t.png) recurring."
)


def _rows(db: Path | str) -> list[dict]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        return [
            dict(r)
            for r in con.execute(
                "SELECT * FROM turns WHERE turn_id != 'genesis' "
                "ORDER BY chain_position"
            )
        ]
    finally:
        con.close()


def _surface_chain(response: str) -> str:
    """The REAL platform_base transform chain, in its real order.

    Mirrors _process_message_background between the handler's return and
    the transport invocation. Imported live, never re-implemented, so
    this helper cannot drift away from the code it models.
    """
    from skills.surface.platform_base import BasePlatformAdapter as _B

    _media, response = _B.extract_media(response)
    _images, text = _B.extract_images(response)
    text = text.replace("[[audio_as_voice]]", "").strip()
    text = re.sub(r"MEDIA:\s*\S+", "", text).strip()
    _local, text = _B.extract_local_files(text)
    return text


def _fn_source(path: Path, qualname: str) -> str:
    """Source of one construct, located by AST — never a line range."""
    tree = ast.parse(path.read_text())
    want = qualname.split(".")[-1]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == want:
            return ast.get_source_segment(path.read_text(), node) or ""
    raise AssertionError(f"{qualname} not found in {path}")


class ProducedBytesBindingTests(unittest.TestCase):
    """Q1, ruled 3-0: the organ row carries the bytes the organ produced."""

    def test_the_constructed_reply_really_does_diverge(self):
        """Positive control — without this the binding test is vacuous.

        A pin written against a reply that happens NOT to diverge proves
        nothing about which bytes were chosen. This asserts the witness
        is a real witness before the next test leans on it.
        """
        delivered = _surface_chain(_DIVERGING_PROPOSAL_REPLY)
        self.assertNotEqual(
            delivered, _DIVERGING_PROPOSAL_REPLY,
            "the witness reply no longer diverges through the real "
            "surface chain — replace it with one that does, or this "
            "file's binding test has quietly stopped testing anything",
        )
        self.assertLess(
            len(delivered), len(_DIVERGING_PROPOSAL_REPLY),
            "the divergence must be a real loss of text",
        )

    @_needs_enabled_writer
    def test_the_organ_row_carries_PRODUCED_not_delivered_bytes(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            answer, db = _run_proposal_turn(tmp, _DIVERGING_PROPOSAL_REPLY)
            rows = _rows(db)

        self.assertEqual(answer, _DIVERGING_PROPOSAL_REPLY, "the reply ships")
        organ = [r for r in rows if r["turn_kind"] == "system_event"]
        self.assertEqual(len(organ), 1, f"expected one organ row, got {rows}")
        row = organ[0]
        self.assertEqual(row["event_origin"], "proposal_interceptor")
        self.assertEqual(
            row["raw_text"], _DIVERGING_PROPOSAL_REPLY,
            "RULED 3-0 (twenty-fourth round): provenance binds to the "
            "bytes the interceptor PRODUCED. This row is a claim about "
            "what the organ said, not about what crossed the wire.",
        )
        self.assertNotEqual(
            row["raw_text"], _surface_chain(_DIVERGING_PROPOSAL_REPLY),
            "the row must NOT carry the post-transform text — that text "
            "is partly authored by platform_base's regexes, and binding "
            "to it would attribute the surface's edits to the organ",
        )


class RecordPlacementIsPinnedTests(unittest.TestCase):
    """Q2/Q4, ruled 3-0: placement does not move, and the pin is the
    mechanism that makes a future move a BUILD failure rather than a
    silent behavioural change."""

    def test_both_record_calls_live_inside_run_inbound_turn(self):
        src = _fn_source(_REPO / "daemon" / "inbound_core.py", "run_inbound_turn")
        for name in ("record_owner_message", "record_organ_event"):
            self.assertIn(
                f"{name}(", src,
                f"{name} left run_inbound_turn. It is the ONLY point "
                "common to BOTH production callers (the Surface V2 "
                "handler and the cockpit /message route); moving it "
                "unwires one of them.",
            )

    def test_the_surface_never_records(self):
        """The relocation guard, stated as the round ruled it.

        Moving the seam into _process_message_background would unwire
        the cockpit (which never enters it) and would turn a discarded
        generation into a silent omission.
        """
        surface = (_REPO / "skills" / "surface" / "platform_base.py").read_text()
        for name in ("record_owner_message", "record_organ_event"):
            self.assertNotIn(
                name, surface,
                "A3's recorder seam appeared in platform_base. The "
                "twenty-fourth round BLOCKED this 3-0: the cockpit "
                "caller never reaches this module, so recording here "
                "omits the cockpit's crisis and proposal mouths "
                "entirely, and recording after the discard converts a "
                "visible phantom row into a silent omission.",
            )

    def test_the_cockpit_caller_still_returns_run_inbound_turns_value(self):
        """Why the placement is load-bearing, pinned as a fact.

        If this stops holding, the 'only common point' argument that
        keeps the record inside run_inbound_turn has changed, and the
        placement question must be re-opened rather than assumed.
        """
        daemon_src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        self.assertIn(
            "reply = asyncio.run(run_inbound_turn(**descriptor))", daemon_src,
            "the cockpit /message route no longer drives run_inbound_turn "
            "directly — re-open the custody-placement question",
        )
        self.assertNotIn(
            "_process_message_background", daemon_src,
            "the cockpit path gained the surface's discard window; the "
            "round's kill shot against relocation rested on it NOT "
            "having one",
        )


class CustodyWindowInventoryTests(unittest.TestCase):
    """Q4's PIN: the window between record and wire cannot widen silently.

    This is NOT a tripwire scope change — widening the tripwire's
    DECLARED scopes is an owner call (scopes are declared, never
    derived). It is a narrow, purpose-built, two-sided inventory of the
    sites that can discard or rewrite a reply after the closure has
    already recorded it. A new discard or a new transform goes red and a
    human looks. It says nothing about completeness, and it must never
    be cited as evidence that the window is safe.
    """

    #: Machine-derived from _process_message_background: every assignment
    #: to a reply-carrying name between the handler's return and the
    #: transport invocation. Frozen by VALUE-SHAPE, not by line number.
    _FROZEN_WINDOW = (
        "response = await self._message_handler(event)",
        "response = None",
        "media_files, response = self.extract_media(response)",
        "images, text_content = self.extract_images(response)",
        "text_content = text_content.replace('[[audio_as_voice]]', '').strip()",
        "text_content = re.sub('MEDIA:\\\\s*\\\\S+', '', text_content).strip()",
        "local_files, text_content = self.extract_local_files(text_content)",
    )

    def _window(self) -> tuple[str, ...]:
        path = _REPO / "skills" / "surface" / "platform_base.py"
        tree = ast.parse(path.read_text())
        fn = next(
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == "_process_message_background"
        )
        names = {"response", "text_content"}
        out = []
        for node in ast.walk(fn):
            if not isinstance(node, ast.Assign):
                continue
            targets: list[str] = []
            for t in node.targets:
                if isinstance(t, ast.Name):
                    targets.append(t.id)
                elif isinstance(t, ast.Tuple):
                    targets += [e.id for e in t.elts if isinstance(e, ast.Name)]
            if set(targets) & names:
                out.append(
                    f"{', '.join(targets)} = {ast.unparse(node.value)}"
                )
        return tuple(out)

    def test_the_custody_window_is_exactly_what_was_ruled_over(self):
        self.assertEqual(
            self._window(), self._FROZEN_WINDOW,
            "the discard/transform window between the A3 closure's "
            "record and the transport invocation CHANGED. The "
            "twenty-fourth round ruled placement over exactly the sites "
            "frozen here (one discard, five transforms). A new site may "
            "be a new phantom-row lane or a new byte divergence — "
            "re-read the round before re-freezing this tuple.",
        )

    def test_the_window_still_contains_a_discard_after_the_handler_returns(self):
        """Two-sided: the window vanishing is also a finding.

        If the discard disappears, the phantom-row lane closed by other
        means and the round's harm analysis is stale.
        """
        self.assertIn(
            "response = None", self._window(),
            "the stale-response discard is gone — the phantom-row lane "
            "the twenty-fourth round ruled over no longer exists, and "
            "the ruling should be revisited rather than assumed",
        )


class TheSharperInstanceIsNamedTests(unittest.TestCase):
    """Q3, ruled 3-0: NAME the class rather than sweep it.

    The window is a property of the SURFACE, not of A3 — and its sharper
    instance is model_reply, which is NOT in this slice's scope and
    cannot be fixed inside it (delivery is A4, a recorded birth blocker
    whose obvious per-row shape the tenth round already forbade).

    These pins exist so the asymmetry cannot be quietly forgotten. They
    assert STRUCTURE, never a hardcoded sentence — a guard that greps
    for a literal goes stale into a lie.
    """

    def test_model_reply_is_read_back_as_self_history_and_system_event_is_not(self):
        from core.ledger.envelope_schema import SELF_HISTORY_KINDS

        self.assertIn(
            "model_reply", SELF_HISTORY_KINDS,
            "model_reply left SELF_HISTORY_KINDS — the asymmetry that "
            "makes it the SHARPER instance of the phantom window has "
            "changed; re-read the twenty-fourth round",
        )
        self.assertNotIn(
            "system_event", SELF_HISTORY_KINDS,
            "system_event entered SELF_HISTORY_KINDS. A3's organ rows "
            "are now read back as Maez's own utterances, which is "
            "EXACTLY the bound that made the phantom window tolerable. "
            "The custody-placement ruling must be re-opened.",
        )

    def test_the_model_reply_lane_records_upstream_of_the_same_window(self):
        """The class fact, verified structurally rather than recalled."""
        path = _REPO / "daemon" / "maez_daemon.py"
        tree = ast.parse(path.read_text())
        enclosing = None
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = ast.unparse(node)
            if "persist_model_reply(" in body and node.name == "handle_message":
                enclosing = node
                break
        self.assertIsNotNone(
            enclosing,
            "persist_model_reply is no longer inside handle_message. It "
            "was there that it sat UPSTREAM of the same surface discard "
            "window as A3's closures — the fact that made an A3-only "
            "placement fix the instance-not-class sin. Re-read Q3.",
        )


def _run_proposal_turn(tmp: str, reply: str) -> tuple:
    """Drive the REAL run_inbound_turn through its proposal closure."""
    import daemon.inbound_core as core_mod
    from tests.test_inbound_core_equivalence import (
        FakeDaemon,
        _make_inline_run_in_executor,
    )

    db = Path(tmp) / "ledger.db"
    migrate.run(str(db))
    env = {
        "MAEZ_LEDGER_DB_PATH": str(db),
        "MAEZ_LEDGER_WRITES": "1",
        # MAEZ_TEST_MODE does NOT sandbox PrivateThoughts — only this does.
        "MAEZ_PRIVATE_THOUGHTS_PATH": str(Path(tmp) / "pt.db"),
        "MAEZ_DATA": str(Path(tmp) / "data"),
    }
    trace: list = []
    fake_daemon = FakeDaemon(trace, pipe=None, memory=None)
    loop = asyncio.new_event_loop()
    inline_run, _ = _make_inline_run_in_executor(loop)

    async def _proposal(**_kw):
        return reply

    try:
        with mock.patch.dict(os.environ, env, clear=False):
            owner.claim_ownership(str(db))
            try:
                with mock.patch.object(
                    loop, "run_in_executor", inline_run
                ), mock.patch.object(
                    core_mod, "surface_parity_enabled", lambda: False
                ), mock.patch.object(
                    core_mod, "get_shared_executor", lambda: None
                ):
                    answer = loop.run_until_complete(
                        core_mod.run_inbound_turn(
                            daemon=fake_daemon,
                            text="show me proposal 7",
                            chat_id="222",
                            resolved_user_id="111",
                            reply_to_message_id=None,
                            context_note=None,
                            photo_analysis=None,
                            is_photo_turn=False,
                            owner_surface_label="telegram_surface",
                            user_id="rohit",
                            channel="telegram_text",
                            owner_auth_factory=lambda: None,
                            observe_turn_label="telegram_turn",
                            chat_history_turns=3,
                            action_engine="actions",
                            get_pipeline=lambda: None,
                            chat_history_provider=lambda limit: [],
                            try_proposal_intent=_proposal,
                            try_search_commitment_intent=None,
                            search_commitment_controller=lambda: None,
                            audit_surface_reply=lambda text, surface: text,
                            clean_exchange=lambda text: text,
                            send_intermediate=lambda text: None,
                            send_progress_receipt=lambda *a, **k: None,
                        )
                    )
            finally:
                owner._reset_for_tests()
    finally:
        loop.close()
    return answer, db


if __name__ == "__main__":
    unittest.main()
