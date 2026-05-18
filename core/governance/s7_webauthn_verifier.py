# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S7.1 WebAuthn verifier adapter.

The production adapter is deliberately isolated from the S7 test fake. It loads
py_webauthn lazily so a core install fails closed with a typed S7 error instead
of arming or crashing the ceremony.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import importlib
import importlib.metadata
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


ImportModule = Callable[[str], ModuleType]


@dataclass(frozen=True)
class S7ProductionWebAuthnVerifier:
    """Lazy py_webauthn adapter for production registration/authentication."""

    import_module: ImportModule = importlib.import_module
    package_name: str = "webauthn"

    def _load(self) -> ModuleType | None:
        try:
            return self.import_module(self.package_name)
        except ModuleNotFoundError:
            return None

    def dependency_state(self) -> dict[str, str | bool | None]:
        module = self._load()
        if module is None:
            return {
                "ok": False,
                "error": "s7_webauthn_dependency_missing",
                "library_name": self.package_name,
                "library_version": None,
            }
        try:
            version = importlib.metadata.version(self.package_name)
        except importlib.metadata.PackageNotFoundError:
            version = getattr(module, "__version__", None)
        return {
            "ok": True,
            "library_name": self.package_name,
            "library_version": version,
        }

    def verify_registration_response(
        self,
        *,
        registration_response: dict[str, Any],
        challenge: dict[str, Any],
        expected_origin: str,
        expected_rp_id: str,
        require_user_verification: bool,
    ) -> dict[str, Any]:
        module = self._load()
        if module is None:
            return {
                "ok": False,
                "error": "s7_webauthn_dependency_missing",
                "library_name": self.package_name,
                "library_version": None,
            }
        try:
            verified = module.verify_registration_response(
                credential=registration_response,
                expected_challenge=_b64url_decode(str(challenge["challenge_b64"])),
                expected_rp_id=expected_rp_id,
                expected_origin=expected_origin,
                require_user_verification=require_user_verification,
            )
        except Exception as exc:
            return {
                "ok": False,
                "error": "s7_registration_invalid",
                "detail": exc.__class__.__name__,
            }
        return {
            "ok": True,
            "credential_ref": _b64url_encode(verified.credential_id),
            "public_key": _b64url_encode(verified.credential_public_key),
            "sign_count": int(verified.sign_count),
            "attestation_format": _enum_value(verified.fmt),
            "aaguid": str(verified.aaguid) if verified.aaguid is not None else None,
            "authenticator_attachment": None,
            "backup_eligible": _enum_value(verified.credential_device_type) == "multi_device",
            "backed_up": bool(verified.credential_backed_up),
            "transports": (),
            "library_name": self.package_name,
            "library_version": self.dependency_state().get("library_version"),
            "sign_count_mode": "constant_zero" if int(verified.sign_count) == 0 else "advancing",
            "uv_capable": bool(verified.user_verified),
        }

    def verify_authentication_response(
        self,
        *,
        authentication_response: dict[str, Any],
        challenge: dict[str, Any],
        credential_public_key: str,
        current_sign_count: int,
        expected_origin: str,
        expected_rp_id: str,
        require_user_verification: bool,
    ) -> dict[str, Any]:
        module = self._load()
        if module is None:
            return {
                "ok": False,
                "error": "s7_webauthn_dependency_missing",
                "library_name": self.package_name,
                "library_version": None,
            }
        try:
            verified = module.verify_authentication_response(
                credential=authentication_response,
                expected_challenge=_b64url_decode(str(challenge["challenge_b64"])),
                expected_rp_id=expected_rp_id,
                expected_origin=expected_origin,
                credential_public_key=_b64url_decode(credential_public_key),
                credential_current_sign_count=int(current_sign_count),
                require_user_verification=require_user_verification,
            )
        except Exception as exc:
            return {
                "ok": False,
                "error": "s7_authentication_invalid",
                "detail": exc.__class__.__name__,
            }
        sign_count = getattr(verified, "new_sign_count", getattr(verified, "sign_count", 0))
        return {
            "ok": True,
            "credential_ref": _b64url_encode(verified.credential_id),
            "sign_count": int(sign_count),
            "user_presence": True,
            "user_verification": bool(verified.user_verified),
            "library_name": self.package_name,
            "library_version": self.dependency_state().get("library_version"),
        }


@dataclass(frozen=True)
class S7VirtualAuthenticatorHarness:
    """CI-only virtual-authenticator harness configuration.

    This is only a boundary guard for the later browser virtual-authenticator
    implementation. It refuses Maez's live ceremony store and production
    origin/RP so tests cannot self-assemble authority against production memory
    or the real cockpit.
    """

    store_root: Path | str
    origin: str | None = None
    rp_id: str | None = None
    remote_debugging_enabled: bool = False

    def __post_init__(self) -> None:
        root = Path(self.store_root)
        if root == Path("memory/s7_1_webauthn") or root.as_posix().endswith(
            "/memory/s7_1_webauthn"
        ):
            raise ValueError("s7_virtual_authenticator_requires_isolated_store")
        if not self.origin or not self.rp_id:
            raise ValueError("s7_virtual_authenticator_requires_test_origin")
        if self.origin == "http://localhost:11437" or self.rp_id == "localhost":
            raise ValueError(
                "s7_virtual_authenticator_must_not_target_production_cockpit"
            )
        if not self.remote_debugging_enabled:
            raise ValueError("s7_virtual_authenticator_requires_test_automation_channel")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _enum_value(value: Any) -> str:
    enum_value = getattr(value, "value", value)
    return str(enum_value)
