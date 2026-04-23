# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
scripts/fast_reply_service.py — Session 11e, staging-only.

First staging local HTTP fast-lane service. Single-file stdlib http.server.
Bound to 127.0.0.1:8765 only — loopback is the safety boundary in 11e.

Endpoints:
    POST /v1/reply
        request body  → core.fast_reply_schema.validate_request
        success body  → core.fast_reply_schema.serialize_response
        error  body   → core.fast_reply_schema.error_response

    Everything else → 404 (unknown path) or 405 (wrong method).

Hard guarantees:
  • No daemon import.
  • No systemd unit.
  • No Telegram integration.
  • No live reasoning loop wiring.
  • Loopback bind verified at startup; refuses to bind anywhere else.
  • Perception data is sourced ONLY from the local shared cache/envelope
    via fast_reply(); the schema rejects any client attempt to inject it.
  • Auth is intentionally absent — local-only is the gate.
  • Graceful shutdown on SIGINT.

Run:
    cd /home/rohit/maez
    source .venv/bin/activate
    python scripts/fast_reply_service.py
    # in another shell:
    curl -sS -X POST http://127.0.0.1:8765/v1/reply \\
        -H 'content-type: application/json' \\
        -d '{"message":"hi","trust_scope":"rohit","max_tokens":300,"timeout_s":120}'
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Allow running from repo root with `python scripts/fast_reply_service.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.fast_reply_schema import (
    validate_request,
    serialize_response,
    error_response,
    ERR_NOT_JSON,
    ERR_INTERNAL,
)
from core.perception_cache import get_cache
from core.fast_conversation_log import get_log
from skills.fast_reply_prototype import fast_reply, FORBIDDEN_HOT_PATH_IMPORTS


# ── safety constants ───────────────────────────────────────────────────
ALLOWED_BIND_HOSTS = frozenset({'127.0.0.1', 'localhost', '::1'})
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8765
ENDPOINT     = '/v1/reply'

# Body size cap. Even though the schema caps message length at 4000 chars,
# the raw body can include other fields. 16KB is a generous ceiling.
MAX_BODY_BYTES = 16 * 1024

# ── CORS allowlist (Session 11f + 11g) ────────────────────────────────
# Strict allowlist for dev-only staging origins. NEVER '*'. NEVER the
# production domain. Adding origins later is a one-line change here.
#
#   :8000  — `python -m http.server` from /home/rohit/maez/staging (11f)
#   :11437 — the maez.live dev Flask app (skills/web_interface.py) (11g)
#
# https://maez.live (production) is intentionally NOT on this list and
# will not be added until the staging path has been observed for a full
# session of traffic.
CORS_ALLOWED_ORIGINS = frozenset({
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'http://127.0.0.1:11437',
    'http://localhost:11437',
})
CORS_ALLOWED_METHODS = 'POST, GET, OPTIONS'
CORS_ALLOWED_HEADERS = 'content-type'
CORS_MAX_AGE_S       = 600

# ── rate limiter (Session 11g) ────────────────────────────────────────
# Per-trust-scope token bucket. Two windows per scope:
#   per-minute window  (short-burst protection)
#   per-hour   window  (sustained-load protection)
#
# Defaults match the spec:
#   guest = 5/min,  30/hr
#   rohit = 60/min, 600/hr
#   default (any unknown scope) = same as guest, deliberately conservative
#
# Cloud-eligible scopes carry a SECONDARY budget for cloud-bound calls
# specifically. That budget is enforced inside the prototype/router layer
# in a future session — for 11g we just record the capacity here so the
# numbers are visible and stable.
RATE_LIMITS_PER_SCOPE: dict[str, dict] = {
    'rohit': {
        'per_min': 60,
        'per_hour': 600,
        'cloud_per_hour': 60,
    },
    'rohit.draft': {
        'per_min': 30,
        'per_hour': 300,
        'cloud_per_hour': 60,
    },
    'guest': {
        'per_min': 5,
        'per_hour': 30,
        'cloud_per_hour': 0,        # guests cannot reach cloud anyway
    },
    'public': {
        'per_min': 5,
        'per_hour': 30,
        'cloud_per_hour': 0,
    },
}
RATE_LIMITS_DEFAULT = {
    'per_min': 5,
    'per_hour': 30,
    'cloud_per_hour': 0,
}

logger = logging.getLogger('fast_reply_service')


# ── RateLimiter ──────────────────────────────────────────────────────
class _RateLimiter:
    """In-memory dual-window rate limiter keyed by trust_scope.

    Each scope has two sliding windows: per_min and per_hour. We store the
    *raw timestamps* of recent calls in two deques per scope and prune as
    we go. Memory cost is bounded by the per-hour budget × number of
    active scopes — for staging numbers this is trivially small.

    On a denied call, returns (False, retry_after_s, reason). On allow,
    records the timestamp and returns (True, 0.0, '').

    Restart resets all buckets, which is acceptable in staging.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # scope -> {'minute': deque[float], 'hour': deque[float]}
        self._buckets: dict[str, dict[str, list[float]]] = {}

    def _limits_for(self, scope: str) -> dict:
        return RATE_LIMITS_PER_SCOPE.get(scope, RATE_LIMITS_DEFAULT)

    def _get_bucket(self, scope: str) -> dict:
        b = self._buckets.get(scope)
        if b is None:
            b = {'minute': [], 'hour': []}
            self._buckets[scope] = b
        return b

    @staticmethod
    def _prune(times: list[float], cutoff: float) -> None:
        # In place: drop everything older than cutoff
        i = 0
        for i in range(len(times)):
            if times[i] >= cutoff:
                break
        else:
            i = len(times)
        if i > 0:
            del times[:i]

    def check_and_record(self, scope: str) -> tuple[bool, float, str]:
        """Atomically check + record one call against `scope`.

        Returns (allowed, retry_after_seconds, reason).
        """
        limits = self._limits_for(scope)
        now = time.time()
        min_cutoff  = now - 60.0
        hour_cutoff = now - 3600.0

        with self._lock:
            b = self._get_bucket(scope)
            self._prune(b['minute'], min_cutoff)
            self._prune(b['hour'], hour_cutoff)

            if len(b['minute']) >= limits['per_min']:
                # When does the oldest minute call age out?
                oldest = b['minute'][0]
                retry_in = max(1.0, (oldest + 60.0) - now)
                return False, retry_in, (
                    f'per_min budget exhausted ({limits["per_min"]}/min)'
                )
            if len(b['hour']) >= limits['per_hour']:
                oldest = b['hour'][0]
                retry_in = max(1.0, (oldest + 3600.0) - now)
                return False, retry_in, (
                    f'per_hour budget exhausted ({limits["per_hour"]}/hour)'
                )

            # Allow + record
            b['minute'].append(now)
            b['hour'].append(now)
            return True, 0.0, ''

    def status(self, scope: str) -> dict:
        """Snapshot of remaining budget for inspection / audit."""
        limits = self._limits_for(scope)
        now = time.time()
        with self._lock:
            b = self._get_bucket(scope)
            self._prune(b['minute'], now - 60.0)
            self._prune(b['hour'], now - 3600.0)
            return {
                'scope': scope,
                'used_per_min':       len(b['minute']),
                'limit_per_min':      limits['per_min'],
                'used_per_hour':      len(b['hour']),
                'limit_per_hour':     limits['per_hour'],
                'cloud_per_hour':     limits.get('cloud_per_hour', 0),
            }


# Module-level singleton — restart resets state, fine for staging.
_rate_limiter = _RateLimiter()


# Lazy import for the audit module so the service starts even if the
# audit file is somehow misconfigured.
def _audit_append_safe(record: dict) -> None:
    try:
        from core.fast_reply_audit import audit_append
        audit_append(record)
    except Exception as e:                                  # pragma: no cover
        logger.warning('audit append failed: %s', e)


# ── handler ────────────────────────────────────────────────────────────
class FastReplyHandler(BaseHTTPRequestHandler):
    """One handler instance per request — keep it dumb and stateless."""

    server_version = 'maez-fast-reply/0.1 (staging)'

    # Suppress noisy default access logs; we log structured ourselves.
    def log_message(self, format: str, *args) -> None:
        pass

    # ── helpers ────────────────────────────────────────────────────
    def _cors_origin(self) -> Optional[str]:
        """If the request's Origin matches the allowlist, return it; else None.
        Allowlist match is exact-string only — no scheme/host wildcarding."""
        origin = self.headers.get('origin')
        if origin and origin in CORS_ALLOWED_ORIGINS:
            return origin
        return None

    def _send_cors_headers(self) -> None:
        """Echo the matching origin (and only the matching origin) plus
        the minimum headers needed for the staging page to call us. No
        wildcards. Called from _send_json and do_OPTIONS."""
        allowed = self._cors_origin()
        if allowed is None:
            # No CORS headers at all when origin is missing or unknown.
            # Same-origin / non-browser clients (curl, the consumer demo)
            # are unaffected.
            return
        self.send_header('access-control-allow-origin', allowed)
        self.send_header('vary', 'origin')
        self.send_header('access-control-allow-methods', CORS_ALLOWED_METHODS)
        self.send_header('access-control-allow-headers', CORS_ALLOWED_HEADERS)
        self.send_header('access-control-max-age', str(CORS_MAX_AGE_S))

    def _send_json(self, status: int, body: dict) -> None:
        try:
            payload = json.dumps(body, default=str).encode('utf-8')
        except Exception as e:
            payload = json.dumps(error_response(
                ERR_INTERNAL, f'response serialization failed: {e!r}',
            )).encode('utf-8')
            status = 500
        self.send_response(status)
        self.send_header('content-type', 'application/json; charset=utf-8')
        self.send_header('content-length', str(len(payload)))
        # Explicitly disallow framing this in cross-origin contexts.
        # The service is loopback-only but defense-in-depth is cheap.
        self.send_header('x-content-type-options', 'nosniff')
        self.send_header('cache-control', 'no-store')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _read_body(self) -> tuple[bool, object, bytes]:
        """Reads the request body and returns (ok, parsed_or_error, raw_bytes).

        raw_bytes is empty on size/format failure, which is fine — the audit
        layer only uses it on the success path."""
        length = self.headers.get('content-length')
        try:
            n = int(length) if length is not None else 0
        except ValueError:
            return False, error_response(
                ERR_NOT_JSON, 'invalid content-length header',
            ), b''
        if n <= 0:
            return False, error_response(
                ERR_NOT_JSON, 'request body is empty',
            ), b''
        if n > MAX_BODY_BYTES:
            return False, error_response(
                'too_large',
                f'request body exceeds {MAX_BODY_BYTES} bytes',
                details={'length': n, 'max': MAX_BODY_BYTES},
            ), b''
        raw = self.rfile.read(n)
        try:
            return True, json.loads(raw.decode('utf-8')), raw
        except json.JSONDecodeError as e:
            return False, error_response(
                ERR_NOT_JSON,
                'request body is not valid JSON',
                details={'parse_error': str(e)},
            ), raw
        except UnicodeDecodeError as e:
            return False, error_response(
                ERR_NOT_JSON,
                'request body is not valid UTF-8',
                details={'decode_error': str(e)},
            ), raw

    # ── routing ────────────────────────────────────────────────────
    def do_OPTIONS(self) -> None:                      # noqa: N802 — preflight
        # Browsers send OPTIONS before a cross-origin POST with non-simple
        # headers (we use content-type: application/json, which triggers
        # preflight). Reply 204 + CORS headers if the origin is allowlisted;
        # otherwise reply 403 with no CORS headers so the browser fails
        # closed.
        allowed = self._cors_origin()
        if allowed is None:
            # Origin missing or not in allowlist — refuse without leaking
            # any CORS info.
            self.send_response(403)
            self.send_header('content-length', '0')
            self.end_headers()
            return
        self.send_response(204)
        self._send_cors_headers()
        self.send_header('content-length', '0')
        self.end_headers()

    def do_GET(self) -> None:                          # noqa: N802 — required name
        if self.path == '/healthz':
            self._send_json(200, {'status': 'ok', 'service': 'maez-fast-reply', 'staging': True})
            return
        self._send_json(404, error_response(
            'not_found',
            f'unknown path {self.path!r}',
            details={'allowed': [ENDPOINT, '/healthz']},
        ))

    def do_POST(self) -> None:                         # noqa: N802
        if self.path != ENDPOINT:
            self._send_json(404, error_response(
                'not_found',
                f'unknown path {self.path!r}',
                details={'allowed': [ENDPOINT]},
            ))
            return

        ct = (self.headers.get('content-type') or '').lower()
        if not ct.startswith('application/json'):
            self._send_json(415, error_response(
                'unsupported_media_type',
                'content-type must be application/json',
                details={'got': ct},
            ))
            return

        ok, body, raw_bytes = self._read_body()
        if not ok:
            self._send_json(400, body)
            return

        ok, request_dict, err = validate_request(body)
        if not ok:
            self._send_json(400, err)
            return

        # ── Session 11h: capture adapter version header ──
        # The maez.live staging adapter sends X-Maez-Adapter-Version so the
        # audit log can distinguish adapter callers from direct callers
        # (curl, the consumer demo, the static dev page). Direct callers
        # leave this as None. We sanitize the value (cap length, strip
        # control chars) before recording.
        raw_av = self.headers.get('x-maez-adapter-version')
        if raw_av is not None:
            adapter_version = ''.join(
                ch for ch in raw_av[:128] if ch.isprintable()
            ) or None
        else:
            adapter_version = None

        # ── rate limit (Session 11g) ──
        # After schema validation so we don't burn budget on garbage,
        # before fast_reply() so we don't pay model cost on rate-limit hits.
        scope = request_dict['trust_scope']
        allowed, retry_after, rl_reason = _rate_limiter.check_and_record(scope)
        if not allowed:
            rl_status = _rate_limiter.status(scope)
            err_body = error_response(
                'rate_limited',
                f'rate limit exceeded for trust_scope={scope!r}: {rl_reason}',
                details={
                    'retry_after_seconds': round(retry_after, 1),
                    'limits': rl_status,
                },
            )
            # Append a clipped Retry-After header on the wire
            self.send_response(429)
            self.send_header('content-type', 'application/json; charset=utf-8')
            payload = json.dumps(err_body).encode('utf-8')
            self.send_header('content-length', str(len(payload)))
            self.send_header('x-content-type-options', 'nosniff')
            self.send_header('cache-control', 'no-store')
            self.send_header('retry-after', str(int(retry_after) + 1))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(payload)
            # Audit the rejection
            _audit_append_safe({
                'ts': time.time(),
                'event': 'rate_limited',
                'trust_scope': scope,
                'request_sha256': hashlib.sha256(raw_bytes).hexdigest(),
                'request_bytes': len(raw_bytes),
                'rl_reason': rl_reason,
                'rl_retry_after_s': round(retry_after, 1),
                'rl_status': rl_status,
                'http_status': 429,
                'adapter_version': adapter_version,
            })
            logger.info('rate_limited scope=%s reason=%s retry_after=%.1f',
                        scope, rl_reason, retry_after)
            return

        # ── snapshot forbidden modules to prove the hot path is clean ──
        pre_call_forbidden = {m for m in FORBIDDEN_HOT_PATH_IMPORTS if m in sys.modules}

        cache = get_cache()
        log   = get_log()
        try:
            result = fast_reply(
                user_message       = request_dict['message'],
                cache              = cache,
                trust_scope        = request_dict['trust_scope'],
                backend            = request_dict['backend'],
                max_tokens         = request_dict['max_tokens'],
                temperature        = request_dict['temperature'],
                timeout_s          = request_dict['timeout_s'],
                history_load_n     = request_dict['history_load_n'],
                persist_history    = request_dict['persist_history'],
                auto_load_history  = request_dict['auto_load_history'],
                history_log        = log,
            )
        except Exception as e:
            logger.exception('fast_reply raised — this should be impossible')
            self._send_json(500, error_response(
                ERR_INTERNAL,
                f'fast_reply raised: {e!r}',
            ))
            _audit_append_safe({
                'ts': time.time(),
                'event': 'internal_error',
                'trust_scope': scope,
                'request_sha256': hashlib.sha256(raw_bytes).hexdigest(),
                'request_bytes': len(raw_bytes),
                'error': repr(e),
                'http_status': 500,
                'adapter_version': adapter_version,
            })
            return

        post_call_forbidden = {m for m in FORBIDDEN_HOT_PATH_IMPORTS if m in sys.modules}
        newly_imported = sorted(post_call_forbidden - pre_call_forbidden)
        if newly_imported:
            logger.error(
                'invariant violated: hot path imported %s',
                newly_imported,
            )
            # Still return the result — but flag the violation in logs.

        response_body = serialize_response(result)
        # Always 200 even on degraded fast_reply; success/error live in body.
        # The HTTP layer is reserved for transport-level failures only.
        self._send_json(200, response_body)

        # Structured access log to stderr
        m = result.metrics
        logger.info(
            'reply scope=%s backend=%s model_ms=%s total_ms=%s '
            'screen=%s system=%s calendar=%s retry=%s rule=%s',
            request_dict['trust_scope'], m.backend_name, m.model_call_ms, m.total_ms,
            m.screen_freshness, m.system_state_freshness, m.calendar_freshness,
            m.retry_strategy or 'none', m.policy_rule or '-',
        )

        # ── audit the call (Session 11g) ──
        # METADATA ONLY. Never log raw prompt content. Never log raw reply
        # content. The request body sha256 + char counts are sufficient
        # for forensic replay against a known-input corpus.
        reply_text = result.reply_text or ''
        _audit_append_safe({
            'ts':                    time.time(),
            'event':                 'reply',
            'trust_scope':           scope,
            'request_sha256':        hashlib.sha256(raw_bytes).hexdigest(),
            'request_bytes':         len(raw_bytes),
            'prompt_chars':          m.prompt_chars,
            'response_chars':        len(reply_text),
            'backend_name':          m.backend_name,
            'backend_success':       m.backend_success,
            'model_call_ms':         m.model_call_ms,
            'total_ms':              m.total_ms,
            'retry_strategy':        m.retry_strategy or '',
            'retry_succeeded':       bool(m.retry_succeeded),
            'policy_rule':           m.policy_rule or '',
            'policy_effective':      m.policy_effective or '',
            'policy_downgraded':     bool(m.policy_downgraded),
            'screen_freshness':      m.screen_freshness,
            'system_state_freshness': m.system_state_freshness,
            'calendar_freshness':    m.calendar_freshness,
            'cloud_redacted':        bool(getattr(m, 'cloud_redacted', False)),
            'cloud_redactions':      int(getattr(m, 'cloud_redactions', 0)),
            'http_status':           200,
            'success':               bool(result.success),
            'adapter_version':       adapter_version,
        })


def _make_server(host: str, port: int) -> HTTPServer:
    if host not in ALLOWED_BIND_HOSTS:
        raise SystemExit(
            f'refusing to bind to {host!r} — only loopback hosts allowed in 11e: '
            f'{sorted(ALLOWED_BIND_HOSTS)}'
        )
    return HTTPServer((host, port), FastReplyHandler)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default=DEFAULT_HOST,
                    help=f'bind host (must be loopback) — default {DEFAULT_HOST}')
    ap.add_argument('--port', type=int, default=DEFAULT_PORT,
                    help=f'bind port — default {DEFAULT_PORT}')
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    httpd = _make_server(args.host, args.port)
    print(f'maez fast-reply staging service listening on http://{args.host}:{args.port}{ENDPOINT}')
    print('  POST a JSON body — see core/fast_reply_schema.py for the schema')
    print('  press Ctrl-C to stop')

    stop_event = threading.Event()

    def _on_signal(signum, frame):
        print(f'\nreceived signal {signum}, shutting down...')
        stop_event.set()
        # http.server's serve_forever doesn't return until shutdown() is
        # called from another thread.
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        print('service stopped')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
