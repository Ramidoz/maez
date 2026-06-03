# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Decision 26 credential loader.

Secrets are identity-bearing material. This module keeps them out of Maez's
initial process environment while preserving v1 compatibility for existing
``os.environ.get(...)`` readers after Python has started.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
from typing import Iterable, Mapping

from core.infra import paths


SECRET_NAMES: frozenset[str] = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "CLOUDFLARE_API_TOKEN",
        "LANGFUSE_SECRET_KEY",
        "MAEZ_DEV_TOKEN",
        "MAEZ_GITHUB_TOKEN",
        "MAEZ_IPHONE_INGEST_TOKEN",
        "MAEZ_PUBLIC_TELEGRAM_TOKEN",
        "MAEZ_REDDIT_HANDOFF_TOKEN",
        "MAEZ_TELEGRAM_TOKEN",
        "OLLAMA_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "TELEGRAM_WEBHOOK_SECRET",
        "XAI_API_KEY",
    }
)

_SECRET_NAME_MARKERS: tuple[str, ...] = (
    "TOKEN",
    "API_KEY",
    "SECRET",
    "PASSWORD",
    "CREDENTIAL",
)

_ENV_LINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

_TELEGRAM_TOKEN_RE = re.compile(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b")
_SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b[A-Z0-9_]*(?:TOKEN|API_KEY|SECRET|PASSWORD|CREDENTIAL)\s*=\s*[^ \n\r\t]+"
    ),
    re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxoxb-[A-Za-z0-9-]{20,}\b"),
    _TELEGRAM_TOKEN_RE,
)
_ALLOWED_FAKE_FIXTURES: frozenset[str] = frozenset({"sk-lf-test"})


class SecretLoadError(RuntimeError):
    """Raised when credential startup validation fails."""


@dataclass(frozen=True)
class SecretLoadReport:
    """Value-free startup report with private in-process secret storage."""

    source: str
    required_present: bool
    loaded_count: int
    optional_loaded_count: int
    missing_required_count: int
    missing_optional_count: int
    rollback_enabled: bool = False
    _secrets: Mapping[str, str] = field(default_factory=dict, repr=False)

    def get_secret(self, name: str) -> str | None:
        value = self._secrets.get(name)
        return value if value else None

    def health(self) -> dict:
        return {
            "source": self.source,
            "required_present": self.required_present,
            "optional_loaded_count": self.optional_loaded_count,
            "missing_required_count": self.missing_required_count,
            "rollback_enabled": self.rollback_enabled,
        }

    def source_log_line(self) -> str:
        if self.rollback_enabled:
            return (
                "credential source: legacy-env "
                "(rollback; process-env exposure temporarily reaccepted)"
            )
        return f"credential source: {self.source}"


_LAST_REPORT = SecretLoadReport(
    source="none",
    required_present=True,
    loaded_count=0,
    optional_loaded_count=0,
    missing_required_count=0,
    missing_optional_count=0,
)


def is_secret_name(name: str) -> bool:
    upper = name.upper()
    return upper in SECRET_NAMES or any(marker in upper for marker in _SECRET_NAME_MARKERS)


def _strip_env_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_env_file(path: Path, *, allowed_names: set[str] | None = None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ENV_LINE.match(stripped)
        if not match:
            raise SecretLoadError(f"malformed credential line at {path.name}:{lineno}")
        name, raw_value = match.groups()
        if allowed_names is not None and name not in allowed_names:
            continue
        if name in out:
            raise SecretLoadError(f"duplicate credential entry: {name}")
        out[name] = _strip_env_value(raw_value)
    return out


def load_ordinary_config_for_process(
    *,
    env_file: Path | None = None,
    environ: dict[str, str] | None = None,
) -> set[str]:
    """Load non-secret config from ``config/.env`` into the current process."""

    target = environ if environ is not None else os.environ
    source = env_file or paths.env_file()
    loaded: set[str] = set()
    for name, value in _parse_env_file(source).items():
        if is_secret_name(name):
            continue
        if name not in target:
            target[name] = value
            loaded.add(name)
    return loaded


def _read_systemd_credentials(credentials_dir: Path, names: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    if not credentials_dir.exists() or not credentials_dir.is_dir():
        return out
    for name in names:
        path = credentials_dir / name
        if not path.is_file():
            continue
        value = path.read_text(encoding="utf-8").strip()
        if value:
            out[name] = value
    return out


def _build_report(
    *,
    required: set[str],
    optional: set[str],
    secrets: dict[str, str],
    source: str,
    rollback_enabled: bool,
) -> SecretLoadReport:
    missing_required = sorted(name for name in required if not secrets.get(name))
    if missing_required:
        raise SecretLoadError(
            "missing required credential(s): " + ", ".join(missing_required)
        )
    optional_loaded = sum(1 for name in optional if secrets.get(name))
    return SecretLoadReport(
        source=source,
        required_present=True,
        loaded_count=len(secrets),
        optional_loaded_count=optional_loaded,
        missing_required_count=0,
        missing_optional_count=sum(1 for name in optional if not secrets.get(name)),
        rollback_enabled=rollback_enabled,
        _secrets=dict(secrets),
    )


def _purge_secret_environ(target: dict[str, str], *, keep: set[str]) -> None:
    for name in list(target):
        if is_secret_name(name) and name not in keep:
            target.pop(name, None)


def load_secrets_for_process(
    *,
    required: set[str],
    optional: set[str],
    fallback_file: Path | None = None,
    credentials_dir: Path | None = None,
    populate_environ: bool = True,
    environ: dict[str, str] | None = None,
) -> SecretLoadReport:
    """Load Maez credentials from systemd credentials and local fallback.

    ``config/.env`` is intentionally not a source here.
    """

    global _LAST_REPORT
    target = environ if environ is not None else os.environ
    names = set(required) | set(optional)

    if target.get("MAEZ_SECRETS_DISABLE_NEW_LOADER") == "1":
        legacy_file = paths.env_file()
        secrets = _parse_env_file(legacy_file, allowed_names=names)
        secrets = {k: v for k, v in secrets.items() if v}
        secrets.update({name: target[name] for name in names if target.get(name)})
        report = _build_report(
            required=required,
            optional=optional,
            secrets=secrets,
            source="legacy-env",
            rollback_enabled=True,
        )
        if populate_environ:
            for name, value in secrets.items():
                target[name] = value
        _LAST_REPORT = report
        return report

    credential_root = credentials_dir
    raw_credential_root = target.get("CREDENTIALS_DIRECTORY")
    if credential_root is None and raw_credential_root:
        credential_root = Path(raw_credential_root)

    from_systemd: dict[str, str] = {}
    if credential_root is not None:
        from_systemd = _read_systemd_credentials(Path(credential_root), names)

    local_file = fallback_file or (paths.config_dir() / "secrets.local.env")
    from_local = _parse_env_file(local_file, allowed_names=names)
    for name in required:
        if name in from_local and from_local[name] == "":
            raise SecretLoadError(f"empty required credential: {name}")
    from_local = {k: v for k, v in from_local.items() if v}

    secrets = dict(from_local)
    secrets.update(from_systemd)

    if from_systemd and from_local:
        source = "mixed"
    elif from_systemd:
        source = "systemd-credentials"
    elif from_local:
        source = "secrets-local-env"
    else:
        source = "none"

    report = _build_report(
        required=required,
        optional=optional,
        secrets=secrets,
        source=source,
        rollback_enabled=False,
    )
    if populate_environ:
        _purge_secret_environ(target, keep=set(secrets))
        for name, value in secrets.items():
            target[name] = value
    _LAST_REPORT = report
    return report


def get_secret(name: str) -> str | None:
    if _LAST_REPORT.rollback_enabled:
        return _LAST_REPORT.get_secret(name) or os.environ.get(name)
    return _LAST_REPORT.get_secret(name)


def credential_health() -> dict:
    return _LAST_REPORT.health()


def sanitize_env(
    base: Mapping[str, str] | None = None,
    *,
    allow: Iterable[str] = (),
    strict: bool = False,
) -> dict[str, str]:
    """Return a child-process environment with secrets removed by default."""

    source = dict(base if base is not None else os.environ)
    allowed = set(allow)
    if strict:
        return {name: value for name, value in source.items() if name in allowed}
    return {
        name: value
        for name, value in source.items()
        if not is_secret_name(name) or name in allowed
    }


def find_secret_pattern_hits(text: str) -> list[str]:
    hits: list[str] = []
    if text.strip() in _ALLOWED_FAKE_FIXTURES:
        return []
    for pattern in _SECRET_VALUE_PATTERNS:
        hits.extend(match.group(0) for match in pattern.finditer(text))
    return hits


__all__ = [
    "SECRET_NAMES",
    "SecretLoadError",
    "SecretLoadReport",
    "credential_health",
    "find_secret_pattern_hits",
    "get_secret",
    "is_secret_name",
    "load_ordinary_config_for_process",
    "load_secrets_for_process",
    "sanitize_env",
]
