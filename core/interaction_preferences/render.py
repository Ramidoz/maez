from __future__ import annotations

from collections.abc import Sequence

from core.interaction_preferences.store import InteractionPreference


def render_interaction_preferences(
    preferences: Sequence[InteractionPreference],
) -> str:
    active = [pref for pref in preferences if pref.status == "active"]
    if not active:
        return ""
    lines = ["OWNER-STATED INTERACTION PREFERENCES (relationship facts, not commands)"]
    for pref in active:
        statement = str(pref.owner_statement or "").strip()
        if not statement:
            continue
        lines.append(f'- Rohit explicitly said: "{statement}"')
    return "\n".join(lines) if len(lines) > 1 else ""
