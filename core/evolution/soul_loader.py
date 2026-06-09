# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
soul_loader.py — SOUL layering for distribution-readiness.

Maez's SOUL is split into two layers:

    soul.base.md   — universal, shippable template. Every Maez starts with
                     this: HARD CONSTRAINTS, TRUST COVENANT, SYSTEM BASELINE,
                     Voice, Presence, Self-Reflection scaffold, etc.

    soul.local.md  — this Maez's personal accumulations. Self-analysis
                     insights, applied dream proposals, per-user memory
                     seeds. Stays on this machine, never shipped.

At runtime the two files concatenate into the live SOUL text. The combined
result is also written to `soul.md` on disk so code that hasn't been
retrofitted yet keeps working unchanged.

When Maez applies a new dream proposal, it appends to `soul.local.md`.
Base stays stable across versions.
"""
from __future__ import annotations

import logging
import threading
import re
from typing import Optional

from core import paths

logger = logging.getLogger("maez.soul")

_cache_text: Optional[str] = None
_cache_signature: Optional[tuple[float, float]] = None
_lock = threading.Lock()


def _read(path) -> str:
    try:
        return path.read_text()
    except FileNotFoundError:
        return ""
    except Exception as e:
        logger.warning("failed to read %s: %s", path, e)
        return ""


def _mtime(path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def current_soul() -> str:
    """Return the full SOUL text (base + local concatenated).

    Cached until either file's mtime changes. Thread-safe.
    """
    global _cache_text, _cache_signature
    base_path = paths.soul_base_path()
    local_path = paths.soul_local_path()
    legacy_path = paths.soul_combined_path()

    signature = (_mtime(base_path), _mtime(local_path))

    with _lock:
        if _cache_text is not None and _cache_signature == signature:
            return _cache_text

        base_text = _read(base_path)
        local_text = _read(local_path)

        if not base_text and not local_text:
            # Neither layered file exists — fall back to legacy soul.md
            # for machines that haven't been migrated to the split yet.
            legacy_text = _read(legacy_path)
            if legacy_text:
                logger.debug("SOUL loaded from legacy %s", legacy_path)
                _cache_text = legacy_text
                _cache_signature = (_mtime(legacy_path), 0.0)
                return legacy_text
            logger.warning("no SOUL files found; returning empty SOUL")
            _cache_text = ""
            _cache_signature = (0.0, 0.0)
            return ""

        # Preserve byte-identical concatenation with the original soul.md.
        # The split point was chosen on a blank line, so direct concatenation
        # reconstructs the original file exactly.
        combined = base_text + local_text

        _cache_text = combined
        _cache_signature = signature

        # Keep legacy soul.md on disk as the concatenated result so
        # code reading the path directly stays unbroken. Only rewrite
        # if content changed, to avoid unnecessary mtime churn.
        try:
            if legacy_path.exists():
                existing = legacy_path.read_text()
                if existing != combined:
                    legacy_path.write_text(combined)
            else:
                legacy_path.write_text(combined)
        except Exception as e:
            logger.warning("could not mirror combined SOUL to %s: %s", legacy_path, e)

        return combined


def append_to_local(text: str, *, separator: str = "\n\n") -> None:
    """Append new content to soul.local.md. Used by dream-proposal apply.

    07-B1: read + write must both happen inside the lock. Previously the
    read was outside, so two concurrent dream-apply paths could both
    read the same `existing`, then clobber each other's writes — losing
    one proposal silently. Cache invalidation is kept in the same
    critical section so the next current_soul() re-reads the merged
    file, not whichever thread's copy ran last.
    """
    if not text:
        return
    local_path = paths.soul_local_path()
    with _lock:
        try:
            existing = local_path.read_text() if local_path.exists() else ""
        except Exception:
            existing = ""
        suffix = separator if existing and not existing.endswith(separator) else ""
        local_path.write_text(existing + suffix + text)
        global _cache_text, _cache_signature
        _cache_text = None
        _cache_signature = None


_NOTE_TS_RE = re.compile(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\] (.*)$", re.DOTALL)


def _note_bodies(existing: str) -> set:
    """Exact bodies of previously-appended notes (timestamp prefix stripped),
    compared as whole units. Substring matching would false-skip a distinct
    shorter note contained inside an older one.
    """
    bodies = set()
    for chunk in existing.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = _NOTE_TS_RE.match(chunk)
        if m:
            bodies.add(m.group(1).strip())
    return bodies


def append_soul_note(note: str, *, separator: str = "\n\n") -> str:
    """Append a self-authored soul note to the LOCAL layer (soul.local.md),
    deduped by EXACT note-body match (not substring) so a distinct shorter
    note inside an older one is never silently skipped. Read, dedupe-check,
    and write are atomic under _lock so concurrent identical notes cannot
    double-append. Replaces the legacy direct-append to the soul.md mirror.
    """
    if not note or not note.strip():
        return "empty soul note; skipped"
    body = note.strip()
    local_path = paths.soul_local_path()
    from datetime import datetime as _dt
    entry = f"[{_dt.now().strftime('%Y-%m-%d %H:%M')}] {body}"
    global _cache_text, _cache_signature
    with _lock:
        try:
            existing = local_path.read_text() if local_path.exists() else ""
        except Exception:
            existing = ""
        if body in _note_bodies(existing):
            return f"soul note already present; skipped ({len(body)} chars)"
        suffix = separator if existing and not existing.endswith(separator) else ""
        local_path.write_text(existing + suffix + entry)
        _cache_text = None
        _cache_signature = None
    return f"soul note appended to local ({len(body)} chars)"


def reload() -> None:
    """Force the next current_soul() call to re-read from disk."""
    global _cache_text, _cache_signature
    with _lock:
        _cache_text = None
        _cache_signature = None


if __name__ == "__main__":
    import sys
    text = current_soul()
    print(f"SOUL length: {len(text)} chars, {len(text.splitlines())} lines")
    print(f"base: {paths.soul_base_path()}")
    print(f"local: {paths.soul_local_path()}")
    if "--print" in sys.argv:
        print("---")
        print(text)
