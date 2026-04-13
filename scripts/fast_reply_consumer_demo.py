"""
scripts/fast_reply_consumer_demo.py — Session 11f, staging-only.

First true external consumer of the staging fast reply HTTP boundary.
Unlike scripts/fast_reply_cli.py (which calls fast_reply() in-process),
this script POSTs over real HTTP to 127.0.0.1:8765/v1/reply, so it
exercises the schema and the wire contract end-to-end.

Two demonstration paths:

  PATH A — privileged direct rohit POST
    Builds the body manually, posts to /v1/reply with trust_scope='rohit'.
    This is what an in-house, trusted consumer (e.g. the future the owner
    desktop wrapper) would do.

  PATH B — public-user shaped guest POST
    Takes a raw "external user" message (with intentional PII), runs it
    through core.public_user_shaping.shape_public_request, prints the
    cleaned + capped body, then POSTs it. Demonstrates the defense layer.

Synthetic conversation:
    Path A sends three messages in sequence to demonstrate that history
    persists across HTTP calls within the same trust_scope.

Validation:
    Run `python scripts/fast_reply_service.py` first, then
    `python scripts/fast_reply_consumer_demo.py`.
    Use `--no-real-backend` to skip the actual model calls (relies on the
    service still being reachable, but uses a tiny max_tokens to fail fast).

This is staging-only:
  • No daemon import.
  • No live routing.
  • Refuses to POST anywhere except a loopback host.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Allow running from repo root with `python scripts/fast_reply_consumer_demo.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.public_user_shaping import (
    shape_public_request,
    split_shaping_telemetry,
    ShapingRejected,
    GUEST_MAX_TOKENS,
)


# ── transport ──────────────────────────────────────────────────────────
DEFAULT_URL = 'http://127.0.0.1:8765/v1/reply'

ALLOWED_HOSTS = frozenset({'127.0.0.1', 'localhost', '::1', '[::1]'})


def _check_loopback_url(url: str) -> None:
    """Refuse to POST anywhere except a loopback host."""
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or '').lower()
    if host not in ALLOWED_HOSTS:
        raise SystemExit(
            f'refusing to POST to non-loopback host {host!r}; '
            f'allowed hosts: {sorted(ALLOWED_HOSTS)}'
        )


def post_json(url: str, body: dict, timeout_s: float = 240.0) -> tuple[int, dict, float]:
    """POST `body` as JSON to `url`. Returns (status, parsed_response, latency_ms).

    Network errors are surfaced as (0, {'error': str}, latency_ms) so the
    caller can print them rather than crash."""
    _check_loopback_url(url)
    raw = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=raw,
        headers={
            'content-type': 'application/json',
            'accept':       'application/json',
            'user-agent':   'maez-fast-reply-consumer-demo/0.1',
        },
        method='POST',
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body_bytes = resp.read()
            status = resp.status
            parsed = json.loads(body_bytes.decode('utf-8'))
    except urllib.error.HTTPError as e:
        # Server returned a 4xx/5xx — body is still parseable JSON in our case
        body_bytes = e.read() or b''
        status = e.code
        try:
            parsed = json.loads(body_bytes.decode('utf-8'))
        except Exception:
            parsed = {'error': {'code': 'unparseable', 'message': body_bytes.decode('utf-8', 'replace')}}
    except urllib.error.URLError as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        return 0, {'error': {'code': 'transport', 'message': str(e)}}, latency_ms
    latency_ms = (time.perf_counter() - t0) * 1000
    return status, parsed, latency_ms


# ── pretty printing ────────────────────────────────────────────────────
def banner(title: str) -> None:
    print()
    print('=' * 78)
    print(f'  {title}')
    print('=' * 78)


def print_request(label: str, body: dict) -> None:
    print(f'  {label}')
    print('  ' + '-' * 76)
    pretty = json.dumps(body, indent=2)
    for line in pretty.splitlines():
        print(f'  {line}')
    print('  ' + '-' * 76)


def print_response(status: int, parsed: dict, latency_ms: float) -> None:
    print(f'  HTTP status     : {status}')
    print(f'  round_trip_ms   : {latency_ms:.1f}')
    print('  response body   :')
    pretty = json.dumps(parsed, indent=2)
    for line in pretty.splitlines():
        print(f'    {line}')
    # Extract a friendly summary
    if isinstance(parsed, dict):
        ok = parsed.get('success')
        backend = parsed.get('backend')
        reply = parsed.get('reply', '')
        m = parsed.get('metrics') or {}
        retry = m.get('retry_strategy') or 'none'
        print()
        print(f'  → success       : {ok}')
        print(f'  → backend       : {backend}')
        print(f'  → reply         : {reply[:200]!r}')
        print(f'  → retry         : {retry}')
        if m:
            print(
                f'  → key timing    : envelope={m.get("envelope_build_ms")}ms '
                f'prompt={m.get("prompt_build_ms")}ms '
                f'model={m.get("model_call_ms")}ms '
                f'total={m.get("total_ms")}ms'
            )
            print(
                f'  → freshness     : screen={m.get("screen_freshness")} '
                f'system_state={m.get("system_state_freshness")} '
                f'calendar={m.get("calendar_freshness")}'
            )
            if m.get('policy_rule'):
                print(
                    f'  → policy        : rule={m.get("policy_rule")} '
                    f'effective={m.get("policy_effective")} '
                    f'allow_cloud={m.get("policy_allow_cloud")} '
                    f'downgraded={m.get("policy_downgraded")}'
                )


# ── path A — privileged direct rohit POST ─────────────────────────────
PATH_A_TURNS = [
    'in one short sentence: are you alive?',
    'good. now: am i talking to maez or to gemma?',
    'last one: confirm in five words.',
]


def path_a_direct_rohit(url: str, max_tokens: int, timeout_s: float) -> int:
    banner("PATH A — direct rohit POST (privileged in-process consumer pattern)")
    print(
        '  This path POSTs the body the in-house consumer would build itself,\n'
        '  with trust_scope=rohit. The server policy table pins this scope to\n'
        '  local-only via maez_local_only.\n'
    )

    failures = 0
    for i, msg in enumerate(PATH_A_TURNS, 1):
        print()
        print(f'  --- turn {i}/{len(PATH_A_TURNS)} ---')
        body = {
            'message':           msg,
            'trust_scope':       'rohit.consumer_demo',
            'backend':           'auto',
            'max_tokens':        max_tokens,
            'temperature':       0.4,
            'timeout_s':         timeout_s,
            'history_load_n':    8,
            'persist_history':   True,
            'auto_load_history': True,
        }
        print_request('REQUEST BODY', body)
        status, parsed, latency_ms = post_json(url, body, timeout_s=timeout_s + 30.0)
        print_response(status, parsed, latency_ms)
        if status != 200 or not (isinstance(parsed, dict) and parsed.get('success')):
            failures += 1
    return failures


# ── path B — public-user shaped guest POST ────────────────────────────
#
# Intentional fake PII for the shaping/redactor demo. The "API key" below
# is a fake, clearly-labeled placeholder constructed at runtime by joining
# harmless fragments — the literal is split across string concatenation so
# secret scanners (GitHub push protection, gitleaks, trufflehog) do not see
# a contiguous Stripe-format string in source. At runtime the assembled
# value still looks like a real key to the redactor under test, which is
# exactly what this demo is trying to exercise.
_DEMO_FAKE_STRIPE_KEY = "sk_" + "test_" + "FAKE0DEMO0KEY0FOR0REDACTOR"
RAW_PUBLIC_MESSAGE = (
    "Hi Maez, my name is Sample User and you can email me at "
    "sample.user@example.com or call (555) 123-4567. My API key is "
    f"{_DEMO_FAKE_STRIPE_KEY} and my home dir is /home/sample/notes. "
    "Please reply with a short greeting."
)


def path_b_shaped_guest(url: str, timeout_s: float) -> int:
    banner("PATH B — public-user shaped guest POST")
    print(
        '  This path takes raw external input with intentional PII and runs it\n'
        '  through core.public_user_shaping.shape_public_request before posting.\n'
    )
    print()
    print('  RAW INPUT:')
    print(f'    {RAW_PUBLIC_MESSAGE!r}')

    try:
        shaped = shape_public_request(RAW_PUBLIC_MESSAGE)
    except ShapingRejected as e:
        print(f'  shaping rejected: code={e.code} message={e}')
        return 1

    server_body, telemetry = split_shaping_telemetry(shaped)
    print()
    print('  SHAPING TELEMETRY:')
    pretty = json.dumps(telemetry, indent=2)
    for line in pretty.splitlines():
        print(f'    {line}')
    print()
    print_request('SHAPED REQUEST BODY (sent to server)', server_body)

    # Bound the timeout passed to post_json to whatever the shaping enforced.
    server_timeout = float(server_body.get('timeout_s', timeout_s))
    status, parsed, latency_ms = post_json(url, server_body, timeout_s=server_timeout + 30.0)
    print_response(status, parsed, latency_ms)
    return 0 if (status == 200 and isinstance(parsed, dict) and parsed.get('success')) else 1


# ── path C — shaper rejects forbidden metadata ────────────────────────
def path_c_forbidden_metadata() -> int:
    banner("PATH C — public shaper rejects forbidden metadata (no HTTP call)")
    print(
        "  Demonstrates the metadata rejection path. The shaper raises\n"
        "  ShapingRejected before any HTTP call happens.\n"
    )
    bad = {'screen': {'activity': 'spoofed'}, 'history': [{'role': 'user', 'text': 'hi'}]}
    print(f'  raw_metadata = {bad!r}')
    try:
        shape_public_request("hello", raw_metadata=bad)
    except ShapingRejected as e:
        print(f'  ✓ rejected: code={e.code} message={e} details={e.details}')
        return 0
    print('  !! shaper did NOT reject — invariant broken')
    return 1


# ── service health probe ──────────────────────────────────────────────
def probe_service(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    health = f'{parsed.scheme}://{parsed.netloc}/healthz'
    try:
        with urllib.request.urlopen(health, timeout=2.0) as resp:
            if resp.status == 200:
                return True
    except Exception:
        return False
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default=DEFAULT_URL,
                    help=f'fast-reply service URL (default {DEFAULT_URL})')
    ap.add_argument('--max-tokens', type=int, default=2200,
                    help='max_tokens for path A turns (gemma4:26b needs >=2000 to be visible)')
    ap.add_argument('--timeout', type=float, default=180.0,
                    help='per-call backend timeout in seconds')
    ap.add_argument('--skip-a', action='store_true',
                    help='skip path A (direct rohit POST)')
    ap.add_argument('--skip-b', action='store_true',
                    help='skip path B (shaped guest POST)')
    args = ap.parse_args()

    print(f'consumer demo — target {args.url}')
    if not probe_service(args.url):
        print('  !! service unreachable; start it with `python scripts/fast_reply_service.py`')
        return 2
    print('  ✓ service /healthz returned ok')

    failures = 0
    if not args.skip_a:
        failures += path_a_direct_rohit(args.url, args.max_tokens, args.timeout)
    if not args.skip_b:
        failures += path_b_shaped_guest(args.url, args.timeout)
    failures += path_c_forbidden_metadata()

    print()
    print('=' * 78)
    if failures:
        print(f'  CONSUMER DEMO FAILED ({failures} failure(s))')
    else:
        print('  CONSUMER DEMO OK')
    print('=' * 78)
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
