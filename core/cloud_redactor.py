"""
core/cloud_redactor.py — Session 11g, staging-only.

Defensive prompt redaction layer applied immediately before any cloud
backend call. The local backend path is NEVER touched by this module.

Purpose:
  • Last line of defense against accidental exfiltration of:
    - PII (emails, phones, paths, API-key-shaped tokens, IPv4, long IDs)
    - Maez internal identifiers (memory_id_*, candidate_*, proposal_*,
      weakness_description fields)
  • The fast lane already has multiple earlier defenses:
      1. core.public_user_shaping.strip_pii (called for guest input)
      2. core.fast_reply_schema (rejects perception/internal field injection)
      3. core.fast_backend_router policy table (pins guest scopes to local)
      4. core.fast_backend_cloud env+credential gates
  • This module is the FIFTH defense, applied after all of those, to
    catch anything that slipped through (e.g. a daemon-side prompt
    template that inadvertently included an internal identifier when
    cloud was enabled for a drafting scope).

Public surface:
    redact_for_cloud(prompt) -> RedactionResult
    is_changed(result)        -> bool

Behavior:
  • Deterministic.
  • Does NOT modify the prompt at all if no patterns match (RedactionResult
    .text is the same string object as the input).
  • Replaces matches with structured placeholder tokens:
      [pii:email]    [pii:phone]    [pii:path]
      [pii:token]    [pii:ip]       [pii:id]
      [internal:memory_id]   [internal:candidate]
      [internal:proposal]    [internal:weakness]
  • Returns count by category for audit purposes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ── PII patterns (mirror of core.public_user_shaping) ─────────────────
_PII_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ('email',   re.compile(
        r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b'
    ), '[pii:email]'),

    ('phone',   re.compile(
        r'(?<!\w)(?:\+?\d{1,3}[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}(?!\w)'
    ), '[pii:phone]'),

    ('fs_path', re.compile(
        r'(?<!\w)/(?:home|root|Users|var|etc|opt|tmp|mnt|srv)/[^\s\'"]*'
    ), '[pii:path]'),

    ('api_key', re.compile(
        r'(?<![A-Za-z0-9])[A-Za-z0-9_\-]{32,}(?![A-Za-z0-9])'
    ), '[pii:token]'),

    ('ipv4',    re.compile(
        r'\b(?!127\.0\.0\.1\b|0\.0\.0\.0\b|255\.255\.255\.255\b)'
        r'(?:\d{1,3}\.){3}\d{1,3}\b'
    ), '[pii:ip]'),

    ('long_digits', re.compile(
        r'(?<!\d)\d{9,}(?!\d)'
    ), '[pii:id]'),
]

# ── Maez internal identifier patterns ─────────────────────────────────
# Cover both bare identifiers like `memory_id_42` and label tokens like
# "weakness_description: Topic concentration on...". Matches are placed
# under their own [internal:*] namespace so audit records can tell PII
# from internal-leak attempts at a glance.
_INTERNAL_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ('memory_id', re.compile(
        r'\bmemory_id[_:]?\s*[A-Za-z0-9_\-]+', re.IGNORECASE
    ), '[internal:memory_id]'),

    ('candidate', re.compile(
        r'\bcandidate[_:]?\s*[A-Za-z0-9_\-]+', re.IGNORECASE
    ), '[internal:candidate]'),

    ('proposal', re.compile(
        r'\bproposal[_:]?\s*[A-Za-z0-9_\-]+', re.IGNORECASE
    ), '[internal:proposal]'),

    # The literal field name as it appears in evolution_engine evidence
    # packets. If this string ever shows up in a cloud-bound prompt, that
    # is itself a leak signal worth flagging.
    ('weakness_description', re.compile(
        r'\bweakness_description\b', re.IGNORECASE
    ), '[internal:weakness]'),

    # Soul note marker — daemon-internal
    ('soul_note', re.compile(
        r'\bsoul_note[_:]?\s*[A-Za-z0-9_\-]*', re.IGNORECASE
    ), '[internal:soul_note]'),
]


@dataclass
class RedactionResult:
    text: str                                    # the (possibly redacted) text
    original_chars: int = 0
    redacted_chars: int = 0
    pii_counts: dict[str, int] = field(default_factory=dict)
    internal_counts: dict[str, int] = field(default_factory=dict)
    changed: bool = False

    def total_redactions(self) -> int:
        return sum(self.pii_counts.values()) + sum(self.internal_counts.values())

    def to_telemetry(self) -> dict:
        """JSON-able dict, METADATA ONLY. Never includes the text."""
        return {
            'original_chars':   self.original_chars,
            'redacted_chars':   self.redacted_chars,
            'pii_counts':       dict(self.pii_counts),
            'internal_counts':  dict(self.internal_counts),
            'total_redactions': self.total_redactions(),
            'changed':          self.changed,
        }


def redact_for_cloud(prompt: str) -> RedactionResult:
    """Apply all PII + internal-identifier patterns to `prompt`.

    Returns a RedactionResult. The result.text is the safe-to-send
    string. Caller MUST send result.text, not the original prompt.
    """
    if prompt is None:
        return RedactionResult(text='', original_chars=0, redacted_chars=0)
    if not isinstance(prompt, str):
        # Be defensive — return empty redacted text and count nothing
        return RedactionResult(text='', original_chars=0, redacted_chars=0)

    out = prompt
    pii_counts: dict[str, int] = {}
    internal_counts: dict[str, int] = {}

    for kind, pattern, replacement in _PII_PATTERNS:
        out, n = pattern.subn(replacement, out)
        if n:
            pii_counts[kind] = n

    for kind, pattern, replacement in _INTERNAL_PATTERNS:
        out, n = pattern.subn(replacement, out)
        if n:
            internal_counts[kind] = n

    changed = (out != prompt)

    return RedactionResult(
        text=out,
        original_chars=len(prompt),
        redacted_chars=len(out),
        pii_counts=pii_counts,
        internal_counts=internal_counts,
        changed=changed,
    )


def is_changed(result: RedactionResult) -> bool:
    return bool(result.changed)
