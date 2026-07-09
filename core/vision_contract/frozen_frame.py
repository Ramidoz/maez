# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Pure frozen-frame evaluation primitives for Vision Organ Slice 3.

This module consumes owner-placed private bench artifacts. It never captures a
screen, contacts a model, writes a receipt, or publishes evidence to Maez.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Literal

from PIL import Image

from core.vision_contract.truth_contract import (
    Field,
    MAX_REGION_CHARS,
    MAX_TEXT_CHARS,
    SpecificityKind,
    Verdict,
    find_specificity_claims,
)

LABEL_SCHEMA_VERSION = "vision_frozen_labels.v1"
MANIFEST_SCHEMA_VERSION = "vision_frozen_manifest.v1"
TRANSFORM_ORDER = ("full_640", "full_1280", "active_native")

RefusalReason = Literal[
    "bench_root_not_private",
    "manifest_missing",
    "manifest_schema_invalid",
    "label_file_missing",
    "label_schema_invalid",
    "labels_empty",
    "human_truth_marker_missing",
    "owner_approval_missing",
    "third_party_review_missing",
    "source_frame_missing",
    "source_frame_invalid",
    "source_hash_mismatch",
    "active_crop_missing",
    "active_crop_invalid",
]
LabelKind = Literal[
    "window_title",
    "filename",
    "command",
    "application_name",
    "error_message",
    "key_string",
]
ScoringReason = Literal[
    "invalid_transform",
    "transform_set_incomplete",
    "candidate_verdict_rejected",
    "labels_empty_for_transform",
    "unknown_region",
]
EvidenceReason = Literal["evidence_contradiction", "evidence_regression"]

_LABEL_KINDS = {
    "window_title",
    "filename",
    "command",
    "application_name",
    "error_message",
    "key_string",
}
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_REGION_ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class HarnessRefusal(ValueError):
    """Typed, content-free refusal raised before evaluation begins."""

    def __init__(self, reason: RefusalReason) -> None:
        self.reason = reason
        super().__init__(reason)


class ScoringRefusal(ValueError):
    """Typed, content-free refusal to score unsupported candidate evidence."""

    def __init__(self, reason: ScoringReason) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class CropBox:
    left: int
    top: int
    right: int
    bottom: int


@dataclass(frozen=True)
class HumanLabel:
    label_id: str
    region_id: str
    aliases: tuple[str, ...]
    kind: LabelKind
    text: str
    visible_in: tuple[str, ...]


@dataclass(frozen=True)
class FrameCase:
    frame_id: str
    source_bytes: bytes
    source_sha256: str
    label_sha256: str
    crop: CropBox
    labels: tuple[HumanLabel, ...]


@dataclass(frozen=True)
class FrozenTransform:
    name: str
    png_bytes: bytes
    sha256: str
    width: int
    height: int


@dataclass(frozen=True)
class Coverage:
    correct_text_numerator: int
    correct_text_denominator: int
    correct_text_coverage: float
    abstention_numerator: int
    abstention_denominator: int
    abstention_coverage: float


@dataclass(frozen=True)
class TransformScore:
    transform_name: str
    coverage: Coverage
    full_value_hashes: tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True)
class EvidenceFinding:
    reason: EvidenceReason
    region_character_count: int
    region_sha256: str
    lower_transform: str
    higher_transform: str


@dataclass(frozen=True)
class InventedSpecificity:
    kind: SpecificityKind
    value: str = dataclass_field(repr=False)
    character_count: int
    string_sha256: str
    transform_name: str


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and ".." not in value
        and bool(_SAFE_ID_RE.fullmatch(value))
    )


def _read_json(path: Path, *, reason: RefusalReason) -> tuple[object, bytes]:
    try:
        raw = path.read_bytes()
        return json.loads(raw), raw
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise HarnessRefusal(reason) from None


def _private_root(bench_root: Path) -> Path:
    root = Path(bench_root)
    try:
        lexical = Path(os.path.abspath(root))
        if any(path.is_symlink() for path in (lexical, *lexical.parents)):
            raise HarnessRefusal("bench_root_not_private")
        if not lexical.is_dir():
            raise HarnessRefusal("bench_root_not_private")
        resolved = lexical.resolve(strict=True)
        root_stat = resolved.stat()
        if (
            root_stat.st_uid != os.geteuid()
            or stat.S_IMODE(root_stat.st_mode) & 0o077
        ):
            raise HarnessRefusal("bench_root_not_private")
    except HarnessRefusal:
        raise
    except OSError:
        raise HarnessRefusal("bench_root_not_private") from None
    return resolved


def _private_artifact(root: Path, *parts: str) -> Path:
    candidate = root.joinpath(*parts)
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError):
        raise HarnessRefusal("bench_root_not_private") from None
    return resolved


def _require_private_input(path: Path) -> None:
    try:
        artifact_stat = path.stat()
        if (
            not stat.S_ISREG(artifact_stat.st_mode)
            or artifact_stat.st_uid != os.geteuid()
            or artifact_stat.st_nlink != 1
        ):
            raise HarnessRefusal("bench_root_not_private")
    except HarnessRefusal:
        raise
    except OSError:
        raise HarnessRefusal("bench_root_not_private") from None


def load_manifest(bench_root: Path) -> tuple[str, ...]:
    """Load the explicit owner corpus manifest; never discover via glob."""
    root = _private_root(bench_root)
    path = _private_artifact(root, "manifest.json")
    if not path.is_file():
        raise HarnessRefusal("manifest_missing")
    _require_private_input(path)
    data, _ = _read_json(path, reason="manifest_schema_invalid")
    if not isinstance(data, dict) or set(data) != {"schema_version", "frames"}:
        raise HarnessRefusal("manifest_schema_invalid")
    frames = data.get("frames")
    if (
        data.get("schema_version") != MANIFEST_SCHEMA_VERSION
        or not isinstance(frames, list)
        or not frames
        or len(frames) > 256
        or any(not _safe_id(item) for item in frames)
        or len(set(frames)) != len(frames)
    ):
        raise HarnessRefusal("manifest_schema_invalid")
    return tuple(frames)


def _load_crop(value: object, *, image_size: tuple[int, int]) -> CropBox:
    if value is None:
        raise HarnessRefusal("active_crop_missing")
    if not isinstance(value, dict) or set(value) != {"left", "top", "right", "bottom"}:
        raise HarnessRefusal("active_crop_invalid")
    coords = tuple(value[name] for name in ("left", "top", "right", "bottom"))
    if any(type(coord) is not int for coord in coords):
        raise HarnessRefusal("active_crop_invalid")
    left, top, right, bottom = coords
    width, height = image_size
    if (
        left < 0
        or top < 0
        or right <= left
        or bottom <= top
        or right > width
        or bottom > height
    ):
        raise HarnessRefusal("active_crop_invalid")
    return CropBox(left=left, top=top, right=right, bottom=bottom)


def _load_human_labels(value: object) -> tuple[HumanLabel, ...]:
    if not isinstance(value, list):
        raise HarnessRefusal("label_schema_invalid")
    if not value:
        raise HarnessRefusal("labels_empty")
    if len(value) > 256:
        raise HarnessRefusal("label_schema_invalid")

    labels: list[HumanLabel] = []
    label_ids: set[str] = set()
    alias_owners: dict[str, str] = {}
    expected_keys = {
        "label_id",
        "region_id",
        "region_aliases",
        "kind",
        "text",
        "visible_in",
    }
    for item in value:
        if not isinstance(item, dict) or set(item) != expected_keys:
            raise HarnessRefusal("label_schema_invalid")
        label_id = item.get("label_id")
        region_id = item.get("region_id")
        aliases = item.get("region_aliases")
        kind = item.get("kind")
        text = item.get("text")
        visible_in = item.get("visible_in")
        if (
            not _safe_id(label_id)
            or label_id in label_ids
            or not _safe_id(region_id)
            or not isinstance(kind, str)
            or kind not in _LABEL_KINDS
            or not isinstance(text, str)
            or not text.strip()
            or len(text) > MAX_TEXT_CHARS
            or not isinstance(aliases, list)
            or not aliases
            or len(aliases) > 16
            or any(
                not isinstance(alias, str)
                or len(alias) > MAX_REGION_CHARS
                or not _REGION_ALIAS_RE.fullmatch(alias)
                for alias in aliases
            )
            or len({alias.casefold() for alias in aliases}) != len(aliases)
            or region_id.casefold() not in {alias.casefold() for alias in aliases}
            or not isinstance(visible_in, list)
            or not visible_in
            or any(not isinstance(name, str) for name in visible_in)
            or len(set(visible_in)) != len(visible_in)
            or any(name not in TRANSFORM_ORDER for name in visible_in)
        ):
            raise HarnessRefusal("label_schema_invalid")
        for alias in aliases:
            key = alias.casefold()
            owner = alias_owners.setdefault(key, region_id)
            if owner != region_id:
                raise HarnessRefusal("label_schema_invalid")
        label_ids.add(label_id)
        labels.append(
            HumanLabel(
                label_id=label_id,
                region_id=region_id,
                aliases=tuple(aliases),
                kind=kind,
                text=text,
                visible_in=tuple(visible_in),
            )
        )
    return tuple(labels)


def load_frame_case(bench_root: Path, frame_id: str) -> FrameCase:
    """Load one explicitly manifested frame and its owner-authored truth."""
    frames = load_manifest(bench_root)
    if not _safe_id(frame_id) or frame_id not in frames:
        raise HarnessRefusal("manifest_schema_invalid")
    root = _private_root(bench_root)
    label_path = _private_artifact(root, "labels", f"{frame_id}.json")
    if not label_path.is_file():
        raise HarnessRefusal("label_file_missing")
    _require_private_input(label_path)
    label_data, label_bytes = _read_json(label_path, reason="label_schema_invalid")
    expected_keys = {
        "schema_version",
        "frame_id",
        "source_sha256",
        "truth_source",
        "owner_approved",
        "third_party_content_reviewed",
        "active_window_crop",
        "labels",
    }
    if not isinstance(label_data, dict) or not set(label_data).issubset(expected_keys):
        raise HarnessRefusal("label_schema_invalid")
    if (
        label_data.get("schema_version") != LABEL_SCHEMA_VERSION
        or label_data.get("frame_id") != frame_id
    ):
        raise HarnessRefusal("label_schema_invalid")
    if label_data.get("truth_source") != "owner_human":
        raise HarnessRefusal("human_truth_marker_missing")
    if label_data.get("owner_approved") is not True:
        raise HarnessRefusal("owner_approval_missing")
    if label_data.get("third_party_content_reviewed") is not True:
        raise HarnessRefusal("third_party_review_missing")
    if "active_window_crop" not in label_data:
        raise HarnessRefusal("active_crop_missing")
    if set(label_data) != expected_keys:
        raise HarnessRefusal("label_schema_invalid")

    source_path = _private_artifact(root, "frames", f"{frame_id}.png")
    if not source_path.is_file():
        raise HarnessRefusal("source_frame_missing")
    _require_private_input(source_path)
    try:
        source_bytes = source_path.read_bytes()
    except OSError:
        raise HarnessRefusal("source_frame_missing") from None
    source_sha256 = _sha256(source_bytes)
    declared_sha256 = label_data.get("source_sha256")
    if not isinstance(declared_sha256, str) or not _SHA256_RE.fullmatch(declared_sha256):
        raise HarnessRefusal("label_schema_invalid")
    if source_sha256 != declared_sha256:
        raise HarnessRefusal("source_hash_mismatch")
    try:
        with Image.open(io.BytesIO(source_bytes)) as image:
            if image.format != "PNG":
                raise HarnessRefusal("source_frame_invalid")
            image.load()
            image_size = image.size
    except HarnessRefusal:
        raise
    except Exception:
        raise HarnessRefusal("source_frame_invalid") from None

    crop = _load_crop(label_data.get("active_window_crop"), image_size=image_size)
    labels = _load_human_labels(label_data.get("labels"))
    return FrameCase(
        frame_id=frame_id,
        source_bytes=source_bytes,
        source_sha256=source_sha256,
        label_sha256=_sha256(label_bytes),
        crop=crop,
        labels=labels,
    )


def _encode_png(image: Image.Image) -> bytes:
    clean = image.copy()
    clean.info.clear()
    output = io.BytesIO()
    clean.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _full_transform(original: Image.Image, max_dimension: int) -> Image.Image:
    longest_edge = max(original.size)
    if longest_edge <= max_dimension:
        return original.copy()
    scale = max_dimension / longest_edge
    target_size = (
        max(1, round(original.width * scale)),
        max(1, round(original.height * scale)),
    )
    return original.resize(target_size, Image.Resampling.LANCZOS)


def derive_transforms(case: FrameCase) -> tuple[FrozenTransform, ...]:
    """Derive every candidate image deterministically from one retained capture."""
    try:
        with Image.open(io.BytesIO(case.source_bytes)) as source:
            source.load()
            original = source.convert("RGB")
    except Exception:
        raise HarnessRefusal("source_frame_invalid") from None
    original.info.clear()
    images = (
        ("full_640", _full_transform(original, 640)),
        ("full_1280", _full_transform(original, 1280)),
        (
            "active_native",
            original.crop(
                (case.crop.left, case.crop.top, case.crop.right, case.crop.bottom)
            ),
        ),
    )
    transforms: list[FrozenTransform] = []
    for name, image in images:
        png_bytes = _encode_png(image)
        transforms.append(
            FrozenTransform(
                name=name,
                png_bytes=png_bytes,
                sha256=_sha256(png_bytes),
                width=image.width,
                height=image.height,
            )
        )
    return tuple(transforms)


def frame_hash_projection(
    case: FrameCase, transforms: tuple[FrozenTransform, ...]
) -> dict[str, object]:
    """Return the content-light hash identity for one frozen frame."""
    if case.source_sha256 != _sha256(case.source_bytes):
        raise ValueError("source_hash_mismatch")
    if tuple(item.name for item in transforms) != TRANSFORM_ORDER:
        raise ValueError("transform_set_invalid")
    if any(item.sha256 != _sha256(item.png_bytes) for item in transforms):
        raise ValueError("transform_hash_mismatch")
    return {
        "source_sha256": case.source_sha256,
        "label_sha256": case.label_sha256,
        "transform_sha256": {item.name: item.sha256 for item in transforms},
    }


def _coverage(
    *, correct: int, abstained: int, denominator: int
) -> Coverage:
    return Coverage(
        correct_text_numerator=correct,
        correct_text_denominator=denominator,
        correct_text_coverage=correct / denominator if denominator else 0.0,
        abstention_numerator=abstained,
        abstention_denominator=denominator,
        abstention_coverage=abstained / denominator if denominator else 0.0,
    )


def _applicable_aliases(
    case: FrameCase, transform_name: str
) -> tuple[tuple[HumanLabel, ...], dict[str, str]]:
    if transform_name not in TRANSFORM_ORDER:
        raise ScoringRefusal("invalid_transform")
    labels = tuple(
        label for label in case.labels if transform_name in label.visible_in
    )
    if not labels:
        raise ScoringRefusal("labels_empty_for_transform")
    aliases = {
        alias.casefold(): label.region_id
        for label in labels
        for alias in label.aliases
    }
    return labels, aliases


def score_transform(
    case: FrameCase, transform_name: str, verdict: Verdict
) -> TransformScore:
    """Score one schema-valid verdict against owner-authored labels only."""
    labels, aliases = _applicable_aliases(case, transform_name)
    if verdict.verdict == "rejected":
        raise ScoringRefusal("candidate_verdict_rejected")

    fields_by_region: dict[str, list[Field]] = {}
    if verdict.verdict == "ok":
        for field in verdict.fields:
            region_id = aliases.get(field.region.casefold())
            if region_id is None:
                raise ScoringRefusal("unknown_region")
            fields_by_region.setdefault(region_id, []).append(field)

    correct = 0
    abstained = 0
    for label in labels:
        fields = fields_by_region.get(label.region_id, [])
        if any(
            field.provenance == "transcribed" and field.text == label.text
            for field in fields
        ):
            correct += 1
        elif verdict.verdict == "empty" or any(
            field.provenance in {"partial", "abstained"} for field in fields
        ):
            abstained += 1

    full_value_hashes = tuple(
        (
            region_id,
            tuple(
                sorted(
                    {
                        _sha256(field.text.encode("utf-8"))
                        for field in fields
                        if field.provenance == "transcribed"
                    }
                )
            ),
        )
        for region_id, fields in sorted(fields_by_region.items())
        if any(field.provenance == "transcribed" for field in fields)
    )
    return TransformScore(
        transform_name=transform_name,
        coverage=_coverage(
            correct=correct,
            abstained=abstained,
            denominator=len(labels),
        ),
        full_value_hashes=full_value_hashes,
    )


def aggregate_coverage(scores: Sequence[TransformScore]) -> Coverage:
    """Aggregate independent coverage counters without blending the metrics."""
    correct = sum(score.coverage.correct_text_numerator for score in scores)
    abstained = sum(score.coverage.abstention_numerator for score in scores)
    correct_denominator = sum(
        score.coverage.correct_text_denominator for score in scores
    )
    abstention_denominator = sum(
        score.coverage.abstention_denominator for score in scores
    )
    if correct_denominator != abstention_denominator:
        raise ValueError("coverage_denominator_mismatch")
    return _coverage(
        correct=correct,
        abstained=abstained,
        denominator=correct_denominator,
    )


def check_evidence_monotonicity(
    case: FrameCase, verdicts: Mapping[str, Verdict]
) -> tuple[EvidenceFinding, ...]:
    """Find contradiction or evidence loss across increasingly rich transforms."""
    supplied_names = set(verdicts)
    required_names = set(TRANSFORM_ORDER)
    if supplied_names != required_names:
        if supplied_names < required_names:
            raise ScoringRefusal("transform_set_incomplete")
        raise ScoringRefusal("invalid_transform")
    ordered_names = TRANSFORM_ORDER
    scores = {
        name: score_transform(case, name, verdicts[name]) for name in ordered_names
    }
    partials: dict[str, dict[str, tuple[str, ...]]] = {}
    full_texts: dict[str, dict[str, tuple[str, ...]]] = {}
    for name in ordered_names:
        _, aliases = _applicable_aliases(case, name)
        partial_by_region: dict[str, list[str]] = {}
        full_by_region: dict[str, list[str]] = {}
        for field in verdicts[name].fields:
            region_id = aliases[field.region.casefold()]
            if field.provenance == "partial":
                partial_by_region.setdefault(region_id, []).append(field.text)
            elif field.provenance == "transcribed":
                full_by_region.setdefault(region_id, []).append(field.text)
        partials[name] = {
            region_id: tuple(values)
            for region_id, values in partial_by_region.items()
        }
        full_texts[name] = {
            region_id: tuple(values) for region_id, values in full_by_region.items()
        }
    findings: list[EvidenceFinding] = []
    seen: set[tuple[str, str]] = set()
    for lower_index, lower_name in enumerate(ordered_names):
        lower_values = dict(scores[lower_name].full_value_hashes)
        lower_regions = {
            label.region_id
            for label in case.labels
            if lower_name in label.visible_in
        }
        for higher_name in ordered_names[lower_index + 1 :]:
            higher_values = dict(scores[higher_name].full_value_hashes)
            higher_regions = {
                label.region_id
                for label in case.labels
                if higher_name in label.visible_in
            }
            for region_id in sorted(lower_regions & higher_regions):
                lower = set(lower_values.get(region_id, ()))
                higher = set(higher_values.get(region_id, ()))
                lost = lower - higher
                added = higher - lower
                allowed_higher = {
                    _sha256(label.text.encode("utf-8"))
                    for label in case.labels
                    if label.region_id == region_id
                    and higher_name in label.visible_in
                }
                unsupported_added = added - allowed_higher
                unsupported_conflict = bool(lower and unsupported_added)
                if lost or unsupported_conflict:
                    reason: EvidenceReason = (
                        "evidence_contradiction"
                        if added or unsupported_added
                        else "evidence_regression"
                    )
                    key = (reason, region_id)
                    if key not in seen:
                        seen.add(key)
                        findings.append(
                            EvidenceFinding(
                                reason=reason,
                                region_character_count=len(region_id),
                                region_sha256=_sha256(region_id.encode("utf-8")),
                                lower_transform=lower_name,
                                higher_transform=higher_name,
                            )
                        )

                lower_partials = partials[lower_name].get(region_id, ())
                if not lower_partials:
                    continue
                owner_completions = tuple(
                    label.text
                    for label in case.labels
                    if label.region_id == region_id
                    and lower_name in label.visible_in
                    and higher_name in label.visible_in
                )
                higher_assertions = (
                    full_texts[higher_name].get(region_id, ())
                    + partials[higher_name].get(region_id, ())
                )
                partial_reason: EvidenceReason | None = None
                if not higher_assertions:
                    partial_reason = "evidence_regression"
                elif any(
                    not any(
                        _partial_assertions_compatible(
                            lower_partial,
                            higher,
                            owner_completions,
                        )
                        for higher in higher_assertions
                    )
                    for lower_partial in lower_partials
                ):
                    partial_reason = "evidence_contradiction"
                if partial_reason is None:
                    continue
                partial_key = (partial_reason, region_id)
                if partial_key in seen:
                    continue
                seen.add(partial_key)
                findings.append(
                    EvidenceFinding(
                        reason=partial_reason,
                        region_character_count=len(region_id),
                        region_sha256=_sha256(region_id.encode("utf-8")),
                        lower_transform=lower_name,
                        higher_transform=higher_name,
                    )
                )
    return tuple(findings)


def _partial_matches(partial: str, asserted: str) -> bool:
    marker = "[UNREADABLE]"
    pieces = [piece.strip() for piece in partial.split(marker)]
    pattern = ".*".join(re.escape(piece) for piece in pieces)
    if not partial.lstrip().startswith(marker):
        pattern = "^" + pattern
    if not partial.rstrip().endswith(marker):
        pattern += "$"
    return re.search(pattern, asserted, flags=re.DOTALL) is not None


def _partial_assertions_compatible(
    lower_partial: str,
    higher: str,
    owner_completions: Sequence[str],
) -> bool:
    if "[UNREADABLE]" not in higher:
        return _partial_matches(lower_partial, higher)
    if any(
        _partial_matches(lower_partial, completion)
        and _partial_matches(higher, completion)
        for completion in owner_completions
    ):
        return True
    lower_known = "".join(
        piece.strip() for piece in lower_partial.split("[UNREADABLE]")
    )
    higher_known = "".join(piece.strip() for piece in higher.split("[UNREADABLE]"))
    return _partial_matches(lower_partial, higher_known) or _partial_matches(
        higher, lower_known
    )


def find_invented_specificity(
    case: FrameCase, transform_name: str, verdict: Verdict
) -> tuple[InventedSpecificity, ...]:
    """Find every high-specificity candidate string absent from owner truth."""
    _applicable_aliases(case, transform_name)
    if verdict.verdict != "ok":
        return ()
    return find_invented_specificity_in_text(
        case,
        transform_name,
        *(field.text for field in verdict.fields),
    )


def find_invented_specificity_in_text(
    case: FrameCase, transform_name: str, *texts: str
) -> tuple[InventedSpecificity, ...]:
    """Audit untrusted text with the shared detector, without reparsing it."""
    labels, _ = _applicable_aliases(case, transform_name)
    human_claims = {
        (claim.kind, claim.value)
        for label in labels
        for claim in find_specificity_claims(label.text)
    }

    findings: list[InventedSpecificity] = []
    seen: set[tuple[SpecificityKind, str]] = set()
    for text in texts:
        for claim in find_specificity_claims(text):
            key = (claim.kind, claim.value)
            if key in seen or key in human_claims:
                continue
            seen.add(key)
            encoded = claim.value.encode("utf-8")
            findings.append(
                InventedSpecificity(
                    kind=claim.kind,
                    value=claim.value,
                    character_count=len(claim.value),
                    string_sha256=_sha256(encoded),
                    transform_name=transform_name,
                )
            )
    return tuple(findings)
