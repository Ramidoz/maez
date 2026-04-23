"""
core/public_user_shaping.py — Session 11f, staging-only.

Shapes a raw public-facing message into the exact request body the staging
fast reply service expects. This is the layer that stops external users
from directly shaping privileged fast-lane requests.

Hard contract:
  • Output is always a dict that core.fast_reply_schema.validate_request
    will accept (when the underlying message is non-empty).
  • trust_scope is forced to 'guest' (and the policy table pins guest to
    local-only — see core.fast_backend_router).
  • max_tokens is capped at GUEST_MAX_TOKENS, even if metadata asks for more.
  • temperature is capped at GUEST_MAX_TEMPERATURE.
  • timeout_s is capped at GUEST_MAX_TIMEOUT_S.
  • Any metadata key that touches perception, daemon state, or schema fields
    the server should own (history, persist_history, etc.) is rejected hard
    via shape_public_request raising ShapingRejected.
  • PII is stripped via deterministic regex replacement BEFORE the message
    leaves this module. Stripping is conservative — false positives are
    preferable to leaks.

Public surface:
    GUEST_MAX_TOKENS               int  (default 512)
    GUEST_MAX_TEMPERATURE          float (0.7)
    GUEST_MAX_TIMEOUT_S            float (60.0)
    PUBLIC_FORBIDDEN_METADATA_KEYS frozenset

    class ShapingRejected(Exception)
        .code: str
        .details: dict

    strip_pii(text) -> (cleaned_text, stripped_count_by_kind)
    shape_public_request(raw_message, raw_metadata=None, scope='guest') -> dict
    is_safe_metadata(raw_metadata) -> (ok: bool, error: dict|None)

The output dict contains the keys validate_request expects:
    message, trust_scope, backend, max_tokens, temperature, timeout_s,
    history_load_n, persist_history, auto_load_history.
"""

from __future__ import annotations

import re
from typing import Any, Optional


# ── caps for guest scope ──────────────────────────────────────────────
GUEST_MAX_TOKENS      = 512
GUEST_MAX_TEMPERATURE = 0.7
# Session 11j: dropped from 180.0 → 15.0. The earlier bumps (60→120→180)
# were compensating for gemma4:26b's thinking phase burning all wall-clock.
# Landing `think: false` in fast_backend_local (same session) cut cold replies
# to ~0.3s, so this cap is now a 50x headroom over the measured worst case
# rather than a life support budget. 15s still absorbs a cold model load or
# temporary GPU contention. Schema MIN_TIMEOUT_S=1.0 floor respected.
GUEST_MAX_TIMEOUT_S   = 15.0
GUEST_HISTORY_LOAD_N  = 4

# Hard ceiling on raw input length BEFORE shaping. The schema also caps at
# 4000 chars; we cap earlier to avoid wasting CPU on huge inputs.
GUEST_MAX_RAW_MESSAGE_CHARS = 2000


# ── forbidden metadata keys ────────────────────────────────────────────
# These overlap intentionally with REQUEST_KEYS_FORBIDDEN in the schema
# (perception injection) plus a wider set of fields the public caller has
# no business setting (history, trust_scope, max_tokens — those are server
# decisions, not client choices).
PUBLIC_FORBIDDEN_METADATA_KEYS = frozenset({
    # perception injection
    'screen', 'system_state', 'system', 'calendar',
    'perception', 'envelope', 'cache', 'snapshot',
    'memory', 'memories', 'soul', 'identity_block',
    # daemon territory
    'cognition_evidence', 'critique',
    'proposal', 'candidate',
    'perception_envelope', 'envelope_sources',
    # server-controlled fields the client cannot set via the public path
    'trust_scope',         # always 'guest' for public callers
    'backend',             # always router-decided for public callers
    'max_tokens',          # capped to GUEST_MAX_TOKENS
    'temperature',         # capped to GUEST_MAX_TEMPERATURE
    'timeout_s',           # capped to GUEST_MAX_TIMEOUT_S
    'history',             # server-side, by trust_scope
    'turns',
    'history_load_n',
    'persist_history',
    'auto_load_history',
})


# ── PII patterns ───────────────────────────────────────────────────────
# Conservative — false positives accepted. Each pattern is named so the
# caller can see what was stripped.
_PII_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # email
    ('email', re.compile(
        r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b'
    ), '[email]'),

    # phone — US-ish, very loose; matches "(555) 123-4567", "555-123-4567",
    # "+1 555 123 4567", "5551234567"
    ('phone', re.compile(
        r'(?<!\w)(?:\+?\d{1,3}[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}(?!\w)'
    ), '[phone]'),

    # absolute filesystem path (linux/mac style) — strong leak signal
    ('fs_path', re.compile(
        r'(?<!\w)/(?:home|root|Users|var|etc|opt|tmp|mnt|srv)/[^\s\'"]*'
    ), '[path]'),

    # plausible API key / token — long base64-ish run with mixed case+digits
    ('api_key', re.compile(
        r'(?<![A-Za-z0-9])[A-Za-z0-9_\-]{32,}(?![A-Za-z0-9])'
    ), '[token]'),

    # IPv4 (don't strip 127.0.0.1 / 0.0.0.0 — those aren't PII)
    ('ipv4', re.compile(
        r'\b(?!127\.0\.0\.1\b|0\.0\.0\.0\b|255\.255\.255\.255\b)'
        r'(?:\d{1,3}\.){3}\d{1,3}\b'
    ), '[ip]'),

    # generic 9+ digit run (SSN-ish, account number, long ID)
    ('long_digits', re.compile(
        r'(?<!\d)\d{9,}(?!\d)'
    ), '[id]'),
]


class ShapingRejected(Exception):
    """Raised when the raw input cannot be safely shaped into a public request."""
    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def strip_pii(text: str) -> tuple[str, dict[str, int]]:
    """Apply all PII patterns to `text`. Returns (cleaned_text, counts_by_kind)."""
    counts: dict[str, int] = {}
    out = text
    for kind, pattern, replacement in _PII_PATTERNS:
        out, n = pattern.subn(replacement, out)
        if n:
            counts[kind] = counts.get(kind, 0) + n
    return out, counts


def is_safe_metadata(raw_metadata: Optional[dict]) -> tuple[bool, Optional[dict]]:
    """Check whether `raw_metadata` contains any forbidden keys.

    Returns (ok, error_dict). When ok is False, error_dict has shape:
        {'code': str, 'message': str, 'details': {...}}
    """
    if raw_metadata is None:
        return True, None
    if not isinstance(raw_metadata, dict):
        return False, {
            'code':    'bad_metadata_type',
            'message': 'metadata must be a dict or None',
            'details': {'got_type': type(raw_metadata).__name__},
        }
    forbidden = PUBLIC_FORBIDDEN_METADATA_KEYS & set(raw_metadata.keys())
    if forbidden:
        return False, {
            'code':    'forbidden_public_metadata',
            'message': (
                'public-facing requests may not set fields the server controls'
            ),
            'details': {'forbidden_keys_present': sorted(forbidden)},
        }
    return True, None


def shape_public_request(
    raw_message: Any,
    raw_metadata: Optional[dict] = None,
    scope: str = 'guest',
) -> dict:
    """Convert raw public input into a server-acceptable request body.

    Raises ShapingRejected on:
      • non-string raw_message
      • empty raw_message
      • raw_message exceeding GUEST_MAX_RAW_MESSAGE_CHARS
      • raw_metadata containing any forbidden key

    Returns a dict ready to POST to /v1/reply. The returned dict
    has a non-standard '_shaping' key with telemetry — the caller
    must remove it before sending to the server (the demo and the
    page do this explicitly).
    """
    if not isinstance(raw_message, str):
        raise ShapingRejected(
            'bad_message_type',
            'raw_message must be a string',
            {'got_type': type(raw_message).__name__},
        )

    raw_stripped = raw_message.strip()
    if not raw_stripped:
        raise ShapingRejected('empty_message', 'raw_message must not be empty')

    if len(raw_stripped) > GUEST_MAX_RAW_MESSAGE_CHARS:
        raise ShapingRejected(
            'raw_message_too_long',
            f'raw_message exceeds {GUEST_MAX_RAW_MESSAGE_CHARS} chars',
            {'length': len(raw_stripped), 'max': GUEST_MAX_RAW_MESSAGE_CHARS},
        )

    ok, err = is_safe_metadata(raw_metadata)
    if not ok:
        raise ShapingRejected(err['code'], err['message'], err.get('details'))

    cleaned, pii_counts = strip_pii(raw_stripped)

    # Force scope to guest by default. We accept an override but ONLY if
    # the override is also a 'public' scope name like 'public' — never
    # 'rohit' or anything privileged. This is defense-in-depth: the
    # caller can't escalate by passing scope='rohit'.
    if scope not in ('guest', 'public'):
        raise ShapingRejected(
            'forbidden_scope',
            'public shaping only allows guest or public trust scopes',
            {'got': scope},
        )
    forced_scope = scope

    body = {
        'message':           cleaned,
        'trust_scope':       forced_scope,
        'backend':           'auto',          # router decides; policy pins to local
        'max_tokens':        GUEST_MAX_TOKENS,
        'temperature':       GUEST_MAX_TEMPERATURE,
        'timeout_s':         GUEST_MAX_TIMEOUT_S,
        'history_load_n':    GUEST_HISTORY_LOAD_N,
        'persist_history':   True,
        'auto_load_history': True,
        # Telemetry — caller must strip before POSTing
        '_shaping': {
            'pii_stripped':     pii_counts,
            'raw_length':       len(raw_stripped),
            'cleaned_length':   len(cleaned),
            'scope_forced_to':  forced_scope,
            'caps_applied': {
                'max_tokens':  GUEST_MAX_TOKENS,
                'temperature': GUEST_MAX_TEMPERATURE,
                'timeout_s':   GUEST_MAX_TIMEOUT_S,
            },
        },
    }
    return body


def split_shaping_telemetry(body: dict) -> tuple[dict, dict]:
    """Split a shaped body into (server_body, telemetry).

    Use this in the demo / consumer / page just before POSTing — the
    server-bound dict has '_shaping' removed; the telemetry is logged
    or shown to the operator.
    """
    if '_shaping' not in body:
        return body, {}
    out = {k: v for k, v in body.items() if k != '_shaping'}
    return out, body['_shaping']
