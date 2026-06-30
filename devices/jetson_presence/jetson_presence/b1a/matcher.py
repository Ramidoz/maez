"""Pure cosine-distance match. No I/O, no models. The one fully host-testable
piece of the recognition logic. Distance in [0, 2]; match is distance < threshold."""
from __future__ import annotations

import math


def cosine_distance(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 1.0  # degenerate vector -> maximally dissimilar, never a match
    cos = max(-1.0, min(1.0, dot / (na * nb)))
    return 1.0 - cos


def is_match(distance: float, *, threshold: float) -> bool:
    return distance < threshold  # strict: at-threshold is NOT a match
