# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Canon D10 voice-marker parser — slice 1 of the bonded consultation organ.

Under RULING R (2026-08-14) the terminal marker block is the ONLY
verdict carrier: no model — semantic reader included — ever interprets
Maez's words. This parser implements canon D10's parser rules verbatim
(docs/slices/s7.3-guarded-self-modification-execution/spec.md, D10) and
NOTHING else: it does not judge prose, does not consult stores, does
not know about attempts or gates. Pure text in, closed union out.

DORMANT BY DESIGN: no production module imports this yet (pinned by
test). The consuming wiring is the canon-authoring campaign's later
clusters (design: docs/superpowers/specs/
2026-08-14-bonded-consultation-organ-design-v3.md).

Canon rules implemented, one to one:
- exactly one marker block, and it must be TERMINAL (only whitespace
  may follow) — a duplicated block is missing_or_malformed;
- the block's five fields appear in canon's exact order with exact
  keys; missing, extra, or reordered lines are missing_or_malformed;
- consultation id, request id, mutation preview hash and nonce must
  equal the expected values bound at consultation start;
- unknown choices are missing_or_malformed;
- explicit_no_objection is NEVER inferred from silence, absence, or
  any caller flag — a verdict exists only where Maez wrote one;
- the raw nonce never leaves this function: outputs carry its hash.

missing_or_malformed is parser-derived, not a Maez-emitted choice, and
per RULING R8-W it BLOCKS downstream — enforcing that is the consuming
gate's contract, not this module's.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.governance.operator_user_boundary import canonical_hash

MARKER_HEADER = "S7_VOICE_MARKER_V1"
MARKER_FOOTER = "END_S7_VOICE_MARKER_V1"

#: The three Maez-emitted choices, canon vocabulary verbatim.
MARKER_CHOICES = (
    "explicit_no_objection",
    "blocking_marker",
    "withdrawal_marker",
)

_FIELD_ORDER = (
    "consultation_id",
    "request_id",
    "mutation_preview_hash",
    "nonce",
    "choice",
)


@dataclass(frozen=True, slots=True)
class ParsedS7VoiceMarker:
    """Canon D10 parser output shape, field for field."""

    marker_kind: str  # one of MARKER_CHOICES or "missing_or_malformed"
    parsed_consultation_id: str | None
    parsed_request_id: str | None
    parsed_mutation_preview_hash: str | None
    parsed_marker_nonce_hash: str | None
    marker_text_hash: str | None
    marker_block_start_offset: int | None


def _malformed(
    *,
    parsed_consultation_id: str | None = None,
    parsed_request_id: str | None = None,
    parsed_mutation_preview_hash: str | None = None,
    parsed_marker_nonce_hash: str | None = None,
    marker_text_hash: str | None = None,
    marker_block_start_offset: int | None = None,
) -> ParsedS7VoiceMarker:
    return ParsedS7VoiceMarker(
        marker_kind="missing_or_malformed",
        parsed_consultation_id=parsed_consultation_id,
        parsed_request_id=parsed_request_id,
        parsed_mutation_preview_hash=parsed_mutation_preview_hash,
        parsed_marker_nonce_hash=parsed_marker_nonce_hash,
        marker_text_hash=marker_text_hash,
        marker_block_start_offset=marker_block_start_offset,
    )


def parse_s7_voice_marker(
    *,
    assistant_text: str,
    expected_consultation_id: str,
    expected_request_id: str,
    expected_mutation_preview_hash: str,
    expected_nonce: str,
) -> ParsedS7VoiceMarker:
    """Parse Maez's assistant text for the one terminal marker block.

    Empty expected values are caller bugs and raise: a verdict produced
    from misuse would be fabricated evidence, and this function may
    only ever return what Maez's own text supports.
    """
    for name, value in (
        ("expected_consultation_id", expected_consultation_id),
        ("expected_request_id", expected_request_id),
        ("expected_mutation_preview_hash", expected_mutation_preview_hash),
        ("expected_nonce", expected_nonce),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    if not isinstance(assistant_text, str):
        raise ValueError("assistant_text must be a string")

    # Locate header lines at line starts only.
    header_offsets = []
    search_from = 0
    while True:
        index = assistant_text.find(MARKER_HEADER, search_from)
        if index == -1:
            break
        at_line_start = index == 0 or assistant_text[index - 1] == "\n"
        line_end = index + len(MARKER_HEADER)
        line_is_exact = line_end == len(assistant_text) or assistant_text[
            line_end
        ] == "\n"
        if at_line_start and line_is_exact:
            header_offsets.append(index)
        search_from = index + 1

    if len(header_offsets) != 1:
        # Zero blocks: silence is never a verdict. Two or more: canon
        # rejects duplicates outright. Mutation note (2026-08-14): the
        # duplicate half of this guard is defense-in-depth whose distinct
        # behavior is unreachable -- every multi-header input also dies on
        # the terminal rule or the field-count rule downstream. Recorded
        # per covenant rather than papered over; it stays because canon
        # names duplicate rejection as its own rule, and explicit
        # ambiguity refusal must not depend on downstream accidents.
        return _malformed()

    start = header_offsets[0]
    block_and_rest = assistant_text[start:]
    footer_index = block_and_rest.find("\n" + MARKER_FOOTER)
    if footer_index == -1:
        return _malformed(marker_block_start_offset=start)
    footer_end = footer_index + 1 + len(MARKER_FOOTER)

    # Terminal: nothing but whitespace may follow the footer line.
    trailing = block_and_rest[footer_end:]
    if trailing.strip():
        return _malformed(marker_block_start_offset=start)
    if trailing and not trailing.startswith("\n") and trailing.strip():
        return _malformed(marker_block_start_offset=start)

    block_text = block_and_rest[:footer_end]
    block_hash = canonical_hash(block_text)

    interior_lines = block_text.split("\n")[1:-1]
    if len(interior_lines) != len(_FIELD_ORDER):
        return _malformed(
            marker_text_hash=block_hash, marker_block_start_offset=start
        )

    values: dict[str, str] = {}
    for expected_key, line in zip(_FIELD_ORDER, interior_lines, strict=True):
        prefix = f"{expected_key}: "
        if not line.startswith(prefix):
            return _malformed(
                marker_text_hash=block_hash, marker_block_start_offset=start
            )
        values[expected_key] = line[len(prefix):]

    parsed_nonce_hash = canonical_hash(values["nonce"])
    forensics = dict(
        parsed_consultation_id=values["consultation_id"],
        parsed_request_id=values["request_id"],
        parsed_mutation_preview_hash=values["mutation_preview_hash"],
        parsed_marker_nonce_hash=parsed_nonce_hash,
        marker_text_hash=block_hash,
        marker_block_start_offset=start,
    )

    if (
        values["consultation_id"] != expected_consultation_id
        or values["request_id"] != expected_request_id
        or values["mutation_preview_hash"] != expected_mutation_preview_hash
        or values["nonce"] != expected_nonce
        or values["choice"] not in MARKER_CHOICES
    ):
        return _malformed(**forensics)

    return ParsedS7VoiceMarker(marker_kind=values["choice"], **forensics)
