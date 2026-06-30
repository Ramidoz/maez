"""Thin requests adapter: POST a label to the host doorway. The ONLY network I/O."""

from __future__ import annotations


def post_label(host_url, intake_path, *, token, label, requests_module=None, timeout=4.0):
    """POST the label with the device token. Returns status code, or None on transport error."""
    if requests_module is None:
        import requests  # lazy: device-only dependency

        requests_module = requests
    url = host_url.rstrip("/") + intake_path
    try:
        resp = requests_module.post(
            url, json=label, headers={"X-Maez-Jetson-Token": token}, timeout=timeout
        )
        return resp.status_code
    except (OSError, TimeoutError):
        return None
