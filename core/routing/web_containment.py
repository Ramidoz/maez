"""Single implementation of live web-context containment: wrap the FINAL
(already-truncated) web evidence text in fresh_containment's un-spoofable envelope,
and produce a content-light receipt asserting balanced markers on the assembled string.

Used by every live prompt throat (focused/legacy/voice/photo) so no two grow a
subtly-different containment.
"""
from __future__ import annotations

import logging

from core.cognition.fetch_screen_flags import fetch_containment_enabled
from core.dispatcher import fresh_containment as _fc

logger = logging.getLogger("maez")


def new_nonce() -> str:
    return _fc.new_nonce()


def standing_instruction() -> str:
    return _fc.standing_instruction()


def wrap_web_text(text: str, *, nonce: str, source: str, digest: str) -> str:
    """Wrap one final/truncated web item string. Markers are added HERE (outside any
    upstream truncation budget). Marker-strip neutralizes forged markers in `text`."""
    return _fc.contain_fresh_text(text, nonce=nonce, source=source, content_digest=digest)


def containment_receipt(assembled_segment: str, *, nonce: str, path: str,
                        expected_segments: int, digest: str) -> dict:
    """Count markers on the ACTUAL assembled string and build the content-light receipt.
    Invariant: open == close == expected_segments (the rendered web-segment count)."""
    opens = assembled_segment.count(f"<<EXT:{nonce}>>")
    closes = assembled_segment.count(f"<</EXT:{nonce}>>")
    balanced = (opens == closes == expected_segments)
    return {
        "path": path,
        "nonce": nonce,
        "rendered_web_segments": expected_segments,
        "open_markers": opens,
        "close_markers": closes,
        "chars": len(assembled_segment),
        "digest": digest,
        "balanced": balanced,
    }


def emit_receipt(receipt: dict) -> None:
    """Content-light log line. NO raw page text ever."""
    logger.info(
        "web_containment_applied path=%s nonce=%s rendered_web_segments=%s "
        "open_markers=%s close_markers=%s chars=%s digest=%s balanced=%s",
        receipt["path"], receipt["nonce"], receipt["rendered_web_segments"],
        receipt["open_markers"], receipt["close_markers"], receipt["chars"],
        receipt["digest"], receipt["balanced"],
    )


def containment_enabled() -> bool:
    return fetch_containment_enabled()
