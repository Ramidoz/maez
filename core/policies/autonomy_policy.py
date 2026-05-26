from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Iterable

from core.policies.autonomy_preferences import PreferenceClass, PreferenceExpressedBy


@dataclass(frozen=True)
class AutonomyCharterFloor:
    """Minimum policy values that observed preferences cannot reduce."""

    minimum_external_knowledge_daily_call_cap: int = 50
    minimum_owner_interrupting_daily_max_count: int = 3
    minimum_capability_acquisition_proposal_rate_per_day: int = 3
    floor_can_only_be_reduced_by: PreferenceExpressedBy = PreferenceExpressedBy.OWNER_EXPLICIT


FIRSTBORN_CHARTER_FLOOR = AutonomyCharterFloor()


@dataclass(frozen=True)
class AutonomyPolicy:
    bond_id: str
    external_knowledge_daily_call_cap: int = 50
    external_knowledge_cost_cap_cents: int = 100
    external_knowledge_allowed_providers: frozenset[str] = frozenset(
        {"public_web", "local_docs"}
    )
    owner_interrupting_quiet_hours: tuple[int, int] = (22, 7)
    owner_interrupting_focus_respect: bool = True
    owner_interrupting_daily_max_count: int = 5
    owner_interrupting_cooldown_minutes: int = 60
    owner_interrupting_minimum_importance: float = 0.3
    capability_acquisition_proposal_rate_per_day: int = 3
    capability_acquisition_classes_owner_will_consider: frozenset[str] = frozenset(
        {"tool", "documentation", "local_integration"}
    )
    signal_unknown_default_interior: bool = True
    signal_unknown_default_owner_interrupting: bool = False
    signal_unknown_override_threshold_importance: float = 0.7
    charter_floor: AutonomyCharterFloor = FIRSTBORN_CHARTER_FLOOR

    @classmethod
    def for_bond(cls, bond_id: str) -> "AutonomyPolicy":
        if not bond_id:
            raise ValueError("bond_id is required")
        policy = _POLICIES_BY_BOND.get(str(bond_id))
        if policy is not None:
            return policy
        return cls(bond_id=str(bond_id))


FIRSTBORN_AUTONOMY_POLICY = AutonomyPolicy(
    bond_id="firstborn",
    external_knowledge_daily_call_cap=200,
    external_knowledge_cost_cap_cents=500,
    owner_interrupting_quiet_hours=(23, 7),
    owner_interrupting_daily_max_count=10,
    owner_interrupting_cooldown_minutes=30,
    owner_interrupting_minimum_importance=0.2,
    capability_acquisition_proposal_rate_per_day=10,
    charter_floor=FIRSTBORN_CHARTER_FLOOR,
)


_POLICIES_BY_BOND: dict[str, AutonomyPolicy] = {
    FIRSTBORN_AUTONOMY_POLICY.bond_id: FIRSTBORN_AUTONOMY_POLICY
}


def register_policy_for_tests(policy: AutonomyPolicy) -> None:
    _POLICIES_BY_BOND[policy.bond_id] = policy


def clamp_to_charter_floor(
    policy: AutonomyPolicy,
    floor: AutonomyCharterFloor,
    *,
    expressed_by: PreferenceExpressedBy,
) -> AutonomyPolicy:
    if expressed_by is floor.floor_can_only_be_reduced_by:
        return policy
    return replace(
        policy,
        external_knowledge_daily_call_cap=max(
            int(policy.external_knowledge_daily_call_cap),
            int(floor.minimum_external_knowledge_daily_call_cap),
        ),
        owner_interrupting_daily_max_count=max(
            int(policy.owner_interrupting_daily_max_count),
            int(floor.minimum_owner_interrupting_daily_max_count),
        ),
        capability_acquisition_proposal_rate_per_day=max(
            int(policy.capability_acquisition_proposal_rate_per_day),
            int(floor.minimum_capability_acquisition_proposal_rate_per_day),
        ),
    )


@dataclass(frozen=True)
class FloorRevisionEvent:
    bond_id: str
    recorded_utc: datetime
    preference_class: PreferenceClass
    expressed_by: PreferenceExpressedBy
    target_field: str
    proposed_value: int
    pattern_digest: str


@dataclass(frozen=True)
class FloorRatificationCard:
    bond_id: str
    target_field: str
    current_floor_value: int
    proposed_floor_value: int
    consistent_event_count: int
    oldest_event_utc: datetime
    newest_event_utc: datetime
    card_action: str
    pattern_digest: str


_FLOOR_FIELDS = {
    "external_knowledge_daily_call_cap": "minimum_external_knowledge_daily_call_cap",
    "owner_interrupting_daily_max_count": "minimum_owner_interrupting_daily_max_count",
    "capability_acquisition_proposal_rate_per_day": (
        "minimum_capability_acquisition_proposal_rate_per_day"
    ),
}


def floor_ratification_surface(
    policy: AutonomyPolicy,
    events: Iterable[FloorRevisionEvent],
    *,
    now_utc: datetime,
    floor_ratification_threshold_days: int = 90,
    floor_ratification_minimum_consistent_events: int = 5,
) -> FloorRatificationCard | None:
    groups: dict[tuple[str, int], list[FloorRevisionEvent]] = {}
    for event in events:
        if event.bond_id != policy.bond_id:
            continue
        if event.preference_class is not PreferenceClass.LANE_FLOOR:
            continue
        if event.expressed_by is not PreferenceExpressedBy.OWNER_EXPLICIT_REVISION:
            continue
        if event.target_field not in _FLOOR_FIELDS:
            continue
        groups.setdefault((event.target_field, int(event.proposed_value)), []).append(event)

    for (target_field, proposed_value), matched in groups.items():
        if len(matched) < floor_ratification_minimum_consistent_events:
            continue
        matched = sorted(matched, key=lambda event: event.recorded_utc)
        span_days = (matched[-1].recorded_utc - matched[0].recorded_utc).days
        if span_days < floor_ratification_threshold_days:
            continue
        floor_field = _FLOOR_FIELDS[target_field]
        current_value = int(getattr(policy.charter_floor, floor_field))
        if proposed_value >= current_value:
            continue
        return FloorRatificationCard(
            bond_id=policy.bond_id,
            target_field=target_field,
            current_floor_value=current_value,
            proposed_floor_value=proposed_value,
            consistent_event_count=len(matched),
            oldest_event_utc=matched[0].recorded_utc,
            newest_event_utc=matched[-1].recorded_utc,
            card_action="autonomy_floor_ratification",
            pattern_digest=matched[-1].pattern_digest,
        )
    return None
