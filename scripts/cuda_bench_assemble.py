"""Inert owner-selected stage-one CUDA bench evidence assembler."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from types import MappingProxyType

from scripts import cuda_migration as cm
from scripts.cuda_bench_driver import (
    BenchRefusal,
    open_bench_file,
    parse_continuation,
    parse_window_authorization,
)


@dataclass(frozen=True, slots=True)
class Stage1ArtifactPaths:
    control_packet: str
    candidate_packet: str
    static_admission: str
    static_completion: str
    control_admission: str
    control_completion: str
    candidate_admission: str
    candidate_completion: str
    window_authorization: str
    continuation: str
    window_consumption: str
    continuation_consumption: str
    control_containment_before: str
    control_containment_after: str
    candidate_containment_before: str
    candidate_containment_after: str
    bench_identity: str
    runtime_identity: str
    static_preflight: str
    quality: str
    owner_voice: str
    rollback: str


@dataclass(frozen=True, slots=True)
class Stage1Evaluation:
    bundle: cm.BenchEvidenceBundle
    verdict: cm.PromotionVerdict
    receipt: Mapping[str, object]


class _Stage1EvaluationFailure(Exception):
    """A valid bundle reached the scorer but could not be evaluated."""


def _refuse() -> None:
    raise BenchRefusal("assembly_refused") from None


def _canonical_authorization(data: bytes) -> bytes:
    try:
        decoded = json.loads(data)
        if not isinstance(decoded, dict):
            _refuse()
        canonical = cm._canonical_wrapper_bytes(decoded)
    except (OverflowError, RecursionError, TypeError, UnicodeError, ValueError):
        _refuse()
    if data != canonical:
        _refuse()
    return data


def _persisted(data: bytes, expected: type[object]) -> cm.PersistedDoc:
    try:
        document = cm.PersistedDoc(data)
    except (OverflowError, RecursionError, TypeError, UnicodeError, ValueError):
        _refuse()
    if type(document.obj) is not expected:
        _refuse()
    return document


def _summary(
    packet: cm.PhasePacket,
    quality: cm.QualityEvidence,
    owner: cm.OwnerVoiceReview,
    rollback: cm.RollbackEvidenceBundle,
) -> cm.BenchSummary:
    try:
        projection = json.loads(packet.summary_projection_json)
        if type(projection) is not dict:
            _refuse()
        summary = cm.BenchSummary(
            phase=packet.phase,
            alias=projection["alias"],
            model_sha256=packet.model_sha256,
            corpus_sha256=packet.corpus_sha256,
            order_sha256=packet.order_sha256,
            sample_n=projection["sample_n"],
            warmup_count=projection["warmup_count"],
            measured_sample_count=projection["measured_sample_count"],
            load_cycles=projection["load_cycles"],
            seven_turn_max_ms=projection["seven_turn_max_ms"],
            p95_e2e_ms=projection["p95_e2e_ms"],
            median_decode_tps=projection["median_decode_tps"],
            median_prefill_tps=projection["median_prefill_tps"],
            cycles=packet.cycle_metrics,
            mtp_drafted_tokens=projection["mtp_drafted_tokens"],
            mtp_accepted_tokens=projection["mtp_accepted_tokens"],
            mtp_rejected_tokens=projection["mtp_rejected_tokens"],
            mtp_initialized=projection["mtp_initialized"],
            false_absence_count=quality.false_absence_count,
            wrong_answered_ungrounded_count=(
                quality.wrong_answered_ungrounded_count
            ),
            type_regression_count=quality.type_regression_count,
            recall_posture=quality.recall_posture,
            quality_failure_count=quality.quality_failure_count,
            owner_voice_evidence=cm.PhaseEvidence(
                "owner_voice_review",
                owner.status,
                owner.artifact_sha256,
                owner.timestamp,
            ),
            kernel_counters=packet.kernel_counters,
            crash_count=projection["crash_count"],
            restart_count=projection["restart_count"],
            hang_count=projection["hang_count"],
            timeout_count=projection["timeout_count"],
            unload_leak_mib=projection["unload_leak_mib"],
            rollback_witness=rollback.witness,
            cold_boot_witness=None,
            provisional_live_witness=None,
        )
        if cm.phase_summary_projection(summary) != projection:
            _refuse()
        return summary
    except (KeyError, OverflowError, TypeError, ValueError):
        _refuse()


@dataclass(frozen=True, slots=True)
class Stage2InputPaths:
    """The stage-2 locating authority: the 22 stage-1 inputs + authorization.

    It names NO command record. Command ordinals are runtime-allocated, so
    admission and completion refs cannot be constants; the completion
    arrives as a locator and the admission and receipt derive from it.
    """

    control_packet: str
    candidate_packet: str
    static_admission: str
    static_completion: str
    control_admission: str
    control_completion: str
    candidate_admission: str
    candidate_completion: str
    window_authorization: str
    continuation: str
    window_consumption: str
    continuation_consumption: str
    control_containment_before: str
    control_containment_after: str
    candidate_containment_before: str
    candidate_containment_after: str
    bench_identity: str
    runtime_identity: str
    static_preflight: str
    quality: str
    owner_voice: str
    rollback: str
    authorization: str


def build_stage2_bundle(
    paths: Stage2InputPaths,
    *,
    root: Path,
    timestamp: str,
) -> cm.BenchEvidenceBundle:
    """The SOLE production stage-2 assembly seam.

    Reuses build_stage1_bundle for the shared evidence rather than
    duplicating it -- the consumer's guarantee is that it reconstructs
    through the same seam the producer used, which two builders would
    quietly falsify.
    """

    if type(paths) is not Stage2InputPaths:
        _refuse()
    stage_one = build_stage1_bundle(
        Stage1ArtifactPaths(
            **{
                field.name: getattr(paths, field.name)
                for field in fields(Stage1ArtifactPaths)
            }
        ),
        root=root,
        timestamp=timestamp,
    )
    try:
        authorization = _persisted(
            open_bench_file(paths.authorization, root=root),
            cm.CutoverAuthorizationDoc,
        )
        # The descriptive witness must NAME the enforceable document: its
        # artifact hash is the authorization's file hash, which is the
        # join step 1 exists to enforce.
        boot = cm.AuthorizationWitness(
            "boot_authorization",
            "pass",
            authorization.file_sha256,
            stage_one.bench_binding_sha256,
            timestamp,
        )
        values = {
            field.name: getattr(stage_one, field.name)
            for field in fields(cm.BenchEvidenceBundle)
            if field.init
        }
        values["cutover_authorization"] = authorization
        values["boot_authorization"] = boot
        return cm.BenchEvidenceBundle(**values)
    except BenchRefusal as exc:
        if exc.code == "assembly_refused":
            raise
        _refuse()
    except (AttributeError, KeyError, OverflowError, TypeError, ValueError):
        _refuse()


def build_stage1_bundle(
    paths: Stage1ArtifactPaths,
    *,
    root: Path,
    timestamp: str,
) -> cm.BenchEvidenceBundle:
    """Reconstruct one genuine P1 bundle without measuring or scoring."""

    if type(paths) is not Stage1ArtifactPaths:
        _refuse()
    try:
        selected = {
            field.name: open_bench_file(getattr(paths, field.name), root=root)
            for field in fields(Stage1ArtifactPaths)
        }

        control_packet_doc = _persisted(
            selected["control_packet"], cm.PhasePacket
        )
        candidate_packet_doc = _persisted(
            selected["candidate_packet"], cm.PhasePacket
        )
        static_completion = _persisted(
            selected["static_completion"], cm.CommandCompletionDoc
        )
        control_completion = _persisted(
            selected["control_completion"], cm.CommandCompletionDoc
        )
        candidate_completion = _persisted(
            selected["candidate_completion"], cm.CommandCompletionDoc
        )
        window_consumption_doc = _persisted(
            selected["window_consumption"], cm.ConsumptionReceipt
        )
        continuation_consumption_doc = _persisted(
            selected["continuation_consumption"], cm.ConsumptionReceipt
        )
        control_before_doc = _persisted(
            selected["control_containment_before"], cm.ContainmentSnapshot
        )
        control_after_doc = _persisted(
            selected["control_containment_after"], cm.ContainmentSnapshot
        )
        candidate_before_doc = _persisted(
            selected["candidate_containment_before"], cm.ContainmentSnapshot
        )
        candidate_after_doc = _persisted(
            selected["candidate_containment_after"], cm.ContainmentSnapshot
        )
        bench_identity_doc = _persisted(
            selected["bench_identity"], cm.RuntimeIdentity
        )
        runtime_identity_doc = _persisted(
            selected["runtime_identity"], cm.RuntimeIdentity
        )
        static_preflight = _persisted(
            selected["static_preflight"], cm.StaticPreflightDoc
        )
        quality_doc = _persisted(selected["quality"], cm.QualityEvidence)
        owner_doc = _persisted(selected["owner_voice"], cm.OwnerVoiceReview)
        rollback_doc = _persisted(
            selected["rollback"], cm.RollbackEvidenceBundle
        )

        static_admission = cm.CommandAdmissionPreimage(
            paths.static_admission, selected["static_admission"]
        )
        control_admission = cm.CommandAdmissionPreimage(
            paths.control_admission, selected["control_admission"]
        )
        candidate_admission = cm.CommandAdmissionPreimage(
            paths.candidate_admission, selected["candidate_admission"]
        )

        parsed_window = parse_window_authorization(
            _canonical_authorization(selected["window_authorization"])
        )
        window = cm.WindowAuthorizationDoc(
            window_id=parsed_window.window_id,
            phases=parsed_window.phases,
            boot_id=parsed_window.boot_id,
            nonce=parsed_window.nonce,
            issued_at=parsed_window.issued_at,
            expires_at=parsed_window.expires_at,
            owner=parsed_window.owner,
        )
        parsed_continuation = parse_continuation(
            _canonical_authorization(selected["continuation"])
        )
        continuation = cm.ContinuationDoc(
            window_id=parsed_continuation.window_id,
            phases=parsed_continuation.phases,
            boot_id=parsed_continuation.boot_id,
            nonce=parsed_continuation.nonce,
            issued_at=parsed_continuation.issued_at,
            expires_at=parsed_continuation.expires_at,
            owner=parsed_continuation.owner,
            parent_vulkan_packet_sha256=(
                parsed_continuation.parent_vulkan_packet_sha256
            ),
        )

        control_packet = control_packet_doc.obj
        candidate_packet = candidate_packet_doc.obj
        quality = quality_doc.obj
        owner = owner_doc.obj
        rollback = rollback_doc.obj
        containment_docs = {
            "vulkan_baseline:before": control_before_doc,
            "vulkan_baseline:after": control_after_doc,
            "cuda_candidate:before": candidate_before_doc,
            "cuda_candidate:after": candidate_after_doc,
        }
        containment = cm.ContainmentWitness(
            (
                control_before_doc.obj,
                control_after_doc.obj,
                candidate_before_doc.obj,
                candidate_after_doc.obj,
                rollback.containment_before,
                rollback.containment_after,
            )
        )
        control_summary = _summary(control_packet, quality, owner, rollback)
        candidate_summary = _summary(candidate_packet, quality, owner, rollback)
        boot = cm.AuthorizationWitness(
            "boot_authorization", "not_attempted", None, None, None
        )
        live = cm.AuthorizationWitness(
            "live_witness_authorization", "not_attempted", None, None, None
        )

        return cm.BenchEvidenceBundle(
            # Stage-1 assembly carries none of the cutover roles: the
            # frozen matrix forbids all three before an authorization
            # exists.  Stage-2+ entrypoints (step 5) supply them.
            cutover_authorization=None,
            stage_two_receipt=None,
            cutover_consumption=None,
            window_id=control_packet.window_id,
            boot_id=control_packet.boot_id,
            gpu_uuid=control_packet.gpu_uuid,
            driver_package_sha256=control_packet.driver_package_sha256,
            control_summary=control_summary,
            candidate_summary=candidate_summary,
            control_packet=control_packet,
            candidate_packet=candidate_packet,
            containment=containment,
            boot_authorization=boot,
            live_authorization=live,
            bench_runtime_identity=bench_identity_doc.obj,
            runtime_identity=runtime_identity_doc.obj,
            quality=quality,
            owner_voice=owner,
            window_authorization=window,
            continuation=continuation,
            window_consumption=window_consumption_doc.obj,
            continuation_consumption=continuation_consumption_doc.obj,
            containment_docs=containment_docs,
            bench_identity_doc=bench_identity_doc,
            runtime_identity_doc=runtime_identity_doc,
            static_preflight=static_preflight,
            static_preflight_ref=paths.static_preflight,
            static_admission=static_admission,
            static_completion=static_completion,
            control_admission=control_admission,
            control_completion=control_completion,
            candidate_admission=candidate_admission,
            candidate_completion=candidate_completion,
            control_packet_doc=control_packet_doc,
            control_packet_ref=paths.control_packet,
            candidate_packet_doc=candidate_packet_doc,
            candidate_packet_ref=paths.candidate_packet,
            rollback=rollback,
            cold_boot_maps=None,
            provisional_live_maps=None,
            timestamp=timestamp,
        )
    except BenchRefusal as exc:
        if exc.code == "assembly_refused":
            raise
        _refuse()
    except (AttributeError, KeyError, OverflowError, TypeError, ValueError):
        _refuse()


def assemble_stage1(
    paths: Stage1ArtifactPaths,
    *,
    root: Path,
    timestamp: str,
) -> Stage1Evaluation:
    bundle = build_stage1_bundle(paths, root=root, timestamp=timestamp)
    try:
        verdict = cm.evaluate_promotion_bundle(bundle)
        receipt = cm.build_receipt(bundle, verdict, timestamp=timestamp)
    except Exception:
        raise _Stage1EvaluationFailure from None
    return Stage1Evaluation(
        bundle=bundle,
        verdict=verdict,
        receipt=MappingProxyType(dict(receipt)),
    )
