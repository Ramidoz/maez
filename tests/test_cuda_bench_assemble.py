"""Contract tests for the inert owner-selected stage-one assembler."""

from __future__ import annotations

import ast
import hashlib
import json
import os
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from types import MappingProxyType
from unittest import mock

import pytest

from scripts import cuda_bench_assemble as assemble
from scripts import cuda_bench_driver as driver
from scripts import cuda_migration as cm
from tests import test_cuda_migration as migration_tests


TIMESTAMP = "2026-07-13T12:02:10Z"
EXPECTED_PATH_FIELDS = (
    "control_packet",
    "candidate_packet",
    "static_admission",
    "static_completion",
    "control_admission",
    "control_completion",
    "candidate_admission",
    "candidate_completion",
    "window_authorization",
    "continuation",
    "window_consumption",
    "continuation_consumption",
    "control_containment_before",
    "control_containment_after",
    "candidate_containment_before",
    "candidate_containment_after",
    "bench_identity",
    "runtime_identity",
    "static_preflight",
    "quality",
    "owner_voice",
    "rollback",
)
PERSISTED_PATH_FIELDS = (
    "control_packet",
    "candidate_packet",
    "static_completion",
    "control_completion",
    "candidate_completion",
    "window_consumption",
    "continuation_consumption",
    "control_containment_before",
    "control_containment_after",
    "candidate_containment_before",
    "candidate_containment_after",
    "bench_identity",
    "runtime_identity",
    "static_preflight",
    "quality",
    "owner_voice",
    "rollback",
)


def _write_private(root: Path, relative: str, payload: bytes) -> None:
    path = root / relative
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    for parent in path.parents:
        if parent == root.parent:
            break
        os.chmod(parent, 0o700)
    path.write_bytes(payload)
    os.chmod(path, 0o600)


def _persisted(
    schema: str,
    obj: object,
    values: dict[str, object],
) -> bytes:
    return migration_tests.PersistedDocTests.wrapper(schema, obj, values)


def _authorization_bytes(
    kind: str,
    document: cm.WindowAuthorizationDoc | cm.ContinuationDoc,
) -> bytes:
    values: dict[str, object] = {
        "schema": document.schema_version,
        "binding_sha256": document.preimage_sha256,
        "window_id": document.window_id,
        "phases": list(document.phases),
        "boot_id": document.boot_id,
        "nonce": document.nonce,
        "issued_at": document.issued_at,
        "expires_at": document.expires_at,
        "owner": document.owner,
    }
    if type(document) is cm.ContinuationDoc:
        values["parent_vulkan_packet_sha256"] = (
            document.parent_vulkan_packet_sha256
        )
    return driver.ProductionArtifactPolicy().encode(kind, values)


def _consumption_bytes(receipt: cm.ConsumptionReceipt) -> bytes:
    return _persisted(
        cm.CONSUMPTION_RECEIPT_SCHEMA,
        receipt,
        {
            "nonce": receipt.nonce,
            "phase": receipt.phase,
            "boot_id": receipt.boot_id,
            "timestamp": receipt.timestamp,
        },
    )


def _quality_bytes(quality: cm.QualityEvidence) -> bytes:
    return _persisted(
        cm.QUALITY_EVIDENCE_SCHEMA,
        quality,
        {
            name: getattr(quality, name)
            for name in migration_tests._QUALITY_EVIDENCE_FIELDS_FOR_TEST
        },
    )


def _owner_bytes(owner: cm.OwnerVoiceReview) -> bytes:
    return _persisted(
        cm.OWNER_VOICE_REVIEW_SCHEMA,
        owner,
        {
            name: getattr(owner, name)
            for name in migration_tests._OWNER_VOICE_REVIEW_FIELDS_FOR_TEST
        },
    )


def _rollback_bytes(rollback: cm.RollbackEvidenceBundle) -> bytes:
    return _persisted(
        cm.ROLLBACK_EVIDENCE_BUNDLE_SCHEMA,
        rollback,
        migration_tests.RollbackEvidenceBundleTests.bundle_fields(rollback),
    )


def _fractional(timestamp: str) -> str:
    assert timestamp.endswith("Z") and "." not in timestamp
    return f"{timestamp[:-1]}.1Z"


def _mutate_persisted_value(name: str, payload: bytes) -> bytes:
    document = cm.PersistedDoc(payload)
    wrapper = json.loads(payload)
    if name in {"bench_identity", "runtime_identity"}:
        updates = {
            "cmake_version": (
                "3.29.0"
                if document.obj.cmake_version != "3.29.0"
                else "4.2.3"
            )
        }
    elif name == "owner_voice":
        updates = {"evaluator_version": "voice-mutated"}
    else:
        updates = {"timestamp": _fractional(document.obj.timestamp)}
    changed = replace(document.obj, **updates)
    wrapper["fields"].update(updates)
    wrapper["binding_sha256"] = changed.binding_sha256
    encoded = cm._canonical_wrapper_bytes(wrapper)
    assert cm.PersistedDoc(encoded).obj == changed
    return encoded


def _mutate_admission(payload: bytes) -> bytes:
    wrapper = json.loads(payload)
    wrapper["fields"]["timestamp"] = _fractional(
        wrapper["fields"]["timestamp"]
    )
    encoded = cm._canonical_wrapper_bytes(wrapper)
    cm.CommandAdmissionPreimage(
        f"command-{wrapper['fields']['command']}-attempt-"
        f"{wrapper['fields']['ordinal']:03d}-admission.json",
        encoded,
    )
    return encoded


def _mutate_authorization(name: str, payload: bytes) -> bytes:
    wrapper = json.loads(payload)
    wrapper["fields"]["issued_at"] = _fractional(
        wrapper["fields"]["issued_at"]
    )
    wrapper["fields"]["expires_at"] = _fractional(
        wrapper["fields"]["expires_at"]
    )
    values = {
        **wrapper["fields"],
        "phases": tuple(wrapper["fields"]["phases"]),
    }
    document = (
        cm.WindowAuthorizationDoc(**values)
        if name == "window_authorization"
        else cm.ContinuationDoc(**values)
    )
    wrapper["binding_sha256"] = document.preimage_sha256
    encoded = cm._canonical_wrapper_bytes(wrapper)
    parser = (
        driver.parse_window_authorization
        if name == "window_authorization"
        else driver.parse_continuation
    )
    assert parser(encoded).preimage_sha256 == document.preimage_sha256
    return encoded


def _valid_canonical_mutation(name: str, payload: bytes) -> bytes:
    if name in {
        "static_admission",
        "control_admission",
        "candidate_admission",
    }:
        return _mutate_admission(payload)
    if name in {"window_authorization", "continuation"}:
        return _mutate_authorization(name, payload)
    return _mutate_persisted_value(name, payload)


def _materialize_stage_one(root: Path) -> tuple[object, object]:
    os.chmod(root, 0o700)
    bundle = migration_tests._make_bundle(1, timestamp=TIMESTAMP)
    refs = {
        "control_packet": bundle.control_packet_ref,
        "candidate_packet": bundle.candidate_packet_ref,
        "static_admission": bundle.static_admission.selected_ref,
        "static_completion": "completions/static-preflight.json",
        "control_admission": bundle.control_admission.selected_ref,
        "control_completion": "completions/vulkan-baseline.json",
        "candidate_admission": bundle.candidate_admission.selected_ref,
        "candidate_completion": "completions/cuda-candidate.json",
        "window_authorization": "authorizations/window.json",
        "continuation": "authorizations/continuation.json",
        "window_consumption": "receipts/window-consumption.json",
        "continuation_consumption": "receipts/continuation-consumption.json",
        "control_containment_before": "containment/control-before.json",
        "control_containment_after": "containment/control-after.json",
        "candidate_containment_before": "containment/candidate-before.json",
        "candidate_containment_after": "containment/candidate-after.json",
        "bench_identity": "identity/bench.json",
        "runtime_identity": "identity/runtime.json",
        "static_preflight": bundle.static_preflight_ref,
        "quality": "evidence/quality.json",
        "owner_voice": "evidence/owner-voice.json",
        "rollback": "evidence/rollback.json",
    }
    payloads = {
        "control_packet": bundle.control_packet_doc.wrapper_bytes,
        "candidate_packet": bundle.candidate_packet_doc.wrapper_bytes,
        "static_admission": bundle.static_admission.wrapper_bytes,
        "static_completion": bundle.static_completion.wrapper_bytes,
        "control_admission": bundle.control_admission.wrapper_bytes,
        "control_completion": bundle.control_completion.wrapper_bytes,
        "candidate_admission": bundle.candidate_admission.wrapper_bytes,
        "candidate_completion": bundle.candidate_completion.wrapper_bytes,
        "window_authorization": _authorization_bytes(
            "window_authorization", bundle.window_authorization
        ),
        "continuation": _authorization_bytes(
            "continuation", bundle.continuation
        ),
        "window_consumption": _consumption_bytes(bundle.window_consumption),
        "continuation_consumption": _consumption_bytes(
            bundle.continuation_consumption
        ),
        "control_containment_before": bundle.containment_docs[
            "vulkan_baseline:before"
        ].wrapper_bytes,
        "control_containment_after": bundle.containment_docs[
            "vulkan_baseline:after"
        ].wrapper_bytes,
        "candidate_containment_before": bundle.containment_docs[
            "cuda_candidate:before"
        ].wrapper_bytes,
        "candidate_containment_after": bundle.containment_docs[
            "cuda_candidate:after"
        ].wrapper_bytes,
        "bench_identity": bundle.bench_identity_doc.wrapper_bytes,
        "runtime_identity": bundle.runtime_identity_doc.wrapper_bytes,
        "static_preflight": bundle.static_preflight.wrapper_bytes,
        "quality": _quality_bytes(bundle.quality),
        "owner_voice": _owner_bytes(bundle.owner_voice),
        "rollback": _rollback_bytes(bundle.rollback),
    }
    for name in EXPECTED_PATH_FIELDS:
        _write_private(root, refs[name], payloads[name])
    return assemble.Stage1ArtifactPaths(**refs), bundle


def _build(root: Path, paths: object) -> cm.BenchEvidenceBundle:
    return assemble.build_stage1_bundle(paths, root=root, timestamp=TIMESTAMP)


def _keep_vulkan_bundle() -> cm.BenchEvidenceBundle:
    bundle = migration_tests._make_bundle(1, timestamp=TIMESTAMP)
    quality = replace(bundle.quality, false_absence_count=1)
    control_summary = migration_tests._summary_for_bundle_packet(
        bundle.control_packet,
        quality=quality,
        owner=bundle.owner_voice,
        rollback_witness=bundle.rollback.witness,
    )
    candidate_summary = migration_tests._summary_for_bundle_packet(
        bundle.candidate_packet,
        quality=quality,
        owner=bundle.owner_voice,
        rollback_witness=bundle.rollback.witness,
    )
    return cm.BenchEvidenceBundle(
        **{
            **migration_tests._bundle_values(bundle),
            "quality": quality,
            "control_summary": control_summary,
            "candidate_summary": candidate_summary,
        }
    )


def test_artifact_paths_are_exactly_the_twenty_two_ratified_roles() -> None:
    assert tuple(field.name for field in fields(assemble.Stage1ArtifactPaths)) == (
        EXPECTED_PATH_FIELDS
    )


def test_stage1_bundle_maps_summaries_and_canonical_containment_order(
    tmp_path: Path,
) -> None:
    paths, expected = _materialize_stage_one(tmp_path)
    bundle = _build(tmp_path, paths)

    assert bundle.control_packet == expected.control_packet
    assert bundle.candidate_packet == expected.candidate_packet
    assert cm.phase_summary_projection(bundle.control_summary) == json.loads(
        bundle.control_packet.summary_projection_json
    )
    assert cm.phase_summary_projection(bundle.candidate_summary) == json.loads(
        bundle.candidate_packet.summary_projection_json
    )
    assert tuple(
        (snapshot.phase, snapshot.boundary)
        for snapshot in bundle.containment.snapshots
    ) == (
        ("vulkan_baseline", "before"),
        ("vulkan_baseline", "after"),
        ("cuda_candidate", "before"),
        ("cuda_candidate", "after"),
        ("vulkan_rollback", "before"),
        ("vulkan_rollback", "after"),
    )


def test_stage1_bundle_is_the_genuine_p1_prefix(tmp_path: Path) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    bundle = _build(tmp_path, paths)

    assert bundle.boot_authorization.status == "not_attempted"
    assert bundle.live_authorization.status == "not_attempted"
    assert bundle.cold_boot_maps is None
    assert bundle.provisional_live_maps is None
    assert bundle.control_summary.cold_boot_witness is None
    assert bundle.candidate_summary.cold_boot_witness is None
    assert bundle.control_summary.provisional_live_witness is None
    assert bundle.candidate_summary.provisional_live_witness is None


@pytest.mark.parametrize("name", EXPECTED_PATH_FIELDS)
def test_each_selected_artifact_mutation_changes_binding_or_refuses(
    tmp_path: Path,
    name: str,
) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    baseline = _build(tmp_path, paths)
    selected = tmp_path / getattr(paths, name)
    selected.write_bytes(
        _valid_canonical_mutation(name, selected.read_bytes())
    )
    os.chmod(selected, 0o600)

    try:
        changed = _build(tmp_path, paths)
    except driver.BenchRefusal as exc:
        assert exc.code == "assembly_refused"
    else:
        assert changed.binding_sha256 != baseline.binding_sha256


@pytest.mark.parametrize(
    ("admission_name", "completion_name"),
    (
        ("static_admission", "static_completion"),
        ("control_admission", "control_completion"),
        ("candidate_admission", "candidate_completion"),
    ),
)
def test_correct_role_orphan_admission_without_completion_refuses(
    tmp_path: Path,
    admission_name: str,
    completion_name: str,
) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    assert (tmp_path / getattr(paths, admission_name)).is_file()
    (tmp_path / getattr(paths, completion_name)).unlink()

    with pytest.raises(driver.BenchRefusal, match="assembly_refused"):
        _build(tmp_path, paths)


@pytest.mark.parametrize(
    ("target", "source"),
    (
        ("control_admission", "static_admission"),
        ("candidate_admission", "control_admission"),
        ("control_admission", "candidate_admission"),
    ),
)
def test_cross_role_admission_substitution_refuses(
    tmp_path: Path,
    target: str,
    source: str,
) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    changed = replace(paths, **{target: getattr(paths, source)})

    with pytest.raises(driver.BenchRefusal, match="assembly_refused"):
        _build(tmp_path, changed)


def test_admission_wrapper_in_non_admission_role_refuses(tmp_path: Path) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    changed = replace(paths, quality=paths.control_admission)

    with pytest.raises(driver.BenchRefusal, match="assembly_refused"):
        _build(tmp_path, changed)


def test_rehearsal_schema_refuses_before_bundle_construction(tmp_path: Path) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    selected = tmp_path / paths.quality
    selected.write_bytes(
        (
            json.dumps(
                {
                    "rehearsal_schema": driver.REHEARSAL_PACKET_SCHEMA,
                    "tier": "rehearsal",
                    "payload": {"kind": "quality", "fields": {}},
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
    )
    os.chmod(selected, 0o600)

    with pytest.raises(driver.BenchRefusal, match="assembly_refused"):
        _build(tmp_path, paths)


@pytest.mark.parametrize("target", PERSISTED_PATH_FIELDS)
def test_each_persisted_role_rejects_a_wrong_typed_document(
    tmp_path: Path,
    target: str,
) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    wrong = (
        paths.quality
        if target not in {"quality", "owner_voice"}
        else paths.control_packet
    )

    with pytest.raises(driver.BenchRefusal, match="assembly_refused"):
        _build(tmp_path, replace(paths, **{target: wrong}))


@pytest.mark.parametrize("name", ("window_authorization", "continuation"))
@pytest.mark.parametrize("mutation", ("whitespace", "key_order"))
def test_authorizations_are_canonical_before_parse(
    tmp_path: Path,
    name: str,
    mutation: str,
) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    selected = tmp_path / getattr(paths, name)
    decoded = json.loads(selected.read_bytes())
    if mutation == "whitespace":
        changed = json.dumps(decoded, sort_keys=True, indent=1).encode() + b"\n"
    else:
        changed = json.dumps(
            {key: decoded[key] for key in reversed(tuple(decoded))},
            separators=(",", ":"),
        ).encode() + b"\n"
    selected.write_bytes(changed)
    os.chmod(selected, 0o600)

    with pytest.raises(driver.BenchRefusal, match="assembly_refused"):
        _build(tmp_path, paths)


def test_selected_current_identity_cannot_be_ignored(tmp_path: Path) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    selected = tmp_path / paths.runtime_identity
    selected.write_bytes(
        _mutate_persisted_value("runtime_identity", selected.read_bytes())
    )
    os.chmod(selected, 0o600)

    with pytest.raises(driver.BenchRefusal, match="assembly_refused"):
        _build(tmp_path, paths)


def test_explicit_selection_opens_exactly_twenty_two_and_ignores_decoys(
    tmp_path: Path,
) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    _write_private(tmp_path, "evidence/decoy.json", b"not evidence\n")
    observed: list[str] = []
    real_open = driver.open_bench_file

    def recording_open(relative: str, *, root: Path) -> bytes:
        observed.append(relative)
        return real_open(relative, root=root)

    with mock.patch.object(assemble, "open_bench_file", recording_open):
        _build(tmp_path, paths)

    assert observed == [getattr(paths, name) for name in EXPECTED_PATH_FIELDS]
    assert "evidence/decoy.json" not in observed


@pytest.mark.parametrize("hazard", ("absolute", "parent", "missing"))
def test_anchored_locator_safety_refuses_basic_escapes(
    tmp_path: Path,
    hazard: str,
) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    changed_ref = {
        "absolute": str((tmp_path / paths.quality).resolve()),
        "parent": "../quality.json",
        "missing": "evidence/missing.json",
    }[hazard]

    with pytest.raises(driver.BenchRefusal, match="assembly_refused"):
        _build(tmp_path, replace(paths, quality=changed_ref))


@pytest.mark.parametrize(
    "hazard",
    ("symlink_final", "symlink_component", "hardlink", "directory", "wrong_mode"),
)
def test_anchored_locator_safety_refuses_filesystem_hazards(
    tmp_path: Path,
    hazard: str,
) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    source = tmp_path / paths.quality
    selected = f"hazards/{hazard}.json"
    target = tmp_path / selected
    target.parent.mkdir(mode=0o700)
    if hazard == "symlink_final":
        target.symlink_to(source)
    elif hazard == "symlink_component":
        target.parent.rmdir()
        target.parent.symlink_to(source.parent, target_is_directory=True)
    elif hazard == "hardlink":
        os.link(source, target)
    elif hazard == "directory":
        target.mkdir(mode=0o700)
    else:
        target.write_bytes(source.read_bytes())
        os.chmod(target, 0o644)

    with pytest.raises(driver.BenchRefusal, match="assembly_refused"):
        _build(tmp_path, replace(paths, quality=selected))


def test_wrong_owner_refuses_before_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    monkeypatch.setattr(driver.os, "geteuid", lambda: os.getuid() + 1)

    with pytest.raises(driver.BenchRefusal, match="assembly_refused"):
        _build(tmp_path, paths)


@pytest.mark.parametrize(
    "completion_overrides",
    (
        {"static_completion": None},
        {"control_completion": "candidate_completion"},
        {"candidate_completion": "static_completion"},
        {"control_completion": "forged"},
    ),
)
def test_direct_bundle_construction_cannot_bypass_completion_roles(
    completion_overrides: dict[str, object],
) -> None:
    bundle = migration_tests._make_bundle(1, timestamp=TIMESTAMP)
    values = migration_tests._bundle_values(bundle)
    for target, source in completion_overrides.items():
        if source == "forged":
            completion = bundle.control_completion
            wrapper = json.loads(completion.wrapper_bytes)
            wrapper["fields"]["admission_sha256"] = "f" * 64
            changed = replace(
                completion.obj,
                admission_sha256="f" * 64,
            )
            wrapper["binding_sha256"] = changed.binding_sha256
            values[target] = cm.PersistedDoc(
                cm._canonical_wrapper_bytes(wrapper)
            )
        else:
            values[target] = (
                getattr(bundle, source) if isinstance(source, str) else source
            )

    with pytest.raises((TypeError, ValueError), match="bundle_binding"):
        cm.BenchEvidenceBundle(**values)


def test_assembler_uses_only_anchored_explicit_selection() -> None:
    source = Path(assemble.__file__).read_text()
    tree = ast.parse(source)
    banned = {"glob", "rglob", "iterdir", "scandir", "open"}
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    called.update(
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    )
    assert called.isdisjoint(banned)


def test_assembler_is_measurement_free_and_imports_only_four_driver_names() -> None:
    source = Path(assemble.__file__).read_text()
    tree = ast.parse(source)
    driver_imports = tuple(
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "scripts.cuda_bench_driver"
        for alias in node.names
    )
    assert driver_imports == (
        "BenchRefusal",
        "open_bench_file",
        "parse_continuation",
        "parse_window_authorization",
    )
    forbidden = (
        "subprocess",
        "socket",
        "systemctl",
        "nvidia-smi",
        "GpuProvider",
        "ServerLauncher",
        "journalctl",
        "_evaluate_promotion_gate",
    )
    assert all(token not in source for token in forbidden)


def test_stage1_evaluation_is_a_frozen_slotted_result() -> None:
    assert tuple(assemble.Stage1Evaluation.__slots__) == (
        "bundle",
        "verdict",
        "receipt",
    )
    bundle = migration_tests._make_bundle(1, timestamp=TIMESTAMP)
    verdict = cm.evaluate_promotion_bundle(bundle)
    result = assemble.Stage1Evaluation(
        bundle=bundle,
        verdict=verdict,
        receipt=MappingProxyType({}),
    )

    with pytest.raises(FrozenInstanceError):
        result.receipt = MappingProxyType({"changed": True})


def test_public_scorer_call_count_is_twice_on_the_same_built_bundle(
    tmp_path: Path,
) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    real_evaluate = cm.evaluate_promotion_bundle
    observed: list[cm.BenchEvidenceBundle] = []

    def recording_evaluate(
        bundle: cm.BenchEvidenceBundle,
    ) -> cm.PromotionVerdict:
        observed.append(bundle)
        return real_evaluate(bundle)

    with mock.patch.object(
        cm, "evaluate_promotion_bundle", recording_evaluate
    ):
        result = assemble.assemble_stage1(
            paths,
            root=tmp_path,
            timestamp=TIMESTAMP,
        )

    assert len(observed) == 2
    assert observed[0] is observed[1] is result.bundle
    assert result.verdict.decision == "bench_passed"


@pytest.mark.parametrize("collision_at", ("explicit_scorer", "receipt_reentry"))
def test_post_build_assembly_refusal_is_internal_evaluation_failure(
    tmp_path: Path,
    collision_at: str,
) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    real_evaluate = cm.evaluate_promotion_bundle
    observed: list[cm.BenchEvidenceBundle] = []

    def colliding_evaluate(
        bundle: cm.BenchEvidenceBundle,
    ) -> cm.PromotionVerdict:
        observed.append(bundle)
        if collision_at == "explicit_scorer" or len(observed) == 2:
            raise driver.BenchRefusal("assembly_refused")
        return real_evaluate(bundle)

    with (
        mock.patch.object(
            cm,
            "evaluate_promotion_bundle",
            colliding_evaluate,
        ),
        pytest.raises(Exception) as captured,
    ):
        assemble.assemble_stage1(
            paths,
            root=tmp_path,
            timestamp=TIMESTAMP,
        )

    assert type(captured.value).__name__ == "_Stage1EvaluationFailure"
    assert not isinstance(captured.value, driver.BenchRefusal)
    assert len(observed) == (
        1 if collision_at == "explicit_scorer" else 2
    )
    assert all(type(bundle) is cm.BenchEvidenceBundle for bundle in observed)
    assert len({id(bundle) for bundle in observed}) == 1


def test_bench_passed_receipt_is_immutable_and_bound_to_both_bundle_hashes(
    tmp_path: Path,
) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    result = assemble.assemble_stage1(
        paths,
        root=tmp_path,
        timestamp=TIMESTAMP,
    )

    assert type(result.receipt) is MappingProxyType
    assert result.verdict.decision == "bench_passed"
    assert result.receipt["decision"] == "bench_passed"
    assert (
        result.receipt["bench_binding_sha256"]
        == result.bundle.bench_binding_sha256
    )
    assert (
        result.receipt["bundle_binding_sha256"]
        == result.bundle.binding_sha256
    )
    assert (
        result.receipt["gate_bindings"]["bench_evidence_sha256"]
        == result.bundle.bench_binding_sha256
    )


def test_keep_vulkan_is_a_distinct_scorer_minted_stage1_verdict(
    tmp_path: Path,
) -> None:
    bundle = _keep_vulkan_bundle()
    with mock.patch.object(
        assemble,
        "build_stage1_bundle",
        return_value=bundle,
    ):
        result = assemble.assemble_stage1(
            mock.sentinel.paths,
            root=tmp_path,
            timestamp=TIMESTAMP,
        )

    assert result.verdict.decision == "keep_vulkan"
    assert result.verdict.reasons == ("false_absence",)
    assert result.receipt["decision"] == "keep_vulkan"
    assert result.receipt["bench_binding_sha256"] == bundle.bench_binding_sha256
    assert result.receipt["bundle_binding_sha256"] == bundle.binding_sha256


def test_structural_refusal_never_calls_public_scorer_or_receipt_builder(
    tmp_path: Path,
) -> None:
    paths, _expected = _materialize_stage_one(tmp_path)
    (tmp_path / paths.quality).unlink()

    with (
        mock.patch.object(
            cm,
            "evaluate_promotion_bundle",
            side_effect=AssertionError("scorer called"),
        ),
        mock.patch.object(
            cm,
            "build_receipt",
            side_effect=AssertionError("receipt builder called"),
        ),
        pytest.raises(driver.BenchRefusal, match="assembly_refused"),
    ):
        assemble.assemble_stage1(
            paths,
            root=tmp_path,
            timestamp=TIMESTAMP,
        )


class TestLeanAirlockIntegration:
    def test_stage1_owner_selected_evidence_returns_bundle_bound_verdict_without_mutation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        outside = tmp_path / "outside"
        outside.mkdir(mode=0o700)
        outside_witness = outside / "production-witness"
        outside_witness.write_bytes(b"unchanged\n")
        os.chmod(outside_witness, 0o600)
        paths, _expected = _materialize_stage_one(root)
        production_witness = {
            relative: hashlib.sha256(
                (Path(__file__).parents[1] / relative).read_bytes()
            ).hexdigest()
            for relative in (
                "scripts/cuda_migration.py",
                "scripts/cuda_bench_driver.py",
            )
        }
        before = {
            path.relative_to(tmp_path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in tmp_path.rglob("*")
            if path.is_file()
        }
        opened: list[tuple[str, Path]] = []
        real_open = driver.open_bench_file

        def recording_open(relative: str, *, root: Path) -> bytes:
            opened.append((relative, root))
            return real_open(relative, root=root)

        monkeypatch.setattr(assemble, "open_bench_file", recording_open)
        scorer_calls: list[cm.BenchEvidenceBundle] = []
        real_scorer = cm.evaluate_promotion_bundle

        def recording_scorer(
            bundle: cm.BenchEvidenceBundle,
        ) -> cm.PromotionVerdict:
            scorer_calls.append(bundle)
            return real_scorer(bundle)

        monkeypatch.setattr(
            cm,
            "evaluate_promotion_bundle",
            recording_scorer,
        )
        forbidden = mock.Mock(
            side_effect=AssertionError("forbidden action surface reached")
        )
        writer_calls: list[Path] = []

        def guarded_writer(
            *args: object,
            root: Path,
            **_kwargs: object,
        ) -> object:
            relative = args[0] if args and type(args[0]) is str else "terminal"
            target = (root / relative).resolve()
            writer_calls.append(target)
            if (
                root.resolve() != admitted_root
                or not target.is_relative_to(admitted_root)
            ):
                raise AssertionError("write outside admitted root")
            raise AssertionError("filesystem writer reached")

        admitted_root = root.resolve()
        for name in (
            "write_private_file",
            "publish_command_artifact",
            "publish_or_verify_immutable",
        ):
            monkeypatch.setattr(driver, name, guarded_writer)
        for target, names in (
            (
                driver,
                (
                    "run_phase",
                    "production_tier",
                    "rehearsal_tier",
                    "RealServiceStateProvider",
                    "RealGpuProvider",
                    "ServerLauncher",
                ),
            ),
            (
                cm,
                (
                    "stop_service",
                    "start_service",
                    "restart_service",
                    "install_override",
                    "remove_override",
                    "set_model_pointer",
                    "switch_model_pointer",
                    "cutover",
                    "rollback_drill",
                ),
            ),
        ):
            for name in names:
                monkeypatch.setattr(target, name, forbidden, raising=False)

        result = assemble.assemble_stage1(
            paths,
            root=root,
            timestamp=TIMESTAMP,
        )

        after = {
            path.relative_to(tmp_path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in tmp_path.rglob("*")
            if path.is_file()
        }
        assert result.verdict.decision == "bench_passed"
        assert result.receipt["bundle_binding_sha256"] == result.bundle.binding_sha256
        assert result.receipt["bench_binding_sha256"] == result.bundle.bench_binding_sha256
        assert opened == [
            (getattr(paths, name), root) for name in EXPECTED_PATH_FIELDS
        ]
        assert len(scorer_calls) == 2
        assert scorer_calls[0] is scorer_calls[1] is result.bundle
        forbidden.assert_not_called()
        assert writer_calls == []
        assert after == before
        assert production_witness == {
            relative: hashlib.sha256(
                (Path(__file__).parents[1] / relative).read_bytes()
            ).hexdigest()
            for relative in production_witness
        }
