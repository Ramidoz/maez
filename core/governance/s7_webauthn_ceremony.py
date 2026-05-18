# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S7.1 local WebAuthn ceremony service.

Daemon and cockpit routes are facades. This service is the shared producer that
will own challenges, credentials, refusal history, and artifacts as the S7.1
implementation fills in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore
from core.governance.s7_webauthn_verifier import S7ProductionWebAuthnVerifier


@dataclass(frozen=True)
class S7CeremonyServiceResult:
    body: dict[str, Any]
    status_code: int


StoreFactory = Callable[[], S7WebAuthnBootstrapStore]


@dataclass(frozen=True)
class S7LocalWebAuthnCeremonyService:
    """Core S7.1 ceremony service behind daemon and cockpit routes."""

    verifier: Any
    store_factory: StoreFactory

    def register_begin(
        self,
        *,
        now: str,
        request_json: dict[str, Any] | None,
    ) -> S7CeremonyServiceResult:
        del request_json
        dependency = self.verifier.dependency_state()
        if dependency.get("ok") is not True:
            return S7CeremonyServiceResult(body=dependency, status_code=503)
        store = self.store_factory()
        readiness = store.first_registration_readiness(now=now)
        if readiness.get("ok") is not True:
            status = 401 if readiness.get("error") == "s7_bootstrap_required" else 410
            return S7CeremonyServiceResult(body=readiness, status_code=status)
        return S7CeremonyServiceResult(
            body={
                "ok": False,
                "error": "s7_schema_invalid",
                "detail": "registration request schema not implemented yet",
            },
            status_code=400,
        )


def default_s7_webauthn_ceremony_service(
    *,
    store_factory: StoreFactory,
) -> S7LocalWebAuthnCeremonyService:
    return S7LocalWebAuthnCeremonyService(
        verifier=S7ProductionWebAuthnVerifier(),
        store_factory=store_factory,
    )
