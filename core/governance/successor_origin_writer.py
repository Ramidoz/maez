# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Human-origin marker minting seam for S6.

Daemon, sidecar, health, and validators must not import this module. Keeping the
writer separate preserves S6's unmintable-by-runtime boundary.
"""

from __future__ import annotations

from core.governance.successor_governance import (
    HumanOriginMarker,
    _MARKER_CONSTRUCTION_TOKEN,
    _expected_marker_id,
    utc_now_iso,
)


def mint_origin_marker(
    *,
    origin: str,
    role_name: str,
    actor_handle_hmac: str,
    capsule_id: str,
    directive_event_type: str,
    directive_payload_hash: str,
    previous_capsule_event_hash: str = "",
    directive_statement_hash: str = "",
    attestation_text_hash: str = "",
    is_tty: bool = True,
) -> HumanOriginMarker:
    if origin.endswith("_cli_tty") and not is_tty:
        raise ValueError("S6 cli_tty origin requires interactive TTY")
    return HumanOriginMarker(
        marker_id=_expected_marker_id(
            origin=origin,
            role_name=role_name,
            actor_handle_hmac=actor_handle_hmac,
            capsule_id=capsule_id,
            directive_event_type=directive_event_type,
            directive_payload_hash=directive_payload_hash,
            previous_capsule_event_hash=previous_capsule_event_hash,
            directive_statement_hash=directive_statement_hash,
            attestation_text_hash=attestation_text_hash,
        ),
        origin=origin,
        role_name=role_name,
        actor_handle_hmac=actor_handle_hmac,
        capsule_id=capsule_id,
        directive_event_type=directive_event_type,
        directive_payload_hash=directive_payload_hash,
        directive_statement_hash=directive_statement_hash,
        previous_capsule_event_hash=previous_capsule_event_hash,
        schema_version="s6.v1",
        created_at=utc_now_iso(),
        attestation_text_hash=attestation_text_hash,
        construction_token=_MARKER_CONSTRUCTION_TOKEN,
    )
