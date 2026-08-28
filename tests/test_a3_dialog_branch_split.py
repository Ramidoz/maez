# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""A3 final slice — the dialog branch split at the PROVENANCE boundary.

Owner-ruled 2026-08-28. The split must NOT key on
``DialogTurnResult.kind``: that kind mixes model-generated
clarifications with the canned DEFER ack, so it cannot discriminate.
The generation path exports HOW its text was produced.

Both branches use the ratified kind ``self_mod_dialog_step`` — "one
turn within a Lane 3 self-modification dialog" — because the KIND says
what the event was while the optional model fields say how that step
was produced. Not ``model_reply``: that requires ``soul_hash``, and
this generation is NOT soul-bound (executed: its system prompt is a
dialog instruction; the soul appears only as the dialog's SUBJECT).
"""

from __future__ import annotations

import unittest


class TheSplitIsAtProvenanceNotKind(unittest.TestCase):
    def test_the_generation_path_exports_provenance(self):
        from skills.self_mod_dialog import (
            CANNED_PROVENANCE,
            DialogTurnProvenance,
            last_turn_provenance,
        )

        self.assertFalse(
            CANNED_PROVENANCE.is_model_generated,
            "the canned sentinel must not claim a model",
        )
        self.assertTrue(
            DialogTurnProvenance(
                model_id="m", prompt_material="p"
            ).is_model_generated
        )
        self.assertIsNotNone(last_turn_provenance())

    def test_the_deterministic_fallback_declares_no_model(self):
        """The exit reached when the LLM raises/returns blank."""
        from skills import self_mod_dialog as smd

        def _blank_llm(_ctx):
            return ""

        class _D:
            history = []

        text, _prompt = smd.generate_response_turn(
            dialog=_D(), user_text="hi",
            classifier_result={}, llm_fn=_blank_llm,
        )
        prov = smd.last_turn_provenance()
        self.assertTrue(text, "the fallback must still produce a reply")
        self.assertFalse(
            prov.is_model_generated,
            "the deterministic fallback claimed model provenance",
        )
        self.assertIsNone(prov.model_id)

    def test_a_model_exit_exports_the_exact_prompt(self):
        from skills import self_mod_dialog as smd

        seen = {}

        def _llm(ctx):
            seen["ctx"] = ctx
            return "I hear you, and I've changed my mind."

        class _D:
            history = []

        text, _p = smd.generate_response_turn(
            dialog=_D(), user_text="you're wrong",
            classifier_result={}, llm_fn=_llm,
        )
        prov = smd.last_turn_provenance()
        self.assertTrue(prov.is_model_generated)
        self.assertEqual(
            prov.prompt_material, seen["ctx"],
            "prompt_material must be the EXACT value the model received, "
            "never a reconstruction — the hash answers 'what actually "
            "shaped this generation'",
        )
        self.assertIn("changed my mind", text)


class TheSeamMethodIsNarrowlyTyped(unittest.TestCase):
    def test_it_writes_only_self_mod_dialog_step(self):
        import inspect

        from core.ledger import recorder

        src = inspect.getsource(recorder.record_self_mod_dialog_step)
        self.assertIn('"self_mod_dialog_step",', src)
        for forbidden in ("turn_kind=", "**kwargs", "event_origin"):
            self.assertNotIn(
                forbidden, src.split('"""')[-1],
                f"{forbidden} appeared — this is a narrowly typed method, "
                "not a generic passthrough",
            )

    def test_it_never_sets_soul_hash_or_evidence_envelope(self):
        import inspect

        from core.ledger import recorder

        body = inspect.getsource(recorder.record_self_mod_dialog_step)
        body = body.split('"""')[-1]
        self.assertNotIn(
            "soul_hash", body,
            "soul_hash was set — this generation is NOT soul-bound, and "
            "hashing the global soul would claim material that never "
            "entered the prompt",
        )
        self.assertNotIn(
            "evidence_envelope", body,
            "the schema restricts the envelope to model_reply / "
            "daemon_cycle / peer_message_out; its absence here is by "
            "design, not an omission",
        )

    def test_model_id_and_prompt_must_come_together(self):
        from core.ledger.recorder import record_self_mod_dialog_step

        with self.assertRaises(ValueError):
            record_self_mod_dialog_step(
                surface="telegram_text", raw_text="x",
                self_mod_dialog_id=1, audit_verdict={},
                model_id="qwen", prompt_material=None,
            )
        with self.assertRaises(ValueError):
            record_self_mod_dialog_step(
                surface="telegram_text", raw_text="x",
                self_mod_dialog_id=1, audit_verdict={},
                model_id=None, prompt_material="p",
            )

    def test_the_dialog_id_may_not_be_a_type_lie(self):
        from core.ledger.recorder import record_self_mod_dialog_step

        with self.assertRaises(TypeError):
            record_self_mod_dialog_step(
                surface="telegram_text", raw_text="x",
                self_mod_dialog_id="dlg-abc",  # TEXT id
                audit_verdict={},
            )

    def test_the_kind_is_ratified_for_exactly_this_path(self):
        """The schema's own contract is why this kind fits."""
        from core.ledger import writer

        req = writer._REQUIRED_FIELDS["self_mod_dialog_step"]
        self.assertEqual(
            set(req), {"raw_text", "audit_verdict", "self_mod_dialog_id"},
            "the required set changed; re-verify that this kind still "
            "fits a non-soul-bound dialog generation",
        )
        self.assertNotIn("soul_hash", req)
        self.assertNotIn("evidence_envelope", req)
        self.assertNotIn(
            "model_id", writer._FORBIDDEN_FIELDS["self_mod_dialog_step"],
            "model_id became forbidden — the deliberate contrast with "
            "approval_decision (which DOES forbid it) is what allows one "
            "kind to carry both branches",
        )


if __name__ == "__main__":
    unittest.main()
