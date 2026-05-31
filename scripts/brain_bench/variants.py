from __future__ import annotations

import hashlib
import ipaddress
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from scripts.brain_bench.bench_packet import (
    ApiFamily,
    GpuContention,
    OpsRubric,
    RestartRecovery,
    StartupHealth,
    Topology,
)


class VariantConfigError(ValueError):
    pass


class ConfigSource(str, Enum):
    ENV = "env"
    FILE = "file"
    INLINE = "inline"


@dataclass(frozen=True)
class Variant:
    label: str
    base_url: str
    model: str
    port: int
    chat_kwargs: dict[str, Any]
    ops_evidence: OpsRubric
    draft_model: str | None = None


@dataclass(frozen=True)
class VariantRegistry:
    variants: tuple[Variant, ...]
    variant_config_source: ConfigSource
    variant_config_hash: str

    def __iter__(self):
        return iter(self.variants)

    def __len__(self) -> int:
        return len(self.variants)

    def __getitem__(self, index: int) -> Variant:
        return self.variants[index]


def _coerce_source(source: ConfigSource | str) -> ConfigSource:
    try:
        return source if isinstance(source, ConfigSource) else ConfigSource(source)
    except ValueError as exc:
        raise VariantConfigError(f"unsupported variant config source: {source}") from exc


def _canonical_hash(parsed: Any) -> str:
    blob = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _loopback_host(host: str | None) -> bool:
    if host is None:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _normalized_endpoint(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    if parsed.scheme != "http":
        raise VariantConfigError("endpoint must use http")
    if parsed.username or parsed.password:
        raise VariantConfigError("endpoint must not include userinfo")
    if not _loopback_host(parsed.hostname):
        raise VariantConfigError("endpoint must be loopback")
    if parsed.port is None:
        raise VariantConfigError("endpoint must include an explicit port")
    if parsed.query or parsed.fragment:
        raise VariantConfigError("endpoint must not include query or fragment")
    if parsed.path not in ("", "/"):
        raise VariantConfigError("endpoint must be pathless; /api/chat is pinned by code")

    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}:{parsed.port}", parsed.port


def _coerce_ops(raw_ops: Any) -> OpsRubric:
    if not isinstance(raw_ops, dict):
        raise VariantConfigError("variant ops evidence is required")
    try:
        return OpsRubric(
            api_family=ApiFamily(raw_ops.get("api_family")),
            topology=Topology(raw_ops.get("topology")),
            bind_host_verified=raw_ops.get("bind_host_verified"),
            live_daemon_disturbance=raw_ops.get("live_daemon_disturbance"),
            gpu_contention=GpuContention(raw_ops.get("gpu_contention")),
            startup_health=StartupHealth(raw_ops.get("startup_health")),
            streaming_support=raw_ops.get("streaming_support"),
            restart_recovery=RestartRecovery(raw_ops.get("restart_recovery")),
        )
    except (TypeError, ValueError) as exc:
        raise VariantConfigError("variant ops evidence must use closed values") from exc


def validate_endpoint(url: str) -> int:
    _normalized, port = _normalized_endpoint(url)
    return port


def resolve_judge_endpoint(url: str = "http://127.0.0.1:8081") -> int:
    return validate_endpoint(url)


def load_variants(
    raw_config: str | None,
    *,
    source: ConfigSource | str = ConfigSource.INLINE,
) -> VariantRegistry:
    config_source = _coerce_source(source)
    if not raw_config:
        raise VariantConfigError("variant config is required")
    try:
        parsed = json.loads(raw_config)
    except json.JSONDecodeError as exc:
        raise VariantConfigError("variant config must be valid JSON") from exc
    if not isinstance(parsed, list) or not parsed:
        raise VariantConfigError("variant config must be a non-empty list")

    labels: set[str] = set()
    variants: list[Variant] = []
    for item in parsed:
        if not isinstance(item, dict):
            raise VariantConfigError("variant entries must be objects")
        label = item.get("label")
        base_url = item.get("base_url")
        model = item.get("model")
        if not isinstance(label, str) or not label:
            raise VariantConfigError("variant label is required")
        if label in labels:
            raise VariantConfigError(f"duplicate variant label: {label}")
        if not isinstance(base_url, str) or not base_url:
            raise VariantConfigError("variant base_url is required")
        if not isinstance(model, str) or not model:
            raise VariantConfigError("variant model is required")
        chat_kwargs = item.get("chat_kwargs", {})
        if not isinstance(chat_kwargs, dict):
            raise VariantConfigError("variant chat_kwargs must be an object")
        draft_model = item.get("draft_model")
        if draft_model is not None and not isinstance(draft_model, str):
            raise VariantConfigError("variant draft_model must be a string")
        ops_evidence = _coerce_ops(item.get("ops"))

        normalized, port = _normalized_endpoint(base_url)
        labels.add(label)
        variants.append(
            Variant(
                label=label,
                base_url=normalized,
                model=model,
                port=port,
                chat_kwargs=dict(chat_kwargs),
                ops_evidence=ops_evidence,
                draft_model=draft_model,
            )
        )

    return VariantRegistry(
        variants=tuple(variants),
        variant_config_source=config_source,
        variant_config_hash=_canonical_hash(parsed),
    )
