# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""A3 per-path closures — the two S4 crisis mouths.

The sharpest omissions on the roster, closed RED-first through the
recorder seam (twenty-second round):

  * daemon/inbound_core.py run_inbound_turn — the LIVE v2 owner path's
    crisis return. Before this closure the whole exchange (the owner's
    words AND the crisis answer) recorded NOTHING: the S4 branch
    returns before handle_message's user_message admission.
  * skills/web_interface.py /chat — the nineteenth round's sharpest
    miss: the owner /chat route returns the crisis answer BEFORE
    submit_user_message. A NON-OWNER process: the record lands as
    spool CUSTODY under the web_owner producer, exactly the lane the
    twenty-second round routed.

Crisis exchanges are ordinary turns in the record (owner ruling); the
S4 organ itself is untouched — the guard still runs FIRST (ADR 0035)
and the reply ships regardless of what recording does.

Store discipline: MAEZ_PRIVATE_THOUGHTS_PATH is redirected in every
test (the S4 guard fires the crisis signal writer; MAEZ_TEST_MODE does
NOT sandbox PrivateThoughts — the eighteenth round's live-store scar),
and MAEZ_DATA is pointed at scratch as defence in depth.
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
from core.ledger import migrate, owner, spool

_needs_enabled_writer = unittest.skipUnless(
    has_wal_reset_fix(),
    "an enabled ledger writer requires SQLite >= 3.51.3 "
    "(run with LD_LIBRARY_PATH=vendor/sqlite/lib)",
)

_PROBE_ROOT = "/var/tmp"

_CRISIS_TEXT = "I want to die and I need a doctor"
_S4_ORIGIN = "s4_clinical_boundary"


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


def _pending(db: Path | str) -> list[tuple[str, dict]]:
    root = Path(spool.default_spool_root(str(db)))
    return [
        (p.parent.parent.name, json.loads(p.read_text()))
        for p in sorted(root.glob("*/pending/*.json"))
    ]


class InboundCoreS4ClosureTests(unittest.TestCase):
    """The v2 owner path's crisis mouth records both ruled shapes."""

    def _run_crisis_turn(self, tmp: str, *, writes_on: bool) -> tuple:
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
        trace: list = []
        fake_daemon = FakeDaemon(trace, pipe=None, memory=None)
        loop = asyncio.new_event_loop()
        inline_run, _ = _make_inline_run_in_executor(loop)
        try:
            with mock.patch.dict(os.environ, env, clear=False):
                if not writes_on:
                    os.environ.pop("MAEZ_LEDGER_WRITES", None)
                if writes_on:
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
                                text=_CRISIS_TEXT,
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
                                try_proposal_intent=None,
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

    @_needs_enabled_writer
    def test_the_crisis_exchange_records_both_ruled_shapes(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            answer, db = self._run_crisis_turn(tmp, writes_on=True)
            rows = _rows(db)
        self.assertTrue(answer, "the crisis reply must ship")
        self.assertEqual(
            len(rows), 2,
            "the S4 exchange must enter the record as TWO turns "
            f"(owner + organ); got {[r['turn_kind'] for r in rows]}",
        )
        owner_row, organ_row = rows
        self.assertEqual(owner_row["turn_kind"], "user_message")
        self.assertEqual(
            owner_row["raw_text"], _CRISIS_TEXT,
            "the owner's message enters IN FULL (exact bytes)",
        )
        # The LIVE v2 label, verbatim (maez_adapter.SURFACE_NAME): the
        # recorder never rewrites; the registry aliases
        # telegram_surface -> telegram_text at ITS seam, not here.
        self.assertEqual(owner_row["surface"], "telegram_surface")
        self.assertEqual(
            json.loads(owner_row["taint_labels_json"]), ["owner_utterance"]
        )
        self.assertEqual(organ_row["turn_kind"], "system_event")
        self.assertEqual(
            organ_row["raw_text"], answer,
            "the organ row carries the EXACT bytes the owner received",
        )
        self.assertEqual(organ_row["event_origin"], _S4_ORIGIN)
        self.assertEqual(
            organ_row["parent_turn_id"], owner_row["turn_id"],
            "the crisis answer hangs off the owner's turn",
        )

    def test_flag_dormant_is_byte_inert_and_the_reply_still_ships(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            before = Path(tmp)
            answer, db = self._run_crisis_turn(tmp, writes_on=False)
            self.assertTrue(answer, "the crisis reply must ship")
            self.assertEqual(_rows(db), [])
            self.assertFalse(
                (before / "ledger_spool").exists()
                or list(before.glob("*.deadletter.*")),
                "a dormant closure left residue",
            )


class WebChatS4ClosureTests(unittest.TestCase):
    """The web /chat crisis mouth records via spool CUSTODY (non-owner).

    DISCOVERED CLOSING IT (2026-08-27, executed): the /chat endpoint is
    PARKED — ``_LEGACY_PARKED_API_ENDPOINTS`` includes ``chat``, so
    every request 410s in ``local_origin_write_guard`` before the
    function body runs. The nineteenth round's "production-wired owner
    egress" framing is stale AT THE ENDPOINT LAYER; the S4 body is
    real but currently unreachable from outside. The parking is
    explicitly reversible ("Reversible parking for retired public web
    doors"), so the closure lands for the day the door reopens; these
    tests unpark it IN-TEST ONLY and say so.
    """

    def _post_crisis(self, tmp: str, *, writes_on: bool):
        db = Path(tmp) / "ledger.db"
        migrate.run(str(db))
        env = {
            "MAEZ_LEDGER_DB_PATH": str(db),
            "MAEZ_PRIVATE_THOUGHTS_PATH": str(Path(tmp) / "pt.db"),
        }
        if writes_on:
            env["MAEZ_LEDGER_WRITES"] = "1"
        with mock.patch.dict(os.environ, env, clear=False):
            if not writes_on:
                os.environ.pop("MAEZ_LEDGER_WRITES", None)
            os.environ.pop("MAEZ_LEDGER_OWNER_PID", None)
            import skills.web_interface as wi

            owner_user = {"display_name": "Rohit", "uuid": "u1"}
            owner_record = {"web_owner": True}
            unparked = {
                k: v
                for k, v in wi._LEGACY_PARKED_API_ENDPOINTS.items()
                if k != "chat"
            }
            with mock.patch.object(
                wi.accounts, "get_by_token", return_value=owner_user
            ), mock.patch.object(
                wi.accounts, "get_user_record", return_value=owner_record
            ), mock.patch.object(
                wi, "_LEGACY_PARKED_API_ENDPOINTS", unparked
            ), mock.patch(
                "core.evolution.subjective_duration.SubjectiveDurationOwnerAuth",
                side_effect=RuntimeError("test: no live salience writes"),
            ):
                client = wi.app.test_client()
                resp = client.post(
                    "/chat",
                    json={"web_token": "t", "message": _CRISIS_TEXT},
                )
        return resp, db

    def test_the_crisis_exchange_takes_custody_under_web_owner(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            resp, db = self._post_crisis(tmp, writes_on=True)
            envelopes = _pending(db)
            self.assertEqual(_rows(db), [], "web never opens the ledger")
        self.assertEqual(resp.status_code, 200)
        reply = resp.get_json()["reply"]
        self.assertTrue(reply, "the crisis reply must ship")
        self.assertEqual(
            len(envelopes), 2,
            "the web S4 exchange must take custody as TWO envelopes "
            f"(owner + organ); got {[e[1]['turn_kind'] for e in envelopes]}",
        )
        by_kind = {e[1]["turn_kind"]: e[1] for e in envelopes}
        producers = {e[0] for e in envelopes}
        self.assertEqual(producers, {"web_owner"})
        owner_env = by_kind["user_message"]
        organ_env = by_kind["system_event"]
        self.assertEqual(owner_env["raw_text"], _CRISIS_TEXT)
        self.assertEqual(
            json.loads(json.dumps(owner_env["kwargs"])).get("taint_labels"),
            ["owner_utterance"],
        )
        self.assertEqual(organ_env["raw_text"], reply)
        self.assertEqual(organ_env["kwargs"].get("event_origin"), _S4_ORIGIN)
        self.assertEqual(
            organ_env["parent_submission_id"],
            owner_env["submission_id"],
            "the organ envelope threads to the owner's turn by "
            "submission id — the custody-lane edge",
        )

    def test_flag_dormant_web_is_byte_inert_and_the_reply_still_ships(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            resp, db = self._post_crisis(tmp, writes_on=False)
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.get_json()["reply"])
            self.assertEqual(_rows(db), [])
            self.assertFalse(
                Path(spool.default_spool_root(str(db))).exists(),
                "a dormant web closure left spool residue",
            )


class HalfExchangeTests(unittest.TestCase):
    """Codex boundary walk B4: a failing owner record must never
    withhold the organ record (ruled by name, twenty-second round)."""

    @_needs_enabled_writer
    def test_an_owner_record_crash_does_not_skip_the_organ_record(self):
        from core.ledger import recorder as recorder_mod

        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            with mock.patch.object(
                recorder_mod,
                "record_owner_message",
                side_effect=RuntimeError("seam bug"),
            ):
                harness = InboundCoreS4ClosureTests()
                answer, db = harness._run_crisis_turn(tmp, writes_on=True)
            rows = _rows(db)
        self.assertTrue(answer, "the crisis reply must ship")
        organ_rows = [r for r in rows if r["turn_kind"] == "system_event"]
        self.assertEqual(
            len(organ_rows), 1,
            "the organ record was withheld because the owner record "
            "crashed — record what you have, thread what you can",
        )
        self.assertIsNone(organ_rows[0]["parent_turn_id"])


class RehearsalWitnessOfTheRealSeamTests(unittest.TestCase):
    """THE MANDATED WITNESS (eighteenth round; nineteenth round
    constraints 1+2): the REAL production path — closure code, seam,
    writer — rehearsed end-to-end BEFORE birth.

    Both row shapes, REAL surface labels (x6_rehearsal structurally
    forbids owner_utterance so the rows carry the live v2 label),
    sidecar db under the rehearsal root, flag armed IN-PROCESS only
    (womb-life practise, not birth), production ledger never opened.

    Injection mechanics, stated: the closures call the seam's public
    functions with the identity-pinned production DEFAULT, and Python
    binds defaults at def time — so the witness swaps
    ``__kwdefaults__`` in-process and restores it, which is exactly
    the injection surface the twenty-second round pinned (an explicit
    recorder object; try_write_turn itself still refuses rehearsal —
    constraint 1 stays pinned by tests/test_a3_rehearsal_lane_witness).
    """

    @_needs_enabled_writer
    def test_the_live_s4_closure_rehearses_both_shapes_end_to_end(self):
        from core.ledger import recorder as recorder_mod

        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            root = Path(tmp) / "logs" / "rehearsal"
            sidecar = root / "x6_a3_s4_witness" / "ledger.db"
            sidecar.parent.mkdir(parents=True)
            migrate.run(str(sidecar))

            # The rehearsal writer reads the flag AT CONSTRUCTION —
            # womb-life practise arms it for the lane's own birth here;
            # the harness re-arms it for the closure run itself.
            with mock.patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                lane = recorder_mod.RehearsalRecorder(
                    str(sidecar), rehearsal_root=root
                )
            seam_fns = (
                recorder_mod.record_owner_message,
                recorder_mod.record_organ_event,
            )
            # The swap lives INSIDE the try so a failure mid-swap cannot
            # leak an injected default past this test (Codex walk B5).
            saved = [fn.__kwdefaults__["recorder"] for fn in seam_fns]
            try:
                for fn in seam_fns:
                    fn.__kwdefaults__["recorder"] = lane
                harness = InboundCoreS4ClosureTests()
                # The harness itself creates and env-names tmp/ledger.db
                # as the production-path target — THAT is the db the
                # no-stealth-write assertion must watch (the walk's B5:
                # the first cut watched an unused file).
                answer, production_db = harness._run_crisis_turn(
                    tmp, writes_on=True
                )
            finally:
                for fn, orig in zip(seam_fns, saved, strict=True):
                    fn.__kwdefaults__["recorder"] = orig
                lane.close()

            self.assertTrue(answer, "the crisis reply must ship")
            con = sqlite3.connect(f"file:{sidecar}?mode=ro", uri=True)
            try:
                con.row_factory = sqlite3.Row
                rows = [
                    dict(r)
                    for r in con.execute(
                        "SELECT * FROM turns WHERE lifecycle_stage="
                        "'rehearsal' ORDER BY chain_position"
                    )
                ]
            finally:
                con.close()
            self.assertEqual(
                _rows(production_db), [],
                "the witness leaked rows into the env-named "
                "production-path db — the rehearsal injection did not "
                "hold",
            )
            self.assertEqual(
                _pending(production_db), [],
                "the witness leaked spool custody beside the env-named "
                "production-path db",
            )
        self.assertEqual(
            [r["turn_kind"] for r in rows],
            ["user_message", "system_event"],
            "both ruled shapes rehearse through the REAL closure",
        )
        owner_row, organ_row = rows
        self.assertEqual(owner_row["raw_text"], _CRISIS_TEXT)
        self.assertEqual(
            owner_row["surface"], "telegram_surface",
            "rehearsal rows carry the REAL surface label "
            "(constraint 2: x6_rehearsal forbids owner_utterance)",
        )
        self.assertEqual(organ_row["raw_text"], answer)
        self.assertEqual(organ_row["event_origin"], _S4_ORIGIN)
        self.assertEqual(organ_row["parent_turn_id"], owner_row["turn_id"])

    def test_the_default_recorder_is_restored_after_the_witness(self):
        from core.ledger import recorder as recorder_mod

        self.assertIs(
            recorder_mod.record_owner_message.__kwdefaults__["recorder"],
            recorder_mod.PRODUCTION,
        )
        self.assertIs(
            recorder_mod.record_organ_event.__kwdefaults__["recorder"],
            recorder_mod.PRODUCTION,
        )


if __name__ == "__main__":
    unittest.main()
