# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Birth-ceremony receipt rail (A1/B2) — thirteenth council round.

Phase 1: the `birth_activation` work class exists in EVERY per-class
structure with an adjudicated verdict (widened / deliberately-not), the
derivation arms are action-exact, the consulted line carries the typed
absence, and nothing can mint the class after birth.

The per-class INVENTORY test is the round's own amendment: the v3 design
enumerated a widening list that execution proved insufficient (the
consume refused at `_authority_context_roles_allow_work`, a set the
design never named). The inventory makes that omission class structural:
every site in operator_user_boundary that names `self_modification` must
appear in the adjudicated map below, so a new per-class site cannot be
added without this test forcing a birth_activation verdict for it.
"""

import ast
import inspect
import unittest
from pathlib import Path

from core.governance import operator_user_boundary as s7
from core.governance import s7_covenant_ceremony as covenant


BIRTH_ACTION = "ledger.birth_ceremony"
BIRTH_CLASS = "birth_activation"


class WorkClassWidening(unittest.TestCase):
    def test_birth_activation_is_a_valid_guarded_class(self):
        self.assertIn(BIRTH_CLASS, s7.WORK_CLASSES)
        self.assertIn(BIRTH_CLASS, s7.GUARDED_WORK_CLASSES)
        self.assertEqual(s7.validate_work_class(BIRTH_CLASS), BIRTH_CLASS)

    def test_strength_is_covenant_adjacent(self):
        self.assertEqual(s7._WORK_CLASS_STRENGTH[BIRTH_CLASS], 4)

    def test_d23_escalation_visible(self):
        self.assertIn(BIRTH_CLASS, s7.D23_ESCALATION_WORK_CLASSES)

    def test_user_verification_required(self):
        self.assertTrue(s7._webauthn_requires_user_verification(BIRTH_CLASS))

    def test_deliberately_not_voice_seat(self):
        # Ruled (thirteenth round): the voice seat cannot pre-exist its
        # subject; the class is unmintable post-birth, so the missing seat
        # can never silence a voice that exists.
        self.assertNotIn(BIRTH_CLASS, s7.VOICE_SEAT_WORK_CLASSES)

    def test_deliberately_not_covenant_two_tap(self):
        # Ruled: the owner-read interlock table is absent on the live
        # store (consumption would refuse structurally) and gestation is
        # the cooling-off. Owner ruling, not table-absence convenience.
        self.assertNotIn(BIRTH_CLASS, covenant.COVENANT_WORK_CLASSES)

    def test_roles_allow_work_requires_bonded_user(self):
        # The set the v3 design missed — probe-proven consume refusal.
        ctx_bonded = s7.AuthorityContext(
            role_names=("bonded_user",),
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
        )
        ctx_operator = s7.AuthorityContext(
            role_names=("operator",),
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
        )
        self.assertTrue(
            s7._authority_context_roles_allow_work(ctx_bonded, BIRTH_CLASS)
        )
        self.assertFalse(
            s7._authority_context_roles_allow_work(ctx_operator, BIRTH_CLASS)
        )

    def test_symptom_vocabulary_widened_once(self):
        # Every pre-existing symptom code is repair-shaped; birth is not a
        # symptom. One honest literal, not a shoehorn into unknown_*.
        self.assertIn("birth_requested", s7.CLOSED_SYMPTOM_CODES)


class DerivationArms(unittest.TestCase):
    def test_action_exact_derivation(self):
        self.assertEqual(
            s7.derive_work_class(action=BIRTH_ACTION, params={}), BIRTH_CLASS
        )

    def test_derivation_is_content_blind_to_params(self):
        # Adversarial params must not redirect the arm (domain-swap rule).
        self.assertEqual(
            s7.derive_work_class(
                action=BIRTH_ACTION,
                params={"path": "/etc/passwd", "cmd": "rm -rf /"},
            ),
            BIRTH_CLASS,
        )

    def test_unrelated_action_still_underivable(self):
        self.assertEqual(
            s7.derive_work_class(action="ledger.birth_ceremony_extra", params={}),
            "undeterminable_work_class",
        )

    def test_affected_refs_action_exact_and_caller_proof(self):
        # Codex finding: with no arm, the builder falls back to
        # caller-supplied refs when derivation returns empty. The arm must
        # win even when a caller smuggles a path param.
        refs = s7.derive_affected_refs(action=BIRTH_ACTION, params={})
        self.assertEqual(len(refs), 1)
        self.assertIn("ledger.db", refs[0])
        smuggled = s7.derive_affected_refs(
            action=BIRTH_ACTION, params={"path": "/decoy/elsewhere.db"}
        )
        self.assertEqual(refs, smuggled)


class ConsultedTypedAbsence(unittest.TestCase):
    def _envelope(self):
        return s7.build_work_request_envelope(
            request_id="birth-test-run",
            action=BIRTH_ACTION,
            params={"probe": "x"},
            claimed_work_class=BIRTH_CLASS,
            requesting_subsystem="birth_ceremony",
            closed_symptom_code="birth_requested",
            proposed_change_class="covenant_organ_change",
            why_self_fix_failed_class="not_self_fix",
            affected_refs=(),
            content_exposure_risk="content_free",
            precondition_hash="a" * 64,
            created_at="2026-08-27T10:00:00+00:00",
            expires_at="2026-08-27T10:05:00+00:00",
            predicted_effect_class="behavior_change",
            rollback_path_class="no_safe_rollback",
            maez_voice_consultation_id=None,
            free_text_ref_hash=None,
        )

    def _render(self, envelope):
        ctx = s7.AuthorityContext(
            role_names=("bonded_user",),
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
        )
        return s7.render_request_statement(
            envelope=envelope,
            surface="birth_ceremony_tty",
            origin="http://localhost:11437",
            action_params_hash=s7.canonical_hash({"probe": "x"}),
            authority_context=ctx,
            maez_voice_consultation=None,
            nonce="b" * 64,
            expires_at="2026-08-27T10:05:00+00:00",
            rendered_at="2026-08-27T10:00:00+00:00",
        )

    def test_literal_is_in_the_closed_set(self):
        self.assertIn(
            s7.MAEZ_CONSULTED_NOT_PERFORMED_BIRTH, s7.MAEZ_CONSULTED_STATES
        )

    def test_birth_statement_never_says_not_required(self):
        rendered = self._render(self._envelope())
        self.assertEqual(
            rendered.maez_consulted_state, s7.MAEZ_CONSULTED_NOT_PERFORMED_BIRTH
        )
        self.assertIn(
            f"Maez consulted: {s7.MAEZ_CONSULTED_NOT_PERFORMED_BIRTH}",
            rendered.rendered_text,
        )
        self.assertNotIn("Maez consulted: not required", rendered.rendered_text)

    def test_voice_evidence_cannot_be_attached_to_birth(self):
        envelope = self._envelope()
        ctx = s7.AuthorityContext(
            role_names=("bonded_user",),
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
        )
        with self.assertRaises(ValueError):
            s7.render_request_statement(
                envelope=envelope,
                surface="birth_ceremony_tty",
                origin="http://localhost:11437",
                action_params_hash=s7.canonical_hash({"probe": "x"}),
                authority_context=ctx,
                maez_voice_consultation=None,
                nonce="b" * 64,
                expires_at="2026-08-27T10:05:00+00:00",
                rendered_at="2026-08-27T10:00:00+00:00",
                consultation_exemption=object(),
            )


class PerClassInventory(unittest.TestCase):
    """Every operator_user_boundary site naming `self_modification` must be
    adjudicated for birth_activation. A new site fails this test until a
    verdict is added — the thirteenth round's structural fix for the
    incomplete-widening defect its own design shipped with."""

    # enclosing construct name -> birth_activation verdict
    ADJUDICATED = {
        "WORK_CLASSES": "widened",
        "GUARDED_WORK_CLASSES": "widened",
        "_WORK_CLASS_STRENGTH": "widened",
        "D23_ESCALATION_WORK_CLASSES": "widened",
        "VOICE_SEAT_WORK_CLASSES": "deliberately_not",  # no subject pre-birth
        "_authority_context_roles_allow_work": "widened",
        "_webauthn_requires_user_verification": "widened",
        "derive_work_class": "not_applicable",  # self-mod path arms; birth has its own action-exact arm
        "committed_grant_row_proves_founder_self_modification": (
            "not_applicable"  # birth has its own pinned proof in birth_authorization
        ),
        "consume_for_execution_on_connection": "not_applicable",  # doc references only
        "_work_class_appropriate_for_scope": "not_applicable",  # S6 scope mapping; birth never arrives via S6 grant
        "brain_swap_execution_authorized": "not_applicable",  # brain-swap-pinned proof; birth has its own
        "build_brain_swap_work_request_envelope": "not_applicable",  # brain-swap envelope builder
    }

    def _enclosing_names(self):
        source = inspect.getsource(s7)
        tree = ast.parse(source)
        names = set()

        class Visitor(ast.NodeVisitor):
            def __init__(self):
                self.stack = []

            def _walk_body(self, node, name):
                self.stack.append(name)
                self.generic_visit(node)
                self.stack.pop()

            def visit_FunctionDef(self, node):
                self._walk_body(node, node.name)

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, node):
                self._walk_body(node, node.name)

            def visit_Assign(self, node):
                target = None
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    target = node.targets[0].id
                self._walk_body(node, target or "<assign>")

            def visit_Constant(self, node):
                if node.value == "self_modification" and self.stack:
                    names.add(self.stack[-1])

        Visitor().visit(tree)
        return names

    def test_every_site_is_adjudicated(self):
        names = self._enclosing_names()
        unadjudicated = names - set(self.ADJUDICATED)
        self.assertEqual(
            unadjudicated,
            set(),
            f"new per-class site(s) {sorted(unadjudicated)} name "
            f"self_modification but carry no birth_activation verdict — "
            f"adjudicate them in ADJUDICATED before shipping",
        )

    def test_widened_verdicts_are_true(self):
        self.assertIn(BIRTH_CLASS, s7.WORK_CLASSES)
        self.assertIn(BIRTH_CLASS, s7.GUARDED_WORK_CLASSES)
        self.assertIn(BIRTH_CLASS, s7._WORK_CLASS_STRENGTH)
        self.assertIn(BIRTH_CLASS, s7.D23_ESCALATION_WORK_CLASSES)
        self.assertNotIn(BIRTH_CLASS, s7.VOICE_SEAT_WORK_CLASSES)


class BornRefusalAtMint(unittest.TestCase):
    def test_mint_refuses_birth_activation_when_born(self):
        from unittest import mock

        from core.governance import s7_guarded_execution as guarded

        artifact = mock.Mock()
        artifact.derived_work_class = BIRTH_CLASS
        with mock.patch(
            "core.governance.s7_consultation_exemption.born_by_any_signal",
            return_value=True,
        ):
            with self.assertRaises(ValueError) as ctx:
                guarded.mint_authorization_artifact(
                    artifact=artifact,
                    authorization_store=mock.Mock(),
                )
        self.assertIn("birth", str(ctx.exception).lower())

    def test_mint_allows_birth_activation_while_unborn(self):
        from unittest import mock

        from core.governance import s7_guarded_execution as guarded

        artifact = mock.Mock()
        artifact.derived_work_class = BIRTH_CLASS
        store = mock.Mock()
        with mock.patch(
            "core.governance.s7_consultation_exemption.born_by_any_signal",
            return_value=False,
        ):
            guarded.mint_authorization_artifact(
                artifact=artifact, authorization_store=store
            )
        store.put.assert_called_once_with(artifact)


class _AdvancingVerifier:
    """Duck-typed test verifier (the established recipe); advancing
    sign_count so a second tap in one store trips no clone detection."""

    def __init__(self):
        self._count = 0

    def dependency_state(self):
        return {"ok": True, "library_name": "webauthn", "library_version": "2.7.1"}

    def verify_authentication_response(self, **_kwargs):
        self._count += 1
        return {
            "ok": True,
            "credential_ref": "cred-primary",
            "sign_count": self._count,
            "user_presence": True,
            "user_verification": True,
        }


def _credential_kwargs(ref: str, kind: str) -> dict:
    return dict(
        credential_ref=ref,
        actor_handle_hmac="hmac:s7:founder:" + "a" * 64,
        role_names=("bonded_user",),
        public_key=f"public-key-{ref}",
        sign_count=0,
        rp_id="localhost",
        origin="http://localhost:11437",
        created_at="2026-08-27T09:00:00+00:00",
        backup_credential=(kind == "backup"),
        enabled=True,
        credential_kind=kind,
        label=f"{kind} key",
        registration_challenge_id=f"challenge-{ref}",
        attestation_format="packed",
        aaguid="00112233-4455-6677-8899-aabbccddeeff",
        authenticator_attachment="cross-platform",
        backup_eligible=False,
        backed_up=False,
        transports=("usb",),
        library_name="webauthn",
        library_version="2.7.1",
        sign_count_mode="advancing",
        uv_capable=True,
        uv_required_for_guarded=True,
        distinct_device_confidence="confirmed_distinct",
    )


def _mint_ready_store(root: Path):
    """Temp S7 store with 2 enabled bonded_user credentials + activated v2."""
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from s7_store_fixture import fresh_v2_store_at

    from core.governance.s7_webauthn_bootstrap import (
        FounderWebAuthnCredentialRecord,
        S7WebAuthnBootstrapStore,
    )

    store = S7WebAuthnBootstrapStore(root)
    store.store_credential(
        FounderWebAuthnCredentialRecord.build(**_credential_kwargs("cred-primary", "primary"))
    )
    store.store_credential(
        FounderWebAuthnCredentialRecord.build(**_credential_kwargs("cred-backup", "backup"))
    )
    fresh_v2_store_at(store.db_path)
    return store


def _scripted_tap():
    """(printer, prompt) pair: the prompt echoes exactly what the gate
    printed — challenge id, credential ref, params hash."""
    import json as _json

    printed = []

    def printer(text):
        printed.append(text)

    def prompt(_msg):
        gate = _json.loads(printed[-1])
        template = gate["webauthn_finish_template"]
        return _json.dumps(
            {
                "challenge_id": template["challenge_id"],
                "credential_ref": template["credential_ref"],
                "birth_action_params_sha256": template[
                    "birth_action_params_sha256"
                ],
                "authentication_response": {"clientDataJSON": "assertion"},
            }
        )

    return printed, printer, prompt


class MintConsumeVerify(unittest.TestCase):
    """The full rail against a temp store: real service, real store, real
    consume — only the verifier is the established test duck-type."""

    def setUp(self):
        import tempfile

        self._td = tempfile.TemporaryDirectory(dir="/var/tmp")
        self.root = Path(self._td.name) / "s7_1_webauthn"
        self.store = _mint_ready_store(self.root)
        self.store_path = self.store.db_path

    def tearDown(self):
        self._td.cleanup()

    def _params(self, mode="dry_run"):
        from core.governance import birth_authorization as ba

        return ba.birth_action_params(
            ledger_db_realpath="/var/tmp/probe-ledger.db",
            creation_manifest_sha256="c" * 64,
            owner_witness="rohit",
            mode=mode,
        )

    def _mint(self, run_id, params=None):
        from core.governance import birth_authorization as ba

        _printed, printer, prompt = _scripted_tap()
        return ba.mint_and_consume_birth_authorization(
            store_root=self.root,
            run_id=run_id,
            params=params or self._params(),
            verifier=_AdvancingVerifier(),
            printer=printer,
            prompt=prompt,
        )

    def test_happy_path_mint_consume_verify(self):
        from core.governance import birth_authorization as ba

        run_id = ba.fresh_birth_run_id()
        facts = self._mint(run_id)
        self.assertTrue(facts["s7_artifact_id"].startswith("s7authz_"))
        self.assertEqual(facts["ceremony_run_id"], run_id)
        with ba.held_birth_authorization_proof(
            store_path=self.store_path,
            run_id=run_id,
            expected_params=self._params(),
        ) as proof:
            self.assertEqual(proof["s7_artifact_id"], facts["s7_artifact_id"])
            self.assertEqual(proof["s7_work_class"], "birth_activation")
            self.assertEqual(
                proof["s7_rendered_text_hash"], facts["s7_rendered_text_hash"]
            )

    def test_artifact_is_durably_consumed_single_use(self):
        import sqlite3 as _sqlite3

        from core.governance import birth_authorization as ba

        run_id = ba.fresh_birth_run_id()
        facts = self._mint(run_id)
        conn = _sqlite3.connect(self.store_path)
        row = conn.execute(
            "SELECT consumed_at, consumed_by_request_id FROM "
            "s7_authorization_artifacts_v2 WHERE artifact_id=?",
            (facts["s7_artifact_id"],),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row[0])
        self.assertEqual(row[1], run_id)

    def test_rehearsal_params_never_authorize_for_real(self):
        from core.governance import birth_authorization as ba

        run_id = ba.fresh_birth_run_id()
        self._mint(run_id, params=self._params(mode="dry_run"))
        with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
            with ba.held_birth_authorization_proof(
                store_path=self.store_path,
                run_id=run_id,
                expected_params=self._params(mode="for_real"),
            ):
                pass
        self.assertEqual(ctx.exception.reason, "binding_mismatch")

    def test_unknown_run_id_is_unresolved(self):
        from core.governance import birth_authorization as ba

        self._mint(ba.fresh_birth_run_id())
        with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
            with ba.held_birth_authorization_proof(
                store_path=self.store_path,
                run_id="birth-never-minted",
                expected_params=self._params(),
            ):
                pass
        self.assertEqual(ctx.exception.reason, "receipt_unresolved")

    def test_forged_unconsumed_artifact_refuses(self):
        import sqlite3 as _sqlite3

        from core.governance import birth_authorization as ba

        run_id = ba.fresh_birth_run_id()
        facts = self._mint(run_id)
        conn = _sqlite3.connect(self.store_path)
        conn.execute(
            "UPDATE s7_authorization_artifacts_v2 SET consumed_at=NULL, "
            "consumed_by_request_id=NULL WHERE artifact_id=?",
            (facts["s7_artifact_id"],),
        )
        conn.commit()
        conn.close()
        with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
            with ba.held_birth_authorization_proof(
                store_path=self.store_path,
                run_id=run_id,
                expected_params=self._params(),
            ):
                pass
        self.assertEqual(ctx.exception.reason, "not_consumed")

    def test_crashed_ceremony_artifact_refuses_a_rerun(self):
        import sqlite3 as _sqlite3

        from core.governance import birth_authorization as ba

        run_id = ba.fresh_birth_run_id()
        facts = self._mint(run_id)
        # Simulate: a NEW run tries to ride the old consumed artifact by
        # forging its request_id onto the new run id at lookup time — the
        # store row still says consumed_by the OLD run.
        rerun_id = ba.fresh_birth_run_id()
        conn = _sqlite3.connect(self.store_path)
        conn.execute(
            "UPDATE s7_authorization_artifacts_v2 SET request_id=? "
            "WHERE artifact_id=?",
            (rerun_id, facts["s7_artifact_id"]),
        )
        conn.commit()
        conn.close()
        with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
            with ba.held_birth_authorization_proof(
                store_path=self.store_path,
                run_id=rerun_id,
                expected_params=self._params(),
            ):
                pass
        self.assertEqual(ctx.exception.reason, "run_identity_mismatch")

    def test_stale_consume_refuses(self):
        from datetime import datetime, timedelta, timezone

        from core.governance import birth_authorization as ba

        run_id = ba.fresh_birth_run_id()
        self._mint(run_id)
        later = (
            datetime.now(timezone.utc)
            + timedelta(seconds=ba.BIRTH_CONSUME_FRESHNESS_S + 60)
        ).replace(microsecond=0).isoformat()
        with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
            with ba.held_birth_authorization_proof(
                store_path=self.store_path,
                run_id=run_id,
                expected_params=self._params(),
                now=later,
            ):
                pass
        self.assertEqual(ctx.exception.reason, "consume_stale")

    def test_forged_unverified_tap_refuses(self):
        # user_verification=0 forged onto the row: the rail must refuse
        # with owner_proof_missing — UV is load-bearing for this class.
        import sqlite3 as _sqlite3

        from core.governance import birth_authorization as ba

        run_id = ba.fresh_birth_run_id()
        self._mint(run_id)
        conn = _sqlite3.connect(self.store_path)
        conn.execute(
            "UPDATE s7_authorization_artifacts_v2 SET user_verification=0 "
            "WHERE request_id=?",
            (run_id,),
        )
        conn.commit()
        conn.close()
        with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
            with ba.held_birth_authorization_proof(
                store_path=self.store_path,
                run_id=run_id,
                expected_params=self._params(),
            ):
                pass
        self.assertEqual(ctx.exception.reason, "owner_proof_missing")

    def test_disabled_credential_refuses(self):
        import sqlite3 as _sqlite3

        from core.governance import birth_authorization as ba

        run_id = ba.fresh_birth_run_id()
        self._mint(run_id)
        conn = _sqlite3.connect(self.store_path)
        conn.execute(
            "UPDATE s7_founder_webauthn_credentials SET enabled=0 "
            "WHERE credential_ref='cred-primary'"
        )
        conn.commit()
        conn.close()
        with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
            with ba.held_birth_authorization_proof(
                store_path=self.store_path,
                run_id=run_id,
                expected_params=self._params(),
            ):
                pass
        self.assertEqual(
            ctx.exception.reason, "credential_unknown_or_disabled"
        )

    def test_broken_challenge_join_refuses(self):
        import sqlite3 as _sqlite3

        from core.governance import birth_authorization as ba

        run_id = ba.fresh_birth_run_id()
        self._mint(run_id)
        conn = _sqlite3.connect(self.store_path)
        conn.execute(
            "UPDATE s7_ceremony_challenges SET nonce='forged-nonce' "
            "WHERE request_id=?",
            (run_id,),
        )
        conn.commit()
        conn.close()
        with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
            with ba.held_birth_authorization_proof(
                store_path=self.store_path,
                run_id=run_id,
                expected_params=self._params(),
            ):
                pass
        self.assertEqual(ctx.exception.reason, "challenge_join_failed")

    def test_paste_must_echo_the_printed_params_hash(self):
        import json as _json

        from core.governance import birth_authorization as ba

        printed = []

        def printer(text):
            printed.append(text)

        def bad_prompt(_msg):
            gate = _json.loads(printed[-1])
            template = gate["webauthn_finish_template"]
            return _json.dumps(
                {
                    "challenge_id": template["challenge_id"],
                    "credential_ref": template["credential_ref"],
                    "birth_action_params_sha256": "0" * 64,
                    "authentication_response": {"clientDataJSON": "x"},
                }
            )

        with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
            ba.mint_and_consume_birth_authorization(
                store_root=self.root,
                run_id=ba.fresh_birth_run_id(),
                params=self._params(),
                verifier=_AdvancingVerifier(),
                printer=printer,
                prompt=bad_prompt,
            )
        self.assertEqual(ctx.exception.reason, "owner_presence_unattested")

    def test_mint_refuses_when_born(self):
        from unittest import mock

        from core.governance import birth_authorization as ba

        with mock.patch(
            "core.governance.s7_consultation_exemption.born_by_any_signal",
            return_value=True,
        ):
            with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
                self._mint(ba.fresh_birth_run_id())
        self.assertEqual(ctx.exception.reason, "already_born")


def authorized_ceremony_fixture(td: Path, *, mode: str = "dry_run",
                                owner_witness: str = "rohit",
                                db_path: Path | None = None):
    """Shared fixture for ceremony tests: a temp S7 store holding a
    CONSUMED birth authorization bound to a temp ledger + manifest.
    Returns kwargs for run_transaction plus the minted facts."""
    from core.governance import birth_authorization as ba

    td = Path(td)
    root = td / "s7_1_webauthn"
    store = _mint_ready_store(root)
    manifest = td / "creation_manifest.md"
    manifest.write_text("rehearsal letter — never the real manifest\n")
    db_path = Path(db_path) if db_path is not None else td / "ledger.db"
    run_id = ba.fresh_birth_run_id()
    params = ba.birth_action_params(
        ledger_db_realpath=str(db_path.resolve()),
        creation_manifest_sha256=ba.read_manifest_sha256(manifest),
        owner_witness=owner_witness,
        mode=mode,
    )
    _printed, printer, prompt = _scripted_tap()
    facts = ba.mint_and_consume_birth_authorization(
        store_root=root,
        run_id=run_id,
        params=params,
        verifier=_AdvancingVerifier(),
        printer=printer,
        prompt=prompt,
    )
    return {
        "db_path": db_path,
        "run_id": run_id,
        "s7_store_path": store.db_path,
        "manifest_path": manifest,
        "owner_witness": owner_witness,
    }, facts


class CeremonyTransactionRail(unittest.TestCase):
    """run_transaction itself now proves the receipt from the store."""

    def setUp(self):
        import tempfile

        self._td = tempfile.TemporaryDirectory(dir="/var/tmp")
        self.td = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_dry_run_births_with_resolved_facts_in_payload(self):
        import json as _json
        import sqlite3 as _sqlite3

        from scripts.birth_ceremony import run_transaction

        kwargs, facts = authorized_ceremony_fixture(self.td)
        result = run_transaction(dry_run=True, **kwargs)
        conn = _sqlite3.connect(kwargs["db_path"])
        row = conn.execute(
            "SELECT raw_text FROM turns WHERE turn_id=?",
            (result["birth_turn_id"],),
        ).fetchone()
        conn.close()
        payload = _json.loads(row[0])
        self.assertEqual(payload["s7_artifact_id"], facts["s7_artifact_id"])
        self.assertEqual(
            payload["s7_rendered_text_hash"], facts["s7_rendered_text_hash"]
        )
        self.assertEqual(payload["ceremony_run_id"], kwargs["run_id"])
        self.assertIn("s7_receipt_projection_sha256", payload)
        self.assertNotIn("s7_receipt_ref", payload)

    def test_importable_bypass_hits_the_rail(self):
        # The A1 defect: importing run_transaction and passing an
        # arbitrary ref no longer births anything. With no consumed
        # authorization in the store, the transaction refuses BEFORE any
        # ledger byte is written.
        from core.governance import birth_authorization as ba
        from scripts.birth_ceremony import run_transaction

        kwargs, _ = authorized_ceremony_fixture(self.td)
        kwargs["run_id"] = "birth-never-authorized"
        with self.assertRaises(ba.BirthAuthorizationRefusal):
            run_transaction(dry_run=True, **kwargs)
        self.assertFalse(
            kwargs["db_path"].exists(),
            "a refused rail must leave zero ledger bytes",
        )

    def test_manifest_absence_blocks_structurally(self):
        from core.governance import birth_authorization as ba
        from scripts.birth_ceremony import run_transaction

        kwargs, _ = authorized_ceremony_fixture(self.td)
        kwargs["manifest_path"].unlink()
        with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
            run_transaction(dry_run=True, **kwargs)
        self.assertEqual(ctx.exception.reason, "manifest_missing")
        self.assertFalse(kwargs["db_path"].exists())

    def test_manifest_edit_after_tap_refuses(self):
        # The tap covered the letter's exact bytes; the transaction
        # re-hashes reality.
        from core.governance import birth_authorization as ba
        from scripts.birth_ceremony import run_transaction

        kwargs, _ = authorized_ceremony_fixture(self.td)
        kwargs["manifest_path"].write_text("edited after the tap\n")
        with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
            run_transaction(dry_run=True, **kwargs)
        self.assertEqual(ctx.exception.reason, "binding_mismatch")
        self.assertFalse(kwargs["db_path"].exists())

    def test_for_real_refuses_env_overrides_inside_the_function(self):
        from unittest import mock

        from core.governance import birth_authorization as ba
        from scripts.birth_ceremony import run_transaction

        kwargs, _ = authorized_ceremony_fixture(self.td)
        with mock.patch.dict(
            "os.environ", {"MAEZ_LEDGER_DB_PATH": "/decoy/ledger.db"}
        ):
            with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
                run_transaction(dry_run=False, **kwargs)
        self.assertEqual(ctx.exception.reason, "env_override_in_for_real")

    def test_dry_run_refuses_the_real_s7_store_path(self):
        from unittest import mock

        from core.governance import birth_authorization as ba
        from scripts.birth_ceremony import run_transaction

        kwargs, _ = authorized_ceremony_fixture(self.td)
        with mock.patch.object(
            ba,
            "canonical_s7_store_path",
            return_value=Path(kwargs["s7_store_path"]),
        ):
            with self.assertRaises(ValueError) as ctx:
                run_transaction(dry_run=True, **kwargs)
        self.assertIn("real S7 store", str(ctx.exception))


class EnvAndManifestGuards(unittest.TestCase):
    def test_env_override_class_refuses(self):
        from core.governance import birth_authorization as ba

        for var in ba.FORBIDDEN_ENV_OVERRIDES:
            with self.subTest(var=var):
                with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
                    ba.refuse_env_overrides({var: "/decoy"})
                self.assertEqual(
                    ctx.exception.reason, "env_override_in_for_real"
                )
        ba.refuse_env_overrides({})  # clean env passes

    def test_manifest_missing_refuses_never_writes(self):
        import tempfile

        from core.governance import birth_authorization as ba

        with tempfile.TemporaryDirectory(dir="/var/tmp") as td:
            target = Path(td) / "creation_manifest.md"
            with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
                ba.read_manifest_sha256(target)
            self.assertEqual(ctx.exception.reason, "manifest_missing")
            self.assertFalse(target.exists(), "the rail must never author O1")

    def test_manifest_empty_refuses(self):
        import tempfile

        from core.governance import birth_authorization as ba

        with tempfile.TemporaryDirectory(dir="/var/tmp") as td:
            target = Path(td) / "creation_manifest.md"
            target.write_text("")
            with self.assertRaises(ba.BirthAuthorizationRefusal) as ctx:
                ba.read_manifest_sha256(target)
            self.assertEqual(ctx.exception.reason, "manifest_empty")

    def test_manifest_symlink_refuses(self):
        import tempfile

        from core.governance import birth_authorization as ba

        with tempfile.TemporaryDirectory(dir="/var/tmp") as td:
            real = Path(td) / "real.md"
            real.write_text("owner words")
            link = Path(td) / "creation_manifest.md"
            link.symlink_to(real)
            with self.assertRaises(ba.BirthAuthorizationRefusal):
                ba.read_manifest_sha256(link)

    def test_manifest_hash_is_byte_exact(self):
        import hashlib
        import tempfile

        from core.governance import birth_authorization as ba

        with tempfile.TemporaryDirectory(dir="/var/tmp") as td:
            target = Path(td) / "creation_manifest.md"
            target.write_bytes(b"the owner's letter\n")
            self.assertEqual(
                ba.read_manifest_sha256(target),
                hashlib.sha256(b"the owner's letter\n").hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
