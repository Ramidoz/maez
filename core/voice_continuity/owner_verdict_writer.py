"""Owner-origin marker minting for the reviewed verdict path."""

from __future__ import annotations

from core.voice_continuity.schema import OwnerOriginMarker, utc_now_iso


def mint_operator_origin_marker(
    *,
    origin: str,
    attested_by: str,
    review_id: str,
    baseline_id: str,
    review_package_hash: str,
    is_tty: bool | None = None,
) -> dict[str, str]:
    if origin == "operator_cli_tty" and not is_tty:
        raise ValueError("operator_cli_tty origin requires an interactive tty")
    return OwnerOriginMarker(
        origin=origin,
        attested_by=attested_by,
        attested_at=utc_now_iso(),
        review_id=review_id,
        baseline_id=baseline_id,
        review_package_hash=review_package_hash,
    ).to_dict()
