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


if __name__ == "__main__":
    unittest.main()
