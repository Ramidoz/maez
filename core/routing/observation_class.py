"""Request-class for routing observations (Slice 1b). Prefers Layer0's semantic
archetype class WHEN Task 0 confirmed it cheap (it did NOT for Slice 1); otherwise a
stable exact-utterance hash (exact-repeat priors). Returns (class_id, score, version).
NEVER raises into the caller."""
from __future__ import annotations
import hashlib

_HASH_VERSION = "utterance_hash_v0"
_LAYER0_ENABLED = False  # Task 0: MiniLM encode too heavy at the live seam; hash-only for Slice 1.

def _utterance_hash_class(text: str) -> tuple[str, float, str]:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16], 1.0, _HASH_VERSION

def _layer0_class(text: str) -> tuple[str, float, str]:
    # Wired per Task 0 (exact entry/attrs confirmed there). Kept patchable for tests.
    from core.dispatcher.layer0 import Layer0Dispatcher
    spec = Layer0Dispatcher().emit_spec(text)
    cls = getattr(spec, "archetype_class", None) or getattr(spec, "class_id", None)
    return str(cls), float(getattr(spec, "archetype_score", 0.0) or 0.0), "archetypes-v0"

def classify_request_class(text: str) -> tuple[str, float, str]:
    if _LAYER0_ENABLED:
        try:
            cid, score, ver = _layer0_class(text)
            if cid:
                return cid, score, ver
        except Exception:
            pass
    return _utterance_hash_class(text)
