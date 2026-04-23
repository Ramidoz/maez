# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
skills.surface — Maez's messaging-platform surface layer.

Vendors and adapts the Hermes Agent gateway platform code (MIT) so
Maez has a battle-tested Telegram bot surface without maintaining
3000+ lines of surface plumbing ourselves. See
`_LICENSE_ATTRIBUTION.md` for the full manifest of what was vendored.

The Maez-specific integration point is `maez_adapter.py` (TBD), which
implements the `MessageHandler` protocol exposed by
`BasePlatformAdapter` and routes each incoming message through Maez's
decision pipeline, capability registry, audit, and residue signals.
"""
from __future__ import annotations

# Public re-exports so callers write `from skills.surface import ...`
# rather than reaching into the vendored modules directly.
from skills.surface.platform_config import (
    Platform,
    PlatformConfig,
    HomeChannel,
)
from skills.surface.session import (
    SessionSource,
    build_session_key,
)
from skills.surface.platform_base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    ProcessingOutcome,
    SendResult,
)
from skills.surface.maez_adapter import (
    MaezMessageHandler,
    build_telegram_adapter,
    SURFACE_NAME,
)

__all__ = [
    "Platform",
    "PlatformConfig",
    "HomeChannel",
    "SessionSource",
    "build_session_key",
    "BasePlatformAdapter",
    "MessageEvent",
    "MessageType",
    "ProcessingOutcome",
    "SendResult",
    "MaezMessageHandler",
    "build_telegram_adapter",
    "SURFACE_NAME",
]
