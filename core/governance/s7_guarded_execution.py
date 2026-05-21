"""S7.3 guarded self-modification execution seams."""

from __future__ import annotations

from dataclasses import dataclass

from core.governance import operator_user_boundary as s7


VOICE_SOURCE_BUNDLE_VALIDATION_STATUSES = frozenset({
    "valid_absent",
    "raw_response_hash_mismatch",
    "reader_route_mismatch",
    "source_bundle_unavailable",
    "not_mint_eligible",
})

VOICE_SOURCE_BUNDLE_AUTHORITY_PROJECTIONS = frozenset({
    "valid_absent",
    "grounded_refusal",
    "grounded_permission",
    "operational_block",
    "marker_only",
    "unavailable",
})


@dataclass(frozen=True)
class S7VoiceSourceBundleValidationResult:
    """Result of the S7.3 source-bundle validator that gates artifact minting."""

    status: str
    source_bundle_valid: bool
    mint_eligible: bool
    authority_projection: str
    failure_reason_code: str | None

    def __post_init__(self) -> None:
        if self.status not in VOICE_SOURCE_BUNDLE_VALIDATION_STATUSES:
            raise ValueError(f"unknown S7.3 voice source bundle validation status: {self.status}")
        if self.authority_projection not in VOICE_SOURCE_BUNDLE_AUTHORITY_PROJECTIONS:
            raise ValueError(
                "unknown S7.3 voice source bundle authority projection: "
                f"{self.authority_projection}"
            )
        if self.status == "valid_absent":
            if self.failure_reason_code is not None:
                raise ValueError("valid_absent source-bundle validation must not carry a failure reason")
            if self.source_bundle_valid is not True or self.mint_eligible is not True:
                raise ValueError("valid_absent source-bundle validation must be valid and mint-eligible")
            if self.authority_projection != "valid_absent":
                raise ValueError("valid_absent source-bundle validation must project valid_absent")
        elif self.failure_reason_code is None:
            raise ValueError("failed source-bundle validation must carry a failure reason")


def require_source_bundle_validation_for_mint(
    source_bundle_validation: S7VoiceSourceBundleValidationResult | None,
) -> S7VoiceSourceBundleValidationResult:
    """Require the literal validator pass before an S7.3 artifact can be minted."""

    if not isinstance(source_bundle_validation, S7VoiceSourceBundleValidationResult):
        raise ValueError("S7.3 artifact mint requires source-bundle validation")
    if (
        source_bundle_validation.status != "valid_absent"
        or source_bundle_validation.source_bundle_valid is not True
        or source_bundle_validation.mint_eligible is not True
        or source_bundle_validation.authority_projection != "valid_absent"
        or source_bundle_validation.failure_reason_code is not None
    ):
        raise ValueError("S7.3 artifact mint requires valid absent source-bundle validation")
    return source_bundle_validation


class S7GuardedStateStore:
    """Guarded S7.3 write facade over the existing S7 authorization artifact store."""

    def __init__(self, *, authorization_store: s7.S7AuthorizationStore):
        self.authorization_store = authorization_store

    def put_artifact_with_bundle_reservation(
        self,
        *,
        artifact: s7.S7AuthorizationArtifact,
        source_bundle_validation: S7VoiceSourceBundleValidationResult | None,
    ) -> None:
        require_source_bundle_validation_for_mint(source_bundle_validation)
        self.authorization_store.put(artifact)
