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
import enum
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
            # CORRECTED (twenty-third round, executed): the honest claim
            # is the bytes the INTERCEPTOR PRODUCED, not the bytes the
            # owner received. platform_base extracts markdown images and
            # MEDIA tokens before transport, so recorded and delivered
            # text diverge for those shapes — and both divergent shapes
            # are web-snippet-shaped, i.e. the mouth still to be closed.
            # Which bytes provenance binds to is a named question for the
            # custody-placement slice.
            "the organ row carries the EXACT bytes the interceptor "
            "produced",
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


def _run_search_turn(tmp: str, produced) -> tuple:
    """Drive the REAL run_inbound_turn through its search closure."""
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
        "MAEZ_PRIVATE_THOUGHTS_PATH": str(Path(tmp) / "pt.db"),
        "MAEZ_DATA": str(Path(tmp) / "data"),
    }
    fake_daemon = FakeDaemon([], pipe=None, memory=None)
    loop = asyncio.new_event_loop()
    inline_run, _ = _make_inline_run_in_executor(loop)

    async def _search(**_kw):
        return produced

    async def _no_proposal(**_kw):
        return None

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
                            text="yes please search that",
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
                            try_proposal_intent=_no_proposal,
                            try_search_commitment_intent=_search,
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


class SearchClosureRecordsTheDeclaredShapeTests(unittest.TestCase):
    """End-to-end: the shape the producer declared becomes the row's taint."""

    @_needs_enabled_writer
    def test_web_results_record_as_tool_and_internet_derived(self):
        from core.ledger.recorder import OrganProvenance, ProducedReply

        web_bytes = (
            'Here\'s what I found for "solar output":\n\n'
            "1. Solar output chart\n   a snippet\n   https://ex.example/a"
        )
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            answer, db = _run_search_turn(
                tmp, ProducedReply(web_bytes, OrganProvenance.WEB_RESULTS)
            )
            rows = _rows(db)
        self.assertEqual(answer, web_bytes, "the reply ships as a str")
        self.assertEqual(len(rows), 2, [r["turn_kind"] for r in rows])
        owner_row, organ_row = rows
        self.assertEqual(owner_row["turn_kind"], "user_message")
        self.assertEqual(organ_row["turn_kind"], "system_event")
        self.assertEqual(organ_row["event_origin"], "search_commitment")
        self.assertEqual(
            organ_row["raw_text"], web_bytes,
            "the bytes the interceptor PRODUCED (twenty-fourth round)",
        )
        self.assertEqual(
            sorted(json.loads(organ_row["taint_labels_json"])),
            ["internet_derived", "self_generated", "tool_output"],
            "the web branch must claim tool AND internet provenance — "
            "stamping {self_generated} here would claim Maez generated "
            "web content it did not",
        )
        self.assertEqual(
            organ_row["parent_turn_id"], owner_row["turn_id"],
            "owner-provenance for the echoed query rides the PARENT "
            "EDGE (owner ruling 2026-08-28), not a widened taint map",
        )

    @_needs_enabled_writer
    def test_a_canned_search_sentence_records_as_self_generated_only(self):
        from core.ledger.recorder import OrganProvenance, ProducedReply

        canned = (
            "My web search is unavailable right now, so I can't follow "
            "through on that search honestly."
        )
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            _answer, db = _run_search_turn(
                tmp, ProducedReply(canned, OrganProvenance.CANNED)
            )
            rows = _rows(db)
        organ_row = rows[1]
        self.assertEqual(
            json.loads(organ_row["taint_labels_json"]), ["self_generated"],
            "a canned sentence must NOT claim internet provenance — "
            "the lie in the other direction",
        )

    @_needs_enabled_writer
    def test_the_two_shapes_produce_DIFFERENT_rows(self):
        """The whole point: one branch, two honest labels."""
        from core.ledger.recorder import OrganProvenance, ProducedReply

        seen = []
        for shape in (OrganProvenance.WEB_RESULTS, OrganProvenance.CANNED):
            with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
                _a, db = _run_search_turn(
                    tmp, ProducedReply("same bytes either way", shape)
                )
                seen.append(json.loads(_rows(db)[1]["taint_labels_json"]))
        self.assertNotEqual(
            seen[0], seen[1],
            "IDENTICAL bytes recorded identically under both shapes — "
            "the export is not reaching the row, which is the exact "
            "defect this slice closed",
        )


    def test_flag_dormant_is_byte_inert_and_the_search_reply_still_ships(self):
        """The hard constraint: Maez stays unborn and the mouth is silent.

        No db bytes, no spool, no dead-letter — and the reply ships
        regardless, because recording never gates egress (ADR 0035).
        """
        import daemon.inbound_core as core_mod
        from core.ledger.recorder import OrganProvenance, ProducedReply
        from tests.test_inbound_core_equivalence import (
            FakeDaemon,
            _make_inline_run_in_executor,
        )

        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            before = db.stat().st_size
            env = {
                "MAEZ_LEDGER_DB_PATH": str(db),
                "MAEZ_PRIVATE_THOUGHTS_PATH": str(Path(tmp) / "pt.db"),
                "MAEZ_DATA": str(Path(tmp) / "data"),
            }
            loop = asyncio.new_event_loop()
            inline_run, _ = _make_inline_run_in_executor(loop)

            async def _search(**_kw):
                return ProducedReply("web bytes", OrganProvenance.WEB_RESULTS)

            async def _no_proposal(**_kw):
                return None

            try:
                with mock.patch.dict(os.environ, env, clear=False):
                    os.environ.pop("MAEZ_LEDGER_WRITES", None)
                    with mock.patch.object(
                        loop, "run_in_executor", inline_run
                    ), mock.patch.object(
                        core_mod, "surface_parity_enabled", lambda: False
                    ), mock.patch.object(
                        core_mod, "get_shared_executor", lambda: None
                    ):
                        answer = loop.run_until_complete(
                            core_mod.run_inbound_turn(
                                daemon=FakeDaemon([], pipe=None, memory=None),
                                text="yes please search that",
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
                                try_proposal_intent=_no_proposal,
                                try_search_commitment_intent=_search,
                                search_commitment_controller=lambda: None,
                                audit_surface_reply=lambda text, surface: text,
                                clean_exchange=lambda text: text,
                                send_intermediate=lambda text: None,
                                send_progress_receipt=lambda *a, **k: None,
                            )
                        )
            finally:
                loop.close()

            self.assertEqual(answer, "web bytes", "the reply ships dormant")
            self.assertEqual(db.stat().st_size, before, "db bytes moved")
            self.assertFalse(
                (Path(tmp) / "ledger_spool").exists()
                or list(Path(tmp).glob("*.deadletter.*")),
                "a dormant search closure left residue",
            )


class SearchCommitmentProvenanceExportTests(unittest.TestCase):
    """The mouth that WAS blocked, now closed by a typed export.

    This class replaces ``SearchCommitmentIsBlockedByAProvenanceGap
    Tests``, whose own docstring said to delete it "if the seam gained
    honest tool/web-derived provenance". It has.

    The gap was never the vocabulary — the writer already admitted
    ``{self_generated, tool_output, internet_derived}`` for
    ``system_event``. The gap was the EXPORT: the producer returned
    canned sentences and live-web-embedding text through one ``str``,
    so ``run_inbound_turn`` could not tell them apart, and BOTH fixed
    labels lied in one branch. The producer now declares a closed named
    shape and the seam binds the taint set.
    """

    def test_the_enum_introduces_no_new_taint_label(self):
        """The folded dissent's condition, pinned.

        The twenty-third round folded FOR a named-shape enum over a
        seat's objection that it mints a fourth provenance vocabulary.
        The objection was ANSWERED, not overruled: the enum may map
        only onto labels that already exist. If that ever stops being
        true, the objection becomes correct and the design must be
        re-opened.
        """
        from core.ledger.recorder import _PROVENANCE_TAINTS
        from core.ledger.taint_stamping import TAINT_LABEL_ORDER

        for shape, labels in _PROVENANCE_TAINTS.items():
            for label in labels:
                self.assertIn(
                    label, TAINT_LABEL_ORDER,
                    f"{shape} maps onto {label!r}, which is NOT in the "
                    "frozen taint vocabulary — the enum has started "
                    "minting labels, which is exactly the "
                    "one-column-two-namespaces sin a seat warned of",
                )

    def test_every_mapped_set_is_one_the_writer_already_admits(self):
        from core.ledger.recorder import _PROVENANCE_TAINTS
        from core.ledger.taint_stamping import (
            DEFAULT_ALLOWED_TAINT_LABEL_SETS_BY_TURN_KIND as _sets,
        )

        for shape, labels in _PROVENANCE_TAINTS.items():
            self.assertIn(
                frozenset(labels), _sets["system_event"],
                f"{shape} maps to a set system_event does not admit — "
                "the owner ruled the frozen map is NOT widened",
            )

    def test_the_producer_exports_a_shape_for_every_reply_it_returns(self):
        """Both provenances are reachable, and they DIFFER.

        A test that only proved 'a shape is attached' would pass on a
        producer that stamped one shape everywhere — which is the lie
        this export exists to prevent.
        """
        import inspect

        from skills.surface.maez_adapter import MaezMessageHandler
        from core.ledger.recorder import OrganProvenance

        src = inspect.getsource(
            MaezMessageHandler._try_search_commitment_intent
        )
        self.assertNotIn(
            "return f\"", src,
            "a bare f-string return reappeared in the search producer — "
            "every reply must leave as a ProducedReply carrying its shape",
        )
        self.assertIn("OrganProvenance.WEB_RESULTS", src)
        self.assertIn("OrganProvenance.CANNED", src)
        self.assertNotEqual(
            OrganProvenance.WEB_RESULTS, OrganProvenance.CANNED
        )

    def test_the_REAL_producer_labels_each_branch_correctly(self):
        """Drive the actual producer; do not trust source-text order.

        Codex's walk argued a WEB/CANNED swap would survive the
        source-text assertions. EXECUTED: a full swap DOES go red — the
        claim was falsified. But the objection stands on method: the
        row tests inject already-labelled ProducedReply objects, so
        nothing exercised the producer's OWN labelling. This does.
        """
        from core.ledger.recorder import OrganProvenance
        from skills.surface.maez_adapter import MaezMessageHandler

        class _Backend:
            def __init__(self, health):
                self._h = health

            def health(self):
                return self._h

        class _Ctrl:
            def __init__(self, results):
                self._results = results

            def get_search_offer(self, *a, **k):
                return type("R", (), {"offered_query": "solar"})()

            def resolve_search_affirmation(self, *a, **k):
                return self._results

            def store_search_offer(self, *a, **k):
                return True

        def _run(results, health="healthy"):
            h = MaezMessageHandler.__new__(MaezMessageHandler)
            h._search_commitment_controller = lambda: _Ctrl(results)
            h._search_commitment_backend = lambda: _Backend(health)
            with mock.patch(
                "skills.surface.maez_adapter._search_commitment_enabled",
                lambda: True,
            ), mock.patch(
                "skills.surface.maez_adapter.sense_enabled", lambda: False
            ), mock.patch(
                "skills.surface.maez_adapter.is_clear_yes", lambda t: True
            ):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(
                        MaezMessageHandler._try_search_commitment_intent(
                            h, text="yes", chat_id="1"
                        )
                    )
                finally:
                    loop.close()

        hit = _run([{"title": "T", "url": "u", "content": "c"}])
        self.assertIsNotNone(hit)
        self.assertEqual(
            hit.provenance, OrganProvenance.WEB_RESULTS,
            "the branch that embeds titles/snippets/URLs must claim "
            "tool AND internet provenance",
        )
        self.assertIn("T", hit.text)

        unavailable = _run(None, health="down")
        self.assertIsNotNone(unavailable)
        self.assertEqual(
            unavailable.provenance, OrganProvenance.CANNED,
            "a canned unavailability sentence must NOT claim the web",
        )

        empty = _run([])
        self.assertEqual(
            empty.provenance, OrganProvenance.CANNED,
            "an EMPTY result set embeds no web content — only the "
            "formatter's own header (Codex walk M8)",
        )

    def test_the_web_branch_is_the_only_one_marked_web_derived(self):
        """The formatter's output is the ONLY live-web-embedding text."""
        import inspect

        from skills.surface.maez_adapter import MaezMessageHandler

        src = inspect.getsource(
            MaezMessageHandler._try_search_commitment_intent
        )
        self.assertEqual(
            src.count("OrganProvenance.WEB_RESULTS"), 1,
            "more than one branch now claims internet provenance — "
            "read them; a canned sentence claiming web derivation is "
            "as much a lie as the reverse",
        )
        web_at = src.index("OrganProvenance.WEB_RESULTS")
        fmt_at = src.index("_format_search_commitment_results")
        self.assertLess(
            fmt_at, web_at,
            "WEB_RESULTS is no longer attached to the formatter's "
            "output — the one branch that embeds titles, snippets and URLs",
        )

    def test_a_producer_may_not_return_empty_text_with_a_shape(self):
        from core.ledger.recorder import OrganProvenance, ProducedReply

        with self.assertRaises(ValueError):
            ProducedReply("", OrganProvenance.CANNED)
        with self.assertRaises(ValueError):
            ProducedReply("   \n ", OrganProvenance.CANNED)

    def test_a_forgotten_provenance_is_a_BUILD_failure_not_a_runtime_hole(self):
        """Ruled: refusal must be UNREACHABLE on a green path."""
        import inspect

        from core.ledger import recorder

        sig = inspect.signature(recorder.record_organ_event)
        param = sig.parameters["provenance"]
        self.assertIs(
            param.default, inspect.Parameter.empty,
            "provenance gained a default — a forgotten wiring would "
            "then silently stamp a guess instead of failing the build",
        )
        self.assertIs(param.kind, inspect.Parameter.KEYWORD_ONLY)

    def test_an_unmappable_provenance_refuses_admission_with_NO_guessed_taint(self):
        """Fail-closed, and the sidecar must carry no laundered label.

        Replay preserves an envelope's kwargs verbatim, so a guessed
        taint in a dead-letter record could be promoted into the chain
        later. The refusal therefore sits with the EARLY seam checks,
        which pass RAW kwargs before taint binding.
        """
        from core.ledger.recorder import _resolve_taints, UnmappableProvenance

        with self.assertRaises(UnmappableProvenance):
            _resolve_taints(None, None)
        with self.assertRaises(UnmappableProvenance):
            _resolve_taints(["self_generated"], _FakeShape.NOT_A_SHAPE)

    def test_the_formatter_can_never_produce_empty_text(self):
        """The one thing standing between a new raise and a lost reply.

        ``ProducedReply`` refuses empty text, and the producer is called
        from ``run_inbound_turn`` OUTSIDE any try block (the record
        calls are guarded; the producer call is not, and was not before
        this slice either). EXECUTED: the formatter's header line is
        unconditional, so empty output is unreachable — even with no
        results, a None query, or wholly blank rows. If that header
        ever becomes conditional, this raise would cost the owner a
        reply, so the property is pinned rather than assumed.
        """
        from skills.surface.maez_adapter import MaezMessageHandler

        fmt = MaezMessageHandler._format_search_commitment_results

        class _S:
            pass

        for query, results in (
            ("", []),
            (None, None),
            ("   ", []),
            ("q", [{"title": "", "url": "", "content": ""}] * 3),
        ):
            out = fmt(_S(), query, results)
            self.assertTrue(
                out and out.strip(),
                f"the formatter returned empty for {query!r}/{results!r} — "
                "ProducedReply would raise inside an UNGUARDED producer "
                "call and the owner would lose the reply",
            )

    def test_no_taint_list_crosses_any_closure_bearing_module(self):
        """The structural point of the design, over EVERY module that
        holds a closure — not just one.

        An earlier version of this test read `inbound_core.py` alone and
        called it "ever", which silently exempted the web closure
        (Codex boundary walk, M6). It is still not a completeness claim:
        a taint list reached through a helper, an alias or a **kwargs
        splat is invisible to it.
        """
        repo = Path(__file__).resolve().parent.parent
        closure_modules = [
            repo / "daemon" / "inbound_core.py",
            repo / "skills" / "web_interface.py",
        ]
        # Two-sided: if a closure-bearing module drops out of this list,
        # the pin silently narrows.
        for path in closure_modules:
            src = path.read_text()
            self.assertIn(
                "record_organ_event", src,
                f"{path.name} no longer holds a closure — this list has "
                "gone stale and the pin now covers less than it claims",
            )
            for line in src.splitlines():
                if "taint_labels" in line and not line.lstrip().startswith("#"):
                    self.fail(
                        f"{path.name} names taint_labels at a closure: "
                        f"{line.strip()!r} — closures name a SHAPE and "
                        "the seam binds the labels"
                    )


class _FakeShape(enum.Enum):
    NOT_A_SHAPE = "not_a_shape"


if __name__ == "__main__":
    unittest.main()
