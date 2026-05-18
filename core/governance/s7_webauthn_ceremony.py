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

from core.governance.operator_user_boundary import live_webauthn_ceremony_enabled
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

    def status(self, *, now: str) -> S7CeremonyServiceResult:
        dependency = self.verifier.dependency_state()
        dependency_state = "available" if dependency.get("ok") is True else "missing"
        dependency_version = dependency.get("library_version")
        store = self.store_factory()
        recovery = store.credential_recovery_state()
        try:
            bootstrap_state = store.bootstrap_state(now=now)
        except Exception:
            bootstrap_state = "unavailable"
        mode = str(recovery["mode"])
        body = {
            "ok": True,
            "ceremony_mode": mode,
            "live_flag_enabled": live_webauthn_ceremony_enabled(),
            "verifier_dependency_state": dependency_state,
            "verifier_dependency_version": dependency_version,
            "bootstrap_state": bootstrap_state,
            "primary_credential_state": recovery["primary_credential_state"],
            "backup_credential_state": recovery["backup_credential_state"],
            "active_credential_count": recovery["active_credential_count"],
            "manual_recovery_required": recovery["manual_recovery_required"],
            "manual_recovery_cause": recovery["manual_recovery_cause"],
            "single_active_credential_warning": recovery["active_credential_count"] == 1,
            "distinct_device_confidence": recovery["distinct_device_confidence"],
            "uv_policy_state": "pending",
            "clone_detection_state": "pending",
            "witnessed_social_recovery_state": "deferred_l9",
            "internal_channel_state": "configured",
            "last_registration_class": None,
            "last_authorization_class": None,
            "last_error_code": None if dependency.get("ok") is True else dependency.get("error"),
        }
        return S7CeremonyServiceResult(body=body, status_code=200)


def default_s7_webauthn_ceremony_service(
    *,
    store_factory: StoreFactory,
) -> S7LocalWebAuthnCeremonyService:
    return S7LocalWebAuthnCeremonyService(
        verifier=S7ProductionWebAuthnVerifier(),
        store_factory=store_factory,
    )
