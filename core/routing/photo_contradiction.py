"""Local photo-contradiction sense helpers.

This module is intentionally light at import time. Heavy model libraries are
imported only inside the enabled verifier load path.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


_CITE_RE = re.compile(r"\[E\d+\]")
_SENTENCE_RE = re.compile(r".+?(?:[.!?](?=\s|$)|$)", re.DOTALL)
_SPACE_RE = re.compile(r"\s+")
_PHOTO_VERBS_RE = re.compile(
    r"\b("
    r"(?:image|photo|picture|screenshot|chart|table|text|title|page|screen)"
    r"\s+(?:shows|says|contains|depicts|lists|names|displays|reads|includes)"
    r"|(?:shows|says|contains|depicts|lists|names|displays|reads|includes)"
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


@dataclass(frozen=True)
class PhotoClaim:
    claim_id: str
    text: str
    direct_perceptual: bool
    evidence_label: str = "E1"


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
