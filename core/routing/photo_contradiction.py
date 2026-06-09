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
