from __future__ import annotations

from enum import Enum


class PreferenceClass(Enum):
    QUIET_PERIOD = "quiet_period"
    ENCOURAGED_TOPIC = "encouraged_topic"
    DISCOURAGED_TOPIC = "discouraged_topic"
    LANE_CEILING = "lane_ceiling"
    LANE_FLOOR = "lane_floor"
    PROVIDER_RESTRICTION = "provider_restriction"


class PreferenceExpressedBy(Enum):
    OWNER_EXPLICIT = "owner_explicit"
    OWNER_EXPLICIT_REVISION = "owner_explicit_revision"
    OWNER_OBSERVED = "owner_observed"
    SYSTEM_DEFAULT = "system_default"
