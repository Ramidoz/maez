"""Cutover step 1 — the complete RED set, separated by invariant.

Written against the ratified design v3 BEFORE implementation. Each class
is one invariant; each failure must be traceable to its own intended
cause rather than to fixture breakage.

Expected pre-implementation failure taxonomy:

* Bypass, ReservedReason  -> the behaviour exists today and must not:
  the assertion fails (DID NOT RAISE / reason present).
* Matrix, ReceiptPreimage, WindowSurface -> the carrying fields do not
  exist yet: construction fails at the signature. That is the
  not-implemented signal, not a broken fixture.
* LiteralAnchor -> a GUARD, not a red. It must pass today and keep
  passing after the v2 bump; it fails only if the bump moves the
  already-minted anchor.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

from scripts import cuda_bench_assemble as assemble
from scripts import cuda_migration as cm
from tests.test_cuda_migration import _bundle_values, _make_bundle

BENCH_ROOT = Path("/home/rohit/maez/local/cuda_migration_bench")
WINDOW = "windows/ab-20260803-1837"
MINTED_BENCH_ANCHOR = (
    "40a7e770d1caf292c5da1993826d34e6a5a1868e36428f3343debdec7c1dc185"
)


class TestBypassInvariant:
    """A descriptive witness must name the enforceable document."""

    def test_forged_artifact_hash_cannot_reach_stage_two(self) -> None:
        bundle = _make_bundle(2)
        forged = cm.AuthorizationWitness(
            "boot_authorization",
            "pass",
            "f" * 64,
            bundle.bench_binding_sha256,
            bundle.boot_authorization.timestamp,
        )
        with pytest.raises(ValueError, match="bundle_binding"):
            replace(bundle, boot_authorization=forged)
        with pytest.raises(ValueError, match="bundle_binding"):
            cm.BenchEvidenceBundle(
                **{**_bundle_values(bundle), "boot_authorization": forged}
            )


class TestThreeRoleMatrixInvariant:
    """Stage 1: none. Stage 2: authorization only. Stages 3-5: all three."""

    @pytest.mark.parametrize(
        ("stage", "extra"),
        [
            (1, "cutover_authorization"),
            (1, "stage_two_receipt"),
            (1, "cutover_consumption"),
            (2, "stage_two_receipt"),
            (2, "cutover_consumption"),
        ],
    )
    def test_extra_role_for_stage_refuses(self, stage: int, extra: str) -> None:
        donor = _make_bundle(3)
        bundle = _make_bundle(stage)
        with pytest.raises(ValueError, match="bundle_binding"):
            cm.BenchEvidenceBundle(
                **{**_bundle_values(bundle), extra: getattr(donor, extra)}
            )

    @pytest.mark.parametrize(
        ("stage", "missing"),
        [
            (2, "cutover_authorization"),
            (3, "cutover_authorization"),
            (3, "stage_two_receipt"),
            (3, "cutover_consumption"),
        ],
    )
    def test_missing_role_for_stage_refuses(
        self, stage: int, missing: str
    ) -> None:
        bundle = _make_bundle(stage)
        with pytest.raises(ValueError, match="bundle_binding"):
            cm.BenchEvidenceBundle(
                **{**_bundle_values(bundle), missing: None}
            )


class TestReceiptPreimageInvariant:
    """A hash is not a document: the stage-2 receipt must travel."""

    def test_arbitrary_stage_two_hashes_without_preimage_refuse(self) -> None:
        bundle = _make_bundle(3)
        burn = bundle.cutover_consumption.obj
        forged = replace(
            burn,
            stage_two_receipt_file_sha256="a" * 64,
            stage_two_receipt_binding_sha256="b" * 64,
        )
        with pytest.raises(ValueError, match="bundle_binding"):
            cm.BenchEvidenceBundle(
                **{
                    **_bundle_values(bundle),
                    "cutover_consumption": cm.PersistedDoc(
                        cm._canonical_wrapper_bytes(
                            {
                                "schema": cm.CUTOVER_CONSUMPTION_SCHEMA,
                                "binding_sha256": forged.binding_sha256,
                                "fields": json.loads(
                                    json.dumps(
                                        {
                                            name: getattr(forged, name)
                                            for name in forged.__dataclass_fields__
                                            if name != "schema_version"
                                        }
                                    )
                                ),
                            }
                        )
                    ),
                }
            )

    def test_stage_two_receipt_must_carry_the_provisional_decision(
        self,
    ) -> None:
        """A CANONICALLY re-bound receipt with the wrong decision refuses.

        Tampering the field alone would break the wrapper's own binding
        and be caught by the roundtrip guard -- which proves nothing about
        the bundle.  Re-binding first makes the receipt internally valid,
        so only the bundle's decision join can refuse it.
        """
        bundle = _make_bundle(3)
        wrapper = json.loads(bundle.stage_two_receipt.wrapper_bytes)
        wrapper["fields"]["decision"] = "keep_vulkan"
        rebound = cm.AssembleReceiptDoc(
            fields=MappingProxyType(dict(wrapper["fields"]))
        )
        wrapper["binding_sha256"] = rebound.binding_sha256
        forged = cm.PersistedDoc(cm._canonical_wrapper_bytes(wrapper))
        assert forged.obj.decision == "keep_vulkan"

        # Re-point the burn at the forged receipt too, so the hash joins
        # SUCCEED and only the decision join can refuse.  Without this the
        # test passes on the binding join and proves nothing about the
        # decision -- caught by mutation.
        burn = replace(
            bundle.cutover_consumption.obj,
            stage_two_receipt_file_sha256=forged.file_sha256,
            stage_two_receipt_binding_sha256=forged.obj.binding_sha256,
        )
        burn_doc = cm.PersistedDoc(
            cm._canonical_wrapper_bytes(
                {
                    "schema": cm.CUTOVER_CONSUMPTION_SCHEMA,
                    "binding_sha256": burn.binding_sha256,
                    "fields": {
                        name: getattr(burn, name)
                        for name in burn.__dataclass_fields__
                        if name != "schema_version"
                    },
                }
            )
        )
        with pytest.raises(ValueError, match="bundle_binding"):
            cm.BenchEvidenceBundle(
                **{
                    **_bundle_values(bundle),
                    "stage_two_receipt": forged,
                    "cutover_consumption": burn_doc,
                }
            )


class TestLiteralAnchorGuard:
    """The already-minted bench anchor must survive the v2 bump verbatim."""

    def test_durable_window8_evidence_still_hashes_to_the_minted_anchor(
        self,
    ) -> None:
        paths = assemble.Stage1ArtifactPaths(
            control_packet=f"{WINDOW}/vulkan_baseline/attempt-000/packets/vulkan_baseline-completed.json",
            candidate_packet=f"{WINDOW}/cuda_candidate/attempt-000/packets/cuda_candidate-completed.json",
            static_admission="command-static-preflight-attempt-022-admission.json",
            static_completion="command-static-preflight-attempt-022-terminal.json",
            control_admission="command-vulkan-baseline-attempt-023-admission.json",
            control_completion="command-vulkan-baseline-attempt-023-terminal.json",
            candidate_admission="command-cuda-candidate-attempt-024-admission.json",
            candidate_completion="command-cuda-candidate-attempt-024-terminal.json",
            window_authorization="window-authorization.json",
            continuation="continuation.json",
            window_consumption=f"{WINDOW}/vulkan_baseline/attempt-000/receipts/consumption-89c56a00f3af2ee223b0fec36f76ba1fd3f9f8c25793db2e3b9c56ad89c1c0bd.json",
            continuation_consumption=f"{WINDOW}/cuda_candidate/attempt-000/receipts/consumption-f102a166198a20262662144281bc6d2ef704984dfdabdbcc0d6958e56b10f737.json",
            control_containment_before=f"{WINDOW}/vulkan_baseline/attempt-000/containment/containment-before.json",
            control_containment_after=f"{WINDOW}/vulkan_baseline/attempt-000/containment/containment-after.json",
            candidate_containment_before=f"{WINDOW}/cuda_candidate/attempt-000/containment/containment-before.json",
            candidate_containment_after=f"{WINDOW}/cuda_candidate/attempt-000/containment/containment-after.json",
            bench_identity=f"{WINDOW}/cuda_candidate/attempt-000/identity/bench_runtime_identity.json",
            runtime_identity=f"{WINDOW}/cuda_candidate/attempt-000/identity/runtime_identity.json",
            static_preflight="receipts/static-preflight-attempt-022.json",
            quality="receipts/quality-evidence.json",
            owner_voice="receipts/owner-voice-review.json",
            rollback="receipts/rollback-evidence.json",
        )
        bundle = assemble.build_stage1_bundle(
            paths,
            root=BENCH_ROOT,
            timestamp=datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        )
        assert bundle.bench_binding_sha256 == MINTED_BENCH_ANCHOR

    def test_anchor_is_invariant_while_full_hash_moves(self) -> None:
        stage1, stage2, stage3 = (_make_bundle(n) for n in (1, 2, 3))
        assert (
            stage1.bench_binding_sha256
            == stage2.bench_binding_sha256
            == stage3.bench_binding_sha256
        )
        assert len(
            {b.binding_sha256 for b in (stage1, stage2, stage3)}
        ) == 3


class TestWindowSurfaceInvariant:
    """cutover_window_id: None at stage 1, exactly the authorization's after."""

    def test_stage_one_verdict_carries_no_window(self) -> None:
        verdict = cm.evaluate_promotion_bundle(_make_bundle(1))
        assert verdict.cutover_window_id is None

    def test_stage_two_verdict_carries_the_authorization_window(self) -> None:
        bundle = _make_bundle(2)
        verdict = cm.evaluate_promotion_bundle(bundle)
        assert (
            verdict.cutover_window_id
            == bundle.cutover_authorization.obj.window_id
        )

    def test_window_disagreement_and_tamper_refuse(self) -> None:
        bundle = _make_bundle(2)
        verdict = cm.evaluate_promotion_bundle(bundle)
        tampered = replace(verdict, cutover_window_id="cutover-forged")
        assert tampered.binding_sha256 != verdict.binding_sha256


class TestReservedReasonInvariant:
    """owner_authorization_failed is unreachable by every valid bundle."""

    def test_no_valid_public_bundle_can_mint_the_reserved_reason(self) -> None:
        assert "owner_authorization_failed" in cm._REASONS
        for stage in (1, 2, 3, 4, 5):
            verdict = cm.evaluate_promotion_bundle(_make_bundle(stage))
            assert "owner_authorization_failed" not in verdict.reasons

    def test_declined_authorization_cannot_construct_stage_two(self) -> None:
        bundle = _make_bundle(2)
        declined = replace(bundle.boot_authorization, status="fail")
        with pytest.raises(ValueError, match="bundle_binding"):
            cm.BenchEvidenceBundle(
                **{**_bundle_values(bundle), "boot_authorization": declined}
            )
