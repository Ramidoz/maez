"""Local photo-contradiction sense helpers.

This module is intentionally light at import time. Heavy model libraries are
imported only inside the enabled verifier load path.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import time
from pathlib import Path
from typing import Protocol


_CITE_RE = re.compile(r"\[E\d+\]")
_SENTENCE_RE = re.compile(r".+?(?:[.!?](?=\s|$)|$)", re.DOTALL)
_SPACE_RE = re.compile(r"\s+")
_PHOTO_VERBS_RE = re.compile(
    r"\b("
    r"(?:image|photo|picture|screenshot|chart|table|text|title|page|screen)"
    r"\s+(?:shows|says|contains|depicts|lists|names|displays|reads|includes)"
    r")\b",
    re.IGNORECASE,
)
_NON_PERCEPTUAL_RE = re.compile(
    r"\b("
    r"matters|roadmap|promising|should|could|would|may want|recommend|"
    r"probably|seems|appears important|means for|suggests we|test later"
    r")\b",
    re.IGNORECASE,
)

NLI_MODEL_ID = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
DEFAULT_NLI_ARTIFACT_DIR = (
    Path(__file__).resolve().parents[2] / "models" / "bakeoff" / "nli"
)


@dataclass(frozen=True)
class PhotoClaim:
    claim_id: str
    text: str
    direct_perceptual: bool
    evidence_label: str = "E1"


@dataclass(frozen=True)
class ClaimVerdict:
    label: str
    score: float | None
    latency_s: float
    model_id: str | None = None
    revision: str | None = None
    sha256: str | None = None
    reason: str | None = None


class ContradictionVerifier(Protocol):
    def predict(self, premise: str, hypothesis: str) -> ClaimVerdict:
        ...


@dataclass(frozen=True)
class ReceiptClaimDetail:
    claim_id: str
    text: str
    evidence_label: str
    verdict_label: str
    score: float | None = None
    model_id: str | None = None
    revision: str | None = None
    sha256: str | None = None
    verifier_reason: str | None = None
    latency_s: float = 0.0


@dataclass(frozen=True)
class ContradictionReceipt:
    state: str
    reason: str
    claim_count: int = 0
    contradiction_count: int = 0
    contradiction_claim_count: int = 0
    claim_limit_exceeded: bool = False
    contradicted_claim_ids: tuple[str, ...] = ()
    sense_note: str | None = None
    verifier_name: str | None = None
    model_id: str | None = None
    revision: str | None = None
    sha256: str | None = None
    latency_ms: int = 0
    claim_details: tuple[ReceiptClaimDetail, ...] = ()


def normalize_claim_text(text: str) -> str:
    text = _CITE_RE.sub("", text or "")
    text = _SPACE_RE.sub(" ", text).strip()
    text = re.sub(r"\s+([.!?]+)", r"\1", text)
    return text


def _clean_sentence(text: str) -> str:
    cleaned = normalize_claim_text(text)
    return cleaned.strip(" \t\r\n")


def _is_direct_perceptual(sentence: str) -> bool:
    if not sentence:
        return False
    if _NON_PERCEPTUAL_RE.search(sentence):
        return False
    return bool(_PHOTO_VERBS_RE.search(sentence))


def extract_photo_claims(
    reply: str,
    *,
    evidence_label: str = "E1",
    limit: int = 5,
) -> list[PhotoClaim]:
    if limit <= 0:
        return []

    claims: list[PhotoClaim] = []
    normalized_reply = normalize_claim_text(reply)
    for match in _SENTENCE_RE.finditer(reply or ""):
        sentence = _clean_sentence(match.group(0))
        if not sentence:
            continue
        if normalize_claim_text(sentence) not in normalized_reply:
            continue
        if not _is_direct_perceptual(sentence):
            continue
        claims.append(
            PhotoClaim(
                claim_id=f"C{len(claims) + 1}",
                text=sentence,
                direct_perceptual=True,
                evidence_label=evidence_label,
            )
        )
        if len(claims) >= limit:
            break
    return claims


def photo_contradiction_sense_enabled(env=os.environ) -> bool:
    value = (env.get("MAEZ_PHOTO_CONTRADICTION_SENSE", "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _looks_multi_photo(premise: str) -> bool:
    markers = re.findall(
        r"\b(?:image|photo|picture)\s+\d+\s*:",
        premise or "",
        re.IGNORECASE,
    )
    return len(markers) > 1


def _count_potential_claims(reply: str) -> int:
    return len(extract_photo_claims(reply, limit=10_000))


def _clip_note_text(text: str, *, limit: int = 500) -> str:
    clipped = normalize_claim_text(text)
    if len(clipped) <= limit:
        return clipped
    return clipped[: limit - 3].rstrip() + "..."


def _build_sense_note(
    premise: str,
    contradictions: list[tuple[PhotoClaim, ClaimVerdict]],
) -> str:
    lines = ["Contradiction sense fired:"]
    for claim, _verdict in contradictions:
        lines.append(f'- Claim {claim.claim_id}: "{_clip_note_text(claim.text)}"')
    lines.append(f"- Conflicts with E1: {_clip_note_text(premise)}")
    lines.append(
        "Revise the answer with this signal in view. Do not claim certainty "
        "where the photo evidence and draft conflict."
    )
    return "\n".join(lines)


def _detail_for(claim: PhotoClaim, verdict: ClaimVerdict) -> ReceiptClaimDetail:
    return ReceiptClaimDetail(
        claim_id=claim.claim_id,
        text=claim.text,
        evidence_label=claim.evidence_label,
        verdict_label=verdict.label,
        score=verdict.score,
        model_id=verdict.model_id,
        revision=verdict.revision,
        sha256=verdict.sha256,
        verifier_reason=verdict.reason,
        latency_s=verdict.latency_s,
    )


def _verdict_metadata(
    details: tuple[ReceiptClaimDetail, ...],
) -> tuple[str | None, str | None, str | None]:
    for detail in details:
        if detail.model_id or detail.revision or detail.sha256:
            return detail.model_id, detail.revision, detail.sha256
    return None, None, None


def check_photo_contradictions(
    *,
    premise: str,
    reply: str,
    verifier: ContradictionVerifier,
    claim_limit: int = 5,
    lane1_receipt_reason: str | None = None,
) -> ContradictionReceipt:
    t0 = time.perf_counter()
    if lane1_receipt_reason == "deterministic_fallback":
        return ContradictionReceipt(
            state="grounded",
            reason="deterministic_fallback",
        )

    if _looks_multi_photo(premise):
        return ContradictionReceipt(
            state="unavailable",
            reason="multi_photo_unsupported",
        )

    total_possible = _count_potential_claims(reply)
    claims = extract_photo_claims(reply, limit=claim_limit)
    claim_limit_exceeded = total_possible > len(claims)
    if not claims:
        return ContradictionReceipt(
            state="unavailable",
            reason="claim_extraction_unavailable",
            claim_limit_exceeded=claim_limit_exceeded,
        )

    contradictions: list[tuple[PhotoClaim, ClaimVerdict]] = []
    details: list[ReceiptClaimDetail] = []
    saw_unavailable = False
    for claim in claims:
        claim_t0 = time.perf_counter()
        try:
            verdict = verifier.predict(premise, claim.text)
        except Exception as exc:
            verdict = ClaimVerdict(
                label="unavailable",
                score=None,
                latency_s=time.perf_counter() - claim_t0,
                reason=f"predict: {type(exc).__name__}: {exc}",
            )
        if verdict.label == "contradicts":
            contradictions.append((claim, verdict))
        elif verdict.label != "grounded":
            saw_unavailable = True
        details.append(_detail_for(claim, verdict))

    latency_ms = int((time.perf_counter() - t0) * 1000)
    claim_details = tuple(details)
    model_id, revision, sha256 = _verdict_metadata(claim_details)
    verifier_name = type(verifier).__name__

    if contradictions:
        contradiction_count = len(contradictions)
        return ContradictionReceipt(
            state="trust_demoted",
            reason="trust_demoted",
            claim_count=len(claims),
            contradiction_count=contradiction_count,
            contradiction_claim_count=contradiction_count,
            claim_limit_exceeded=claim_limit_exceeded,
            contradicted_claim_ids=tuple(c.claim_id for c, _v in contradictions),
            sense_note=_build_sense_note(premise, contradictions),
            verifier_name=verifier_name,
            model_id=model_id,
            revision=revision,
            sha256=sha256,
            latency_ms=latency_ms,
            claim_details=claim_details,
        )

    if saw_unavailable:
        return ContradictionReceipt(
            state="unavailable",
            reason="verifier_unavailable",
            claim_count=len(claims),
            claim_limit_exceeded=claim_limit_exceeded,
            verifier_name=verifier_name,
            model_id=model_id,
            revision=revision,
            sha256=sha256,
            latency_ms=latency_ms,
            claim_details=claim_details,
        )

    return ContradictionReceipt(
        state="grounded",
        reason="clear",
        claim_count=len(claims),
        claim_limit_exceeded=claim_limit_exceeded,
        verifier_name=verifier_name,
        model_id=model_id,
        revision=revision,
        sha256=sha256,
        latency_ms=latency_ms,
        claim_details=claim_details,
    )


def _flatten_pipeline_output(output):
    if output and isinstance(output[0], list):
        return output[0]
    return output


def nli_grounded_score_from_output(output) -> float:
    rows = _flatten_pipeline_output(output)
    probs = {
        str(row["label"]).lower(): float(row["score"])
        for row in rows
        if "label" in row and "score" in row
    }
    contradiction = None
    for label in ("contradiction", "contradictory"):
        if label in probs:
            contradiction = probs[label]
            break
    if contradiction is None:
        raise ValueError(f"NLI output lacks contradiction label: {sorted(probs)}")
    return 1.0 - float(contradiction)


def _read_manifest(artifact_dir: Path) -> dict | None:
    try:
        with (artifact_dir / "bakeoff_manifest.json").open(encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _load_transformers_pipeline(artifact_dir: Path):
    from transformers import pipeline

    return pipeline(
        "text-classification",
        model=str(artifact_dir),
        tokenizer=str(artifact_dir),
        top_k=None,
        local_files_only=True,
    )


class LocalNLIContradictionVerifier:
    def __init__(
        self,
        *,
        artifact_dir: str | os.PathLike[str] | None = None,
        threshold: float = 0.5,
    ) -> None:
        self.artifact_dir = Path(artifact_dir) if artifact_dir else DEFAULT_NLI_ARTIFACT_DIR
        self.threshold = threshold
        self._model = None
        self._load_failed_reason: str | None = None
        self.model_id = NLI_MODEL_ID
        self.revision: str | None = None
        self.sha256: str | None = None

    def _unavailable(self, reason: str, latency_s: float = 0.0) -> ClaimVerdict:
        return ClaimVerdict(
            label="unavailable",
            score=None,
            latency_s=latency_s,
            model_id=self.model_id,
            revision=self.revision,
            sha256=self.sha256,
            reason=reason,
        )

    def _ensure_loaded(self) -> str | None:
        if self._model is not None:
            return None
        if self._load_failed_reason:
            return self._load_failed_reason
        if not self.artifact_dir.is_dir():
            self._load_failed_reason = f"missing artifact: {self.artifact_dir}"
            return self._load_failed_reason

        manifest = _read_manifest(self.artifact_dir)
        if not manifest:
            self._load_failed_reason = (
                f"missing manifest: {self.artifact_dir / 'bakeoff_manifest.json'}"
            )
            return self._load_failed_reason

        manifest_repo = manifest.get("repo_id")
        if manifest_repo != self.model_id:
            self._load_failed_reason = (
                f"manifest repo_id {manifest_repo!r} != expected {self.model_id!r}"
            )
            return self._load_failed_reason
        self.revision = manifest.get("revision")
        self.sha256 = manifest.get("sha256")

        try:
            self._model = _load_transformers_pipeline(self.artifact_dir)
        except Exception as exc:
            self._load_failed_reason = f"load: {type(exc).__name__}: {exc}"
            return self._load_failed_reason
        return None

    def predict(self, premise: str, hypothesis: str) -> ClaimVerdict:
        t0 = time.perf_counter()
        unavailable = self._ensure_loaded()
        if unavailable:
            return self._unavailable(unavailable, time.perf_counter() - t0)

        try:
            output = self._model({"text": premise, "text_pair": hypothesis})
            grounded_score = nli_grounded_score_from_output(output)
            label = "grounded" if grounded_score >= self.threshold else "contradicts"
            return ClaimVerdict(
                label=label,
                score=grounded_score,
                latency_s=time.perf_counter() - t0,
                model_id=self.model_id,
                revision=self.revision,
                sha256=self.sha256,
            )
        except Exception as exc:
            return self._unavailable(
                f"predict: {type(exc).__name__}: {exc}",
                time.perf_counter() - t0,
            )
