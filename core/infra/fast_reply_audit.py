"""
core/fast_reply_audit.py — Session 11g + 11h, staging-only.

Append-only forensic audit log for the staging fast-lane HTTP boundary.

Hard contract:
  • Writes to memory/fast_reply_audit.jsonl, ONE JSON OBJECT PER LINE.
  • This file is deliberately separate from any daemon-owned memory file
    (memory/db/, memory/*.db, etc.) so the live daemon never touches it
    and a corrupted audit log cannot affect the live observation window.
  • METADATA ONLY. The contract is: never log raw prompt content, never
    log raw reply content, never log raw secrets. The caller is
    responsible for stripping such fields BEFORE calling audit_append().
    This module enforces a defensive ban list as a second line of
    defense — any record that contains a forbidden key (e.g. 'prompt',
    'reply_text', 'message', 'raw') is rejected before write.
  • Append uses fcntl.flock() to prevent interleaved writes when multiple
    server worker threads call audit_append() concurrently.
  • Never raises out of audit_append — failure is logged but never crashes
    the request hot path. (The caller wraps this in _audit_append_safe.)

Session 11h additions:
  • Lazy size-based rotation. When the active audit file exceeds
    MAX_AUDIT_BYTES (10 MB by default), it is rotated to .1, the prior
    .1 to .2, etc., up to MAX_ROTATIONS (5). The oldest file is dropped.
  • Rotation runs INSIDE audit_append while the cross-process flock is
    held, so concurrent appends from multiple worker threads can never
    race against the rename() / unlink() steps.
  • No background thread, no scheduler, no daemon. Lazy on append.
  • The threshold can be lowered for testing via the env var
    MAEZ_AUDIT_MAX_BYTES (positive integer). The default 10 MB constant
    is the production-ish value and is what should ship.

Public surface:
    AUDIT_PATH                  -> Path
    BANNED_RECORD_KEYS          -> frozenset
    audit_append(record)        -> bool
    audit_tail(n=10)            -> list[dict]   (debug only)
    audit_rotate_if_needed()    -> int          (manual trigger; usually
                                                 you don't call this)
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger('fast_reply_audit')


# Audit file lives next to the conversation log under memory/, but with
# a clearly different name so it can never collide with daemon-owned
# memory files.
try:
    from core.paths import memory_dir as _memory_dir
    AUDIT_PATH = _memory_dir() / 'fast_reply_audit.jsonl'
except Exception:
    AUDIT_PATH = Path('/home/rohit/maez/memory/fast_reply_audit.jsonl')

# Defense-in-depth: keys that must NEVER appear in an audit record. The
# caller is supposed to strip these — this is a backstop. If any of these
# show up, we reject the entire record (not strip silently — failing
# loud is correct here).
BANNED_RECORD_KEYS = frozenset({
    'prompt',
    'prompt_text',
    'message',           # the raw user message
    'reply',
    'reply_text',
    'raw',
    'raw_body',
    'response',
    'response_body',
    'value',             # generic — would catch e.g. cache values
    'screen',
    'system_state',
    'calendar',
    'observation',
    'envelope',
})

# Maximum size of any individual record on disk. Records that serialize
# beyond this are rejected — the audit log should be small forever.
MAX_RECORD_BYTES = 4 * 1024

# ── Session 11h: rotation policy ──
MAX_AUDIT_BYTES_DEFAULT = 10 * 1024 * 1024     # 10 MB
MAX_ROTATIONS           = 5                    # keep .1 .. .5


def _max_audit_bytes() -> int:
    """Effective rotation threshold. Honors MAEZ_AUDIT_MAX_BYTES env override
    when set to a positive integer. Used by tests to lower the threshold
    without monkey-patching constants."""
    raw = os.environ.get('MAEZ_AUDIT_MAX_BYTES')
    if raw:
        try:
            v = int(raw)
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass
    return MAX_AUDIT_BYTES_DEFAULT


_LOCK = threading.RLock()


def _validate_record(record: Any) -> tuple[bool, str]:
    if not isinstance(record, dict):
        return False, f'record must be a dict, got {type(record).__name__}'
    if not record:
        return False, 'record is empty'
    banned = BANNED_RECORD_KEYS & set(record.keys())
    if banned:
        return False, f'record contains forbidden keys: {sorted(banned)}'
    return True, ''


def _rotated_path(n: int) -> Path:
    """Return the rotation path for slot n (1..MAX_ROTATIONS).
    e.g. AUDIT_PATH=fast_reply_audit.jsonl  →  fast_reply_audit.jsonl.1"""
    return AUDIT_PATH.with_name(AUDIT_PATH.name + f'.{n}')


def _rotate_locked() -> int:
    """Rotate the active audit file: .5 dropped, .4→.5, ..., .1→.2,
    current→.1. Returns the number of slots that were moved.

    MUST be called while holding both the in-process _LOCK AND the
    cross-process flock on the active file. The caller in audit_append
    holds both. We do NOT acquire either here.

    Never raises. On any individual rename failure, logs and continues."""
    if not AUDIT_PATH.exists():
        return 0

    moved = 0

    # Step 1: drop the oldest slot, then shift each older slot up by 1
    oldest = _rotated_path(MAX_ROTATIONS)
    if oldest.exists():
        try:
            oldest.unlink()
        except Exception as e:                              # pragma: no cover
            logger.warning('audit_rotate: failed to drop oldest %s: %s', oldest, e)

    for n in range(MAX_ROTATIONS - 1, 0, -1):
        src = _rotated_path(n)
        dst = _rotated_path(n + 1)
        if src.exists():
            try:
                src.rename(dst)
                moved += 1
            except Exception as e:                          # pragma: no cover
                logger.warning('audit_rotate: failed to move %s → %s: %s', src, dst, e)

    # Step 2: move the current file to .1
    try:
        AUDIT_PATH.rename(_rotated_path(1))
        moved += 1
    except Exception as e:                                  # pragma: no cover
        logger.warning('audit_rotate: failed to rotate active file: %s', e)
        return moved

    logger.info('audit_rotate: rotated %d slot(s) (threshold=%d bytes)',
                moved, _max_audit_bytes())
    return moved


def _maybe_rotate_locked() -> bool:
    """Check the active file size and rotate if it exceeds the threshold.
    Returns True if rotation occurred. Caller must hold _LOCK."""
    threshold = _max_audit_bytes()
    try:
        size = AUDIT_PATH.stat().st_size if AUDIT_PATH.exists() else 0
    except Exception:
        size = 0
    if size <= threshold:
        return False
    _rotate_locked()
    return True


def audit_rotate_if_needed() -> int:
    """Manual rotation trigger. Returns number of slots moved (0 if no
    rotation was needed). Useful for tests and admin tooling. Same
    locking discipline as audit_append: in-process lock + cross-process
    flock on the active file."""
    threshold = _max_audit_bytes()
    try:
        size = AUDIT_PATH.stat().st_size if AUDIT_PATH.exists() else 0
    except Exception:
        return 0
    if size <= threshold:
        return 0
    with _LOCK:
        # Re-check after acquiring lock — another thread may have
        # rotated already.
        try:
            if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size <= threshold:
                return 0
        except Exception:
            return 0
        # Acquire the cross-process flock on the active file before rotating
        try:
            with open(AUDIT_PATH, 'rb') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    return _rotate_locked()
                finally:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning('audit_rotate_if_needed failed: %s', e)
            return 0


def audit_append(record: dict) -> bool:
    """Append `record` as one JSON line to the audit log.

    Returns True on success, False on any failure (logged, never raised).
    Adds an 'audit_v' = '11g' tag to the record so future format changes
    are inspectable.
    """
    ok, reason = _validate_record(record)
    if not ok:
        logger.warning('audit_append rejected: %s', reason)
        return False

    enriched = dict(record)
    enriched.setdefault('ts', time.time())
    enriched['audit_v'] = '11h'

    try:
        line = json.dumps(enriched, default=str, separators=(',', ':')) + '\n'
    except Exception as e:                                  # pragma: no cover
        logger.warning('audit_append serialize failed: %s', e)
        return False

    if len(line) > MAX_RECORD_BYTES:
        logger.warning(
            'audit_append rejected: serialized record %d > MAX_RECORD_BYTES %d',
            len(line), MAX_RECORD_BYTES,
        )
        return False

    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Open append-binary so the encoding is explicit, and use flock
        # to prevent interleaved writes from multiple worker threads.
        threshold = _max_audit_bytes()
        rotate_after = False
        with _LOCK:
            with open(AUDIT_PATH, 'ab') as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    f.write(line.encode('utf-8'))
                    f.flush()
                    # Check post-write size on the same fd we just wrote.
                    # Defer the actual rotate to after we drop the flock,
                    # since rename() races against an open exclusive lock.
                    try:
                        size_after = os.fstat(f.fileno()).st_size
                        if size_after > threshold:
                            rotate_after = True
                    except Exception:
                        pass
                finally:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except Exception:
                        pass

            # If we crossed the threshold on this append, rotate now while
            # still holding _LOCK so concurrent in-process appends queue
            # behind us. Cross-process safety: _rotate_locked re-acquires
            # an exclusive flock on the active file before doing renames.
            if rotate_after:
                try:
                    with open(AUDIT_PATH, 'rb') as rf:
                        fcntl.flock(rf.fileno(), fcntl.LOCK_EX)
                        try:
                            # Re-check size under the lock — another worker
                            # may have rotated between our two opens.
                            cur_size = os.fstat(rf.fileno()).st_size
                            if cur_size > threshold:
                                _rotate_locked()
                        finally:
                            try:
                                fcntl.flock(rf.fileno(), fcntl.LOCK_UN)
                            except Exception:
                                pass
                except FileNotFoundError:
                    # Already rotated by someone else; nothing to do
                    pass
                except Exception as e:                      # pragma: no cover
                    logger.warning('audit_append rotate-after-write failed: %s', e)
    except Exception as e:
        logger.warning('audit_append write failed: %s', e)
        return False

    return True


def audit_tail(n: int = 10) -> list[dict]:
    """Return the last `n` audit records as parsed dicts. Debug only —
    do NOT use this from production code paths."""
    if n <= 0 or not AUDIT_PATH.exists():
        return []
    try:
        with open(AUDIT_PATH, 'rb') as f:
            # Cheap tail: read everything if file is small (audit is small forever)
            data = f.read().decode('utf-8', errors='replace')
    except Exception:
        return []
    lines = [ln for ln in data.splitlines() if ln.strip()]
    out: list[dict] = []
    for ln in lines[-n:]:
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out
