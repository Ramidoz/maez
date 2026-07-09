# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Private, non-admitting frozen-frame vision bake-off (Vision Slice 3)."""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
import re
import secrets
import stat
import subprocess
import tempfile
import threading
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Literal, Mapping, Sequence, TypeVar
from urllib.parse import urlsplit

import requests

from core.vision_contract.frozen_frame import (
    TRANSFORM_ORDER,
    Coverage,
    FrameCase,
    FrozenTransform,
    HarnessRefusal,
    InventedSpecificity,
    ScoringRefusal,
    aggregate_coverage,
    check_evidence_monotonicity,
    derive_transforms,
    find_invented_specificity,
    find_invented_specificity_in_text,
    frame_hash_projection,
    load_frame_case,
    load_manifest,
    score_transform,
)
from core.vision_contract.truth_contract import (
    Verdict,
    build_transcribe_request,
    parse_and_validate,
)

CandidateConfigReason = Literal[
    "invalid_candidate",
    "invalid_base_url",
    "candidate_not_ready",
    "candidate_model_mismatch",
    "candidate_protocol_error",
]

_CANDIDATE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_REPO_ROOT = Path(__file__).resolve().parent.parent
_CANONICAL_IN_REPO_BENCH = _REPO_ROOT / "local" / "vision_bench"
_NVIDIA_SMI_PATH = Path("/usr/bin/nvidia-smi")

ArtifactChainReason = Literal[
    "bench_root_not_private",
    "bench_root_not_allowed",
    "invalid_run_id",
    "artifact_exists",
    "artifact_write_failed",
    "diagnostic_path_invalid",
    "diagnostic_missing",
    "diagnostic_hash_mismatch",
    "diagnostic_schema_invalid",
    "diagnostic_finding_missing",
]
VramWitnessStatus = Literal["scored", "unscored"]
VramMissingReason = Literal[
    "vram_after_load_missing",
    "vram_after_image_missing",
]
VramSamplingReason = Literal["vram_poller_not_ready"]
T = TypeVar("T")


class CandidateConfigError(ValueError):
    """Content-free refusal for an unsafe or unavailable bench candidate."""

    def __init__(self, reason: CandidateConfigReason) -> None:
        self.reason = reason
        super().__init__(reason)


class ArtifactChainError(ValueError):
    """Content-free failure while writing or resolving private diagnostics."""

    def __init__(self, reason: ArtifactChainReason) -> None:
        self.reason = reason
        super().__init__(reason)


class VramSamplingError(RuntimeError):
    """Typed, content-free failure of the finite VRAM polling lifecycle."""

    def __init__(self, reason: VramSamplingReason) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class PrivateArtifactChain:
    diagnostic_path: str
    diagnostic_sha256: str
    transcript_path: str
    transcript_sha256: str
    invented_findings: tuple[InventedSpecificity, ...]


@dataclass(frozen=True)
class VramWitness:
    vram_after_load_mib: int | None
    vram_after_image_mib: int | None
    status: VramWitnessStatus
    reason: VramMissingReason | None


@dataclass(frozen=True)
class PreparedFrame:
    case: FrameCase
    transforms: tuple[FrozenTransform, ...]


@dataclass(frozen=True)
class CandidateSpec:
    label: str
    base_url: str
    model: str

    def __post_init__(self) -> None:
        if not (
            isinstance(self.label, str)
            and _CANDIDATE_NAME_RE.fullmatch(self.label)
            and isinstance(self.model, str)
            and _CANDIDATE_NAME_RE.fullmatch(self.model)
        ):
            raise CandidateConfigError("invalid_candidate")
        try:
            parsed = urlsplit(self.base_url)
            explicit_port = parsed.port
        except (AttributeError, TypeError, ValueError):
            raise CandidateConfigError("invalid_base_url") from None
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost"}
            or explicit_port is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise CandidateConfigError("invalid_base_url")
        object.__setattr__(
            self,
            "base_url",
            f"http://{parsed.hostname}:{explicit_port}",
        )


class HttpCandidateInvoker:
    """Call one already-running loopback candidate through the Slice 2 contract."""

    def __init__(
        self,
        spec: CandidateSpec,
        *,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.spec = spec
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.trust_env = False
        self._last_raw: str | None = None

    def _clear_proxy_routes(self) -> None:
        # http.client's global debug mode prints entire request bodies. A
        # frozen frame must remain private even if another tool enabled it.
        http.client.HTTPConnection.debuglevel = 0
        self.session.proxies.clear()

    @property
    def last_raw(self) -> str | None:
        """The last untrusted response, for private quarantine artifacts only."""
        return self._last_raw

    def verify_ready(self) -> None:
        self._clear_proxy_routes()
        try:
            response = self.session.get(
                f"{self.spec.base_url}/v1/models",
                timeout=self.timeout_seconds,
                allow_redirects=False,
            )
            if response.status_code != 200:
                raise CandidateConfigError("candidate_not_ready")
            payload = response.json()
        except CandidateConfigError:
            raise
        except (requests.RequestException, ValueError, TypeError):
            raise CandidateConfigError("candidate_not_ready") from None
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise CandidateConfigError("candidate_not_ready")
        model_ids = {
            item.get("id")
            for item in data
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        if self.spec.model not in model_ids:
            raise CandidateConfigError("candidate_model_mismatch")

    def invoke(self, image_png: bytes) -> Verdict:
        self._last_raw = None
        self._clear_proxy_routes()
        request = build_transcribe_request(
            image_b64=base64.b64encode(image_png).decode("ascii"),
            model=self.spec.model,
        )
        try:
            response = self.session.post(
                f"{self.spec.base_url}/v1/chat/completions",
                json=request,
                timeout=self.timeout_seconds,
                allow_redirects=False,
            )
            if response.status_code != 200:
                raise CandidateConfigError("candidate_protocol_error")
            payload = response.json()
        except CandidateConfigError:
            raise
        except (requests.RequestException, ValueError, TypeError):
            raise CandidateConfigError("candidate_protocol_error") from None
        try:
            raw = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raw = None
        self._last_raw = raw if isinstance(raw, str) else None
        return parse_and_validate(raw)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _private_bench_root(bench_root: Path) -> Path:
    root = Path(bench_root)
    try:
        lexical = Path(os.path.abspath(root))
        if any(path.is_symlink() for path in (lexical, *lexical.parents)):
            raise ArtifactChainError("bench_root_not_private")
        if not lexical.is_dir():
            raise ArtifactChainError("bench_root_not_private")
        resolved = lexical.resolve(strict=True)
        root_stat = resolved.stat()
        if (
            root_stat.st_uid != os.geteuid()
            or stat.S_IMODE(root_stat.st_mode) & 0o077
        ):
            raise ArtifactChainError("bench_root_not_private")
    except ArtifactChainError:
        raise
    except OSError:
        raise ArtifactChainError("bench_root_not_private") from None
    return resolved


def _authorized_bench_root(
    bench_root: Path, *, allow_external_test_root: bool = False
) -> Path:
    root = _private_bench_root(bench_root)
    if root == _CANONICAL_IN_REPO_BENCH:
        return root
    temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    if allow_external_test_root and root.is_relative_to(temp_root):
        return root
    raise ArtifactChainError("bench_root_not_allowed")


def _contained_path(root: Path, relative_path: str) -> Path:
    try:
        pure = PurePosixPath(relative_path)
        if (
            not relative_path
            or pure.is_absolute()
            or pure.as_posix() != relative_path
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise ArtifactChainError("diagnostic_path_invalid")
        resolved = root.joinpath(*pure.parts).resolve(strict=False)
        resolved.relative_to(root)
    except ArtifactChainError:
        raise
    except (OSError, TypeError, ValueError):
        raise ArtifactChainError("diagnostic_path_invalid") from None
    return resolved


def _secure_write(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
    except FileExistsError:
        raise ArtifactChainError("artifact_exists") from None
    except OSError:
        raise ArtifactChainError("artifact_write_failed") from None


def write_private_artifacts(
    bench_root: Path,
    *,
    run_id: str,
    transcripts: Mapping[str, str | None],
    invented_findings: Sequence[InventedSpecificity],
    allow_external_test_root: bool = False,
) -> PrivateArtifactChain:
    """Write quarantined literal evidence beneath one private run directory."""
    root = _authorized_bench_root(
        bench_root,
        allow_external_test_root=allow_external_test_root,
    )
    if not isinstance(run_id, str) or not _RUN_ID_RE.fullmatch(run_id):
        raise ArtifactChainError("invalid_run_id")
    runs_dir = _contained_path(root, "runs")
    run_dir = _contained_path(root, f"runs/{run_id}")
    try:
        runs_dir.mkdir(mode=0o700, exist_ok=True)
        if runs_dir.is_symlink() or stat.S_IMODE(runs_dir.stat().st_mode) & 0o077:
            raise ArtifactChainError("bench_root_not_private")
        run_dir.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError:
        raise ArtifactChainError("artifact_exists") from None
    except ArtifactChainError:
        raise
    except OSError:
        raise ArtifactChainError("artifact_write_failed") from None

    unique_findings: dict[tuple[str, str], InventedSpecificity] = {}
    for finding in invented_findings:
        if (
            finding.kind not in {"filename", "shell_command", "shell_prompt"}
            or finding.character_count != len(finding.value)
            or finding.string_sha256 != _sha256(finding.value.encode("utf-8"))
        ):
            raise ArtifactChainError("diagnostic_schema_invalid")
        unique_findings.setdefault((finding.kind, finding.value), finding)
    findings = tuple(unique_findings.values())
    diagnostic_payload = {
        "artifact_class": "UNTRUSTED",
        "quarantined": True,
        "promotable": False,
        "schema_version": "vision_frozen_diagnostic.v1",
        "findings": [
            {
                "kind": finding.kind,
                "literal": finding.value,
                "character_count": finding.character_count,
                "string_sha256": finding.string_sha256,
                "transform_name": finding.transform_name,
            }
            for finding in findings
        ],
    }
    transcript_payload = {
        "artifact_class": "UNTRUSTED",
        "quarantined": True,
        "promotable": False,
        "schema_version": "vision_frozen_transcripts.v1",
        "transcripts": dict(transcripts),
    }
    diagnostic_bytes = _json_bytes(diagnostic_payload)
    transcript_bytes = _json_bytes(transcript_payload)
    diagnostic_path = run_dir / "diagnostics.json"
    transcript_path = run_dir / "transcripts.json"
    _secure_write(diagnostic_path, diagnostic_bytes)
    _secure_write(transcript_path, transcript_bytes)
    return PrivateArtifactChain(
        diagnostic_path=diagnostic_path.relative_to(root).as_posix(),
        diagnostic_sha256=_sha256(diagnostic_bytes),
        transcript_path=transcript_path.relative_to(root).as_posix(),
        transcript_sha256=_sha256(transcript_bytes),
        invented_findings=findings,
    )


def specificity_receipt_entries(
    chain: PrivateArtifactChain,
) -> tuple[dict[str, object], ...]:
    """Project literal findings into the content-light v1.1 receipt shape."""
    return tuple(
        {
            "kind": finding.kind,
            "character_count": finding.character_count,
            "string_sha256": finding.string_sha256,
            "diagnostic_path": chain.diagnostic_path,
            "diagnostic_sha256": chain.diagnostic_sha256,
        }
        for finding in chain.invented_findings
    )


def resolve_receipt_finding(
    bench_root: Path, receipt_finding: Mapping[str, object]
) -> str:
    """Verify receipt -> diagnostic integrity and return its private literal."""
    path_value = receipt_finding.get("diagnostic_path")
    if not isinstance(path_value, str):
        raise ArtifactChainError("diagnostic_path_invalid")
    root = _private_bench_root(bench_root)
    path = _contained_path(root, path_value)
    try:
        raw = path.read_bytes()
    except OSError:
        raise ArtifactChainError("diagnostic_missing") from None
    if receipt_finding.get("diagnostic_sha256") != _sha256(raw):
        raise ArtifactChainError("diagnostic_hash_mismatch")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ArtifactChainError("diagnostic_schema_invalid") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("findings"), list):
        raise ArtifactChainError("diagnostic_schema_invalid")
    matches: list[str] = []
    for item in payload["findings"]:
        if not isinstance(item, dict):
            raise ArtifactChainError("diagnostic_schema_invalid")
        literal = item.get("literal")
        if not isinstance(literal, str):
            raise ArtifactChainError("diagnostic_schema_invalid")
        if (
            item.get("kind") == receipt_finding.get("kind")
            and len(literal) == receipt_finding.get("character_count")
            and _sha256(literal.encode("utf-8"))
            == receipt_finding.get("string_sha256")
        ):
            matches.append(literal)
    if len(matches) != 1:
        raise ArtifactChainError("diagnostic_finding_missing")
    return matches[0]


class NvidiaSmiVramMeter:
    """Finite two-phase peak VRAM sampler for one bench candidate."""

    def __init__(
        self,
        *,
        sample: Callable[[], int | None] | None = None,
        load_sample_count: int = 3,
        poll_interval_seconds: float = 0.05,
        poller_ready_timeout_seconds: float = 5.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if (
            load_sample_count < 1
            or poll_interval_seconds < 0
            or poller_ready_timeout_seconds <= 0
        ):
            raise ValueError("invalid_vram_sampling_config")
        self._sample = sample or self._sample_nvidia_smi
        self._load_sample_count = load_sample_count
        self._poll_interval_seconds = poll_interval_seconds
        self._poller_ready_timeout_seconds = poller_ready_timeout_seconds
        self._sleeper = sleeper

    @staticmethod
    def _sample_nvidia_smi() -> int | None:
        try:
            if not _NVIDIA_SMI_PATH.is_file() or not os.access(
                _NVIDIA_SMI_PATH, os.X_OK
            ):
                return None
            completed = subprocess.run(
                [
                    "/usr/bin/nvidia-smi",
                    "--query-gpu=memory.used",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            if completed.returncode != 0:
                return None
            values = [
                int(line.strip())
                for line in completed.stdout.splitlines()
                if line.strip()
            ]
            if not values or any(value < 0 for value in values):
                return None
            return sum(values)
        except (OSError, subprocess.SubprocessError, TypeError, ValueError):
            return None

    def _safe_sample(self) -> int | None:
        try:
            value = self._sample()
        except Exception:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return value

    @staticmethod
    def _peak(samples: Sequence[int | None]) -> int | None:
        valid = tuple(sample for sample in samples if sample is not None)
        return max(valid) if valid else None

    def peak_after_load(self) -> int | None:
        samples: list[int | None] = []
        for index in range(self._load_sample_count):
            samples.append(self._safe_sample())
            if index + 1 < self._load_sample_count:
                self._sleeper(self._poll_interval_seconds)
        return self._peak(samples)

    def around_image_batch(self, call: Callable[[], T]) -> tuple[T, int | None]:
        samples: list[int | None] = [self._safe_sample()]
        stop = threading.Event()
        ready = threading.Event()

        def poll() -> None:
            samples.append(self._safe_sample())
            ready.set()
            while not stop.wait(self._poll_interval_seconds):
                samples.append(self._safe_sample())

        thread = threading.Thread(
            target=poll,
            name="maez-vision-vram-poller",
            daemon=True,
        )
        thread.start()
        if not ready.wait(timeout=self._poller_ready_timeout_seconds):
            stop.set()
            thread.join()
            raise VramSamplingError("vram_poller_not_ready")
        try:
            result = call()
        finally:
            samples.append(self._safe_sample())
            stop.set()
            thread.join()
        return result, self._peak(samples)


def build_vram_witness(
    vram_after_load_mib: int | None,
    vram_after_image_mib: int | None,
) -> VramWitness:
    if vram_after_load_mib is None:
        return VramWitness(
            vram_after_load_mib=None,
            vram_after_image_mib=vram_after_image_mib,
            status="unscored",
            reason="vram_after_load_missing",
        )
    if vram_after_image_mib is None:
        return VramWitness(
            vram_after_load_mib=vram_after_load_mib,
            vram_after_image_mib=None,
            status="unscored",
            reason="vram_after_image_missing",
        )
    return VramWitness(
        vram_after_load_mib=vram_after_load_mib,
        vram_after_image_mib=vram_after_image_mib,
        status="scored",
        reason=None,
    )


def _coverage_receipt(coverage: Coverage) -> dict[str, int | float]:
    return {
        "correct_text_numerator": coverage.correct_text_numerator,
        "correct_text_denominator": coverage.correct_text_denominator,
        "correct_text_coverage": coverage.correct_text_coverage,
        "abstention_numerator": coverage.abstention_numerator,
        "abstention_denominator": coverage.abstention_denominator,
        "abstention_coverage": coverage.abstention_coverage,
    }


def _prepare_frames(bench_root: Path) -> tuple[PreparedFrame, ...]:
    prepared: list[PreparedFrame] = []
    empty = parse_and_validate("NO_TEXT_VISIBLE")
    for frame_id in load_manifest(bench_root):
        case = load_frame_case(bench_root, frame_id)
        transforms = derive_transforms(case)
        frame_hash_projection(case, transforms)
        for transform_name in TRANSFORM_ORDER:
            # Transform-scoped human truth is mandatory before any model or
            # VRAM contact. This call is pure and contains no candidate data.
            score_transform(case, transform_name, empty)
        prepared.append(PreparedFrame(case=case, transforms=transforms))
    return tuple(prepared)


def _prepared_frame_receipts(
    prepared_frames: Sequence[PreparedFrame],
) -> list[dict[str, object]]:
    receipts: list[dict[str, object]] = []
    for prepared in prepared_frames:
        case = prepared.case
        projection = frame_hash_projection(case, prepared.transforms)
        receipts.append(
            {
                "frame_id_character_count": len(case.frame_id),
                "frame_id_sha256": _sha256(case.frame_id.encode("utf-8")),
                "source_sha256": projection["source_sha256"],
                "label_sha256": projection["label_sha256"],
                "transforms": [
                    {
                        "name": transform.name,
                        "sha256": transform.sha256,
                        "width": transform.width,
                        "height": transform.height,
                    }
                    for transform in prepared.transforms
                ],
                "contract_verdicts": [],
                "coverage_by_transform": [],
                "aggregate_coverage": None,
                "evidence_findings": [],
                "hard_fail_reasons": [],
            }
        )
    return receipts


def _audit_partial_transcripts(
    prepared_frames: Sequence[PreparedFrame],
    transcripts: Mapping[str, str | None],
) -> tuple[InventedSpecificity, ...]:
    findings: list[InventedSpecificity] = []
    for prepared in prepared_frames:
        for transform_name in TRANSFORM_ORDER:
            raw = transcripts.get(f"{prepared.case.frame_id}/{transform_name}")
            if isinstance(raw, str):
                findings.extend(
                    find_invented_specificity_in_text(
                        prepared.case,
                        transform_name,
                        raw,
                    )
                )
    return tuple(findings)


def _evaluate_frames(
    prepared_frames: Sequence[PreparedFrame],
    invoker: HttpCandidateInvoker,
    transcripts: dict[str, str | None],
) -> tuple[list[dict[str, object]], tuple[InventedSpecificity, ...], list[str]]:
    frame_receipts: list[dict[str, object]] = []
    all_invented: list[InventedSpecificity] = []
    hard_fail_reasons: list[str] = []
    for prepared in prepared_frames:
        case = prepared.case
        verdicts: dict[str, Verdict] = {}
        for transform in prepared.transforms:
            verdict = invoker.invoke(transform.png_bytes)
            verdicts[transform.name] = verdict
            transcripts[f"{case.frame_id}/{transform.name}"] = invoker.last_raw

        scores = {}
        frame_invented: list[InventedSpecificity] = []
        frame_reasons: list[str] = []
        for transform_name in TRANSFORM_ORDER:
            verdict = verdicts[transform_name]
            transcript = transcripts.get(f"{case.frame_id}/{transform_name}")
            if isinstance(transcript, str):
                frame_invented.extend(
                    find_invented_specificity_in_text(
                        case,
                        transform_name,
                        transcript,
                    )
                )
            else:
                frame_invented.extend(
                    find_invented_specificity(case, transform_name, verdict)
                )
            try:
                scores[transform_name] = score_transform(
                    case, transform_name, verdict
                )
            except ScoringRefusal as exc:
                frame_reasons.append(exc.reason)

        evidence = ()
        aggregate = None
        if len(scores) == len(TRANSFORM_ORDER):
            evidence = check_evidence_monotonicity(case, verdicts)
            aggregate = aggregate_coverage(tuple(scores[name] for name in TRANSFORM_ORDER))
            frame_reasons.extend(finding.reason for finding in evidence)
        if frame_invented:
            frame_reasons.append("invented_specificity")
        all_invented.extend(frame_invented)
        hard_fail_reasons.extend(frame_reasons)

        hash_projection = frame_hash_projection(case, prepared.transforms)
        frame_receipts.append(
            {
                "frame_id_character_count": len(case.frame_id),
                "frame_id_sha256": _sha256(case.frame_id.encode("utf-8")),
                "source_sha256": hash_projection["source_sha256"],
                "label_sha256": hash_projection["label_sha256"],
                "transforms": [
                    {
                        "name": transform.name,
                        "sha256": transform.sha256,
                        "width": transform.width,
                        "height": transform.height,
                    }
                    for transform in prepared.transforms
                ],
                "contract_verdicts": [
                    {
                        "transform": name,
                        "verdict": verdicts[name].verdict,
                        "reason": verdicts[name].reason,
                        "support": verdicts[name].support,
                        "schema_version": verdicts[name].schema_version,
                        "field_count": len(verdicts[name].fields),
                    }
                    for name in TRANSFORM_ORDER
                ],
                "coverage_by_transform": [
                    {
                        "transform": name,
                        "coverage": _coverage_receipt(scores[name].coverage)
                        if name in scores
                        else None,
                    }
                    for name in TRANSFORM_ORDER
                ],
                "aggregate_coverage": _coverage_receipt(aggregate)
                if aggregate is not None
                else None,
                "evidence_findings": [
                    {
                        "reason": finding.reason,
                        "region_character_count": finding.region_character_count,
                        "region_sha256": finding.region_sha256,
                        "lower_transform": finding.lower_transform,
                        "higher_transform": finding.higher_transform,
                    }
                    for finding in evidence
                ],
                "hard_fail_reasons": sorted(set(frame_reasons)),
            }
        )
    return frame_receipts, tuple(all_invented), hard_fail_reasons


def _write_receipt(
    bench_root: Path,
    run_id: str,
    receipt: Mapping[str, object],
    *,
    allow_external_test_root: bool = False,
) -> str:
    root = _authorized_bench_root(
        bench_root,
        allow_external_test_root=allow_external_test_root,
    )
    receipts_dir = _contained_path(root, "receipts")
    try:
        receipts_dir.mkdir(mode=0o700, exist_ok=True)
        if (
            receipts_dir.is_symlink()
            or stat.S_IMODE(receipts_dir.stat().st_mode) & 0o077
        ):
            raise ArtifactChainError("bench_root_not_private")
    except ArtifactChainError:
        raise
    except OSError:
        raise ArtifactChainError("artifact_write_failed") from None
    relative_path = f"receipts/{run_id}.json"
    _secure_write(_contained_path(root, relative_path), _json_bytes(receipt))
    return relative_path


def _refusal_receipt(
    *, run_id: str, spec: CandidateSpec, reason: str
) -> dict[str, object]:
    return {
        "schema_version": "vision_frozen_receipt.v1",
        "run_id": run_id,
        "status": "refused",
        "refusal_reason": reason,
        "candidate_label": spec.label,
        "model_alias": spec.model,
        "frame_count": 0,
        "frames": [],
        "vram_after_load_mib": None,
        "vram_after_image_mib": None,
        "invented_specificity": [],
    }


def run_bench(
    *,
    bench_root: Path,
    spec: CandidateSpec,
    meter: NvidiaSmiVramMeter,
    run_id: str,
    allow_external_test_root: bool = False,
) -> tuple[str, str]:
    """Evaluate one candidate without ranking, admission, or production writes."""
    if not _RUN_ID_RE.fullmatch(run_id):
        raise ArtifactChainError("invalid_run_id")
    bench_root = _authorized_bench_root(
        bench_root,
        allow_external_test_root=allow_external_test_root,
    )
    try:
        prepared = _prepare_frames(bench_root)
    except (HarnessRefusal, ScoringRefusal) as exc:
        receipt = _refusal_receipt(run_id=run_id, spec=spec, reason=exc.reason)
        return "refused", _write_receipt(
            bench_root,
            run_id,
            receipt,
            allow_external_test_root=allow_external_test_root,
        )

    invoker = HttpCandidateInvoker(spec)
    try:
        invoker.verify_ready()
    except CandidateConfigError as exc:
        receipt = _refusal_receipt(run_id=run_id, spec=spec, reason=exc.reason)
        return "refused", _write_receipt(
            bench_root,
            run_id,
            receipt,
            allow_external_test_root=allow_external_test_root,
        )

    vram_after_load_mib = meter.peak_after_load()
    transcripts: dict[str, str | None] = {}
    try:
        (frame_receipts, invented, hard_fail_reasons), vram_after_image_mib = (
            meter.around_image_batch(
                lambda: _evaluate_frames(prepared, invoker, transcripts)
            )
        )
        sampling_reason = None
    except VramSamplingError as exc:
        frame_receipts = _prepared_frame_receipts(prepared)
        invented = ()
        hard_fail_reasons = []
        vram_after_image_mib = None
        sampling_reason = exc.reason
    except CandidateConfigError as exc:
        chain = write_private_artifacts(
            bench_root,
            run_id=run_id,
            transcripts=transcripts,
            invented_findings=_audit_partial_transcripts(prepared, transcripts),
            allow_external_test_root=allow_external_test_root,
        )
        receipt = {
            "schema_version": "vision_frozen_receipt.v1",
            "run_id": run_id,
            "status": "refused",
            "refusal_reason": exc.reason,
            "candidate_label": spec.label,
            "model_alias": spec.model,
            "frame_count": len(prepared),
            "frames": _prepared_frame_receipts(prepared),
            "vram_after_load_mib": vram_after_load_mib,
            "vram_after_image_mib": None,
            "vram_complete": False,
            "unscored_reason": "vram_after_image_missing",
            "invented_specificity": list(specificity_receipt_entries(chain)),
            "diagnostic_artifact": {
                "path": chain.diagnostic_path,
                "sha256": chain.diagnostic_sha256,
            },
            "transcript_artifact": {
                "path": chain.transcript_path,
                "sha256": chain.transcript_sha256,
            },
        }
        return "refused", _write_receipt(
            bench_root,
            run_id,
            receipt,
            allow_external_test_root=allow_external_test_root,
        )

    chain = write_private_artifacts(
        bench_root,
        run_id=run_id,
        transcripts=transcripts,
        invented_findings=invented,
        allow_external_test_root=allow_external_test_root,
    )
    vram = build_vram_witness(vram_after_load_mib, vram_after_image_mib)
    if hard_fail_reasons:
        status = "hard_fail"
    elif vram.status == "unscored":
        status = "unscored"
    else:
        status = "evaluated"
    reason_counts = Counter(hard_fail_reasons)
    receipt = {
        "schema_version": "vision_frozen_receipt.v1",
        "run_id": run_id,
        "status": status,
        "candidate_label": spec.label,
        "model_alias": spec.model,
        "frame_count": len(prepared),
        "frames": frame_receipts,
        "vram_after_load_mib": vram.vram_after_load_mib,
        "vram_after_image_mib": vram.vram_after_image_mib,
        "vram_complete": vram.status == "scored",
        "unscored_reason": sampling_reason or vram.reason,
        "hard_fail_reason_counts": dict(sorted(reason_counts.items())),
        "invented_specificity": list(specificity_receipt_entries(chain)),
        "diagnostic_artifact": {
            "path": chain.diagnostic_path,
            "sha256": chain.diagnostic_sha256,
        },
        "transcript_artifact": {
            "path": chain.transcript_path,
            "sha256": chain.transcript_sha256,
        },
    }
    return status, _write_receipt(
        bench_root,
        run_id,
        receipt,
        allow_external_test_root=allow_external_test_root,
    )


def _default_run_id() -> str:
    timestamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    return f"{timestamp}-{secrets.token_hex(4)}"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Judge one already-running loopback vision candidate."
    )
    parser.add_argument("--bench-root", type=Path, required=True)
    parser.add_argument("--candidate-label", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    meter: NvidiaSmiVramMeter | None = None,
    run_id: str | None = None,
    allow_external_test_root: bool = False,
) -> int:
    args = _parser().parse_args(argv)
    resolved_run_id = run_id or _default_run_id()
    try:
        spec = CandidateSpec(
            label=args.candidate_label,
            base_url=args.base_url,
            model=args.model,
        )
        status, receipt_path = run_bench(
            bench_root=args.bench_root,
            spec=spec,
            meter=meter or NvidiaSmiVramMeter(),
            run_id=resolved_run_id,
            allow_external_test_root=allow_external_test_root,
        )
    except (CandidateConfigError, ArtifactChainError) as exc:
        print(
            json.dumps(
                {
                    "run_id": resolved_run_id,
                    "status": "refused",
                    "reason": exc.reason,
                    "receipt_path": None,
                },
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "run_id": resolved_run_id,
                "status": status,
                "receipt_path": receipt_path,
            },
            sort_keys=True,
        )
    )
    return 0 if status == "evaluated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
