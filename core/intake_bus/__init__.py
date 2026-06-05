"""Personal Data Intake Bus — the shared admission doorway for personal-data limbs."""

from core.intake_bus.admit import admit
from core.intake_bus.contract import (
    IntakeFact,
    IntakeOutcome,
    PromotionPosture,
    StoreAdapter,
)

__all__ = [
    "IntakeFact",
    "IntakeOutcome",
    "PromotionPosture",
    "StoreAdapter",
    "admit",
]
