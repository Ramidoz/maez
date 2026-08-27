# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Dead-letter replay organ — APPLY half.

The classifier answers "what happened to each record?"; this half acts on
that answer and nothing else. Every test here pins a council ruling or an
EXECUTED hazard, not a preference:

- eligibility comes ONLY from classify()'s dispositions, and the selected
  set is machine-derived — there is no per-record switch to express taste
  through (tenth round, 3-0);
- KIND-BLIND, always: flipping turn_kind must not move a single decision.
  "A gate only on model_reply structurally teaches the record that her
  words were the suspect class";
- the reconstructed BODY preserves turn_kind/surface/raw_surface/
  taint_labels/privacy_access EXACTLY, and RELOCATES the authority kwargs
  the record carries (submission_id, parent_turn_id) into envelope fields
  — executed: a verbatim enqueue is quarantined at drain;
- the COMPANION is not a child (parent NULL both ways), is content-light
  by CONSTRUCTION, and is published only against an OBSERVED commit;
- crash-completeness runs both directions, including the standing-block-7
  window: body committed, companion missing → enqueue ONLY the companion.
"""
from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DIR = tempfile.mkdtemp(prefix="maez_test_dl_apply_", dir="/var/tmp")

from core.ledger import dead_letter_replay as R  # noqa: E402
from core.ledger import migrate, spool  # noqa: E402
from core.ledger import owner as ledger_owner  # noqa: E402
from core.ledger import writer as ledger_writer  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


#: A payload complete enough for every kind under test. §4.2 requires
#: model_id/prompt_hash/soul_hash/evidence_envelope/audit_verdict for
#: model_reply and daemon_cycle; supplying them everywhere lets the
#: flip-turn_kind tests vary ONLY the kind.
def _kwargs_for(kind: str, **over) -> dict:
    base = {
        "surface": "web_owner",
        "raw_surface": None,
        "taint_labels": ["self_generated"],
        "privacy_access": "public",
    }
    if kind == "user_message":
        base["taint_labels"] = ["owner_utterance"]
    elif kind in ("model_reply", "daemon_cycle"):
        base.update(
            model_id="maez-local",
            prompt_hash="a" * 64,
            soul_hash="b" * 64,
            evidence_envelope={"claimable": []},
            audit_verdict={"ran": True},
        )
    elif kind == "tool_call":
        base["action_proposal"] = {"kind": "noop"}
    elif kind == "tool_result":
        base["taint_labels"] = ["tool_output"]
    base.update(over)
    return base


class _Fixture:
    """One isolated ledger with writes enabled and no live daemon."""

    def __init__(self, name: str):
        self.dir = Path(_TEST_DIR) / f"{name}_{os.urandom(4).hex()}"
        self.dir.mkdir()
        self.db = str(self.dir / "ledger.db")
        migrate.run(self.db)
        self.spool_root = spool.default_spool_root(self.db)

    # -- production of real dead letters ---------------------------------
    def dead_letter(self, kind="user_message", text="an omitted life", **kw):
        """Produce a REAL dead-letter record through the shipped writer —
        never a hand-written line. The record's kwargs then carry exactly
        what production would carry, including the authority fields."""
        with _enabled(), patch.object(
            ledger_writer.LedgerWriter, "write_turn",
            side_effect=OSError("disk went away"),
        ):
            ledger_owner.owner_write_turn(
                self.db, kind, text, **_kwargs_for(kind, **kw)
            )
        return self.records()[-1]

    def commit(self, kind="user_message", text="hello", **kw):
        with _enabled():
            return ledger_owner.owner_write_turn(
                self.db, kind, text, **_kwargs_for(kind, **kw)
            )

    def records(self):
        return sorted(R._records(self.db)[0], key=lambda r: r["ts"])

    def manifest(self, role="owner_trustee"):
        m = R.build_manifest(self.db, role=role)
        return m, R.write_manifest(self.db, m)

    def rows(self, sid):
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        try:
            return conn.execute(
                "SELECT turn_kind, surface, raw_surface, taint_labels_json,"
                " privacy_access, parent_turn_id, submitted_at, timestamp,"
                " raw_text FROM turns WHERE submission_id = ?", (sid,),
            ).fetchall()
        finally:
            conn.close()

    def drain(self):
        with _enabled():
            return spool.drain_once(self.spool_root, self.db)


def _enabled():
    return patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"})


class ManifestTests(unittest.TestCase):
    def setUp(self):
        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)
        self.f = _Fixture("manifest")

    def test_only_replayable_records_are_selected(self):
        """Eligibility comes ONLY from dispositions. Every other class
        stays evidence — refused/unknown/unverified/conflict — and
        possibly_committed waits for the evidence lane."""
        self.f.dead_letter(text="plain failure")                      # replayable
        with _enabled(), patch.object(
            ledger_writer.LedgerWriter, "write_turn",
            side_effect=ValueError("bad provenance"),
        ):
            ledger_owner.owner_write_turn(                            # refused
                self.f.db, "user_message", "judged bytes",
                **_kwargs_for("user_message"))
        m, _ = self.f.manifest()
        by_disp = {}
        for e in m["census"]:
            by_disp.setdefault(e["disposition"], []).append(e["event_id"])
        self.assertEqual(len(m["selected"]["bodies"]), 1)
        self.assertEqual(m["selected"]["bodies"], by_disp["replayable"])
        self.assertNotIn(by_disp["refused_evidence"][0], m["selected"]["bodies"])
        self.assertEqual(m["selected"]["companions"], [])

    def test_possibly_committed_is_never_selected(self):
        """Review adds EVIDENCE; preference or regret can never resolve
        an ambiguous identity (tenth round)."""
        self.f.commit(text="an ambiguous life")
        rec = self.f.dead_letter(text="an ambiguous life")
        self.assertEqual(
            [e["disposition"] for e in R.classify(self.f.db)["records"]
             if e["event_id"] == rec["event_id"]],
            ["possibly_committed"],
        )
        m, _ = self.f.manifest()
        self.assertEqual(m["selected"]["bodies"], [])

    def test_selection_is_kind_blind(self):
        """MANDATORY (tenth round, 3-0). Flip turn_kind across every kind
        the record could carry; the selection must not move by one entry.
        'A gate only on model_reply structurally teaches the record that
        her words were the suspect class.'"""
        kinds = ["user_message", "model_reply", "tool_call", "daemon_cycle",
                 "peer_message_in", "peer_message_out", "system_event"]
        selected_counts = []
        for kind in kinds:
            f = _Fixture(f"kindblind_{kind}")
            f.dead_letter(kind=kind, text="the same life, a different kind")
            m, _ = f.manifest()
            selected_counts.append(
                (kind, len(m["selected"]["bodies"]), m["census"][0]["disposition"])
            )
        self.assertEqual(
            {c for _, c, _ in selected_counts}, {1},
            f"selection moved with turn_kind: {selected_counts}")
        self.assertEqual(
            {d for _, _, d in selected_counts}, {"replayable"},
            f"disposition moved with turn_kind: {selected_counts}")

    def test_manifest_records_operator_as_fact_not_consent(self):
        m, _ = self.f.manifest(role="owner_trustee")
        self.assertEqual(m["operator"]["role"], "owner_trustee")
        self.assertEqual(m["operator"]["recorded_as"], "fact_not_consent")
        self.assertIsInstance(m["operator"]["uid"], int)

    def test_consent_shaped_role_is_refused(self):
        with self.assertRaises(ValueError) as cm:
            self.f.manifest(role="owner_approved")
        self.assertIn("consent-shaped", str(cm.exception))

    def test_consent_semantics_refused_anywhere_in_the_document(self):
        """Nested is the same laundering as top-level."""
        m, _ = self.f.manifest()
        m["selected"]["approved"] = True
        with self.assertRaises(ValueError) as cm:
            R.write_manifest(self.f.db, m)
        self.assertIn("consent semantics", str(cm.exception))

    def test_manifest_has_no_per_record_switch(self):
        """Taste must be structurally inexpressible: there is no argument
        through which a caller can omit or add one sid."""
        import inspect
        params = set(inspect.signature(R.build_manifest).parameters)
        self.assertEqual(params, {"db_path", "role"})
        self.assertEqual(
            set(inspect.signature(R.apply).parameters),
            {"db_path", "manifest_path"})

    def test_manifest_binds_ledger_instance_and_chain_head(self):
        self.f.commit(text="anchor me")
        m, _ = self.f.manifest()
        t = m["target_ledger"]
        self.assertEqual(t["realpath"], os.path.realpath(self.f.db))
        self.assertTrue(t["instance_anchor"])
        self.assertTrue(t["pre_apply_chain_head"])

    def test_manifest_carries_the_standing_limitations(self):
        m, _ = self.f.manifest()
        names = {limit["name"] for limit in m["limitations"]}
        self.assertIn("delivery_evidence_unavailable", names)
        self.assertIn("sidecar_authenticity_not_proven", names)

    def test_manifest_lives_beside_the_ledger_not_in_the_spool(self):
        """EXECUTED hazard: drain_once treats every directory in the spool
        root as a producer, mkdirs pending/acked/refused inside it, and
        reports it in spool_status."""
        _, path = self.f.manifest()
        self.assertFalse(path.startswith(self.f.spool_root + os.sep))
        self.assertTrue(path.startswith(R.manifest_root(self.f.db)))
        self.f.drain()
        self.assertNotIn(
            "ledger_replay_manifests",
            spool.spool_status(self.f.spool_root)["producers"])


class BindingRefusalTests(unittest.TestCase):
    """The manifest is evidence about a moment. These are the checks that
    stop it becoming an authorization that outlives its evidence."""

    def setUp(self):
        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)
        self.f = _Fixture("binding")
        self.f.commit(text="anchor")
        self.f.dead_letter(text="a life to restore")

    def _apply_expecting(self, name, mutate=None):
        m, path = self.f.manifest()
        if mutate:
            mutate(m)
            Path(path).write_text(json.dumps(m), encoding="utf-8")
        with self.assertRaises(R.ReplayRefusal) as cm:
            R.apply(self.f.db, path)
        self.assertEqual(cm.exception.name, name)
        return path

    def test_stale_chain_head_refuses(self):
        m, path = self.f.manifest()
        self.f.commit(text="the chain moved under the census")
        with self.assertRaises(R.ReplayRefusal) as cm:
            R.apply(self.f.db, path)
        self.assertEqual(cm.exception.name, "stale_chain_head")

    def test_different_ledger_instance_refuses(self):
        self._apply_expecting(
            "ledger_instance_changed",
            lambda m: m["target_ledger"].update(instance_anchor="f" * 64))

    def test_target_path_mismatch_refuses(self):
        self._apply_expecting(
            "target_ledger_mismatch",
            lambda m: m["target_ledger"].update(realpath="/var/tmp/not-this-one.db"))

    def test_unknown_manifest_version_refuses(self):
        self._apply_expecting(
            "manifest_version_unknown",
            lambda m: m.update(manifest_version=999))

    def test_unanchored_ledger_refuses(self):
        """A ledger with no genesis_hash cannot bind a census to an
        INSTANCE, so the census might describe a different ledger's life."""
        bare = _Fixture("bare")
        m, path = self.f.manifest()
        m["target_ledger"]["realpath"] = os.path.realpath(bare.db)
        Path(path).write_text(json.dumps(m), encoding="utf-8")
        conn = sqlite3.connect(bare.db)
        try:
            conn.execute("DELETE FROM meta WHERE key='genesis_hash'")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(R.ReplayRefusal) as cm:
            R.apply(bare.db, path)
        self.assertEqual(cm.exception.name, "ledger_instance_unanchored")

    def test_refusal_before_consumption_leaves_the_manifest_usable(self):
        """A binding refusal must not spend the document — it is the right
        document for the right ledger, refused against the wrong one."""
        path = self._apply_expecting(
            "target_ledger_mismatch",
            lambda m: m["target_ledger"].update(realpath="/var/tmp/elsewhere.db"))
        self.assertTrue(Path(path).exists())

    def test_manifest_is_single_use(self):
        m, path = self.f.manifest()
        first = R.apply(self.f.db, path)
        self.assertEqual(first["counts"], {
            "body_published": 1,
            # Two-pass, against an OBSERVED commit: nothing has drained,
            # so the companion is deferred rather than assumed.
            "companion:companion_deferred_body_not_committed": 1,
        })
        self.assertFalse(Path(path).exists(), "manifest was not consumed")
        self.assertTrue(
            Path(first["manifest_consumed"]).exists(),
            "the spent manifest must remain as evidence")
        with self.assertRaises(FileNotFoundError):
            R.apply(self.f.db, path)

    def test_apply_lock_refuses_a_concurrent_run(self):
        m, path = self.f.manifest()
        lock_root = Path(R.manifest_root(self.f.db))
        lock_root.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock_root / "replay.apply.lock"),
                     os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with self.assertRaises(R.ReplayRefusal) as cm:
                R.apply(self.f.db, path)
            self.assertEqual(cm.exception.name, "apply_lock_held")
        finally:
            os.close(fd)
        self.assertTrue(Path(path).exists(),
                        "a lock refusal must not spend the manifest")

    def test_edited_record_bytes_refuse_by_name(self):
        m, path = self.f.manifest()
        m["census"][0]["record_digest"] = "0" * 64
        Path(path).write_text(json.dumps(m), encoding="utf-8")
        report = R.apply(self.f.db, path)
        outcome = next(iter(report["outcomes"].values()))
        self.assertEqual(outcome["refusal"], "record_digest_mismatch")

    def test_disposition_change_refuses_by_name(self):
        """The census said replayable; if the live classifier disagrees at
        apply time, that mutation refuses — eligibility comes only from
        the disposition, and the disposition moved."""
        m, path = self.f.manifest()
        sid = m["selected"]["bodies"][0]
        rec = next(r for r in self.f.records() if r["event_id"] == sid)
        kw = dict(rec["kwargs"])
        kw.pop("submission_id", None)
        kw.pop("parent_turn_id", None)
        spool.enqueue_reconstructed(
            self.f.spool_root, submission_id=sid, submitted_at=rec["ts"],
            producer="dead_letter_replay", turn_kind=rec["turn_kind"],
            raw_text=rec["raw_text"], kwargs=kw)
        report = R.apply(self.f.db, path)
        self.assertEqual(report["outcomes"][sid]["refusal"], "disposition_changed")


class BodyReconstructionTests(unittest.TestCase):
    def setUp(self):
        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)
        self.f = _Fixture("body")
        self.f.commit(text="anchor")

    def test_body_preserves_the_five_fields_exactly_through_drain(self):
        """turn_kind, surface, raw_surface (INCLUDING None), taint_labels
        and privacy_access survive byte-exact. Executed round seven: the
        writer passes ``raw_surface or surface`` as caller authority into
        the closed taint validator, so overwriting raw_surface with the
        replay marker can make the organ refuse its own replay."""
        rec = self.f.dead_letter(
            kind="model_reply", text="preserved speech",
            surface="web_owner", raw_surface=None,
            privacy_access="sealed_adjacent")
        m, path = self.f.manifest()
        R.apply(self.f.db, path)
        self.f.drain()
        rows = self.f.rows(rec["event_id"])
        self.assertEqual(len(rows), 1)
        kind, surface, raw_surface, taint, privacy, _p, _s, _t, text = rows[0]
        self.assertEqual(kind, "model_reply")
        self.assertEqual(surface, "web_owner")
        self.assertIsNone(raw_surface, "raw_surface=None must survive as None")
        self.assertEqual(json.loads(taint), ["self_generated"])
        self.assertEqual(privacy, "sealed_adjacent")
        self.assertEqual(text, "preserved speech")

    def test_authority_kwargs_are_relocated_not_passed_through(self):
        """EXECUTED hazard: every owner-path record carries submission_id
        (setdefault-ed before the attempt) and usually parent_turn_id, both
        of which are spool._AUTHORITY_KWARGS. A verbatim enqueue is
        QUARANTINED at drain — and a quarantine is terminal."""
        parent = self.f.commit(text="the question")
        rec = self.f.dead_letter(kind="model_reply", text="the answer",
                                 parent_turn_id=parent)
        self.assertIn("submission_id", rec["kwargs"])
        self.assertIn("parent_turn_id", rec["kwargs"])
        m, path = self.f.manifest()
        R.apply(self.f.db, path)
        drained = self.f.drain()
        self.assertEqual(drained["refused"], 0, "the body was quarantined")
        self.assertEqual(drained["acked"], 1)
        row = self.f.rows(rec["event_id"])[0]
        self.assertEqual(row[5], parent, "the parent edge must be REAL")

    def test_stranded_authority_kwarg_refuses_by_name(self):
        """tenant_id, birth_anchor, meta_marker_keys and lifecycle_stage
        have nowhere lawful to go: birth and tenancy travel through no
        transport, ever."""
        rec = self.f.dead_letter(text="a life with tenancy authority",
                                 tenant_id="somebody_else")
        m, path = self.f.manifest()
        report = R.apply(self.f.db, path)
        out = report["outcomes"][rec["event_id"]]
        self.assertEqual(out["refusal"], "authority_kwarg_inexpressible")
        self.assertIn("tenant_id", out["detail"])

    def test_unresolvable_parent_refuses_by_name(self):
        """Replaying unparented would assert this speech had no parent,
        and append-only forbids binding it later (standing block 2)."""
        rec = self.f.dead_letter(
            text="a child of a lost parent",
            parent_turn_id="00000000-0000-4000-8000-000000000000")
        m, path = self.f.manifest()
        report = R.apply(self.f.db, path)
        out = report["outcomes"][rec["event_id"]]
        self.assertEqual(out["refusal"], "parent_identity_unavailable")
        self.assertEqual(self.f.rows(rec["event_id"]), [],
                         "nothing may commit for a refused mutation")

    def test_parent_refusal_is_kind_blind(self):
        """MANDATORY flip test. The refusal predicate names no turn_kind,
        and must fire identically for every kind. The RED control this
        guards: letting the door decide instead protects tool_result by
        schema accident (it REQUIRES a parent) while silently committing
        an unparented model_reply with a false lineage."""
        kinds = ["user_message", "model_reply", "tool_call", "tool_result",
                 "daemon_cycle", "peer_message_in", "peer_message_out",
                 "system_event"]
        seen = {}
        for kind in kinds:
            f = _Fixture(f"parentflip_{kind}")
            f.commit(text="anchor")
            rec = f.dead_letter(
                kind=kind, text="a child of a lost parent",
                parent_turn_id="00000000-0000-4000-8000-000000000000")
            _, path = f.manifest()
            report = R.apply(f.db, path)
            seen[kind] = report["outcomes"][rec["event_id"]].get("refusal")
        self.assertEqual(
            set(seen.values()), {"parent_identity_unavailable"},
            f"the refusal moved with turn_kind: {seen}")

    def test_body_clock_is_the_record_clock_and_commit_is_later(self):
        """Split clocks. The body's lived time is the record's ts; the
        commit timestamp is when it entered the record. Never backdated,
        never fabricated forward."""
        rec = self.f.dead_letter(text="a life with a clock")
        _, path = self.f.manifest()
        R.apply(self.f.db, path)
        self.f.drain()
        row = self.f.rows(rec["event_id"])[0]
        self.assertEqual(row[6], rec["ts"], "submitted_at must be the record ts")
        self.assertGreater(row[7], row[6], "commit must be later than lived")

    def test_body_clock_is_what_makes_a_replay_distinguishable(self):
        """The causation discriminator, executed: an ORIGINAL owner-direct
        write leaves submitted_at NULL, a reconstructed body never does.
        A NULL body clock would erase the only durable row-side evidence
        that a row is a replay rather than a timeout-after-commit."""
        original = self.f.commit(text="an original life")
        conn = sqlite3.connect(f"file:{self.f.db}?mode=ro", uri=True)
        try:
            self.assertIsNone(
                conn.execute("SELECT submitted_at FROM turns WHERE turn_id=?",
                             (original,)).fetchone()[0])
        finally:
            conn.close()
        rec = self.f.dead_letter(text="a replayed life")
        _, path = self.f.manifest()
        R.apply(self.f.db, path)
        self.f.drain()
        self.assertIsNotNone(self.f.rows(rec["event_id"])[0][6])


class CompanionTests(unittest.TestCase):
    def setUp(self):
        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)
        self.f = _Fixture("companion")
        self.f.commit(text="anchor")

    def _replay_and_drain(self, **kw):
        rec = self.f.dead_letter(**kw)
        _, path = self.f.manifest()
        R.apply(self.f.db, path)
        self.f.drain()
        return rec

    def test_companion_is_not_a_child_and_carries_the_marker(self):
        """Ninth round Q-C, 2-1: parent_turn_id stays NULL. An annotation
        edge would surface inside conversation spans and read as dialogue.
        The RED control the majority refused: a parent_submission_id on a
        companion DOES become a stored parent edge."""
        rec = self._replay_and_drain(text="annotated speech")
        _, path = self.f.manifest()
        R.apply(self.f.db, path)
        self.f.drain()
        csid = R.companion_submission_id(rec["event_id"])
        row = self.f.rows(csid)[0]
        self.assertEqual(row[0], "system_event")
        self.assertEqual(row[2], "dead_letter_replay")
        self.assertEqual(json.loads(row[3]), ["self_generated"])
        self.assertIsNone(row[5], "the companion must NOT be a child")

    def test_companion_inherits_the_body_privacy(self):
        """A note about a turn must never be more visible than the turn."""
        rec = self._replay_and_drain(text="sealed speech",
                                     privacy_access="sealed_adjacent")
        _, path = self.f.manifest()
        R.apply(self.f.db, path)
        self.f.drain()
        csid = R.companion_submission_id(rec["event_id"])
        self.assertEqual(self.f.rows(csid)[0][4], "sealed_adjacent")

    def test_companion_clock_is_replay_time_never_backdated(self):
        before = time.time()
        rec = self._replay_and_drain(text="a clock of its own")
        _, path = self.f.manifest()
        R.apply(self.f.db, path)
        self.f.drain()
        csid = R.companion_submission_id(rec["event_id"])
        companion_clock = self.f.rows(csid)[0][6]
        self.assertGreaterEqual(companion_clock, before)
        self.assertGreater(companion_clock, rec["ts"],
                           "the companion happened NOW, not when the body did")

    def test_companion_sid_is_deterministic_and_distinguishable(self):
        a = R.companion_submission_id("f" * 32)
        self.assertEqual(a, R.companion_submission_id("f" * 32))
        self.assertNotEqual(a, R.companion_submission_id("e" * 32))
        self.assertEqual(len(a), 64, "distinguishable from a 32-char uuid4 hex")

    def test_constructor_refuses_a_companion_carrying_copied_content(self):
        """ORGAN-LEVEL refusal, required by ninth round Q-D: content-
        lightness is enforced, not hoped. Copying content would make the
        companion's truthful taint 'original + self_generated', which the
        frozen system_event vocabulary cannot express."""
        record = {"event_id": "a" * 32, "ts": 1.0, "stage": "write",
                  "turn_kind": "model_reply", "raw_text": "the secret words",
                  "kwargs": {"surface": "web_owner"}}
        row = ("turn-1", 3, "c" * 64, "public")
        good = R.build_companion(record=record, body_submission_id="a" * 32,
                                 body_row=row, run_id="r1", replayed_at=2.0)
        payload = json.loads(good["raw_text"])
        self.assertNotIn("the secret words", good["raw_text"])

        with patch.object(R, "_COMPANION_PAYLOAD_KEYS",
                          R._COMPANION_PAYLOAD_KEYS | {"source_file"}):
            pass  # keys unchanged; the two refusals below are the point

        # (1) a whitelisted field filled with body content
        smuggled = dict(payload, source_file="the secret words")
        with self.assertRaises(R.ReplayRefusal) as cm:
            R._refuse_copied_content(smuggled, record)
        self.assertEqual(cm.exception.name, "companion_not_content_light")

        # (2) a NEW field nobody whitelisted
        with self.assertRaises(R.ReplayRefusal) as cm:
            R._refuse_copied_content(dict(payload, raw_text="anything"), record)
        self.assertEqual(cm.exception.name, "companion_not_content_light")

    def test_companion_copied_kwargs_value_is_refused(self):
        record = {"event_id": "a" * 32, "ts": 1.0, "stage": "write",
                  "turn_kind": "user_message", "raw_text": "x",
                  "kwargs": {"surface": "a_distinctive_surface_name"}}
        payload = json.loads(R.build_companion(
            record=record, body_submission_id="a" * 32,
            body_row=("t", 1, "c" * 64, "public"),
            run_id="r", replayed_at=2.0)["raw_text"])
        with self.assertRaises(R.ReplayRefusal):
            R._refuse_copied_content(
                dict(payload, source_file="a_distinctive_surface_name"), record)

    def test_companion_makes_no_delivery_claim(self):
        """The substrate captures no delivery evidence for ANY turn. A
        per-row field whose value is constant would advertise a
        discriminating capability that does not exist, and imply by
        omission that unstamped rows have evidence. Only the NAMED
        limitation travels."""
        rec = self._replay_and_drain(kind="model_reply", text="unheard words")
        _, path = self.f.manifest()
        R.apply(self.f.db, path)
        self.f.drain()
        csid = R.companion_submission_id(rec["event_id"])
        payload = json.loads(self.f.rows(csid)[0][8])
        self.assertNotIn("delivery_evidence", payload)
        self.assertIn("delivery_evidence_unavailable", payload["limitations"])
        self.assertNotIn("delivered", json.dumps(payload).lower())

    def test_companion_cannot_name_the_kind_it_annotates(self):
        """Kind-blindness made structural: no downstream reader can build
        a kind filter out of a field the companion does not carry."""
        self.assertNotIn("body_turn_kind", R._COMPANION_PAYLOAD_KEYS)
        rec = self._replay_and_drain(kind="model_reply", text="kindless note")
        _, path = self.f.manifest()
        R.apply(self.f.db, path)
        self.f.drain()
        payload = json.loads(
            self.f.rows(R.companion_submission_id(rec["event_id"]))[0][8])
        self.assertNotIn("model_reply", json.dumps(payload))


class CrashCompletenessTests(unittest.TestCase):
    """Standing block 7, both directions, plus exactly-once throughout."""

    def setUp(self):
        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)
        self.f = _Fixture("crash")
        self.f.commit(text="anchor")

    def test_body_committed_companion_missing_enqueues_only_the_companion(self):
        """The named window: 'a crash after body commit but before
        companion enqueue must enqueue the missing companion, not skip
        the record as already_committed'."""
        rec = self.f.dead_letter(text="a half-finished restoration")
        _, path = self.f.manifest()
        R.apply(self.f.db, path)
        self.f.drain()                       # body commits; then we "crash"

        m2, path2 = self.f.manifest()
        self.assertEqual(m2["selected"]["bodies"], [],
                         "the body must NOT be re-enqueued")
        self.assertEqual(m2["selected"]["companions"], [rec["event_id"]])
        report = R.apply(self.f.db, path2)
        self.assertEqual(report["outcomes"][rec["event_id"]]["outcome"],
                         "companion_published")
        self.f.drain()
        self.assertEqual(len(self.f.rows(rec["event_id"])), 1)
        self.assertEqual(
            len(self.f.rows(R.companion_submission_id(rec["event_id"]))), 1)

    def test_phantom_commit_never_gets_a_companion(self):
        """A record that is already_committed because the ORIGINAL owner
        write landed must NOT get a replay companion — that would be a
        false claim that the row was replayed. Executed council attack
        (Codex, xhigh): publishing a replay-producer envelope for such an
        identity must not flip the disposition."""
        rec = self.f.dead_letter(text="the twice-told life")
        self.f.commit(text="the twice-told life",
                      submission_id=rec["event_id"])   # the write DID land
        entry = next(e for e in R.classify(self.f.db)["records"]
                     if e["event_id"] == rec["event_id"])
        self.assertEqual(entry["disposition"], "already_committed")

        # the attack: publish and drain a replay envelope under that sid
        kw = dict(rec["kwargs"])
        kw.pop("submission_id", None)
        kw.pop("parent_turn_id", None)
        spool.enqueue_reconstructed(
            self.f.spool_root, submission_id=rec["event_id"],
            submitted_at=rec["ts"], producer="dead_letter_replay",
            turn_kind=rec["turn_kind"], raw_text=rec["raw_text"], kwargs=kw)
        self.f.drain()
        entry = next(e for e in R.classify(self.f.db)["records"]
                     if e["event_id"] == rec["event_id"])
        self.assertEqual(
            entry["disposition"], "already_committed",
            "custody is not causation: an envelope's existence must not "
            "convert a phantom into a replay")
        self.assertIn("NULL submitted_at", entry["causation_check"])
        m, path = self.f.manifest()
        self.assertEqual(m["selected"]["companions"], [])

    def test_kill_between_the_two_passes_is_resumable(self):
        rec = self.f.dead_letter(text="interrupted between passes")
        _, path = self.f.manifest()
        with patch.object(R, "_apply_one_companion",
                          side_effect=KeyboardInterrupt("killed")):
            with self.assertRaises(KeyboardInterrupt):
                R.apply(self.f.db, path)
        self.f.drain()
        _, path2 = self.f.manifest()
        report = R.apply(self.f.db, path2)
        self.assertEqual(report["outcomes"][rec["event_id"]]["outcome"],
                         "companion_published")

    def test_kill_between_publication_and_ack_stays_exactly_once(self):
        """The spool's own redrive path owns this window: the receipt is
        written before the envelope moves, so a crash leaves the envelope
        pending and the next pass re-resolves by identity (UNIQUE)."""
        rec = self.f.dead_letter(text="committed but unacked")
        _, path = self.f.manifest()
        R.apply(self.f.db, path)
        with patch.object(spool, "_ack",
                          side_effect=RuntimeError("killed before ack")):
            self.f.drain()
        self.assertEqual(len(self.f.rows(rec["event_id"])), 1)
        self.assertEqual(
            spool._submission_exists(self.f.spool_root, "dead_letter_replay",
                                     rec["event_id"]), "pending")
        self.f.drain()                                   # redrive completes it
        self.assertEqual(len(self.f.rows(rec["event_id"])), 1,
                         "the redrive must not duplicate a life")
        self.assertEqual(
            spool._submission_exists(self.f.spool_root, "dead_letter_replay",
                                     rec["event_id"]), "acked")

    def test_redrive_twice_is_exactly_once(self):
        rec = self.f.dead_letter(text="driven three times")
        _, path = self.f.manifest()
        R.apply(self.f.db, path)
        for _ in range(3):
            self.f.drain()
        _, path2 = self.f.manifest()
        R.apply(self.f.db, path2)
        for _ in range(3):
            self.f.drain()
        self.assertEqual(len(self.f.rows(rec["event_id"])), 1)
        self.assertEqual(
            len(self.f.rows(R.companion_submission_id(rec["event_id"]))), 1)
        m3, _ = self.f.manifest()
        self.assertEqual(m3["selected"], m3["selected"] | {
            "bodies": [], "companions": []})

    def test_replaying_a_second_time_publishes_nothing_new(self):
        rec = self.f.dead_letter(text="already published")
        _, path = self.f.manifest()
        R.apply(self.f.db, path)
        # A second manifest built before any drain sees already_enqueued.
        m2, path2 = self.f.manifest()
        self.assertEqual(m2["selected"]["bodies"], [])
        self.assertEqual(
            next(e["disposition"] for e in m2["census"]
                 if e["event_id"] == rec["event_id"]),
            "already_enqueued")


class TerminalRefusalTests(unittest.TestCase):
    """A door refusal is permanent: the envelope sits in refused/, where
    _submission_exists still finds it, so no second envelope can ever be
    published under that identity. Reporting that as 'already_enqueued'
    named a grave 'in flight'."""

    def setUp(self):
        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)
        self.f = _Fixture("terminal")
        self.f.commit(text="anchor")

    def _refused_body(self):
        with _enabled(), patch.object(
            ledger_writer.LedgerWriter, "write_turn",
            side_effect=OSError("disk went away"),
        ):
            ledger_owner.owner_write_turn(
                self.f.db, "model_reply", "an incomplete reply",
                surface="web_owner", raw_surface=None, model_id="maez-local",
                taint_labels=["self_generated"], privacy_access="public")
        rec = self.f.records()[-1]
        _, path = self.f.manifest()
        R.apply(self.f.db, path)
        self.f.drain()
        return rec

    def test_door_refusal_is_reported_as_terminal_with_the_doors_reason(self):
        rec = self._refused_body()
        entry = next(e for e in R.classify(self.f.db)["records"]
                     if e["event_id"] == rec["event_id"])
        self.assertEqual(entry["disposition"], "replay_refused")
        self.assertIn("prompt_hash", entry["refusal_reason"])
        self.assertIn("terminal", entry["reason"])

    def test_a_terminally_refused_record_is_never_reselected(self):
        rec = self._refused_body()
        m, _ = self.f.manifest()
        self.assertEqual(m["selected"]["bodies"], [])
        self.assertEqual(m["selected"]["companions"], [])
        self.assertEqual(m["census_counts"].get("replay_refused"), 1)
        self.assertIsNone(m["census_counts"].get("already_enqueued"))

    def test_an_ack_against_a_different_kind_is_not_our_replay(self):
        """The writer's idempotent-redrive branch compares ONLY raw_text
        (writer.py's IntegrityError handler), so an envelope can ACK
        against an existing row of a DIFFERENT turn_kind that happens to
        share the identity and the text. Executed by a council seat
        (Codex, xhigh, 2026-08-26) and reproduced here: 'a filename,
        producer directory, SID and ACK receipt prove custody and identity
        resolution; they do not prove which mutation created the row.'

        So the causation predicate compares the committed row's PAYLOAD to
        the envelope we published, not just its clock.
        """
        shared_sid = "c0ffee" * 5 + "ab"
        shared_text = "one text, two kinds"
        lived = 1_700_000_000.0

        # Someone else's submission commits first, under that identity,
        # with a clock our envelope will also carry.
        spool.enqueue_reconstructed(
            self.f.spool_root, submission_id=shared_sid, submitted_at=lived,
            producer="web", turn_kind="user_message", raw_text=shared_text,
            kwargs={"surface": "web_owner",
                    "taint_labels": ["owner_utterance"],
                    "privacy_access": "public"})
        self.f.drain()
        row = self.f.rows(shared_sid)[0]
        self.assertEqual(row[0], "user_message")
        self.assertEqual(row[6], lived)

        # Our organ publishes a system_event body under the same identity
        # and the same text; the door ACKs it to the existing row.
        envelope = {"submission_id": shared_sid, "submitted_at": lived,
                    "turn_kind": "system_event", "raw_text": shared_text}
        is_ours, why = R._row_is_our_replay(self.f.db, envelope)
        self.assertFalse(
            is_ours,
            "an ack against a row of another kind must not read as our replay")
        self.assertIn("payload", why)
