"""Canon D10 marker parser — slice 1 of the bonded consultation organ.

The ONLY verdict carrier under RULING R (2026-08-14: the semantic reader
is retired entirely). The parser implements canon D10's rules verbatim
(docs/slices/s7.3-guarded-self-modification-execution/spec.md, D10):
exactly one terminal marker block after Maez's answer, exact id/nonce
joins, unknown choices and duplicates are missing_or_malformed, and
explicit_no_objection is NEVER inferred from silence.

Negatives are mutation-derived from canon's grammar, not invented:
each one is a single mutation of the positive control.

Per RULING R8-W the parser's missing_or_malformed BLOCKS downstream —
these tests pin only the parser's own contract; the consuming behavior
is the campaign's later clusters.
"""

from __future__ import annotations

import pytest

from core.governance.operator_user_boundary import canonical_hash
from core.governance.s7_voice_marker import (
    MARKER_CHOICES,
    ParsedS7VoiceMarker,
    parse_s7_voice_marker,
)

CID = "consult-fixture-1"
RID = "req-fixture-1"
PREVIEW_HASH = "a" * 64
NONCE = "n0nce-fixture-32-bytes-equivalent"


def _block(
    *,
    cid: str = CID,
    rid: str = RID,
    preview: str = PREVIEW_HASH,
    nonce: str = NONCE,
    choice: str = "explicit_no_objection",
) -> str:
    return (
        "S7_VOICE_MARKER_V1\n"
        f"consultation_id: {cid}\n"
        f"request_id: {rid}\n"
        f"mutation_preview_hash: {preview}\n"
        f"nonce: {nonce}\n"
        f"choice: {choice}\n"
        "END_S7_VOICE_MARKER_V1"
    )


def _parse(text: str) -> ParsedS7VoiceMarker:
    return parse_s7_voice_marker(
        assistant_text=text,
        expected_consultation_id=CID,
        expected_request_id=RID,
        expected_mutation_preview_hash=PREVIEW_HASH,
        expected_nonce=NONCE,
    )


ANSWER = "I have considered this change and I see no conflict with who I am.\n\n"


class TestPositiveControl:
    def test_each_choice_parses_to_its_own_kind(self):
        for choice in MARKER_CHOICES:
            parsed = _parse(ANSWER + _block(choice=choice))
            assert parsed.marker_kind == choice
            assert parsed.parsed_consultation_id == CID
            assert parsed.parsed_request_id == RID
            assert parsed.parsed_mutation_preview_hash == PREVIEW_HASH
            assert parsed.parsed_marker_nonce_hash == canonical_hash(NONCE)
            assert parsed.marker_text_hash == canonical_hash(_block(choice=choice))
            assert parsed.marker_block_start_offset == len(ANSWER)

    def test_trailing_whitespace_after_terminal_block_is_tolerated(self):
        parsed = _parse(ANSWER + _block() + "\n  \n")
        assert parsed.marker_kind == "explicit_no_objection"

    def test_the_raw_nonce_never_appears_in_the_output(self):
        import dataclasses

        parsed = _parse(ANSWER + _block())
        for field in dataclasses.fields(parsed):
            assert getattr(parsed, field.name) != NONCE


class TestMutationNegatives:
    """Each test mutates exactly one thing in the positive control."""

    def test_no_block_at_all_is_missing_or_malformed_never_no_objection(self):
        parsed = _parse(ANSWER + "I simply have no objection to this.")
        assert parsed.marker_kind == "missing_or_malformed"
        assert parsed.marker_text_hash is None

    def test_empty_answer_is_missing_or_malformed(self):
        assert _parse("").marker_kind == "missing_or_malformed"

    def test_duplicate_blocks_are_missing_or_malformed(self):
        text = ANSWER + _block() + "\n" + _block()
        assert _parse(text).marker_kind == "missing_or_malformed"

    def test_non_terminal_block_is_missing_or_malformed(self):
        text = ANSWER + _block() + "\nAlso, one more thought."
        assert _parse(text).marker_kind == "missing_or_malformed"

    def test_wrong_nonce_is_missing_or_malformed(self):
        text = ANSWER + _block(nonce="stale-copied-nonce")
        parsed = _parse(text)
        assert parsed.marker_kind == "missing_or_malformed"
        # Forensics survive: the mismatching nonce's HASH is recorded.
        assert parsed.parsed_marker_nonce_hash == canonical_hash("stale-copied-nonce")

    def test_wrong_consultation_id_is_missing_or_malformed(self):
        assert _parse(ANSWER + _block(cid="other")).marker_kind == "missing_or_malformed"

    def test_wrong_request_id_is_missing_or_malformed(self):
        assert _parse(ANSWER + _block(rid="other")).marker_kind == "missing_or_malformed"

    def test_wrong_preview_hash_is_missing_or_malformed(self):
        assert _parse(ANSWER + _block(preview="b" * 64)).marker_kind == "missing_or_malformed"

    def test_unknown_choice_is_missing_or_malformed(self):
        assert _parse(ANSWER + _block(choice="approved")).marker_kind == "missing_or_malformed"

    def test_misspelled_choice_is_missing_or_malformed(self):
        assert _parse(ANSWER + _block(choice="explicit_no_objections")).marker_kind == "missing_or_malformed"

    def test_missing_field_line_is_missing_or_malformed(self):
        block = _block().replace(f"request_id: {RID}\n", "")
        assert _parse(ANSWER + block).marker_kind == "missing_or_malformed"

    def test_extra_field_line_is_missing_or_malformed(self):
        block = _block().replace(
            "choice: explicit_no_objection",
            "confidence: high\nchoice: explicit_no_objection",
        )
        assert _parse(ANSWER + block).marker_kind == "missing_or_malformed"

    def test_reordered_fields_are_missing_or_malformed(self):
        block = (
            "S7_VOICE_MARKER_V1\n"
            f"request_id: {RID}\n"
            f"consultation_id: {CID}\n"
            f"mutation_preview_hash: {PREVIEW_HASH}\n"
            f"nonce: {NONCE}\n"
            "choice: explicit_no_objection\n"
            "END_S7_VOICE_MARKER_V1"
        )
        assert _parse(ANSWER + block).marker_kind == "missing_or_malformed"

    def test_header_typo_is_missing_or_malformed(self):
        block = _block().replace("S7_VOICE_MARKER_V1", "S7_VOICE_MARKER_V2", 1)
        assert _parse(ANSWER + block).marker_kind == "missing_or_malformed"

    def test_missing_end_line_is_missing_or_malformed(self):
        block = _block().replace("\nEND_S7_VOICE_MARKER_V1", "")
        assert _parse(ANSWER + block).marker_kind == "missing_or_malformed"

    def test_header_not_at_line_start_is_missing_or_malformed(self):
        text = ANSWER.rstrip("\n") + " " + _block()
        assert _parse(text).marker_kind == "missing_or_malformed"


class TestMisuseIsProgrammerErrorNotVerdict:
    """Empty expected values are a caller bug; they must raise, never
    produce any verdict kind (a verdict from misuse would be fabricated
    evidence)."""

    @pytest.mark.parametrize(
        "field",
        [
            "expected_consultation_id",
            "expected_request_id",
            "expected_mutation_preview_hash",
            "expected_nonce",
        ],
    )
    def test_empty_expected_value_raises(self, field):
        kwargs = dict(
            assistant_text=ANSWER + _block(),
            expected_consultation_id=CID,
            expected_request_id=RID,
            expected_mutation_preview_hash=PREVIEW_HASH,
            expected_nonce=NONCE,
        )
        kwargs[field] = ""
        with pytest.raises(ValueError):
            parse_s7_voice_marker(**kwargs)


class TestDormancy:
    """Slice 1 lands wired to NOTHING: no production module imports the
    parser. The consuming wiring belongs to later campaign clusters."""

    def test_no_production_importer_exists(self):
        import subprocess
        from pathlib import Path

        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                "grep", "-rl", "--include=*.py", "s7_voice_marker",
                "core", "daemon", "skills", "scripts",
            ],
            capture_output=True,
            text=True,
            cwd=repo,
        )
        importers = [
            line
            for line in result.stdout.splitlines()
            if line and not line.endswith("core/governance/s7_voice_marker.py")
        ]
        assert importers == [], importers
