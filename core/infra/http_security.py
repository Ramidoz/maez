# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Local HTTP origin guard for Maez's loopback APIs.

Loopback binding is not enough when a browser is involved: any web
page can try to POST to 127.0.0.1. This module permits owner-local
browser origins and non-browser local clients, while rejecting browser
requests from arbitrary origins.
"""

from __future__ import annotations

from urllib.parse import urlparse

_TRUSTED_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_BROWSER_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE", "OPTIONS"})


def is_trusted_loopback_origin(value: str | None) -> bool:
    """Return true only for localhost/loopback HTTP(S) origins."""
    if not value:
        return False
    raw = value.strip()
    if raw.lower() == "null":
        return False
    try:
        parsed = urlparse(raw)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname
    return bool(host and host.lower() in _TRUSTED_LOOPBACK_HOSTS)


def cors_allow_origin(origin: str | None) -> str | None:
    """Return the exact origin to echo in CORS, or None to omit CORS."""
    if is_trusted_loopback_origin(origin):
        return origin.strip()
    return None


def apply_local_cors_headers(response, request=None):
    """Attach local-only CORS headers without wildcarding the API."""
    origin = request.headers.get("Origin") if request is not None else None
    allowed = cors_allow_origin(origin)
    if allowed:
        response.headers["Access-Control-Allow-Origin"] = allowed
        vary = response.headers.get("Vary")
        if vary:
            if "Origin" not in {part.strip() for part in vary.split(",")}:
                response.headers["Vary"] = f"{vary}, Origin"
        else:
            response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def reject_untrusted_browser_write(request):
    """Return a Flask 403 response for untrusted browser write attempts.

    No Origin/Referer means a non-browser local caller such as urllib,
    curl, or the web-to-daemon proxy. Those remain allowed.
    """
    if request.method not in _BROWSER_WRITE_METHODS:
        return None
    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")
    if origin and not is_trusted_loopback_origin(origin):
        from flask import jsonify

        return jsonify({"ok": False, "error": "untrusted_origin"}), 403
    if not origin and referer and not is_trusted_loopback_origin(referer):
        from flask import jsonify

        return jsonify({"ok": False, "error": "untrusted_referer"}), 403
    return None
