#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""OWNER-RUN. Mint the enforceable cutover authorization.

The document the ceremony consumes: a named window, a fresh nonce, this
boot's id, the closed action set, the staged recovery identity and the
bench parent. It is time-boxed to exactly four hours and bound to the
current boot, so it is minted SHORTLY BEFORE the ceremony and cannot
survive a restart.

    python3 -m scripts.s7_mint_cutover_authorization

Minting writes one file and changes nothing else. It refuses if an
authorization already exists -- a second one would leave two live windows
with no statement of which the ceremony consumes -- and it refuses if the
staged recovery copies do not match the frozen Vulkan identity, because
the authorization binds the rollback you would fall back to.

After minting, run the preflight. It reports the window and the minutes
remaining, so the ceremony is entered with the clock visible rather than
assumed.
"""

from __future__ import annotations

import sys


def main() -> int:
    from scripts import cuda_cutover

    target = cuda_cutover.BENCH_ROOT / cuda_cutover.AUTHORIZATION_NAME
    if target.exists():
        print(f"an authorization already exists: {target}")
        print(
            "Refusing to mint a second. Check it with the preflight; if it is "
            "expired or stale-boot, move it aside deliberately and re-mint."
        )
        return 1

    print("minting cutover authorization")
    print(f"  into: {target}")
    try:
        doc = cuda_cutover.mint_cutover_authorization()
    except cuda_cutover.CutoverRefusal as exc:
        # Content-light by design: the refusal code is the message.
        print(f"\nREFUSED: {exc}")
        if str(exc) == "recovery_copies_mismatch":
            print(
                "The staged recovery copies do not match the frozen Vulkan "
                "identity. The authorization binds the rollback you would fall "
                "back to, so it will not bind one it cannot verify."
            )
        return 1
    except Exception as exc:
        print(f"\nFAILED: {type(exc).__name__}: {exc}")
        return 1

    print("\nminted:")
    print(f"  window   {doc.window_id}")
    print(f"  valid    {doc.issued_at} -> {doc.expires_at}  (4h)")
    print(f"  boot     {doc.boot_id}")
    print(f"  actions  {', '.join(doc.actions)}")
    print("\nNow run:  python3 -m scripts.s7_r11_preflight")
    print(
        "The ceremony's final operation is a HOST REBOOT. Be at the machine "
        "before you start it."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
