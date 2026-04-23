# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
core/fast_reply_schema.py — Session 11e, staging-only.

Strict request/response schema for the staging fast-lane HTTP service
(scripts/fast_reply_service.py). The boundary lives here so the server
file stays small and inspectable.

Hard rejection rules:
  • Unknown top-level keys are rejected (no silent ignore).
  • Any key whose name suggests perception injection is rejected with a
    specific error code, even before type validation. The server MUST
    source perception only from the local shared cache/envelope; clients
    cannot inject screen state, system state, calendar state, an entire
    envelope, or any cache-shaped object.
  • Type-checking is explicit; no duck typing on `bool` vs `int`.
  • Lengths are capped to keep payloads small (this is the fast lane,
    not a long-form deep reasoning channel).

Public surface:
    REQUEST_KEYS_REQUIRED       — frozenset
    REQUEST_KEYS_OPTIONAL       — frozenset
    REQUEST_KEYS_FORBIDDEN      — frozenset
    MAX_MESSAGE_CHARS           — int
    validate_request(payload)   -> (ok: bool, request: dict|None, error: dict|None)
    serialize_response(result)  -> dict   (FastReplyResult -> JSON-able dict)
    error_response(code, message, details=None) -> dict
"""

from __future__ import annotations

from typing import Any, Optional


# ── allowed shape ────────────────────────────────────────────────────
REQUEST_KEYS_REQUIRED = frozenset({'message', 'trust_scope'})
REQUEST_KEYS_OPTIONAL = frozenset({
    'backend',          # 'auto' | 'local' | 'cloud'
    'max_tokens',       # int
    'temperature',      # float
    'timeout_s',        # float
    'history_load_n',   # int
    'persist_history',  # bool
    'auto_load_history',# bool
})
REQUEST_KEYS_ALLOWED = REQUEST_KEYS_REQUIRED | REQUEST_KEYS_OPTIONAL

# Anything that looks like a perception-injection or daemon-state-injection
# attempt. The server MUST refuse these specifically and visibly so callers
# get a clear error rather than a silent drop.
REQUEST_KEYS_FORBIDDEN = frozenset({
    'screen', 'system_state', 'system', 'calendar',
    'perception', 'envelope', 'cache', 'snapshot',
    'memory', 'memories', 'soul', 'identity_block',
    'history', 'turns',                 # history is server-side, by trust_scope
    'cognition_evidence', 'critique',   # daemon territory, not fast lane
    'proposal', 'candidate',            # proposal machinery, not fast lane
    'perception_envelope', 'envelope_sources',
    'screen_value', 'system_state_value', 'calendar_value',
})

VALID_BACKENDS = frozenset({'auto', 'local', 'cloud'})

# Caps — kept tight on purpose; this is the fast lane.
MAX_MESSAGE_CHARS  = 4000
MAX_TRUST_SCOPE    = 64
MAX_TOKENS_CEILING = 4096
MIN_TOKENS         = 16
MAX_TEMPERATURE    = 2.0
MAX_TIMEOUT_S      = 600.0
MIN_TIMEOUT_S      = 1.0
MAX_HISTORY_LOAD_N = 32


# ── error codes ──────────────────────────────────────────────────────
ERR_NOT_JSON              = 'not_json'
ERR_NOT_OBJECT            = 'not_object'
ERR_UNKNOWN_KEY           = 'unknown_key'
ERR_FORBIDDEN_KEY         = 'forbidden_key_perception_injection'
ERR_MISSING_REQUIRED      = 'missing_required'
ERR_BAD_TYPE              = 'bad_type'
ERR_BAD_VALUE             = 'bad_value'
ERR_TOO_LARGE             = 'too_large'
ERR_INTERNAL              = 'internal'


def error_response(code: str, message: str, details: Optional[dict] = None) -> dict:
    out = {
        'success': False,
        'reply': '',
        'backend': 'none',
        'metrics': {},
        'error': {
            'code': code,
            'message': message,
        },
    }
    if details:
        out['error']['details'] = details
    return out


def _is_int(v: Any) -> bool:
    # bool is a subclass of int — exclude it explicitly
    return isinstance(v, int) and not isinstance(v, bool)


def _is_number(v: Any) -> bool:
    return (isinstance(v, (int, float)) and not isinstance(v, bool))


def _is_bool(v: Any) -> bool:
    return isinstance(v, bool)


def validate_request(payload: Any) -> tuple[bool, Optional[dict], Optional[dict]]:
    """Validate the parsed JSON body of a /v1/reply POST.

    Returns (ok, request_dict_with_defaults, error_dict).
    Exactly one of (request_dict, error_dict) is non-None.

    On success the returned dict has every optional field filled in with
    its default so the service can call fast_reply() without per-field
    None checks.
    """
    if not isinstance(payload, dict):
        return (False, None, error_response(
            ERR_NOT_OBJECT,
            'request body must be a JSON object',
        ))

    # ── 1. forbidden keys ──
    forbidden_present = REQUEST_KEYS_FORBIDDEN & set(payload.keys())
    if forbidden_present:
        return (False, None, error_response(
            ERR_FORBIDDEN_KEY,
            (
                'request contains forbidden keys — perception data must come '
                'from the local cache, never from the client'
            ),
            details={'forbidden_keys_present': sorted(forbidden_present)},
        ))

    # ── 2. unknown keys ──
    unknown = set(payload.keys()) - REQUEST_KEYS_ALLOWED
    if unknown:
        return (False, None, error_response(
            ERR_UNKNOWN_KEY,
            'request contains keys not in the allowed schema',
            details={
                'unknown_keys': sorted(unknown),
                'allowed_keys': sorted(REQUEST_KEYS_ALLOWED),
            },
        ))

    # ── 3. required keys present ──
    missing = REQUEST_KEYS_REQUIRED - set(payload.keys())
    if missing:
        return (False, None, error_response(
            ERR_MISSING_REQUIRED,
            'request is missing required keys',
            details={'missing_keys': sorted(missing)},
        ))

    # ── 4. message ──
    message = payload['message']
    if not isinstance(message, str):
        return (False, None, error_response(
            ERR_BAD_TYPE, 'message must be a string',
            details={'got_type': type(message).__name__},
        ))
    message = message.strip()
    if not message:
        return (False, None, error_response(
            ERR_BAD_VALUE, 'message must not be empty',
        ))
    if len(message) > MAX_MESSAGE_CHARS:
        return (False, None, error_response(
            ERR_TOO_LARGE,
            f'message exceeds {MAX_MESSAGE_CHARS} chars',
            details={'length': len(message), 'max': MAX_MESSAGE_CHARS},
        ))

    # ── 5. trust_scope ──
    trust_scope = payload['trust_scope']
    if not isinstance(trust_scope, str):
        return (False, None, error_response(
            ERR_BAD_TYPE, 'trust_scope must be a string',
            details={'got_type': type(trust_scope).__name__},
        ))
    trust_scope = trust_scope.strip()
    if not trust_scope:
        return (False, None, error_response(
            ERR_BAD_VALUE, 'trust_scope must not be empty',
        ))
    if len(trust_scope) > MAX_TRUST_SCOPE:
        return (False, None, error_response(
            ERR_TOO_LARGE, f'trust_scope exceeds {MAX_TRUST_SCOPE} chars',
        ))
    # Limited charset — letters, digits, dot, dash, underscore. Rejects
    # path-traversal, shell injection, and unicode confusion attacks.
    for ch in trust_scope:
        if not (ch.isalnum() or ch in '._-'):
            return (False, None, error_response(
                ERR_BAD_VALUE,
                'trust_scope must contain only [A-Za-z0-9._-]',
                details={'illegal_char': ch},
            ))

    # ── 6. backend ──
    backend = payload.get('backend', 'auto')
    if not isinstance(backend, str):
        return (False, None, error_response(
            ERR_BAD_TYPE, 'backend must be a string',
        ))
    if backend not in VALID_BACKENDS:
        return (False, None, error_response(
            ERR_BAD_VALUE,
            f'backend must be one of {sorted(VALID_BACKENDS)}',
            details={'got': backend},
        ))

    # ── 7. max_tokens ──
    max_tokens = payload.get('max_tokens', 256)
    if not _is_int(max_tokens):
        return (False, None, error_response(
            ERR_BAD_TYPE, 'max_tokens must be an integer',
        ))
    if not (MIN_TOKENS <= max_tokens <= MAX_TOKENS_CEILING):
        return (False, None, error_response(
            ERR_BAD_VALUE,
            f'max_tokens must be in [{MIN_TOKENS}, {MAX_TOKENS_CEILING}]',
            details={'got': max_tokens},
        ))

    # ── 8. temperature ──
    temperature = payload.get('temperature', 0.4)
    if not _is_number(temperature):
        return (False, None, error_response(
            ERR_BAD_TYPE, 'temperature must be a number',
        ))
    if not (0.0 <= float(temperature) <= MAX_TEMPERATURE):
        return (False, None, error_response(
            ERR_BAD_VALUE,
            f'temperature must be in [0.0, {MAX_TEMPERATURE}]',
            details={'got': temperature},
        ))
    temperature = float(temperature)

    # ── 9. timeout_s ──
    timeout_s = payload.get('timeout_s', 120.0)
    if not _is_number(timeout_s):
        return (False, None, error_response(
            ERR_BAD_TYPE, 'timeout_s must be a number',
        ))
    if not (MIN_TIMEOUT_S <= float(timeout_s) <= MAX_TIMEOUT_S):
        return (False, None, error_response(
            ERR_BAD_VALUE,
            f'timeout_s must be in [{MIN_TIMEOUT_S}, {MAX_TIMEOUT_S}]',
            details={'got': timeout_s},
        ))
    timeout_s = float(timeout_s)

    # ── 10. history_load_n ──
    history_load_n = payload.get('history_load_n', 8)
    if not _is_int(history_load_n):
        return (False, None, error_response(
            ERR_BAD_TYPE, 'history_load_n must be an integer',
        ))
    if not (0 <= history_load_n <= MAX_HISTORY_LOAD_N):
        return (False, None, error_response(
            ERR_BAD_VALUE,
            f'history_load_n must be in [0, {MAX_HISTORY_LOAD_N}]',
            details={'got': history_load_n},
        ))

    # ── 11. booleans ──
    persist_history = payload.get('persist_history', True)
    if not _is_bool(persist_history):
        return (False, None, error_response(
            ERR_BAD_TYPE, 'persist_history must be a boolean',
        ))
    auto_load_history = payload.get('auto_load_history', True)
    if not _is_bool(auto_load_history):
        return (False, None, error_response(
            ERR_BAD_TYPE, 'auto_load_history must be a boolean',
        ))

    return (True, {
        'message':           message,
        'trust_scope':       trust_scope,
        'backend':           backend,
        'max_tokens':        max_tokens,
        'temperature':       temperature,
        'timeout_s':         timeout_s,
        'history_load_n':    history_load_n,
        'persist_history':   persist_history,
        'auto_load_history': auto_load_history,
    }, None)


def serialize_response(result) -> dict:
    """Convert a FastReplyResult into the JSON-able response shape.
    `result` is a skills.fast_reply_prototype.FastReplyResult."""
    metrics_dict = result.metrics.to_dict() if hasattr(result.metrics, 'to_dict') else {}
    payload = {
        'success': bool(result.success),
        'reply':   result.reply_text or '',
        'backend': metrics_dict.get('backend_name', 'none'),
        'metrics': metrics_dict,
    }
    if not result.success:
        payload['error'] = {
            'code':    'reply_failed',
            'message': result.error or 'unknown error',
        }
    else:
        payload['error'] = None
    return payload
