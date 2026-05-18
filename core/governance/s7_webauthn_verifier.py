# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S7.1 WebAuthn verifier adapter.

The production adapter is deliberately isolated from the S7 test fake. It loads
py_webauthn lazily so a core install fails closed with a typed S7 error instead
of arming or crashing the ceremony.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.metadata
from pathlib import Path
from types import ModuleType
from typing import Callable


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


@dataclass(frozen=True)
class S7VirtualAuthenticatorHarness:
    """CI-only virtual-authenticator harness configuration.

    This is only a boundary guard for the later browser virtual-authenticator
    implementation. It refuses Maez's live ceremony store so tests cannot
    self-assemble authority against production memory.
    """

    store_root: Path | str

    def __post_init__(self) -> None:
        root = Path(self.store_root)
        if root == Path("memory/s7_1_webauthn") or root.as_posix().endswith(
            "/memory/s7_1_webauthn"
        ):
            raise ValueError("s7_virtual_authenticator_requires_isolated_store")
