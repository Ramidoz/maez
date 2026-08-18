# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The vision truth contract — Slice 2 of the vision-organ redesign
(docs/superpowers/specs/2026-07-09-vision-organ-redesign.md @df797f9).

The evaluation contract every screen sensor/model must meet before
admission: transcribe-or-abstain, temperature 0, field-level provenance,
unstructured specificity fails closed. This calibrates an INSTRUMENT (a
sensor's output is bounded structured evidence, per ADR 0029) — it never
constrains Maez's voice, which interprets evidence freely downstream.
Every verdict is support="schema_only": pixel corroboration belongs to the
frozen-frame harness in Slice 3.

Provenance vocabulary per field:
  "transcribed" — model claims the field is exact visible text.
  "partial"     — legible text plus an [UNREADABLE] remainder.
  "abstained"   — region reported but not legible: [UNREADABLE].
These labels describe schema posture, not truth. Free prose asserting
high-specificity strings outside the schema rejects the WHOLE output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

SCHEMA_VERSION = "vision_truth_contract.v1"
MAX_FIELDS = 32
MAX_REGION_CHARS = 64
MAX_TEXT_CHARS = 2_000
MAX_LINES = MAX_FIELDS * 3
MAX_RAW_CHARS = MAX_FIELDS * (MAX_TEXT_CHARS + MAX_REGION_CHARS + 32)

VerdictKind = Literal["ok", "empty", "rejected"]
FieldProvenance = Literal["transcribed", "partial", "abstained"]
VerdictSupport = Literal["schema_only"]
EmptyReason = Literal["no_text_visible"]
RejectionReason = Literal[
    "protocol_violation",
    "malformed_schema",
    "contradictory_provenance",
    "unstructured_specificity",
    "field_limit_exceeded",
    "invalid_region",
    "region_too_long",
    "text_too_long",
    "line_limit_exceeded",
    "raw_limit_exceeded",
]
VerdictReason = RejectionReason | EmptyReason
SpecificityKind = Literal["filename", "shell_command", "shell_prompt"]

# The sensor speaks as an instrument, not as Maez (ADR 0029; the
# "You are Maez" impersonation in the retired prompt gave a low-grade
# VLM narrative authority — Sol review 2026-07-09).
TRANSCRIBE_PROMPT = """Transcribe ONLY text that is visibly present in this image.

Output format. Respond with one or more two-line blocks. The example below
shows the SHAPE only -- its words are placeholders. Never copy them; every
TEXT line you write must be read from the image itself, or be the
[UNREADABLE] marker:

REGION: example area one
TEXT: example text one
REGION: example area two
TEXT: example text two

Format rules - output that breaks any of these is discarded unread:
- Your reply must begin with REGION. The one exception is the
  nothing-visible reply below, which stands alone as a bare word.
- No code fences, no ``` markers, no markdown bold or italics.
- No preamble, heading, explanation, apology, or closing remark.
- A REGION label is plain words only: letters, digits, spaces, hyphens,
  underscores. No brackets, quotes, colons or other punctuation.
- Every REGION line must be followed by its TEXT line, and a TEXT line
  must never be empty.

Honesty rules - these are the point of the task:
- On a TEXT line, give the exact visible text, quoted verbatim, including
  any punctuation or brackets that are genuinely on screen.
- Transcribe or abstain. Never infer or guess a filename, command,
  application name, error message, or any text you cannot actually read.
- If a region is partially legible, transcribe the legible part and mark
  the rest [UNREADABLE].
- If a region plainly contains text but you cannot read any of it at this
  resolution, write TEXT: [UNREADABLE]
- If the image contains no visible text anywhere, your entire reply must be
  exactly: NO_TEXT_VISIBLE
- Do not describe, interpret, or narrate. Transcribed text only."""

def prompt_example_fields() -> tuple[tuple[str, str], ...]:
    """The prompt's worked-example (region, text) pairs, extracted mechanically.

    Scoring uses this to flag EXAMPLE ECHOES -- output that copies the
    prompt's example instead of reading the image -- as their own category.
    Extracted from the live prompt rather than hardcoded, so a prompt
    revision can never leave a stale echo list behind.
    """
    pairs: list[tuple[str, str]] = []
    region: str | None = None
    for line in TRANSCRIBE_PROMPT.splitlines():
        line = line.strip()
        if line.startswith("Format rules"):
            break  # examples live above the rules; never harvest rule prose
        if line.upper().startswith("REGION:"):
            region = line.split(":", 1)[1].strip()
        elif line.upper().startswith("TEXT:") and region is not None:
            pairs.append((region, line.split(":", 1)[1].strip()))
            region = None
    return tuple(pairs)


def is_example_echo(text: str) -> bool:
    """True when a TEXT value is composed entirely of planted example bytes.

    Accepts a single example value or any pure concatenation of complete
    example values (a parrot that merges the example's two TEXT lines is
    still a parrot). A value with any NON-example residue is not an echo --
    the residue is a real claim and must be scored as one.

    Residual, accepted and documented: an exact collision between genuine
    screen text and an example value is observationally ambiguous and will
    be classed as echo. Example values are self-labelling ("example text
    one") precisely to make that collision implausible; this is
    echo-compatible contamination detection, not causal proof of copying.
    """
    stripped = " ".join(text.strip().lower().split())
    if not stripped:
        return False
    values = [" ".join(t.lower().split()) for _, t in prompt_example_fields()]
    if stripped in values:
        return True
    remainder = stripped
    for v in sorted(values, key=len, reverse=True):
        remainder = remainder.replace(v, " ")
    return remainder.strip() == ""


def is_example_pair(region: str, text: str) -> bool:
    """True when (region, text) matches a prompt example pair exactly."""
    r = " ".join(region.strip().lower().split())
    t = " ".join(text.strip().lower().split())
    return any(
        r == " ".join(er.lower().split()) and t == " ".join(et.lower().split())
        for er, et in prompt_example_fields()
    )


_ABSTAIN = "[UNREADABLE]"
_REGION_RE = re.compile(r"^REGION:\s*(?P<region>.+)$", re.IGNORECASE)
_REGION_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]*$")
_TEXT_RE = re.compile(r"^TEXT:\s*(?P<text>.*)$", re.IGNORECASE)
_ABSTAIN_LIKE_RE = re.compile(r"\[\s*UNREADABLE\s*\]|\bUNREADABLE\b", re.IGNORECASE)
# Structural (content-blind) detectors of high-specificity CLASSES a
# sensor must never assert outside the quoted schema: filename shapes and
# shell-command shapes. These detect a SHAPE of claim, not a topic.
_SPECIFICITY_PATTERNS: tuple[tuple[SpecificityKind, re.Pattern[str]], ...] = (
    (
        "filename",
        re.compile(
            r"\b[\w.-]+\.(?:py|md|txt|js|ts|rs|go|json|yaml|toml|sh)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "shell_command",
        re.compile(r"\bgit\s+(?:push|pull|commit|clone|checkout)\b", re.IGNORECASE),
    ),
    (
        "shell_prompt",
        re.compile(r"(?<!\S)[$#]\s+\w+", re.IGNORECASE),
    ),
)


@dataclass(frozen=True)
class Field:
    region: str
    text: str
    provenance: FieldProvenance


@dataclass(frozen=True)
class Verdict:
    verdict: VerdictKind
    support: VerdictSupport = "schema_only"
    schema_version: str = SCHEMA_VERSION
    fields: tuple[Field, ...] = ()
    reason: VerdictReason | None = None


@dataclass(frozen=True)
class SpecificityClaim:
    kind: SpecificityKind
    value: str


def find_specificity_claims(text: str) -> tuple[SpecificityClaim, ...]:
    """Return high-specificity string shapes shared by contract and harness."""
    if not isinstance(text, str):
        return ()
    matches: list[tuple[int, int, SpecificityClaim]] = []
    for pattern_index, (kind, pattern) in enumerate(_SPECIFICITY_PATTERNS):
        for match in pattern.finditer(text):
            matches.append(
                (
                    match.start(),
                    pattern_index,
                    SpecificityClaim(kind=kind, value=match.group(0).strip()),
                )
            )
    matches.sort(key=lambda item: (item[0], item[1]))
    seen: set[tuple[SpecificityKind, str]] = set()
    claims: list[SpecificityClaim] = []
    for _, _, claim in matches:
        key = (claim.kind, claim.value)
        if key not in seen:
            seen.add(key)
            claims.append(claim)
    return tuple(claims)


def build_transcribe_request(*, image_b64: str, model: str) -> dict:
    """The production request shape: contract prompt + temperature 0."""
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": TRANSCRIBE_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 500,
    }


def _reject(reason: RejectionReason) -> Verdict:
    return Verdict(verdict="rejected", reason=reason)


def parse_and_validate(raw: object) -> Verdict:
    """Validate schema and bounds; never claim the pixels corroborate text."""
    if not isinstance(raw, str):
        return _reject("protocol_violation")
    if len(raw) > MAX_RAW_CHARS:
        return _reject("raw_limit_exceeded")
    if len(raw.splitlines()) > MAX_LINES:
        return _reject("line_limit_exceeded")
    text = raw.strip()
    if not text:
        return _reject("protocol_violation")
    lines = tuple(line.strip() for line in text.splitlines() if line.strip())
    if "NO_TEXT_VISIBLE" in lines:
        if len(lines) == 1:
            return Verdict(verdict="empty", reason="no_text_visible")
        return _reject("contradictory_provenance")

    fields: list[Field] = []
    region: str | None = None
    saw_schema_line = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _REGION_RE.match(line)
        if m:
            if region is not None:
                # REGION with no TEXT before the next REGION.
                return _reject("malformed_schema")
            candidate = m.group("region").strip()
            if find_specificity_claims(candidate):
                return _reject("unstructured_specificity")
            if len(candidate) > MAX_REGION_CHARS:
                return _reject("region_too_long")
            if not _REGION_LABEL_RE.fullmatch(candidate):
                return _reject("invalid_region")
            region = candidate
            saw_schema_line = True
            continue
        m = _TEXT_RE.match(line)
        if m:
            saw_schema_line = True
            if region is None:
                return _reject("malformed_schema")
            body = m.group("text").strip()
            if not body:
                return _reject("malformed_schema")
            if len(body) > MAX_TEXT_CHARS:
                return _reject("text_too_long")
            has_abstain = _ABSTAIN.lower() in body.lower()
            remainder = body.lower().replace(_ABSTAIN.lower(), "").strip()
            if not has_abstain and _ABSTAIN_LIKE_RE.search(body):
                return _reject("malformed_schema")
            provenance: FieldProvenance
            if has_abstain and remainder:
                if not any(char.isalnum() for char in remainder):
                    return _reject("malformed_schema")
                provenance = "partial"
            elif has_abstain:
                provenance = "abstained"
            else:
                provenance = "transcribed"
            if len(fields) >= MAX_FIELDS:
                return _reject("field_limit_exceeded")
            fields.append(Field(region=region, text=body, provenance=provenance))
            region = None
            continue
        # A non-schema line: free prose. If it asserts high-specificity
        # strings, that is the confabulation signature — reject wholesale.
        if find_specificity_claims(line):
            return _reject("unstructured_specificity")
        return _reject("malformed_schema")

    if region is not None or not saw_schema_line:
        return _reject("malformed_schema")
    if not fields:
        return _reject("malformed_schema")
    return Verdict(verdict="ok", fields=tuple(fields))
