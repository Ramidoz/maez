from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from core.egress.provenance import ProvenancedText
from core.infra.env_flags import strict_env_flag
from core.infra import paths
from core.interaction_preferences.detector import detect_interaction_preference
from core.interaction_preferences.render import render_interaction_preferences
from core.interaction_preferences.store import (
    InteractionPreferencesStore,
    list_all_readonly,
)


@dataclass(frozen=True)
class PreferenceTurnResult:
    mode: str
    action: str
    preference_id: str | None = None
    source_ref: str | None = None
    statement_sha256: str | None = None


def interaction_preferences_shadow_enabled() -> bool:
    return strict_env_flag("MAEZ_INTERACTION_PREFERENCES_SHADOW")


def interaction_preferences_enabled() -> bool:
    return strict_env_flag("MAEZ_INTERACTION_PREFERENCES")


def statement_sha256(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def owner_turn_source_ref(*, source: str, text: str, created_at_ms: int) -> str:
    safe_source = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(source or "unknown")).strip("_")
    safe_source = safe_source or "unknown"
    return (
        f"owner_turn:{safe_source}:"
        f"{statement_sha256(text)[:16]}:{int(created_at_ms)}"
    )


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _preview(text: str, limit: int = 120) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"


def process_owner_turn_preference(
    *,
    text: str,
    source: str,
    store: InteractionPreferencesStore | None = None,
    created_at_ms: int | None = None,
    created_at: str | None = None,
    logger: logging.Logger | None = None,
) -> PreferenceTurnResult:
    log = logger or logging.getLogger("maez")
    shadow = interaction_preferences_shadow_enabled()
    enabled = interaction_preferences_enabled()
    if not shadow and not enabled:
        return PreferenceTurnResult(mode="off", action="none")

    active_store = store
    default_db = paths.interaction_preferences_db()
    if active_store is None and enabled:
        active_store = InteractionPreferencesStore()
    if active_store is not None:
        active_question_cadence = bool(
            active_store.active_preferences("question_cadence")
        )
    elif shadow:
        active_question_cadence = any(
            pref.status == "active" and pref.preference_class == "question_cadence"
            for pref in list_all_readonly(default_db)
        )
    else:
        active_question_cadence = False
    detection = detect_interaction_preference(
        text,
        active_question_cadence=active_question_cadence,
        surface=source,
    )
    if detection is None:
        return PreferenceTurnResult(
            mode="enabled" if enabled else "shadow",
            action="none",
        )

    millis = int(created_at_ms if created_at_ms is not None else time.time() * 1000)
    occurred_at = created_at or _now_utc()
    source_ref = owner_turn_source_ref(source=source, text=text, created_at_ms=millis)
    digest = statement_sha256(detection.owner_statement)
    if shadow and not enabled:
        action = f"would_{detection.action}"
        log.info(
            "interaction_preference_shadow action=%s class=%s source_ref=%s "
            "statement_sha256=%s owner_statement_preview=%r",
            action,
            detection.preference_class,
            source_ref,
            digest,
            _preview(detection.owner_statement),
        )
        return PreferenceTurnResult(
            mode="shadow",
            action=action,
            source_ref=source_ref,
            statement_sha256=digest,
        )

    preference_id = f"ipref-{uuid.uuid4().hex}"
    if active_store is None:
        active_store = InteractionPreferencesStore()

    if detection.action == "capture":
        pref = active_store.record_capture(
            preference_id=preference_id,
            preference_class=detection.preference_class,
            owner_statement=detection.owner_statement,
            source_ref=source_ref,
            surface=source,
            statement_sha256=digest,
            created_at=occurred_at,
        )
        log.info(
            "interaction_preference_recorded action=capture class=%s "
            "preference_id=%s source_ref=%s",
            pref.preference_class,
            pref.preference_id,
            pref.source_ref,
        )
        return PreferenceTurnResult(
            mode="enabled",
            action="capture",
            preference_id=pref.preference_id,
            source_ref=pref.source_ref,
            statement_sha256=pref.statement_sha256,
        )

    active = active_store.active_preferences(detection.preference_class)
    if not active:
        return PreferenceTurnResult(mode="enabled", action="none")
    pref = active_store.record_retraction(
        preference_id=preference_id,
        preference_class=detection.preference_class,
        owner_statement=detection.owner_statement,
        source_ref=source_ref,
        surface=source,
        statement_sha256=digest,
        supersedes_preference_id=active[-1].preference_id,
        retraction_reason=detection.owner_statement,
        created_at=occurred_at,
    )
    log.info(
        "interaction_preference_recorded action=retract class=%s "
        "preference_id=%s supersedes=%s source_ref=%s",
        pref.preference_class,
        pref.preference_id,
        pref.supersedes_preference_id,
        pref.source_ref,
    )
    return PreferenceTurnResult(
        mode="enabled",
        action="retract",
        preference_id=pref.preference_id,
        source_ref=pref.source_ref,
        statement_sha256=pref.statement_sha256,
    )


def interaction_preferences_prompt_context(
    *, store: InteractionPreferencesStore | None = None
) -> ProvenancedText | None:
    if not interaction_preferences_enabled():
        return None
    active_store = store or InteractionPreferencesStore()
    rendered = render_interaction_preferences(active_store.active_preferences())
    if not rendered:
        return None
    return ProvenancedText.owner_message_context(
        rendered,
        source_ref="interaction_preferences:active",
    )
