"""Absence-claim shadow detector for evidence precedence.

This observes the marked audited draft before natural rendering strips
``[E#]``. v0 never gates or rewrites; it only writes content-light rows.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path

from core.cognition.capability_card import evidence_precedence_enabled
from core.infra.env_flags import strict_env_flag

logger = logging.getLogger("maez")

_ABSENCE_RE = re.compile(
    r"truncated|missing|cut off|not (?:in|present in|part of)|"
    r"doesn'?t contain|lacks|absent from",
    re.IGNORECASE,
)
_MARKER_RE = re.compile(r"\[E(\d+)\]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_ROTATE_BYTES = 2_000_000
_ROTATE_KEEP = 2


def _default_ledger() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "maez" / "evidence_precedence_shadow.jsonl"


def _debug() -> bool:
    return strict_env_flag("MAEZ_EVIDENCE_PRECEDENCE_DEBUG")


def _rotate(path: Path) -> None:
    try:
        if not path.exists() or path.stat().st_size < _ROTATE_BYTES:
            return
        for idx in range(_ROTATE_KEEP, 0, -1):
            src = path.with_name(path.name + f".{idx}")
            if idx == _ROTATE_KEEP:
                if src.exists():
                    src.unlink()
                continue
            if src.exists():
                src.rename(path.with_name(path.name + f".{idx + 1}"))
        path.rename(path.with_name(path.name + ".1"))
    except Exception:
        pass


def observe_marked_draft(
    marked_draft,
    *,
    surface: str,
    fresh_indices,
    web_present: bool,
    ledger_path: Path | None = None,
) -> int:
    """Write shadow rows for absence-claims about fresh evidence. Never raises."""
    try:
        if not evidence_precedence_enabled():
            return 0
        if not isinstance(marked_draft, str) or not marked_draft:
            return 0
        if fresh_indices is not None:
            mode = "proof"
            fresh = {int(i) for i in fresh_indices}
        else:
            if not web_present:
                return 0
            mode = "fallback_all_cited"
            fresh = None

        path = ledger_path or _default_ledger()
        written = 0
        for sentence in _SENTENCE_SPLIT_RE.split(marked_draft):
            sentence = sentence.strip()
            if not sentence:
                continue
            verb = _ABSENCE_RE.search(sentence)
            if not verb:
                continue
            cited = [int(m) for m in _MARKER_RE.findall(sentence)]
            hits = [i for i in cited if fresh is None or i in fresh]
            if not hits:
                continue
            row = {
                "ts": int(time.time()),
                "surface": surface,
                "sentence_hash": hashlib.sha256(sentence.encode("utf-8")).hexdigest()[
                    :16
                ],
                "absence_verb": verb.group(0).lower(),
                "marker_indices": cited,
                "flagged_indices": hits,
                "fresh_index_mode": mode,
                "fresh_index_set": sorted(fresh) if fresh is not None else None,
            }
            if _debug():
                row["sentence_excerpt"] = sentence[:200]
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                _rotate(path)
                with path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, sort_keys=True) + "\n")
                written += 1
            except Exception:
                pass
        return written
    except Exception:
        logger.debug("evidence precedence shadow failed", exc_info=True)
        return 0
