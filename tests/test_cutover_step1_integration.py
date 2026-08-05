"""Cutover step 1 -- INTEGRATION reds against the real producer path.

The focused invariant suite in test_cutover_step1_invariants.py hand-built
every document to satisfy the constructor it was testing.  Tests and code
therefore shared one blind spot, and five production-path defects survived
a green run plus a seven-mutation pass.  Mutation testing proves the joins
you wrote are load-bearing; it cannot see the joins you never wrote.

These three tests close that hole.  None of them may hand-author a
document that the real producer could not emit:

1. Decode the real durable attempt-026 bytes off disk.
2. Produce a stage-2 receipt ONLY through cm.build_receipt plus the real
   driver encoder, then decode it.
3. Reconstruct stage 3 from that PRODUCED receipt -- never from a
   hand-authored equivalent.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType

import pytest

from scripts import cuda_bench_driver as driver
from scripts import cuda_migration as cm

BENCH_ROOT = Path("/home/rohit/maez/local/cuda_migration_bench")
DURABLE_RECEIPT = BENCH_ROOT / "command-assemble-stage1-attempt-026-terminal.json"
# The SECOND frozen literal, alongside the bench anchor 40a7e770...
FROZEN_STAGE1_BUNDLE_BINDING = (
    "fa790eb8e594f750f100f6d4af664504d58cf4c4a756c4654a5661d3cd764dee"
)


def _encode_receipt(receipt: dict[str, object], binding: str) -> bytes:
    """The REAL encoder, exactly as scripts/cuda_bench_cli.py drives it."""

    document = dict(receipt)
    document["binding_sha256"] = binding
    return driver.ProductionArtifactPolicy().encode("receipt", document)


class TestRealReceiptDecoding:
    """The established writer's own bytes must decode."""

    def test_durable_attempt_026_receipt_decodes_as_the_typed_role(self) -> None:
        raw = DURABLE_RECEIPT.read_bytes()
        document = cm.PersistedDoc(raw)
        typed = cm._canonical_persisted_role(document, cm.AssembleReceiptDoc)
        assert typed.obj.decision == "bench_passed"
        assert typed.obj.cutover_window_id is None

    def test_durable_receipt_binding_follows_the_writer_convention(self) -> None:
        """The wrapper binding IS the bundle binding -- not a content hash.

        This is the convention the durable artifact was written under.  A
        typed view that computes anything else cannot read real evidence.
        """
        wrapper = json.loads(DURABLE_RECEIPT.read_bytes())
        assert (
            wrapper["binding_sha256"]
            == wrapper["fields"]["bundle_binding_sha256"]
        )
        document = cm.PersistedDoc(DURABLE_RECEIPT.read_bytes())
        assert document.obj.binding_sha256 == wrapper["binding_sha256"]


class TestFrozenBundleBindingGuard:
    """BOTH frozen literals, not just the bench anchor.

    Commit 8989c32 froze the bench anchor's hash domain and wrote a guard
    for it, then let the same v1->v2 schema bump move the FULL bundle
    binding from fa790eb8... to 0ed9f1f7... -- orphaning the
    bundle_binding_sha256 the durable attempt-026 receipt carries.  One
    anchor was protected and its sibling was silently broken.  This guard
    exists so that cannot recur.

    Note the binding is timestamp-sensitive: it is only reproducible when
    rebuilt at the receipt's OWN timestamp.  That is exactly why the
    stage-2 projection must be rebuilt using receipt.timestamp.
    """

    def test_durable_stage_one_bundle_binding_is_reproducible(self) -> None:
        from tests.test_cutover_step1_invariants import stage1_paths

        wrapper = json.loads(DURABLE_RECEIPT.read_bytes())
        from scripts import cuda_bench_assemble as assemble

        bundle = assemble.build_stage1_bundle(
            stage1_paths(),
            root=BENCH_ROOT,
            timestamp=wrapper["fields"]["timestamp"],
        )
        assert bundle.binding_sha256 == wrapper["binding_sha256"]
        assert bundle.binding_sha256 == FROZEN_STAGE1_BUNDLE_BINDING

    def test_a_schema_bump_must_not_move_either_frozen_literal(self) -> None:
        assert cm.BENCH_EVIDENCE_HASH_DOMAIN.endswith(".v1")
        assert cm.BENCH_EVIDENCE_FULL_HASH_DOMAIN.endswith(".v1")
        assert cm.BENCH_EVIDENCE_BUNDLE_SCHEMA.endswith(".v2")
        assert cm.BENCH_EVIDENCE_HASH_DOMAIN != cm.BENCH_EVIDENCE_BUNDLE_SCHEMA
        assert (
            cm.BENCH_EVIDENCE_FULL_HASH_DOMAIN != cm.BENCH_EVIDENCE_BUNDLE_SCHEMA
        )


class TestProducedStageTwoReceipt:
    """A stage-2 receipt must come from build_receipt, not from a fixture."""

    def test_build_receipt_emits_the_cutover_window_for_stage_two(self) -> None:
        from tests.test_cuda_migration import _make_bundle

        bundle = _make_bundle(2)
        verdict = cm.evaluate_promotion_bundle(bundle)
        receipt = cm.build_receipt(
            bundle, verdict, timestamp=bundle.timestamp
        )
        assert receipt["cutover_window_id"] == verdict.cutover_window_id
        assert receipt["cutover_window_id"] is not None

    def test_stage_one_receipt_still_omits_the_window_field(self) -> None:
        """The closed sum must not widen stage 1.

        The durable attempt-026 receipt carries exactly the historical 14
        fields.  Adding the window unconditionally would change its shape
        and orphan it.
        """
        from tests.test_cuda_migration import _make_bundle

        bundle = _make_bundle(1)
        verdict = cm.evaluate_promotion_bundle(bundle)
        receipt = cm.build_receipt(bundle, verdict, timestamp=bundle.timestamp)
        assert "cutover_window_id" not in receipt

    def test_produced_receipt_survives_the_real_encoder_and_decodes(self) -> None:
        from tests.test_cuda_migration import _make_bundle

        bundle = _make_bundle(2)
        verdict = cm.evaluate_promotion_bundle(bundle)
        receipt = cm.build_receipt(
            bundle, verdict, timestamp=bundle.timestamp
        )
        raw = _encode_receipt(receipt, bundle.binding_sha256)
        document = cm.PersistedDoc(raw)
        typed = cm._canonical_persisted_role(document, cm.AssembleReceiptDoc)
        assert typed.obj.decision == "provisional_cuda_boot"
        assert typed.obj.cutover_window_id == verdict.cutover_window_id
        assert typed.obj.bundle_binding_sha256 == bundle.binding_sha256


class TestStageThreeFromProducedReceipt:
    """Stage 3 must be reconstructible from the produced stage-2 receipt."""

    def test_stage_three_accepts_the_produced_receipt(self) -> None:
        from tests.test_cuda_migration import _make_bundle

        bundle = _make_bundle(3)
        receipt_doc = bundle.stage_two_receipt
        typed = cm._canonical_persisted_role(receipt_doc, cm.AssembleReceiptDoc)
        assert typed.obj.decision == "provisional_cuda_boot"

    def test_stage_two_projection_is_recomputable_from_the_receipt(self) -> None:
        """The claimed stage-2 binding must be REBUILDABLE, not asserted.

        A stage-3 bundle carries everything a stage-2 bundle carried; the
        constructor normalizes itself back to the stage-2 shape using the
        receipt's own timestamp and recomputes the binding.  A receipt
        naming any other bundle cannot be smuggled in.
        """
        from tests.test_cuda_migration import _make_bundle

        stage2 = _make_bundle(2)
        stage3 = _make_bundle(3)
        receipt = cm._canonical_persisted_role(
            stage3.stage_two_receipt, cm.AssembleReceiptDoc
        ).obj
        assert receipt.bundle_binding_sha256 == stage2.binding_sha256
        assert (
            stage3._stage_two_projection(receipt.timestamp).binding_sha256
            == receipt.bundle_binding_sha256
        )

    @pytest.mark.parametrize("stage", [3, 4, 5])
    def test_projection_rule_holds_from_every_later_stage(
        self, stage: int
    ) -> None:
        """Run the equality rule from stages 3, 4 AND 5.

        Stage 3 alone cannot falsify the live_authorization or
        provisional_live_maps normalizations -- those fields only diverge
        from their stage-2 values at stages 4 and 5.  A mutation check run
        only at stage 3 would report them load-bearing-unknown.
        """
        from tests.test_cuda_migration import _make_bundle

        later = _make_bundle(stage)
        receipt = cm._canonical_persisted_role(
            later.stage_two_receipt, cm.AssembleReceiptDoc
        ).obj
        projection = later._stage_two_projection(receipt.timestamp)
        assert projection.binding_sha256 == receipt.bundle_binding_sha256
        assert projection.binding_sha256 == _make_bundle(2).binding_sha256

    def test_containment_doc_keys_are_stage_invariant(self) -> None:
        """Pins WHY the containment_docs normalization is a no-op today.

        _validate_persisted_documents requires exactly this key set at
        every stage, and it is a subset of the base containment keys.  If
        that ever widens to include cold_boot, this test fails and the
        projection's filter becomes load-bearing.
        """
        assert set(cm._AB_CONTAINMENT_DOC_KEYS) <= set(cm._BASE_CONTAINMENT_KEYS)

    def test_receipt_naming_a_foreign_bundle_is_refused(self) -> None:
        from dataclasses import replace

        from tests.test_cuda_migration import _bundle_values, _make_bundle

        stage3 = _make_bundle(3)
        fields = dict(
            json.loads(stage3.stage_two_receipt.wrapper_bytes)["fields"]
        )
        fields["bundle_binding_sha256"] = "b" * 64
        raw = driver.ProductionArtifactPolicy().encode(
            "receipt", {**fields, "binding_sha256": "b" * 64}
        )
        forged = cm.PersistedDoc(raw)
        burn = replace(
            stage3.cutover_consumption.obj,
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
                    **_bundle_values(stage3),
                    "stage_two_receipt": forged,
                    "cutover_consumption": burn_doc,
                }
            )


def _rebuild(stage: int, *, auth=None, burn=None, timestamp=None):
    """Rebuild a bundle with the authorization/burn/stamp perturbed.

    A perturbed authorization changes the stage-2 projection, so the
    stage-2 receipt must be RE-PRODUCED through build_receipt against the
    perturbed stage-2 bundle -- otherwise the D4 projection join refuses
    first and the chronology link under test is never reached.  An earlier
    version of this helper did exactly that, and the mutation check caught
    it: the evidence<issued link SURVIVED removal because its test was
    passing on the projection join.
    """
    from dataclasses import replace

    from tests.test_cuda_migration import (
        _bundle_values,
        _make_bundle,
        _persisted_doc,
    )

    overrides: dict[str, object] = {}
    if auth:
        overrides["cutover_issued_at"] = auth["issued_at"]
        overrides["cutover_expires_at"] = auth["expires_at"]
    # _make_bundle re-produces the receipt AND the burn from whatever
    # authorization it is handed, through the real producer path.
    bundle = _make_bundle(stage, **overrides)
    if burn is None and timestamp is None:
        return bundle

    values = _bundle_values(bundle)
    if burn:
        obj = replace(bundle.cutover_consumption.obj, **burn)
        values["cutover_consumption"] = _persisted_doc(
            cm.CUTOVER_CONSUMPTION_SCHEMA,
            obj,
            {
                name: getattr(obj, name)
                for name in obj.__dataclass_fields__
                if name != "schema_version"
            },
        )
    if timestamp:
        values["timestamp"] = timestamp
    return cm.BenchEvidenceBundle(**values)


class TestChronologyChain:
    """evidence < issued <= witness <= receipt <= burn <= results <= bundle < expiry."""

    def test_the_coherent_ceremony_clock_is_accepted(self) -> None:
        assert _rebuild(3) is not None

    def test_authorization_may_not_predate_the_evidence(self) -> None:
        """The narrow TTL-bounded hole: 'authorizing' unminted evidence."""
        with pytest.raises(ValueError, match="bundle_binding"):
            _rebuild(
                3,
                auth={
                    "issued_at": "2026-07-13T08:04:00Z",
                    "expires_at": "2026-07-13T12:04:00Z",
                },
            )

    def test_burn_may_not_follow_the_mutation_it_authorizes(self) -> None:
        """The exact incoherence the previous fixture baked in."""
        with pytest.raises(ValueError, match="bundle_binding"):
            _rebuild(3, burn={"consumed_at": "2026-07-13T12:03:12Z"})

    def test_burn_may_not_precede_the_stage_two_receipt(self) -> None:
        with pytest.raises(ValueError, match="bundle_binding"):
            _rebuild(3, burn={"consumed_at": "2026-07-13T12:03:01Z"})

    def test_assembly_after_expiry_is_refused(self) -> None:
        with pytest.raises(ValueError, match="bundle_binding"):
            _rebuild(3, timestamp="2026-07-13T16:02:31Z")

    def test_assembly_before_the_mutation_results_is_refused(self) -> None:
        with pytest.raises(ValueError, match="bundle_binding"):
            _rebuild(3, timestamp="2026-07-13T12:03:05Z")


class TestStageTwoChronologyIsNotDeferrable:
    """Stage 2 IS the pre-mutation permit -- refusing at stage 3 is too late.

    _validate_boot_authorization returned early when there was no
    consumption document, so the complete chain never ran for the one
    bundle that actually authorizes the mutation.
    """

    def _stage_two(self, **overrides):
        from tests.test_cuda_migration import _make_bundle

        return _make_bundle(2, **overrides)

    def test_stage_two_rejects_authorization_predating_its_evidence(
        self,
    ) -> None:
        with pytest.raises(ValueError, match="bundle_binding"):
            self._stage_two(
                cutover_issued_at="2026-07-13T08:04:00Z",
                cutover_expires_at="2026-07-13T12:04:00Z",
            )

    def test_stage_two_rejects_assembly_before_the_witness(self) -> None:
        with pytest.raises(ValueError, match="bundle_binding"):
            self._stage_two(timestamp="2026-07-13T12:02:59Z")

    def test_stage_two_rejects_assembly_after_expiry(self) -> None:
        # CUTOVER_TTL_S is exact, so the window cannot be shortened; the
        # reachable case is assembly drifting past a valid window.
        with pytest.raises(ValueError, match="bundle_binding"):
            self._stage_two(timestamp="2026-07-13T16:02:31Z")

    def test_the_public_evaluator_never_mints_from_impossible_timing(
        self,
    ) -> None:
        """The route that matters: scorer + real receipt builder."""
        for overrides in (
            {
                "cutover_issued_at": "2026-07-13T08:04:00Z",
                "cutover_expires_at": "2026-07-13T12:04:00Z",
            },
            {"timestamp": "2026-07-13T12:02:59Z"},
            {"timestamp": "2026-07-13T16:02:31Z"},
        ):
            with pytest.raises(ValueError, match="bundle_binding"):
                bundle = self._stage_two(**overrides)
                verdict = cm.evaluate_promotion_bundle(bundle)
                cm.build_receipt(bundle, verdict, timestamp=bundle.timestamp)


class TestWindowIdentityIsTypedNotCoerced:
    """A JSON number is not a window id."""

    @pytest.mark.parametrize("value", [123, True, 1.5, ["c"], {"a": 1}])
    def test_typed_receipt_refuses_a_non_string_window(self, value) -> None:
        from tests.test_cuda_migration import _make_bundle

        fields = dict(
            json.loads(_make_bundle(3).stage_two_receipt.wrapper_bytes)["fields"]
        )
        fields["cutover_window_id"] = value
        with pytest.raises(ValueError, match="assemble_receipt"):
            cm.AssembleReceiptDoc(fields=MappingProxyType(fields))

    def test_full_bundle_refuses_a_numeric_window_matching_a_string(
        self,
    ) -> None:
        """JSON 123 must not satisfy an authorization holding "123"."""
        from tests.test_cuda_migration import _bundle_values, _make_bundle

        bundle = _make_bundle(3)
        wrapper = json.loads(bundle.stage_two_receipt.wrapper_bytes)
        wrapper["fields"]["cutover_window_id"] = 123
        # It must not even decode: the type is refused at the document
        # boundary, before any bundle can be built around it.
        with pytest.raises(ValueError, match="persisted_roundtrip"):
            cm.PersistedDoc(cm._canonical_wrapper_bytes(wrapper))
        assert _bundle_values(bundle)["stage_two_receipt"] is not None


class TestProducerBindsTheWindow:
    """_promotion_verdict_packet drives build_receipt's mismatch check."""

    def _bundle_and_verdict(self, stage: int):
        from tests.test_cuda_migration import _make_bundle

        bundle = _make_bundle(stage)
        return bundle, cm.evaluate_promotion_bundle(bundle)

    def test_forged_stage_two_window_is_refused(self) -> None:
        from dataclasses import replace

        bundle, verdict = self._bundle_and_verdict(2)
        with pytest.raises(ValueError, match="verdict_binding_mismatch"):
            cm.build_receipt(
                bundle,
                replace(verdict, cutover_window_id="cutover-forged"),
                timestamp=bundle.timestamp,
            )

    def test_missing_stage_two_window_is_refused(self) -> None:
        from dataclasses import replace

        bundle, verdict = self._bundle_and_verdict(2)
        with pytest.raises(ValueError, match="verdict_binding_mismatch"):
            cm.build_receipt(
                bundle,
                replace(verdict, cutover_window_id=None),
                timestamp=bundle.timestamp,
            )

    def test_non_null_stage_one_window_is_refused(self) -> None:
        from dataclasses import replace

        bundle, verdict = self._bundle_and_verdict(1)
        with pytest.raises(ValueError, match="verdict_binding_mismatch"):
            cm.build_receipt(
                bundle,
                replace(verdict, cutover_window_id="cutover-forged"),
                timestamp=bundle.timestamp,
            )
