# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Owner TTY ceremony for minting an S7.1 primary-key bootstrap intent.

This tool only creates the time-boxed permission-to-enroll that the existing
WebAuthn register-primary flow already requires. It does not touch founder
credentials, verify WebAuthn responses, consume intents, or bypass S7 gates.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from datetime import timezone
import os
from pathlib import Path
import sys

from core.governance.s7_webauthn_bootstrap import DEFAULT_BOOTSTRAP_TTL_MINUTES
from core.governance.s7_webauthn_bootstrap import DEFAULT_STORE_ROOT
from core.governance.s7_webauthn_bootstrap import MAX_BOOTSTRAP_TTL_MINUTES
from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore


CONFIRM_PHRASE = "mint s7 primary key"
DEFAULT_EXPIRES_MINUTES = DEFAULT_BOOTSTRAP_TTL_MINUTES


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-root", type=Path, default=DEFAULT_STORE_ROOT)
    parser.add_argument("--expires-min", type=int, default=DEFAULT_EXPIRES_MINUTES)
    parser.add_argument("--now", help=argparse.SUPPRESS)
    return parser


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stdin_tty_path() -> str:
    try:
        return os.ttyname(sys.stdin.fileno())
    except OSError:
        return "unknown-owner-tty"


def _clamped_expiry_minutes(requested: int) -> tuple[int, bool]:
    if requested <= 0:
        raise ValueError("expires-min must be positive")
    if requested > MAX_BOOTSTRAP_TTL_MINUTES:
        return MAX_BOOTSTRAP_TTL_MINUTES, True
    return requested, False


def _read_confirmation() -> str:
    print(
        f'Type "{CONFIRM_PHRASE}" to mint an S7 bootstrap intent: ',
        end="",
        file=sys.stderr,
        flush=True,
    )
    return sys.stdin.readline().strip()


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not sys.stdin.isatty():
        print("REFUSED: bootstrap intent minting requires an interactive owner TTY", file=sys.stderr)
        return 2
    typed = _read_confirmation()
    if typed != CONFIRM_PHRASE:
        print("aborted: phrase mismatch; no bootstrap intent minted", file=sys.stderr)
        return 2
    try:
        expires_min, clamped = _clamped_expiry_minutes(args.expires_min)
    except ValueError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    if clamped:
        print(
            f"NOTICE: --expires-min clamped to {MAX_BOOTSTRAP_TTL_MINUTES} minutes",
            file=sys.stderr,
        )

    store = S7WebAuthnBootstrapStore(args.store_root)
    now = args.now or _now_iso()
    try:
        intent = store.create_bootstrap_intent(
            purpose="register_primary",
            ttl_minutes=expires_min,
            now=now,
            is_interactive=True,
            tty_path=_stdin_tty_path(),
        )
    except (RuntimeError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    print("S7.1 primary-key bootstrap intent minted")
    print("Warning: bootstrap_token is a short-lived bearer secret for the cockpit channel-token gate.")
    print(f"intent_id: {intent.intent_id}")
    print(f"bootstrap_token: {intent.raw_token}")
    print(f"expires_at: {intent.expires_at}")
    print(
        "next_step: open cockpit Ceremony room -> register primary key "
        f"within {expires_min} minutes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
