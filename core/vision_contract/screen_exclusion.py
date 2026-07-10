# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Single bounded Decision-9 authority for screen-context exclusion."""

from __future__ import annotations

import os
import re
from urllib.parse import unquote
from collections.abc import Mapping, Sequence

DEFAULT_EXCLUDE = (
    "keepassxc", "bitwarden", "1password", "gnome-keyring", "signal",
    "whatsapp", "telegram", "slack", "gmail", "email", "mail", "inbox",
    "zoom", "meet.google", "google meet", "teams", "webex", "bank",
    "banking", "chase", "capital one", "citi", "amex", "american express",
    "wellsfargo", "wells fargo", "fidelity", "vanguard", "schwab",
    "mychart", "medical", "health", "patient", "portal", "password",
    "credential", "vault",
)
MAX_WINDOW_CLASS_CHARS = 256
MAX_WINDOW_TITLE_CHARS = 1024
MAX_DOCUMENT_REFS = 32
MAX_DOCUMENT_REF_CHARS = 4096
_BAD_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_PERCENT_ESCAPE = re.compile(r"%[0-9A-Fa-f]{2}")


def _canonical_reference(value: str) -> str | None:
    if _BAD_PERCENT_ESCAPE.search(value):
        return None
    current = value
    try:
        for _ in range(3):
            decoded = unquote(current, encoding="utf-8", errors="strict")
            if decoded == current:
                break
            current = decoded
    except UnicodeDecodeError:
        return None
    if _PERCENT_ESCAPE.search(current):
        return None
    return current.lower()


def exclusion_terms(env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    source = os.environ if env is None else env
    extra = source.get("MAEZ_SCREEN_EXCLUDE", "")
    extra_terms = tuple(term.strip().lower() for term in extra.split(",") if term.strip())
    return DEFAULT_EXCLUDE + extra_terms


def active_window_preflight_reason(
    window: Mapping[str, object] | None,
    *,
    document_refs: Sequence[str] = (),
    terms: Sequence[str] | None = None,
) -> str | None:
    """Reject sensitive window identity or document-wide references."""
    if not isinstance(window, Mapping):
        return "window_unavailable"
    app_class = window.get("class")
    if (
        not isinstance(app_class, str)
        or not app_class.strip()
        or len(app_class) > MAX_WINDOW_CLASS_CHARS
    ):
        return "class_unavailable"
    title = window.get("title")
    if title is not None and not isinstance(title, str):
        return "window_schema_invalid"
    title_text = title or ""
    if len(title_text) > MAX_WINDOW_TITLE_CHARS:
        return "window_schema_invalid"
    if not isinstance(document_refs, Sequence) or isinstance(document_refs, (str, bytes)):
        return "window_schema_invalid"
    refs = tuple(document_refs)
    if len(refs) > MAX_DOCUMENT_REFS:
        return "window_schema_invalid"
    bounded_terms = tuple(terms if terms is not None else exclusion_terms())
    if any(not isinstance(term, str) or not term for term in bounded_terms):
        return "window_schema_invalid"
    haystack = f"{app_class} {title_text}".lower()
    if any(term in haystack for term in bounded_terms):
        return "sensitive_window"
    for ref in refs:
        if not isinstance(ref, str) or not ref or len(ref) > MAX_DOCUMENT_REF_CHARS:
            return "window_schema_invalid"
        canonical = _canonical_reference(ref)
        if canonical is None:
            return "window_schema_invalid"
        if any(term in canonical for term in bounded_terms):
            return "excluded_path"
    return None
