"""Local-endpoint preflight for background digestion calls."""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from urllib.parse import urlparse

from core.routing.model_config import (
    BACKEND_LLAMACPP,
    BACKEND_OLLAMA,
    active_backend,
    llamacpp_base_url_from_env,
    primary_base_url_from_env,
)


@dataclass(frozen=True)
class DigestionEndpointLocality:
    allowed: bool
    backend: str
    endpoint: str
    refusal_code: str = ""
    reason: str = ""


def _ollama_endpoint_from_env() -> str:
    return (os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")


def resolve_active_backend_endpoint() -> tuple[str, str]:
    backend = active_backend()
    if backend == BACKEND_LLAMACPP:
        endpoint = llamacpp_base_url_from_env() or primary_base_url_from_env()
        return backend, endpoint.rstrip("/")
    if backend == BACKEND_OLLAMA:
        return backend, _ollama_endpoint_from_env()
    return backend, primary_base_url_from_env()


def _is_unix_socket_endpoint(endpoint: str) -> bool:
    parsed = urlparse(endpoint)
    if parsed.scheme in {"unix", "http+unix", "https+unix"}:
        return True
    return not parsed.scheme and endpoint.startswith("/") and endpoint.endswith(".sock")


def _is_loopback_endpoint(endpoint: str) -> bool:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname or ""
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _is_local_endpoint(endpoint: str) -> bool:
    return _is_unix_socket_endpoint(endpoint) or _is_loopback_endpoint(endpoint)


def check_digestion_endpoint_locality() -> DigestionEndpointLocality:
    backend, endpoint = resolve_active_backend_endpoint()
    if _is_local_endpoint(endpoint):
        return DigestionEndpointLocality(
            allowed=True,
            backend=backend,
            endpoint=endpoint,
        )
    return DigestionEndpointLocality(
        allowed=False,
        backend=backend,
        endpoint=endpoint,
        refusal_code="non_local_endpoint",
        reason=f"digestion endpoint is not local: {endpoint}",
    )
