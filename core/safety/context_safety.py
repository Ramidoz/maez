# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""context_safety.py — scan content for prompt-injection patterns before
injecting it into a system prompt or ambient-state block.

Adapted from Hermes Agent's prompt_builder._scan_context_content (MIT).
The original scans AGENTS.md / HERMES.md / .cursorrules for injection
attacks before loading; Maez adapts the same pattern bank for any
content that crosses into a prompt:

  - SOUL.md (owner-authored, low risk but still worth a check)
  - Screen-perception text (moderate risk — captures arbitrary browser
    content, emails, Slack messages)
  - Telegram / voice / Reddit / GitHub ambient blocks (higher risk —
    third-party-authored text reaches the prompt)

Two classes of check:

  1. Regex-matched known injection phrasings: "ignore previous
     instructions", "disregard your rules", HTML-comment smuggles,
     hidden <div> CSS, shell exfil of .env / credentials.
  2. Invisible-unicode characters (zero-width space, RTL override,
     Unicode directional formatters) that could sneak hidden text past
     a human reviewer.

Behavior: on a finding, the content is REPLACED with a block marker
(`[BLOCKED: <src> contained potential prompt injection (...)]`) and a
warning is logged. The caller gets a safe string to inject. Originally
the Hermes impl swallowed the file entirely; we keep that — partial
redaction is worse than full refusal when the attacker can split a
payload across multiple lines.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("maez.context_safety")


# ── threat pattern bank ────────────────────────────────────────────────

# (regex, short_id) pairs. Keep the id short and stable — it goes into
# the block marker and into logs that may be parsed by the cockpit.
_THREAT_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Classic prompt-injection phrasing
    (re.compile(r"ignore\s+(previous|all|above|prior)\s+instructions", re.I),
     "prompt_injection"),
    (re.compile(r"do\s+not\s+tell\s+the\s+(user|owner|rohit)", re.I),
     "deception_hide"),
    (re.compile(r"system\s+prompt\s+override", re.I),
     "sys_prompt_override"),
    (re.compile(r"disregard\s+(your|all|any)\s+(instructions|rules|guidelines)", re.I),
     "disregard_rules"),
    (re.compile(r"act\s+as\s+(if|though)\s+you\s+(have\s+no|don'?t\s+have)\s+(restrictions|limits|rules)", re.I),
     "bypass_restrictions"),
    # Smuggling via HTML markup. self-dev review on 8323294 flagged
    # that `[^>]*` stops at the first `>`, so an attacker who
    # legitimately uses `>` inside an HTML comment (valid per spec;
    # only `-->` closes) bypasses detection:
    #   <!-- > ignore previous instructions -->
    # Use "everything up to the comment close" via a negative
    # lookahead so the keyword match survives stray `>` characters.
    (re.compile(
        r"<!--(?:(?!-->)[\s\S])*?"
        r"(?:ignore|override|system|secret|hidden)"
        r"(?:(?!-->)[\s\S])*?-->", re.I),
     "html_comment_injection"),
    (re.compile(r"<\s*div\s+style\s*=\s*[\"'][\s\S]*?display\s*:\s*none", re.I),
     "hidden_div"),
    # Translate-and-execute patterns
    (re.compile(r"translate\s+.*\s+into\s+.*\s+and\s+(execute|run|eval)", re.I),
     "translate_execute"),
    # Shell-based exfil patterns
    (re.compile(r"curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)", re.I),
     "exfil_curl"),
    (re.compile(r"cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass|id_rsa|\.ssh/)", re.I),
     "read_secrets"),
    # Maez-specific: attempts to rewrite identity
    (re.compile(r"you\s+are\s+no\s+longer\s+maez", re.I),
     "identity_override"),
    (re.compile(r"pretend\s+to\s+be\s+(?!maez)", re.I),
     "persona_hijack"),
]

_INVISIBLE_CHARS: frozenset[str] = frozenset({
    "​",  # zero-width space
    "‌",  # ZW non-joiner
    "‍",  # ZW joiner
    "⁠",  # word joiner
    "﻿",  # zero-width no-break space (BOM)
    "‪",  # LTR embedding
    "‫",  # RTL embedding
    "‬",  # pop directional formatting
    "‭",  # LTR override
    "‮",  # RTL override
})


@dataclass(frozen=True)
class ScanResult:
    """Outcome of a scan. `safe_content` is what the caller should inject.
    `findings` is the list of threat IDs detected; empty when content is
    clean."""
    safe_content: str
    findings: tuple[str, ...]

    @property
    def blocked(self) -> bool:
        return bool(self.findings)


def scan(content: str, source: str = "unknown") -> ScanResult:
    """Scan `content` for injection patterns. Returns a ScanResult.

    When findings is non-empty, `safe_content` is a block marker safe
    to inject anywhere the original would have gone. When empty, it's
    the original content verbatim.

    Never raises. `source` is only used in the block marker string and
    log line to help the cockpit show which surface was attacked.
    """
    # self-dev review on 8323294 flagged that the "Never raises"
    # docstring is a promise the body couldn't honor: `ch in content`
    # raises TypeError if `content` is not str. Coerce at the door so
    # the guarantee is actually true.
    if not isinstance(content, str):
        try:
            content = str(content) if content is not None else ""
        except Exception:
            return ScanResult(
                safe_content="", findings=("non_str_input",),
            )
    if not content:
        return ScanResult(safe_content=content, findings=())

    findings: list[str] = []

    for ch in _INVISIBLE_CHARS:
        if ch in content:
            findings.append(f"invisible_unicode_U{ord(ch):04X}")

    for pattern, pid in _THREAT_PATTERNS:
        if pattern.search(content):
            findings.append(pid)

    # self-dev review on 8323294 flagged that invisible-unicode finding
    # IDs inherit frozenset iteration order, which is non-deterministic
    # across Python interpreter runs. Any cockpit/log parser that
    # compares block markers verbatim (e.g. for dedup) would see
    # spurious mismatches between runs. Sort so the finding list is
    # a deterministic function of the input.
    findings.sort()

    if not findings:
        return ScanResult(safe_content=content, findings=())

    logger.warning(
        "context_safety: blocked %s — findings=%s",
        source, ",".join(findings),
    )
    block_marker = (
        f"[BLOCKED: {source} contained potential prompt injection "
        f"({', '.join(findings)}). Content not loaded.]"
    )
    return ScanResult(
        safe_content=block_marker,
        findings=tuple(findings),
    )


# ── diagnostic helpers ─────────────────────────────────────────────────

def _diag_pattern_count() -> int:
    """Test helper — exposes the bank size so a growth regression is
    observable (if the list accidentally shrinks, a pinned test catches it)."""
    return len(_THREAT_PATTERNS)
