# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""A3 per-path closures — the PROPOSAL interceptor mouth.

``run_inbound_turn`` returns the proposal interceptor's answer at
``daemon/inbound_core.py`` before the ledger seam, so today the whole
exchange (the owner's words AND Maez's answer) records nothing. This
closes it through the recorder seam, same shape as the S4 closures.

PROVENANCE CHECKED BEFORE ENCODING, per the twentieth round's warning
that not all interceptor text is canned: every proposal reply producer
was read and NONE calls a model. ``_try_surface_parity_proposal_intent``
and its three sub-handlers (dream, evolution, disambiguation) return
templates and f-strings over proposal ids/statuses, or render Maez's own
stored proposal content. ``{self_generated}`` is therefore the honest
stamp — a model_reply row here would be the eighteenth round's six
false claims, and a foreign-provenance stamp would be the reverse lie.

DELIBERATELY NOT CLOSED HERE — the SEARCH-COMMITMENT mouth, blocked by
a provenance export gap (see the module-level test below, which pins
the reason so a future closure cannot quietly guess a label).
"""

from __future__ import annotations

import asyncio
import json
import os
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

#: Benign owner text: must NOT trip the S4 guard, which returns earlier.
_OWNER_TEXT = "apply proposal 7 please"
_PROPOSAL_REPLY = "Proposal #7 is already applied - nothing to apply/reject."
_PROPOSAL_ORIGIN = "proposal_interceptor"


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


def _run_turn(tmp: str, *, writes_on: bool, proposal_reply):
    """Drive the REAL run_inbound_turn to its proposal interceptor."""
    import daemon.inbound_core as core_mod
    from tests.test_inbound_core_equivalence import (
        FakeDaemon,
        _make_inline_run_in_executor,
    )

    db = Path(tmp) / "ledger.db"
    migrate.run(str(db))
    env = {
        "MAEZ_LEDGER_DB_PATH": str(db),
        "MAEZ_PRIVATE_THOUGHTS_PATH": str(Path(tmp) / "pt.db"),
        "MAEZ_DATA": str(Path(tmp) / "data"),
    }
    if writes_on:
        env["MAEZ_LEDGER_WRITES"] = "1"

    async def _proposal(**kwargs):
        return proposal_reply

    async def _no_search(**kwargs):
        return None

    trace: list = []
    fake_daemon = FakeDaemon(trace, pipe=None, memory=None)
    loop = asyncio.new_event_loop()
    inline_run, _ = _make_inline_run_in_executor(loop)
    try:
        with mock.patch.dict(os.environ, env, clear=False):
            if not writes_on:
                os.environ.pop("MAEZ_LEDGER_WRITES", None)
            else:
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
                            text=_OWNER_TEXT,
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
                            try_search_commitment_intent=_no_search,
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


class ProposalClosureTests(unittest.TestCase):
    """The proposal interceptor's exchange enters the record."""

    @_needs_enabled_writer
    def test_the_proposal_exchange_records_both_ruled_shapes(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            answer, db = _run_turn(
                tmp, writes_on=True, proposal_reply=_PROPOSAL_REPLY
            )
            rows = _rows(db)
        self.assertEqual(answer, _PROPOSAL_REPLY, "the reply must ship")
        self.assertEqual(
            len(rows), 2,
            "the proposal exchange must enter as TWO turns (owner + "
            f"organ); got {[r['turn_kind'] for r in rows]}",
        )
        owner_row, organ_row = rows
        self.assertEqual(owner_row["turn_kind"], "user_message")
        self.assertEqual(owner_row["raw_text"], _OWNER_TEXT)
        self.assertEqual(
            json.loads(owner_row["taint_labels_json"]), ["owner_utterance"]
        )
        self.assertEqual(organ_row["turn_kind"], "system_event")
        self.assertEqual(
            organ_row["raw_text"], _PROPOSAL_REPLY,
            "the organ row carries the EXACT bytes the owner received",
        )
        self.assertEqual(organ_row["event_origin"], _PROPOSAL_ORIGIN)
        self.assertEqual(
            json.loads(organ_row["taint_labels_json"]), ["self_generated"],
            "every proposal producer was read: none calls a model, and "
            "the rendered content is Maez's own stored proposals",
        )
        self.assertEqual(
            organ_row["parent_turn_id"], owner_row["turn_id"],
            "the answer hangs off the owner's turn",
        )

    @_needs_enabled_writer
    def test_a_silent_interceptor_writes_no_proposal_row(self):
        """The closure fires on the EGRESS branch ONLY. When the
        interceptor declines, the turn falls through to the ordinary
        path (which has its own admission) and this mouth must leave
        no trace — a phantom exchange is its own kind of lie."""
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            _answer, db = _run_turn(tmp, writes_on=True, proposal_reply=None)
            rows = _rows(db)
        self.assertEqual(
            [r for r in rows if r["event_origin"] == _PROPOSAL_ORIGIN],
            [],
            "a proposal row was written for a turn the interceptor "
            "never answered — a phantom exchange",
        )

    def test_flag_dormant_is_byte_inert_and_the_reply_still_ships(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            answer, db = _run_turn(
                tmp, writes_on=False, proposal_reply=_PROPOSAL_REPLY
            )
            self.assertEqual(answer, _PROPOSAL_REPLY)
            self.assertEqual(_rows(db), [])
            self.assertFalse(
                (Path(tmp) / "ledger_spool").exists()
                or list(Path(tmp).glob("*.deadletter.*")),
                "a dormant closure left residue",
            )


class SearchCommitmentIsBlockedByAProvenanceGapTests(unittest.TestCase):
    """WHY the search mouth is NOT closed in this slice — pinned so a
    future closure cannot quietly guess a taint label.

    EXECUTED: ``_try_search_commitment_intent`` returns two materially
    different kinds of text through ONE ``str`` return —

      * canned sentences ("My web sense is degraded right now ...",
        "I can search for this ... Want me to?"), honestly
        ``{self_generated}``; and
      * ``_format_search_commitment_results``, which embeds LIVE WEB
        CONTENT — result titles, snippets and URLs — honestly
        ``{self_generated, tool_output, internet_derived}``, a set the
        writer's DEFAULT map already permits for ``system_event``.

    ``run_inbound_turn`` receives only the string, so it cannot tell
    them apart. Stamping every search reply ``{self_generated}`` would
    claim Maez generated web content it did not (a fabrication-class
    lie); stamping every reply web-derived would claim internet
    provenance for a purely canned sentence. Both directions lie.

    The honest fix is an export: the producer must declare its own
    provenance, because only it knows — the same export-gap shape the
    twentieth round found for the dialog id and for model-generated
    replies. Until that exists, this mouth stays open AND NAMED.
    """

    def test_the_seam_cannot_express_tool_or_web_derived_organ_output(self):
        import inspect

        from core.ledger import recorder

        src = inspect.getsource(recorder.record_organ_event)
        self.assertIn(
            'taint_labels=["self_generated"]', src,
            "record_organ_event no longer hardcodes self_generated — if "
            "the seam gained honest tool/web-derived provenance, close "
            "the search-commitment mouth and delete this test",
        )

    def test_the_writer_would_accept_the_honest_web_derived_set(self):
        """The vocabulary is NOT the blocker — the export is."""
        from core.ledger.taint_stamping import (
            DEFAULT_ALLOWED_TAINT_LABEL_SETS_BY_TURN_KIND as _sets,
        )

        self.assertIn(
            frozenset(("self_generated", "tool_output", "internet_derived")),
            _sets["system_event"],
            "system_event already admits web-derived organ output; the "
            "gap is that the producer never tells the closure which "
            "branch spoke",
        )


if __name__ == "__main__":
    unittest.main()
