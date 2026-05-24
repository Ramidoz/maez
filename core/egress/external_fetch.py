from __future__ import annotations

import asyncio
import hmac
import hashlib
import ipaddress
import json
import math
import os
import socket
import time
import uuid
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from core.egress.gate import load_or_create_telemetry_key
from core.egress.provenance import ProvenancedText


USER_AGENT = "MaezExternalFetch/1.0"
SCHEMA_VERSION = "external-fetch-diagnostic-v1"

PUBLIC_LOOKUP = "public_lookup"
UNKNOWN_URL_FETCH = "unknown_url_fetch"
RESERVED_THREAT_CLASSES = {
    "weather_lookup",
    "owner_private_api",
    "untrusted_model_output_fetch",
}
THREAT_MODEL_CLASSES = {
    PUBLIC_LOOKUP,
    UNKNOWN_URL_FETCH,
    *RESERVED_THREAT_CLASSES,
}
FORBIDDEN_REQUEST_HEADERS = {
    "accept-language",
    "authorization",
    "cookie",
    "proxy-authorization",
    "user-agent",
}
_RESERVED_IPV4_NETWORKS = (
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("240.0.0.0/4"),
)
_ZERO_IPV4_NETWORK = ipaddress.ip_network("0.0.0.0/8")
_MAX_REDIRECTS = 5


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        return None


class _NoHttpErrorProcessor(urllib.request.HTTPErrorProcessor):
    def http_response(self, request, response):  # noqa: N802
        return response

    https_response = http_response


_DEFAULT_OPENER = urllib.request.build_opener(
    _NoRedirectHandler,
    _NoHttpErrorProcessor,
)


@dataclass(frozen=True)
class FetchTypeEntry:
    fetch_type: str
    threat_model_class: str
    result_origin_class: str
    enforcement_posture: str
    spec_extension_acknowledged: str | None = None


class FetchRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, FetchTypeEntry] = {}

    def register_fetch_type(
        self,
        fetch_type: str,
        *,
        threat_model_class: str,
        result_origin_class: str,
        enforcement_posture: str = "substrate_shadow",
        spec_extension_acknowledged: str | None = None,
    ) -> FetchTypeEntry:
        if threat_model_class not in THREAT_MODEL_CLASSES:
            raise ValueError(f"unknown threat_model_class: {threat_model_class}")
        if threat_model_class in RESERVED_THREAT_CLASSES:
            if not isinstance(spec_extension_acknowledged, str) or not spec_extension_acknowledged.strip():
                raise ValueError(
                    f"reserved threat_model_class {threat_model_class!r} requires "
                    "spec_extension_acknowledged"
                )
        entry = FetchTypeEntry(
            fetch_type=str(fetch_type),
            threat_model_class=threat_model_class,
            result_origin_class=result_origin_class,
            enforcement_posture=enforcement_posture,
            spec_extension_acknowledged=spec_extension_acknowledged,
        )
        self._entries[entry.fetch_type] = entry
        return entry

    def require_fetch_type(self, fetch_type: str) -> FetchTypeEntry:
        try:
            return self._entries[fetch_type]
        except KeyError as exc:
            raise ValueError(f"unknown fetch_type: {fetch_type}") from exc

    def reserved_instance_count(self) -> int:
        return sum(
            1
            for entry in self._entries.values()
            if entry.threat_model_class in RESERVED_THREAT_CLASSES
        )

    def entries(self) -> tuple[FetchTypeEntry, ...]:
        return tuple(self._entries.values())


def build_fetch_registry() -> FetchRegistry:
    registry = FetchRegistry()
    registry.register_fetch_type(
        "web_search",
        threat_model_class=PUBLIC_LOOKUP,
        result_origin_class="tool_result_public",
    )
    registry.register_fetch_type(
        "search_rss",
        threat_model_class=PUBLIC_LOOKUP,
        result_origin_class="tool_result_public",
    )
    registry.register_fetch_type(
        "fetch_url",
        threat_model_class=UNKNOWN_URL_FETCH,
        result_origin_class="unclassified",
    )
    registry.register_fetch_type(
        "currency_lookup",
        threat_model_class=PUBLIC_LOOKUP,
        result_origin_class="tool_result_public",
    )
    registry.register_fetch_type(
        "stock_lookup",
        threat_model_class=PUBLIC_LOOKUP,
        result_origin_class="tool_result_public",
    )
    return registry


@dataclass(frozen=True)
class ExternalFetchResult:
    ok: bool
    text: str = ""
    fetch_type: str = "unknown"
    threat_model_class: str = "unknown"
    result_origin_class: str = "unclassified"
    decision: str = "block"
    reason_codes: tuple[str, ...] = ()
    status_code: int | None = None
    request_id: str = ""
    preflight_status: str = "not_run"
    preflight_refusal_kind: str | None = None
    response_bytes: int = 0

    def to_provenanced_text(self, *, source_ref: str | None = None) -> ProvenancedText:
        ref = source_ref or f"external_fetch:{self.fetch_type}:{self.request_id}"
        if self.result_origin_class == "tool_result_public":
            return ProvenancedText.tool_result_public(self.text, source_ref=ref)
        return ProvenancedText.from_raw_conservative(self.text, source_ref=ref)


@dataclass(frozen=True)
class _PreflightResult:
    ok: bool
    url: str
    host: str = ""
    query: str = ""
    status: str = "allowed"
    refusal_kind: str | None = None


def _hmac_digest(value: bytes | str) -> str:
    raw = value.encode("utf-8", errors="replace") if isinstance(value, str) else value
    key = load_or_create_telemetry_key()
    return "hmac-sha256:" + hmac.new(key, raw, hashlib.sha256).hexdigest()


def _diagnostic_path() -> Path:
    return Path(os.environ.get("MAEZ_EXTERNAL_FETCH_LOG", "logs/external_fetch_diagnostics.jsonl"))


def _write_diagnostic(
    *,
    result: ExternalFetchResult,
    caller: str,
    url: str,
    query: str = "",
    host: str = "",
) -> None:
    row = {
        "schema_version": SCHEMA_VERSION,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "request_id": result.request_id,
        "caller": caller,
        "fetch_type": result.fetch_type,
        "threat_model_class": result.threat_model_class,
        "result_origin_class": result.result_origin_class,
        "enforcement_posture": "substrate_shadow",
        "decision": result.decision,
        "reason_codes": list(result.reason_codes),
        "destination_host_digest": _hmac_digest(host or ""),
        "url_digest": _hmac_digest(url or ""),
        "query_digest": _hmac_digest(query or ""),
        "response_digest": _hmac_digest(result.text.encode("utf-8", errors="replace")),
        "status_code": result.status_code,
        "request_bytes": 0,
        "response_bytes": result.response_bytes,
        "preflight_status": result.preflight_status,
        "preflight_refusal_kind": result.preflight_refusal_kind,
    }
    path = _diagnostic_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _result(
    *,
    entry: FetchTypeEntry,
    ok: bool,
    text: str = "",
    decision: str,
    reason_codes: tuple[str, ...],
    request_id: str,
    status_code: int | None = None,
    preflight_status: str = "allowed",
    preflight_refusal_kind: str | None = None,
) -> ExternalFetchResult:
    return ExternalFetchResult(
        ok=ok,
        text=text,
        fetch_type=entry.fetch_type,
        threat_model_class=entry.threat_model_class,
        result_origin_class=entry.result_origin_class,
        decision=decision,
        reason_codes=reason_codes,
        status_code=status_code,
        request_id=request_id,
        preflight_status=preflight_status,
        preflight_refusal_kind=preflight_refusal_kind,
        response_bytes=len(text.encode("utf-8", errors="replace")),
    )


def _normalize_ip(value: str) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, bool]:
    ip = ipaddress.ip_address(value)
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return mapped, True
    return ip, False


def _classify_ip(value: str) -> str | None:
    try:
        ip, was_mapped = _normalize_ip(value)
    except ValueError:
        return "preflight_refused_dns_resolution"
    if was_mapped and (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip in _ZERO_IPV4_NETWORK
    ):
        return "preflight_refused_ipv4_mapped_ipv6"
    if ip.is_loopback or ip.is_unspecified or ip in _ZERO_IPV4_NETWORK:
        return "preflight_refused_loopback"
    if isinstance(ip, ipaddress.IPv4Address) and ip == ipaddress.ip_address("255.255.255.255"):
        return "preflight_refused_reserved_range"
    if ip in ipaddress.ip_network("fc00::/7") or any(ip in network for network in _RESERVED_IPV4_NETWORKS):
        return "preflight_refused_reserved_range"
    if ip.is_link_local:
        return "preflight_refused_link_local"
    if ip.is_private:
        return "preflight_refused_private_range"
    return None


def _default_resolver(host: str) -> list[str]:
    answers = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return sorted({str(item[4][0]) for item in answers})


def _resolve_and_validate(
    host: str,
    resolver: Callable[[str], Iterable[str]] | None,
) -> str | None:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        direct_literal = False
        answers = list((resolver or _default_resolver)(host))
    else:
        direct_literal = True
        answers = [host]
    if not answers:
        return "preflight_refused_dns_resolution"
    for answer in answers:
        refusal = _classify_ip(str(answer))
        if refusal:
            if direct_literal or refusal == "preflight_refused_ipv4_mapped_ipv6":
                return refusal
            return "preflight_refused_dns_resolution"
    return None


def _preflight_url(
    url: str,
    *,
    resolver: Callable[[str], Iterable[str]] | None,
) -> _PreflightResult:
    if not url or not str(url).strip():
        return _PreflightResult(False, str(url or ""), status="refused", refusal_kind="preflight_refused_empty_url")
    parsed = urllib.parse.urlsplit(str(url).strip())
    if parsed.scheme not in {"http", "https"}:
        return _PreflightResult(False, str(url), status="refused", refusal_kind="preflight_refused_scheme")
    if parsed.username or parsed.password:
        return _PreflightResult(False, str(url), status="refused", refusal_kind="preflight_refused_credentials")
    if not parsed.hostname:
        return _PreflightResult(False, str(url), status="refused", refusal_kind="preflight_refused_empty_url")
    if parsed.hostname.lower().rstrip(".") == "localhost":
        return _PreflightResult(False, str(url), host=parsed.hostname, query=parsed.query, status="refused", refusal_kind="preflight_refused_loopback")
    refusal = _resolve_and_validate(parsed.hostname, resolver)
    if refusal:
        return _PreflightResult(False, str(url), host=parsed.hostname, query=parsed.query, status="refused", refusal_kind=refusal)
    return _PreflightResult(True, str(url), host=parsed.hostname, query=parsed.query)


def _validate_timeout(timeout_s: float | int | None) -> bool:
    if timeout_s is None:
        return False
    try:
        value = float(timeout_s)
    except (TypeError, ValueError):
        return False
    return value > 0 and math.isfinite(value)


def _request_headers(headers: dict[str, str] | None) -> dict[str, str]:
    sanitized = {"User-Agent": USER_AGENT}
    for name, value in (headers or {}).items():
        lower = str(name).lower()
        if lower in FORBIDDEN_REQUEST_HEADERS or lower.startswith("x-forwarded-"):
            continue
        # v1 is deny-by-default. Future classes can add explicit allowlists.
        _ = value
    return sanitized


def _read_response_body(response: object, max_bytes: int) -> bytes:
    reader = getattr(response, "read")
    try:
        return reader(max_bytes)
    except TypeError:
        return reader()


def _response_status(response: object) -> int | None:
    return response.getcode() if hasattr(response, "getcode") else getattr(response, "status", None)


def _response_header(response: object, name: str) -> str | None:
    if hasattr(response, "getheader"):
        value = response.getheader(name)
        return str(value) if value is not None else None
    headers = getattr(response, "headers", None)
    if hasattr(headers, "get"):
        value = headers.get(name)
        return str(value) if value is not None else None
    return None


def _open_request(request: urllib.request.Request, *, timeout: float) -> object:
    return _DEFAULT_OPENER.open(request, timeout=timeout)


def fetch_text(
    *,
    fetch_type: str,
    url: str,
    caller: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout_s: float | int | None = 10.0,
    max_bytes: int = 512 * 1024,
    request_id: str | None = None,
    opener: Callable[..., object] | None = None,
    resolver: Callable[[str], Iterable[str]] | None = None,
    registry: FetchRegistry | None = None,
) -> ExternalFetchResult:
    registry = registry or build_fetch_registry()
    entry = registry.require_fetch_type(fetch_type)
    request_id = request_id or str(uuid.uuid4())

    if str(method or "").upper() != "GET":
        result = _result(
            entry=entry,
            ok=False,
            decision="block",
            reason_codes=("method_not_allowed",),
            request_id=request_id,
            preflight_status="not_run",
        )
        _write_diagnostic(result=result, caller=caller, url=url)
        return result

    if not _validate_timeout(timeout_s):
        result = _result(
            entry=entry,
            ok=False,
            decision="block",
            reason_codes=("invalid_timeout",),
            request_id=request_id,
            preflight_status="not_run",
        )
        _write_diagnostic(result=result, caller=caller, url=url)
        return result

    current_url = str(url)
    preflight = _preflight_url(current_url, resolver=resolver)
    if not preflight.ok:
        result = _result(
            entry=entry,
            ok=False,
            decision="block",
            reason_codes=(preflight.refusal_kind or "preflight_refused_dns_resolution",),
            request_id=request_id,
            preflight_status="refused",
            preflight_refusal_kind=preflight.refusal_kind,
        )
        _write_diagnostic(result=result, caller=caller, url=current_url, query=preflight.query, host=preflight.host)
        return result

    redirects = 0
    while True:
        # Revalidate immediately before open. This is the v1 DNS-rebinding guard.
        reconnect_refusal = _resolve_and_validate(preflight.host, resolver)
        if reconnect_refusal:
            result = _result(
                entry=entry,
                ok=False,
                decision="block",
                reason_codes=(reconnect_refusal,),
                request_id=request_id,
                preflight_status="refused",
                preflight_refusal_kind=reconnect_refusal,
            )
            _write_diagnostic(result=result, caller=caller, url=current_url, query=preflight.query, host=preflight.host)
            return result

        request = urllib.request.Request(current_url, headers=_request_headers(headers))
        response_obj = (opener or _open_request)(request, timeout=float(timeout_s))
        with response_obj as response:
            status_code = _response_status(response)
            if status_code in {301, 302, 303, 307, 308}:
                redirects += 1
                if redirects > _MAX_REDIRECTS:
                    result = _result(
                        entry=entry,
                        ok=False,
                        decision="block",
                        reason_codes=("preflight_refused_redirect_limit",),
                        request_id=request_id,
                        preflight_status="refused",
                        preflight_refusal_kind="preflight_refused_redirect_limit",
                    )
                    _write_diagnostic(result=result, caller=caller, url=current_url, query=preflight.query, host=preflight.host)
                    return result
                location = _response_header(response, "Location")
                next_url = urllib.parse.urljoin(current_url, location or "")
                redirected = _preflight_url(next_url, resolver=resolver)
                if not redirected.ok:
                    result = _result(
                        entry=entry,
                        ok=False,
                        decision="block",
                        reason_codes=("preflight_refused_redirect_target",),
                        request_id=request_id,
                        preflight_status="refused",
                        preflight_refusal_kind="preflight_refused_redirect_target",
                    )
                    _write_diagnostic(result=result, caller=caller, url=next_url, query=redirected.query, host=redirected.host)
                    return result
                current_url = next_url
                preflight = redirected
                continue
            body = _read_response_body(response, int(max_bytes))
            break
    text = body.decode("utf-8", errors="replace")
    if entry.threat_model_class == UNKNOWN_URL_FETCH:
        decision = "would_block"
        reasons = ("would_block_unknown_url_fetch",)
    else:
        decision = "allow"
        reasons = ("public_lookup_allowed",)
    result = _result(
        entry=entry,
        ok=True,
        text=text,
        decision=decision,
        reason_codes=reasons,
        status_code=status_code,
        request_id=request_id,
        preflight_status="allowed",
    )
    _write_diagnostic(result=result, caller=caller, url=current_url, query=preflight.query, host=preflight.host)
    return result


async def fetch_text_async(**kwargs) -> ExternalFetchResult:
    return await asyncio.to_thread(fetch_text, **kwargs)
