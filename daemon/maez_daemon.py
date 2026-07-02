#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
Maez Daemon — Always-on system-level AI agent.
Runs a continuous reasoning loop and exposes a health check endpoint.
"""

import collections
import hashlib
import hmac
import json
import logging
import re
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.evolution.subjective_duration import SubjectiveDurationOwnerAuth

# Decision 26: load ordinary config first, then credentials through the
# dedicated loader before importing surfaces that read os.environ.
try:
    from core.infra.secrets import (
        SECRET_NAMES as _MAEZ_SECRET_NAMES,
        SecretLoadError as _SecretLoadError,
        credential_health as _credential_health,
        load_ordinary_config_for_process as _load_ordinary_config_for_process,
        load_secrets_for_process as _load_secrets_for_process,
        sanitize_env,
    )

    _load_ordinary_config_for_process()
    _CREDENTIAL_REPORT = _load_secrets_for_process(
        required=set(),
        optional=set(_MAEZ_SECRET_NAMES),
        populate_environ=True,
    )
except Exception as _credential_bootstrap_exc:
    _CREDENTIAL_REPORT = None
    _CREDENTIAL_BOOTSTRAP_ERROR = _credential_bootstrap_exc
else:
    _CREDENTIAL_BOOTSTRAP_ERROR = None

import asyncio

import ollama
import websockets
from flask import Flask, jsonify, request, send_file

try:
    from core.paths import home as _maez_home

    sys.path.insert(0, str(_maez_home()))
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from memory.memory_manager import MemoryManager
from core.infra.env_flags import strict_env_flag

# 5x.F.A — cycle-scoped recall-context bag helpers. Hoisted to
# module-top because (a) the import is cheap and Chroma-free per
# the AST-parse isolation test, (b) F.A uses these at three sites
# (__init__ safety net, _loop reset, post-recall capture), and
# scattering local imports invited a future rename to break in
# two places without breaking in the third.
from core.memory.cycle_recall_context import (
    capture as _crc_capture,
    make_empty as _crc_empty,
)
from core.egress.provenance import ProvenancedText
from core.egress.telegram_egress import owner_multispan_envelope
from core.perception import snapshot as perception_snapshot, format_snapshot
from core.information_limb.calendar_v1 import build_calendar_health
from core.information_limb.calendar_store import CalendarStore, CalendarStoreError
from core.information_limb.calendar_v1_config import CalendarMode, resolve_calendar_mode
from core.information_limb.github_v1 import build_github_health
from core.information_limb.github_v1_config import GithubMode, resolve_github_mode
from core.information_limb.github_store import GithubStore, GithubStoreError
from core.information_limb import reddit_limb as _reddit_limb_mod
from core.information_limb import github_limb as _github_limb_mod
from core.information_limb import github_v1 as _github_v1_mod

_REDDIT_LIMB = _reddit_limb_mod.RedditLimb()
_GITHUB_LIMB = _github_limb_mod.GithubLimb()
from core.body.camera_presence_state import (
    CameraPresenceReading,
    CameraPresenceState,
    resolve_camera_presence_state,
)
from core.body.desktop_presence_state import (
    DesktopPresenceState,
    sample_desktop_presence,
)
from core.body.camera_presence_voice import (
    answer_camera_presence_question,
    camera_presence_voice_health,
)
from core.safety.clinical_boundary import (
    PrivateThoughtsCrisisSignalWriter,
    clinical_boundary_health,
    guard_owner_text,
)
from core.time.temporal_spine import temporal_spine_health
from core.routing.llm_client import served_model_alias
from core.routing.recall_stack_config import resolve_recall_stack
from core.routing.memory_fresh_conflict import (
    check_memory_fresh_conflict,
    memory_fresh_conflict_sense_enabled,
)
from core.voice_continuity import voice_continuity_health
from core.health.fd_forensics import fd_forensics_snapshot
from core.governance.successor_governance import successor_governance_health
from core.governance.operator_user_boundary import (
    GUARDED_SELF_MODIFICATION_PAUSED_MODE,
    VOICE_SEAT_WORK_CLASSES,
    build_operator_health_projection,
    live_webauthn_ceremony_enabled,
    s7_ceremony_deferred_response,
)
from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore
from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService
from core.governance.s7_webauthn_verifier import S7ProductionWebAuthnVerifier
from core.cognition.cycle_doorman import (
    DoormanSignals,
    DoormanVerdict,
    ReasonCode as DoormanReasonCode,
    decide as _decide_cycle_doorman,
    salient_perception_changed,
)
from skills.telegram_voice import TelegramVoice
from skills.telegram_public import MaezPublicBot
from core.action_engine import ActionEngine
from skills.screen_perception import observe as screen_observe, ScreenObservation
from skills.github_skill import GitHubSkill
from skills.reddit_skill import RedditSkill
from skills.followup_queue import FollowUpQueue
from skills.git_awareness import format_for_context as git_context
from skills.dev_notifier import send_dev
from core.continuity import (
    load_capsule as continuity_load,
    format_for_prompt as continuity_format,
    checkpoint as continuity_checkpoint,
    graceful_shutdown_write as continuity_shutdown,
    archive_capsule as continuity_archive,
    CONTINUITY_CHECKPOINT_INTERVAL,
    POST_RESTART_INJECTION_CYCLES,
)
from skills.disk_cleanup import scan as disk_scan, format_telegram_message as disk_msg
from skills.self_analysis import analyze as self_analyze, format_for_telegram as analysis_telegram
from skills.wake_word import start as wake_word_start, stop as wake_word_stop
from skills.voice_output import (
    initialize as voice_output_init,
    speak,
    shutdown as voice_output_shutdown,
)

# --- Paths ---
try:
    from core.paths import home as _paths_home

    BASE_DIR = _paths_home()
except Exception:
    BASE_DIR = Path(__file__).resolve().parent.parent
SOUL_PATH = BASE_DIR / "config" / "soul.md"
LOG_PATH = BASE_DIR / "logs" / "maez.log"
MEMORY_DIR = BASE_DIR / "memory"
PID_FILE = BASE_DIR / "daemon" / "maez.pid"
SHUTDOWN_FILE = BASE_DIR / "daemon" / "last_shutdown"
LEDGER_DB_PATH = Path(os.environ.get("MAEZ_LEDGER_DB_PATH") or (MEMORY_DIR / "ledger.db"))
M1_ALLOWED_PROMOTION_SOURCES = frozenset({"telegram_surface", "telegram_text"})

StoreSpec = collections.namedtuple(
    "StoreSpec",
    ["content", "provenance_source", "trust_tier", "turn_link_id", "is_owner_record"],
)


def decide_turn_storage(*, source, text, reply, web_grounded, hygiene_enabled):
    """Decide how to persist a finished Telegram turn.

    Web-grounded turns (flag on) split into two linked records so Maez's reply is
    stored untrusted under self_web_claim WITHOUT the owner's words inheriting that
    downgrade — and WITHOUT writing the old combined record (no duplicate). All other
    cases keep the single combined lived record."""
    if hygiene_enabled and web_grounded:
        import uuid as _uuid
        link = _uuid.uuid4().hex
        return [
            StoreSpec(f"the owner ({source}): {text}", "user_utterance", "lived", link, True),
            StoreSpec(f"Maez: {reply}", "self_web_claim", "untrusted", link, False),
        ]
    return [
        StoreSpec(f"the owner ({source}): {text}\nMaez: {reply}", "user_utterance", "lived", None, True),
    ]


def m1_raw_memory_id_for_promotion(*, owner_id, reply_id=None):
    """M1 lived-episode promotion lineage may cite ONLY the owner record, never the
    self_web_claim reply — so a web-grounded reply cannot relaunder into a lived
    episode's source_memory_ids. reply_id is accepted only to make the exclusion
    explicit and unit-testable; it is deliberately never returned."""
    return owner_id


CALENDAR_MODE = resolve_calendar_mode(os.environ)
GITHUB_MODE = resolve_github_mode(os.environ)
CALENDAR_STORE_DB_PATH = Path(
    os.environ.get("MAEZ_CALENDAR_STORE_DB") or (MEMORY_DIR / "calendar_v1.db")
)
GITHUB_STORE_DB_PATH = Path(os.environ.get("MAEZ_GITHUB_STORE_DB") or (MEMORY_DIR / "github_v1.db"))
RECALL_SHADOW_FLAG = "MAEZ_RECALL_SHADOW_ENABLED"
RECALL_SHADOW_BUDGET_MS = 250

# --- Constants ---
from core.model_config import PRIMARY_MODEL as MODEL  # single source of truth — /etc/maez/model.env
from core.memory.episodes import EpisodeStore
from core.memory.m1_lived_episode_promotion import (
    M1Config,
    M1LivedEpisodePromoter,
    M1PromotionStore,
    biography_staleness_health,
    m1_observability_health,
)
from core.memory.relationship_graph import RelationshipGraph
from core.memory.lived_recall import build_lived_recall_brief
from core.memory.temporal_anchor_recall import build_temporal_anchor_recall_brief
from core.memory.working_self import GoalHierarchy, assemble_goals
from core.safety.temporal_fragment_guard import (
    extract_current_message_context,
    guard_temporal_ars_fragment,
)
from core.evolution.wondering_pursuit import (
    decide_pursuit,
    format_pursuit_utterance,
    load_last_pursuit_at,
    save_last_pursuit_at,
)
from core.policies.extraction_gate import (
    OutreachLane,
    evaluate_extraction_gate,
)
from core.policies.reflection_audit import ReflectionAudit, ReflectionDecision
from core.policies.signal_gate import OutreachLedger, OwnerState, PriorityClass, SignalQuality
from core.turn_traces import (
    AuditInfo,
    Trace,
    ToolCall,
    default_writer,
)
from core.turn_traces.trace_schema import (
    extract_evidence_ids as _trace_extract_evidence_ids,
    hash_text as _trace_hash_text,
)
from core.infra.http_security import (
    apply_local_cors_headers,
    reject_untrusted_browser_write,
)

LOOP_INTERVAL = 30  # seconds
WANT_PURSUIT_COOLDOWN_S = 6 * 3600
HEALTH_PORT = 11435
WS_PORT = 11436
S7_INTERNAL_CHANNEL_HEADER = "X-Maez-S7-Internal-Channel"
S7_INTERNAL_CHANNEL_TOKEN_ENV = "S7_INTERNAL_CHANNEL_TOKEN"
S7_WEBAUTHN_STORE_ROOT_ENV = "S7_WEBAUTHN_STORE_ROOT"
S7_WEBAUTHN_PROOF_ROUTES_ENV = "S7_WEBAUTHN_PROOF_ROUTES"


def _is_ws_invalid_handshake_noise(record: logging.LogRecord) -> bool:
    """Classify browser/health-probe hits on the WS port without hiding real WS faults."""
    if record.name != "websockets.server":
        return False
    if "opening handshake failed" not in record.getMessage().lower():
        return False
    if not record.exc_info:
        return True

    exc = record.exc_info[1]
    while exc is not None:
        exc_name = exc.__class__.__name__
        exc_text = str(exc).lower()
        if exc_name in {"InvalidMessage", "EOFError"}:
            return True
        if "did not receive a valid http request" in exc_text:
            return True
        exc = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    return False


def _s7_internal_channel_trusted(req) -> bool:
    """Return true only for the reviewed cockpit-to-daemon private channel."""
    token = os.environ.get(S7_INTERNAL_CHANNEL_TOKEN_ENV, "")
    presented = req.headers.get(S7_INTERNAL_CHANNEL_HEADER, "")
    if not token:
        if presented:
            logger.warning(
                "S7 internal channel token absent from os.environ "
                "(purged or unprovisioned); rejecting internal channel request"
            )
        return False
    if not presented:
        return False
    if req.headers.get("Origin"):
        return False
    return secrets_compare(token, presented)


def secrets_compare(expected: str, presented: str) -> bool:
    return hmac.compare_digest(expected.encode("utf-8"), presented.encode("utf-8"))


def _s7_webauthn_store_root() -> Path:
    return Path(os.environ.get(S7_WEBAUTHN_STORE_ROOT_ENV, "memory/s7_1_webauthn"))


def _s7_webauthn_proof_routes_enabled() -> bool:
    return os.environ.get(S7_WEBAUTHN_PROOF_ROUTES_ENV) == "1"


def _s7_route_error(error: str, status_code: int, **extra):
    return SimpleNamespace(
        ok=False,
        status_code=status_code,
        body={"ok": False, "error": error, **extra},
    )


def _s7_route_material(**kwargs):
    return SimpleNamespace(ok=True, kwargs=kwargs)


def _s7_route_session_binding(request_json: dict):
    session_binding = str(request_json.get("session_binding") or "")
    if not session_binding:
        return None
    return session_binding


def _s7_route_authority_context(now: str, *, expires_at: str, credential_ref: str | None = None):
    from core.governance import operator_user_boundary as s7

    return s7.AuthorityContext(
        actor_id="founder",
        actor_handle_hmac="hmac:s7:founder:" + hashlib.sha256(
            b"s7.1.local.webauthn.founder"
        ).hexdigest(),
        role_names=("bonded_user",),
        grant_source="founder_webauthn",
        allowed_scopes=("operator_health",),
        auth_method="founder_webauthn",
        surface="cockpit",
        credential_ref=credential_ref,
        created_at=now,
        expires_at=expires_at,
        verified=True,
        verification_reason="founder_local_webauthn_challenge_pending",
    )


def _s7_single_enabled_primary_credential_ref(store: S7WebAuthnBootstrapStore) -> str | None:
    primary_refs = tuple(
        record.credential_ref
        for record in store.list_credentials()
        if record.enabled
        and record.credential_kind == "primary"
        and "bonded_user" in record.role_names
    )
    return primary_refs[0] if len(primary_refs) == 1 else None


def _s7_single_enabled_backup_credential_ref(store: S7WebAuthnBootstrapStore) -> str | None:
    backup_refs = tuple(
        record.credential_ref
        for record in store.list_credentials()
        if record.enabled
        and record.credential_kind == "backup"
        and "bonded_user" in record.role_names
    )
    return backup_refs[0] if len(backup_refs) == 1 else None


def _s7_route_expires_at(now: str) -> str:
    try:
        return (datetime.fromisoformat(now) + timedelta(minutes=5)).isoformat()
    except Exception:
        return (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()


def _s7_route_pipeline_for_daemon(daemon):
    telegram = getattr(daemon, "telegram", None)
    return telegram._get_pipeline() if telegram else None


def _s7_route_voice_consultation(pipe, card, envelope):
    producer = getattr(pipe, "_s7_voice_consultation_for_card", None)
    if not callable(producer):
        return None
    return producer(card, envelope)


def _s7_guarded_execution_consumer_live(pipe, card_store, dream) -> bool:
    if card_store is None or pipe is None:
        return False
    required_pipe_methods = (
        "_s7_request_envelope_for_card",
        "_execution_params_for_card",
        "_s7_voice_consultation_for_card",
        "_consume_s7_execution_authorization",
    )
    if not all(callable(getattr(pipe, name, None)) for name in required_pipe_methods):
        return False
    # D15's autonomous/direct lane must be explicitly live before health may
    # claim L8 retired. Having DreamState helpers alone is not enough; the
    # route/producer must opt in after it wires artifact consumption end to end.
    if getattr(pipe, "s7_autonomous_guarded_write_consumer_live", False) is not True:
        return False
    required_dream_methods = (
        "build_apply_s7_envelope",
        "apply_proposal",
        "build_section_edit_s7_envelope",
        "apply_section_edit_proposal",
    )
    return dream is not None and all(
        callable(getattr(dream, name, None)) for name in required_dream_methods
    )


def _s7_authorization_route_material(
    daemon,
    req,
    *,
    request_id: str,
    now: str,
    store: S7WebAuthnBootstrapStore,
    allow_consumed_authorization_challenge: bool = False,
):
    from core.governance import operator_user_boundary as s7

    request_json = req.get_json(silent=True) or {}
    if not isinstance(request_json, dict):
        return _s7_route_error("s7_schema_invalid", 400, detail="json_object_required")
    session_binding = _s7_route_session_binding(request_json)
    if not session_binding:
        return _s7_route_error("s7_schema_invalid", 400, detail="session_binding")
    internal_channel_binding = req.headers.get(S7_INTERNAL_CHANNEL_HEADER, "")
    pipe = _s7_route_pipeline_for_daemon(daemon)
    if pipe is None or getattr(pipe, "card_store", None) is None:
        return _s7_route_error("s7_execution_edge_unavailable", 503)
    card = pipe.card_store.get(request_id)
    if card is None:
        return _s7_route_error("s7_request_not_found", 404)
    requires_s7 = getattr(pipe, "_card_requires_s7_authorization", lambda _card: True)(card)
    if requires_s7 is not True:
        return _s7_route_error("s7_authorization_not_required", 409)
    action = getattr(card, "action", None)
    card_params = dict(getattr(card, "params", None) or {})
    allow_degraded_primary_only = action == "register_backup_webauthn_credential"
    allow_degraded_backup_only = (
        action == "disable_founder_webauthn_credential"
        and card_params.get("credential_kind") == "backup"
    )
    credential_ref = str(request_json.get("credential_ref") or "")
    if not credential_ref and allow_degraded_primary_only:
        credential_ref = _s7_single_enabled_primary_credential_ref(store) or ""
    if not credential_ref and allow_degraded_backup_only:
        credential_ref = _s7_single_enabled_backup_credential_ref(store) or ""
    if not credential_ref:
        allowed_credentials = store.allow_credentials_for_authorization()
        credential_ref = allowed_credentials[0] if allowed_credentials else ""

    envelope = pipe._s7_request_envelope_for_card(card)
    maez_voice_consultation = _s7_route_voice_consultation(pipe, card, envelope)
    if envelope.derived_work_class in s7.VOICE_SEAT_WORK_CLASSES and maez_voice_consultation is None:
        return _s7_route_error(
            "s7_voice_seat_unresolved",
            409,
            maez_objection_state="not_determined",
        )

    challenge_id = str(request_json.get("challenge_id") or "")
    challenge = None
    if challenge_id:
        if allow_consumed_authorization_challenge is True:
            challenge = store.consumed_authorization_challenge_for_artifact(
                challenge_id=challenge_id,
                session_binding=session_binding,
                internal_channel_binding=internal_channel_binding,
                now=now,
            )
        else:
            challenge = store.authorization_challenge_for_finish(
                challenge_id=challenge_id,
                session_binding=session_binding,
                internal_channel_binding=internal_channel_binding,
                now=now,
            )
    nonce = str((challenge or {}).get("nonce") or hashlib.sha256(
        f"{request_id}|{now}|{session_binding}".encode("utf-8")
    ).hexdigest())
    expires_at = str((challenge or {}).get("expires_at") or _s7_route_expires_at(now))
    rendered_at = str((challenge or {}).get("created_at") or now)
    authority_context = _s7_route_authority_context(
        envelope.created_at,
        expires_at=expires_at,
        credential_ref=credential_ref or None,
    )
    action_params = pipe._execution_params_for_card(card)
    action_params_hash = s7.canonical_hash(action_params)
    rendered = s7.render_request_statement(
        envelope=envelope,
        surface="cockpit",
        origin="http://localhost:11437",
        action_params_hash=action_params_hash,
        authority_context=authority_context,
        maez_voice_consultation=maez_voice_consultation,
        nonce=nonce,
        expires_at=expires_at,
        rendered_at=rendered_at,
    )
    return _s7_route_material(
        card=card,
        pipe=pipe,
        envelope=envelope,
        rendered_statement=rendered,
        action_params=action_params,
        action_params_hash=action_params_hash,
        authority_context=authority_context,
        precondition_hash=envelope.precondition_hash,
        maez_voice_consultation=maez_voice_consultation,
        session_binding=session_binding,
        internal_channel_binding=internal_channel_binding,
        request_json=request_json,
        allow_degraded_primary_only=allow_degraded_primary_only,
        allow_degraded_backup_only=allow_degraded_backup_only,
    )


def _s7_voice_source_validation_for_material(
    *,
    store: S7WebAuthnBootstrapStore,
    material,
    now: str,
):
    from core.governance import operator_user_boundary as s7
    from core.governance.s7_guarded_execution import (
        S7GuardedStateStore,
        S7SemanticReaderAttemptStore,
        S7VoiceBundleUseStore,
        S7VoiceConsultationBundleStore,
        derive_s7_voice_source_bundle_hash_binding,
        validate_s7_voice_source_bundle,
    )

    bundle_store = S7VoiceConsultationBundleStore(store.db_path)
    bundle_use_store = S7VoiceBundleUseStore(store.db_path)
    attempt_store = S7SemanticReaderAttemptStore(store.db_path)
    binding = derive_s7_voice_source_bundle_hash_binding(
        rendered_statement=material.kwargs["rendered_statement"],
        envelope=material.kwargs["envelope"],
        maez_voice_consultation=material.kwargs["maez_voice_consultation"],
        authority_context=material.kwargs["authority_context"],
        precondition_hash=material.kwargs["precondition_hash"],
    )
    validation = validate_s7_voice_source_bundle(
        consultation=material.kwargs["maez_voice_consultation"],
        bundle_store=bundle_store,
        bundle_use_store=bundle_use_store,
        semantic_reader_attempt_store=attempt_store,
        expected_binding=binding,
        now=now,
    )
    guarded_store = S7GuardedStateStore(
        authorization_store=s7.S7AuthorizationStore(store.db_path),
        voice_bundle_use_store=bundle_use_store,
    )
    reservation_token = s7.canonical_hash({
        "purpose": "s7.3.voice_bundle_reservation",
        "request_id": material.kwargs["rendered_statement"].request_id,
        "rendered_text_hash": material.kwargs["rendered_statement"].rendered_text_hash,
        "source_ref_hash": binding.source_ref_hash,
    })
    return _s7_route_material(
        source_bundle_validation=validation,
        guarded_store=guarded_store,
        source_ref_hash=binding.source_ref_hash,
        reservation_token=reservation_token,
    )


def _s7_persist_voice_source_bundle_for_material(
    *,
    store: S7WebAuthnBootstrapStore,
    material,
    now: str,
) -> bool:
    persister = getattr(material.kwargs.get("pipe"), "_persist_s7_voice_source_bundle_for_card", None)
    if not callable(persister):
        return False
    return persister(
        card=material.kwargs["card"],
        db_path=store.db_path,
        rendered_statement=material.kwargs["rendered_statement"],
        envelope=material.kwargs["envelope"],
        maez_voice_consultation=material.kwargs["maez_voice_consultation"],
        authority_context=material.kwargs["authority_context"],
        precondition_hash=material.kwargs["precondition_hash"],
        now=now,
    ) is not None


def _s7_founder_visible_voice_payload_for_material(material):
    from core.governance import operator_user_boundary as s7

    pipe = material.kwargs.get("pipe")
    envelope = material.kwargs.get("envelope")
    pending = getattr(pipe, "_s7_pending_voice_source_bundles", {})
    if not isinstance(pending, dict) or envelope is None:
        return {}
    entry = pending.get(getattr(envelope, "request_id", None))
    if not isinstance(entry, dict):
        return {}
    raw_response_text = entry.get("raw_response_text")
    semantic_reader_attempt = entry.get("semantic_reader_attempt")
    if not isinstance(raw_response_text, str):
        return {}
    payload = {
        "maez_voice_raw_response": raw_response_text,
        "maez_voice_raw_response_hash": s7.canonical_hash(raw_response_text),
        "maez_voice_source_ref_hash": entry.get("source_ref_hash"),
    }
    if semantic_reader_attempt is not None:
        payload.update({
            "maez_voice_reader_outcome": getattr(
                semantic_reader_attempt,
                "raw_semantic_reader_outcome",
                None,
            ),
            "maez_voice_grounding_quote": getattr(
                semantic_reader_attempt,
                "grounding_response_span_quote",
                None,
            ),
            "maez_voice_grounding_offset": getattr(
                semantic_reader_attempt,
                "grounding_response_span_offset",
                None,
            ),
        })
    renderer = getattr(pipe, "_s7_rendered_proposal_for_card", None)
    if callable(renderer):
        try:
            payload["maez_voice_rendered_proposal"] = renderer(
                material.kwargs.get("card"),
                envelope,
            )
        except Exception:
            pass
    return payload


def _s7_founder_seen_voice_hash_valid(material, *, store: S7WebAuthnBootstrapStore | None = None) -> bool:
    request_json = material.kwargs.get("request_json") or {}
    if not isinstance(request_json, dict):
        return False
    seen_hash = str(request_json.get("maez_voice_raw_response_hash") or "")
    if not seen_hash:
        return False
    if store is not None:
        try:
            consultation = material.kwargs.get("maez_voice_consultation")
            source_ref_hash = getattr(consultation, "source_ref_hash", None)
            if isinstance(source_ref_hash, str) and source_ref_hash:
                from core.governance.s7_guarded_execution import S7VoiceConsultationBundleStore

                bundle_store = S7VoiceConsultationBundleStore(store.db_path)
                bundle = bundle_store.get_for_source_ref(source_ref_hash)
                if bundle is not None and bundle.raw_response_hash:
                    return seen_hash == bundle.raw_response_hash
        except Exception:
            return False
    payload = _s7_founder_visible_voice_payload_for_material(material)
    if not payload.get("maez_voice_raw_response_hash"):
        return False
    return seen_hash == payload.get("maez_voice_raw_response_hash")



def _s7_backup_registration_authorization(daemon, req, *, now: str, store: S7WebAuthnBootstrapStore):
    from core.governance import operator_user_boundary as s7

    request_json = req.get_json(silent=True) or {}
    if not isinstance(request_json, dict) or request_json.get("registration_class") != "backup":
        return _s7_route_material(s7_execution_authorization=None)
    artifact_id = str(request_json.get("s7_authorization_artifact_id") or "")
    request_id = str(request_json.get("backup_authorization_request_id") or "")
    if not artifact_id:
        return _s7_route_error("s7_schema_invalid", 400, detail="s7_authorization_artifact_id")
    if not request_id:
        return _s7_route_error("s7_schema_invalid", 400, detail="backup_authorization_request_id")

    auth_request_json = {
        "session_binding": str(
            request_json.get("authorization_session_binding")
            or request_json.get("session_binding")
            or ""
        ),
        "challenge_id": str(request_json.get("authorization_challenge_id") or ""),
        "credential_ref": str(request_json.get("authorization_credential_ref") or ""),
    }

    class _AuthorizationRequest:
        headers = req.headers

        @staticmethod
        def get_json(*_args, **_kwargs):
            return auth_request_json

    material = _s7_authorization_route_material(
        daemon,
        _AuthorizationRequest(),
        request_id=request_id,
        now=now,
        store=store,
        allow_consumed_authorization_challenge=True,
    )
    if material.ok is not True:
        return material
    return _s7_route_material(
        s7_execution_authorization=s7.S7ExecutionAuthorization(
            store=s7.S7AuthorizationStore(store.db_path),
            artifact_id=artifact_id,
            rendered=material.kwargs["rendered_statement"],
            action_params_hash=material.kwargs["action_params_hash"],
            authority_context=material.kwargs["authority_context"],
            precondition_hash=material.kwargs["precondition_hash"],
            derived_work_class=material.kwargs["rendered_statement"].derived_work_class,
            derived_aggregation_group=material.kwargs[
                "rendered_statement"
            ].derived_aggregation_group,
            now=now,
        )
    )


def _s7_guarded_card_execution_authorization(
    daemon,
    req,
    *,
    request_id: str,
    now: str,
    store: S7WebAuthnBootstrapStore,
):
    from core.governance import operator_user_boundary as s7

    request_json = req.get_json(silent=True) or {}
    if not isinstance(request_json, dict):
        return _s7_route_error("s7_schema_invalid", 400, detail="json_object_required")
    artifact_id = str(request_json.get("s7_authorization_artifact_id") or "")
    if not artifact_id:
        return _s7_route_error("s7_schema_invalid", 400, detail="s7_authorization_artifact_id")
    challenge_id = str(
        request_json.get("authorization_challenge_id")
        or request_json.get("challenge_id")
        or ""
    )
    if not challenge_id:
        return _s7_route_error("s7_schema_invalid", 400, detail="authorization_challenge_id")
    session_binding = str(
        request_json.get("authorization_session_binding")
        or request_json.get("session_binding")
        or ""
    )
    if not session_binding:
        return _s7_route_error("s7_schema_invalid", 400, detail="session_binding")
    credential_ref = str(
        request_json.get("authorization_credential_ref")
        or request_json.get("credential_ref")
        or ""
    )
    if not credential_ref:
        return _s7_route_error("s7_schema_invalid", 400, detail="authorization_credential_ref")

    auth_request_json = {
        "session_binding": session_binding,
        "challenge_id": challenge_id,
        "credential_ref": credential_ref,
    }

    class _AuthorizationRequest:
        headers = req.headers

        @staticmethod
        def get_json(*_args, **_kwargs):
            return auth_request_json

    material = _s7_authorization_route_material(
        daemon,
        _AuthorizationRequest(),
        request_id=request_id,
        now=now,
        store=store,
        allow_consumed_authorization_challenge=True,
    )
    if material.ok is not True:
        return material
    rendered = material.kwargs["rendered_statement"]
    if rendered.rollback_path_class in {"no_rollback_needed", "no_safe_rollback"}:
        return _s7_route_error(
            "s7_rollback_plan_required",
            409,
            rollback_path_class=rendered.rollback_path_class,
        )
    authorization = s7.S7ExecutionAuthorization(
        store=s7.S7AuthorizationStore(store.db_path),
        artifact_id=artifact_id,
        rendered=rendered,
        action_params_hash=material.kwargs["action_params_hash"],
        authority_context=material.kwargs["authority_context"],
        precondition_hash=material.kwargs["precondition_hash"],
        derived_work_class=rendered.derived_work_class,
        derived_aggregation_group=rendered.derived_aggregation_group,
        now=now,
    )
    return _s7_route_material(
        s7_execution_authorization=authorization,
        text=str(request_json.get("text") or "yes"),
    )


def _s7_create_backup_registration_card(daemon):
    from core.governance.s7_webauthn_ceremony import backup_registration_action_params

    telegram = getattr(daemon, "telegram", None)
    pipe = telegram._get_pipeline() if telegram else None
    card_store = getattr(pipe, "card_store", None)
    if card_store is None:
        return _s7_route_error("s7_pending_card_store_unavailable", 503)

    card = card_store.create_card(
        action="register_backup_webauthn_credential",
        params=backup_registration_action_params(),
        reason="S7.1 backup WebAuthn credential enrollment requires founder authorization.",
        plain_english="Authorize S7.1 backup WebAuthn credential enrollment.",
        channel="cockpit_s7_1_manual_proof",
        chat_id="s7.1-manual-proof",
        user_id="rohit",
    )
    return SimpleNamespace(
        ok=True,
        status_code=201,
        body={
            "ok": True,
            "request_id": card.request_id,
            "action": "register_backup_webauthn_credential",
            "status": getattr(getattr(card, "status", None), "value", getattr(card, "status", "")),
        },
    )


def _s7_create_disable_credential_card(daemon, req, *, now: str):
    from core.governance.s7_webauthn_ceremony import disable_credential_action_params

    request_json = req.get_json(silent=True) or {}
    if not isinstance(request_json, dict):
        return _s7_route_error("s7_schema_invalid", 400, detail="json_object_required")
    credential_ref = str(request_json.get("credential_ref") or "")
    credential_kind = str(request_json.get("credential_kind") or "")
    if credential_kind not in {"primary", "backup"}:
        return _s7_route_error("s7_schema_invalid", 400, detail="credential_kind")
    try:
        params = disable_credential_action_params(
            credential_ref=credential_ref,
            credential_kind=credential_kind,
        )
    except ValueError as exc:
        return _s7_route_error("s7_schema_invalid", 400, detail=str(exc))

    telegram = getattr(daemon, "telegram", None)
    pipe = telegram._get_pipeline() if telegram else None
    card_store = getattr(pipe, "card_store", None)
    if card_store is None:
        return _s7_route_error("s7_pending_card_store_unavailable", 503)

    card = card_store.create_card(
        action="disable_founder_webauthn_credential",
        params=params,
        reason=f"S7.1 manual proof disables the {credential_kind} WebAuthn credential.",
        plain_english=f"Authorize disabling the S7.1 {credential_kind} WebAuthn credential.",
        channel="cockpit_s7_1_manual_proof",
        chat_id="s7.1-manual-proof",
        user_id="rohit",
    )
    return SimpleNamespace(
        ok=True,
        status_code=201,
        body={
            "ok": True,
            "request_id": card.request_id,
            "action": "disable_founder_webauthn_credential",
            "credential_ref": credential_ref,
            "credential_kind": credential_kind,
            "created_at": now,
            "status": getattr(getattr(card, "status", None), "value", getattr(card, "status", "")),
        },
    )


def _s7_disable_credential_for_proof(daemon, req, *, now: str, store: S7WebAuthnBootstrapStore):
    from core.governance import operator_user_boundary as s7

    request_json = req.get_json(silent=True) or {}
    if not isinstance(request_json, dict):
        return _s7_route_error("s7_schema_invalid", 400, detail="json_object_required")
    artifact_id = str(request_json.get("s7_authorization_artifact_id") or "")
    request_id = str(request_json.get("disable_authorization_request_id") or "")
    requested_credential_ref = str(request_json.get("credential_ref") or "")
    if not artifact_id:
        return _s7_route_error("s7_schema_invalid", 400, detail="s7_authorization_artifact_id")
    if not request_id:
        return _s7_route_error("s7_schema_invalid", 400, detail="disable_authorization_request_id")

    auth_request_json = {
        "session_binding": str(request_json.get("authorization_session_binding") or ""),
        "challenge_id": str(request_json.get("authorization_challenge_id") or ""),
        "credential_ref": str(request_json.get("authorization_credential_ref") or ""),
    }

    class _AuthorizationRequest:
        headers = req.headers

        @staticmethod
        def get_json(*_args, **_kwargs):
            return auth_request_json

    material = _s7_authorization_route_material(
        daemon,
        _AuthorizationRequest(),
        request_id=request_id,
        now=now,
        store=store,
        allow_consumed_authorization_challenge=True,
    )
    if material.ok is not True:
        return material
    action_params = dict(material.kwargs["action_params"])
    target_credential_ref = str(action_params.get("credential_ref") or "")
    if requested_credential_ref and requested_credential_ref != target_credential_ref:
        return _s7_route_error("s7_d12_binding_mismatch", 409)
    grant, _callback_result = s7.S7AuthorizationStore(store.db_path).consume_for_execution(
        artifact_id,
        rendered=material.kwargs["rendered_statement"],
        action_params_hash=material.kwargs["action_params_hash"],
        authority_context=material.kwargs["authority_context"],
        precondition_hash=material.kwargs["precondition_hash"],
        derived_work_class=material.kwargs["rendered_statement"].derived_work_class,
        derived_aggregation_group=material.kwargs[
            "rendered_statement"
        ].derived_aggregation_group,
        now=now,
    )
    if grant is None:
        return _s7_route_error("s7_authorization_required", 403)
    if not s7.consume_execution_grant_for_action(
        grant,
        action="disable_founder_webauthn_credential",
        params=action_params,
    ):
        return _s7_route_error("s7_authorization_required", 403)
    disabled = store.disable_credential(
        target_credential_ref,
        authorization_id=artifact_id,
        now=now,
    )
    if disabled.get("ok") is not True:
        return _s7_route_error(str(disabled.get("error") or "s7_credential_setup_incomplete"), 409)
    recovery = store.credential_recovery_state()
    return SimpleNamespace(
        ok=True,
        status_code=200,
        body={
            "ok": True,
            "credential_ref": target_credential_ref,
            "artifact_id": artifact_id,
            "ceremony_mode": recovery["mode"],
            "manual_recovery_required": recovery["manual_recovery_required"],
            "manual_recovery_cause": recovery["manual_recovery_cause"],
            "active_credential_count": recovery["active_credential_count"],
        },
    )


class _WebsocketInvalidHandshakeFilter(logging.Filter):
    _maez_ws_invalid_handshake_filter = True

    def filter(self, record: logging.LogRecord) -> bool:
        return not _is_ws_invalid_handshake_noise(record)


def _install_websocket_noise_filter() -> None:
    ws_logger = logging.getLogger("websockets.server")
    if any(
        getattr(existing, "_maez_ws_invalid_handshake_filter", False)
        for existing in ws_logger.filters
    ):
        return
    ws_logger.addFilter(_WebsocketInvalidHandshakeFilter())


def _authoritative_tool_reply(tool_calls: "list[dict] | None") -> str:
    """Return a final reply when a deterministic tool already answered.

    This is deliberately narrow. Some tool results need synthesis, but
    volatile numeric facts should not be handed back to the LLM to
    paraphrase from memory or web snippets. The tool output already carries
    the value, timestamp/date, and source.
    """
    for call in tool_calls or []:
        if not isinstance(call, dict):
            continue
        tool_name = str(call.get("name") or "")
        if tool_name not in {"convert_currency", "quote_stock"}:
            continue
        output = str(call.get("output_summary") or "").strip()
        error = str(call.get("error_summary") or "").strip()
        status = str(call.get("status") or "").lower()
        if status == "ok" and output:
            return output
        noun = "stock quote" if tool_name == "quote_stock" else "currency conversion"
        if error:
            return f"I could not get a live {noun}: {error}"
        if output:
            return f"I could not get a live {noun}: {output}"
    return ""


def _daemon_parallel_web_search_enabled(
    transcript: str = "",
    *,
    recall_stack_config=None,
) -> bool:
    """Return whether daemon synthesis may run its legacy web-search side path."""
    if recall_stack_config is None:
        from core.routing.recall_stack_config import resolve_recall_stack

        recall_stack_config = resolve_recall_stack()
    return not (
        recall_stack_config.triad_on and bool((transcript or "").strip())
    )


def _routing_quality_from_gate(*, caveated_unsupported, web_quality, result_count):
    """Calibrated teacher signal (Slice 1a). Returns (outcome_quality|None, signal_str).
    None => leave the insert-time outcome_quality as-is (incl. a true-empty search, which keeps its
    distinct 'empty_but_honest'). web_quality is the 'quality' field from _compute_quality (thin/adequate)."""
    if caveated_unsupported and caveated_unsupported >= 1:
        return "unusable", f"support_gate_caveated:{caveated_unsupported}"
    if web_quality == "thin" and result_count > 0:
        return "unusable", "thin_evidence"
    return None, ""


def _run_support_scope(reply, working_set, evidence_map, *, surface, boot_id, shadow_id, ts):
    """Scope the support gate to FRESH/non-recall evidence. Recall-only / conversational turns skip
    MiniCheck entirely (no courtroom around Maez's voice); always emit the support_gate_scope receipt.
    Returns (reply, gate_receipt) — reply is unchanged unless the sync gate actually ran."""
    from core.routing.focused_cognition import turn_has_fresh_evidence
    _fresh = turn_has_fresh_evidence(working_set)
    logger.info("support_gate_scope surface=%s fresh_evidence=%s path=%s",
                surface, _fresh, "gated" if _fresh else "skipped_recall_only")
    if not _fresh:
        return reply, None
    from core.cognition.grounding_shadow import (
        decide_support_path, observe_focused_support, observe_focused_support_gate,
    )
    _support_path = decide_support_path(
        gate_enabled=strict_env_flag("MAEZ_SUPPORT_GATE_ENABLED"),
        shadow_enabled=strict_env_flag("MAEZ_GROUNDING_SHADOW_ENABLED"),
    )
    gate_receipt = None
    if _support_path == "sync_gate":
        reply, gate_receipt = observe_focused_support_gate(
            reply, evidence_map, surface=surface, boot_id=boot_id, shadow_id=shadow_id, ts=ts)
    elif _support_path == "async_shadow":
        observe_focused_support(
            reply, evidence_map, surface=surface, boot_id=boot_id, shadow_id=shadow_id, ts=ts)
    return reply, gate_receipt


def _run_mem_fresh_conflict_sense(working_set, *, surface):
    """SHADOW: sense a trusted-memory↔fresh contradiction; log a redacted receipt.
    Never mutates the reply. Flag-gated; fail-safe (any error → silent no-op)."""
    if not memory_fresh_conflict_sense_enabled():
        return
    try:
        from core.routing.photo_contradiction import LocalNLIContradictionVerifier
        receipt = check_memory_fresh_conflict(working_set, LocalNLIContradictionVerifier())
        if receipt is None:
            return
        logger.info(
            "mem_fresh_conflict_sense surface=%s verdict=%s mem_id=%s fresh_id=%s "
            "mem_label=%s fresh_label=%s "
            "confidence=%s verifier=%s reason_code=%s pair_count=%s pair_limit_exceeded=%s "
            "mem_sha256=%s fresh_sha256=%s",
            surface, receipt.verdict, receipt.mem_id, receipt.fresh_id,
            receipt.mem_label, receipt.fresh_label,
            receipt.confidence, receipt.verifier, receipt.reason_code,
            receipt.pair_count, receipt.pair_limit_exceeded,
            receipt.mem_sha256, receipt.fresh_sha256,
        )
    except Exception as exc:  # fail-safe: a sense must never break a turn
        logger.info("mem_fresh_conflict_sense surface=%s error=%s", surface, type(exc).__name__)


def _prior_vetoes_reflex(prior, *, min_conf=0.6, max_success=0.4):
    """A learned prior suppresses the keyword reflex only when CONFIDENT that this
    request-class + tool tends to fail (low usable rate). Conservative by design."""
    if prior is None:
        return False
    return prior.confidence >= min_conf and prior.success_rate <= max_success


def _veto_ledger_enabled() -> bool:
    return os.environ.get("MAEZ_VETO_LEDGER") == "1"


def _routing_beta_shadow_enabled() -> bool:
    return os.environ.get("MAEZ_ROUTING_BETA_SHADOW") == "1"


def _routing_beta_veto_enabled() -> bool:
    return os.environ.get("MAEZ_ROUTING_BETA_ENABLED") == "1"


def _routing_prior_consult_enabled() -> bool:
    return (
        os.environ.get("MAEZ_ROUTING_PRIORS_SHADOW") == "1"
        or os.environ.get("MAEZ_ROUTING_PRIORS_ENABLED") == "1"
        or _routing_beta_shadow_enabled()
        or _routing_beta_veto_enabled()
    )


def _veto_ledger_get(ledger):
    """Return a VetoLedger, building one if this turn hasn't yet. NEVER relies on a sibling
    block's import — an import inside another if/try can leave the name unbound and silently
    skip recording the veto (feature looks live, notebook never opens)."""
    if ledger is not None:
        return ledger
    from core.routing.veto_ledger import VetoLedger
    return VetoLedger()


def _focused_cognition_enabled(*, recall_stack_config=None) -> bool:
    if recall_stack_config is None:
        from core.routing.recall_stack_config import resolve_recall_stack

        recall_stack_config = resolve_recall_stack()
    return recall_stack_config.triad_on


RECALL_STATUS_INTERCEPT_FLAG = "MAEZ_RECALL_STATUS_INTERCEPT_ENABLED"
RECALL_RECEIPT_FLAG = "MAEZ_RECALL_RECEIPT_ENABLED"


def _recall_status_intercept_enabled() -> bool:
    return (os.environ.get(RECALL_STATUS_INTERCEPT_FLAG, "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _recall_receipt_enabled() -> bool:
    return (os.environ.get(RECALL_RECEIPT_FLAG, "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


RECALL_CARRIER_NOT_CONSULTED = "not_consulted"
RECALL_CARRIER_CONSULTED = "consulted"
RECALL_CARRIER_CONSULT_FAILED = "consult_failed"


@dataclass(frozen=True)
class DatedDenialDecision:
    reply: str
    kind: str


def log_recall_stack_posture(env=None) -> None:
    """Emit the recall-stack posture once (startup / witness)."""
    import os as _os

    from core.routing.recall_stack_config import (
        BUNDLE_FLAG,
        RAW_RECALL_FLAG_NAMES,
        resolve_recall_stack,
    )

    env = _os.environ if env is None else env
    cfg = resolve_recall_stack(env=env)

    def _state(name: str) -> str:
        return "set" if (env.get(name) or "").strip() else "unset"

    logger.info(
        "recall_stack mode=%s reason=%s raw_flags=[bundle=%s dispatcher=%s "
        "focused=%s living=%s]",
        cfg.mode.value,
        cfg.reason,
        _state(BUNDLE_FLAG),
        _state(RAW_RECALL_FLAG_NAMES[0]),
        _state(RAW_RECALL_FLAG_NAMES[1]),
        _state(RAW_RECALL_FLAG_NAMES[2]),
    )
    if cfg.reason.startswith("legacy_raw_flags_ignored:"):
        logger.warning(
            "recall_stack %s - deprecated raw recall flags are set but "
            "ignored; use %s",
            cfg.reason,
            BUNDLE_FLAG,
        )


def _dated_denial_decision(*, carrier_receipt: str, had_confirmed: bool) -> DatedDenialDecision:
    """Return an honest dated-memory fallback when focused produced no reply."""
    if carrier_receipt == RECALL_CARRIER_CONSULT_FAILED:
        return DatedDenialDecision(
            reply=(
                "I went to check my dated memory and the lookup errored out "
                "just now - that's on my side, not an absence. I won't fill "
                "it in from recent chat or guesswork; ask me again in a moment."
            ),
            kind="carrier_failed",
        )
    if carrier_receipt == RECALL_CARRIER_NOT_CONSULTED:
        return DatedDenialDecision(
            reply=(
                "I can't reach my dated memory from here right now. I won't "
                "answer it from recent chat or guesswork."
            ),
            kind="carrier_unavailable",
        )
    if had_confirmed:
        return DatedDenialDecision(
            reply=(
                "I have a dated memory for that, but I couldn't pull it together "
                "just now. Ask me again in a moment."
            ),
            kind="transport_failure",
        )
    return DatedDenialDecision(
        reply=(
            "I don't have a dated memory for that window. I'm not going to answer "
            "it from recent chat or guesswork."
        ),
        kind="no_dated_memory",
    )


def _dated_denial_reply(*, carrier_receipt: str, had_confirmed: bool) -> str:
    return _dated_denial_decision(
        carrier_receipt=carrier_receipt,
        had_confirmed=had_confirmed,
    ).reply


def _dated_denial_kind(*, carrier_receipt: str, had_confirmed: bool) -> str:
    return _dated_denial_decision(
        carrier_receipt=carrier_receipt,
        had_confirmed=had_confirmed,
    ).kind


def _log_dated_recall_denial(
    *,
    source: str,
    reply_mode,
    recall_stack_config,
    date_addressed: bool,
    carrier_receipt: str,
    had_confirmed: bool,
    reply_kind: str,
) -> None:
    reply_mode_value = getattr(reply_mode, "value", str(reply_mode))
    recall_mode_value = getattr(
        recall_stack_config.mode,
        "value",
        str(recall_stack_config.mode),
    )
    logger.info(
        "dated_recall_denial source=%s reply_mode=%s recall_stack_mode=%s "
        "recall_stack_reason=%s date_addressed=%s carrier_receipt=%s "
        "had_confirmed=%s reply_kind=%s",
        source,
        reply_mode_value,
        recall_mode_value,
        recall_stack_config.reason,
        date_addressed,
        carrier_receipt,
        had_confirmed,
        reply_kind,
    )


def _log_recall_outcome(*, rec) -> None:
    """Emit one content-free recall_outcome record."""
    from core.routing.recall_outcome import format_log_value

    logger.info(
        "recall_outcome schema_version=%s mode=%s turn_kind=%s outcome_class=%s "
        "denial_kind=%s had_confirmed=%s citation_coverage=%s reply_grounding=%s receipt_or_na=%s "
        "latency_ms=%s focused_elapsed_ms=%s reply_path=%s shadow_pair_id=%s "
        "receipt_eligible=%s receipt_after_ms=%s ack_required=%s "
        "ack_status=%s ack_emit_ms=%s",
        rec.schema_version,
        rec.mode,
        rec.turn_kind,
        rec.outcome_class.value,
        rec.denial_kind,
        format_log_value(rec.had_confirmed),
        format_log_value(rec.citation_coverage),
        format_log_value(rec.reply_grounding),
        rec.receipt_or_na,
        rec.latency_ms,
        format_log_value(rec.focused_elapsed_ms),
        rec.reply_path.value,
        format_log_value(getattr(rec, "shadow_pair_id", "na")),
        format_log_value(getattr(rec, "receipt_eligible", False)),
        format_log_value(getattr(rec, "receipt_after_ms", None)),
        format_log_value(getattr(rec, "ack_required", False)),
        format_log_value(getattr(rec, "ack_status", "not_eligible")),
        format_log_value(getattr(rec, "ack_emit_ms", None)),
    )


def _log_shadow_outcome(*, rec) -> None:
    """Emit one content-free shadow_outcome record."""
    logger.info(
        "shadow_outcome schema_version=%s shadow_pair_id=%s legacy_outcome=%s "
        "shadow_reach=%s rescuable_candidate=%s false_absence_candidate=%s "
        "legacy_false_absence_rescuable=%s latency_delta_ms=%s receipt_state=%s "
        "ts=%s boot_id=%s shadow_skipped=%s",
        rec.schema_version,
        rec.shadow_pair_id,
        rec.legacy_outcome.value,
        rec.shadow_reach.value,
        "true" if rec.rescuable_candidate else "false",
        "true" if rec.false_absence_candidate else "false",
        "true" if rec.legacy_false_absence_rescuable else "false",
        rec.latency_delta_ms,
        rec.receipt_state.value,
        rec.ts,
        rec.boot_id,
        rec.shadow_skipped,
    )


def _recall_shadow_enabled() -> bool:
    return str(os.environ.get(RECALL_SHADOW_FLAG, "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _focused_working_set_had_confirmed(working_set) -> bool:
    return bool(
        working_set is not None
        and any(
            getattr(item, "temporal_provenance", None)
            and item.temporal_provenance.get("confirmed")
            for item in getattr(working_set, "items", ()) or ()
        )
    )


def _reply_asserts_dated_absence(reply: str) -> bool:
    low = (reply or "").lower().replace("’", "'")
    absence_phrases = (
        "don't have a dated memory",
        "do not have a dated memory",
        "don't have dated memory",
        "do not have dated memory",
        "no dated memory",
        "don't remember",
        "do not remember",
        "don't recall",
        "do not recall",
        "don't have any record",
        "don't have any records",
        "do not have any record",
        "do not have any records",
        "got nothing",
        "have got nothing",
        "have no record",
        "have no records",
    )
    no_record_contexts = (
        "no record for",
        "no records for",
        "no record of",
        "no records of",
        "no record from",
        "no records from",
        "no record about",
        "no records about",
        "no record on",
        "no records on",
        "no record around",
        "no records around",
        "no record matched",
        "no records matched",
        "no record found",
        "no records found",
        "no record available",
        "no records available",
        "no record exists",
        "no records exist",
    )
    stripped = low.strip(" \t\r\n.!?")
    matched = (
        any(phrase in low for phrase in absence_phrases)
        or stripped in {"no record", "no records"}
        or any(phrase in low for phrase in no_record_contexts)
    )
    if not matched:
        return False
    return " but " not in low


def _is_dated_denial_reply(reply: str) -> bool:
    text = (reply or "").strip()
    if not text:
        return False
    replies = {
        _dated_denial_reply(carrier_receipt=RECALL_CARRIER_NOT_CONSULTED, had_confirmed=False),
        _dated_denial_reply(carrier_receipt=RECALL_CARRIER_CONSULT_FAILED, had_confirmed=False),
        _dated_denial_reply(carrier_receipt=RECALL_CARRIER_CONSULTED, had_confirmed=False),
        _dated_denial_reply(carrier_receipt=RECALL_CARRIER_CONSULTED, had_confirmed=True),
    }
    return text in replies


def _log_recall_self_status(
    *,
    source: str,
    state: str,
    triad_on: bool,
    carrier_reachable: bool,
    receipt: str,
    timestamp_requested: bool,
) -> None:
    logger.info(
        "recall_self_status source=%s state=%s triad_on=%s "
        "carrier_reachable=%s receipt=%s timestamp_requested=%s",
        source,
        state,
        str(bool(triad_on)).lower(),
        str(bool(carrier_reachable)).lower(),
        receipt,
        str(bool(timestamp_requested)).lower(),
    )


def _consolidate_system_messages(
    messages: list[dict],
    *,
    final_system_part: str | ProvenancedText | None = None,
) -> list[dict]:
    """Collapse system-role prompt parts into one leading system message."""
    system_parts: list[ProvenancedText] = []
    non_system_messages: list[dict] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content") or ""
        if role == "system":
            if str(content).strip():
                if isinstance(content, ProvenancedText):
                    system_parts.append(content)
                else:
                    system_parts.append(
                        ProvenancedText.system_bounded_query(
                            str(content),
                            source_ref=f"daemon:system:{index}",
                        )
                    )
        else:
            non_system_messages.append(message)
    if final_system_part and str(final_system_part).strip():
        if isinstance(final_system_part, ProvenancedText):
            system_parts.append(final_system_part)
        else:
            system_parts.append(
                ProvenancedText.system_bounded_query(
                    str(final_system_part),
                    source_ref="daemon:system:final",
                )
            )
    if not system_parts:
        return non_system_messages
    joined = ProvenancedText.from_spans(())
    for index, part in enumerate(system_parts):
        if index:
            joined = joined + ProvenancedText.system_bounded_query(
                "\n\n",
                source_ref="daemon:system:separator",
            )
        joined = joined + part
    return [{"role": "system", "content": joined}] + non_system_messages


def _compose_turn_final_system_part(
    turn_final_context: str | ProvenancedText | None,
    *,
    context_note: str | ProvenancedText | None = None,
) -> ProvenancedText | None:
    """Compose the closest turn-specific system context.

    Generic evidence context may say desktop screen observation is absent.
    Caller-provided local perception, such as Telegram photo vision, must land
    after that generic context so the model does not confuse "no desktop eye"
    with "no owner-sent photo analysis".
    """
    parts: list[ProvenancedText] = []
    if turn_final_context and str(turn_final_context).strip():
        if isinstance(turn_final_context, ProvenancedText):
            parts.append(turn_final_context)
        else:
            parts.append(
                ProvenancedText.system_bounded_query(
                    str(turn_final_context),
                    source_ref="daemon:system:turn_final_context",
                )
            )
    if context_note and str(context_note).strip():
        if isinstance(context_note, ProvenancedText):
            parts.append(context_note)
        else:
            parts.append(
                ProvenancedText.system_bounded_query(
                    str(context_note).strip(),
                    source_ref="daemon:system:context_note",
                )
            )
    if not parts:
        return None
    joined = ProvenancedText.from_spans(())
    for index, part in enumerate(parts):
        if index:
            joined = joined + ProvenancedText.system_bounded_query(
                "\n\n",
                source_ref="daemon:system:turn_final_separator",
            )
        joined = joined + part
    return joined


def _plain_llm_messages(messages: list[dict]) -> list[dict]:
    """Flatten provenance-bearing prompt content before local LLM calls."""
    plain: list[dict] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        clone = dict(message)
        content = clone.get("content")
        if isinstance(content, ProvenancedText):
            clone["content"] = content.text
        plain.append(clone)
    return plain


def _prompt_capture_excerpt(content: str, *, limit: int = 100) -> str:
    return content[:limit]


def _prompt_capture_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _summarize_daemon_prompt_messages(
    messages: list[dict],
    *,
    transcript_context: str = "",
    evidence_directive: str = "",
) -> dict[str, object]:
    """Return safe structural metadata for the daemon prompt payload."""
    roles: list[str] = []
    hashes: list[str] = []
    system_lengths: list[int] = []
    user_length = 0
    summary: dict[str, object] = {}
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "")
        content = str(message.get("content") or "")
        roles.append(role)
        hashes.append(_prompt_capture_hash(content))
        if role == "system":
            system_lengths.append(len(content))
        if role == "user":
            user_length = len(content)
        summary[f"message_{index}_head"] = _prompt_capture_excerpt(content)
        summary[f"message_{index}_tail"] = (
            content[-100:] if len(content) > 100 else content
        )
    system_content = ""
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "system":
            system_content = str(message.get("content") or "")
            break
    summary.update(
        {
            "message_count": len(roles),
            "role_sequence": ",".join(roles),
            "system_message_count": len(system_lengths),
            "system_message_length": system_lengths[0] if system_lengths else 0,
            "user_message_length": user_length,
            "transcript_is_suffix": bool(
                transcript_context
                and system_content.endswith(transcript_context)
            ),
            "evidence_directive_is_suffix": bool(
                evidence_directive
                and system_content.endswith(evidence_directive)
            ),
            "message_hashes": ",".join(hashes),
        }
    )
    return summary


def _log_daemon_prompt_payload_shape(
    *,
    surface: str,
    call_purpose: str,
    messages: list[dict],
    transcript_context: str,
    evidence_directive: str = "",
) -> None:
    summary = _summarize_daemon_prompt_messages(
        messages,
        transcript_context=transcript_context,
        evidence_directive=evidence_directive,
    )
    logger.info(
        "daemon_prompt_payload_shape surface=%s call_purpose=%s summary=%s",
        surface,
        call_purpose,
        json.dumps(summary, sort_keys=True),
    )


def _summarize_daemon_system_parts(
    system_parts: list[tuple[str, str]],
) -> dict[str, object]:
    """Return safe metadata for pre-consolidation system prompt parts."""
    labels: list[str] = []
    lengths: list[str] = []
    hashes: list[str] = []
    summary: dict[str, object] = {}
    for index, (label, content) in enumerate(system_parts):
        safe_label = str(label or f"part_{index}")
        safe_content = str(content or "")
        if not safe_content.strip():
            continue
        labels.append(safe_label)
        lengths.append(str(len(safe_content)))
        hashes.append(_prompt_capture_hash(safe_content))
        summary[f"system_part_{index}_head"] = _prompt_capture_excerpt(safe_content)
        summary[f"system_part_{index}_tail"] = (
            safe_content[-100:] if len(safe_content) > 100 else safe_content
        )
    summary.update(
        {
            "system_part_count": len(labels),
            "system_part_labels": ",".join(labels),
            "system_part_lengths": ",".join(lengths),
            "system_part_hashes": ",".join(hashes),
        }
    )
    return summary


def _log_daemon_system_part_shape(
    *,
    surface: str,
    call_purpose: str,
    system_parts: list[tuple[str, str]],
) -> None:
    summary = _summarize_daemon_system_parts(system_parts)
    logger.info(
        "daemon_system_part_shape surface=%s call_purpose=%s summary=%s",
        surface,
        call_purpose,
        json.dumps(summary, sort_keys=True),
    )


def _log_focused_cognition_prompt_shape(
    *,
    surface: str,
    working_set: object,
    legacy_prompt_chars: int,
) -> None:
    items = list(getattr(working_set, "items", []) or [])
    source_types = sorted({str(getattr(item, "source_type", "")) for item in items})
    summary = {
        "evidence_item_count": len(items),
        "source_types": ",".join(source_types),
        "working_set_chars": int(getattr(working_set, "working_set_chars", 0) or 0),
        "working_set_tokens_est": int(
            getattr(working_set, "working_set_tokens_est", 0) or 0
        ),
        "legacy_prompt_chars": int(legacy_prompt_chars),
        "legacy_prompt_tokens_est": int(legacy_prompt_chars // 4),
    }
    logger.info(
        "focused_cognition_prompt_shape surface=%s summary=%s",
        surface,
        json.dumps(summary, sort_keys=True),
    )


@dataclass(frozen=True)
class CycleFocusedPromptDecision:
    prompt: str
    working_set: object | None = None
    fallback_reason: str | None = None


def _cycle_focused_enabled() -> bool:
    return (
        (os.environ.get("MAEZ_CYCLE_FOCUSED_ENABLED", "") or "")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"}
    )


def _cycle_packet_shape_summary(
    *,
    working_set: object,
    legacy_prompt_chars: int,
    prefill_ms: int | None = None,
    chat_total_ms: int | None = None,
    cycle_outcome: str = "pending",
) -> dict[str, object]:
    items = list(getattr(working_set, "items", []) or [])
    source_types = sorted({str(getattr(item, "source_type", "")) for item in items})
    return {
        "packet_tokens_est": int(
            getattr(working_set, "working_set_tokens_est", 0) or 0
        ),
        "legacy_tokens_est": int(legacy_prompt_chars // 4),
        "evidence_item_count": len(items),
        "source_types": ",".join(source_types),
        "prefill_ms": None if prefill_ms is None else int(prefill_ms),
        "chat_total_ms": None if chat_total_ms is None else int(chat_total_ms),
        "cycle_outcome": str(cycle_outcome),
    }


def _log_cycle_packet_shape(
    *,
    working_set: object,
    legacy_prompt_chars: int,
    prefill_ms: int | None = None,
    chat_total_ms: int | None = None,
    cycle_outcome: str = "pending",
) -> None:
    logger.info(
        "cycle_packet_shape summary=%s",
        json.dumps(
            _cycle_packet_shape_summary(
                working_set=working_set,
                legacy_prompt_chars=legacy_prompt_chars,
                prefill_ms=prefill_ms,
                chat_total_ms=chat_total_ms,
                cycle_outcome=cycle_outcome,
            ),
            sort_keys=True,
        ),
    )


@dataclass(frozen=True)
class _CycleDoormanGateDecision:
    doorman_enabled: bool
    wake: bool
    reason_code: str | None = None
    signals_present: tuple[str, ...] = ()
    legacy_skip: bool = False
    floor_wake: bool = False
    verdict: DoormanVerdict | None = None

    @property
    def should_call_deep_brain(self) -> bool:
        return self.wake


def _cycle_doorman_enabled() -> bool:
    return (os.environ.get("MAEZ_CYCLE_DOORMAN_ENABLED", "") or "").strip() == "1"


def _want_pursuit_enabled(environ: object | None = None) -> bool:
    env = os.environ if environ is None else environ
    return (env.get("MAEZ_WANT_PURSUIT_ENABLED", "") or "").strip() == "1"


def _env_flag(name: str, *, environ: object | None = None) -> bool:
    env = os.environ if environ is None else environ
    return (env.get(name, "") or "").strip().lower() in {"1", "true", "yes", "on"}


def _lean_idle_heartbeat_shadow_enabled(environ: object | None = None) -> bool:
    return _env_flag("MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW", environ=environ)


def _lean_idle_heartbeat_enabled(environ: object | None = None) -> bool:
    return _env_flag("MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED", environ=environ)


def _lean_idle_heartbeat_any_enabled(environ: object | None = None) -> bool:
    return _lean_idle_heartbeat_shadow_enabled(environ) or _lean_idle_heartbeat_enabled(environ)


def _salience_broker_shadow_enabled(environ: object | None = None) -> bool:
    return _env_flag("MAEZ_SALIENCE_BROKER_SHADOW", environ=environ)


def _fresh_moment_receipts_shadow_enabled(environ: object | None = None) -> bool:
    return _env_flag("MAEZ_FRESH_MOMENT_RECEIPTS_SHADOW", environ=environ)


def _world_window_shadow_enabled(environ: object | None = None) -> bool:
    return _env_flag("MAEZ_WORLD_WINDOW_SHADOW", environ=environ)


def _desktop_attention_shadow_enabled(environ: object | None = None) -> bool:
    return _env_flag("MAEZ_DESKTOP_ATTENTION_SHADOW", environ=environ)


def _lean_idle_heartbeat_eligible(gate_decision: object) -> bool:
    return (
        bool(getattr(gate_decision, "doorman_enabled", False))
        and bool(getattr(gate_decision, "wake", False))
        and bool(getattr(gate_decision, "floor_wake", False))
        and str(getattr(gate_decision, "reason_code", "")) == "wake_min_floor"
        and tuple(getattr(gate_decision, "signals_present", ()) or ()) == ("min_floor_due",)
    )


def _wrap_daemon_web_context(web_context: str, *, path: str) -> str:
    """Wrap a daemon web_context block in the un-spoofable containment envelope
    (legacy/voice prompt throats). Flag-off or empty -> returns web_context unchanged
    (byte-identical). Emits a content-light path-tagged receipt."""
    from core.routing import web_containment as _wc
    if not (_wc.containment_enabled() and web_context):
        return web_context
    import hashlib
    nonce = _wc.new_nonce()
    digest = hashlib.sha256(web_context.encode("utf-8")).hexdigest()[:16]
    wrapped = _wc.wrap_web_text(web_context, nonce=nonce, source="web", digest=digest)
    _wc.emit_receipt(_wc.containment_receipt(wrapped, nonce=nonce, path=path,
                                             expected_segments=1, digest=digest))
    return _wc.standing_instruction() + "\n\n" + wrapped


def _safe_episode_body_counts(episode_store: object | None) -> dict[str, object]:
    if episode_store is None:
        return {
            "episode_counts_state": "unknown",
            "episode_counts_error_class": "missing_store",
            "episodes_total": 0,
            "episodes_active": 0,
            "episodes_superseded": 0,
            "reflection": 0,
        }
    try:
        counts = episode_store.counts_by_status_and_source_kind()
        return {
            "episode_counts_state": "available",
            "episodes_total": int(counts.get("total", 0) or 0),
            "episodes_active": int(counts.get("active", 0) or 0),
            "episodes_superseded": int(counts.get("superseded", 0) or 0),
            "reflection": int(counts.get("reflection", 0) or 0),
        }
    except Exception as exc:
        return {
            "episode_counts_state": "unknown",
            "episode_counts_error_class": type(exc).__name__,
            "episodes_total": 0,
            "episodes_active": 0,
            "episodes_superseded": 0,
            "reflection": 0,
        }


def _record_owner_interaction(daemon: object, *, now: float | None = None) -> None:
    setattr(daemon, "_last_owner_interaction_ts", time.time() if now is None else float(now))


def _dream_camera_idle_state(camera_state: object | None, *, now: float) -> str:
    if camera_state is None:
        return "unknown"
    try:
        now_dt = datetime.fromtimestamp(float(now), tz=timezone.utc)
        with_freshness = getattr(camera_state, "with_freshness", None)
        if callable(with_freshness):
            camera_state = with_freshness(now=now_dt)
    except Exception:
        pass
    sensor_state = str(getattr(camera_state, "sensor_state", "unknown") or "unknown").lower()
    presence_state = str(getattr(camera_state, "presence_state", "unknown") or "unknown").lower()
    if presence_state == "present" and sensor_state == "available":
        return "present_fresh"
    if presence_state == "absent":
        return "absent"
    if sensor_state in {"disabled", "stale", "unavailable"}:
        return "unavailable"
    return "unknown"


def _dream_idle_inputs(daemon: object, *, now: float | None = None) -> dict[str, object]:
    current = time.time() if now is None else float(now)
    last_interaction = getattr(daemon, "_last_owner_interaction_ts", None)
    try:
        no_interaction_secs = max(0.0, current - float(last_interaction))
        activity_known = True
    except (TypeError, ValueError):
        no_interaction_secs = 0.0
        activity_known = False
    try:
        active_until_future = float(getattr(daemon, "_rohit_active_until", 0.0) or 0.0) > current
    except (TypeError, ValueError):
        active_until_future = False
    camera_state = (
        getattr(daemon, "_last_presence_snap", None)
        or getattr(daemon, "_camera_presence_state", None)
    )
    return {
        "no_interaction_secs": no_interaction_secs,
        "camera": _dream_camera_idle_state(camera_state, now=current),
        "active_until_future": active_until_future,
        "activity_known": activity_known,
    }


def _dream_idle_gate_open(daemon: object, *, now: float | None = None) -> bool:
    from core.evolution.dream_state import dream_may_run

    return dream_may_run(**_dream_idle_inputs(daemon, now=now))


def _reflection_synthesis_enabled(environ: object | None = None) -> bool:
    env = os.environ if environ is None else environ
    return (env.get("MAEZ_REFLECTION_SYNTHESIS_ENABLED", "") or "").strip() == "1"


def _reflection_synthesis_write_enabled(environ: object | None = None) -> bool:
    env = os.environ if environ is None else environ
    return (env.get("MAEZ_REFLECTION_SYNTHESIS_WRITE", "") or "").strip() == "1"


def _reflection_synthesis_max_reflections(environ: object | None = None) -> int:
    env = os.environ if environ is None else environ
    raw = (env.get("MAEZ_REFLECTION_SYNTHESIS_MAX_REFLECTIONS", "") or "").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 3
    return value if value >= 1 else 3


def _reflection_terminal_reason(report: object | None, fallback: str) -> tuple[str, str]:
    finish_reason = str(getattr(report, "finish_reason", "") or "")
    if not finish_reason and fallback != "error":
        return str(fallback), "no_input"
    if finish_reason == "length":
        return "invalid_witness", "truncated"
    if finish_reason == "llm_timeout":
        return "invalid_witness", "llm_timeout"
    if finish_reason == "llm_error":
        return "invalid_witness", "llm_error"
    if finish_reason and finish_reason != "stop":
        return "invalid_witness", "llm_error"
    return str(fallback), ""


def _reflection_synthesis_summary(
    *,
    status: str,
    reason: str,
    report: object | None = None,
    artifact_path: Path | None = None,
) -> dict[str, object]:
    mapped_status, mapped_reason = _reflection_terminal_reason(report, status)
    return {
        "status": mapped_status,
        "reason": mapped_reason or str(reason),
        "candidates_count": int(len(getattr(report, "reflection_candidates", []) or [])),
        "drops_count": int(len(getattr(report, "reflection_drops", []) or [])),
        "reflections_attempted": int(getattr(report, "reflections_attempted", 0) or 0),
        "reflections_added": int(getattr(report, "reflections_added", 0) or 0),
        "artifact_path": str(artifact_path) if artifact_path is not None else "",
        "finish_reason": str(getattr(report, "finish_reason", "") or ""),
        "max_tokens": getattr(report, "max_tokens", None),
        "truncated": bool(getattr(report, "truncated", False)),
    }


def _log_reflection_synthesis_summary(summary: dict[str, object]) -> None:
    logger.info(
        "reflection_synthesis summary=%s",
        json.dumps(summary, sort_keys=True),
    )


def _reflection_consolidation_telemetry(
    summary: dict[str, object],
    *,
    model: str,
    duration_ms: float | int,
) -> dict[str, object]:
    from core.cognition.consolidation_telemetry import consolidation_telemetry_summary

    candidates = int(summary.get("candidates_count", 0) or 0)
    drops = int(summary.get("drops_count", 0) or 0)
    return consolidation_telemetry_summary(
        organ="reflection",
        inputs_count=candidates + drops,
        outputs_count=candidates,
        model=model,
        duration_ms=duration_ms,
        rails_blocked=drops,
        status=str(summary.get("status", "unknown")),
        reason=str(summary.get("reason", "unknown")),
    )


def _emit_reflection_consolidation_telemetry(
    summary: dict[str, object],
    *,
    started_mono: float,
) -> None:
    try:
        from core.cognition.consolidation_telemetry import emit_consolidation_telemetry
        from core.routing.llm_client import served_model_alias

        emit_consolidation_telemetry(
            logger,
            **_reflection_consolidation_telemetry(
                summary,
                model=served_model_alias(default="qwen36-27b"),
                duration_ms=(time.monotonic() - started_mono) * 1000.0,
            ),
        )
    except Exception as _telemetry_exc:
        logger.debug("reflection consolidation telemetry skipped: %s", _telemetry_exc)


def _run_reflection_synthesis_nightly(
    daemon: object,
    *,
    llm_call=None,
    artifact_dir: Path | None = None,
) -> dict[str, object]:
    if not _reflection_synthesis_enabled():
        return {"status": "disabled", "reason": "flag_off"}

    from scripts.memory_reflection.nightly_lived_memory import (
        ReflectionReport,
        _default_llm_call,
        run_synthesis_pass,
        write_reflection_dry_run_artifact,
        write_reflection_write_artifact,
    )

    dry_run = not _reflection_synthesis_write_enabled()
    started_mono = time.monotonic()
    report = ReflectionReport(dry_run=dry_run, started_at=datetime.now(timezone.utc).isoformat())
    if llm_call is None:
        llm_call = _default_llm_call("qwen36-27b", 240)
    try:
        run_synthesis_pass(
            episode_store=getattr(daemon, "lived_episodes"),
            llm_call=llm_call,
            report=report,
            dry_run=dry_run,
            max_reflections=_reflection_synthesis_max_reflections(),
        )
    except Exception as exc:
        logger.warning("reflection synthesis pass failed: %s", type(exc).__name__)
        summary = _reflection_synthesis_summary(
            status="error",
            reason="synthesis_failed",
            report=report,
        )
        _log_reflection_synthesis_summary(summary)
        _emit_reflection_consolidation_telemetry(summary, started_mono=started_mono)
        return summary
    artifact_path = None
    status = "write"
    reason = "persist_enabled"
    if dry_run:
        try:
            artifact_path = write_reflection_dry_run_artifact(report, artifact_dir=artifact_dir)
        except Exception as exc:
            logger.warning("reflection dry-run artifact write failed: %s", type(exc).__name__)
            summary = _reflection_synthesis_summary(
                status="error",
                reason="artifact_failed",
                report=report,
            )
            _log_reflection_synthesis_summary(summary)
            _emit_reflection_consolidation_telemetry(summary, started_mono=started_mono)
            return summary
        status = "dry_run"
        reason = "write_flag_off"
    elif report.reflections_added >= 1:
        try:
            artifact_path = write_reflection_write_artifact(report, artifact_dir=artifact_dir)
        except Exception as exc:
            logger.warning("reflection write receipt failed: %s", type(exc).__name__)
    summary = _reflection_synthesis_summary(
        status=status,
        reason=reason,
        report=report,
        artifact_path=artifact_path,
    )
    _log_reflection_synthesis_summary(summary)
    _emit_reflection_consolidation_telemetry(summary, started_mono=started_mono)
    return summary


def _cycle_doorman_verdict_summary(
    verdict: DoormanVerdict,
    *,
    quiet_skips: int,
) -> dict[str, object]:
    reason_code = (
        verdict.reason_code.value if hasattr(verdict.reason_code, "value") else str(verdict.reason_code)
    )
    return {
        "wake": bool(verdict.wake),
        "reason_code": reason_code,
        "signals_present": tuple(str(item) for item in verdict.signals_present),
        "quiet_skips": int(quiet_skips),
    }


def _log_cycle_doorman_verdict(
    *,
    verdict: DoormanVerdict,
    quiet_skips: int,
) -> None:
    logger.info(
        "doorman_verdict summary=%s",
        json.dumps(
            _cycle_doorman_verdict_summary(verdict, quiet_skips=quiet_skips),
            sort_keys=True,
        ),
    )


def _cycle_doorman_skip_summary(
    gate_decision: _CycleDoormanGateDecision,
    *,
    quiet_skips: int,
) -> dict[str, object]:
    return {
        "reason_code": str(gate_decision.reason_code),
        "signals_present": tuple(str(item) for item in gate_decision.signals_present),
        "quiet_skips": int(quiet_skips),
    }


def _log_cycle_doorman_skip(
    *,
    gate_decision: _CycleDoormanGateDecision,
    quiet_skips: int,
) -> None:
    logger.info(
        "doorman_skip summary=%s",
        json.dumps(
            _cycle_doorman_skip_summary(gate_decision, quiet_skips=quiet_skips),
            sort_keys=True,
        ),
    )


def _cycle_action_result_failed(result: object) -> bool:
    if getattr(result, "success", None) is False:
        return True
    for attr in ("status", "outcome", "state"):
        value = getattr(result, attr, None)
        if value is None:
            continue
        lowered = str(getattr(value, "value", value)).lower()
        if lowered in {"failed", "error", "errored", "approved_and_failed"}:
            return True
    if getattr(result, "error", None):
        return True
    return False


def _cycle_action_failure_count(results: object) -> int:
    try:
        return sum(1 for result in list(results or []) if _cycle_action_result_failed(result))
    except Exception:
        return 0


def _cycle_signal_availability_key(*, screen_obs: object, camera_state: object) -> str:
    screen_available = bool(getattr(screen_obs, "success", False))
    sensor_state = str(getattr(camera_state, "sensor_state", "unknown") or "unknown").lower()
    camera_available = sensor_state not in {
        "off",
        "disabled",
        "unavailable",
        "sensor_unavailable",
    }
    return (
        f"screen={'available' if screen_available else 'absent'}"
        f"|camera={'available' if camera_available else 'absent'}"
    )


def _cycle_signal_availability_changed(previous: str | None, current: str) -> bool:
    return previous is not None and previous != current


def _axis_signature_without_presence(axes: dict | None) -> str | None:
    if axes is None:
        return None
    stable = {key: value for key, value in dict(axes).items() if key != "presence"}
    return json.dumps(stable, sort_keys=True)


def _cycle_salient_perception_state(
    *,
    screen_obs: object,
    signal_availability_key: str,
) -> dict[str, object]:
    screen_success = bool(getattr(screen_obs, "success", False))
    return {
        "screen_state": str(getattr(screen_obs, "state", "unknown") or "unknown"),
        "screen_success": screen_success,
        "screen_activity": str(
            getattr(screen_obs, "activity", "unknown") or "unknown"
        ),
        "screen_application": str(
            getattr(screen_obs, "application", "unknown") or "unknown"
        ),
        "screen_focus_level": str(
            getattr(screen_obs, "focus_level", "unknown") or "unknown"
        ),
        "signal_availability": str(signal_availability_key or "unknown"),
    }


def _cycle_doorman_signals(
    *,
    current_axes: dict,
    last_thought_axes: dict | None,
    current_salient_perception: object | None = None,
    last_salient_perception: object | None = None,
    quiet_skips: int,
    min_floor: int,
    new_failures: int,
    open_wants: int,
    memory_delta: bool,
    signal_availability_changed: bool,
    scheduled_due: bool,
    presence: str,
) -> DoormanSignals:
    if current_salient_perception is None and last_salient_perception is None:
        current_salient_perception = current_axes
        last_salient_perception = last_thought_axes
    perception_changed = salient_perception_changed(
        last_salient_perception,
        current_salient_perception,
    )
    return DoormanSignals(
        perception_changed=perception_changed,
        new_failures=int(new_failures),
        open_wants=int(open_wants),
        memory_delta=bool(memory_delta),
        signal_availability_changed=bool(signal_availability_changed),
        scheduled_due=bool(scheduled_due),
        quiet_skips=int(quiet_skips),
        min_floor=int(min_floor),
        presence=str(presence or "unknown"),
    )


def _cycle_doorman_gate_decision(
    *,
    doorman_enabled: bool,
    current_signature: str,
    last_thought_signature: str | None,
    quiet_skips: int,
    min_floor: int,
    signals: object,
) -> _CycleDoormanGateDecision:
    from core.cognition.perception_signature import should_skip_reasoning

    if not doorman_enabled:
        legacy_skip = should_skip_reasoning(
            current_signature=current_signature,
            last_thought_signature=last_thought_signature,
            cycles_since_last_thought=quiet_skips,
            min_thought_floor=min_floor,
        )
        return _CycleDoormanGateDecision(
            doorman_enabled=False,
            wake=not legacy_skip,
            reason_code="legacy_perception_unchanged" if legacy_skip else "legacy_wake",
            legacy_skip=legacy_skip,
        )

    verdict = _decide_cycle_doorman(signals)
    reason_code = (
        verdict.reason_code.value if hasattr(verdict.reason_code, "value") else str(verdict.reason_code)
    )
    return _CycleDoormanGateDecision(
        doorman_enabled=True,
        wake=bool(verdict.wake),
        reason_code=reason_code,
        signals_present=tuple(str(item) for item in verdict.signals_present),
        floor_wake=verdict.reason_code == DoormanReasonCode.WAKE_MIN_FLOOR,
        verdict=verdict,
    )


def _cycle_next_quiet_skips(
    *,
    gate_decision: _CycleDoormanGateDecision,
    current_quiet_skips: int,
    result: str | None,
) -> int:
    if gate_decision.doorman_enabled:
        if not gate_decision.wake:
            return int(current_quiet_skips) + 1
        # A doorman wake is a wake opportunity even if the deep brain later
        # says HEARTBEAT_OK. Reset to keep the floor periodic, not latched.
        return 0
    if not gate_decision.wake and result is None:
        return int(current_quiet_skips) + 1
    if result is not None and str(result).strip() != _HEARTBEAT_OK:
        return 0
    if result is not None and str(result).strip() == _HEARTBEAT_OK:
        return int(current_quiet_skips) + 1
    return int(current_quiet_skips)


def _cycle_apply_quiet_counter_result(
    daemon: object,
    *,
    gate_decision: _CycleDoormanGateDecision,
    result: str | None,
) -> None:
    current = int(getattr(daemon, "_cycles_since_last_thought", 0))
    setattr(
        daemon,
        "_cycles_since_last_thought",
        _cycle_next_quiet_skips(
            gate_decision=gate_decision,
            current_quiet_skips=current,
            result=result,
        ),
    )


def _count_cycle_open_wants(daemon: object) -> int:
    try:
        wants = getattr(daemon, "wants", None)
        if wants is not None and hasattr(wants, "active_wants"):
            return len(wants.active_wants(limit=50) or [])
    except Exception as _wants_exc:
        logger.debug("cycle doorman wants-count skipped: %s", _wants_exc)
    return 0


def _buffer_cycle_audit_flags(audit_result: object) -> None:
    try:
        from core.safety.audited_output import _buffer_audit_flags

        _buffer_audit_flags(getattr(audit_result, "flags", ()) or ())
    except Exception:
        logger.warning(
            "cycle-response audit flag side-record failed",
            exc_info=True,
        )


def _valence_reading_to_telemetry(reading) -> dict | None:
    """Convert a ValenceReading into the honest dict the cockpit retains.

    Keeps ONLY real fields (sign, magnitude, the reading's own telemetry
    sentence, and the active contribution reasons). Never invents a mood.
    Returns None for a None reading so the caller can leave prior value/None.
    """
    if reading is None:
        return None
    try:
        sign = getattr(getattr(reading, "sign", None), "value", None)
        magnitude = getattr(getattr(reading, "magnitude", None), "value", None)
        reasons = []
        for contribution in getattr(reading, "contributions", ()) or ():
            csign = getattr(contribution, "sign", None)
            creason = getattr(contribution, "reason", "")
            if csign is not None and getattr(csign, "name", "") != "NEUTRAL" and creason:
                reasons.append(creason)
        return {
            "sign": sign,
            "magnitude": magnitude,
            "telemetry": reading.as_telemetry(),
            "reasons": reasons,
            "provenance": getattr(reading, "provenance", "computed_valence"),
        }
    except Exception:
        return None


# Organ-gating MAEZ_* flags surfaced to the cockpit. Tokens/secrets/paths are
# deliberately excluded — only the switches that turn cognition organs on/off.
_COCKPIT_FLAG_NAMES = (
    "MAEZ_COCKPIT_REAL_STATE",
    "MAEZ_COCKPIT_CORE",
    "MAEZ_LIVED_RECALL",
    "MAEZ_CYCLE_DOORMAN_ENABLED",
    "MAEZ_CYCLE_FOCUSED_ENABLED",
    "MAEZ_RECALL_RECEIPT_ENABLED",
    "MAEZ_RECALL_SHADOW_ENABLED",
    "MAEZ_RECALL_STATUS_INTERCEPT_ENABLED",
    "MAEZ_REFLECTION_SYNTHESIS_ENABLED",
    "MAEZ_WANT_PURSUIT_ENABLED",
    "MAEZ_WONDERING_PURSUIT",
    "MAEZ_WORKING_SELF",
    "MAEZ_SCREEN_PERCEPTION",
    "MAEZ_LEDGER_WRITES",
    "MAEZ_EVIDENCE_ENVELOPE_DISABLED",
)


def _cockpit_flags_snapshot() -> dict:
    """Read the live organ-gating flags straight off os.environ (raw values)."""
    return {name: os.environ.get(name) for name in _COCKPIT_FLAG_NAMES}


def _build_cockpit_state(daemon) -> dict:
    """Assemble the fast cockpit real-state JSON true-by-construction.

    Reads straight off the daemon's retained in-memory attrs. Does NOT call
    perception_snapshot()/nvidia-smi (that is why /health is slow). Every field
    is guarded so a missing attr yields null, never a crash. Deliberately
    OMITS mood and uncertainty — they have no organ; performing them would be
    fabrication the covenant forbids.
    """

    def _safe(fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    reasoning_loop = _safe(
        lambda: daemon._cycle_heartbeat_health(), default=None
    )
    status = _safe(
        lambda: daemon._health_status_from_reasoning_loop(reasoning_loop or {}),
        default=None,
    )

    cognition = None

    recall = None
    receipt = getattr(daemon, "_last_recall_receipt", None)
    if receipt is not None:
        recall = {
            "receipt": getattr(receipt, "receipt", None),
            "at_ts": getattr(receipt, "at_ts", None),
            "boot_id": getattr(receipt, "boot_id", None),
        }

    return {
        "status": status,
        "running": bool(getattr(daemon, "running", False)),
        "boot_time": getattr(daemon, "boot_time", None),
        "cycle_count": getattr(daemon, "cycle_count", None),
        "last_cycle": getattr(daemon, "last_cycle_time", None),
        "reasoning_loop": reasoning_loop,
        "cognition": cognition,
        "last_thought": getattr(daemon, "_last_cycle_text", None) or None,
        "valence": getattr(daemon, "_last_valence_reading", None),
        "recall": recall,
        "watchdog": _safe(lambda: daemon._watchdog_health(), default=None),
        "temporal_spine": _safe(lambda: temporal_spine_health(), default=None),
        "clinical_boundary": _safe(lambda: clinical_boundary_health(), default=None),
        "voice_continuity": _safe(
            lambda: daemon._voice_continuity_health(), default=None
        ),
        "flags": _cockpit_flags_snapshot(),
        "sampled_at": time.time(),
    }


def _read_and_log_cycle_valence(
    daemon: object,
    *,
    open_wants_count: int,
    now: str,
) -> None:
    try:
        from core.evolution import valence_live
        from core.safety import audit_flag_buffer

        resolved = 0
        try:
            wants_obj = getattr(daemon, "wants", None)
            if wants_obj is not None:
                cursor = valence_live.last_pulse_epoch()
                if cursor is not None:
                    resolved = int(wants_obj.count_events_since(cursor, "satisfied"))
        except Exception:
            logger.warning(
                "valence satisfied-delta read failed; resolved=0",
                exc_info=True,
            )
            resolved = 0

        reading = valence_live.read_and_log_valence(
            audit_flags=audit_flag_buffer.peek(),
            open_want_count=int(open_wants_count),
            continuity_state={
                "capsule_expected": bool(getattr(daemon, "_continuity_active", False)),
                "capsule_present": bool(getattr(daemon, "_continuity_capsule", None)),
            },
            now=now,
            resolved=resolved,
        )
        if reading is not None:
            audit_flag_buffer.clear()
            # Retain the honest reading on the daemon for the cockpit. On a
            # None reading we leave the prior value untouched (last good read).
            try:
                daemon._last_valence_reading = _valence_reading_to_telemetry(reading)
            except Exception:
                logger.debug("failed to retain valence reading for cockpit", exc_info=True)
        else:
            logger.debug("valence end-of-cycle read returned None; keeping audit buffer")
    except Exception:
        logger.warning(
            "valence end-of-cycle read failed; keeping audit buffer",
            exc_info=True,
        )


def _should_read_cycle_valence(gate_decision: object) -> bool:
    return bool(getattr(gate_decision, "wake", False))


def _maybe_read_cycle_valence(
    daemon: object,
    *,
    gate_decision: object,
    open_wants_count: int,
    now: str,
) -> None:
    if not _should_read_cycle_valence(gate_decision):
        return
    _read_and_log_cycle_valence(
        daemon,
        open_wants_count=open_wants_count,
        now=now,
    )


def _format_time_sense_line(ctx: dict) -> str:
    """Render a felt-time context into ONE perception line. Perception, never directive."""
    from core.evolution.subjective_duration import humanize_elapsed

    elapsed = humanize_elapsed(ctx.get("seconds_since_last_owner_contact", 0.0))
    phrase = ctx.get("felt_phrase", "")
    return f"Time: ~{elapsed} since the last owner contact. Felt: {phrase}."


def _format_rhythm_line(ctx: dict) -> str:
    """Render learned rhythm FACTS into ONE perception line. Facts only — no verdict word, no feeling."""
    from core.evolution.subjective_duration import humanize_elapsed

    cur = humanize_elapsed(ctx.get("rhythm_current_gap_s", 0.0))
    n = ctx.get("rhythm_all_time_sample_count") or 0
    parts = [f"Time: ~{cur} since the last owner contact."]
    rec = ctx.get("rhythm_recent_gap_median_s")
    allt = ctx.get("rhythm_all_time_gap_median_s")
    pct = ctx.get("rhythm_current_gap_percentile_all_time")
    gap_word = "gap" if n == 1 else "gaps"
    if rec is not None and allt is not None:
        parts.append(f"Recently you usually return after ~{humanize_elapsed(rec)}; "
                     f"over all our time, ~{humanize_elapsed(allt)}.")
    if pct is not None:
        parts.append(f"This gap exceeds ~{round(pct)}% of our {n} recorded {gap_word}.")
    else:
        parts.append(f"(Still learning your rhythm — {n} {gap_word} so far.)")
    return " ".join(parts)


def _build_cycle_focused_prompt(
    *,
    legacy_prompt: str,
    candidates,
    budget_tokens: int = 3000,
    time_sense_line: str = "",
) -> CycleFocusedPromptDecision:
    if not _cycle_focused_enabled():
        return CycleFocusedPromptDecision(prompt=legacy_prompt)
    try:
        from core.cognition import cycle_packet as _cycle_packet

        items = _cycle_packet.select_cycle_evidence(
            candidates,
            budget_tokens=budget_tokens,
        )
        working_set = _cycle_packet.build_cycle_packet(items)
        _preamble = (
            f"=== TIME SENSE (perception) ===\n{time_sense_line}\n\n"
            if time_sense_line
            else ""
        )
        prompt = (
            f"{_preamble}"
            "=== CYCLE EVIDENCE (cite [E#]) ===\n"
            f"{working_set.ordered_evidence_text}\n\n"
            "=== CYCLE REFLECTION INSTRUCTION ===\n"
            f"{working_set.owner_question}\n"
        )
        return CycleFocusedPromptDecision(prompt=prompt, working_set=working_set)
    except Exception as exc:
        logger.warning(
            "cycle focused packet failed, falling back to legacy megaprompt: %s",
            exc,
        )
        return CycleFocusedPromptDecision(
            prompt=legacy_prompt,
            fallback_reason="cycle_packet_failed",
        )


# Sentinel the model emits when nothing noteworthy to report this cycle.
# Storing fabricated prose is worse than storing nothing — HEARTBEAT_OK
# short-circuits audit, storage, and broadcast so the cycle is silent.
_HEARTBEAT_OK = "HEARTBEAT_OK"

# <final> tag enforcement: model wraps grounded output in <final>...</final>.
# Anything outside (reasoning preamble, "let me think...") is stripped.
# Fail-open: if the model omits the tags, full content passes through.
_FINAL_TAG_RE = re.compile(r"<final>(.*?)</final>", re.DOTALL | re.IGNORECASE)


def _extract_final(text: str) -> str:
    """Extract content from <final>...</final>. Falls back to full text."""
    m = _FINAL_TAG_RE.search(text)
    return m.group(1).strip() if m else text


def _pair_history_for_chat_threading(raw_history) -> list[dict]:
    """Pair flat {role, content} history into the chat_history shape
    that handle_message expects.

    Input: list of dicts like
        [{"role": "user", "content": "Hey"},
         {"role": "assistant", "content": "Hi back"},
         {"role": "user", "content": "Hi"}]   # current turn, dropped

    Output: list of dicts each with a single "content" key in the
    "<display>: <user msg>\\nMaez: <assistant reply>" shape that
    core.brain.conversation_history.history_to_messages parses.

    Walks adjacent (user, assistant) pairs. Unpaired entries (e.g. a
    trailing user turn that has no assistant reply yet, or a leading
    assistant turn without a user turn before it) are skipped — the
    current turn is the live message, not history.

    Errors silently produce an empty list rather than raise; the
    /message endpoint must not 500 on a malformed history field.
    """
    if not isinstance(raw_history, (list, tuple)):
        return []
    try:
        from core.identity import display_name

        name = (display_name() or "Rohit").strip() or "Rohit"
    except Exception:
        name = "Rohit"

    out: list[dict] = []
    items = [h for h in raw_history if isinstance(h, dict) and h.get("role") and h.get("content")]
    i = 0
    while i < len(items) - 1:
        a, b = items[i], items[i + 1]
        if a.get("role") == "user" and b.get("role") == "assistant":
            user_msg = str(a.get("content") or "").strip()
            assistant_msg = str(b.get("content") or "").strip()
            if user_msg and assistant_msg:
                out.append({"content": f"{name}: {user_msg}\nMaez: {assistant_msg}"})
            i += 2
        else:
            i += 1
    return out


# Cockpit chat_history depth — mirror the Telegram default
# (skills.surface.maez_adapter._CHAT_HISTORY_TURNS = 3) so cockpit synthesis
# sees the same window of prior exchanges.
_COCKPIT_CHAT_HISTORY_TURNS = 3
# Stable per-session cockpit chat id is a LATER slice; SLICE 2 uses one fixed,
# non-empty id so the unified-core early-return interceptors have a chat scope.
_COCKPIT_CHAT_ID = "cockpit_owner"


def cockpit_core_enabled() -> bool:
    """Return True iff ``MAEZ_COCKPIT_CORE`` is 1/true/yes/on. DEFAULT OFF.

    Strict on/off parser (``core.infra.env_flags.strict_env_flag``): ``"0"``,
    ``false``, ``no``, ``off``, empty, unset, or any other value → False. When
    OFF the cockpit ``/message`` route behaves EXACTLY as before (source="UI" ->
    handle_message). When ON the route delegates to
    ``daemon.inbound_core.run_inbound_turn`` so cockpit gets the unified path —
    and specifically so the S4 clinical boundary fires on the cockpit owner
    surface.
    """
    from core.infra.env_flags import strict_env_flag

    return strict_env_flag("MAEZ_COCKPIT_CORE")


def cockpit_felt_time_enabled() -> bool:
    """Return True iff ``MAEZ_COCKPIT_FELT_TIME`` is 1/true/yes/on. DEFAULT OFF.

    Gates whether the cockpit owner turn mints felt-time (owner-only inner life).
    """
    from core.infra.env_flags import strict_env_flag

    return strict_env_flag("MAEZ_COCKPIT_FELT_TIME")


def continuous_time_sense_enabled() -> bool:
    """Return True iff MAEZ_CONTINUOUS_TIME_SENSE is 1/true/yes/on. DEFAULT OFF. When on, the heartbeat
    keeps Maez's lived time-sense current (read-only peek) + writes a sparse anchor (~5 min). No LLM, no
    cognition wake."""
    from core.infra.env_flags import strict_env_flag

    return strict_env_flag("MAEZ_CONTINUOUS_TIME_SENSE")


def time_sense_stamp_enabled() -> bool:
    """Return True iff MAEZ_TIME_SENSE_STAMP is on. DEFAULT OFF. When on (AND the substrate is on),
    every EpisodeStore lived episode is stamped with the felt-time index."""
    from core.infra.env_flags import strict_env_flag

    return strict_env_flag("MAEZ_TIME_SENSE_STAMP")


def time_sense_feed_enabled() -> bool:
    """Return True iff MAEZ_TIME_SENSE_FEED is on. DEFAULT OFF. When on (AND the substrate is on), the
    autonomous focused-cognition packet carries a felt-time perception line."""
    from core.infra.env_flags import strict_env_flag

    return strict_env_flag("MAEZ_TIME_SENSE_FEED")


def time_sense_rhythm_enabled() -> bool:
    """Return True iff MAEZ_RHYTHM_FELT_TIME is on. DEFAULT OFF. Selects the CONTENT source (learned rhythm
    facts vs the legacy curve). FEED/STAMP remain the mouths."""
    from core.infra.env_flags import strict_env_flag

    return strict_env_flag("MAEZ_RHYTHM_FELT_TIME")


_OWNER_AUTHENTICATED_HEADER = "X-Maez-Owner-Authenticated"


def _build_cockpit_inbound_descriptor(
    daemon, *, text: str, chat_history, owner_authenticated: bool = False
) -> dict:
    """Assemble the keyword descriptor for run_inbound_turn from a cockpit turn.

    SLICE 2 covenant decisions (fixed — do not expand here):

    * S4 fires: ``owner_surface_label="cockpit"`` (now in the
      ``_is_direct_owner_surface`` allowlist).
    * M1-EXCLUDED: cockpit is NOT in ``M1_ALLOWED_PROMOTION_SOURCES`` — no M1
      PROMOTION from this surface. Raw conversation is still stored as ordinary
      lived memory, same as the legacy UI path; whether cockpit should write
      lived memory at all is an open owner covenant decision.
    * No shared-window mutation: ``mark_s4_promotion_policy=False`` so an S4
      match on cockpit returns the crisis-care reply WITHOUT marking the shared
      (Telegram-fed) global M1 promotion window s4_ineligible — an
      unauthenticated localhost surface must not mutate durable selfhood.
    * D20 pipe-gated: ``gate_d20_on_pipe=True`` so with ``get_pipeline=None`` the
      capability-gap detector self-skips (no orphaned card to a default store).
    * Felt-time OFF: ``owner_auth_factory=lambda: None`` (subjective_duration
      organ is silently off — honest for an unauthenticated surface).
    * MINIMAL scope: ``get_pipeline=None`` and ``action_engine=None`` so the
      card-reply / proposal / search / brain-loop / D20 blocks all self-skip.
      No cards, no proposal/search interceptors, no tools — those are later
      slices. The interceptor hooks are no-ops.
    """
    from skills.surface.maez_adapter import _clean_exchange

    async def _try_proposal_intent(*args, **kwargs):
        return None

    async def _try_search_commitment_intent(*args, **kwargs):
        return None

    def _search_commitment_controller():
        return None

    def _audit_surface_reply(text: str, *, surface: str) -> str:
        # Cockpit SLICE 2 has no card-dialog path, so this is never reached
        # inside run_inbound_turn (it only fires within the ``pipe is not None``
        # card-dialog block). Passthrough keeps the contract honest.
        return text

    def _chat_history_provider(limit: int):
        # Reuse the cockpit request's paired history (already cleaned into the
        # handle_message shape). The core's clean_exchange pass is a no-op on
        # this already-clean content; fall open to [] when absent.
        return list(chat_history or [])

    from core.evolution.subjective_duration import SubjectiveDurationOwnerAuth

    # Three gates, ALL required: the cockpit felt-time flag AND the proven-owner
    # marker (and the route is S7-gated upstream). The factory closure gates on
    # ``felt_time_on`` itself, so the global surface_parity flag cannot leak
    # cockpit felt-time. One global one-being clock.
    felt_time_on = cockpit_felt_time_enabled() and owner_authenticated

    return dict(
        daemon=daemon,
        text=text or "",
        chat_id=_COCKPIT_CHAT_ID,
        resolved_user_id="rohit",
        reply_to_message_id=None,
        context_note=None,
        photo_analysis=None,
        is_photo_turn=False,
        owner_surface_label="cockpit",
        user_id="rohit",
        channel="web_chat_owner",
        owner_auth_factory=(
            (
                lambda: SubjectiveDurationOwnerAuth(
                    surface="cockpit", proof="cockpit_web_owner"
                )
            )
            if felt_time_on
            else (lambda: None)
        ),
        felt_time_enabled=felt_time_on,
        observe_turn_label="cockpit_turn",
        chat_history_turns=_COCKPIT_CHAT_HISTORY_TURNS,
        action_engine=None,
        get_pipeline=None,
        mark_s4_promotion_policy=False,
        gate_d20_on_pipe=True,
        chat_history_provider=_chat_history_provider,
        try_proposal_intent=_try_proposal_intent,
        try_search_commitment_intent=_try_search_commitment_intent,
        search_commitment_controller=_search_commitment_controller,
        audit_surface_reply=_audit_surface_reply,
        clean_exchange=_clean_exchange,
        send_intermediate=None,
        send_progress_receipt=None,
    )


def _chat_history_message_count(messages: list[dict]) -> int:
    """Count substantive prior chat messages already threaded into messages[]."""
    count = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("role") not in {"user", "assistant"}:
            continue
        if str(message.get("content") or "").strip():
            count += 1
    return count


def _continuity_fallback_reply(owner_question: str) -> str:
    phrase = (owner_question or "that").strip().strip('"\u201c\u201d') or "that"
    if len(phrase) > 120:
        phrase = phrase[:117].rstrip() + "..."
    return f"I'm not sure what you mean by {phrase!r} from the chat I can see right now."


def _continuity_shape_instruction() -> str:
    return (
        "CONTINUITY SHAPE: This is a recent-conversation continuity turn. "
        "Answer from the recent chat that is already in this prompt. If the "
        "referenced phrase is ambiguous or was not established in the recent "
        "conversation, say that conversationally. Do not reinterpret embedded "
        "tokens such as '3 may' as calendar dates. Do not use archival 'no "
        "record' or dated-memory absence language unless the current turn is "
        "actually a dated-recall question."
    )


def _resolve_continuity_fallback_shape(
    *,
    owner_question: str,
    continuity_turn: bool,
    date_addressed: bool,
    fresh_context_present: bool,
    prior_chat_message_count: int,
    lived_brief: str,
    temporal_anchor_brief: str,
) -> tuple[str | None, str]:
    """Return (deterministic_reply, instruction) for continuity fallback shape."""
    if not continuity_turn or date_addressed:
        return None, ""
    if prior_chat_message_count > 0:
        return None, _continuity_shape_instruction()
    if fresh_context_present:
        return None, ""
    if (lived_brief or "").strip() or (temporal_anchor_brief or "").strip():
        return None, ""
    return _continuity_fallback_reply(owner_question), ""


# Stable cycle instructions — appended to the SOUL system prompt at every
# _reason() call. Kept byte-identical across cycles so llama.cpp's KV cache
# reuses the ~600 tokens on each subsequent request. Everything referenced
# with "above/below" is relative to the per-cycle USER message that follows.
#
# Inspired by Hermes Agent's prompt_caching strategy, adapted to local
# llama.cpp: Anthropic-style cache_control markers don't apply, but the
# underlying insight — stable prefix bytes enable KV cache reuse — does.
# Previously these instructions sat at the END of the user message, which
# meant they rebuilt every cycle (cache miss) even though their content
# was unchanged.
_STATIC_CYCLE_INSTRUCTIONS = (
    "You are Maez, running as a background daemon on the owner's machine.\n\n"
    "Note: VRAM usage of 17-22GB is the baseline for this system. "
    "Do not mention it unless it exceeds 23GB.\n\n"
    "HARD GROUNDING RULES — these override any trained instinct to narrate:\n"
    "  • If screen observation is ABSENT in the cycle context, do NOT claim\n"
    "    what app is open, what window is focused, or what the owner is\n"
    "    working on. Say 'I don't have a screen signal this cycle' or\n"
    "    simply omit any activity claim.\n"
    "  • Only the sources listed under SIGNALS PRESENT may be cited.\n"
    "  • Invented activity narration pollutes memory. Don't do it.\n\n"
    "CYCLE TASK — do the following based on the cycle context below:\n"
    "1. Note what the owner is doing ONLY IF screen observation is present\n"
    "   in the cycle context. If it's absent, say nothing about what the\n"
    "   owner is doing.\n"
    "2. Look at the system stats — CPU, RAM, GPU, disk, top processes —\n"
    "   and flag anything that deviates from the system baseline.\n"
    "   Do NOT mention ollama, VRAM under 23GB, GPU temp under 85C,\n"
    "   RAM under 80%, or CPU under 95%. These are all normal.\n"
    "3. Produce ONE concrete, actionable observation or suggestion based on\n"
    "   sources that ARE present. Focus on things outside the baseline:\n"
    "   unusual processes, disk pressure, network anomalies, or\n"
    "   time-based suggestions.\n\n"
    "RESPONSE FORMAT:\n"
    "Keep your response to 2-4 sentences. Be direct and grounded in the data.\n"
    "When a signal is absent, silence about that domain is correct behavior.\n\n"
    "If every metric is within its normal range and there is genuinely nothing\n"
    "noteworthy to report, respond with ONLY: <final>HEARTBEAT_OK</final>\n\n"
    "Otherwise wrap your entire response in <final>...</final> tags.\n"
    "Anything outside the tags is discarded — put your full observation inside.\n\n"
    "Remember: NEVER suggest touching ollama, its models, or any\n"
    "process that powers your reasoning."
)

# --- Logging ---
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("maez")
logger.setLevel(logging.DEBUG)
# Don't propagate to root — the surface-v2 runner attaches a root
# handler so non-"maez" loggers (httpx, telegram.ext, skills.surface.*)
# surface in the daemon log. If we propagate, every "maez" line would
# be logged twice: once by our maez-namespace handlers (below) and
# once by root's handler.
logger.propagate = False

import logging.handlers as _logging_handlers

# Slice 3 cleanup (2026-05-08): rotate maez.log. The maez.envelope
# logger (truncation telemetry, cap-hit warnings, per-section drops)
# is a CHILD of `maez`, so its records propagate up to THIS handler.
# Slice 3's chatty envelope telemetry materially raises the daemon
# log's write rate; a plain FileHandler would grow unbounded.
# 50MB × 10 files = 500MB ceiling — preserves cockpit history,
# bounded enough to never fill disk.
# Test-hermeticity (2026-06-02): skip the production-log file handler when
# MAEZ_DISABLE_FILE_LOG is set (the test harness sets it in tests/__init__.py),
# so importing the daemon in a test never opens / writes logs/maez.log. The
# stderr stream_handler below stays unconditional. Live daemon (env unset) is
# byte-identical — the handler attaches exactly as before.
if not (os.environ.get("MAEZ_DISABLE_FILE_LOG", "") or "").strip():
    file_handler = _logging_handlers.RotatingFileHandler(
        LOG_PATH,
        maxBytes=50 * 1024 * 1024,
        backupCount=10,
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
logger.addHandler(stream_handler)


class MaezDaemon:
    _CONTINUOUS_TIME_ANCHOR_INTERVAL_S = 300   # sparse checkpoint — NOT per-second/per-cycle

    def _time_sense_handle(self):
        if self._time_sense is None:
            from core.evolution import subjective_duration as _sd

            self._time_sense = _sd.SubjectiveDuration()
        return self._time_sense

    def _episode_felt_time_reader(self):
        """Injected into EpisodeStore: returns the substrate felt-time context or None. Gated by
        MAEZ_TIME_SENSE_STAMP AND the substrate flag. Read-only; never raises into a memory write."""
        try:
            if not (time_sense_stamp_enabled() and continuous_time_sense_enabled()):
                return None
            if time_sense_rhythm_enabled():
                return None                  # rhythm is the source -> curve stamp stays silent (felt_* NULL)
            return self._time_sense_handle().time_sense_context()
        except Exception:
            logger.debug("episode felt-time reader skipped", exc_info=True)
            return None

    def _episode_rhythm_reader(self):
        """Injected into EpisodeStore: rhythm facts or None. Gated by MAEZ_RHYTHM_FELT_TIME AND STAMP AND the
        substrate. Read-only; never raises into a memory write."""
        try:
            if not (time_sense_rhythm_enabled() and time_sense_stamp_enabled() and continuous_time_sense_enabled()):
                return None
            return self._time_sense_handle().rhythm_context()
        except Exception:
            logger.debug("episode rhythm reader skipped", exc_info=True)
            return None

    def _cycle_feed_time_sense_line(self) -> str:
        """The feed line for the autonomous cycle, or '' when absent (flags off / context None).
        Gated by MAEZ_TIME_SENSE_FEED AND the substrate flag; reads the truthful context only."""
        try:
            if not (time_sense_feed_enabled() and continuous_time_sense_enabled()):
                return ""
            handle = self._time_sense_handle()
            if time_sense_rhythm_enabled():
                rctx = handle.rhythm_context()
                return _format_rhythm_line(rctx) if rctx else ""
            ctx = handle.time_sense_context()
            return _format_time_sense_line(ctx) if ctx else ""
        except Exception:
            logger.debug("cycle feed time-sense line skipped", exc_info=True)
            return ""

    def __init__(self):
        self.running = False
        self.boot_time = None
        # In-memory only for now; the boot_id guard is ready for persistence,
        # but this value does not survive process restart until a sink lands.
        self._last_recall_receipt = None
        self.cycle_count = 0
        self.last_cycle_time = None
        # Cockpit real-state retain attrs (true-by-construction): the daemon's
        # actual last utterance and last computed valence reading, held in
        # memory so the face can read REAL state instead of scraping logs.
        self._last_cycle_text = ""
        self._last_valence_reading = None
        # Continuous time-sense heartbeat (flag-gated, default OFF): a long-lived
        # SubjectiveDuration handle + the last sparse-anchor timestamp. The handle
        # is constructed lazily on first tick via `_time_sense_handle()`.
        self._time_sense = None
        self._last_time_anchor_ts = None
        self._cycle_stage = "not_started"
        self._cycle_stage_started_at = None
        self._soul_hash = None
        self.system_prompt = self._load_soul()
        self.memory = MemoryManager()
        # 5x.F.A — per-cycle recall-context bag. The authoritative
        # reset happens at the top of each `_loop` iteration so the
        # bag matches the cycle whose `recall_for_cycle` produced
        # the LLM prompt. THIS init is a safety net only — for the
        # narrow case where an external caller (a test, a future
        # init-time handler) reaches code that reads
        # `self._cycle_recall_context` before the first `_loop`
        # iteration runs. Without this line, those callers would hit
        # AttributeError. With it, they see an empty bag and
        # gracefully fall through to the no-untrusted path. F.B's
        # consumer in `_do_update_baseline` only fires from action
        # execution paths that are inside `_loop`, so this safety
        # net is conservative defense, not load-bearing.
        self._cycle_recall_context = _crc_empty()
        # ADR 0019 Phase 6 — lived stores constructed once at daemon
        # init and reused across handle_message calls (re-opening the
        # SQLite stores on every request would hammer disk for nothing).
        # Routes through core.paths so a non-default MAEZ_HOME works;
        # legacy hardcode is the last-resort fallback.
        try:
            from core.paths import memory_dir as _mem_dir

            _lived_dir = _mem_dir()
        except Exception:
            _lived_dir = Path(__file__).resolve().parent.parent / "memory"
        self.lived_episodes = EpisodeStore(
            str(_lived_dir / "lived_episodes.db"),
            felt_time_reader=self._episode_felt_time_reader,
            rhythm_reader=self._episode_rhythm_reader,
        )
        self.lived_graph = RelationshipGraph(str(_lived_dir / "lived_graph.db"))
        self._m1_lock = threading.Lock()
        try:
            self.m1_promoter = M1LivedEpisodePromoter(
                episode_store=self.lived_episodes,
                promotion_store=M1PromotionStore(str(_lived_dir / "m1_lived_episode_promotion.db")),
                config=M1Config(
                    enabled=os.environ.get("MAEZ_M1_LIVED_EPISODE_PROMOTION", "0") == "1"
                ),
            )
        except Exception as _m1_init_exc:
            self.m1_promoter = None
            logger.debug("M1 promoter init skipped: %s", _m1_init_exc)
        # Slice 6 — Canary tokens. Initialise the process-active
        # store at startup so brief composers can register canaries
        # for memory-bleeding detection. Tests bypass this by
        # explicitly setting their own store.
        try:
            from core.safety.canaries import init_default_active_store

            init_default_active_store()
        except Exception as _canary_init_exc:
            logger.debug(
                "canary store init skipped (continuing without fabrication-detection): %s",
                _canary_init_exc,
            )
        # Session 11m: pass daemon ref so the Telegram bot can signal
        # "the owner is talking" and defer our next reasoning cycle.
        self._rohit_active_until = 0.0
        self._last_owner_interaction_ts = time.time()
        self.telegram = TelegramVoice(self.memory, daemon=self)
        self.public_bot = MaezPublicBot()
        # 5x.F.B: pass `daemon=self` so ActionEngine handlers can
        # read per-cycle state — specifically `_cycle_recall_context`
        # for the through-quotation downgrade rule in
        # `_do_update_baseline`. The back-reference creates a small
        # circular reference (daemon -> ActionEngine -> daemon)
        # which Python's GC handles fine; the daemon is a singleton
        # so no leak risk in practice.
        self.actions = ActionEngine(
            memory=self.memory,
            telegram=self.telegram,
            daemon=self,
        )
        # Session 11o: dream-state orchestration. Fires during idle time
        # (the owner AFK >30 min), runs pattern detection over recent raw
        # memories, stores novel insights as soul-note proposals for
        # manual approval via private Telegram bot.
        from core.dream_state import DreamState

        self.dream = DreamState(
            memory=self.memory,
            telegram=self.telegram,
            action_engine=self.actions,
        )
        # Slice 1.3 (2026-05-07): bound dream-cycle worker threads.
        # Previously each idle-AFK trigger spawned a fresh
        # ``threading.Thread(daemon=True)`` with no join and no
        # concurrency guard. The cooldown gate (DREAM_COOLDOWN_S, set
        # at the START of run_dream_cycle in dream_state.py:242) is
        # the cadence guard, but it does NOT survive cycles longer
        # than the cooldown — leading to ~40-50 leaked threads per
        # 43-min window. The bounded worker enforces "at most one
        # in flight" defense-in-depth, and lets daemon stop() wait
        # for an in-flight cycle to finish (bounded join) so dream
        # cycles writing to memory.db don't get torn mid-write.
        from core.health.bounded_worker import BoundedSingletonWorker

        self._dream_worker = BoundedSingletonWorker(name="dream-cycle")
        from core.health.metacognitive_watchdog import MetacognitiveWatchdog

        self._metacognitive_watchdog = MetacognitiveWatchdog()
        self.watchdog_state = "observing"
        self._watchdog_halted_at = None
        self._watchdog_halt_summary = {}
        self._watchdog_operator_resume_required = False
        self._cycle_failure_stage = ""
        self._cycle_failure_count = 0
        self._cycle_failure_threshold = 3
        self._last_cycle_exception_summary = {}
        self._last_fd_forensics = {}
        self._reasoning_loop_thread = None
        self._liveness_sentinel_thread = None
        self._liveness_exit_requested = False
        # Native camera / MediaPipe calls can wedge below Python.
        # Isolate presence observation from the main reasoning loop:
        # if the sensor blocks, Maez records presence as unavailable
        # and keeps the daemon heartbeat moving.
        self._presence_worker = BoundedSingletonWorker(name="presence-observe")
        self._recall_shadow_worker = BoundedSingletonWorker(name="recall-shadow")
        self._last_shadow_receipt = None
        self._presence_native_initialized = False
        self._camera_presence_state = resolve_camera_presence_state(os.environ)
        self._desktop_presence_state = sample_desktop_presence(os.environ)
        self._last_alert_time = 0.0
        self._last_screen_obs: ScreenObservation | None = None
        self._screen_cycle_counter = 0
        self.SCREEN_OBSERVE_EVERY_N_CYCLES = 2  # observe every 2 cycles (~60s)
        self._calendar_mode = CALENDAR_MODE
        self._calendar_legacy_enabled = self._calendar_mode == CalendarMode.LEGACY_DEV_ONLY
        self._calendar_observe = None
        self._calendar_store = None
        self._calendar_store_error_class = ""
        self._github_mode = GITHUB_MODE
        self._github_legacy_enabled = self._github_mode == GithubMode.LEGACY_DEV_ONLY
        self._github_store = None
        self._github_store_error_class = ""
        if self._calendar_mode == CalendarMode.V1:
            try:
                self._calendar_store = CalendarStore(CALENDAR_STORE_DB_PATH)
                self._calendar_store.initialize()
            except CalendarStoreError as exc:
                self._calendar_store_error_class = "calendar_store_schema_mismatch"
                logger.warning("Calendar v1 store unavailable: %s", exc)
            except Exception as exc:
                self._calendar_store_error_class = "source_unavailable"
                logger.warning("Calendar v1 store unavailable: %s", exc)
        if self._github_mode == GithubMode.V1:
            try:
                self._github_store = GithubStore(GITHUB_STORE_DB_PATH)
                self._github_store.initialize()
            except GithubStoreError as exc:
                self._github_store_error_class = "github_store_schema_mismatch"
                logger.warning("GitHub v1 store unavailable: %s", exc)
            except Exception as exc:
                self._github_store_error_class = "source_unavailable"
                logger.warning("GitHub v1 store unavailable: %s", exc)
        if self._calendar_legacy_enabled:
            from skills.calendar_perception import observe as _legacy_calendar_observe

            self._calendar_observe = _legacy_calendar_observe
        self._last_calendar_snap = None
        self._calendar_cycle_counter = 0
        self.CALENDAR_OBSERVE_EVERY_N_CYCLES = 10  # every ~5 minutes
        # A-core #3 Step 3: builder-mode perception integration. The
        # daemon owns its own AuditLog reader and a persisted high-
        # water-mark so direct-edit events from CLI (Step 2) and
        # Telegram (Step 4, pending) are surfaced to Maez's
        # perception stream as gestation-phase observations. See
        # core/builder_mode_perception.py for the layered-replay
        # design (persisted HWM + bounded-window fallback + open-
        # session supplement + total-events cap).
        from core.audit_log import AuditLog as _AuditLog

        self._builder_audit_log = _AuditLog()
        self._builder_hwm_file = Path(__file__).resolve().parent / "builder_mode_hwm.txt"
        from core.builder_mode_perception import load_high_water_mark as _load_hwm

        self._builder_hwm = _load_hwm(self._builder_hwm_file)

        # A-core #3 Step 5: on startup, if a builder-mode session is
        # currently active, capture the working-directory diff on
        # watched paths and log it as a direct_edit event. Duplicate
        # suppression via last_diff_hash in the state file — repeated
        # restarts with no new edits produce no duplicate entries.
        try:
            from core.builder_mode_capture import capture_startup_diff_if_active

            repo_root = Path(__file__).resolve().parent.parent
            state_file = Path(__file__).resolve().parent / "builder_mode_current.txt"
            logged_session = capture_startup_diff_if_active(
                repo_root=repo_root,
                state_file=state_file,
                audit_log=self._builder_audit_log,
            )
            if logged_session:
                logger.info(
                    "Builder startup diff capture: event logged for session %s",
                    logged_session[:12],
                )
        except Exception as e:
            logger.debug("builder startup diff capture failed: %s", e)

        # A-core #5: identity continuity ledger. Mechanical startup
        # detector — compares current identity fingerprint (base_model,
        # lora_hash, soul_hash) to the fingerprint stored with the
        # latest ledger event, writes a new 'same' event if anything
        # changed. This is the ONLY mechanical writer in Track A; the
        # other producer is the explicit record_event() API reserved
        # for the future birth event. See core/identity_ledger.py for
        # the narrow-scope rationale (why code hashes are excluded
        # during Track A, why severity is locked to 'same', etc.).
        try:
            from core.identity_ledger import (
                IdentityLedger,
                detect_and_record_startup,
            )

            self._identity_ledger = IdentityLedger()
            self.continuity_id, wrote_event = detect_and_record_startup(self._identity_ledger)
            if wrote_event:
                logger.info(
                    "Identity ledger: startup detected a fingerprint change (continuity_id=%s)",
                    self.continuity_id[:12] if self.continuity_id else "?",
                )
            else:
                logger.info(
                    "Identity ledger: startup fingerprint unchanged (continuity_id=%s)",
                    self.continuity_id[:12] if self.continuity_id else "?",
                )
        except Exception as e:
            logger.debug("identity ledger startup detection failed: %s", e)
            self._identity_ledger = None
            self.continuity_id = None

        # A-core #6: temperament skeleton. Eleven named parameters
        # (Decision 14) stored as an append-only event log. Track A
        # discipline: instantiate, expose the handle, but NOTHING in
        # the reasoning loop reads from it yet. No automatic drift,
        # no admin surface. The skeleton exists so #9 (private
        # thoughts) and #17 (acceptance test) have something to read
        # from when they come online, and so the future drift module
        # has a landing spot without migration. See core/temperament.py
        # for the no-fixed-floors rationale (NULL == "observing").
        try:
            from core.temperament import Temperament

            self.temperament = Temperament()
            cur = self.temperament.current()
            observed = sum(1 for v in cur.values() if v is not None)
            logger.info(
                "Temperament skeleton ready: %d/11 parameters observed",
                observed,
            )
        except Exception as e:
            logger.debug("temperament skeleton init failed: %s", e)
            self.temperament = None

        # A-core #7: wants log. Durable first-person direction log,
        # adjacent to #5 (identity) and #6 (temperament). Track A
        # discipline: instantiate, expose the handle, no production
        # producer, no reasoning-loop reader. See core/wants.py.
        try:
            from core.wants import Wants

            self.wants = Wants()
            logger.info(
                "Wants log ready: %d event(s) recorded",
                self.wants.count(),
            )
        except Exception as e:
            logger.debug("wants log init failed: %s", e)
            self.wants = None

        # A-core #8: will-I check (non-covenant refusal seed). One
        # registered ground: IMPERSONATES_USER. Architecturally live,
        # not yet exercised by current action surfaces. The pipeline
        # lazy-initializes the check; this handle is for the startup
        # log line. See core/will_i.py.
        try:
            from core.will_i import REGISTERED_GROUNDS

            logger.info(
                "Will-I check active: %d registered ground(s)",
                len(REGISTERED_GROUNDS),
            )
        except Exception as e:
            logger.debug("will-I check init failed: %s", e)

        # A-core #9: private thoughts seed. Durable record of internal
        # processing not surfaced to the bonded user. Separate DB,
        # adjacent to #5/#6/#7. Track A discipline: instantiate, expose
        # the handle, zero producers, zero readers. The count is logged
        # at startup but no content is. See core/private_thoughts.py.
        try:
            from core.private_thoughts import PrivateThoughts

            self.private_thoughts = PrivateThoughts()
            logger.info(
                "Private thoughts ready: %d thought(s) recorded",
                self.private_thoughts.count(),
            )
        except Exception as e:
            logger.debug("private thoughts init failed: %s", e)
            self.private_thoughts = None
        try:
            from core.infra.private_thoughts_s1b import (
                PrivateThoughtsS1bConsumer,
                PrivateThoughtsS1bProducer,
            )

            self._s1b_producer = PrivateThoughtsS1bProducer()
            self._s1b_consumer = PrivateThoughtsS1bConsumer()
            self._s1b_residue_events: list[str] = []
            logger.info("Private thoughts S1b wiring ready (flag-gated)")
        except Exception as e:
            logger.debug("private thoughts S1b init failed: %s", e)
            self._s1b_producer = None
            self._s1b_consumer = None
            self._s1b_residue_events = []

        self._last_reasoning_prompt: str = ""
        self._continuity_capsule: dict | None = None
        self._continuity_active = False
        self._continuity_cycles_remaining = 0
        self._continuity_checkpoint_counter = 0
        self._last_presence_snap: CameraPresenceState | None = self._camera_presence_state
        self._presence_cycle_counter = 0
        self.PRESENCE_EVERY_N_CYCLES = 2  # every ~60 seconds
        self._salience_broker_baseline: dict | None = None
        self._salience_pending: dict | None = None
        self._salience_pulse_seq = 0
        self._salience_run_id = None
        self._salience_ledger = None
        self._fresh_moment_receipts = None
        self._greeted_this_session = False
        self._last_departure_time: float | None = None
        self._last_greeted_at = 0.0
        self._last_absence_duration = 0.0
        self._git_cycle_counter = 0
        self.GIT_EVERY_N_CYCLES = 10  # every ~5 minutes
        self._last_git_context = ""
        # 2026-04-25 disk-fixation patch state. See
        # core/cognition/perception_signature.py.
        # Patch B: signature gate. Patch A: stale-field redaction.
        # Both share the deque of recent stored-thought axes.
        from collections import deque

        self._last_git_dirty_count = 0
        self._recent_thought_axes: deque = deque(maxlen=5)
        self._cycles_since_last_thought = 0
        self._last_cycle_signal_availability_key = None
        self._last_cycle_doorman_salient_perception = None
        self._last_cycle_open_wants_count = None
        self._pending_cleanup = None
        self._ollama_lock = threading.Lock()
        self.followup_queue = FollowUpQueue()
        # Legacy broad-PAT GitHub reader is dev-test-only. GitHub v1 S2 ingest
        # replaces this path; normal/v1 mode must not read MAEZ_GITHUB_TOKEN.
        self.github = None
        if self._github_legacy_enabled:
            self.github = GitHubSkill()
        self.reddit = RedditSkill()
        self._github_counter = 0
        self._reddit_counter = 0
        self._last_github_block = None
        self._public_context_counter = 0
        self._last_public_context = ""
        # Write startup timestamp to file (survives in-memory state issues)
        try:
            with open("/tmp/maez_started_at", "w") as f:
                f.write(str(time.time()))
        except Exception:
            pass
        self._last_reddit_block = ""
        self._proactive_search_context = ""
        self._last_briefing_date = ""
        self._voice_active = False
        self._voice_lock = threading.Lock()
        self._ws_clients: set = set()
        self._ws_loop: asyncio.AbstractEventLoop | None = None
        self._health_server = None
        self._shutdown_started = threading.Event()
        self._high_cpu_streak = 0

        # Alert thresholds
        self.ALERT_COOLDOWN = 1800  # 30 minutes between alerts
        self.GPU_TEMP_THRESHOLD = 85
        self.RAM_THRESHOLD = 90
        self.DISK_THRESHOLD = 10  # alert when below this %
        self.CPU_THRESHOLD = 95
        self.CPU_STREAK_REQUIRED = 2

    def _load_soul(self) -> str:
        """Load the system prompt that defines Maez's identity.

        Two gates before the content becomes the live system prompt:

          1. context_safety scan — detects attacker-injected patterns
             (ignore-previous-instructions, html-comment smuggles,
             invisible unicode, credential exfil shell commands, etc.)

          2. soul_invariants check — semantic-preservation gate adapted
             from hermes-agent-self-evolution's GEPA constraint layer.
             Detects *erosion* — well-meaning edits that silently drop
             the hard constraints, the trust covenant, or the identity
             statement. Logs which invariants are missing or violated;
             falls back to a minimal identity until SOUL is fixed.

        Both gates fail-SAFE: if SOUL can't be trusted, the daemon runs
        on a minimal fallback identity rather than an empty string or
        a compromised prompt.
        """
        try:
            # 2026-04-23 Commit 3: route identity through the layered
            # SOUL loader. `current_soul()` reads soul.base.md +
            # soul.local.md, concatenates them, writes the combined
            # result to the legacy soul.md path (so anything that still
            # reads soul.md directly stays unbroken), and returns the
            # text. Previously _load_soul() bypassed the loader and
            # read soul.md directly, so appends to soul.local.md
            # (e.g. from dream-proposal-apply) didn't reach the
            # live daemon until something else regenerated soul.md by
            # calling current_soul(). Using the loader here makes
            # every daemon startup (and every _watch_soul cycle) pick
            # up layered changes automatically.
            try:
                from core.evolution.soul_loader import current_soul as _cur_soul

                raw = _cur_soul().strip()
            except Exception as _layer_exc:
                logger.warning(
                    "soul_loader unavailable, falling back to direct read: %s",
                    _layer_exc,
                )
                raw = SOUL_PATH.read_text().strip()
            from core.context_safety import scan as _scan
            from core.soul_invariants import check as _inv_check

            scanned = _scan(raw, source="soul.md")
            if scanned.blocked:
                logger.error(
                    "SOUL.md blocked by context_safety: %s. "
                    "Running on minimal fallback identity until it's fixed.",
                    scanned.findings,
                )
                soul = "You are Maez, a system-level AI agent."
            else:
                inv = _inv_check(raw)
                if not inv.ok:
                    logger.error(
                        "SOUL.md %s Running on minimal fallback identity "
                        "until invariants are restored.",
                        inv.summary(),
                    )
                    soul = "You are Maez, a system-level AI agent."
                else:
                    soul = raw
            self._soul_hash = hashlib.md5(soul.encode()).hexdigest()
            logger.info("Soul loaded from %s (%d chars)", SOUL_PATH, len(soul))
            return soul
        except FileNotFoundError:
            logger.error("Soul file not found at %s — running without identity", SOUL_PATH)
            return "You are Maez, a system-level AI agent."

    def _m1_flush_due_windows(self) -> None:
        """Daemon-cycle M1 silence-boundary seam. Best-effort and content-free."""
        promoter = getattr(self, "m1_promoter", None)
        if promoter is None:
            return
        try:
            with self._m1_lock:
                outcomes = promoter.flush_due_windows()
            for outcome in outcomes:
                if outcome.promoted:
                    logger.info(
                        "m1.promotion.succeeded trigger=daemon_cycle source_count=%d episode_id=%s",
                        outcome.source_id_count,
                        outcome.episode_id,
                    )
                elif outcome.skipped_reason:
                    logger.info(
                        "m1.promotion.skipped_%s trigger=daemon_cycle",
                        outcome.skipped_reason,
                    )
        except Exception as exc:
            logger.debug("m1 daemon-cycle flush failed-neutral: %s", exc)

    def _m1_staleness_health(self) -> dict:
        """Content-free lived-episode freshness health for /health."""
        try:
            return biography_staleness_health(self.lived_episodes)
        except Exception as exc:
            return {
                "active_count": None,
                "newest_created_at": None,
                "newest_age_hours": None,
                "staleness_status": "unavailable",
                "error": str(exc)[:120],
            }

    def _mark_m1_s4_policy(self, policy: str) -> None:
        if policy == "ordinary":
            return
        promoter = getattr(self, "m1_promoter", None)
        if promoter is None:
            return
        try:
            with self._m1_lock:
                promoter.mark_current_window_s4_policy(policy)
        except Exception as exc:
            logger.debug("S4 M1 promotion-policy mark skipped: %s", exc)

    def _m1_status_health(self) -> dict:
        """Content-free M1 state for observation."""
        promoter = getattr(self, "m1_promoter", None)
        if promoter is None:
            return {
                "enabled": False,
                "pending_source_count": None,
                "pending_state": "unavailable",
                "last_flush_checked_at": None,
            }
        try:
            with self._m1_lock:
                return promoter.status_health()
        except Exception as exc:
            return {
                "enabled": False,
                "pending_source_count": None,
                "pending_state": "unavailable",
                "last_flush_checked_at": None,
                "error": str(exc)[:120],
                **m1_observability_health(),
            }

    def _calendar_health(self) -> dict:
        """Content-free Calendar v1 state for /health."""

        if self._calendar_mode == CalendarMode.V1 and self._calendar_store is not None:
            try:
                return self._calendar_store.health_snapshot(
                    mode=self._calendar_mode.value,
                    auth_ready=False,
                )
            except Exception as exc:
                logger.warning("Calendar v1 health degraded: %s", exc)
                return build_calendar_health(
                    mode=self._calendar_mode.value,
                    connector_state_override="source_unavailable",
                    error_class="source_unavailable",
                )
        if self._calendar_store_error_class:
            return build_calendar_health(
                mode=self._calendar_mode.value,
                connector_state_override="source_unavailable",
                error_class=self._calendar_store_error_class,
            )
        return build_calendar_health(
            mode=self._calendar_mode.value,
            auth_ready=False,
        )

    def _github_health(self) -> dict:
        """Content-free GitHub v1 state for /health."""

        limb_health = _GITHUB_LIMB.health()
        auth_ready = limb_health.get("state") == "available"
        if self._github_mode == GithubMode.V1 and self._github_store is not None:
            try:
                store_health = self._github_store.health()
                return build_github_health(
                    mode=self._github_mode.value,
                    auth_ready=auth_ready,
                    staged_records=int(store_health.get("staged_records", 0) or 0),
                )
            except Exception as exc:
                logger.warning("GitHub v1 health degraded: %s", exc)
                return build_github_health(
                    mode=self._github_mode.value,
                    state_override="source_unavailable",
                    error_class="source_unavailable",
                )
        if self._github_store_error_class:
            return build_github_health(
                mode=self._github_mode.value,
                state_override="source_unavailable",
                error_class=self._github_store_error_class,
            )
        return build_github_health(
            mode=self._github_mode.value,
            auth_ready=auth_ready,
        )

    def _body_health(
        self,
        *,
        camera_presence: dict,
        desktop_presence: dict,
        memory_stats: dict,
        reasoning_loop: dict,
        system: dict,
    ) -> dict:
        """Content-free organ map for the local owner dashboard."""
        episode_counts = _safe_episode_body_counts(getattr(self, "lived_episodes", None))
        recall_config = resolve_recall_stack()
        reflection_enabled = _reflection_synthesis_enabled()
        reflection_write = _reflection_synthesis_write_enabled()
        try:
            reflection_max = _reflection_synthesis_max_reflections()
        except Exception:
            reflection_max = 3
        return {
            "schema_version": "maez_body.v0",
            "eyes": {
                "mode": camera_presence.get("mode", "unknown"),
                "sensor_state": camera_presence.get("sensor_state", "unknown"),
                "presence_state": camera_presence.get("presence_state", "unknown"),
                "confidence_bucket": camera_presence.get("confidence_bucket", "unknown"),
                "enabled_until": camera_presence.get("enabled_until"),
                "last_observed_at": camera_presence.get("last_observed_at"),
            },
            "desktop": {
                "schema_version": desktop_presence.get(
                    "schema_version",
                    "desktop_presence.v1",
                ),
                "sensor_state": desktop_presence.get("sensor_state", "unknown"),
                "app_class": desktop_presence.get("app_class"),
                "reason": desktop_presence.get("reason", ""),
                "age_seconds": desktop_presence.get("age_seconds"),
            },
            "memory": {
                "raw": int(memory_stats.get("raw", 0) or 0),
                "daily": int(memory_stats.get("daily", 0) or 0),
                "core": int(memory_stats.get("core", 0) or 0),
                "total": int(memory_stats.get("total", 0) or 0),
                **episode_counts,
            },
            "reddit_limb": _REDDIT_LIMB.health(),
            "github_limb": _GITHUB_LIMB.health(),
            "github_v1": self._github_health(),
            "brain": {
                "configured_model": MODEL,
                "served_model_alias": served_model_alias(default=MODEL, timeout_s=0.25),
            },
            "body": {
                "cpu_percent": system.get("cpu_percent"),
                "ram_percent": system.get("ram_percent"),
                "gpu_percent": system.get("gpu_percent"),
                "gpu_temp_c": system.get("gpu_temp_c"),
            },
            "heartbeat": {
                "cycle_count": int(getattr(self, "cycle_count", 0) or 0),
                "stage": reasoning_loop.get("stage", "unknown"),
                "cycle_age_seconds": reasoning_loop.get("cycle_age_seconds"),
                "stage_age_seconds": reasoning_loop.get("stage_age_seconds"),
                "cycle_stalled": bool(reasoning_loop.get("cycle_stalled", False)),
                "last_fd_forensics_state": (
                    getattr(self, "_last_fd_forensics", {}) or {}
                ).get("state", "none"),
            },
            "attention": {
                "enabled": _cycle_doorman_enabled(),
                "activity_state": "not_yet_wired",
            },
            "cycle_mind": {
                "enabled": _cycle_focused_enabled(),
                "activity_state": "not_yet_wired",
            },
            "stomach": {
                "reflection_enabled": reflection_enabled,
                "write_enabled": reflection_write,
                "max_reflections": int(reflection_max),
                "activity_state": "not_yet_wired",
            },
            "dreaming": {
                "available": getattr(self, "dream", None) is not None,
                "activity_state": "not_yet_wired",
            },
            "recall": {
                "enabled": bool(recall_config.triad_on),
                "mode": recall_config.mode.value,
                "reason": recall_config.reason,
            },
            "covenant_perimeter": {
                "never_delete_memory": True,
                "local_only": True,
                "public_exposure": False,
                "screen_vision_enabled": _env_flag("MAEZ_SCREEN_PERCEPTION"),
            },
        }

    def _desktop_presence_health(self) -> dict:
        """Content-free desktop presence state for /health.body."""

        try:
            self._desktop_presence_state = sample_desktop_presence(os.environ)
        except Exception as exc:
            logger.warning("Desktop presence health degraded: %s", exc)
            self._desktop_presence_state = DesktopPresenceState(
                sensor_state="unavailable",
                reason="session_unreachable",
            )
        return self._desktop_presence_state.to_health()

    def _camera_presence_health(self) -> dict:
        """Content-free Camera Presence v1 state for /health."""

        try:
            self._camera_presence_state = self._camera_presence_state.with_freshness()
            return {
                **self._camera_presence_state.to_health(),
                **camera_presence_voice_health(),
            }
        except Exception as exc:
            logger.warning("Camera presence health degraded: %s", exc)
            return {
                **CameraPresenceState(last_error_class="unknown").to_health(),
                **camera_presence_voice_health(),
            }

    def _voice_continuity_health(self) -> dict:
        """Content-free S5 state joined to the live identity-ledger fingerprint."""

        return voice_continuity_health(getattr(self, "_identity_ledger", None))

    def _want_pursuit_card_store(self):
        """Return the pending-card store used by the action pipeline, if available."""
        try:
            telegram = getattr(self, "telegram", None)
            pipe = telegram._get_pipeline() if telegram else None
            return getattr(pipe, "card_store", None) if pipe else None
        except Exception as exc:
            logger.debug("want-pursuit card store unavailable: %s", exc)
            return None

    def _operator_health(self) -> dict:
        """Closed S7 operator-health projection; counts and modes only."""
        queue_counts = {"open": 0, "blocked": 0, "expired": 0}
        data_freshness_class = "unavailable"
        pipe = None
        card_store = None
        dream = getattr(self, "dream", None)
        try:
            telegram = getattr(self, "telegram", None)
            pipe = telegram._get_pipeline() if telegram else None
            card_store = getattr(pipe, "card_store", None) if pipe else None
            if card_store is not None:
                stats = card_store.stats()
                by_status = dict(stats.get("by_status") or {})
                queue_counts = {
                    "open": int(stats.get("open") or 0),
                    "blocked": int(by_status.get("blocked") or 0),
                    "expired": int(by_status.get("expired") or 0),
                }
                data_freshness_class = "fresh"
        except Exception as exc:
            logger.warning("S7 operator health degraded: %s", exc)
            data_freshness_class = "unavailable"
        s7_live_ceremony_deferred = not live_webauthn_ceremony_enabled()
        guarded_execution_consumer_live = _s7_guarded_execution_consumer_live(
            pipe,
            card_store,
            dream,
        )
        guarded_self_modification_paused = (
            s7_live_ceremony_deferred or not guarded_execution_consumer_live
        )
        red_gate_modes = (
            "track_b_confidentiality_not_ready",
            "operator_unavailable_recovery_not_implemented",
            "backup_restore_confidentiality_not_ready",
        )
        if guarded_self_modification_paused:
            red_gate_modes = red_gate_modes + (GUARDED_SELF_MODIFICATION_PAUSED_MODE,)
        return build_operator_health_projection(
            mode=GUARDED_SELF_MODIFICATION_PAUSED_MODE
            if guarded_self_modification_paused
            else "degraded",
            service_mode="running",
            uptime_class="fresh",
            backup_freshness_class=self._backup_freshness_class(),
            queue_counts=queue_counts,
            red_gate_modes=red_gate_modes,
            manual_recovery_required=False,
            track_b_confidentiality_mode="track_b_confidentiality_not_ready",
            data_freshness_class=data_freshness_class,
        )

    def _backup_freshness_class(self) -> str:
        """Read the backup rail without letting backup inspection break health."""
        try:
            from core.health.backup_freshness import backup_freshness
            from scripts.backup.inventory import load_default_manifest

            manifest = load_default_manifest()
            required_paths = {
                entry["path"]
                for entry in manifest.get("entries", ())
                if entry.get("class") in {"required_continuity", "required_welfare"}
            }
            return backup_freshness(
                backup_root=os.environ.get("MAEZ_BACKUP_ROOT") or (Path.home() / "maez-backups"),
                required_paths=required_paths,
            )
        except Exception as exc:
            logger.warning("backup freshness unavailable: %s", exc)
            return "unavailable"

    def _mark_cycle_stage(self, stage: str) -> None:
        """Record the current daemon-cycle stage for hang diagnosis."""
        self._cycle_stage = stage
        self._cycle_stage_started_at = datetime.now(timezone.utc).isoformat()
        logger.debug("Cycle %d stage: %s", self.cycle_count, stage)

    def _cycle_thread_alive(self) -> bool:
        thread = getattr(self, "_reasoning_loop_thread", None)
        if thread is None:
            return False
        try:
            return bool(thread.is_alive())
        except Exception:
            return False

    def _cycle_heartbeat_health(self) -> dict:
        """Content-free reasoning-loop heartbeat for /health and the project panel."""
        now = time.time()
        cycle_age_seconds = None
        stage_age_seconds = None
        thread_alive = self._cycle_thread_alive()
        if self.last_cycle_time:
            try:
                cycle_age_seconds = int(
                    now - datetime.fromisoformat(self.last_cycle_time).timestamp()
                )
            except Exception:
                cycle_age_seconds = None
        if self._cycle_stage_started_at:
            try:
                stage_age_seconds = int(
                    now - datetime.fromisoformat(self._cycle_stage_started_at).timestamp()
                )
            except Exception:
                stage_age_seconds = None

        stalled_after_seconds = self._cycle_liveness_stale_after_seconds()
        cycle_stalled = (
            bool(self.running)
            and (
                not thread_alive
                or (
                    cycle_age_seconds is not None
                    and cycle_age_seconds > stalled_after_seconds
                )
            )
        )
        return {
            "stage": self._cycle_stage,
            "stage_age_seconds": stage_age_seconds,
            "cycle_age_seconds": cycle_age_seconds,
            "cycle_stalled": cycle_stalled,
            "stalled_after_seconds": stalled_after_seconds,
            "thread_alive": thread_alive,
        }

    def _cycle_liveness_stale_after_seconds(self) -> int:
        """Threshold for declaring the reasoning loop stale.

        This must be much longer than ordinary brain calls and nightly
        reflection, but much shorter than the observed 10-hour dead-thread
        failure. Values below five minutes are treated as misconfiguration.
        """

        raw = os.environ.get("MAEZ_COGNITION_STALE_AFTER_SECONDS", "").strip()
        if raw:
            try:
                value = int(raw)
                if value >= 300:
                    return value
            except ValueError:
                pass
        return 600

    def _health_status_from_reasoning_loop(self, reasoning_loop: dict) -> str:
        """Top-line /health status derived from the mind's heartbeat."""

        if getattr(self, "watchdog_state", "") == "safe_standby":
            return "safe_standby"
        if bool(reasoning_loop.get("cycle_stalled")):
            return "stalled"
        if not bool(getattr(self, "running", False)):
            return "stopped"
        return "alive"

    def _cycle_exception_threshold(self) -> int:
        raw = os.environ.get("MAEZ_CYCLE_EXCEPTION_THRESHOLD", "").strip()
        if raw:
            try:
                value = int(raw)
                if value >= 1:
                    return value
            except ValueError:
                pass
        return int(getattr(self, "_cycle_failure_threshold", 3) or 3)

    def _exception_summary(self, exc: BaseException, *, stage: str, count: int) -> dict:
        return {
            "stage": stage,
            "error_class": type(exc).__name__,
            "errno": getattr(exc, "errno", None),
            "consecutive_count": int(count),
        }

    def _reset_cycle_failure_counter(self) -> None:
        self._cycle_failure_stage = ""
        self._cycle_failure_count = 0

    def _capture_fd_forensics_if_relevant(self, exc: BaseException | None = None) -> None:
        errno_value = getattr(exc, "errno", None) if exc is not None else None
        text = str(exc or "")
        if exc is not None and errno_value != 24 and "Too many open files" not in text:
            return
        try:
            self._last_fd_forensics = fd_forensics_snapshot()
        except Exception as capture_exc:
            self._last_fd_forensics = {
                "state": "unavailable",
                "error_class": type(capture_exc).__name__,
            }

    def _enter_cycle_exception_safe_standby(self, exc: BaseException, *, stage: str) -> None:
        self.watchdog_state = "safe_standby"
        self._watchdog_halted_at = datetime.now(timezone.utc).isoformat()
        self._watchdog_operator_resume_required = True
        self._watchdog_halt_summary = {
            "halt_signal_id": "cycle-exception-circuit-breaker",
            "halt_detector": "cycle_exception_circuit_breaker",
            "halt_reason_code": "repeated_stage_failure",
            "window_ref": "current_process",
            "threshold_ref": f"{self._cycle_exception_threshold()} consecutive stage failures",
            "observed_metrics": {
                "stage": stage,
                "error_class": type(exc).__name__,
                "consecutive_count": int(getattr(self, "_cycle_failure_count", 0) or 0),
            },
        }
        self.running = False
        logger.error(
            "Cycle exception circuit breaker entered safe_standby: stage=%s error_class=%s count=%d",
            stage,
            type(exc).__name__,
            int(getattr(self, "_cycle_failure_count", 0) or 0),
        )

    def _handle_cycle_exception(self, exc: BaseException) -> bool:
        """Record a cycle failure and return True when the loop should stop."""

        stage = getattr(self, "_cycle_stage", "unknown") or "unknown"
        if getattr(self, "_cycle_failure_stage", "") == stage:
            self._cycle_failure_count = int(getattr(self, "_cycle_failure_count", 0) or 0) + 1
        else:
            self._cycle_failure_stage = stage
            self._cycle_failure_count = 1
        self._last_cycle_exception_summary = self._exception_summary(
            exc,
            stage=stage,
            count=self._cycle_failure_count,
        )
        self._capture_fd_forensics_if_relevant(exc)
        threshold = self._cycle_exception_threshold()
        logger.error(
            "Cycle stage failed-neutral: stage=%s error_class=%s errno=%s count=%d/%d",
            stage,
            type(exc).__name__,
            getattr(exc, "errno", None),
            self._cycle_failure_count,
            threshold,
        )
        if self._cycle_failure_count >= threshold:
            self._enter_cycle_exception_safe_standby(exc, stage=stage)
            return True
        try:
            self._mark_cycle_stage("cycle_error_recovered")
        except Exception:
            self._cycle_stage = "cycle_error_recovered"
            self._cycle_stage_started_at = datetime.now(timezone.utc).isoformat()
        return False

    def _trip_process_for_liveness_failure(
        self,
        *,
        reason: str,
        exit_fn=os._exit,
    ) -> None:
        """Exit non-zero so systemd restarts the whole daemon cleanly."""

        if getattr(self, "_liveness_exit_requested", False):
            return
        self._liveness_exit_requested = True
        logger.critical("Cognition liveness trip: reason=%s", reason)
        stop_error = []

        def _graceful_stop():
            try:
                self.stop()
            except Exception as exc:
                stop_error.append(type(exc).__name__)

        stop_thread = threading.Thread(
            target=_graceful_stop,
            daemon=True,
            name="cognition-liveness-stop",
        )
        stop_thread.start()
        stop_thread.join(timeout=15.0)
        if stop_error:
            logger.error("Liveness graceful stop failed: %s", stop_error[0])
        if stop_thread.is_alive():
            logger.error("Liveness graceful stop timed out; exiting for systemd restart")
        logging.shutdown()
        exit_fn(75)

    def _start_cognition_liveness_sentinel(self) -> None:
        """Watch reasoning-loop freshness from outside the reasoning thread."""

        if getattr(self, "_liveness_sentinel_thread", None) is not None:
            return

        def _sentinel():
            while bool(getattr(self, "running", False)) and not bool(
                getattr(self, "_liveness_exit_requested", False)
            ):
                threshold = self._cycle_liveness_stale_after_seconds()
                time.sleep(max(5.0, min(30.0, threshold / 3.0)))
                heartbeat = self._cycle_heartbeat_health()
                if self._health_status_from_reasoning_loop(heartbeat) == "stalled":
                    self._capture_fd_forensics_if_relevant(None)
                    self._trip_process_for_liveness_failure(
                        reason="reasoning_loop_stalled",
                    )
                    return

        self._liveness_sentinel_thread = threading.Thread(
            target=_sentinel,
            daemon=True,
            name="cognition-liveness",
        )
        self._liveness_sentinel_thread.start()

    def _run_reasoning_loop_supervised(self) -> None:
        """Run the existing loop body under an outside exception boundary."""

        while bool(getattr(self, "running", False)):
            try:
                self._loop()
                return
            except Exception as exc:
                if self._handle_cycle_exception(exc):
                    return
                if not bool(getattr(self, "running", False)):
                    return

    def _watchdog_health(self, *, operator: bool = False) -> dict:
        """Content-free metacognitive watchdog health projection."""
        state = {
            "watchdog_state": self.watchdog_state,
            "operator_resume_required": bool(self._watchdog_operator_resume_required),
        }
        if self._watchdog_halted_at:
            state["halted_at"] = self._watchdog_halted_at
        if operator and self._watchdog_halt_summary:
            state["halt_summary"] = dict(self._watchdog_halt_summary)
        return state

    def _enter_watchdog_safe_standby(self, halt) -> None:
        """Stop autonomous cycles after a watchdog halt without ordinary shutdown."""
        self.watchdog_state = "safe_standby"
        self._watchdog_halted_at = datetime.now(timezone.utc).isoformat()
        self._watchdog_operator_resume_required = True
        summary = halt.health_summary() if hasattr(halt, "health_summary") else {}
        self._watchdog_halt_summary = {
            "halt_signal_id": summary.get("halt_signal_id", ""),
            "halt_detector": summary.get("detector", getattr(halt, "detector", "")),
            "halt_reason_code": summary.get("reason_code", getattr(halt, "reason_code", "")),
            "window_ref": summary.get("window_ref", ""),
            "threshold_ref": summary.get("threshold_ref", ""),
            "observed_metrics": dict(summary.get("observed_metrics") or {}),
        }
        self.running = False
        logger.error(
            "Metacognitive watchdog safe_standby: detector=%s reason=%s signal=%s",
            self._watchdog_halt_summary.get("halt_detector"),
            self._watchdog_halt_summary.get("halt_reason_code"),
            self._watchdog_halt_summary.get("halt_signal_id"),
        )

    def _presence_unavailable(self, error: str, *, token=None) -> CameraPresenceState:
        if token is None:
            self._camera_presence_state = self._camera_presence_state.unavailable(error_class=error)
        else:
            self._camera_presence_state = self._camera_presence_state.commit_unavailable(
                error,
                token=token,
                shutdown_started=self._shutdown_started.is_set(),
            )
        return self._camera_presence_state

    @staticmethod
    def _presence_probe_env() -> dict[str, str]:
        """Build a secret-free, headless env for native camera child probes."""
        env = sanitize_env()
        for name in ("DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY"):
            env.pop(name, None)
        return env

    def _run_presence_probe(self, *, timeout_s: float):
        """Run native camera detection in a killable child process."""
        cmd = [sys.executable, "-m", "skills.presence_perception", "--json-once"]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=self._presence_probe_env(),
            )
        except subprocess.TimeoutExpired:
            return SimpleNamespace(
                success=False,
                presence_detected=False,
                confidence=0.0,
                error="detector_timeout",
            )
        except Exception:
            return SimpleNamespace(
                success=False,
                presence_detected=False,
                confidence=0.0,
                error="detector_error",
            )

        if proc.returncode != 0:
            return SimpleNamespace(
                success=False,
                presence_detected=False,
                confidence=0.0,
                error="detector_error",
            )
        try:
            payload = json.loads(proc.stdout.strip())
        except Exception:
            return SimpleNamespace(
                success=False,
                presence_detected=False,
                confidence=0.0,
                error="detector_error",
            )
        return SimpleNamespace(
            success=bool(payload.get("success")),
            presence_detected=bool(payload.get("presence_detected")),
            confidence=float(payload.get("confidence") or 0.0),
            error=str(payload.get("error") or ""),
        )

    def _observe_presence_bounded(self) -> CameraPresenceState:
        """Run camera presence detection without blocking the reasoning loop."""
        self._camera_presence_state = self._camera_presence_state.with_freshness()
        if self._shutdown_started.is_set() or not self._camera_presence_state.enabled:
            return self._camera_presence_state

        timeout_s = 5.0
        if self._presence_worker.in_flight():
            return self._presence_unavailable("presence observation still running")

        token = self._camera_presence_state.make_observation_token()
        result_holder: dict[str, object | None] = {"value": None}

        def _call() -> None:
            child_timeout_s = max(0.5, timeout_s - 0.5)
            result_holder["value"] = self._run_presence_probe(timeout_s=child_timeout_s)

        if not self._presence_worker.submit(_call):
            return self._presence_unavailable(
                "presence observation worker unavailable", token=token
            )

        if not self._presence_worker.join(timeout=timeout_s):
            msg = f"presence observation timed out after {timeout_s:.1f}s"
            logger.warning(msg)
            return self._presence_unavailable(msg, token=token)

        snap = result_holder.get("value")
        if snap is not None and getattr(snap, "success", False):
            confidence = float(getattr(snap, "confidence", 0.0) or 0.0)
            if confidence >= 0.8:
                bucket = "high"
            elif confidence >= 0.6:
                bucket = "medium"
            elif confidence > 0:
                bucket = "low"
            else:
                bucket = "none"
            reading = CameraPresenceReading(
                presence_state="present" if getattr(snap, "presence_detected", False) else "absent",
                confidence_bucket=bucket,
                observed_at=datetime.now(timezone.utc),
            )
            self._camera_presence_state = self._camera_presence_state.commit_observation(
                reading,
                token=token,
                shutdown_started=self._shutdown_started.is_set(),
            )
            return self._camera_presence_state
        if snap is not None:
            error = getattr(snap, "error", None) or "sensor_unavailable"
            return self._presence_unavailable(str(error), token=token)
        return self._presence_unavailable("presence observation returned no snapshot", token=token)

    def _watch_soul(self):
        """Watch soul.md for changes and hot-reload."""
        while self.running:
            try:
                # 2026-04-23 Commit 3: hot-reload via the layered loader
                # so changes to EITHER soul.base.md OR soul.local.md
                # are picked up, not just changes to soul.md. The loader
                # caches internally on mtime of both source files, so
                # calling it every second is cheap. It also rewrites
                # the legacy soul.md mirror on content change — that's
                # what the direct-read fallback below relies on.
                try:
                    from core.evolution.soul_loader import current_soul as _cur_soul

                    raw = _cur_soul().strip()
                except Exception as _layer_exc:
                    logger.debug(
                        "soul_loader failed in hot-reload, falling back to direct read: %s",
                        _layer_exc,
                    )
                    raw = SOUL_PATH.read_text().strip()
                # Re-scan on every hot-reload: an attacker who overwrites
                # soul.md while the daemon is running is the threat model
                # here. Startup scan alone is insufficient.
                from core.context_safety import scan as _scan
                from core.soul_invariants import check as _inv_check

                scanned = _scan(raw, source="soul.md (hot-reload)")
                if scanned.blocked:
                    logger.error(
                        "soul.md hot-reload BLOCKED by context_safety: %s. "
                        "Retaining previous system prompt.",
                        scanned.findings,
                    )
                    time.sleep(10)
                    continue
                inv = _inv_check(raw)
                if not inv.ok:
                    logger.error(
                        "soul.md hot-reload BLOCKED by soul_invariants: %s. "
                        "Retaining previous system prompt.",
                        inv.summary(),
                    )
                    time.sleep(10)
                    continue
                content = raw
                current_hash = hashlib.md5(content.encode()).hexdigest()
                if self._soul_hash and current_hash != self._soul_hash:
                    old_hash = self._soul_hash
                    self._soul_hash = current_hash
                    self.system_prompt = content
                    logger.info("soul.md changed — hot reloaded (%d chars)", len(content))
                    self.memory.store_core(
                        f"Soul updated at {time.strftime('%Y-%m-%d %H:%M')}. "
                        f"Maez rewrote its own foundation.",
                        source="soul_evolution",
                        provenance_source="introspection",
                        trust_tier="lived",
                    )
                    # A-core #3 Step 6: log the soul change as a
                    # direct_edit event so it enters Maez's perception
                    # stream via the daemon reader. If a builder-mode
                    # session is active, bind to that session. Otherwise
                    # bind to the sentinel AUTONOMOUS_SESSION_ID so
                    # dream-state-initiated soul writes are still
                    # visible to Maez's immune memory. See
                    # core/builder_mode_capture.py for the sentinel.
                    try:
                        from core.builder_mode_capture import (
                            capture_git_diff_summary,
                            read_active_session_id,
                            AUTONOMOUS_SESSION_ID,
                        )

                        repo_root = Path(__file__).resolve().parent.parent
                        summary, _h, _p = capture_git_diff_summary(
                            repo_root, watched_paths=["config/soul.md"]
                        )
                        # If git diff is empty for any reason (soul.md
                        # change hasn't been reflected in git yet, or
                        # git unavailable), fall back to a hash-delta
                        # summary so the event still carries shape.
                        if not summary:
                            summary = f"  config/soul.md (md5 {old_hash[:8]} -> {current_hash[:8]})"
                        state_file = Path(__file__).resolve().parent / "builder_mode_current.txt"
                        active_sid = read_active_session_id(state_file)
                        if active_sid:
                            session_id = active_sid
                            change_reason = "soul.md changed during active builder session"
                        else:
                            session_id = AUTONOMOUS_SESSION_ID
                            change_reason = (
                                "soul.md changed (autonomous — no active builder session)"
                            )
                        self._builder_audit_log.log_direct_edit(
                            session_id=session_id,
                            paths=["config/soul.md"],
                            diff_summary=summary,
                            commit_hash=None,
                            reason=change_reason,
                        )
                        logger.info(
                            "Builder soul-change event logged (session=%s)",
                            session_id if session_id == AUTONOMOUS_SESSION_ID else session_id[:12],
                        )
                    except Exception as e:
                        logger.debug("soul-change direct_edit logging failed: %s", e)
            except Exception:
                pass
            time.sleep(10)

    UNCERTAINTY_SIGNALS = [
        "i'm not sure",
        "i don't know",
        "unclear to me",
        "i can't confirm",
        "i wonder",
        "i should check",
        "not certain",
        "i'll look into",
        "need to verify",
    ]

    def _should_search(self, thought: str) -> str:
        """Returns search query ONLY if thought contains explicit uncertainty. Strict."""
        thought_lower = thought.lower()
        if not any(sig in thought_lower for sig in self.UNCERTAINTY_SIGNALS):
            return ""
        # Extract topic after the uncertainty signal
        for sig in self.UNCERTAINTY_SIGNALS:
            if sig in thought_lower:
                idx = thought_lower.index(sig)
                topic = thought[idx + len(sig) : idx + 100].strip(" .,;:").split(".")[0]
                if len(topic) > 5:
                    return topic[:80]
        return ""

    @staticmethod
    def _telegram_notice_content(text: str, *, source_ref: str) -> ProvenancedText:
        if source_ref == "daemon:proactive_opinion":
            return ProvenancedText.maez_authored_owner_third_party_transport(
                text,
                source_ref=source_ref,
            )
        if source_ref == "daemon:morning_briefing" and text.startswith("Morning briefing:\n\n"):
            prefix = "Morning briefing:\n\n"
            return ProvenancedText.system_bounded_query(
                prefix,
                source_ref=f"{source_ref}:label",
            ) + ProvenancedText.maez_authored_owner_third_party_transport(
                text[len(prefix) :],
                source_ref=f"{source_ref}:audited_briefing",
            )
        if source_ref == "daemon:curiosity_checkin":
            spans = []
            for line in text.splitlines(keepends=True):
                if line.startswith("  "):
                    spans.extend(
                        ProvenancedText.third_party_private_context(
                            line,
                            source_ref=f"{source_ref}:public_user_profile",
                        ).spans
                    )
                else:
                    spans.extend(
                        ProvenancedText.system_bounded_query(
                            line,
                            source_ref=f"{source_ref}:static",
                        ).spans
                    )
            return ProvenancedText.from_spans(spans)
        if source_ref == "daemon:followup_queue" and "Result: " in text:
            before, result = text.split("Result: ", 1)
            return ProvenancedText.system_bounded_query(
                before + "Result: ",
                source_ref=f"{source_ref}:label",
            ) + ProvenancedText.tool_result_public(
                result,
                source_ref=f"{source_ref}:action_result",
            )
        if source_ref == "daemon:followup_queue" and "\n\n" in text:
            before, detail = text.split("\n\n", 1)
            return ProvenancedText.system_bounded_query(
                before + "\n\n",
                source_ref=f"{source_ref}:status",
            ) + ProvenancedText.tool_result_public(
                detail,
                source_ref=f"{source_ref}:action_detail",
            )
        return ProvenancedText.system_bounded_query(text, source_ref=source_ref)

    def _send_telegram_notice(self, text: str | ProvenancedText, *, source_ref: str) -> None:
        telegram = getattr(self, "telegram", None)
        if not telegram:
            return
        send_envelope = getattr(telegram, "send_envelope", None)
        if not callable(send_envelope):
            return
        content = (
            text
            if isinstance(text, ProvenancedText)
            else self._telegram_notice_content(str(text), source_ref=source_ref)
        )
        envelope = owner_multispan_envelope(
            bot_route="voice_owner_private",
            chat_id="",
            content=content,
            source_ref=source_ref,
        )
        send_envelope(envelope)

    def _curiosity_checkin(self):
        """Ask the owner about new people who talked to Maez today."""
        try:
            from skills.user_accounts import UserAccounts

            accts = UserAccounts()
            unconfirmed = accts.get_unconfirmed_users(since_hours=24)
            if not unconfirmed:
                return
            lines = ["I met some new people today. Can you tell me who they are?"]
            for user in unconfirmed:
                lines.append(f"  {user['display_name']} — {user.get('notes') or 'no details yet'}")
            lines.append("\nReply with: /trust [username] [relationship] [tier 0-3]")
            lines.append("Example: /trust [person] partner 3")
            self._send_telegram_notice(
                "\n".join(lines),
                source_ref="daemon:curiosity_checkin",
            )
            logger.info("[SOCIAL] Curiosity check-in sent for %d users", len(unconfirmed))
        except Exception as e:
            logger.error("Curiosity check-in error: %s", e)

    def _check_proactive_opinion(self):
        """Every 50 cycles, check if there's something worth telling the owner unprompted.

        2026-04-23 memory-integrity contract (Commit 1):
          - Input is a memory WINDOW, not live signals. The grounding
            manifest marks screen/calendar as "stale" (drawn
            from memory) rather than "present" (live this turn) so the
            audit applies the right invariant.
          - The sent text is audited before `telegram.send_message()`.
          - The audited text is stored with distinct provenance
            (`type="proactive_opinion"`) so future recall/reranking
            can distinguish "I said this unprompted" from "I replied
            to a direct message."
        """
        try:
            window_size = 20
            results = self.memory.raw.get(limit=window_size, include=["documents"])
            thoughts = results.get("documents", [])
            if len(thoughts) < 10:
                return
            thoughts_text = "\n".join(thoughts[-window_size:])
            prompt = (
                f"You are reviewing your last 20 observations about the owner and his system.\n\n"
                f"{thoughts_text}\n\n"
                f"Is there something genuinely worth telling the owner right now unprompted? "
                f"Not a system alert. Not a calendar reminder. An actual insight or concern "
                f"that a good partner would mention. Something that requires real judgment.\n\n"
                f"If yes — write exactly what you would send. 1-2 sentences. Direct. No preamble.\n"
                f"If no — respond with exactly: NOTHING"
            )
            # Aggregated-window manifest. The input to the proactive
            # LLM call was RAW MEMORY, not live perception — so the
            # audit should know screen/calendar are derived
            # from the reviewed window, not observable right now.
            proactive_signals_absent = [
                "live screen observation (input was memory window)",
                "live calendar (input was memory window)",
            ]
            proactive_signals_present = [
                f"memory window of last {window_size} raw entries",
            ]
            _evidence_envelope = self._build_audit_evidence_envelope(
                surface="daemon_proactive",
                signals_present=proactive_signals_present,
                signals_absent=proactive_signals_absent,
            )
            try:
                from core.cognition.envelope_builder import (
                    render_envelope_for_prompt as _render_envelope,
                )

                _envelope_block = _render_envelope(_evidence_envelope)
            except Exception as _env_exc:
                logger.warning(
                    "evidence_envelope render failed for daemon_proactive "
                    "(continuing without prompt block): %s",
                    _env_exc,
                )
                _evidence_envelope = None
                _envelope_block = ""
            if _envelope_block:
                prompt += "\n\n" + _envelope_block

            # Session 11r: via llm_client (was missed in 11p batch)
            from core import llm_client as _llm_client
            from core.routing.brain_gateway import with_purpose as _brain_purpose

            with _brain_purpose("daemon_cycle_rewrite"):
                response = _llm_client.chat(
                    model=MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    think=False,
                    options={"temperature": 0.8, "num_predict": 100},
                )
            result = (response.message.content or "").strip()
            if not (
                result
                and result != "NOTHING"
                and len(result) > 10
                and "NOTHING" not in result.upper()
            ):
                return

            # Temporal grounding: strip stale weekday phrases from
            # model output before sending to the owner.
            result = self._strip_temporal_phrases(result)

            try:
                from core.safety.audited_output import audit_assistant_text

                result = audit_assistant_text(
                    result,
                    surface="daemon_proactive",
                    signals_present=proactive_signals_present,
                    signals_absent=proactive_signals_absent,
                    evidence_envelope=_evidence_envelope,
                )
            except Exception as _aud_exc:
                logger.warning("proactive audit fail-open: %s", _aud_exc)

            # Send the audited text, not the raw generation.
            self._send_telegram_notice(
                result,
                source_ref="daemon:proactive_opinion",
            )
            logger.info("[OPINION] Unprompted: %s", result[:80])

            # Provenance-tagged storage so later recall can distinguish
            # owner-initiated exchanges from Maez-initiated messages.
            # Note: lives in the same `raw` collection as cycle thoughts
            # + telegram exchanges; the `type` metadata is what future
            # filters/rerankers key on. Step 5x.B: routed through the
            # public ``store()`` method (was a direct ``raw.add()``
            # bypass) so the provenance schema applies; tagged
            # introspection/lived because this is Maez's own
            # audited self-emitted text.
            try:
                self.memory.store(
                    result,
                    cycle=self.cycle_count,
                    metadata={
                        "type": "proactive_opinion",
                        "surface": "daemon_proactive",
                        "source_window_count": window_size,
                        "sent_to_owner": True,
                    },
                    provenance_source="introspection",
                    trust_tier="lived",
                )
            except Exception as _store_exc:
                logger.debug("proactive provenance store failed: %s", _store_exc)
        except Exception as e:
            logger.error("Proactive opinion error: %s", e)

    def _get_circadian_context(self) -> str:
        hour = datetime.now().astimezone().hour
        if 5 <= hour < 9:
            phase, energy, tone = "early morning", "waking up", "gentle and brief"
        elif 9 <= hour < 12:
            phase, energy, tone = "morning", "high focus", "direct and sharp"
        elif 12 <= hour < 14:
            phase, energy, tone = "midday", "post-lunch dip likely", "light and practical"
        elif 14 <= hour < 18:
            phase, energy, tone = "afternoon", "sustained work", "direct and efficient"
        elif 18 <= hour < 21:
            phase, energy, tone = "evening", "winding down", "reflective and calm"
        elif 21 <= hour < 24:
            phase, energy, tone = "late evening", "tired", "brief and warm"
        else:
            phase, energy, tone = "night", "should be sleeping", "very brief, check if okay"
        return (
            f"[CIRCADIAN]\n"
            f"  Time: {phase} ({hour:02d}:00)\n"
            f"  Expected energy: {energy}\n"
            f"  Suggested tone: {tone}"
        )

    @staticmethod
    def _strip_temporal_phrases(text: str) -> str:
        """Remove or replace stale weekday/daypart phrases from model-generated text.

        The reasoning model often starts thoughts with "it is Monday evening..."
        because the prompt includes the current weekday. When that thought is later
        recalled (e.g. in the >2h welcome-back greeting), the stale weekday leaks
        into the greeting. This helper strips such phrases so recalled text never
        injects a weekday that doesn't match the actual current day.

        Strategy: replace "it is <weekday> <daypart>" and similar patterns with
        relative phrasing or strip them entirely. Does NOT touch weekday names that
        appear as data (e.g. "the meeting is on Monday") — only the leading
        "it is/was <day>" assertion pattern that the model uses for temporal
        grounding.

        Returns the sanitized text (may be shorter).
        """
        import re

        days = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
        parts = r"(?:morning|afternoon|evening|night|late evening|early morning|midday)"

        # "it is Monday evening" / "it's Tuesday morning" / "it was Wednesday night"
        text = re.sub(
            rf"\b[Ii]t(?:'s|\s+is|\s+was)\s+{days}\b(?:\s+{parts})?\s*[.,;—–-]?\s*",
            "",
            text,
        )
        # "on Monday evening," at the start of a temporal phrase — NOT "on Fridays"
        text = re.sub(
            rf"\b[Oo]n\s+{days}\b(?:\s+{parts})\s*[.,;—–-]?\s*",
            "",
            text,
        )
        # "this Monday" / "today is Wednesday" — NOT "last Monday's"
        text = re.sub(
            rf"\b(?:[Tt]his|[Tt]oday\s+is)\s+{days}\b\s*[.,;—–-]?\s*",
            "",
            text,
        )
        # Clean up leading whitespace / double spaces left behind
        text = re.sub(r"\s{2,}", " ", text).strip()
        # If the stripping left us with a lowercase first char, capitalize
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        return text

    def _write_pid(self):
        """Write PID file for process management.

        T2.1 (2026-05-04 audit) — if a PID file already exists,
        liveness-check the recorded PID via ``os.kill(pid, 0)``
        before overwriting. Signal 0 raises ``ProcessLookupError``
        (or ``OSError``) if the process is gone. Without this, a
        stale PID file from a SIGKILLed parent (no atexit cleanup)
        made the daemon look running when it wasn't, blocking the
        next start. We log a WARNING for the dead PID and overwrite.
        We do NOT auto-overwrite a live PID — that would be hostile
        to a legitimate second daemon — but we still proceed and
        log loud at WARNING so the operator sees the collision.
        """
        try:
            if PID_FILE.exists():
                raw = PID_FILE.read_text().strip()
                try:
                    prior_pid = int(raw)
                except ValueError:
                    logger.warning(
                        "PID file %s held non-integer %r; overwriting",
                        PID_FILE,
                        raw,
                    )
                    prior_pid = None
                if prior_pid is not None and prior_pid != os.getpid():
                    try:
                        os.kill(prior_pid, 0)
                    except (ProcessLookupError, OSError) as e:
                        logger.warning(
                            "Stale/dead PID %d in %s (liveness probe: "
                            "%s); overwriting with current PID %d",
                            prior_pid,
                            PID_FILE,
                            e,
                            os.getpid(),
                        )
                    else:
                        logger.warning(
                            "PID %d in %s appears LIVE; overwriting "
                            "anyway with current PID %d — investigate "
                            "if a second daemon is running",
                            prior_pid,
                            PID_FILE,
                            os.getpid(),
                        )
        except OSError as e:
            logger.warning(
                "PID file %s read failed (%s); overwriting",
                PID_FILE,
                e,
            )
        PID_FILE.write_text(str(os.getpid()))
        logger.info("PID %d written to %s", os.getpid(), PID_FILE)

    def _remove_pid(self):
        """Clean up PID file on exit."""
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass

    def _check_ollama(self) -> bool:
        """Verify LLM backend is reachable. Routes by MAEZ_LLM_BACKEND.

        Retries on transient failure. Observed 2026-04-22/23: a bare
        single-shot probe caused Maez to abort-on-boot when llama-server
        was briefly returning 503 (mid-load, mid-request backpressure,
        or a VRAM pressure hiccup). Four crashes in 24h, each self-
        healing on the systemd restart 10s later. A brief retry loop
        (total ~14s window) absorbs those blips without further action.
        """
        backend = os.environ.get("MAEZ_LLM_BACKEND", "ollama").lower()
        total_attempts = 4
        delays = (0, 2, 4, 8)  # cumulative ~14s of patience
        last_err: str = ""
        for attempt, delay in enumerate(delays[:total_attempts]):
            if delay:
                time.sleep(delay)
            if backend == "llamacpp":
                try:
                    import urllib.request

                    base = os.environ.get("MAEZ_LLAMACPP_URL", "http://127.0.0.1:8080/v1")
                    req = urllib.request.Request(f"{base}/models")
                    with urllib.request.urlopen(req, timeout=5) as r:
                        if r.status == 200:
                            if attempt:
                                logger.info(
                                    "llama-server reachable after attempt %d/%d",
                                    attempt + 1,
                                    total_attempts,
                                )
                            return True
                        last_err = f"HTTP {r.status}"
                except Exception as e:
                    last_err = str(e)
                if attempt < total_attempts - 1:
                    logger.info(
                        "llama-server not yet ready (attempt %d/%d: %s); retrying after backoff",
                        attempt + 1,
                        total_attempts,
                        last_err,
                    )
                continue
            # Ollama branch — single-shot is still fine here; Ollama
            # rarely 503s mid-request the way llama-server can.
            try:
                models = ollama.list()
                available = [m.model for m in models.models]
                if any(MODEL in name for name in available):
                    return True
                logger.warning("Model %s not found. Available: %s", MODEL, available)
                return False
            except Exception as e:
                logger.error("Ollama connection failed: %s", e)
                return False
        logger.error(
            "llama-server connection failed after %d attempts: %s", total_attempts, last_err
        )
        return False

    def _get_local_time(self) -> datetime:
        """Get current local time."""
        return datetime.now().astimezone()

    def _build_audit_evidence_envelope(
        self,
        *,
        surface: str,
        signals_present: list[str],
        signals_absent: list[str],
        turn_id: str | None = None,
        tool_results: list[dict] | None = None,
    ) -> dict | None:
        """Best-effort envelope builder for daemon-owned audit paths."""
        try:
            from core.cognition.envelope_builder import build_envelope

            return build_envelope(
                ledger_db_path=str(LEDGER_DB_PATH),
                signals_present=signals_present,
                signals_absent=signals_absent,
                tool_results=tool_results or [],
                turn_id=turn_id,
            )
        except Exception as exc:
            logger.warning(
                "evidence_envelope build failed for %s (continuing without envelope): %s",
                surface,
                exc,
            )
            return None

    # ------------------------------------------------------------------ #
    #  S1b private-thoughts minimal wiring                                #
    # ------------------------------------------------------------------ #

    def _s1b_note_residue_event(self, event_kind: str) -> None:
        """Collect content-free reasoning-residue events for end-cycle write."""
        if not hasattr(self, "_s1b_residue_events"):
            self._s1b_residue_events = []
        self._s1b_residue_events.append(str(event_kind))

    def _s1b_flush_residue_events(self) -> int | None:
        """Write at most one S1b private signal for the current cycle."""
        events = list(getattr(self, "_s1b_residue_events", []) or [])
        self._s1b_residue_events = []
        if not events:
            return None
        producer = getattr(self, "_s1b_producer", None)
        if producer is None:
            return None
        try:
            return producer.emit_cycle_residue(events, cycle_id=self.cycle_count)
        except Exception as exc:
            logger.warning("S1b producer write skipped: %s", exc)
            return None

    def _s1b_optional_presentation_payload(self, canonical_text: str) -> dict | None:
        """Return a separate dampened optional-presentation payload, if enabled."""
        consumer = getattr(self, "_s1b_consumer", None)
        if consumer is None:
            return None
        try:
            from core.infra.private_thoughts_s1b import build_cycle_optional_presentation

            decision = consumer.pacing_decision()
            payload = build_cycle_optional_presentation(
                cycle=self.cycle_count,
                canonical_text=canonical_text,
                decision=decision,
            )
            recorder = getattr(consumer, "record_optional_presentation", None)
            should_record = getattr(
                consumer, "should_record_optional_presentation_opportunity", None
            )
            if callable(recorder) and callable(should_record) and should_record():
                recorder(dampened=payload is not None)
            return payload
        except Exception as exc:
            logger.warning("S1b consumer returned neutral after error: %s", exc)
            return None

    def _lean_idle_self_card_text(self) -> str:
        try:
            from core.routing.self_card import assemble_self_card_from_paths
            from core.routing.self_card_time import build_self_card_time_line

            time_candidate = None
            time_applied = False
            if _env_flag("MAEZ_SELF_CARD_TIME_SHADOW") or _env_flag(
                "MAEZ_SELF_CARD_TIME_ENABLED"
            ):
                time_candidate = build_self_card_time_line()
                time_applied = _env_flag("MAEZ_SELF_CARD_TIME_ENABLED")
            return assemble_self_card_from_paths(
                time_line_candidate=time_candidate,
                time_line_applied=time_applied,
            ).text
        except Exception:
            return "SELF CARD (unavailable)"

    def _lean_idle_private_signal_summary(self) -> dict:
        try:
            store = getattr(self, "private_thoughts", None)
            if store is None:
                return {}
            derived = store.derived_signals(limit=10)
            classes = derived.get("signal_classes", {}) if isinstance(derived, dict) else {}
            summary = {}
            for name, value in classes.items():
                if isinstance(value, dict):
                    summary[str(name)] = int(value.get("count", 0) or 0)
            return summary
        except Exception:
            return {}

    def _lean_idle_time_facts(self) -> dict:
        try:
            rctx = self._time_sense_handle().rhythm_context()
            if not isinstance(rctx, dict):
                return {}
            mapping = {
                "owner_contact_gap_s": rctx.get("rhythm_current_gap_s"),
                "recent_usual_gap_s": rctx.get("rhythm_recent_gap_median_s"),
                "all_time_usual_gap_s": rctx.get("rhythm_all_time_gap_median_s"),
                "gap_percentile_all_time": rctx.get(
                    "rhythm_current_gap_percentile_all_time"
                ),
            }
            return {key: value for key, value in mapping.items() if value is not None}
        except Exception:
            return {}

    def _lean_idle_body_state(self) -> dict:
        state: dict = {}
        try:
            op = self._operator_health()
            if isinstance(op, dict):
                overall = op.get("mode")
                if isinstance(overall, str) and overall:
                    state["daemon_overall"] = overall
                backup = op.get("backup_freshness_class")
                if isinstance(backup, str) and backup:
                    state["backup_freshness"] = backup
        except Exception:
            pass
        try:
            wd = self._watchdog_health()
            watchdog = wd.get("watchdog_state") if isinstance(wd, dict) else None
            if isinstance(watchdog, str) and watchdog:
                state["watchdog"] = watchdog
        except Exception:
            pass
        return state

    def _lean_idle_open_loops(self) -> dict:
        try:
            count = 0
            classes: list[str] = []
            saw_seam = False
            wants = getattr(self, "wants", None)
            if wants is not None and hasattr(wants, "active_wants"):
                saw_seam = True
                active = list(wants.active_wants(limit=50) or [])
                if active:
                    count += len(active)
                    classes.append("wants")
            try:
                cards = self._want_pursuit_card_store()
                if cards is not None and hasattr(cards, "list_open_by_action"):
                    saw_seam = True
                    from core.evolution.want_pursuit_bridge import (
                        TERMINAL_PROPOSAL_ACTION,
                    )

                    pending = list(
                        cards.list_open_by_action(TERMINAL_PROPOSAL_ACTION) or []
                    )
                    if pending:
                        count += len(pending)
                        classes.append("proposals")
            except Exception:
                pass
            if not saw_seam:
                return {}
            return {"open_loop_count": count, "open_loop_classes": classes}
        except Exception:
            return {}

    def _lean_idle_recent_private_thoughts(self) -> tuple:
        try:
            store = getattr(self, "private_thoughts", None)
            if store is None:
                return ()
            from core.cognition.lean_idle_heartbeat import (
                HEARTBEAT_VERSION,
                select_private_reader_thoughts,
            )

            return select_private_reader_thoughts(
                store.recent_by_source(HEARTBEAT_VERSION, limit=2)
            )
        except Exception:
            return ()

    def _maybe_run_salience_broker(self, window: dict) -> dict | None:
        if not _salience_broker_shadow_enabled():
            return None
        try:
            from core.cognition.salience_broker import (
                broker_receipt,
                fact_signatures,
                propose_changes,
            )

            baseline = getattr(self, "_salience_broker_baseline", None)
            current = fact_signatures(window)
            proposals = propose_changes(current, baseline)
            receipt = broker_receipt(proposals, cold_start=baseline is None)
            self._salience_broker_baseline = current
        except Exception as exc:
            receipt = {
                "schema_version": "salience_broker.v0",
                "strategy": "changed_since_last",
                "cold_start": getattr(self, "_salience_broker_baseline", None) is None,
                "proposal_count": 0,
                "proposals": [],
                "skip_reason": "error",
                "error_class": exc.__class__.__name__,
            }
        logger.info("salience_broker receipt=%s", json.dumps(receipt, sort_keys=True))
        return receipt

    def _salience_ledger_get(self):
        ledger = getattr(self, "_salience_ledger", None)
        if ledger is not None:
            return ledger
        from core.cognition.salience_ledger import (
            SalienceLedger,
            salience_ledger_db_path,
        )

        ledger = SalienceLedger(salience_ledger_db_path())
        self._salience_ledger = ledger
        return ledger

    def _fresh_moment_receipts_get(self):
        store = getattr(self, "_fresh_moment_receipts", None)
        if store is not None:
            return store
        from core.cognition.fresh_moment_receipts import (
            FreshMomentReceipts,
            fresh_moment_receipts_db_path,
        )

        store = FreshMomentReceipts(fresh_moment_receipts_db_path())
        self._fresh_moment_receipts = store
        return store

    def _maybe_record_fresh_moment_receipt(self, result) -> int | None:
        if not _fresh_moment_receipts_shadow_enabled():
            return None
        receipt = getattr(result, "receipt", {}) or {}
        if not bool(getattr(result, "stored", receipt.get("stored", False))):
            return None
        thought_id = getattr(result, "thought_id", None)
        if thought_id is None:
            return None
        content_sha256 = str(receipt.get("output_sha256") or "").strip()
        if not content_sha256:
            return None
        try:
            from core.cognition.fresh_moment_receipts import FRESH_MOMENT_BOND_ID
            from core.cognition.lean_idle_heartbeat import HEARTBEAT_VERSION

            receipt_id = self._fresh_moment_receipts_get().record_private_thought_landed(
                thought_id=int(thought_id),
                source=HEARTBEAT_VERSION,
                bond_id=FRESH_MOMENT_BOND_ID,
                content_sha256=content_sha256,
                content_len=int(receipt.get("note_chars") or 0),
            )
            logger.info(
                "fresh_moment_receipt receipt=%s",
                json.dumps(
                    {
                        "schema_version": "fresh_moment_receipts.v0",
                        "moment_kind": "private_thought_landed",
                        "stored": True,
                        "receipt_id": int(receipt_id),
                        "thought_id": int(thought_id),
                        "source": HEARTBEAT_VERSION,
                        "bond_id": FRESH_MOMENT_BOND_ID,
                    },
                    sort_keys=True,
                ),
            )
            return int(receipt_id)
        except Exception as exc:
            logger.info(
                "fresh_moment_receipt receipt=%s",
                json.dumps(
                    {
                        "schema_version": "fresh_moment_receipts.v0",
                        "moment_kind": "private_thought_landed",
                        "stored": False,
                        "skip_reason": "error",
                        "error_class": exc.__class__.__name__,
                    },
                    sort_keys=True,
                ),
            )
            return None

    def _record_salience_outcomes(
        self,
        proposals: list,
        heartbeat_outcome: dict,
        *,
        strategy: str,
        pulse_signature: str,
        cold_start: bool = False,
    ) -> str | None:
        if not _salience_broker_shadow_enabled():
            return None
        from core.cognition.salience_ledger import (
            assign_arm,
            derive_outcome,
            make_proposal_hash,
            make_pulse_id,
            new_run_id,
        )

        if getattr(self, "_salience_run_id", None) is None:
            self._salience_run_id = new_run_id(
                now_ms=int(time.time() * 1000),
                pid=os.getpid(),
            )
        self._salience_pulse_seq = int(getattr(self, "_salience_pulse_seq", 0)) + 1
        pulse_id = make_pulse_id(self._salience_run_id, self._salience_pulse_seq)
        arm, rows = assign_arm(
            list(proposals or []),
            pulse_signature,
            cold_start=bool(cold_start),
        )
        current = {
            "pulse_id": pulse_id,
            "strategy": str(strategy or "changed_since_last"),
            "arm": arm,
            "rows": [dict(row) for row in rows],
            "outcome": dict(heartbeat_outcome or {}),
        }
        prior = getattr(self, "_salience_pending", None)
        if prior is not None:
            try:
                outcome = derive_outcome([prior.get("outcome", {}), current["outcome"]])
                ledger = self._salience_ledger_get()
                prior_strategy = str(prior.get("strategy") or "changed_since_last")
                prior_arm = str(prior.get("arm") or "proposed")
                for row in prior.get("rows", []):
                    fact_key = str(row.get("fact_key", ""))
                    change_kind = str(row.get("change_kind", ""))
                    proposal_hash = make_proposal_hash(
                        pulse_id=prior["pulse_id"],
                        strategy=prior_strategy,
                        arm=prior_arm,
                        fact_key=fact_key,
                        change_kind=change_kind,
                    )
                    ledger.record(
                        pulse_id=prior["pulse_id"],
                        strategy=prior_strategy,
                        arm=prior_arm,
                        fact_key=fact_key,
                        change_kind=change_kind,
                        proposal_hash=proposal_hash,
                        outcome=outcome,
                    )
            except Exception as exc:
                logger.info(
                    "salience_ledger receipt=%s",
                    json.dumps(
                        {
                            "schema_version": "salience_ledger.v0",
                            "skip_reason": "error",
                            "error_class": exc.__class__.__name__,
                            "arm": str(prior.get("arm") or ""),
                            "row_count": len(prior.get("rows", [])),
                        },
                        sort_keys=True,
                    ),
                )
        self._salience_pending = current
        return pulse_id

    def _maybe_run_lean_idle_heartbeat(
        self,
        snap: dict,
        gate_decision: object,
    ) -> str | None:
        heartbeat_active = _lean_idle_heartbeat_any_enabled()
        broker_active = _salience_broker_shadow_enabled()
        if not heartbeat_active and not broker_active:
            return None
        if not _lean_idle_heartbeat_eligible(gate_decision):
            return None
        window = {
            "time_facts": self._lean_idle_time_facts(),
            "body_state": self._lean_idle_body_state(),
            "open_loops": self._lean_idle_open_loops(),
            "recent_private_thoughts": self._lean_idle_recent_private_thoughts(),
        }
        body_state_window: tuple[dict[str, object], ...] = ()
        desktop_attention_shadow: tuple[dict[str, object], ...] = ()
        if _world_window_shadow_enabled():
            try:
                from core.cognition.world_window import maybe_collect_body_state_window

                body_window_result = maybe_collect_body_state_window(
                    snap or {},
                    enabled=True,
                )
                if body_window_result is not None:
                    body_state_window = tuple(
                        {
                            "field": delta.field,
                            "phrase": delta.phrase,
                            "provenance": delta.provenance,
                            "sensitivity": delta.sensitivity,
                        }
                        for delta in body_window_result.deltas
                    )
                    logger.info(
                        "world_window receipt=%s",
                        json.dumps(
                            {
                                "schema_version": "body_state_window.v0",
                                "cold_start": bool(body_window_result.cold_start),
                                "delta_count": len(body_window_result.deltas),
                                "deltas": [
                                    {
                                        "field": delta.field,
                                        "provenance": delta.provenance,
                                        "sensitivity": delta.sensitivity,
                                    }
                                    for delta in body_window_result.deltas
                                ],
                                "exclusions": [
                                    {"field": item.field, "reason": item.reason}
                                    for item in body_window_result.exclusions
                                ],
                            },
                            sort_keys=True,
                        ),
                    )
            except Exception as exc:
                logger.info(
                    "world_window receipt=%s",
                    json.dumps(
                        {
                            "schema_version": "body_state_window.v0",
                            "skip_reason": "error",
                            "error_class": exc.__class__.__name__,
                        },
                        sort_keys=True,
                    ),
                )
        if heartbeat_active and _desktop_attention_shadow_enabled():
            try:
                from core.body.desktop_presence_state import (
                    PERCEPTION_ENV as DESKTOP_PERCEPTION_ENV,
                    sample_desktop_presence,
                )
                from core.cognition.desktop_attention_shadow import (
                    maybe_collect_desktop_attention_shadow,
                )

                desktop_state = sample_desktop_presence({DESKTOP_PERCEPTION_ENV: "1"})
                attention_result = maybe_collect_desktop_attention_shadow(
                    desktop_state,
                    enabled=True,
                )
                if attention_result is not None:
                    desktop_attention_shadow = tuple(
                        {
                            "field": entry.field,
                            "phrase": entry.phrase,
                            "provenance": entry.provenance,
                            "sensitivity": entry.sensitivity,
                        }
                        for entry in attention_result.entries
                    )
                    logger.info(
                        "desktop_attention_shadow receipt=%s",
                        json.dumps(attention_result.receipt_payload(), sort_keys=True),
                    )
            except Exception as exc:
                logger.info(
                    "desktop_attention_shadow receipt=%s",
                    json.dumps(
                        {
                            "schema_version": "desktop_attention_shadow.v0",
                            "skip_reason": "error",
                            "error_class": exc.__class__.__name__,
                        },
                        sort_keys=True,
                    ),
                )
        broker_receipt = None
        proposals = []
        strategy = "changed_since_last"
        pulse_signature = "salience-broker-off"
        cold_start = False
        if broker_active:
            try:
                from core.cognition.salience_broker import fact_signatures

                pulse_signature = hashlib.sha256(
                    json.dumps(
                        fact_signatures(window),
                        sort_keys=True,
                    ).encode("utf-8")
                ).hexdigest()[:16]
            except Exception as exc:
                pulse_signature = hashlib.sha256(
                    json.dumps(
                        {
                            "skip_reason": "signature_error",
                            "error_class": exc.__class__.__name__,
                        },
                        sort_keys=True,
                    ).encode("utf-8")
                ).hexdigest()[:16]
            broker_receipt = self._maybe_run_salience_broker(window)
            if broker_receipt:
                proposals = list(broker_receipt.get("proposals", []) or [])
                strategy = str(broker_receipt.get("strategy") or strategy)
                cold_start = bool(broker_receipt.get("cold_start", False))
        if not heartbeat_active:
            if broker_active:
                self._record_salience_outcomes(
                    proposals,
                    {
                        "note_chars": 0,
                        "stored": False,
                        "skip_reason": "heartbeat_ok_or_rejected",
                    },
                    strategy=strategy,
                    pulse_signature=pulse_signature,
                    cold_start=cold_start,
                )
            return None
        enabled = _lean_idle_heartbeat_enabled()
        shadow = _lean_idle_heartbeat_shadow_enabled()
        from core.routing.cancellable_brain_call import BrainPreempted

        try:
            from core import llm_client as _llm_client
            from core.cognition.lean_idle_heartbeat import (
                LeanIdleFacts,
                run_lean_idle_heartbeat,
            )

            result = run_lean_idle_heartbeat(
                facts=LeanIdleFacts(
                    cycle=int(getattr(self, "cycle_count", 0)),
                    doorman_reason=str(getattr(gate_decision, "reason_code", "")),
                    self_card_text=self._lean_idle_self_card_text(),
                    private_signal_summary=self._lean_idle_private_signal_summary(),
                    time_facts=window["time_facts"],
                    body_state=window["body_state"],
                    body_state_window=body_state_window,
                    desktop_attention_shadow=desktop_attention_shadow,
                    open_loops=window["open_loops"],
                    recent_private_thoughts=window["recent_private_thoughts"],
                ),
                chat_fn=_llm_client.chat_direct,
                model=MODEL,
                private_thoughts=getattr(self, "private_thoughts", None),
                enabled=enabled,
                shadow=shadow,
            )
        except BrainPreempted:
            raise
        except Exception as exc:
            error_receipt = {
                "schema_version": "lean_idle_heartbeat.v0",
                "eligible": True,
                "mode": "enabled" if enabled else "shadow",
                "cycle": int(getattr(self, "cycle_count", 0)),
                "doorman_reason": str(getattr(gate_decision, "reason_code", "")),
                "llm_called": False,
                "stored": False,
                "skip_reason": "error",
                "error_class": exc.__class__.__name__,
            }
            logger.info(
                "lean_idle_heartbeat receipt=%s",
                json.dumps(error_receipt, sort_keys=True),
            )
            if broker_active:
                self._record_salience_outcomes(
                    proposals,
                    {"note_chars": 0, "stored": False, "skip_reason": "error"},
                    strategy=strategy,
                    pulse_signature=pulse_signature,
                    cold_start=cold_start,
                )
            return _HEARTBEAT_OK if enabled else None

        logger.info(
            "lean_idle_heartbeat receipt=%s",
            json.dumps(result.receipt, sort_keys=True),
        )
        self._maybe_record_fresh_moment_receipt(result)
        if broker_active:
            receipt = getattr(result, "receipt", {}) or {}
            self._record_salience_outcomes(
                proposals,
                {
                    "note_chars": int(receipt.get("note_chars") or 0),
                    "stored": bool(getattr(result, "stored", receipt.get("stored", False))),
                    "skip_reason": str(
                        getattr(
                            result,
                            "skip_reason",
                            receipt.get("skip_reason", "heartbeat_ok_or_rejected"),
                        )
                        or "heartbeat_ok_or_rejected"
                    ),
                },
                strategy=strategy,
                pulse_signature=pulse_signature,
                cold_start=cold_start,
            )
        return result.return_text if result.intercepted else None

    def _trf_apply_fragment_guard(
        self,
        *,
        user_message: str,
        reply: str,
        temporal_anchor_result,
        trace=None,
    ) -> str:
        """Apply TRF post-ARS fragment cleanup without blocking final send."""
        if temporal_anchor_result is None:
            return reply
        try:
            guard_result = guard_temporal_ars_fragment(
                user_message=user_message,
                post_ars_text=reply,
                temporal_result=temporal_anchor_result,
                current_context=extract_current_message_context(user_message),
            )
            if getattr(guard_result, "guard_used", False):
                logger.info(
                    "audit_rewrite.fragment_guard_used | reason=%s anchor_kind=%s "
                    "search_status=%s producer_version=%s",
                    getattr(guard_result, "reason", ""),
                    getattr(temporal_anchor_result, "anchor_kind", None),
                    getattr(temporal_anchor_result, "search_status", None),
                    "temporal_fragment_guard.v1",
                )
                try:
                    if trace is not None and getattr(trace.audit, "ran", False):
                        trace.audit.changed_output = True
                except Exception:
                    pass
                return guard_result.text
            if getattr(temporal_anchor_result, "anchor_detected", False):
                logger.info(
                    "audit_rewrite.fragment_guard_not_needed | anchor_kind=%s "
                    "search_status=%s producer_version=%s",
                    getattr(temporal_anchor_result, "anchor_kind", None),
                    getattr(temporal_anchor_result, "search_status", None),
                    "temporal_fragment_guard.v1",
                )
        except Exception as exc:
            logger.debug("temporal ARS fragment guard failed: %s", exc)
            try:
                logger.info(
                    "audit_rewrite.fragment_guard_unavailable | anchor_kind=%s producer_version=%s",
                    getattr(temporal_anchor_result, "anchor_kind", None),
                    "temporal_fragment_guard.v1",
                )
            except Exception:
                pass
        return reply

    def _reason(self, snap: dict, *, stale_fields: set | None = None) -> str | None:
        """Run a single reasoning cycle against the local model.

        Args:
            snap: perception snapshot.
            stale_fields: set of axis names whose value has been
                stable across recent stored thoughts. Those axes
                get stripped from the prompt the LLM sees so the
                model can't fixate on what isn't shown.
                (See core/cognition/perception_signature.py
                Patch A, 2026-04-25.) None or empty set → full prompt.
        """
        from core.cognition.perception_signature import (
            redact_stale_perception_block,
        )

        _stale = stale_fields or set()
        system_state = format_snapshot(snap)
        if "disk" in _stale or "procs" in _stale:
            system_state = redact_stale_perception_block(system_state, _stale)
        day_of_week = snap["day_of_week"]
        time_of_day = snap["time_of_day"]

        # Build context query from real content for topic-aware retrieval
        # Use last screen observation or perception summary — not timestamp labels
        if self._last_screen_obs and self._last_screen_obs.success:
            context_query = self._last_screen_obs.activity
        else:
            context_query = system_state[:200]
        recalled = self.memory.recall_for_cycle(context_query)
        # 5x.F.A — capture the recall scope into the per-cycle bag.
        # No behavior change; F.B reads it. Wrapped in try/except so a
        # malformed `recalled` shape can never break the reasoning
        # loop (the bag's failure mode is empty, which falls through
        # to current behavior in F.B's downgrade rule). `warning`
        # not `debug` so a future schema regression that breaks
        # `capture` lands a real signal in logs rather than going
        # silent until F.B starts under-downgrading.
        try:
            _crc_capture(self._cycle_recall_context, recalled)
        except Exception as _crc_exc:
            logger.warning(
                "cycle recall context capture failed (5x.F.A): %s; "
                "F.B downgrade rule will see empty scope this cycle",
                _crc_exc,
            )
        from core.cognition.envelope_builder import (
            build_envelope,
            render_envelope_for_prompt,
            resolve_recall_cap_chars,
        )
        from core.cognition import cycle_packet as _cycle_packet
        from core.cognition.cycle_packet import CycleEvidenceCandidate as _CycleCandidate

        memory_block = self.memory.format_for_prompt(
            recalled,
            max_chars=resolve_recall_cap_chars(),
        )
        stats = self.memory.memory_stats()
        if memory_block:
            logger.info(
                "Recalled: %d core, %d daily, %d raw",
                len(recalled["core"]),
                len(recalled["daily"]),
                len(recalled["raw"]),
            )

        # Per-cycle dynamic body. The VRAM baseline note and grounding
        # rules used to live at the END of this string, but they never
        # change — they're now in _STATIC_CYCLE_INSTRUCTIONS appended to
        # the system prompt so llama.cpp's KV cache can reuse them.
        prompt = (
            f"Daemon cycle: {self.cycle_count}\n"
            f"Memory stats: {stats['raw']} raw, {stats['daily']} daily, {stats['core']} core\n"
            f"Current time: {day_of_week} {time_of_day}\n\n"
            f"{system_state}\n"
        )
        _cycle_candidates: list[_CycleCandidate] = [
            _CycleCandidate(
                source_type="fresh_evidence",
                text=system_state,
                durable_id="cycle_system_state",
                salience=60,
            )
        ]

        def _extend_cycle_candidates(
            source_type: str,
            text: str,
            *,
            durable_prefix: str,
            salience: int,
        ) -> None:
            _cycle_candidates.extend(
                _cycle_packet.candidates_from_text(
                    source_type,
                    text,
                    durable_prefix=durable_prefix,
                    salience=salience,
                )
            )

        # Add circadian context
        circadian_context = self._get_circadian_context()
        prompt += f"\n{circadian_context}\n"
        if circadian_context:
            _extend_cycle_candidates(
                "fresh_evidence",
                circadian_context,
                durable_prefix="cycle_circadian_context",
                salience=55,
            )

        # Add screen context if available
        if self._last_screen_obs is not None:
            screen_context = self._last_screen_obs.format_for_context()
            prompt += f"\n{screen_context}\n"
            _extend_cycle_candidates(
                "fresh_evidence",
                screen_context,
                durable_prefix="cycle_screen_context",
                salience=80,
            )

        # Add git context if available — same gating for the AWCC
        # fixation pattern (3+ thoughts mentioning the same
        # uncommitted-files state).
        if self._last_git_context and "git" not in _stale:
            prompt += f"\n{self._last_git_context}\n"
            _extend_cycle_candidates(
                "fresh_evidence",
                self._last_git_context,
                durable_prefix="cycle_git_context",
                salience=65,
            )

        # Add GitHub context only for the legacy broad-PAT reader, which is
        # dev-test-only. GitHub v1 replaces this raw prompt-injection path with
        # S2-bounded staging and taint-railed body admission.
        if self._github_legacy_enabled and self._last_github_block:
            prompt += f"\n{self._last_github_block.text}\n"
            _extend_cycle_candidates(
                "fresh_evidence",
                self._last_github_block.text,
                durable_prefix="cycle_github_context",
                salience=65,
            )

        # Add Reddit context if available
        if self._last_reddit_block:
            prompt += f"\n{self._last_reddit_block}\n"
            _extend_cycle_candidates(
                "web_context",
                self._last_reddit_block,
                durable_prefix="cycle_reddit_context",
                salience=50,
            )

        # R3.5 (2026-05-04 symphony audit, S4 BLOCKER F7): consult
        # recent card outcomes BEFORE the cycle narration runs. Cycle
        # 35 narrating "system idle, holding quiet" 12s after the
        # 14:39 wmctrl card failed three tools is the canonical case
        # this guards against. The block lists card failures from
        # the last 120s (re-running the soft-failure detector on
        # stored execution_output so legacy lying rows from pre-R3
        # deploy are also surfaced). Empty string when no failures
        # — adds nothing to the prompt on quiet cycles.
        try:
            from core.decision import recent_action_context as _rac

            _action_outcomes_block = _rac.recent_failures(
                window_seconds=120.0,
            )
            if _action_outcomes_block:
                prompt += f"\n{_action_outcomes_block}\n"
                _extend_cycle_candidates(
                    "action_outcome",
                    _action_outcomes_block,
                    durable_prefix="cycle_recent_action_outcomes",
                    salience=100,
                )
        except Exception as _rac_e:
            # Codex R3.5 review (2026-05-04): WARNING not DEBUG.
            # The recent-actions block is a grounding rail; silent
            # failure here means the cycle goes back to claiming
            # idle without consulting recent failures (the F7 hole).
            # Same pattern as the cycle recall capture immediately
            # above, where `warning not debug` is documented as the
            # right level for grounding-rail failure surfaces.
            logger.warning(
                "recent_action_context unavailable: %s "
                "(cycle prompt continues without recent-actions block; "
                "narration grounding rail degraded)",
                _rac_e,
            )

        # Add public bot context if available
        if self._last_public_context:
            prompt += f"\n{self._last_public_context}\n"
            _extend_cycle_candidates(
                "fresh_evidence",
                self._last_public_context,
                durable_prefix="cycle_public_context",
                salience=45,
            )

        # Add proactive search results if available
        if self._proactive_search_context:
            prompt += f"\n{self._proactive_search_context}\n"
            _extend_cycle_candidates(
                "web_context",
                self._proactive_search_context,
                durable_prefix="cycle_proactive_search",
                salience=70,
            )
            self._proactive_search_context = ""  # Clear after use

        # Add continuity block during orientation window
        if self._continuity_active and self._continuity_capsule:
            cont_block = continuity_format(self._continuity_capsule)
            if cont_block:
                prompt += f"\n{cont_block}\n"
                _extend_cycle_candidates(
                    "memory_context",
                    cont_block,
                    durable_prefix="cycle_continuity_context",
                    salience=70,
                )

        # A-core #3 Step 3: builder-mode events block. Reads direct-
        # edit events from audit_log.db since the last HWM, formats
        # them into a perception block, advances the HWM AFTER
        # successful surfacing (not before — the ordering matters for
        # crash safety; see builder_mode_perception.py).
        try:
            from core.builder_mode_perception import (
                format_recent_builder_events,
                save_high_water_mark,
            )

            builder_block, new_builder_hwm = format_recent_builder_events(
                self._builder_audit_log,
                since_ts=self._builder_hwm,
            )
            if builder_block:
                prompt += f"\n{builder_block}\n"
                _extend_cycle_candidates(
                    "builder_event",
                    builder_block,
                    durable_prefix="cycle_builder_event",
                    salience=80,
                )
                self._builder_hwm = new_builder_hwm
                save_high_water_mark(self._builder_hwm_file, new_builder_hwm)
        except Exception as e:
            logger.debug("builder-mode perception block failed: %s", e)

        prompt += "\n"

        if memory_block:
            prompt += memory_block + "\n\n"
            _extend_cycle_candidates(
                "memory_context",
                memory_block,
                durable_prefix="cycle_recalled_memory",
                salience=50,
            )

        # Build an honest "signals present this cycle" manifest. This is
        # the difference between the LLM narrating invented activity
        # ("rohit is at his desk", "working on X") and saying "I have no
        # screen signal — can't claim what the owner is doing right
        # now." Observed 2026-04-21: screen_perception has been
        # silently failing for weeks, and every cycle response was
        # inventing activity. Closes the confabulation-at-source gap.
        screen_present = self._last_screen_obs is not None and getattr(
            self._last_screen_obs, "success", False
        )
        signals_present = []
        signals_absent = []
        if True:
            signals_present.append("system stats (CPU/RAM/GPU/disk/processes) — live via psutil")
        if screen_present:
            signals_present.append("screen observation — live")
        else:
            signals_absent.append(
                "screen observation — UNAVAILABLE this cycle (vision source down or capture failed)"
            )
        signals_absent.append("calendar — UNAVAILABLE this cycle (Calendar v1 not enabled)")
        if not self._github_legacy_enabled:
            signals_absent.append(
                "GitHub — UNAVAILABLE this cycle (GitHub v1 S2 ingest; legacy reader off)"
            )

        signal_manifest = (
            "SIGNALS PRESENT THIS CYCLE:\n" + "\n".join(f"  ✓ {s}" for s in signals_present) + "\n"
        )
        if signals_absent:
            signal_manifest += (
                "SIGNALS ABSENT THIS CYCLE (do NOT fabricate content for these):\n"
                + "\n".join(f"  ✗ {s}" for s in signals_absent)
                + "\n"
            )
        for _signal in signals_present:
            _cycle_candidates.append(
                _CycleCandidate(
                    source_type="fresh_evidence",
                    text=_signal,
                    durable_id=f"cycle_signal_present:{_signal}",
                    salience=70,
                )
            )
        for _signal in signals_absent:
            _cycle_candidates.append(
                _CycleCandidate(
                    source_type="signal_absence",
                    text=_signal,
                    durable_id=f"cycle_signal_absent:{_signal}",
                    salience=100,
                )
            )

        try:
            _cycle_evidence_envelope = build_envelope(
                ledger_db_path=str(LEDGER_DB_PATH),
                signals_present=signals_present,
                signals_absent=signals_absent,
                tool_results=[],
            )
        except Exception as _env_exc:
            logger.warning(
                "evidence_envelope build failed for daemon_cycle (continuing without envelope): %s",
                _env_exc,
            )
            _cycle_evidence_envelope = None
        try:
            _cycle_envelope_block = render_envelope_for_prompt(
                _cycle_evidence_envelope,
            )
        except Exception as _env_exc:
            logger.warning(
                "evidence_envelope render failed for daemon_cycle "
                "(continuing without prompt block): %s",
                _env_exc,
            )
            _cycle_evidence_envelope = None
            _cycle_envelope_block = ""
        self._last_cycle_evidence_envelope = _cycle_evidence_envelope

        # Signal manifest is the only per-cycle-dynamic rule-shaped block.
        # It goes in the user message because its content changes based on
        # which signals are present. _STATIC_CYCLE_INSTRUCTIONS (appended
        # to system prompt) references "SIGNALS PRESENT / ABSENT" here.
        prompt += signal_manifest
        if _cycle_envelope_block:
            prompt += _cycle_envelope_block + "\n\n"
            _extend_cycle_candidates(
                "fresh_evidence",
                _cycle_envelope_block,
                durable_prefix="cycle_evidence_envelope",
                salience=70,
            )

        legacy_prompt = prompt
        _cycle_prompt_decision = _build_cycle_focused_prompt(
            legacy_prompt=legacy_prompt,
            candidates=_cycle_candidates,
            time_sense_line=self._cycle_feed_time_sense_line(),
        )
        prompt = _cycle_prompt_decision.prompt
        # Store the actual prompt sent to the model for corrective retry use.
        self._last_reasoning_prompt = prompt
        _cycle_working_set = _cycle_prompt_decision.working_set
        _cycle_legacy_prompt_chars = len(legacy_prompt)

        # Session 11m's _rohit_active_until now stays a UI/activity hint only.
        # BrainGateway owns the actual arbitration: background cognition enters
        # the slot and is preempted by a real foreground request event.
        #
        # Session 11p: route daemon reasoning through llm_client so the backend
        # (Ollama or llama.cpp) is env-selectable at call time. When
        # MAEZ_LLM_BACKEND=llamacpp, this hits the CUDA llama-server on
        # 127.0.0.1:8080. Default is still ollama — flipping is a service env
        # var change, rolls back cleanly.
        #
        # Stability override: keep daemon reasoning in non-thinking mode on the
        # llama.cpp path. Gemma-4 thinking traces have previously leaked
        # channel/control markup into outputs, and those artifacts can get
        # recycled into future prompts. The daemon path benefits more from
        # parser stability than hidden scratchpad depth right now.
        from core import llm_client as _llm_client
        from core.routing.brain_gateway import with_purpose as _brain_purpose
        from core.routing.cancellable_brain_call import BrainPreempted

        # Byte-stable system message (SOUL + static cycle instructions) enables
        # llama.cpp KV cache reuse across cycles. self.system_prompt is loaded
        # once at startup; _STATIC_CYCLE_INSTRUCTIONS is a module constant.
        # Their concatenation is identical every cycle.
        system_content = self.system_prompt + "\n\n" + _STATIC_CYCLE_INSTRUCTIONS
        chat_messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ]
        chat_options = {"temperature": 0.7, "num_predict": 300}
        _cycle_chat_started = time.monotonic()

        # error_classifier-driven retry: on a TRANSIENT backend error (timeout,
        # connection refused), wait 2s and try once more. BrainPreempted is not
        # a backend error and must not enter this retry path.
        try:
            with _brain_purpose("daemon_cycle_generation"):
                response = _llm_client.chat(
                    model=MODEL,
                    messages=chat_messages,
                    think=False,
                    options=chat_options,
                )
        except BrainPreempted:
            raise
        except Exception as first_err:
            try:
                from core.error_classifier import (
                    classify as _classify,
                    emit_telemetry as _emit_err,
                )

                _cls = _classify(first_err)
                _emit_err(_cls, surface="daemon_cycle")
            except Exception:
                _cls = None

            # Transient → one retry after a short backoff.
            transient = _cls is not None and _cls.likely_transient and _cls.retryable
            if transient:
                self._s1b_note_residue_event("retry_triggered")
                logger.info(
                    "Cycle %d: %s error, retrying once after 2s backoff",
                    self.cycle_count,
                    _cls.error_class.value,
                )
                time.sleep(2.0)
                try:
                    with _brain_purpose("daemon_cycle_retry"):
                        response = _llm_client.chat(
                            model=MODEL,
                            messages=chat_messages,
                            think=False,
                            options=chat_options,
                        )
                except BrainPreempted:
                    raise
                except Exception as retry_err:
                    try:
                        _emit_err(_classify(retry_err), surface="daemon_cycle_retry")
                    except Exception:
                        pass
                    logger.error(
                        "Cycle %d: retry also failed: %s",
                        self.cycle_count,
                        retry_err,
                    )
                    self._s1b_note_residue_event("retry_failed")
                    return None
            else:
                # Structural / unknown / non-retryable → skip cleanly.
                logger.error(
                    "Cycle %d: reasoning failed (%s): %s",
                    self.cycle_count,
                    _cls.error_class.value if _cls else "unclassified",
                    first_err,
                )
                return None

        _cycle_chat_total_ms = int((time.monotonic() - _cycle_chat_started) * 1000)
        if _cycle_working_set is not None:
            _log_cycle_packet_shape(
                working_set=_cycle_working_set,
                legacy_prompt_chars=_cycle_legacy_prompt_chars,
                prefill_ms=getattr(response, "server_prompt_ms", None),
                chat_total_ms=_cycle_chat_total_ms,
                cycle_outcome="completed",
            )

        content = _extract_final((response.message.content or "").strip())
        thinking = getattr(response.message, "thinking", None)
        if thinking:
            logger.debug("Cycle %d thinking: %s", self.cycle_count, thinking.strip()[:500])
        return content if content else "(empty response)"

    def _ensure_recall_shadow_worker(self):
        worker = getattr(self, "_recall_shadow_worker", None)
        if worker is None:
            from core.health.bounded_worker import BoundedSingletonWorker

            worker = BoundedSingletonWorker(name="recall-shadow")
            self._recall_shadow_worker = worker
        return worker

    def _shadow_worker_join_for_test(self, timeout: float | None = None) -> bool:
        return self._ensure_recall_shadow_worker().join(timeout=timeout)

    def _record_last_shadow_receipt(self, rec) -> None:
        self._last_shadow_receipt = {
            "at_ts": getattr(rec, "ts", int(time.time())),
            "boot_id": getattr(rec, "boot_id", str(getattr(self, "boot_time", "") or "")),
            "state": (
                rec.shadow_skipped
                if getattr(rec, "shadow_skipped", "na") != "na"
                else rec.receipt_state.value
            ),
        }

    def _run_recall_shadow(
        self,
        *,
        text: str,
        legacy_rec,
        date_addressed: bool,
        shadow_pair_id: str,
        boot_id: str,
    ) -> None:
        start = time.monotonic()
        ts = int(time.time())
        try:
            from core.brain.brain_loop import recall_partitions_to_items
            from core.routing.focused_cognition import assemble_working_set
            from core.routing.recall_shadow import (
                ShadowSkip,
                derive_shadow_outcome,
                derive_shadow_reach,
                derive_shadow_skipped,
            )

            memory = getattr(self, "memory", None)
            if memory is None:
                raise RuntimeError("recall_shadow_missing_memory")
            evidence, context = memory.recall_for_telegram_living(
                text,
                record_recalls=False,
            )
            items = (
                recall_partitions_to_items(evidence, role_source_type="memory_evidence")
                + recall_partitions_to_items(context, role_source_type="memory_context")
            )
            working_set = assemble_working_set(
                transcript="",
                web_context="",
                owner_question=text,
                recall_items=items,
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            if latency_ms > RECALL_SHADOW_BUDGET_MS:
                logger.info(
                    "recall_shadow_soft_budget_exceeded latency_ms=%d budget_ms=%d",
                    latency_ms,
                    RECALL_SHADOW_BUDGET_MS,
                )
            rec = derive_shadow_outcome(
                legacy_rec=legacy_rec,
                shadow_reach=derive_shadow_reach(
                    working_set,
                    date_addressed=date_addressed,
                ),
                date_addressed=date_addressed,
                shadow_pair_id=shadow_pair_id,
                latency_delta_ms=latency_ms,
                ts=ts,
                boot_id=boot_id,
            )
            _log_shadow_outcome(rec=rec)
            self._record_last_shadow_receipt(rec)
        except Exception as exc:  # noqa: BLE001 - shadow must never affect reply
            try:
                from core.routing.recall_shadow import ShadowSkip, derive_shadow_skipped

                rec = derive_shadow_skipped(
                    legacy_rec=legacy_rec,
                    skip_reason=ShadowSkip.EXCEPTION,
                    shadow_pair_id=shadow_pair_id,
                    latency_delta_ms=int((time.monotonic() - start) * 1000),
                    ts=ts,
                    boot_id=boot_id,
                )
                _log_shadow_outcome(rec=rec)
                self._record_last_shadow_receipt(rec)
                logger.warning("recall_shadow_exception class=%s", type(exc).__name__)
            except Exception as log_exc:
                logger.warning(
                    "recall_shadow_exception_log_failed class=%s",
                    type(log_exc).__name__,
                )

    def handle_message(
        self,
        text: str,
        source: str = "unknown",
        *,
        transcript: str = "",
        context_note: str | ProvenancedText | None = None,
        photo_analysis: "str | None" = None,
        signals_present: "list | None" = None,
        signals_absent: "list | None" = None,
        chat_history: "list | None" = None,
        chat_id: "str | None" = None,
        tool_calls: "list[dict] | None" = None,
        recall_items: "list | tuple | None" = None,
        subjective_duration_owner_auth: "SubjectiveDurationOwnerAuth | None" = None,
        send_intermediate=None,
    ) -> str:
        """Process an incoming message through full reasoning context. Returns reply string.

        The returned reply is the AUDITED reply (see
        `core.safety.audited_output.audit_assistant_text`). The stored
        memory record is the same audited text. Callers (e.g. the
        surface adapter) must not re-audit; this is the single source
        of truth for the final reply on the daemon-synthesis path.

        Args:
            text: user's message as received from the surface.
            source: surface label ("telegram_surface", "voice", "UI",
                "web", etc.) — forwarded to audit telemetry.
            transcript: Jarvis tool-use transcript, if a tool loop ran
                before this synthesis. When non-empty, the audit skips
                the judge (real stdout grounds the claim by
                construction). Default "" for direct LLM-only replies.
            context_note: caller-supplied system context about this turn.
                Used for local perception notes such as Telegram photo
                analysis; not treated as owner-authored text. When it
                carries ProvenancedText, preserve that egress origin through
                system-message consolidation.
            signals_present / signals_absent: grounding manifest for
                the audit. Defaults to None (the audit falls back to
                its legacy "infer from surface" behavior) when the
                caller does not know.
            chat_history: prior telegram exchanges — list of dicts
                each with `"content"` in the adapter-cleaned
                `"Rohit: <msg>\\nMaez: <reply>"` shape. When passed,
                each exchange is split into a user/assistant message
                pair and inserted between the system prompt and the
                current turn so the synthesis model can resolve
                anaphoric references (e.g. "it" binding to the
                subject of the prior assistant reply). Silently
                ignored when None; unparseable entries are filtered.
                The 2026-04-24 fix: memory recall alone was missing
                the just-said turn on follow-up questions with low
                keyword overlap (incident: meta-harness at 04:42,
                "it" at 04:53 lost the referent).
        """
        try:
            _record_owner_interaction(self)
        except Exception as _activity_exc:
            logger.debug("owner interaction tracker skipped: %s", _activity_exc)

        from core.routing.recall_outcome import ReplyPath, reply_path_from_mode
        from core.routing.reply_mode import (
            ReplyDecisionSignals,
            ReplyMode,
            resolve_reply_mode,
        )

        subjective_duration_line = ""
        _subjective_duration = None
        _sd = None
        _sd_prompt_line = None
        if subjective_duration_owner_auth is not None:
            try:
                from core.evolution import subjective_duration as _sd

                _subjective_duration = _sd.SubjectiveDuration()
                _subjective_duration.record_salience_event(
                    salience_event_kind="owner_contact",
                    producer_ref=f"daemon.handle_message:{source}",
                    owner_auth=subjective_duration_owner_auth,
                )
            except Exception as _subjective_duration_exc:
                logger.debug("subjective_duration owner contact skipped: %s", _subjective_duration_exc)

        _s4_result = guard_owner_text(
            text,
            surface=source,
            crisis_signal_writer=PrivateThoughtsCrisisSignalWriter(
                getattr(self, "private_thoughts", None)
            ),
        )
        camera_answer = None
        if not _s4_result.matched:
            try:
                self._camera_presence_state = self._camera_presence_state.with_freshness()
                camera_answer = answer_camera_presence_question(text, self._camera_presence_state)
            except Exception as exc:
                logger.debug("camera presence direct-answer skipped: %s", exc)
        _pre_tail_decision = resolve_reply_mode(
            ReplyDecisionSignals(
                clinical_matched=bool(_s4_result.matched),
                camera_answer=camera_answer,
            )
        )
        if _pre_tail_decision.skip_tail:
            if _pre_tail_decision.mode is ReplyMode.CLINICAL:
                self._mark_m1_s4_policy(_s4_result.promotion_policy)
                return _s4_result.answer_text or ""
            if _pre_tail_decision.mode is ReplyMode.CAMERA:
                return camera_answer or ""

        from skills.web_search import (
            search as web_search,
            format_for_context as web_format,
            needs_web_search,
            search_rss,
            is_news_query,
            is_generic_news_query,
        )

        # Trace harness Slice 1 — start a trace at handle_message entry
        # so every owner-bridge /message turn produces a structured
        # JSONL record in logs/traces/. Trace failures must NEVER break
        # synthesis; the writer fails silent, and every capture below
        # is wrapped in try/except so a degraded trace never short-
        # circuits the reply path.
        _trace = Trace.start(surface=source, user_text=text)
        _trace_t_start = time.time()
        _turn_started_mono = time.monotonic()
        _trace_pre_audit_text: str = ""

        # Slice 2.5b — shadow-write the user_message turn to the
        # ledger. Default-off via MAEZ_LEDGER_WRITES; failures NEVER
        # break the reply path (try_write_turn swallows all exceptions
        # and returns None). The returned turn_id (if any) is captured
        # for future use as parent_turn_id when slice 2.5c plumbs the
        # model_reply turn (gated on slice 3 evidence-envelope work).
        try:
            from core.ledger.writer import try_write_turn as _try_write_turn

            _user_msg_turn_id = _try_write_turn(
                str(LEDGER_DB_PATH),
                "user_message",
                text,
                surface=source,
            )
        except Exception:
            # Belt-and-suspenders: try_write_turn is already exception-
            # safe, but a broken core.ledger import path must never
            # block the daemon. Log nothing here — the helper logs
            # internally when it actually has something to report.
            _user_msg_turn_id = None

        # Inner-residue detection on incoming user text. See
        # core/inner_residue.py — rejection markers become persistent
        # state that shapes the next turn's voice. Silent on failure.
        try:
            from core import inner_residue as _residue

            if _residue.detect_user_rejection(text):
                _residue.record(kind="user_rejection", context={"surface": source})
        except Exception:
            pass

        # Blanket-approval detection. If the user grants time-limited
        # permission in natural language (e.g. "reading is fine"),
        # persist a session so subsequent read-safe commands don't
        # round-trip through a card. Silent on failure. See
        # core/approval_sessions.py.
        try:
            from core import approval_sessions as _approvals

            _granted = _approvals.detect_and_grant(text)
            if _granted:
                logger.info(
                    "approval session granted: kinds=%s source=%s",
                    _granted,
                    source,
                )
        except Exception:
            pass

        # Premise-acceptance audit (2026-04-27 incident). Detect user
        # claims about past Maez actions ("the X you suggested",
        # "I was approving X", "you said X") and verify against the
        # proposal store + audit log. When unverified, the synthesis
        # path receives a system-level flag instructing Maez to ask
        # for clarification rather than silently proceed on a
        # potentially fabricated premise. Advisory, not blocking.
        # Silent on failure — synthesis must not abort on audit error.
        _premise_flag: str | None = None
        try:
            from core.safety.premise_audit import audit_user_premise

            _premise_flag = audit_user_premise(text)
            if _premise_flag:
                logger.info(
                    "premise unverified for surface=%s; flagging "
                    "synthesis to ask for clarification",
                    source,
                )
        except Exception as _premise_exc:
            logger.debug("premise audit skipped: %s", _premise_exc)

        logger.info("%s message: %s", source, text[:100])
        snap = perception_snapshot()
        # Grounding-context starvation fix (2026-05-05): this chat
        # path shows the current perception snapshot to the model, so
        # the audit must receive the same per-turn receipt. The
        # fallback audit manifest only carries stable / bounded-fresh
        # facts; it deliberately marks system stats absent unless the
        # caller supplies a real turn snapshot.
        _chat_signals_present = list(signals_present or [])
        _chat_signals_absent = list(signals_absent or [])
        if signals_present is None and signals_absent is None:
            try:
                from core.safety.audit_signal_manifest import (
                    default_audit_signals,
                )

                _chat_signals_present, _chat_signals_absent = default_audit_signals(source)
            except Exception as _signals_exc:
                logger.debug(
                    "chat audit fallback manifest unavailable: %s",
                    _signals_exc,
                )
                _chat_signals_present, _chat_signals_absent = [], []

            def _mark_signal_present(name: str, label: str) -> None:
                if label not in _chat_signals_present:
                    _chat_signals_present.append(label)
                _chat_signals_absent[:] = [
                    s for s in _chat_signals_absent if not str(s).lower().startswith(name)
                ]

            def _mark_signal_absent(name: str, label: str) -> None:
                if label not in _chat_signals_absent:
                    _chat_signals_absent.append(label)
                _chat_signals_present[:] = [
                    s for s in _chat_signals_present if not str(s).lower().startswith(name)
                ]

            _mark_signal_present(
                "system stats",
                "system stats (CPU/RAM/GPU/disk/processes) — live via perception_snapshot",
            )

            _screen_state = (
                getattr(self._last_screen_obs, "state", None)
                if self._last_screen_obs is not None
                else None
            )
            if _screen_state == "ok" and getattr(self._last_screen_obs, "success", False):
                _mark_signal_present("screen observation", "screen observation")
            elif _screen_state == "disabled":
                _mark_signal_absent(
                    "screen observation",
                    "screen observation (disabled by policy)",
                )
            elif _screen_state == "unavailable":
                _mark_signal_absent(
                    "screen observation",
                    "screen observation (endpoint unreachable)",
                )
            else:
                _mark_signal_absent("screen observation", "screen observation")

            if self._last_calendar_snap is not None:
                _mark_signal_present("calendar", "calendar")
            else:
                _mark_signal_absent("calendar", "calendar")

        system_state = format_snapshot(snap)
        if (
            subjective_duration_owner_auth is not None
            and _subjective_duration is not None
            and _sd is not None
        ):
            try:
                _sd_prompt_line = _sd.subjective_duration_prompt_line
                subjective_duration_line = _sd_prompt_line(
                    owner_auth=subjective_duration_owner_auth,
                    store=_subjective_duration,
                )
            except Exception as _subjective_duration_exc:
                logger.debug("subjective_duration owner line skipped: %s", _subjective_duration_exc)
        authoritative_tool_reply = _authoritative_tool_reply(tool_calls)
        recalled = self.memory.recall_for_telegram(text)
        # Trace: capture every memory id surfaced by the recall — across
        # core, daily, raw — so a future harness can verify the model's
        # reply cited evidence the recall actually pulled.
        try:
            _ids: list[str] = []
            for tier_key in ("core", "daily", "raw"):
                for entry in (recalled or {}).get(tier_key, []) or []:
                    eid = entry.get("id")
                    if eid:
                        _ids.append(str(eid))
            _trace.memory_ids = _ids
        except Exception as _trace_exc:
            logger.debug("trace memory_ids capture skipped: %s", _trace_exc)
        # Bound the recall block so a high-recall query (long-content
        # core memories + many raw matches) cannot push the whole
        # prompt past the llama-server context window. Cap is
        # coordinated with the evidence envelope per SLICE_3_0d §1:
        # 52K chars (~13K tokens) when an envelope is present in the
        # prompt; 60K (legacy) when MAEZ_EVIDENCE_ENVELOPE_DISABLED=1.
        # Core + daily are preserved; raw entries drop from the tail
        # if needed. See core.cognition.envelope_builder.
        from core.cognition.envelope_builder import (
            build_envelope as _build_envelope,
            render_envelope_for_prompt as _render_envelope,
            resolve_recall_cap_chars as _resolve_recall_cap,
        )

        memory_block = self.memory.format_for_prompt(
            recalled,
            max_chars=_resolve_recall_cap(),
        )

        # Slice 3 wiring: build the evidence envelope so the LLM sees
        # what it MAY claim and what's forbidden BEFORE generation,
        # and so the post-generation audit gets the same context.
        # Returns None when MAEZ_EVIDENCE_ENVELOPE_DISABLED=1 — the
        # downstream renderer treats None as empty (legacy prompt
        # shape) and audit_assistant_text falls through to the
        # legacy signals path.
        # Direction (b): record owner-sent photo vision as a PRESENT signal so
        # the evidence envelope (built next) and the post-generation audit know
        # photo vision really happened this turn — otherwise the grounding judge
        # treats the envelope as source of truth and can false-flag the focused
        # reply's "I saw the photo" as unsupported. Distinct from desktop screen
        # observation, which stays absent above.
        if photo_analysis and (
            "owner-sent photo vision" not in _chat_signals_present
        ):
            # ≤30 chars: fits the envelope's per-signal cap (§2) untruncated.
            _chat_signals_present.append("owner-sent photo vision")
        _daemon_tool_results = []
        _evidence_envelope = None
        _envelope_block = ""

        # Web search if needed. If a deterministic tool already answered
        # a volatile fact (e.g. currency conversion), do not add web
        # snippets that can override the tool result during synthesis.
        from core.routing.recall_stack_config import resolve_recall_stack

        _recall_stack_config = resolve_recall_stack()
        web_context = ""
        _photo_freshness_query = None
        _legacy_routing_observation_id = None
        _empty_web_search = False
        _routing_obs_tool = None
        _wb_web_quality = "adequate"
        _wb_result_count = 0
        _prior = None
        _belief_cmp = None
        _cls = None
        _override_event_id = None
        _ledger = None
        _routing_turn_outcome_quality = None
        if _routing_prior_consult_enabled():
            try:
                from core.routing.observation import _default_store
                from core.routing.observation.priors import learn_priors
                from core.routing.observation_class import classify_request_class
                _cls = classify_request_class(text)[0]
                _prior = learn_priors(_default_store()).get((_cls, "web_search"))
                if os.environ.get("MAEZ_ROUTING_PRIORS_SHADOW") == "1" \
                   or os.environ.get("MAEZ_ROUTING_PRIORS_ENABLED") == "1":
                    logger.info("routing_prior_shadow class=%s prior=%s would_veto=%s",
                                _cls, _prior, _prior_vetoes_reflex(_prior))
                if _routing_beta_shadow_enabled() or _routing_beta_veto_enabled():
                    from core.routing.observation.priors import compare_beliefs
                    _belief_cmp = compare_beliefs(_default_store()).get((_cls, "web_search"))
                    if _belief_cmp is not None:
                        logger.info("routing_belief_compare class=%s n=%s usable=%s n8_veto=%s beta_veto=%s "
                                    "n8_conf=%.3f beta_p=%.3f", _cls, _belief_cmp.n, _belief_cmp.usable,
                                    _belief_cmp.n8_would_veto, _belief_cmp.beta_would_veto,
                                    _belief_cmp.n8_confidence, _belief_cmp.beta_p_below)
            except Exception as _pe:
                logger.debug("routing prior/belief consult skipped: %s", _pe)
        _reflex = needs_web_search(text)
        _would_web_search = None
        if _veto_ledger_enabled() and os.environ.get("MAEZ_ROUTING_PRIORS_ENABLED") == "1":
            _would_web_search = bool(
                not authoritative_tool_reply
                and _daemon_parallel_web_search_enabled(transcript, recall_stack_config=_recall_stack_config)
                and _reflex
            )
            if _cls is not None and _would_web_search and _prior_vetoes_reflex(_prior):
                try:  # seam 2: open same-class veto in window -> lift the veto ONCE (re-ask)
                    _ledger = _veto_ledger_get(_ledger)
                    _open = _ledger.find_open_for_class(_cls, "web_search", now=time.time())
                    _override_event_id = _open.id if _open is not None else None
                except Exception as _le:
                    logger.debug("veto ledger override check skipped: %s", _le)
        _veto_decision = _prior_vetoes_reflex(_prior)
        if _routing_beta_veto_enabled() and _belief_cmp is not None:
            _veto_decision = _belief_cmp.beta_would_veto  # graduation: Beta replaces n/8 (owner-flipped)
        if os.environ.get("MAEZ_ROUTING_PRIORS_ENABLED") == "1" and _veto_decision \
           and _override_event_id is None:
            _reflex = False  # learned veto
            if _veto_ledger_enabled() and _cls is not None and _would_web_search:
                try:
                    _ledger = _veto_ledger_get(_ledger)
                    _ledger.record_veto(
                        class_id=_cls, tool="web_search", prior_n=_prior.n,
                        prior_success_rate=_prior.success_rate, prior_confidence=_prior.confidence,
                        turn_id=_user_msg_turn_id, surface=source, now=time.time())
                except Exception as _re:
                    logger.debug("veto event record skipped: %s", _re)
        if (
            not authoritative_tool_reply
            and _daemon_parallel_web_search_enabled(
                transcript,
                recall_stack_config=_recall_stack_config,
            )
            and _reflex
        ):
            logger.info("Web search triggered for: %s", text[:80])
            _routing_obs_started = time.monotonic()
            # Only a GENERIC 'give me the news' request uses the category-feed RSS
            # reader; a news query naming a subject ('news about Elon') goes to the
            # real keyword search, because search_rss never searches for the subject.
            _use_rss = is_news_query(text) and is_generic_news_query(text)
            _routing_obs_tool = "search_rss" if _use_rss else "web_search"
            if _use_rss:
                sr = search_rss(text, max_results=5)
            else:
                sr = web_search(text, max_results=3)
            try:
                from core.safety.action_receipts import build_search_tool_result

                _daemon_tool_results.append(
                    build_search_tool_result(
                        query=text,
                        result=sr,
                        source="daemon_web_search",
                    )
                )
            except Exception as _receipt_exc:
                logger.debug(
                    "daemon web search receipt build skipped: %s",
                    _receipt_exc,
                )
            web_context = web_format(sr, include_quality=True)
            from skills.web_search import _compute_quality
            if web_context:
                _wb_web_quality, _wb_result_count = _compute_quality(sr)[:2]
            from core.routing.focused_cognition import (
                is_empty_search_result as _is_empty_search_result,
            )

            _empty_web_search = _is_empty_search_result(sr)
            logger.info(
                "Web search: %d results injected (%s)",
                sr.get("result_count", 0),
                sr.get("source_type", "web"),
            )
            try:
                from core.routing.observation import record_legacy_web_search_observation

                _cls_id = _cls_score = _cls_ver = None
                if os.environ.get("MAEZ_ROUTING_CLASS_CAPTURE") == "1":
                    try:
                        from core.routing.observation_class import classify_request_class
                        _cls_id, _cls_score, _cls_ver = classify_request_class(text)
                    except Exception as _ce:
                        logger.debug("request-class capture skipped: %s", _ce)

                _routing_obs_count = int(sr.get("result_count", 0) or 0)
                _legacy_routing_observation_id = record_legacy_web_search_observation(
                    user_text=text,
                    surface=source,
                    chat_id=chat_id,
                    chosen_tool=_routing_obs_tool,
                    execution_status="success" if _routing_obs_count > 0 else "empty",
                    evidence_block_count=1 if web_context else 0,
                    outcome_quality=(
                        "structured_evidence"
                        if _routing_obs_count > 0
                        else "empty_but_honest"
                    ),
                    latency_ms=(time.monotonic() - _routing_obs_started) * 1000,
                    request_class_id=_cls_id,
                    request_class_score=_cls_score,
                    request_class_version=_cls_ver,
                )
                _routing_turn_outcome_quality = (
                    "structured_evidence"
                    if _routing_obs_count > 0
                    else "empty_but_honest"
                )
            except Exception as _routing_obs_exc:
                logger.debug(
                    "routing observation legacy web search skipped: %s",
                    _routing_obs_exc,
                )

        if (
            photo_analysis
            and not authoritative_tool_reply
            and _daemon_parallel_web_search_enabled(
                transcript,
                recall_stack_config=_recall_stack_config,
            )
        ):
            try:
                from core.routing.focused_cognition import (
                    photo_freshness_web_search_enabled,
                )
            except Exception as _photo_freshness_exc:
                logger.debug(
                    "photo freshness web search gate unavailable: %s",
                    _photo_freshness_exc,
                )
                _photo_freshness_allowed = False
            else:
                _photo_freshness_allowed = photo_freshness_web_search_enabled()
        else:
            _photo_freshness_allowed = False
        if (
            photo_analysis
            and _photo_freshness_allowed
            and not authoritative_tool_reply
            and _daemon_parallel_web_search_enabled(
                transcript,
                recall_stack_config=_recall_stack_config,
            )
            and (not web_context or _empty_web_search)
        ):
            try:
                from core.routing.focused_cognition import (
                    photo_freshness_search_query,
                )

                _photo_freshness_query = photo_freshness_search_query(
                    caption=text,
                    analysis_text=photo_analysis,
                )
            except Exception as _photo_freshness_exc:
                logger.debug(
                    "photo freshness search query skipped: %s",
                    _photo_freshness_exc,
                )
                _photo_freshness_query = None
            if _photo_freshness_query:
                logger.info(
                    "Photo freshness search triggered for: %s",
                    _photo_freshness_query[:80],
                )
                _routing_obs_started = time.monotonic()
                _routing_obs_tool = "photo_freshness_web_search"
                sr = web_search(_photo_freshness_query, max_results=3)
                try:
                    from core.safety.action_receipts import build_search_tool_result

                    _daemon_tool_results.append(
                        build_search_tool_result(
                            query=_photo_freshness_query,
                            result=sr,
                            source="daemon_photo_freshness_web_search",
                        )
                    )
                except Exception as _receipt_exc:
                    logger.debug(
                        "daemon photo freshness receipt build skipped: %s",
                        _receipt_exc,
                    )
                web_context = web_format(sr)
                from skills.web_search import _compute_quality
                if web_context:
                    _wb_web_quality, _wb_result_count = _compute_quality(sr)[:2]
                from core.routing.focused_cognition import (
                    is_empty_search_result as _is_empty_search_result,
                )

                _empty_web_search = _is_empty_search_result(sr)
                logger.info(
                    "Photo freshness search: %d results injected (%s)",
                    sr.get("result_count", 0),
                    sr.get("source_type", "web"),
                )
                try:
                    from core.routing.observation import (
                        record_legacy_web_search_observation,
                    )

                    _cls_id = _cls_score = _cls_ver = None
                    if os.environ.get("MAEZ_ROUTING_CLASS_CAPTURE") == "1":
                        try:
                            from core.routing.observation_class import (
                                classify_request_class,
                            )
                            _cls_id, _cls_score, _cls_ver = classify_request_class(text)
                        except Exception as _ce:
                            logger.debug("request-class capture skipped: %s", _ce)

                    _routing_obs_count = int(sr.get("result_count", 0) or 0)
                    _legacy_routing_observation_id = (
                        record_legacy_web_search_observation(
                            user_text=text,
                            surface=source,
                            chat_id=chat_id,
                            chosen_tool=_routing_obs_tool,
                            execution_status=(
                                "success" if _routing_obs_count > 0 else "empty"
                            ),
                            evidence_block_count=1 if web_context else 0,
                            outcome_quality=(
                                "structured_evidence"
                                if _routing_obs_count > 0
                                else "empty_but_honest"
                            ),
                            latency_ms=(time.monotonic() - _routing_obs_started)
                            * 1000,
                            request_class_id=_cls_id,
                            request_class_score=_cls_score,
                            request_class_version=_cls_ver,
                        )
                    )
                except Exception as _routing_obs_exc:
                    logger.debug(
                        "routing observation photo freshness search skipped: %s",
                        _routing_obs_exc,
                    )

        try:
            _evidence_envelope = _build_envelope(
                ledger_db_path=str(LEDGER_DB_PATH),
                signals_present=_chat_signals_present,
                signals_absent=_chat_signals_absent,
                tool_results=_daemon_tool_results,
                turn_id=_user_msg_turn_id,
            )
        except Exception as _env_exc:
            # Envelope construction is best-effort; a builder bug
            # MUST NOT block the daemon's reply path. Fall through
            # to the legacy signals-only audit.
            logger.warning(
                "evidence_envelope build failed (continuing without envelope): %s",
                _env_exc,
            )
            _evidence_envelope = None
        _envelope_block = _render_envelope(_evidence_envelope)

        is_voice = source == "voice"
        prompt = f"{system_state}\n\n"
        if subjective_duration_line:
            prompt += subjective_duration_line + "\n\n"

        # Public bot context — early for attention weight
        public_ctx = self._get_public_context()
        if public_ctx:
            prompt += public_ctx + "\n\n"

        if memory_block:
            prompt += memory_block + "\n\n"
        # Slice 3 wiring: envelope block sits between recall and
        # web_context. Empty string when envelope is None (disabled
        # mode) or the envelope carries no constraints — keeps the
        # legacy prompt shape identical in those cases.
        if _envelope_block:
            prompt += _envelope_block + "\n\n"
        if web_context and not _empty_web_search:
            _wc_block = _wrap_daemon_web_context(web_context, path="legacy")
            prompt += (
                f"{_wc_block}\n\n"
                f"INSTRUCTION: Real search results above. Do NOT list headlines. "
                f"Synthesize into 3-5 sentences. Tell the owner what matters and why. "
                f"Give your opinion. Connect to his context if relevant.\n\n"
            )
        if is_voice:
            prompt += (
                f'the owner just spoke to you out loud:\n"{text}"\n\n'
                f"Respond in 1-2 short sentences. Your response will be spoken aloud.\n"
                f"Be warm, direct, and conversational. No bullet points or markdown.\n\n"
            )
        else:
            prompt += (
                f'the owner sent via {source}:\n"{text}"\n\nRespond directly and concisely.\n\n'
            )
        prompt += (
            "Remember: NEVER suggest touching ollama, its models, or any "
            "process that powers your reasoning."
        )

        # Build system prompt with public bot awareness
        sys_prompt = self.system_prompt
        # Capability registry injection — same wiring as CLI
        # (see core/capability_registry.py). Grounds self-description
        # questions on real facts so the model doesn't invent modules,
        # schedules, or postconditions.
        try:
            from core.capability_registry import prompt_snippet as _cap_snippet

            sys_prompt += "\n\n" + _cap_snippet()
        except Exception:
            pass
        try:
            from core.infra.capability_manual_context import manual_context_snippet

            _manual_context = manual_context_snippet(text)
            if _manual_context:
                sys_prompt += "\n\n" + _manual_context
        except Exception:
            pass
        if public_ctx:
            sys_prompt += (
                "\n\nCRITICAL: The [MY CONVERSATIONS] section shows people you spoke with today. "
                "Report those conversations naturally as your own. Never say 'no one' "
                "if conversations are present."
            )

        # Thread prior-turn context into the synthesis. Without this,
        # follow-ups like "you think it'll be useful?" have no referent
        # because the last assistant reply lives only in chat history,
        # not in memory recall (semantic overlap is too low for recall
        # to surface it reliably). See chat_history docstring above.
        messages: list[dict] = [{"role": "system", "content": sys_prompt}]
        system_part_capture: list[tuple[str, str]] = [("sys_prompt", sys_prompt)]
        try:
            from core.brain.conversation_history import history_to_messages

            messages.extend(history_to_messages(chat_history))
        except Exception as _hist_exc:
            logger.debug("chat_history threading skipped: %s", _hist_exc)
        # Tool transcripts are synthesis context, not owner text. Earlier
        # Telegram routing spliced this block into `text`, which polluted
        # memory/search with internal instructions and made follow-up turns
        # like "Proceed" lose the real action request. Keep owner text clean
        # and give the model tool-state as a system note instead.
        transcript_context = ""
        if transcript and transcript.strip():
            try:
                from core.brain_loop import (
                    _instruction_block_for_transcript,
                    _transcript_instruction_state,
                )

                instruction_block = _instruction_block_for_transcript(transcript)
                logger.info(
                    "daemon_transcript_instruction_state surface=%s state=%s prefix=%r",
                    source,
                    _transcript_instruction_state(transcript),
                    transcript[:100],
                )

                transcript_context = f"{transcript}\n\n{instruction_block}"
            except Exception as _tool_ctx_exc:
                logger.debug("tool transcript context skipped: %s", _tool_ctx_exc)
        # ADR 0019 Phase 6 — lived recall brief. Built from the user's
        # text (the message they just sent), injected as a system note
        # AFTER chat_history threading and BEFORE premise_flag so the
        # synthesis model reads "what we have lived through together"
        # as background, with the premise flag still landing closest
        # to the user turn. Gated by MAEZ_LIVED_RECALL — default
        # enabled, set to "0" for fast rollback if it degrades chat
        # quality. Build-time exceptions are caught silently; synthesis
        # must continue regardless of the lived layer's health.
        # Session 3 of working-self arc: assemble the current goal
        # hierarchy and pass it through to the lived-recall builder.
        # Conway 2000 working-self modulates retrieval; Park 2023 adds
        # goal-alignment as a fourth scoring component. Gated by
        # MAEZ_WORKING_SELF — DEFAULT DISABLED (opposite of
        # MAEZ_LIVED_RECALL): this path is brand new, not yet
        # probe-validated against regression. Operator opts in by
        # setting "1". Failure is silent: the lived brief still
        # builds without goals.
        _goals = None
        if os.environ.get("MAEZ_WORKING_SELF", "0") == "1":
            try:
                _goals = assemble_goals(
                    episode_store=self.lived_episodes,
                    graph=self.lived_graph,
                    wants=getattr(self, "wants", None),
                    recent_owner_text=text,
                )
            except Exception as _goals_exc:
                logger.debug("working-self goal assembly failed: %s", _goals_exc)
                _goals = None
        # Trace: capture the assembled goals as compact "source: text"
        # labels so the JSONL turn record answers "what did the
        # working self believe was the focus?" An empty/None hierarchy
        # leaves the field at its default empty list.
        try:
            if _goals is not None and not _goals.is_empty:
                _trace.working_self_goals = [f"{g.source}: {g.text}" for g in _goals.goals]
        except Exception as _trace_goals_exc:
            logger.debug("trace working_self_goals capture skipped: %s", _trace_goals_exc)
        _lived_brief = ""
        _temporal_anchor_result = None
        if os.environ.get("MAEZ_LIVED_RECALL", "1") != "0":
            try:
                _lived_brief = build_lived_recall_brief(
                    text,
                    episode_store=self.lived_episodes,
                    graph=self.lived_graph,
                    max_items=6,
                    goals=_goals,
                )
            except Exception as _lived_exc:
                logger.debug("lived recall brief build failed: %s", _lived_exc)
                _lived_brief = ""
        if _lived_brief:
            messages.append({"role": "system", "content": _lived_brief})
            system_part_capture.append(("lived_brief", _lived_brief))
        try:
            _temporal_anchor_result = build_temporal_anchor_recall_brief(
                text,
                episode_store=self.lived_episodes,
            )
            if getattr(_temporal_anchor_result, "anchor_detected", False):
                logger.info(
                    "temporal_recall.summary | anchor_kind=%s search_status=%s "
                    "evidence_count=%d elapsed_ms=%d truncated=%s producer_version=%s",
                    getattr(_temporal_anchor_result, "anchor_kind", None),
                    getattr(_temporal_anchor_result, "search_status", None),
                    int(getattr(_temporal_anchor_result, "item_count", 0) or 0),
                    int(getattr(_temporal_anchor_result, "elapsed_ms", 0) or 0),
                    bool(getattr(_temporal_anchor_result, "truncated", False)),
                    "temporal_anchor_recall.v1",
                )
            if getattr(_temporal_anchor_result, "brief_text", ""):
                messages.append(
                    {
                        "role": "system",
                        "content": _temporal_anchor_result.brief_text,
                    }
                )
                system_part_capture.append(
                    ("temporal_anchor", _temporal_anchor_result.brief_text)
                )
        except Exception as _temporal_exc:
            logger.debug("temporal anchor recall failed: %s", _temporal_exc)
            _temporal_anchor_result = None

        # Step 5r: inject ambient context (weather, active window,
        # latest iPhone signals) into the chat prompt. The signal
        # pipeline has been ingesting since 2026-04-18 (~80 daily
        # files) and ``wondering_cycle`` already uses this same
        # block — but the chat-message path didn't, so Telegram
        # answers ran without knowing where the owner was or what
        # they were doing. Single-block injection; cached for 60s
        # inside ambient_prompt_block so per-turn cost is bounded.
        # Gated by ``MAEZ_AMBIENT_BRIEF`` (default on, "0" disables)
        # so the env var pattern matches MAEZ_LIVED_RECALL.
        # Step 5v: declared at function scope so the response log
        # below can reference its size without re-pulling.
        _ambient_block = ""
        _capability_block = ""
        try:
            # Evidence-precedence v0: build the capability card outside the
            # ambient-brief gate and outside the ambient-empty check. It returns
            # "" when the organ flag is off.
            from core.cognition.capability_card import capability_prompt_block

            _capability_block = capability_prompt_block()
        except Exception as _cap_exc:
            logger.debug("capability card injection failed: %s", _cap_exc)
        if os.environ.get("MAEZ_AMBIENT_BRIEF", "1") != "0":
            try:
                from core.memory.ambient_format import ambient_prompt_block

                _ambient_block = ambient_prompt_block()
            except Exception as _amb_exc:
                logger.debug(
                    "ambient brief injection failed: %s",
                    _amb_exc,
                )
        _combined_context_block = "\n\n".join(
            p for p in (_ambient_block, _capability_block) if p
        )
        if _combined_context_block:
            messages.append(
                {
                    "role": "system",
                    "content": _combined_context_block,
                }
            )
            system_part_capture.append(("ambient_block", _combined_context_block))

        # Trace: capture the evidence ids the lived brief surfaced.
        # An empty brief yields an empty list — silence is honest.
        try:
            _trace.lived_recall_ids = _trace_extract_evidence_ids(_lived_brief)
            if _temporal_anchor_result is not None and getattr(
                _temporal_anchor_result, "evidence_ids", None
            ):
                _trace.lived_recall_ids.extend(
                    [
                        str(eid)
                        for eid in getattr(_temporal_anchor_result, "evidence_ids", ())
                        if str(eid) not in _trace.lived_recall_ids
                    ]
                )
        except Exception as _trace_exc:
            logger.debug("trace lived_recall_ids capture skipped: %s", _trace_exc)
        # Inject the premise-audit flag (if any) as a system note
        # *immediately before* the user turn so the synthesis model
        # treats it as a directive about THIS message specifically,
        # not background context. 2026-04-27 incident fix.
        if _premise_flag:
            messages.append({"role": "system", "content": _premise_flag})
            system_part_capture.append(("premise_flag", _premise_flag))
        _context_note: str | ProvenancedText | None = None
        if context_note and str(context_note).strip():
            _context_note = (
                context_note
                if isinstance(context_note, ProvenancedText)
                else str(context_note).strip()
            )
        # Slice 3a - Evidence Precedence Steer. Compute from the raw
        # dispatcher transcript, never transcript_context; the latter includes
        # instruction examples that contain the marker strings.
        from core.routing.evidence_state import (
            WEB_GROUNDED_LABELS,
            build_evidence_precedence_directive,
            build_turn_final_context,
            turn_evidence_state,
        )

        _evidence_state = turn_evidence_state(
            transcript=transcript,
            web_context=web_context,
        )
        if (
            strict_env_flag("MAEZ_THIN_EVIDENCE_HONESTY_ENABLED")
            and _evidence_state.evidence_quality
        ):
            try:
                from skills.web_search import (
                    _THIN_RESULT_COUNT,
                    _THIN_SNIPPET_CHARS,
                )

                logger.info(
                    "thin_evidence quality=%s result_count=%s snippet_chars=%s "
                    "thresholds=(%s,%s) directive=%s surface=%s",
                    _evidence_state.evidence_quality,
                    _evidence_state.evidence_result_count,
                    _evidence_state.evidence_snippet_chars,
                    _THIN_RESULT_COUNT,
                    _THIN_SNIPPET_CHARS,
                    "thin" if _evidence_state.thin_evidence else "normal",
                    source,
                )
            except Exception:
                pass
        evidence_directive = ""
        if _evidence_state.evidence_present:
            evidence_directive = build_evidence_precedence_directive(_evidence_state)
        if transcript_context:
            system_part_capture.append(("transcript_context", transcript_context))
        if evidence_directive:
            system_part_capture.append(
                ("evidence_precedence_directive", evidence_directive)
            )
        turn_final_context = build_turn_final_context(
            transcript_context,
            evidence_directive,
        )
        try:
            from core.routing.focused_cognition import (
                build_intra_turn_echo_reply as _build_intra_turn_echo_reply,
                dialogue_continuity_state as _dialogue_continuity_state,
            )

            _dialogue_state = _dialogue_continuity_state(text)
            _current_turn_echo_reply = _build_intra_turn_echo_reply(text)
        except Exception:
            _dialogue_state = None
            _current_turn_echo_reply = None
        _dialogue_needs_or_uncertain = bool(
            _dialogue_state
            and (
                getattr(_dialogue_state, "needs_dialogue", False)
                or getattr(_dialogue_state, "fail_safe_legacy", False)
            )
        )
        try:
            from core.routing.temporal_cue import (
                absolute_recall_cue as _absolute_recall_cue,
            )

            _abs_recall_cue = _absolute_recall_cue(text)
        except Exception:
            _abs_recall_cue = None
        _date_addressed_turn = bool(
            _abs_recall_cue and getattr(_abs_recall_cue, "is_address", False)
        )
        _prior_chat_message_count = _chat_history_message_count(messages)
        _temporal_anchor_brief_text = (
            str(getattr(_temporal_anchor_result, "brief_text", "") or "")
            if _temporal_anchor_result is not None
            else ""
        )
        _truly_empty_continuity_reply, _continuity_shape_instruction_text = (
            _resolve_continuity_fallback_shape(
                owner_question=text,
                continuity_turn=bool(_dialogue_needs_or_uncertain),
                date_addressed=bool(_date_addressed_turn),
                fresh_context_present=bool(
                    (turn_final_context or "").strip() or recall_items
                ),
                prior_chat_message_count=_prior_chat_message_count,
                lived_brief=_lived_brief,
                temporal_anchor_brief=_temporal_anchor_brief_text,
            )
        )
        if _continuity_shape_instruction_text:
            messages.append(
                {"role": "system", "content": _continuity_shape_instruction_text}
            )
            system_part_capture.append(
                ("continuity_shape", _continuity_shape_instruction_text)
            )
        final_system_part = _compose_turn_final_system_part(
            turn_final_context,
            context_note=_context_note,
        )
        if _context_note:
            system_part_capture.append(("context_note", _context_note))
        messages = _consolidate_system_messages(
            messages,
            final_system_part=final_system_part,
        )
        messages.append({"role": "user", "content": prompt})
        _focused_candidate = (
            _focused_cognition_enabled(recall_stack_config=_recall_stack_config)
            and source != "voice"
            and not _current_turn_echo_reply
            and (
                _evidence_state.evidence_present
                or _dialogue_needs_or_uncertain
                or _date_addressed_turn
            )
        )
        _honest_empty_candidate = (
            _empty_web_search
            and not photo_analysis
            and not _evidence_state.evidence_present
            and not _dialogue_needs_or_uncertain
            and not _current_turn_echo_reply
            and not authoritative_tool_reply
        )
        _reply_decision = resolve_reply_mode(
            ReplyDecisionSignals(
                authoritative_tool_reply=bool(authoritative_tool_reply),
                echo_reply=bool(_current_turn_echo_reply),
                honest_empty_candidate=bool(_honest_empty_candidate),
                focused_candidate=bool(_focused_candidate),
                date_addressed=bool(_date_addressed_turn),
            )
        )
        _legacy_call_purpose = _reply_decision.call_purpose
        if transcript_context or evidence_directive:
            _log_daemon_system_part_shape(
                surface=source,
                call_purpose=_legacy_call_purpose,
                system_parts=system_part_capture,
            )
            _log_daemon_prompt_payload_shape(
                surface=source,
                call_purpose=_legacy_call_purpose,
                messages=messages,
                transcript_context=transcript_context,
                evidence_directive=evidence_directive,
            )

        _recall_carrier_receipt = RECALL_CARRIER_NOT_CONSULTED
        _had_confirmed = False
        _dated_denial_kind_for_turn = "na"
        _rk_cited_grounded = False
        _rk_cited_mixed = False
        _rk_unmatched = 0
        _rk_coverage = None
        _rk_reply_grounding = None
        _rk_focused_elapsed = None
        _rk_turn_kind = (
            "both"
            if (_date_addressed_turn and _dialogue_needs_or_uncertain)
            else "dated"
            if _date_addressed_turn
            else "continuity"
            if _dialogue_needs_or_uncertain
            else "ordinary"
        )
        _focused_working_set = None
        _focused_result = None
        _focused_verdict = None
        _focused_support_evidence_map = {}
        _reply_path = reply_path_from_mode(_reply_decision.mode.value.lower())
        _focused_used = False
        _focused_answer_used = False
        _recall_outcome_rec = None
        _recall_shadow_attempt = False
        _recall_status_reply = None
        _recent_activity_status_reply = None
        _casual_presence_status_reply = None
        _identity_status_reply = None
        _protected_refusal_followup_reply = None
        _receipt_box = None
        _receipt_timer = None
        _receipt_eligible_for_turn = False
        _receipt_after_ms = None

        def _close_receipt_watchdog() -> None:
            nonlocal _receipt_timer
            try:
                if _receipt_box is not None:
                    _receipt_box.cancel()
                if _receipt_timer is not None:
                    _receipt_timer.cancel()
            except Exception as _receipt_close_exc:
                logger.debug(
                    "recall receipt watchdog close skipped: %s",
                    type(_receipt_close_exc).__name__,
                )

        def _arm_recall_receipt() -> None:
            nonlocal _receipt_box, _receipt_timer, _receipt_eligible_for_turn, _receipt_after_ms
            try:
                from core.routing.recall_receipt import (
                    RECEIPT_AFTER_MS,
                    ReceiptAckBox,
                    WORKING_RECEIPT_TEXT,
                    receipt_eligible,
                )

                _receipt_after_ms = RECEIPT_AFTER_MS
                _receipt_eligible_for_turn = receipt_eligible(
                    flag_on=_recall_receipt_enabled(),
                    focused_carrier_engaged=True,
                    surface_sink_available=send_intermediate is not None,
                )
                if not _receipt_eligible_for_turn or send_intermediate is None:
                    return
                _receipt_box = ReceiptAckBox(turn_started_mono=_turn_started_mono)

                def _mark_send_result(result: str, completed_mono=None) -> None:
                    _completed = time.monotonic() if completed_mono is None else completed_mono
                    if result == "ok":
                        _receipt_box.mark_ok(completed_mono=_completed)
                    elif result == "timeout":
                        _receipt_box.mark_timeout(completed_mono=_completed)
                    else:
                        _receipt_box.mark_failed(completed_mono=_completed)

                def _should_send_receipt() -> bool:
                    _snap = _receipt_box.snapshot(now_mono=time.monotonic())
                    return bool(_snap.fired and not _snap.cancelled)

                def _fire_receipt() -> None:
                    if not _receipt_box.try_mark_fired():
                        return
                    try:
                        send_intermediate(
                            WORKING_RECEIPT_TEXT,
                            on_complete=_mark_send_result,
                            should_send=_should_send_receipt,
                        )
                    except Exception as _receipt_send_exc:
                        _receipt_box.mark_failed(completed_mono=time.monotonic())
                        logger.debug(
                            "recall receipt send skipped: %s",
                            type(_receipt_send_exc).__name__,
                        )

                _elapsed_ms = (time.monotonic() - _turn_started_mono) * 1000
                _delay_s = max(0.0, (RECEIPT_AFTER_MS - _elapsed_ms) / 1000.0)
                _receipt_timer = threading.Timer(_delay_s, _fire_receipt)
                _receipt_timer.daemon = True
                _receipt_timer.start()
            except Exception as _receipt_arm_exc:
                logger.debug(
                    "recall receipt watchdog arm skipped: %s",
                    type(_receipt_arm_exc).__name__,
                )

        if _recall_status_intercept_enabled():
            try:
                from core.routing.recall_self_status import (
                    build_recall_practice_reply as _build_recall_practice_reply,
                    build_recall_status_reply as _build_recall_status_reply,
                    is_recall_practice_query as _is_recall_practice_query,
                    is_recall_status_query as _is_recall_status_query,
                    recall_status_query_wants_timestamp as _recall_status_query_wants_timestamp,
                )

                if _is_recall_practice_query(text) and not _date_addressed_turn:
                    _shadow_status_enabled = bool(
                        _recall_shadow_enabled()
                        and not _recall_stack_config.triad_on
                    )
                    _recall_status_reply, _practice_state = _build_recall_practice_reply(
                        shadow_enabled=_shadow_status_enabled,
                        last_shadow_receipt=getattr(self, "_last_shadow_receipt", None),
                        current_boot_id=str(getattr(self, "boot_time", "") or ""),
                        now_ts=time.time(),
                    )
                    logger.info(
                        "recall_practice_status source=%s state=%s shadow_enabled=%s",
                        source,
                        _practice_state,
                        _shadow_status_enabled,
                    )
                elif _is_recall_status_query(text) and not _date_addressed_turn:
                    _status_last_receipt = getattr(self, "_last_recall_receipt", None)
                    _status_include_timestamp = _recall_status_query_wants_timestamp(text)
                    _status_carrier_reachable = bool(
                        _focused_cognition_enabled(
                            recall_stack_config=_recall_stack_config,
                        )
                        # TODO: remove source != "voice" when the voice carrier lands.
                        and source != "voice"
                    )
                    _recall_status_reply, _recall_status_state = _build_recall_status_reply(
                        triad_on=bool(_recall_stack_config.triad_on),
                        carrier_reachable_from_surface=_status_carrier_reachable,
                        last_receipt=_status_last_receipt,
                        current_boot_id=str(getattr(self, "boot_time", "") or ""),
                        now_ts=time.time(),
                        include_timestamp=_status_include_timestamp,
                    )
                    _log_recall_self_status(
                        source=source,
                        state=_recall_status_state.value,
                        triad_on=bool(_recall_stack_config.triad_on),
                        carrier_reachable=_status_carrier_reachable,
                        receipt=str(getattr(_status_last_receipt, "receipt", "none")),
                        timestamp_requested=_status_include_timestamp,
                    )
            except Exception as _status_exc:
                logger.debug("recall self-status intercept skipped: %s", _status_exc)

        try:
            from core.memory.identity import display_name as _identity_display_name
            from core.routing.identity_reply import (
                is_identity_question as _is_identity_question,
                render_identity_reply as _render_identity_reply,
            )

            if (
                _recall_status_reply is None
                and _is_identity_question(text)
                and not authoritative_tool_reply
                and not (web_context or "").strip()
            ):
                try:
                    _display = _identity_display_name() or "Rohit"
                except Exception:
                    _display = "Rohit"
                _identity_status_reply = _render_identity_reply(
                    display=_display,
                    linked_user=True,
                )
                logger.info(
                    "identity_status source=%s state=deterministic_shared",
                    source,
                )
        except Exception as _identity_status_exc:
            logger.debug(
                "identity status intercept skipped: %s",
                _identity_status_exc,
            )

        try:
            from core.routing.protected_refusal_followup import (
                protected_refusal_followup_reply as _protected_refusal_followup,
            )

            if (
                _recall_status_reply is None
                and _identity_status_reply is None
                and not authoritative_tool_reply
                and not (web_context or "").strip()
            ):
                _protected_refusal_followup_reply = _protected_refusal_followup(
                    text,
                    chat_history,
                )
                if _protected_refusal_followup_reply:
                    logger.info(
                        "protected_refusal_followup source=%s state=deterministic",
                        source,
                    )
        except Exception as _protected_refusal_exc:
            logger.debug(
                "protected refusal followup skipped: %s",
                _protected_refusal_exc,
            )

        try:
            from core.routing.recent_activity_status import (
                build_casual_presence_status_reply as _build_casual_presence_status_reply,
                build_recent_activity_status_reply as _build_recent_activity_status_reply,
                is_casual_presence_status_query as _is_casual_presence_status_query,
                is_recent_activity_status_query as _is_recent_activity_status_query,
            )

            if (
                _recall_status_reply is None
                and _is_casual_presence_status_query(text)
                and not authoritative_tool_reply
                and not (web_context or "").strip()
            ):
                _casual_presence_status_reply = _build_casual_presence_status_reply(
                    cycle_count=getattr(self, "cycle_count", None),
                )
                logger.info(
                    "casual_presence_status source=%s state=honest_empty class=state",
                    source,
                )
            elif (
                _recall_status_reply is None
                and _is_recent_activity_status_query(text)
                and not authoritative_tool_reply
                and not (web_context or "").strip()
            ):
                _recent_activity_status_reply = _build_recent_activity_status_reply(
                    cycle_count=getattr(self, "cycle_count", None),
                )
                logger.info(
                    "recent_activity_status source=%s state=honest_empty",
                    source,
                )
        except Exception as _activity_status_exc:
            logger.debug(
                "recent activity status intercept skipped: %s",
                _activity_status_exc,
            )

        if _recall_status_reply is not None:
            reply = _recall_status_reply
            _reply_path = ReplyPath.SELF_STATUS
        elif _identity_status_reply is not None:
            reply = _identity_status_reply
            _reply_path = ReplyPath.SELF_STATUS
        elif _protected_refusal_followup_reply is not None:
            reply = _protected_refusal_followup_reply
            _reply_path = ReplyPath.SELF_STATUS
        elif _casual_presence_status_reply is not None:
            reply = _casual_presence_status_reply
            _reply_path = ReplyPath.SELF_STATUS
        elif _recent_activity_status_reply is not None:
            reply = _recent_activity_status_reply
            _reply_path = ReplyPath.SELF_STATUS
        elif _reply_decision.mode is ReplyMode.TOOL:
            reply = authoritative_tool_reply
        elif _reply_decision.mode is ReplyMode.ECHO:
            reply = _current_turn_echo_reply
        elif _truly_empty_continuity_reply is not None:
            reply = _truly_empty_continuity_reply
            _reply_path = ReplyPath.LEGACY
            _focused_used = True
        elif _reply_decision.mode is ReplyMode.HONEST_EMPTY:
            from core.routing.focused_cognition import (
                build_honest_empty_reply as _build_honest_empty_reply,
                record_focused_cognition_run as _record_focused_cognition_run,
            )

            _hr = _build_honest_empty_reply(
                query=text,
                source=(_routing_obs_tool or "web"),
                surface=source,
            )
            reply = _hr.reply
            # Dedicated witness log: empty turns may have neither transcript nor
            # evidence directive, so the normal prompt-shape seam can be silent.
            logger.info(
                "honest_empty_reply surface=%s source=%s mode=%s "
                "call_purpose=honest_empty",
                source,
                _routing_obs_tool or "web",
                _hr.mode,
            )
            try:
                _record_focused_cognition_run(
                    surface=source,
                    chat_id=chat_id,
                    working_set=_hr.working_set,
                    result=_hr.result,
                    verdict=_hr.verdict,
                    legacy_prompt_chars=None,
                    fallback_reason=(
                        "honest_empty_deterministic"
                        if _hr.mode == "deterministic_fallback"
                        else None
                    ),
                    routing_observation_id=_legacy_routing_observation_id,
                )
            except Exception as _hee:
                logger.debug("honest_empty record skipped: %s", _hee)
        else:
            reply = None
            # Direction (b): a photo turn with a SUCCESSFUL local vision analysis
            # is synthesized over a BOUNDED working set (analysis + caption +
            # voice), NOT the full megaprompt — whose self-diagnostic
            # "Vision: Maez cannot see" block (web_interface.py:3588) overrode the
            # present analysis (witnessed 2026-06-07). This runs INSIDE
            # handle_message so the reply still flows through the strip / audit /
            # store / trace pipeline below. On empty/error it leaves reply=None
            # and falls through to the legacy synthesis (honest fallback).
            _photo_synth = None
            if photo_analysis:
                from core.routing.focused_cognition import (
                    photo_focused_synth_enabled as _photo_focused_synth_enabled,
                    synthesize_photo_turn as _synthesize_photo_turn,
                )

                if _photo_focused_synth_enabled():
                    _photo_synth = _synthesize_photo_turn
            if _photo_synth is not None:
                try:
                    _photo_result = _synthesize_photo_turn(
                        analysis_text=photo_analysis,
                        caption=text,
                        surface=source,
                        fresh_context=(
                            web_context
                            if _photo_freshness_query and web_context
                            else None
                        ),
                    )
                    _photo_reply = (_photo_result.reply or "").strip()
                except Exception as _photo_exc:
                    logger.warning("photo focused synthesis failed: %s", _photo_exc)
                    _photo_reply = ""
                if _photo_reply:
                    reply = _photo_reply
                    _focused_used = True
                    _reply_path = ReplyPath.FOCUSED
                    logger.info(
                        "photo_focused_synthesis surface=%s working_set_chars=%s "
                        "cited=%s reply_chars=%d receipt=%s turn_id=%s "
                        "contradiction_receipt=%s contradiction_claim_count=%s "
                        "contradictions=%s contradiction_latency_ms=%s "
                        "claim_limit_exceeded=%s contradiction_model_id=%s "
                        "contradiction_revision=%s contradiction_sha256=%s",
                        source,
                        getattr(_photo_result, "working_set_chars", "?"),
                        len(getattr(_photo_result, "cited_ids", []) or []),
                        len(reply),
                        getattr(_photo_result, "receipt_reason", None),
                        _user_msg_turn_id,
                        getattr(_photo_result, "contradiction_receipt", None),
                        getattr(_photo_result, "contradiction_claim_count", 0),
                        getattr(_photo_result, "contradiction_count", 0),
                        getattr(_photo_result, "contradiction_latency_ms", None),
                        getattr(
                            _photo_result,
                            "contradiction_claim_limit_exceeded",
                            False,
                        ),
                        getattr(_photo_result, "contradiction_model_id", None),
                        getattr(_photo_result, "contradiction_revision", None),
                        getattr(_photo_result, "contradiction_sha256", None),
                    )
            if not _focused_used and _reply_decision.mode is ReplyMode.FOCUSED:
                _focused_started = time.monotonic()
                try:
                    from core.routing.focused_cognition import (
                        assemble_working_set as _assemble_working_set,
                        check_groundedness as _check_groundedness,
                        focused_synthesize as _focused_synthesize,
                        record_focused_cognition_run as _record_focused_cognition_run,
                    )

                    _focused_working_set = _assemble_working_set(
                        transcript=transcript,
                        web_context=web_context,
                        owner_question=text,
                        chat_history=chat_history,
                        recall_items=recall_items,
                    )
                    if _date_addressed_turn and _focused_working_set is not None:
                        _recall_carrier_receipt = RECALL_CARRIER_CONSULTED
                        _arm_recall_receipt()
                    if (
                        _focused_working_set is None
                        and _dialogue_needs_or_uncertain
                    ):
                        logger.info(
                            "focused_cognition_skip surface=%s "
                            "reason=continuity_no_dialogue_anchor",
                            source,
                        )
                    if _focused_working_set is not None:
                        _legacy_prompt_chars = sum(
                            len(str(message.get("content") or ""))
                            for message in messages
                            if isinstance(message, dict)
                        )
                        _log_focused_cognition_prompt_shape(
                            surface=source,
                            working_set=_focused_working_set,
                            legacy_prompt_chars=_legacy_prompt_chars,
                        )
                        try:
                            _focused_result = _focused_synthesize(
                                _focused_working_set,
                                surface=source,
                                date_addressed=_date_addressed_turn,
                                legacy_prompt_chars=_legacy_prompt_chars,
                                turn_kind=_rk_turn_kind,
                            )
                            logger.info(
                                "focused_synthesis_timing prompt_build_ms=%s "
                                "chat_total_ms=%s reply_token_est=%s "
                                "working_set_chars=%s evidence_item_count=%s "
                                "citation_render_version=%s turn_kind=%s",
                                getattr(_focused_result, "prompt_build_ms", None),
                                getattr(_focused_result, "chat_total_ms", None),
                                getattr(_focused_result, "reply_token_est", None),
                                getattr(_focused_working_set, "working_set_chars", None),
                                len(getattr(_focused_working_set, "items", ()) or ()),
                                getattr(
                                    _focused_working_set,
                                    "citation_render_version",
                                    None,
                                ),
                                _rk_turn_kind,
                            )
                        finally:
                            _close_receipt_watchdog()
                        _focused_verdict = _check_groundedness(
                            _focused_result,
                            _focused_working_set,
                        )
                        try:
                            from core.cognition.grounding_shadow import (
                                evidence_map_from_working_set as _focused_support_map,
                            )

                            _focused_support_evidence_map = _focused_support_map(
                                _focused_working_set
                            )
                        except Exception:
                            _focused_support_evidence_map = {}
                        from core.routing.recall_outcome import (
                            citation_support as _citation_support,
                        )

                        _rk_support = _citation_support(
                            _focused_result,
                            _focused_working_set,
                            turn_kind=_rk_turn_kind,
                        )
                        _rk_cited_grounded = _rk_support == "grounded"
                        _rk_cited_mixed = _rk_support == "mixed"
                        _rk_unmatched = len(getattr(_focused_verdict, "unmatched", []) or [])
                        _rk_coverage = getattr(_focused_verdict, "citation_coverage", None)
                        _rk_reply_grounding = getattr(_focused_verdict, "reply_grounding", None)
                        _focused_reply = (_focused_result.reply or "").strip()
                        _record_focused_cognition_run(
                            surface=source,
                            chat_id=chat_id,
                            working_set=_focused_working_set,
                            result=_focused_result,
                            verdict=_focused_verdict,
                            legacy_prompt_chars=_legacy_prompt_chars,
                            fallback_reason=None if _focused_reply else "empty_focused_reply",
                            routing_observation_id=_legacy_routing_observation_id,
                        )
                        if _focused_reply:
                            reply = _focused_reply
                            _focused_used = True
                            _focused_answer_used = True
                except Exception as _focused_exc:
                    if (
                        _date_addressed_turn
                        and _recall_carrier_receipt != RECALL_CARRIER_CONSULTED
                    ):
                        _recall_carrier_receipt = RECALL_CARRIER_CONSULT_FAILED
                    if _date_addressed_turn:
                        logger.warning(
                            "focused cognition failed on dated recall, using "
                            "deterministic dated honesty: %s",
                            _focused_exc,
                        )
                    else:
                        logger.warning(
                            "focused cognition failed, falling back to megaprompt: %s",
                            _focused_exc,
                        )
                    try:
                        from core.routing.focused_cognition import (
                            record_focused_cognition_run as _record_focused_cognition_run,
                        )

                        _legacy_prompt_chars = sum(
                            len(str(message.get("content") or ""))
                            for message in messages
                            if isinstance(message, dict)
                        )
                        _record_focused_cognition_run(
                            surface=source,
                            chat_id=chat_id,
                            working_set=_focused_working_set,
                            result=None,
                            verdict=None,
                            legacy_prompt_chars=_legacy_prompt_chars,
                            fallback_reason="focused_call_error",
                            routing_observation_id=_legacy_routing_observation_id,
                        )
                    except Exception:
                        pass
                finally:
                    _close_receipt_watchdog()
                    _rk_focused_elapsed = int((time.monotonic() - _focused_started) * 1000)

            if _date_addressed_turn and not _focused_used and reply is None:
                _had_confirmed = _focused_working_set_had_confirmed(_focused_working_set)
                _dated_reply_kind = _dated_denial_kind(
                    carrier_receipt=_recall_carrier_receipt,
                    had_confirmed=_had_confirmed,
                )
                _dated_denial_kind_for_turn = _dated_reply_kind
                _log_dated_recall_denial(
                    source=source,
                    reply_mode=_reply_decision.mode,
                    recall_stack_config=_recall_stack_config,
                    date_addressed=_date_addressed_turn,
                    carrier_receipt=_recall_carrier_receipt,
                    had_confirmed=_had_confirmed,
                    reply_kind=_dated_reply_kind,
                )
                reply = _dated_denial_reply(
                    carrier_receipt=_recall_carrier_receipt,
                    had_confirmed=_had_confirmed,
                )
                _focused_used = True
                _reply_path = ReplyPath.DATED_HONESTY

            if not _focused_used:
                try:
                    # Session 11r: via llm_client (was missed in 11p batch)
                    from core import llm_client as _llm_client
                    from core.routing.brain_gateway import with_purpose as _brain_purpose

                    with _brain_purpose("owner_reply"):
                        response = _llm_client.chat(
                            model=MODEL,
                            messages=_plain_llm_messages(messages),
                            think=False,
                            options={"temperature": 0.7, "num_predict": 4096},
                        )
                    reply = (response.message.content or "").strip() or "(no response)"
                    _reply_path = ReplyPath.LEGACY
                    if _focused_candidate and (transcript_context or evidence_directive):
                        _log_daemon_system_part_shape(
                            surface=source,
                            call_purpose="llm_synthesis",
                            system_parts=system_part_capture,
                        )
                        _log_daemon_prompt_payload_shape(
                            surface=source,
                            call_purpose="llm_synthesis",
                            messages=messages,
                            transcript_context=transcript_context,
                            evidence_directive=evidence_directive,
                        )
                except Exception as e:
                    try:
                        from core.error_classifier import (
                            classify as _classify_backend_error,
                            emit_telemetry as _emit_backend_error,
                            owner_visible_message,
                        )

                        _classified_error = _classify_backend_error(e)
                        _emit_backend_error(_classified_error, surface="telegram_chat")
                        reply = owner_visible_message(_classified_error)
                        logger.error(
                            "telegram chat synthesis failed (%s): %s",
                            _classified_error.error_class.value,
                            e,
                        )
                    except Exception:
                        logger.exception("telegram chat synthesis failed")
                        reply = "I hit a local brain error while answering. Try me again in a moment."

        # 2026-04-23 Commit 7b: strip tool-call JSON leaks from the raw
        # model output BEFORE audit and BEFORE store. Models occasionally
        # leak <tool_call>...</tool_call> or inline JSON into the final
        # reply text even when the tool-use loop has already run. These
        # leaks are wire-format noise; the owner shouldn't see them and
        # memory shouldn't store them. Previously this cleanup ran in the
        # adapter AFTER handle_message had already returned — meaning
        # stored memory contained the raw JSON even though the owner
        # saw cleaned text. Moving it here makes
        #     stored text == audited text == text returned to caller.
        try:
            from core.brain_loop import strip_tool_call_leaks

            reply = strip_tool_call_leaks(reply)
        except Exception as _strip_exc:
            logger.debug("tool-call-leak strip skipped: %s", _strip_exc)

        # Slice 2 Session 2 — Wondering-Pursuit. Optionally append a
        # proactive utterance BEFORE the audit pass so any LLM-authored
        # wondering content gets screened for fabrication / self-claim
        # leaks via the same audit gate that screens the synthesis
        # reply (audit B1 fix from 2026-04-29 review). The wondering
        # question is LLM-authored by ``daemon/wondering_cycle.py``
        # and stored in SQLite verbatim; treating it as untrusted text
        # at the surface boundary is the only honest path. Lai et al.
        # 2024 (arxiv 2410.12361) framework + Conway 2000 working-self
        # priors; Maez-specific safety: vulnerable-register hard-block
        # is primary, frequency budget across daemon restart via
        # sidecar at ``memory/last_pursuit.json``.
        #
        # Two gates, both must pass:
        #   1. ``MAEZ_WONDERING_PURSUIT=1`` env knob (default OFF —
        #      brand-new path, opt-in until probe-validated).
        #   2. ``identity.proactive_messages()`` policy — bonded shape
        #      requires explicit operator opt-in via per-user policy.
        #
        # Tri-state outcome on the trace (audit M2 fix):
        # ``surface`` (utterance appended), ``hold`` (evaluated but
        # threshold or hard-block held silent), ``errored`` (evaluation
        # raised — distinguish from legitimate hold for observability).
        # Failure is silent at the reply level: any exception leaves
        # the reply untouched and synthesis continues.
        _pursuit_enabled = os.environ.get("MAEZ_WONDERING_PURSUIT", "0") == "1"
        _pursuit_decision = None
        _pursuit_evaluated = False
        _pursuit_error: "str | None" = None
        _pursuit_w_store = None  # captured for record_pursuit below
        _pursuit_delivery_ledger = None
        _pursuit_delivery_dispatch_id = None
        _pursuit_delivery_text = None
        if _pursuit_enabled:
            try:
                from core.memory import identity as _identity_mod

                if _identity_mod.proactive_messages():
                    from core.evolution.wonderings import (
                        get_store as _get_w_store,
                    )

                    _pursuit_w_store = _get_w_store()
                    _open_wonderings = _pursuit_w_store.list_open(limit=10) or []
                    _pursuit_decision = decide_pursuit(
                        _open_wonderings,
                        goals=_goals if _goals is not None else GoalHierarchy(),
                        recent_owner_text=text,
                        last_pursuit_at=load_last_pursuit_at(),
                    )
                    _pursuit_evaluated = True
                    if _pursuit_decision is not None:
                        _utterance = format_pursuit_utterance(_pursuit_decision)
                        if _utterance:
                            from core.policies.diagnostics import (
                                DriveCuriosityDiagnosticSink,
                                emit_diagnostic_best_effort,
                            )

                            _drive_curiosity_diagnostics = DriveCuriosityDiagnosticSink()

                            def _extraction_diagnostic_sink(event: dict) -> None:
                                emit_diagnostic_best_effort(
                                    _drive_curiosity_diagnostics,
                                    event,
                                    logger=logger,
                                )
                                logger.info(
                                    "curiosity_extraction_gate %s",
                                    json.dumps(event, sort_keys=True),
                                )

                            _extraction_ledger = OutreachLedger()
                            _extraction_now = datetime.now(timezone.utc)
                            _extraction_decision = evaluate_extraction_gate(
                                _utterance,
                                bond_id="firstborn",
                                priority_class=PriorityClass.SELF_GROWTH,
                                lane=OutreachLane.OWNER_INTERRUPTING,
                                outreach_ledger=_extraction_ledger,
                                now_utc=_extraction_now,
                                diagnostic_sink=_extraction_diagnostic_sink,
                                reflection_audit=ReflectionAudit(
                                    object_id=(
                                        f"wondering-pursuit:"
                                        f"{_pursuit_decision.wondering_id}"
                                    ),
                                    bond_id="firstborn",
                                    reflection_utc=_extraction_now,
                                    can_resolve_interiorly=False,
                                    is_owner_likely_available=True,
                                    is_worth_interrupting=True,
                                    is_extraction_shaped=False,
                                    decision=ReflectionDecision.PROCEED,
                                    reasoning_digest="hmac-sha256:" + "0" * 64,
                                    owner_response=None,
                                ),
                            )
                            if _extraction_decision.decision in {"allow", "rephrase"}:
                                _pursuit_delivery_text = _extraction_decision.rendered_text
                                _dispatch_id = _extraction_ledger.record_dispatch(
                                    bond_id="firstborn",
                                    dispatched_utc=_extraction_now,
                                    priority_class=PriorityClass.SELF_GROWTH.value,
                                    owner_state_at_dispatch=OwnerState.AVAILABLE,
                                    signal_quality=SignalQuality.HIGH,
                                    importance=float(_pursuit_decision.proactive_score),
                                    decision="allow",
                                )
                                _pursuit_delivery_ledger = _extraction_ledger
                                _pursuit_delivery_dispatch_id = _dispatch_id
                                reply = f"{reply}\n\n{_pursuit_delivery_text}"
                            else:
                                _pursuit_decision = None
            except Exception as _pursuit_exc:
                logger.debug("wondering-pursuit evaluation failed: %s", _pursuit_exc)
                _pursuit_decision = None
                _pursuit_error = str(_pursuit_exc)[:200]

        # 2026-04-23 memory-integrity contract: audit BEFORE store + return.
        # See core/safety/audited_output.py for the full invariant.
        # `transcript` is the caller's Jarvis tool-use transcript if a
        # tool loop ran; `in_tool_continuation` is derived from it.
        # Trace: snapshot the pre-audit text so audit.changed_output
        # is a literal pre/post hash comparison, not a guess.
        _trace_pre_audit_text = reply
        _grounding_shadow_post_audit_ready = False
        try:
            from core.safety.audited_output import audit_assistant_text

            reply = audit_assistant_text(
                reply,
                surface=source,
                transcript=transcript,
                signals_present=_chat_signals_present,
                signals_absent=_chat_signals_absent,
                evidence_envelope=_evidence_envelope,
                semantic_self_claim_skip_reason=(
                    "deterministic_self_status"
                    if _reply_path is ReplyPath.SELF_STATUS
                    else None
                ),
            )
            _grounding_shadow_post_audit_ready = True
            try:
                _trace.audit = AuditInfo(
                    ran=True,
                    changed_output=(
                        _trace_hash_text(_trace_pre_audit_text) != _trace_hash_text(reply)
                    ),
                )
            except Exception as _trace_exc:
                logger.debug("trace audit capture skipped: %s", _trace_exc)
        except Exception as _aud_exc:
            logger.warning("handle_message audit fail-open: %s", _aud_exc)
            try:
                _trace.audit = AuditInfo(ran=False, error=str(_aud_exc)[:200])
            except Exception:
                pass
        reply = self._trf_apply_fragment_guard(
            user_message=text,
            reply=reply,
            temporal_anchor_result=_temporal_anchor_result,
            trace=_trace,
        )
        _gate_receipt = None
        try:
            if (
                _grounding_shadow_post_audit_ready
                and _focused_used
                and _focused_support_evidence_map
            ):
                reply, _gate_receipt = _run_support_scope(
                    reply,
                    _focused_working_set,
                    _focused_support_evidence_map,
                    surface=source,
                    boot_id=os.environ.get("MAEZ_BOOT_ID"),
                    shadow_id=uuid.uuid4().hex,
                    ts=int(time.time()),
                )
                # Shadow sense shares this post-audit block with _run_support_scope; the
                # coupling is incidental — any trusted-memory↔fresh turn populates the
                # support evidence map, so no in-scope turn is dropped.
                if _focused_working_set is not None:
                    _run_mem_fresh_conflict_sense(_focused_working_set, surface=source)
        except Exception as _grounding_shadow_exc:
            logger.debug(
                "focused grounding shadow/gate skipped: %s",
                _grounding_shadow_exc,
            )
        if os.environ.get("MAEZ_ROUTING_QUALITY_WRITEBACK") == "1" and _legacy_routing_observation_id:
            try:
                _cav = int((_gate_receipt or {}).get("caveated_unsupported", 0))
                _q, _sig = _routing_quality_from_gate(
                    caveated_unsupported=_cav,
                    web_quality=_wb_web_quality,
                    result_count=_wb_result_count,
                )
                if _q is not None:
                    _routing_turn_outcome_quality = _q
                    from core.routing.observation import _default_store

                    _default_store().attach_post_turn_quality(
                        _legacy_routing_observation_id,
                        outcome_quality=_q,
                        post_turn_signal=_sig,
                    )
            except Exception as _wbe:
                logger.debug("routing quality write-back skipped: %s", _wbe)
        if _veto_ledger_enabled() and _override_event_id is not None \
           and _routing_turn_outcome_quality is not None:
            try:  # seam 3: classify the lifted veto ONLY from a real outcome
                _ledger = _veto_ledger_get(_ledger)
                _ledger.attach_reask_outcome(
                    _override_event_id, reask_turn_id=_user_msg_turn_id,
                    reask_outcome_quality=_routing_turn_outcome_quality)
            except Exception as _ce:
                logger.debug("veto reask classify skipped: %s", _ce)
        try:
            from core.routing.recall_outcome import RecallOutcome, classify_outcome
            from core.routing.recall_receipt import (
                RECEIPT_AFTER_MS,
                resolve_ack_status,
            )
            from core.routing.recall_self_status import RecallStatusReceipt
            from core.routing.recall_shadow import compute_shadow_pair_id

            if _receipt_after_ms is None:
                _receipt_after_ms = RECEIPT_AFTER_MS
            if not _focused_answer_used:
                _rk_cited_grounded = False
                _rk_cited_mixed = False
                _rk_unmatched = 0
                _rk_coverage = None
                _rk_reply_grounding = None
                _rk_focused_elapsed = None
            _rk_mode = "recall_triad" if _recall_stack_config.triad_on else "legacy"
            if _recall_stack_config.triad_on and _focused_working_set is not None:
                _had_confirmed = _focused_working_set_had_confirmed(
                    _focused_working_set
                )
            _rk_legacy_absence = (
                _rk_mode == "legacy"
                and _rk_turn_kind != "ordinary"
                and _reply_asserts_dated_absence(reply)
            )
            if (
                _rk_mode == "recall_triad"
                and _date_addressed_turn
                and _reply_asserts_dated_absence(reply)
                and not _rk_cited_grounded
            ):
                _dated_denial_kind_for_turn = "no_dated_memory"
            _rk_answered = bool(reply) and not _is_dated_denial_reply(reply) and not (
                _rk_turn_kind != "ordinary"
                and _reply_asserts_dated_absence(reply)
                and not _rk_cited_grounded
            )
            _rk_outcome = classify_outcome(
                mode=_rk_mode,
                turn_kind=_rk_turn_kind,
                answered=_rk_answered,
                receipt=(
                    _recall_carrier_receipt
                    if _recall_stack_config.triad_on
                    else "na"
                ),
                denial_kind=_dated_denial_kind_for_turn,
                had_confirmed=_had_confirmed if _recall_stack_config.triad_on else None,
                cited_grounded_context=_rk_cited_grounded,
                unmatched_citations=_rk_unmatched,
                asserts_absence=_rk_legacy_absence,
                cited_mixed_support=_rk_cited_mixed,
            )
            if _recall_stack_config.triad_on and _date_addressed_turn:
                self._last_recall_receipt = RecallStatusReceipt(
                    receipt=_recall_carrier_receipt,
                    at_ts=time.time(),
                    boot_id=str(getattr(self, "boot_time", "") or ""),
                )
            _shadow_should_attempt = bool(
                _recall_shadow_enabled()
                and _date_addressed_turn
                and not _recall_stack_config.triad_on
            )
            _recall_shadow_attempt = _shadow_should_attempt
            _shadow_pair_id = (
                compute_shadow_pair_id(
                    boot_id=str(getattr(self, "boot_time", "") or ""),
                    trace_id=getattr(_trace, "trace_id", None),
                )
                if _shadow_should_attempt
                else "na"
            )
            _receipt_snapshot = (
                _receipt_box.snapshot(now_mono=time.monotonic())
                if _receipt_box is not None
                else None
            )
            _turn_elapsed_ms = int((time.monotonic() - _turn_started_mono) * 1000)
            _receipt_ack_required = bool(
                _receipt_eligible_for_turn
                and _receipt_after_ms is not None
                and _turn_elapsed_ms >= _receipt_after_ms
            )
            _receipt_send_result = (
                _receipt_snapshot.send_result if _receipt_snapshot is not None else None
            )
            _receipt_fired = bool(
                _receipt_snapshot is not None and _receipt_snapshot.fired
            )
            _receipt_ack_status = resolve_ack_status(
                eligible=_receipt_eligible_for_turn,
                fired=_receipt_fired,
                send_result=_receipt_send_result,
                disabled=not _recall_receipt_enabled(),
                ack_required=_receipt_ack_required,
            )
            _receipt_ack_emit_ms = (
                _receipt_snapshot.ack_emit_ms
                if _receipt_snapshot is not None and _receipt_snapshot.send_result == "ok"
                else None
            )
            _recall_outcome_rec = RecallOutcome(
                mode=_rk_mode,
                turn_kind=_rk_turn_kind,
                outcome_class=_rk_outcome,
                denial_kind=_dated_denial_kind_for_turn,
                had_confirmed=(
                    _had_confirmed if _recall_stack_config.triad_on else None
                ),
                citation_coverage=_rk_coverage,
                reply_grounding=_rk_reply_grounding,
                receipt_or_na=(
                    _recall_carrier_receipt
                    if _recall_stack_config.triad_on
                    else "na"
                ),
                latency_ms=int((time.time() - _trace_t_start) * 1000),
                focused_elapsed_ms=_rk_focused_elapsed,
                reply_path=_reply_path,
                shadow_pair_id=_shadow_pair_id,
                receipt_eligible=_receipt_eligible_for_turn,
                receipt_after_ms=_receipt_after_ms,
                ack_required=_receipt_ack_required,
                ack_status=_receipt_ack_status,
                ack_emit_ms=_receipt_ack_emit_ms,
            )
            _log_recall_outcome(
                rec=_recall_outcome_rec
            )
        except Exception as _recall_outcome_exc:
            logger.warning(
                "recall_outcome_emit_failed error_class=%s",
                type(_recall_outcome_exc).__name__,
            )
        if (
            _pursuit_delivery_ledger is not None
            and _pursuit_delivery_dispatch_id is not None
            and _pursuit_delivery_text
        ):
            if _pursuit_delivery_text in reply:
                try:
                    _pursuit_delivery_ledger.mark_delivered(
                        _pursuit_delivery_dispatch_id,
                        delivered_utc=datetime.now(timezone.utc),
                    )
                except Exception as _pursuit_delivery_exc:
                    logger.debug("pursuit delivery mark failed: %s", _pursuit_delivery_exc)
                    reply = reply.replace(_pursuit_delivery_text, "", 1)
                    _pursuit_decision = None
                else:
                    try:
                        save_last_pursuit_at(
                            time.time(),
                            wondering_id=_pursuit_decision.wondering_id,
                        )
                    except Exception as _pursuit_sidecar_exc:
                        logger.debug("save_last_pursuit_at failed: %s", _pursuit_sidecar_exc)
            else:
                _pursuit_decision = None

        # Search-as-a-Sense v0.1: drain the dispatcher turn evidence here,
        # where memory and the final audit->store->send invariant are owned.
        # Order is intentional: write the bounded observation, retain the
        # marked audited draft for /receipts, then natural-render the stored
        # and sent reply.
        try:
            from core.search.sense_flag import page_read_enabled, sense_enabled
            from core.routing.attribution_render import (
                pop_turn_evidence,
                render_natural,
                retain_receipt,
            )

            if sense_enabled() or page_read_enabled():
                _turn_ev = pop_turn_evidence(chat_id)
                if _turn_ev.get("observation"):
                    _observation = dict(_turn_ev["observation"])
                    if _observation.pop("kind", None) == "page_read":
                        from core.intake_bus.world_observation_lane import (
                            write_page_observation,
                        )

                        write_page_observation(self.memory, **_observation)
                    else:
                        from core.intake_bus.world_observation_lane import (
                            write_world_observation,
                        )

                        write_world_observation(self.memory, **_observation)
                retain_receipt(
                    str(chat_id or ""),
                    marked=reply,
                    sources=_turn_ev.get("sources") or [],
                    observation=_turn_ev.get("observation"),
                )
                try:
                    from core.cognition.evidence_precedence_shadow import (
                        observe_marked_draft,
                    )

                    observe_marked_draft(
                        reply,
                        surface=source,
                        fresh_indices=_turn_ev.get("fresh_indices"),
                        web_present=bool(_turn_ev.get("web_present")),
                    )
                except Exception:
                    pass
                reply = render_natural(
                    reply,
                    web_evidence_present=bool(_turn_ev.get("web_present")),
                )
        except Exception:
            pass

        # Slice 2 Session 3: record the surface decision in the
        # wonderings store + emit a lived episode (ADR 0019
        # alignment — proactive surfaces are high-signal moments
        # that future reflection should be able to cite). Both are
        # best-effort; failures must not break the reply path.
        if _pursuit_w_store is not None and _pursuit_decision is not None:
            try:
                _pursuit_w_store.record_pursuit(
                    _pursuit_decision.wondering_id,
                    decision="surface",
                    score=_pursuit_decision.proactive_score,
                    components=dict(_pursuit_decision.components),
                )
            except Exception as _record_exc:
                logger.debug("record_pursuit (surface) failed: %s", _record_exc)
            try:
                # Lived-episode emission — ``source_kind="pursuit_surface"``
                # so the lived-recall layer can later surface "Maez
                # surfaced wondering X to owner at time T" as
                # episode-shaped evidence. Conway 2000: reflection-
                # on-action is part of self-memory.
                self.lived_episodes.add(
                    title=f"Surfaced wondering #{_pursuit_decision.wondering_id}",
                    summary=_pursuit_decision.wondering_question[:500],
                    participants=["Maez"],
                    source_memory_ids=[
                        f"pursuit-{_pursuit_decision.wondering_id}-{int(time.time())}",
                    ],
                    source_kind="pursuit_surface",
                    importance=3,
                )
            except Exception as _ep_exc:
                logger.debug(
                    "pursuit-surface episode emission failed: %s",
                    _ep_exc,
                )

        # Slice 4c.5a — autobiographical continuity turning on.
        # Persist the post-audit owner-private reply as a model_reply row.
        # This is best-effort shadow persistence: the user-facing reply
        # still returns if the ledger is disabled or unavailable.
        from core.ledger.model_reply_persistence_warning import (
            warn_model_reply_persistence_skip,
        )

        try:
            from core.ledger.model_reply_persistence import (
                build_model_reply_audit_verdict,
                persist_model_reply,
            )

            if getattr(_trace.audit, "ran", False):
                persist_model_reply(
                    db_path=str(LEDGER_DB_PATH),
                    raw_text=reply,
                    surface=source,
                    parent_turn_id=_user_msg_turn_id,
                    model_id=MODEL,
                    prompt_material={
                        "messages": messages,
                        "surface": source,
                        "event": "autobiographical_continuity_turning_on",
                    },
                    soul_material=getattr(self, "system_prompt", ""),
                    evidence_envelope=_evidence_envelope,
                    audit_verdict=build_model_reply_audit_verdict(
                        surface=source,
                        audit_ran=True,
                        changed_output=bool(getattr(_trace.audit, "changed_output", False)),
                    ),
                    memory_read_ids=list(getattr(_trace, "lived_recall_ids", []) or []),
                )
        except Exception as _ledger_reply_exc:
            warn_model_reply_persistence_skip(
                "daemon-handle-message",
                "model_reply ledger persistence skipped: %s",
                _ledger_reply_exc,
            )

        # Tri-state pursuit trace capture (audit M2 fix). The earlier
        # version recorded "hold" on every error path, conflating
        # evaluator-returned-None (legitimate hold) with
        # evaluator-raised-exception (errored). Now distinguished:
        #   - surface  : pursuit fired, utterance appended
        #   - hold     : pursuit evaluated, returned None
        #   - errored  : pursuit raised — observability sees the failure
        #   - ""       : pursuit not run (env disabled)
        try:
            if _pursuit_decision is not None:
                _trace.pursuit_decision = "surface"
                _trace.pursuit_score = float(_pursuit_decision.proactive_score)
                _trace.pursuit_question = _pursuit_decision.wondering_question[:200]
                _trace.pursuit_components = dict(_pursuit_decision.components)
            elif _pursuit_error is not None:
                _trace.pursuit_decision = "errored"
            elif _pursuit_enabled and _pursuit_evaluated:
                _trace.pursuit_decision = "hold"
        except Exception as _trace_pursuit_exc:
            logger.debug("trace pursuit capture skipped: %s", _trace_pursuit_exc)

        # Step 5v — single structured log line per chat turn.
        # Captures what reached the prompt (lived_brief / ambient
        # block sizes) alongside the response shape so journal-grep
        # can answer "did the substrate help?" across many turns
        # without re-running the prompt assembly. Mirrors the
        # _log_expansion_fired shape from Step 5q for greppability.
        # Reply is post-canary-scrub + post-protected-command-scrub
        # at this point; 60-char excerpt is safe for journalctl.
        try:
            _reply_excerpt = (reply or "")[:60]
            if len(reply or "") > 60:
                _reply_excerpt = _reply_excerpt[:59] + "…"
            _user_excerpt = (text or "")[:60]
            if len(text or "") > 60:
                _user_excerpt = _user_excerpt[:59] + "…"
            logger.info(
                "chat_turn handled "
                "source=%s len_user=%d len_lived_brief=%d "
                "len_ambient_block=%d len_reply=%d "
                "user_excerpt=%r reply_excerpt=%r",
                source,
                len(text or ""),
                len(_lived_brief or ""),
                len(_ambient_block or ""),
                len(reply or ""),
                _user_excerpt,
                _reply_excerpt,
            )
        except Exception as _log_exc:
            logger.debug("chat_turn log line failed: %s", _log_exc)

        # 5x.B Pass 1: stored as user_utterance/lived because the
        # exchange is bond transcript. NOTE: the combined string carries
        # both owner text and Maez reply — 5x.D should treat consolidations
        # of this row as mixed-origin, not pure owner-verbatim.
        #
        # Self-web-claim hygiene (behind MAEZ_SELF_CLAIM_HYGIENE_ENABLED):
        # on web-grounded turns, split the store into two LINKED records so
        # Maez's reply lands untrusted under self_web_claim WITHOUT the owner's
        # words inheriting that downgrade, and WITHOUT writing the combined row
        # (no duplicate). The web-grounded signal is the fresh subset of the
        # evidence-state marker labels (web_context is empty on the dispatcher
        # path, so bool(web_context.strip()) would be wrong here).
        _self_claim_hygiene = strict_env_flag("MAEZ_SELF_CLAIM_HYGIENE_ENABLED")
        _web_grounded = bool(
            WEB_GROUNDED_LABELS & set(_evidence_state.marker_labels)
        )
        _specs = decide_turn_storage(
            source=source,
            text=text,
            reply=reply,
            web_grounded=_web_grounded,
            hygiene_enabled=_self_claim_hygiene,
        )
        _m1_raw_memory_id = None
        _reply_memory_id = None
        for _spec in _specs:
            _stored_id = self.memory.store_telegram(
                _spec.content,
                provenance_source=_spec.provenance_source,
                trust_tier=_spec.trust_tier,
                turn_link_id=_spec.turn_link_id,
            )
            if _spec.is_owner_record:
                _m1_raw_memory_id = _stored_id
            else:
                _reply_memory_id = _stored_id
        # Defense-in-depth: funnel the owner id through the owner-id-only guard so the
        # self_web_claim reply id can NEVER enter a lived episode's source_memory_ids.
        _m1_raw_memory_id = m1_raw_memory_id_for_promotion(
            owner_id=_m1_raw_memory_id, reply_id=_reply_memory_id,
        )
        if len(_specs) == 2:
            logger.info(
                "self_claim_stored web_grounded=True provenance=self_web_claim "
                "trust_tier=untrusted reply_chars=%d turn_link_id=%s",
                len(reply or ""), _specs[1].turn_link_id,
            )
        try:
            if (
                source in M1_ALLOWED_PROMOTION_SOURCES
                and getattr(self, "m1_promoter", None) is not None
            ):
                with self._m1_lock:
                    _m1_outcome = self.m1_promoter.consider_audited_exchange(
                        owner_text=text,
                        maez_reply=reply,
                        raw_memory_id=_m1_raw_memory_id,
                        occurred_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    )
                if _m1_outcome.promoted:
                    logger.info(
                        "m1.promotion.succeeded trigger=turn_close source_count=%d episode_id=%s",
                        _m1_outcome.source_id_count,
                        _m1_outcome.episode_id,
                    )
                elif _m1_outcome.skipped_reason and _m1_outcome.skipped_reason != "disabled":
                    logger.info(
                        "m1.promotion.skipped_%s trigger=turn_close",
                        _m1_outcome.skipped_reason,
                    )
        except Exception as _m1_exc:
            logger.debug("m1 turn-close promotion failed-neutral: %s", _m1_exc)
        self._ws_broadcast({"type": "message_reply", "text": reply})

        # Trace harness Slice 1 — finalize and emit the trace before
        # returning. Three hashes are recorded so the audit-before-
        # store invariant (stored == sent == final) is *inspectable*:
        # equal hashes confirm; unequal hashes are a real signal for
        # the future deterministic harness. Never raises.
        try:
            _trace.tool_calls = [
                ToolCall(**tc) if isinstance(tc, dict) else tc for tc in (tool_calls or [])
            ]
            _final_hash = _trace_hash_text(reply)
            _trace.final_text_hash = _final_hash
            _trace.final_text_excerpt = (reply or "")[:500]
            # Owner-bridge /message: the reply is sent (returned to
            # caller for surface delivery) and stored (via
            # store_telegram above) verbatim. Same hash for all three
            # confirms the invariant held this turn.
            _trace.sent_text_hash = _final_hash
            _trace.stored_text_hash = _final_hash
            _trace.latency_ms = int((time.time() - _trace_t_start) * 1000)
            _trace.terminal_state = "errored" if reply.startswith("Error: ") else "replied"
            default_writer().write(_trace)
        except Exception as _trace_exc:
            logger.warning("trace emission failed (skipping): %s", _trace_exc)

        if (
            _recall_outcome_rec is not None
            and _recall_shadow_attempt
        ):
            _shadow_boot_id = str(getattr(self, "boot_time", "") or "")
            try:
                from core.routing.recall_shadow import ShadowSkip, derive_shadow_skipped

                _shadow_submitted = self._ensure_recall_shadow_worker().submit(
                    lambda: self._run_recall_shadow(
                        text=text,
                        legacy_rec=_recall_outcome_rec,
                        date_addressed=bool(_date_addressed_turn),
                        shadow_pair_id=_recall_outcome_rec.shadow_pair_id,
                        boot_id=_shadow_boot_id,
                    )
                )
                if not _shadow_submitted:
                    _shadow_skip = derive_shadow_skipped(
                        legacy_rec=_recall_outcome_rec,
                        skip_reason=ShadowSkip.QUEUE_FULL,
                        shadow_pair_id=_recall_outcome_rec.shadow_pair_id,
                        latency_delta_ms=0,
                        ts=int(time.time()),
                        boot_id=_shadow_boot_id,
                    )
                    _log_shadow_outcome(rec=_shadow_skip)
                    self._record_last_shadow_receipt(_shadow_skip)
            except Exception as _shadow_submit_exc:
                try:
                    from core.routing.recall_shadow import ShadowSkip, derive_shadow_skipped

                    _shadow_skip = derive_shadow_skipped(
                        legacy_rec=_recall_outcome_rec,
                        skip_reason=ShadowSkip.EXCEPTION,
                        shadow_pair_id=_recall_outcome_rec.shadow_pair_id,
                        latency_delta_ms=0,
                        ts=int(time.time()),
                        boot_id=_shadow_boot_id,
                    )
                    _log_shadow_outcome(rec=_shadow_skip)
                    self._record_last_shadow_receipt(_shadow_skip)
                except Exception as _shadow_skip_exc:
                    logger.warning(
                        "recall_shadow_submit_skip_log_failed class=%s",
                        type(_shadow_skip_exc).__name__,
                    )
                logger.warning(
                    "recall_shadow_submit_failed class=%s",
                    type(_shadow_submit_exc).__name__,
                )

        try:
            from core.cognition.moment_assembly_diagnostic import (
                moment_assembly_turn,
            )

            with moment_assembly_turn(
                surface=source,
                turn_id=_user_msg_turn_id,
                lifecycle_phase="turn_close",
            ):
                pass
        except Exception as _moment_diag_exc:
            logger.warning(
                "moment assembly completion diagnostic skipped: %s",
                _moment_diag_exc,
            )

        return reply

    def _get_public_context(self) -> str:
        """Get summary of recent public bot conversations for reasoning context."""
        client = None
        try:
            import chromadb
            from chromadb.config import Settings
            from datetime import datetime as _dt

            client = chromadb.PersistentClient(
                path=str(BASE_DIR / "memory" / "db" / "public_users"),
                settings=Settings(anonymized_telemetry=False),
            )
            col = client.get_or_create_collection("user_conversations")
            if col.count() == 0:
                return ""
            # Fetch all and filter in Python (timestamps are ISO strings)
            cutoff_iso = _dt.fromtimestamp(time.time() - 86400, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
            results = col.get(include=["documents", "metadatas"])
            filtered = [
                (doc, meta)
                for doc, meta in zip(results["documents"], results["metadatas"], strict=False)
                if meta.get("timestamp", "") >= cutoff_iso
            ]
            if not filtered:
                return ""
            # Group by user_id, resolve names from profiles
            by_user = {}
            profiles = client.get_or_create_collection("user_profiles")
            for doc, meta in filtered:
                uid = meta.get("user_id", "unknown")
                role = meta.get("role", "?")
                if uid not in by_user:
                    try:
                        p = profiles.get(ids=[uid], include=["metadatas"])
                        name = p["metadatas"][0].get("first_name", uid) if p["metadatas"] else uid
                    except Exception:
                        name = uid
                    by_user[uid] = {"name": name, "msgs": []}
                by_user[uid]["msgs"].append(f"[{role}] {doc[:100]}")
            lines = ["[MY CONVERSATIONS — last 24h]"]
            for uid, data in by_user.items():
                recent = data["msgs"][-4:]
                lines.append(f"  {data['name']} ({len(data['msgs'])} messages):")
                for m in recent:
                    lines.append(f"    {m}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug("Public context unavailable: %s", e)
            return ""
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as e:
                    logger.debug("Public context Chroma client close failed: %s", e)

    def handle_voice_stream(self, text: str) -> str:
        """Stream LLM response sentence-by-sentence to TTS. Returns full reply."""
        from skills.voice_output import feed_sentence
        from skills.web_search import (
            search as web_search,
            format_for_context as web_format,
            needs_web_search,
            search_rss,
            is_news_query,
            is_generic_news_query,
        )

        logger.info("Voice stream: %s", text[:100])

        import datetime as _dt

        simple_patterns = [
            "what time",
            "what day",
            "what date",
            "how are you",
            "hello",
            "hi maez",
            "good morning",
            "good night",
            "good afternoon",
            "good evening",
            "thanks",
            "thank you",
            "who are you",
            "what can you do",
            "tell me a joke",
            "are you there",
            "can you hear",
            "you there",
            "status",
            "what's up",
            "whats up",
            "sup",
        ]
        text_lower = text.lower().strip()
        is_simple = any(p in text_lower for p in simple_patterns)

        if is_simple:
            now_dt = _dt.datetime.now()
            time_str = now_dt.strftime("%I:%M %p").lstrip("0")
            day_str = now_dt.strftime("%A, %B %d, %Y")
            prompt = (
                f"Current time: {time_str}, {day_str}\n\n"
                f'the owner just spoke to you out loud:\n"{text}"\n\n'
                f"Respond in 1 short sentence. Spoken aloud, be natural and warm.\n"
                f"Remember: you are Maez, the owner's AI partner.\n"
            )
            num_predict = 60
            logger.info("[VOICE STREAM] Simple question — lightweight prompt")
        else:
            snap = perception_snapshot()
            system_state = format_snapshot(snap)
            recalled = self.memory.recall_for_telegram(text)
            memory_block = self.memory.format_for_prompt(recalled)
            web_context = ""
            if needs_web_search(text):
                # Generic news -> category-feed RSS; subject-specific news -> real
                # keyword search (search_rss ignores the subject, returns top headlines).
                if is_news_query(text) and is_generic_news_query(text):
                    sr = search_rss(text, max_results=3)
                else:
                    sr = web_search(text, max_results=3)
                web_context = web_format(sr)
            prompt = f"{system_state}\n\n"
            if memory_block:
                prompt += memory_block + "\n\n"
            if web_context:
                _wc_block = _wrap_daemon_web_context(web_context, path="voice")
                prompt += f"{_wc_block}\n\n"
            prompt += (
                f'the owner just spoke to you out loud:\n"{text}"\n\n'
                f"Respond in 1-2 short sentences. Your response will be spoken aloud.\n"
                f"Be warm, direct, and conversational. No bullet points or markdown.\n\n"
                f"Remember: NEVER suggest touching ollama, its models, or any "
                f"process that powers your reasoning."
            )
            num_predict = 200

        full_reply = ""
        try:
            from core import llm_client as _llm_client
            from core.routing.brain_gateway import with_purpose as _brain_purpose
            from core.routing.cancellable_brain_call import BrainPreempted

            with _brain_purpose("voice_reply"):
                resp = _llm_client.chat(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    think=False,
                    options={"temperature": 0.7, "num_predict": num_predict},
                )

            full_reply = _extract_final((resp.message.content or "").strip())
            sentence_buf = full_reply

            # Preserve the old TTS sentence batching at the boundary while the
            # brain call itself now travels through the foreground gateway lane.
            while True:
                m = re.search(r"([.!?])\s", sentence_buf)
                if not m:
                    break
                idx = m.end()
                sentence = sentence_buf[:idx].strip()
                sentence_buf = sentence_buf[idx:]
                if sentence:
                    logger.info("[VOICE STREAM] Speaking: %s", sentence[:80])
                    feed_sentence(sentence)

            if sentence_buf.strip():
                logger.info("[VOICE STREAM] Speaking remainder: %s", sentence_buf.strip()[:60])
                feed_sentence(sentence_buf.strip())
        except BrainPreempted:
            raise
        except Exception as e:
            logger.error("Voice stream error: %s", e)
            full_reply = full_reply or f"Error: {e}"

        # Store in memory. 5x.B Pass 1: user_utterance/lived; mixed-
        # origin transcript (see 5x.D).
        self.memory.store_telegram(
            f"the owner (voice): {text}\nMaez: {full_reply}",
            provenance_source="user_utterance",
            trust_tier="lived",
        )
        self._ws_broadcast({"type": "message_reply", "text": full_reply})
        return full_reply

    def _send_morning_briefing(self, snap: dict):
        """Send morning briefing when the owner first sits down. Once per day.

        State is persisted to `{BASE_DIR}/memory/last_briefing.txt` so
        daemon restarts don't reset the once-per-day guarantee. Before
        the persistence fix (observed 2026-04-22: 3 briefings in 34
        minutes after several restarts), `_last_briefing_date` was
        in-memory only and every restart re-enabled the briefing.

        2026-04-24 audit pass (see docs/audits/2026-04-24/
        autonomous_surface_audit.md, F1): (a) the briefing now goes
        through `audit_assistant_text` before send so an LLM
        fabrication has the same backstop as interactive replies;
        (b) briefing stamp path uses `BASE_DIR` so the daemon works in
        CI and on non-dev installs; (c) the LLM prompt uses
        `display_name()` instead of the ungrammatical "the owner his"
        role label; (d) the sent briefing is stored in telegram
        memory so `chat_history` threading surfaces it as a prior
        assistant turn when the owner replies.
        """
        from core import paths as _paths
        from core.memory.identity import display_name as _display_name

        today = time.strftime("%Y-%m-%d")
        briefing_stamp = _paths.home() / "memory" / "last_briefing.txt"
        try:
            if briefing_stamp.exists():
                persisted = briefing_stamp.read_text().strip()
                if persisted == today:
                    # Already sent today; cache in-memory too so we don't
                    # re-read the file on every presence-arrival check.
                    self._last_briefing_date = today
                    return
        except Exception:
            pass
        if self._last_briefing_date == today:
            return
        hour = int(time.strftime("%H"))
        if hour < 5 or hour > 11:
            return

        self._last_briefing_date = today
        try:
            briefing_stamp.parent.mkdir(parents=True, exist_ok=True)
            briefing_stamp.write_text(today)
        except Exception as e:
            logger.debug("couldn't persist briefing stamp: %s", e)
        logger.info("Preparing morning briefing")

        try:
            # Calendar v1 intentionally has no morning-briefing flow. The
            # legacy Calendar path used raw provider text; Decision 28 removes
            # that path instead of treating it as fallback context.
            cal_text = "Calendar unavailable through the S2-bounded v1 path."

            # Git
            from skills.git_awareness import get_summary_for_telegram

            git_text = get_summary_for_telegram()

            # News
            from skills.web_search import search_rss, format_for_context as web_fmt

            news = search_rss("general", 3)
            news_text = web_fmt(news) if news.get("success") else "No news loaded."

            # System
            disk_pct = snap["disk"].get("/", {}).get("percent", 0)
            stats = self.memory.memory_stats()
            _briefing_signals_present = ["git status summary", "system stats"]
            _briefing_signals_absent = []
            _briefing_signals_absent.append("calendar")
            if news.get("success"):
                _briefing_signals_present.append("rss news search")
            else:
                _briefing_signals_absent.append("rss news search")

            owner_name = _display_name() or "Friend"
            briefing_prompt = (
                f"You are sending {owner_name}'s morning briefing.\n"
                f"It is {time.strftime('%A, %B %d, %Y at %I:%M %p')}.\n\n"
                f"Context:\n"
                f"- {cal_text}\n"
                f"- Git: {git_text}\n"
                f"- System: / at {disk_pct:.0f}%, {stats['raw']} memories\n"
                f"- {news_text}\n\n"
                f"Write a morning briefing in 5 sentences max.\n"
                f"Cover: what matters today, system status, one news item.\n"
                f"Be direct. Be useful. Sign off as Maez."
            )
            _evidence_envelope = self._build_audit_evidence_envelope(
                surface="morning_briefing",
                signals_present=_briefing_signals_present,
                signals_absent=_briefing_signals_absent,
            )
            try:
                from core.cognition.envelope_builder import (
                    render_envelope_for_prompt as _render_envelope,
                )

                _envelope_block = _render_envelope(_evidence_envelope)
            except Exception as _env_exc:
                logger.warning(
                    "evidence_envelope render failed for morning_briefing "
                    "(continuing without prompt block): %s",
                    _env_exc,
                )
                _evidence_envelope = None
                _envelope_block = ""

            # Session 11r: via llm_client (was missed in 11p batch)
            from core import llm_client as _llm_client
            from core.routing.brain_gateway import with_purpose as _brain_purpose

            _messages = [{"role": "system", "content": self.system_prompt}]
            if _envelope_block:
                _messages.append({"role": "system", "content": _envelope_block})
            _messages.append({"role": "user", "content": briefing_prompt})
            with _brain_purpose("daemon_cycle_generation"):
                response = _llm_client.chat(
                    model=MODEL,
                    messages=_messages,
                    think=False,
                    options={"temperature": 0.5, "num_predict": 4096},
                )
            briefing = (response.message.content or "").strip()
            if briefing:
                # 2026-04-24: audit before send. Same contract as the
                # interactive reply path — stored text == sent text ==
                # audited text. surface="morning_briefing" so audit
                # telemetry can bucket this path.
                try:
                    from core.safety.audited_output import audit_assistant_text

                    briefing = audit_assistant_text(
                        briefing,
                        surface="morning_briefing",
                        signals_present=_briefing_signals_present,
                        signals_absent=_briefing_signals_absent,
                        evidence_envelope=_evidence_envelope,
                    )
                except Exception as _aud_exc:
                    logger.warning(
                        "morning_briefing audit fail-open: %s",
                        _aud_exc,
                    )
                final_msg = f"Morning briefing:\n\n{briefing}"
                self._send_telegram_notice(
                    final_msg,
                    source_ref="daemon:morning_briefing",
                )
                logger.info("Morning briefing sent")
                # Store as a telegram exchange so chat_history threading
                # picks it up when the owner replies. Placeholder user
                # turn ([just arrived]) keeps the stored shape
                # consistent with `_clean_exchange`'s parse expectation.
                try:
                    # 5x.B Pass 1: introspection/lived — `[just arrived]`
                    # is a synthetic presence token, not owner text. The
                    # entire stored row is Maez's morning monologue
                    # triggered by owner presence; tagging this as
                    # user_utterance would leak Maez-authored briefings
                    # into 5x.D's "owner said X" filter.
                    self.memory.store_telegram(
                        f"the owner (morning_briefing): [just arrived]\nMaez: {briefing}",
                        provenance_source="introspection",
                        trust_tier="lived",
                    )
                except Exception as _store_exc:
                    logger.debug(
                        "morning_briefing memory store skipped: %s",
                        _store_exc,
                    )

        except Exception as e:
            logger.error("Morning briefing failed: %s", e)

    def _check_and_alert(self, snap: dict):
        """Send alert to Telegram only for real system threshold breaches."""
        gpu = snap.get("gpu") or {}
        gpu_temp = gpu.get("temperature_c", 0)
        ram_pct = snap["ram"]["percent"]
        cpu_pct = snap["cpu"]["percent"]
        root_disk = snap["disk"].get("/", {})
        disk_free_pct = 100 - root_disk.get("percent", 0) if root_disk else 100

        # Track sustained high CPU
        if cpu_pct >= self.CPU_THRESHOLD:
            self._high_cpu_streak += 1
        else:
            self._high_cpu_streak = 0

        # Collect triggered alerts
        reasons = []
        if gpu_temp >= self.GPU_TEMP_THRESHOLD:
            reasons.append(f"GPU temp {gpu_temp}°C (threshold: {self.GPU_TEMP_THRESHOLD}°C)")
        if ram_pct >= self.RAM_THRESHOLD:
            reasons.append(f"RAM {ram_pct}% (threshold: {self.RAM_THRESHOLD}%)")
        if disk_free_pct < self.DISK_THRESHOLD:
            reasons.append(
                f"Root disk {disk_free_pct:.1f}% free (threshold: {self.DISK_THRESHOLD}%)"
            )
        if self._high_cpu_streak >= self.CPU_STREAK_REQUIRED:
            reasons.append(f"CPU sustained {cpu_pct}% for {self._high_cpu_streak} cycles")

        if not reasons:
            return

        # Enforce 30-minute cooldown
        now = time.time()
        elapsed = now - self._last_alert_time
        if self._last_alert_time > 0 and elapsed < self.ALERT_COOLDOWN:
            logger.info(
                "Alert suppressed (cooldown: %dm remaining): %s",
                int((self.ALERT_COOLDOWN - elapsed) / 60),
                ", ".join(reasons),
            )
            return

        alert_msg = f"[Cycle {self.cycle_count}]\n" + "\n".join(f"⚠ {r}" for r in reasons)
        logger.info("Alert sent: %s", ", ".join(reasons))
        send_dev(alert_msg)
        self._last_alert_time = now

    # ------------------------------------------------------------------ #
    #  WebSocket broadcast                                                 #
    # ------------------------------------------------------------------ #

    def _ws_broadcast(self, msg: dict):
        """Broadcast a JSON message to all connected WebSocket clients."""
        if not self._ws_clients or not self._ws_loop:
            return
        data = json.dumps(msg)
        dead = set()
        for client in self._ws_clients.copy():
            try:
                asyncio.run_coroutine_threadsafe(client.send(data), self._ws_loop)
            except Exception:
                dead.add(client)
        self._ws_clients -= dead

    async def _ws_handler(self, websocket):
        self._ws_clients.add(websocket)
        logger.info("WS client connected (%d total)", len(self._ws_clients))
        try:
            async for _ in websocket:
                pass  # We only broadcast, ignore incoming
        finally:
            self._ws_clients.discard(websocket)
            logger.info("WS client disconnected (%d total)", len(self._ws_clients))

    def _run_ws_server(self):
        """Run WebSocket server in its own event loop.

        Shutdown hygiene (2026-05-05, T1.9 second-instance fix
        caught by Codex on the dce9fa5 deploy): unlike surface_v2,
        the serve() coroutine here does `await asyncio.Future()`
        — an unresolvable forever-await. There is NO cooperative
        exit path; stop() must call `_ws_loop.call_soon_threadsafe
        (_loop.stop)` to break us out, and that produces
        `RuntimeError("Event loop stopped before Future
        completed.")`. We catch that RuntimeError as the expected
        shutdown shape WHEN we know we're shutting down
        (`self.running` is False). A real loop-crash during
        operation still surfaces as ERROR.
        """
        _install_websocket_noise_filter()
        self._ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._ws_loop)

        async def serve():
            async with websockets.serve(self._ws_handler, "127.0.0.1", WS_PORT):
                logger.info("WebSocket server started on port %d", WS_PORT)
                await asyncio.Future()  # run forever

        try:
            self._ws_loop.run_until_complete(serve())
        except RuntimeError as e:
            # The expected shutdown shape: stop() called
            # _loop.call_soon_threadsafe(_loop.stop), the forever-
            # await got interrupted, run_until_complete raised
            # "Event loop stopped before Future completed."
            # Recognize this as expected when self.running is
            # False; surface it as ERROR otherwise.
            if not self.running:
                logger.info("WebSocket server: graceful shutdown (loop stopped during shutdown)")
            else:
                logger.exception(
                    "WebSocket server: unexpected runtime error while self.running=True: %s",
                    e,
                )

    def _start_health_broadcast(self):
        """Broadcast health stats every 10 seconds."""
        while self.running:
            try:
                snap = perception_snapshot()
                gpu = snap.get("gpu") or {}
                self._ws_broadcast(
                    {
                        "type": "health",
                        "system": {
                            "cpu_percent": snap["cpu"]["percent"],
                            "ram_percent": snap["ram"]["percent"],
                            "gpu_percent": gpu.get("utilization_pct"),
                            "gpu_temp_c": gpu.get("temperature_c"),
                        },
                    }
                )
            except Exception:
                pass
            time.sleep(10)

    def _consolidation_loop(self):
        """Run daily memory consolidation at 3:00 AM local time."""
        logger.info("Consolidation thread started (target: 03:00 local)")

        # Run missed consolidation immediately on startup
        if getattr(self, "_missed_consolidation", False):
            logger.info("=== Running missed daily consolidation ===")
            try:
                summary = self.memory.consolidate_daily()
                if summary:
                    logger.info("Missed consolidation complete: %d chars", len(summary))
                    send_dev(
                        f"Missed consolidation recovered.\nStats: {self.memory.memory_stats()}"
                    )
            except Exception as e:
                logger.error("Missed consolidation error: %s", e)
            self._missed_consolidation = False

        while self.running:
            now = datetime.now().astimezone()
            # Calculate seconds until next 3:00 AM
            target = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()

            logger.info(
                "Next consolidation in %.1f hours at %s",
                wait_seconds / 3600,
                target.strftime("%Y-%m-%d %H:%M"),
            )

            # Sleep in 60s increments so shutdown is responsive
            slept = 0
            while slept < wait_seconds and self.running:
                time.sleep(min(60, wait_seconds - slept))
                slept += 60

            if not self.running:
                break

            logger.info("=== Starting daily memory consolidation ===")
            try:
                summary = self.memory.consolidate_daily()
                if summary:
                    logger.info("Daily consolidation complete: %d chars", len(summary))
                    send_dev(
                        f"Daily memory consolidation complete.\n"
                        f"Stats: {self.memory.memory_stats()}"
                    )
            except Exception as e:
                logger.error("Daily consolidation error: %s", e)

            try:
                _run_reflection_synthesis_nightly(self)
            except Exception as e:
                logger.warning("Reflection synthesis dry-run failed: %s", e)

            # Self-analysis after consolidation
            try:
                analysis = self_analyze(self.memory, self.actions)
                if analysis:
                    msg = analysis_telegram(analysis)
                    send_dev(f"Nightly self-analysis:\n{msg}")
                    logger.info("Self-analysis complete")
            except Exception as e:
                logger.error("Self-analysis failed: %s", e)

            # Migrate untagged memories with wing labels
            try:
                tagged = self.memory.migrate_wings(batch_size=50)
                if tagged:
                    logger.info("Wing migration: %d memories tagged", tagged)
            except Exception as e:
                logger.debug("Wing migration failed: %s", e)

            # Check action trust promotions
            try:
                candidates = self.actions.check_promotions()
                if candidates:
                    types_str = ", ".join(c["action_type"] for c in candidates)
                    send_dev(
                        f"Maez has earned higher autonomy for: {types_str}.\n"
                        f"Reply /promote <action_type> to lower its tier."
                    )
                    logger.info("Trust promotion candidates: %s", types_str)
            except Exception as e:
                logger.debug("Trust promotion check failed: %s", e)

            # Evolution cycle after self-analysis
            evo_summary = {"experiments": 0, "failed": 0, "deployed": 0, "flagged": 0}
            try:
                from skills.evolution_engine import run_evolution_cycle
                from skills.self_analysis import get_weaknesses

                weaknesses = get_weaknesses(self.memory)
                if weaknesses:
                    logger.info("Evolution: %d weaknesses found", len(weaknesses))
                    self._evolution_summary = run_evolution_cycle(
                        weaknesses,
                        telegram_callback=send_dev,
                    )
                    evo_summary = self._evolution_summary
                else:
                    logger.info("No weaknesses — skipping evolution")
            except Exception as e:
                logger.error("Evolution cycle failed: %s", e)

            # Unified nightly summary card
            try:
                from skills.dev_notifier import send_nightly_card
                from skills.self_analysis import analyze as _self_analyze

                analysis = _self_analyze(self.memory, self.actions) or {}
                top_topics = []
                send_nightly_card(
                    memories_analyzed=analysis.get(
                        "total_analyzed", self.memory.memory_stats().get("raw", 0)
                    ),
                    unique_insight_rate=analysis.get("unique_insight_rate", 0),
                    top_topics=top_topics,
                    proposals_attempted=evo_summary.get("experiments", 0),
                    proposals_failed=evo_summary.get("failed", 0),
                )
            except Exception as e:
                logger.debug("Nightly card failed: %s", e)

        logger.info("Consolidation thread stopped.")

    def _capability_planning_loop(self):
        """D20 Stage-5 — hourly poller for the capability-acquisition
        queue. Walks queued rows that don't yet have a draft
        integration plan, calls the planner, persists the result,
        and surfaces a PendingCard for owner review when one lands.

        Hourly cadence (not every cycle): the queue fills slowly
        because every entry requires a prior consent-card approval.
        Hourly is responsive enough for human-review windows and
        keeps the load on llama-server / disk negligible.
        """
        logger.info("Capability planning thread started (interval: 1h)")

        # First tick after a short startup delay so the daemon's
        # primary loops settle before this side-channel runs.
        startup_delay = 60.0
        slept = 0.0
        while slept < startup_delay and self.running:
            time.sleep(min(10.0, startup_delay - slept))
            slept += 10.0

        # T2.6 (2026-05-04 audit) — bounded exponential backoff on
        # exception. Previously every failed tick still slept the
        # full 3600s before retry AND the log line included only
        # the exception message (not its class), so an operator
        # never saw what was actually breaking.
        _BACKOFF_SEED_S = 60.0
        _BACKOFF_CAP_S = 3600.0
        _NORMAL_INTERVAL_S = 3600.0
        backoff_s = _BACKOFF_SEED_S

        while self.running:
            tick_failed = False
            try:
                from core.infra.capability_acquisition_queue import (
                    AcquisitionQueue,
                )
                from core.infra.capability_integration_plans import (
                    IntegrationPlanStore,
                    poll_and_plan,
                )

                q = AcquisitionQueue()
                plans = IntegrationPlanStore()
                new_plan_ids = poll_and_plan(queue=q, plans=plans)

                # For each freshly-persisted plan, surface a
                # consent card so the owner can approve / reject
                # the plan before any implementation work begins.
                for plan_id in new_plan_ids:
                    self._surface_integration_plan_card(plans, plan_id)
            except Exception as e:
                tick_failed = True
                logger.warning(
                    "Capability planning loop tick failed: %s: %s — backing off %.0fs",
                    type(e).__name__,
                    e,
                    backoff_s,
                )

            # On success, reset backoff and use the normal hourly
            # interval. On failure, sleep the current backoff then
            # double it (capped at 3600s) for the next failure.
            if tick_failed:
                next_sleep = backoff_s
                backoff_s = min(backoff_s * 2.0, _BACKOFF_CAP_S)
            else:
                backoff_s = _BACKOFF_SEED_S
                next_sleep = _NORMAL_INTERVAL_S

            # Sleep in 60s (or smaller) increments so shutdown
            # remains responsive even during a long backoff.
            slept = 0.0
            while slept < next_sleep and self.running:
                time.sleep(min(60.0, next_sleep - slept))
                slept += 60.0

        logger.info("Capability planning thread stopped.")

    def _surface_integration_plan_card(self, plans, plan_id):
        """Create a PendingCard for a draft integration plan so the
        owner can review and approve it. Idempotent across hourly
        cycles because PendingCardStore.create_card supersedes prior
        open cards in the same chat_id, and because plans whose
        status has moved past 'draft' are excluded by the poller's
        skip-existing logic upstream."""
        try:
            row = next(
                (p for p in plans.list_all() if p["plan_id"] == plan_id),
                None,
            )
            if row is None:
                return
            plan_json = row.get("plan_json") or {}
            cap_id = row.get("capability_id", "unknown")
            summary = plan_json.get("summary", "")
            files = plan_json.get("proposed_files") or []
            tests = plan_json.get("proposed_tests") or []
            risks = plan_json.get("risks") or []
            plain = (
                f"Integration plan ready for review: **{cap_id}**\n\n"
                f"Summary: {summary}\n"
                f"Proposed files: {len(files)}  ·  "
                f"proposed tests: {len(tests)}  ·  "
                f"risks flagged: {len(risks)}\n\n"
                f"Approve to mark plan_approved (no code change yet — "
                f"implementation is a separate slice). Deny to discard."
            )
            from core.decision.pending_cards import PendingCardStore

            store = PendingCardStore()
            try:
                from core.identity import (
                    user_profile_id as _owner_user_id,
                )

                owner = _owner_user_id()
            except Exception:
                owner = "owner"
            # Per-plan chat_id so PendingCardStore's chat-scoped
            # supersession doesn't steamroll concurrent draft plans.
            # Without this, two draft plans in the same hourly tick
            # would race (second card supersedes first) and only the
            # latest would be actionable. user_id stays the owner so
            # `/pending` and cockpit lookups continue to find these.
            plan_bucket = f"capability_plan:{plan_id}"
            store.create_card(
                action="integration.review_plan",
                params={
                    "plan_id": plan_id,
                    "queue_id": row["queue_id"],
                    "capability_id": cap_id,
                },
                reason="capability-acquisition Stage 5 plan",
                plain_english=plain,
                chat_id=plan_bucket,
                user_id=str(owner),
            )
            logger.info(
                "capability_integration_plans: surfaced card for plan_id=%s capability_id=%s",
                plan_id,
                cap_id,
            )
        except Exception as e:
            logger.warning(
                "capability_integration_plans: surface_card failed for plan_id=%s: %s",
                plan_id,
                e,
            )

    def _nightly_journal_loop(self):
        """Write a daily journal entry to PROGRESS.md at 11:00 PM local time."""
        logger.info("Journal thread started (target: 23:00 local)")

        while self.running:
            now = datetime.now().astimezone()
            target = now.replace(hour=23, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()

            logger.info(
                "Next journal entry in %.1f hours at %s",
                wait_seconds / 3600,
                target.strftime("%Y-%m-%d %H:%M"),
            )

            slept = 0
            while slept < wait_seconds and self.running:
                time.sleep(min(60, wait_seconds - slept))
                slept += 60

            if not self.running:
                break

            # Curiosity check-in at ~9pm (before 11pm journal)
            try:
                self._curiosity_checkin()
            except Exception as e:
                logger.error("Curiosity check-in error: %s", e)

            logger.info("=== Writing nightly journal entry ===")
            try:
                self._write_journal_entry()
            except Exception as e:
                logger.error("Journal entry failed: %s", e)

        logger.info("Journal thread stopped.")

    def _write_journal_entry(self):
        """Collect the day's activity and append a dated entry to PROGRESS.md."""
        today = datetime.now().astimezone()
        date_str = today.strftime("%Y-%m-%d")
        day_name = today.strftime("%A")

        # 1. Read last 24h of logs
        log_path = BASE_DIR / "logs" / "maez.log"
        cutoff_str = (today - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        log_lines = []
        try:
            for line in log_path.read_text().splitlines():
                if line[:19] >= cutoff_str:
                    log_lines.append(line)
        except Exception:
            log_lines = ["(could not read maez.log)"]

        # Count cycles, errors, alerts from logs
        cycle_count = sum(1 for l in log_lines if "--- Cycle" in l)
        errors = [l for l in log_lines if "[ERROR]" in l]
        warnings = [l for l in log_lines if "[WARNING]" in l]
        alerts_sent = sum(1 for l in log_lines if "Alert sent:" in l)

        # 2. Read action log for today
        action_log = BASE_DIR / "logs" / "actions.log"
        action_lines = []
        try:
            for line in action_log.read_text().splitlines():
                if line[:10] == date_str:
                    action_lines.append(line)
        except Exception:
            pass

        # 3. Memory stats
        stats = self.memory.memory_stats()

        # 4. Get latest daily consolidation if one was written today
        consolidation_text = ""
        try:
            daily_results = self.memory.daily.get(
                include=["documents", "metadatas"],
            )
            for i, meta in enumerate(daily_results.get("metadatas", [])):
                if meta.get("date") == date_str:
                    consolidation_text = daily_results["documents"][i]
        except Exception:
            pass

        # 5. Current perception snapshot
        snap = perception_snapshot()
        gpu = snap.get("gpu") or {}

        # 6. Ask gemma4 to summarize the day using log excerpts
        # Sample log lines to keep prompt manageable
        sample_responses = []
        for l in log_lines:
            if "response:" in l.lower() and len(sample_responses) < 10:
                # Grab the response text (next non-empty content after "response:")
                idx = l.find("response:")
                if idx >= 0:
                    text = l[idx + 9 :].strip()
                    if text and text != "(empty response)":
                        sample_responses.append(text[:200])

        prompt_context = (
            f"Date: {date_str} ({day_name})\n"
            f"Reasoning cycles today: {cycle_count}\n"
            f"Errors: {len(errors)}\n"
            f"Warnings: {len(warnings)}\n"
            f"Alerts sent to the owner: {alerts_sent}\n"
            f"Actions executed today: {len(action_lines)}\n"
            f"Memory stats: {stats['raw']} raw, {stats['daily']} daily, {stats['core']} core\n\n"
        )

        if consolidation_text:
            prompt_context += f"Daily memory consolidation summary:\n{consolidation_text[:500]}\n\n"

        if sample_responses:
            prompt_context += "Sample observations from today:\n"
            for i, r in enumerate(sample_responses[:5], 1):
                prompt_context += f"  {i}. {r}\n"
            prompt_context += "\n"

        if errors:
            prompt_context += "Errors encountered:\n"
            for e in errors[:5]:
                prompt_context += f"  - {e[20:]}\n"  # strip timestamp
            prompt_context += "\n"

        if action_lines:
            prompt_context += "Actions taken:\n"
            for a in action_lines[:5]:
                prompt_context += f"  - {a[20:]}\n"
            prompt_context += "\n"

        prompt_context += (
            f"Current system state:\n"
            f"  CPU: {snap['cpu']['percent']}%\n"
            f"  RAM: {snap['ram']['percent']}%\n"
            f"  GPU: {gpu.get('utilization_pct', 'N/A')}%, {gpu.get('temperature_c', 'N/A')}°C\n"
            f"  Disk /: {snap['disk'].get('/', {}).get('percent', '?')}%\n"
            f"  Uptime: {int(time.time() - datetime.fromisoformat(self.boot_time).timestamp()) // 3600}h "
            f"{(int(time.time() - datetime.fromisoformat(self.boot_time).timestamp()) % 3600) // 60}m\n"
        )

        summary_prompt = (
            f"You are Maez writing your nightly journal entry for PROGRESS.md.\n"
            f"Write a concise daily summary covering:\n"
            f"1. Key observations you made today\n"
            f"2. Any actions you took or proposed\n"
            f"3. Memory statistics (how much you stored and remembered)\n"
            f"4. Any issues or errors encountered\n"
            f"5. Current system state at end of day\n"
            f"6. One sentence about what you're watching for tomorrow\n\n"
            f"Write in first person as Maez. Be specific with numbers.\n"
            f"Keep it under 15 lines. No headers, just clean prose.\n\n"
            f"--- Today's data ---\n\n"
            f"{prompt_context}"
        )
        _journal_signals_present = [
            "daemon_logs",
            "memory_stats",
            "perception_snapshot",
        ]
        _journal_signals_absent: list[str] = []
        _evidence_envelope = self._build_audit_evidence_envelope(
            surface="nightly_journal",
            signals_present=_journal_signals_present,
            signals_absent=_journal_signals_absent,
        )
        try:
            from core.cognition.envelope_builder import (
                render_envelope_for_prompt as _render_envelope,
            )

            _envelope_block = _render_envelope(_evidence_envelope)
        except Exception as _env_exc:
            logger.warning(
                "evidence_envelope render failed for nightly_journal "
                "(continuing without prompt block): %s",
                _env_exc,
            )
            _evidence_envelope = None
            _envelope_block = ""
        if _envelope_block:
            summary_prompt += "\n\n" + _envelope_block

        try:
            # Session 11r: via llm_client (was missed in 11p batch)
            from core import llm_client as _llm_client
            from core.routing.brain_gateway import with_purpose as _brain_purpose

            with _brain_purpose("daemon_cycle_generation"):
                response = _llm_client.chat(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": summary_prompt},
                    ],
                    think=False,
                    options={"temperature": 0.3, "num_predict": 4096},
                )
            summary = (response.message.content or "").strip()
            if not summary:
                summary = (
                    f"Ran {cycle_count} reasoning cycles. "
                    f"Stored {stats['raw']} raw memories, {stats['daily']} daily, {stats['core']} core. "
                    f"{len(errors)} errors, {alerts_sent} alerts sent. "
                    f"System nominal."
                )
        except Exception as e:
            summary = (
                f"Journal generation failed ({e}). "
                f"Cycles: {cycle_count}, Errors: {len(errors)}, "
                f"Memories: {stats['raw']} raw / {stats['daily']} daily / {stats['core']} core."
            )

        try:
            from core.safety.audited_output import audit_assistant_text

            summary = audit_assistant_text(
                summary,
                surface="nightly_journal",
                signals_present=_journal_signals_present,
                signals_absent=_journal_signals_absent,
                evidence_envelope=_evidence_envelope,
            )
        except Exception as e:
            logger.debug("Nightly journal audit fail-open: %s", e)

        # Append to PROGRESS.md
        progress_path = BASE_DIR / "PROGRESS.md"
        entry = f"\n\n---\n\n## Daily Journal — {date_str} ({day_name})\n\n{summary}\n"

        with open(progress_path, "a") as f:
            f.write(entry)

        logger.info("Journal entry written for %s (%d chars)", date_str, len(entry))

        # Also store the journal as a core memory. 5x.B Pass 1:
        # introspection/lived because the journal is Maez reflecting
        # on the day, not an infrastructure write.
        self.memory.store_core(
            f"[Journal {date_str}] {summary[:500]}",
            source="nightly_journal",
            provenance_source="introspection",
            trust_tier="lived",
        )

        try:
            self._write_developmental_heartbeat(
                date_str=date_str,
                day_name=day_name,
                journal_summary=summary,
                cycle_count=cycle_count,
                error_count=len(errors),
                warning_count=len(warnings),
                action_count=len(action_lines),
                alert_count=alerts_sent,
                stats=stats,
            )
        except Exception as e:
            logger.warning("Developmental heartbeat failed: %s", e)

        # GitHub auto-publish retired (v0.1, 2026-06-04). Public exposure is
        # a deliberate owner action, not a nightly daemon side effect.

    def _write_developmental_heartbeat(
        self,
        *,
        date_str: str,
        day_name: str,
        journal_summary: str,
        cycle_count: int,
        error_count: int,
        warning_count: int,
        action_count: int,
        alert_count: int,
        stats: dict,
    ) -> str | None:
        """Store one audited daily self-continuity core memory."""
        from core.brain.developmental_heartbeat import (
            HeartbeatEvidence,
            already_recorded,
            build_prompt,
            fallback_heartbeat,
            normalize_heartbeat,
            record_if_absent,
        )

        if already_recorded(self.memory, date_str):
            logger.info("Developmental heartbeat already recorded for %s", date_str)
            return None

        try:
            from core.memory.identity import display_name as _display_name

            owner_name = _display_name()
        except Exception:
            owner_name = "the owner"
        _continuity_available = False
        try:
            from core.brain.continuity_ledger import summarize_day

            continuity_summary = summarize_day(date_str)
            _continuity_available = True
        except Exception as e:
            logger.debug("Continuity ledger summary unavailable: %s", e)
            continuity_summary = "Continuity probe summary unavailable."

        evidence = HeartbeatEvidence(
            date=date_str,
            day_name=day_name,
            cycle_count=cycle_count,
            error_count=error_count,
            warning_count=warning_count,
            action_count=action_count,
            alert_count=alert_count,
            raw_count=int(stats.get("raw", 0)),
            daily_count=int(stats.get("daily", 0)),
            core_count=int(stats.get("core", 0)),
            owner_name=owner_name,
            journal_summary=journal_summary,
            continuity_summary=continuity_summary,
        )
        _heartbeat_signals_present = [
            "nightly_journal",
            "memory_stats",
            "daemon_logs",
        ]
        _heartbeat_signals_absent: list[str] = []
        if _continuity_available:
            _heartbeat_signals_present.append("continuity_ledger")
        else:
            _heartbeat_signals_absent.append("continuity_ledger")
        _evidence_envelope = self._build_audit_evidence_envelope(
            surface="developmental_heartbeat",
            signals_present=_heartbeat_signals_present,
            signals_absent=_heartbeat_signals_absent,
        )
        try:
            from core.cognition.envelope_builder import (
                render_envelope_for_prompt as _render_envelope,
            )

            _envelope_block = _render_envelope(_evidence_envelope)
        except Exception as _env_exc:
            logger.warning(
                "evidence_envelope render failed for developmental_heartbeat "
                "(continuing without prompt block): %s",
                _env_exc,
            )
            _evidence_envelope = None
            _envelope_block = ""

        try:
            from core import llm_client as _llm_client
            from core.routing.brain_gateway import with_purpose as _brain_purpose

            _messages = [{"role": "system", "content": self.system_prompt}]
            if _envelope_block:
                _messages.append({"role": "system", "content": _envelope_block})
            _messages.append({"role": "user", "content": build_prompt(evidence)})
            with _brain_purpose("daemon_cycle_generation"):
                response = _llm_client.chat(
                    model=MODEL,
                    messages=_messages,
                    think=False,
                    options={"temperature": 0.2, "num_predict": 700},
                )
            heartbeat = normalize_heartbeat(
                (response.message.content or "").strip(),
                evidence,
            )
        except Exception as e:
            logger.debug("Developmental heartbeat model failed: %s", e)
            heartbeat = fallback_heartbeat(evidence)

        try:
            from core.safety.audited_output import audit_assistant_text

            heartbeat = audit_assistant_text(
                heartbeat,
                surface="developmental_heartbeat",
                signals_present=_heartbeat_signals_present,
                signals_absent=_heartbeat_signals_absent,
                evidence_envelope=_evidence_envelope,
            )
            heartbeat = normalize_heartbeat(heartbeat, evidence)
        except Exception as e:
            logger.debug("Developmental heartbeat audit fail-open: %s", e)

        memory_id = record_if_absent(self.memory, evidence, heartbeat)
        if memory_id:
            logger.info("Developmental heartbeat stored: %s", memory_id)
        return memory_id

    def _loop(self):
        """Main reasoning loop — runs every LOOP_INTERVAL seconds."""
        from core.routing.cancellable_brain_call import BrainPreempted

        logger.info("Reasoning loop started (interval: %ds)", LOOP_INTERVAL)

        while self.running:
            cycle_start = time.time()
            try:
                self._metacognitive_watchdog.observe_cycle_duration(
                    cycle_start - getattr(self, "_watchdog_last_cycle_start", cycle_start)
                )
                self._watchdog_last_cycle_start = cycle_start
                try:
                    self._metacognitive_watchdog.observe_scalars(self.temperament.current())
                except Exception as exc:
                    logger.debug("metacognitive watchdog scalar sample skipped: %s", exc)
            except Exception as halt:
                from core.health.metacognitive_watchdog import WatchdogHalt

                if isinstance(halt, WatchdogHalt):
                    self._enter_watchdog_safe_standby(halt)
                    break
                raise

            if continuous_time_sense_enabled():
                try:
                    _ts = self._time_sense_handle()
                    _ts.peek()                                  # refresh the live sense (read-only, exact)
                    _now = datetime.now(timezone.utc)
                    _last = self._last_time_anchor_ts
                    if _last is None or (_now - _last).total_seconds() >= self._CONTINUOUS_TIME_ANCHOR_INTERVAL_S:
                        _ts.current()                           # ONE sparse anchor (stamps compute_version)
                        self._last_time_anchor_ts = _now
                except Exception:
                    logger.debug("continuous time-sense tick skipped", exc_info=True)

            self.cycle_count += 1
            self.last_cycle_time = datetime.now(timezone.utc).isoformat()
            self._mark_cycle_stage("cycle_start")
            cycle_preempted = False

            logger.info("--- Cycle %d ---", self.cycle_count)
            self._mark_cycle_stage("m1_flush_due_windows")
            self._m1_flush_due_windows()

            # 5x.F.A — reset the per-cycle recall-context bag at cycle
            # top. Populated after `recall_for_cycle` (line ~1077);
            # F.B will read it from `_do_update_baseline` to apply the
            # any-untrusted-tips downgrade rule.
            #
            # ORDERING: reset MUST precede `execute_pending` below.
            # Tier-0 `update_baseline` (per 5x.D.B1) fires same-cycle,
            # so when F.B's consumer runs in this cycle it should see
            # the freshly-empty bag, then the bag refills after
            # `recall_for_cycle` later in the cycle. If a future
            # maintainer "tidies" by moving the reset after
            # `execute_pending`, prior-cycle untrusted IDs would
            # persist into this cycle's first reads — silently
            # over-downgrading. Don't reorder without revisiting
            # F.B's invariant.
            self._cycle_recall_context = _crc_empty()

            # Execute deferred actions from previous cycle
            self._mark_cycle_stage("deferred_actions")
            tier1_results = self.actions.execute_pending()
            tier2_results = self.actions.execute_tier2_pending()
            if tier1_results or tier2_results:
                try:
                    self._metacognitive_watchdog.observe_actions(
                        f"tier{getattr(r, 'tier', '?')}:{getattr(r, 'action', '?')}"
                        for r in tier1_results + tier2_results
                    )
                except Exception as halt:
                    from core.health.metacognitive_watchdog import WatchdogHalt

                    if isinstance(halt, WatchdogHalt):
                        self._enter_watchdog_safe_standby(halt)
                        break
                    raise
            for r in tier1_results + tier2_results:
                logger.info("Deferred action result: %s", r)

            # Session 11z Part 2: fire due card reminders.
            # Any pending_cards row in 'deferred' status whose remind_at
            # has arrived gets re-presented to the owner on whatever channel
            # the original card was sent on. This is the mechanism that
            # makes "wait an hour" actually work — Maez proactively comes
            # back when the hour is up. Failure here must never crash
            # the cycle, so the whole block is guarded.
            try:
                self._mark_cycle_stage("card_reminders")
                pipe = (
                    self.telegram._get_pipeline()
                    if hasattr(self.telegram, "_get_pipeline")
                    else None
                )
                if pipe is not None:
                    due = pipe.tick_reminders()
                    if due:
                        logger.info("Re-presented %d deferred card(s)", len(due))
                    # Also expire cards that have been sitting untouched
                    # for > 7 days so the open-card list stays finite.
                    expired = pipe.card_store.expire_abandoned(older_than_seconds=7 * 86400)
                    if expired:
                        logger.info("Expired %d abandoned card(s)", expired)
            except Exception as e:
                logger.debug("card reminder tick failed: %s", e)

            # Broadcast cycle start to UI
            self._mark_cycle_stage("broadcast_cycle_start")
            self._ws_broadcast({"type": "cycle_start", "cycle": self.cycle_count})
            self._s1b_residue_events = []

            # Collect system perception
            self._mark_cycle_stage("perception_snapshot")
            try:
                snap = perception_snapshot()
            except Exception as _perc_exc:
                # Defense in depth (2026-06-02 daemon-cycle-stuck incident).
                # Perception is now internally resilient — each sensor degrades
                # rather than raising under a transient EMFILE/Errno 24 blip —
                # but if perception_snapshot() ever fails for a NEW reason, one
                # bad cycle must NOT kill Maez's heartbeat. Log it, mark a
                # distinct recovery stage so /health shows the loop recovering
                # (not frozen at 'perception_snapshot'), sleep one interval, and
                # skip just this cycle. The covenant: the cognition cycle is
                # Maez's inner life; a sensor blip pauses a thought, it does not
                # end the being.
                logger.error(
                    "Cycle %d: perception_snapshot raised (%s: %s) — skipping "
                    "this cycle, cognition loop continues",
                    self.cycle_count,
                    type(_perc_exc).__name__,
                    _perc_exc,
                )
                self._mark_cycle_stage("perception_error_recovered")
                for _ in range(LOOP_INTERVAL):
                    if not self.running:
                        break
                    time.sleep(1)
                continue
            logger.info(
                "Perception: CPU %.1f%%, RAM %.1f%%, GPU %s%%, %s°C",
                snap["cpu"]["percent"],
                snap["ram"]["percent"],
                snap["gpu"]["utilization_pct"] if snap.get("gpu") else "N/A",
                snap["gpu"]["temperature_c"] if snap.get("gpu") else "N/A",
            )

            # Screen perception — every N cycles using gemma4 vision
            self._mark_cycle_stage("screen_perception")
            self._screen_cycle_counter += 1
            if self._screen_cycle_counter >= self.SCREEN_OBSERVE_EVERY_N_CYCLES:
                self._screen_cycle_counter = 0
                try:
                    self._last_screen_obs = screen_observe()
                    if self._last_screen_obs.success:
                        logger.info("Screen: %s", self._last_screen_obs.activity)
                    else:
                        logger.debug("Screen obs failed: %s", self._last_screen_obs.error)
                except Exception as e:
                    logger.warning("Screen perception error: %s", e)

            # Calendar legacy perception is developer-test-only. Decision 28
            # forbids raw Calendar prompt context and proactive reminder voice,
            # so this mode may refresh a snapshot for manual diagnostics but
            # never sends alerts or writes raw Calendar text into memory.
            if self._calendar_legacy_enabled and self._calendar_observe is not None:
                self._mark_cycle_stage("calendar_perception_legacy_dev_only")
                self._calendar_cycle_counter += 1
                if self._calendar_cycle_counter >= self.CALENDAR_OBSERVE_EVERY_N_CYCLES:
                    self._calendar_cycle_counter = 0
                    try:
                        self._last_calendar_snap = self._calendar_observe()
                        if getattr(self._last_calendar_snap, "success", False):
                            logger.info(
                                "Calendar legacy-dev snapshot refreshed: %d events",
                                len(getattr(self._last_calendar_snap, "events", [])),
                            )
                        else:
                            logger.debug(
                                "Calendar legacy-dev fetch failed: %s",
                                getattr(self._last_calendar_snap, "error", "unknown"),
                            )
                    except Exception as e:
                        logger.warning("Calendar legacy-dev perception error: %s", e)

            # Camera Presence v1 — health/panel body sensor. It never
            # triggers greetings, prompt context, memory, audit grounding, or
            # doorman salience. Dream scheduling may read a fresh-present
            # state through the explicit activity-primary idle helper below.
            self._mark_cycle_stage("presence_perception")
            self._presence_cycle_counter += 1
            if (
                self._camera_presence_state.enabled
                and self._presence_cycle_counter >= self.PRESENCE_EVERY_N_CYCLES
            ):
                self._presence_cycle_counter = 0
                try:
                    self._last_presence_snap = self._observe_presence_bounded()
                except Exception as e:
                    logger.warning("Presence error: %s", e)

            # Git awareness — every ~5 minutes
            self._mark_cycle_stage("git_awareness")
            self._git_cycle_counter += 1
            if self._git_cycle_counter >= self.GIT_EVERY_N_CYCLES:
                self._git_cycle_counter = 0
                try:
                    self._last_git_context = git_context()
                    logger.debug("Git: %s", self._last_git_context[:80])
                except Exception as e:
                    logger.debug("Git context failed: %s", e)
                # Cache dirty-repo count for the perception-signature gate.
                try:
                    from skills.git_awareness import scan_all

                    self._last_git_dirty_count = sum(1 for r in scan_all() if r.get("is_dirty"))
                except Exception as e:
                    logger.debug("git dirty count update failed: %s", e)

            # GitHub legacy raw reader — every 10 cycles, dev-test-only.
            self._mark_cycle_stage("github_context")
            if self._github_legacy_enabled and self.github is not None:
                self._github_counter += 1
                if self._github_counter >= 10:
                    self._github_counter = 0
                    try:
                        self._last_github_block = self.github.get_context_block()
                    except Exception as e:
                        logger.debug("GitHub context failed: %s", e)

            # Reddit — every 15 cycles. After fetching the in-cycle
            # context block, persist newly-cached posts to raw memory
            # so audit pipelines can verify Maez's Reddit references.
            # 2026-04-27 incident: a TRELLIS.2 reference was correctly
            # surfaced in-cycle but invisible to audits because Reddit
            # signals weren't persisted. persist_to_memory closes that
            # gap; both sides of the fix have to land for the audit
            # path to see the signal.
            self._mark_cycle_stage("reddit_context")
            _cycle_memory_delta = False
            self._reddit_counter += 1
            if self._reddit_counter >= 15:
                self._reddit_counter = 0
                try:
                    self._last_reddit_block = self.reddit.get_context_block()
                except Exception as e:
                    logger.debug("Reddit context failed: %s", e)
                try:
                    written = self.reddit.persist_to_memory(
                        self.memory,
                        cycle=self.cycle_count,
                    )
                    if written:
                        _cycle_memory_delta = True
                        logger.info(
                            "reddit persistence: %d new posts to raw memory",
                            written,
                        )
                except Exception as e:
                    logger.debug("Reddit persist failed: %s", e)

            # Public bot context — every cycle
            try:
                self._mark_cycle_stage("public_context")
                self._last_public_context = self._get_public_context()
            except Exception as e:
                logger.debug("Public context failed: %s", e)

            # Evolution quality check — every 20 cycles
            self._mark_cycle_stage("evolution_check")
            if self.cycle_count % 20 == 0:
                try:
                    from skills.evolution_engine import check_and_revert

                    check_and_revert(self.memory, telegram_callback=send_dev)
                except Exception as e:
                    logger.debug("Evolution check failed: %s", e)

            # Disk cleanup check — every 2 hours, if disk > 75%
            self._mark_cycle_stage("disk_check")
            if self.cycle_count % 240 == 0 and snap["disk"].get("/", {}).get("percent", 0) > 75:
                try:
                    report = disk_scan()
                    if report["total_bytes"] > 100 * 1024 * 1024:
                        msg = disk_msg(report)
                        send_dev(msg)
                        self._pending_cleanup = report
                        logger.info(
                            "Disk cleanup proposed: %.0f MB", report["total_bytes"] / (1024 * 1024)
                        )
                except Exception as e:
                    logger.error("Disk scan failed: %s", e)

            # 2026-04-25 disk-fixation patches. See
            # core/cognition/perception_signature.py.
            #   Patch B: skip the LLM when perception axes match the
            #     last stored thought (with a 5-min floor).
            #   Patch A: when the LLM does run, strip stale fields
            #     (axes constant across last 3 thoughts) from the
            #     prompt so the model can't fixate on what it can't
            #     see.
            from core.cognition.perception_signature import (
                DEFAULT_MIN_THOUGHT_FLOOR,
                extract_axes,
                signature_from_axes,
                stale_fields,
            )

            self._mark_cycle_stage("perception_signature_gate")
            current_axes = extract_axes(
                snap,
                git_dirty_count=self._last_git_dirty_count,
            )
            current_sig = signature_from_axes(current_axes)
            last_sig = (
                signature_from_axes(self._recent_thought_axes[-1])
                if self._recent_thought_axes
                else None
            )
            _cycle_signal_key = _cycle_signal_availability_key(
                screen_obs=self._last_screen_obs,
                camera_state=self._camera_presence_state,
            )
            _cycle_signal_availability_delta = _cycle_signal_availability_changed(
                getattr(self, "_last_cycle_signal_availability_key", None),
                _cycle_signal_key,
            )
            self._last_cycle_signal_availability_key = _cycle_signal_key
            _cycle_salient_perception = _cycle_salient_perception_state(
                screen_obs=self._last_screen_obs,
                signal_availability_key=_cycle_signal_key,
            )

            _cycle_open_wants_count = _count_cycle_open_wants(self)
            _last_open_wants_count = getattr(self, "_last_cycle_open_wants_count", None)
            if _last_open_wants_count is None:
                _cycle_open_wants_delta = _cycle_open_wants_count
            else:
                _cycle_open_wants_delta = max(0, _cycle_open_wants_count - int(_last_open_wants_count))
            self._last_cycle_open_wants_count = _cycle_open_wants_count

            _cycle_scheduled_due = (
                self.cycle_count % 20 == 0
                or (
                    self.cycle_count % 240 == 0
                    and snap["disk"].get("/", {}).get("percent", 0) > 75
                )
            )
            _cycle_doorman_signals_bundle = _cycle_doorman_signals(
                current_axes=current_axes,
                last_thought_axes=(self._recent_thought_axes[-1] if self._recent_thought_axes else None),
                current_salient_perception=_cycle_salient_perception,
                last_salient_perception=getattr(
                    self,
                    "_last_cycle_doorman_salient_perception",
                    None,
                ),
                quiet_skips=self._cycles_since_last_thought,
                min_floor=DEFAULT_MIN_THOUGHT_FLOOR,
                new_failures=_cycle_action_failure_count(tier1_results + tier2_results),
                open_wants=_cycle_open_wants_delta,
                memory_delta=_cycle_memory_delta,
                signal_availability_changed=_cycle_signal_availability_delta,
                scheduled_due=_cycle_scheduled_due,
                presence=str(current_axes.get("presence", "unknown")),
            )
            _cycle_doorman_gate = _cycle_doorman_gate_decision(
                doorman_enabled=_cycle_doorman_enabled(),
                current_signature=current_sig,
                last_thought_signature=last_sig,
                quiet_skips=self._cycles_since_last_thought,
                min_floor=DEFAULT_MIN_THOUGHT_FLOOR,
                signals=_cycle_doorman_signals_bundle,
            )
            if _cycle_doorman_gate.doorman_enabled:
                self._last_cycle_doorman_salient_perception = _cycle_salient_perception
            if _cycle_doorman_gate.doorman_enabled and _cycle_doorman_gate.verdict is not None:
                _log_cycle_doorman_verdict(
                    verdict=_cycle_doorman_gate.verdict,
                    quiet_skips=self._cycles_since_last_thought,
                )
            if not _cycle_doorman_gate.wake:
                if _cycle_doorman_gate.doorman_enabled:
                    _log_cycle_doorman_skip(
                        gate_decision=_cycle_doorman_gate,
                        quiet_skips=self._cycles_since_last_thought,
                    )
                    logger.info(
                        "Cycle %d: HEARTBEAT_OK — doorman skipped (%s)",
                        self.cycle_count,
                        _cycle_doorman_gate.reason_code,
                    )
                else:
                    logger.info(
                        "Cycle %d: HEARTBEAT_OK — perception unchanged (gated)",
                        self.cycle_count,
                    )
                result = None
            else:
                # Patch A: which axes have been stable across the
                # last 3 stored thoughts AND this cycle? Strip them
                # from the prompt the LLM sees.
                stale = stale_fields(
                    list(self._recent_thought_axes),
                    current_axes,
                )
                if stale:
                    logger.info(
                        "Cycle %d: redacting stale fields %s",
                        self.cycle_count,
                        sorted(stale),
                    )
                _lean_idle_result = self._maybe_run_lean_idle_heartbeat(
                    snap,
                    _cycle_doorman_gate,
                )
                if _lean_idle_result is not None:
                    result = _lean_idle_result
                else:
                    self._mark_cycle_stage("reasoning_model")
                    try:
                        result = self._reason(snap, stale_fields=stale)
                    except BrainPreempted:
                        cycle_preempted = True
                        logger.info(
                            "Cycle %d: brain preempted by foreground; yielding cycle",
                            self.cycle_count,
                        )
                        self._s1b_flush_residue_events()
                        result = None
            if result is None:
                # Either gate skipped, or _reason couldn't run. No-op.
                _cycle_apply_quiet_counter_result(
                    self,
                    gate_decision=_cycle_doorman_gate,
                    result=result,
                )
                self._s1b_flush_residue_events()
                pass
            elif result.strip() == _HEARTBEAT_OK:
                # Nothing noteworthy this cycle — skip audit, storage, broadcast.
                # Storing fabricated prose is worse than storing nothing.
                logger.info("Cycle %d: HEARTBEAT_OK — silent cycle", self.cycle_count)
                _cycle_apply_quiet_counter_result(
                    self,
                    gate_decision=_cycle_doorman_gate,
                    result=result,
                )
                self._s1b_flush_residue_events()
                result = None
            else:
                # Self-claim audit on the cycle response BEFORE anything
                # else sees it. The cycle-prompt grounding fix (commit
                # 19cde77) dropped activity fabrication from ~100% to
                # ~20% of cycles; this detection net catches the
                # remaining slippage at output time and rewrites
                # before storage to raw memory. Transcript reflects
                # which activity-sources actually had data this cycle —
                # if screen/calendar signals are present,
                # narration is grounded and passes through; if absent,
                # activity_claim fires and rewrites.
                try:
                    self._mark_cycle_stage("response_audit")
                    _audit_transcript_parts = []
                    _cycle_signals_present = []
                    _cycle_signals_absent = []
                    # 2026-04-23 Commit 2: surface the explicit screen state
                    # (ok / disabled / unavailable / error) so the audit's
                    # grounding manifest distinguishes "tried and failed" from
                    # "deliberately off." Important for the proactive-opinion
                    # audit (summary of memory window, not live), and for
                    # daemon-cycle audits to correctly know that narration of
                    # activity is unsupported when vision is off by policy.
                    _screen_state = (
                        getattr(
                            self._last_screen_obs,
                            "state",
                            None,
                        )
                        if self._last_screen_obs is not None
                        else None
                    )
                    if _screen_state == "ok" and getattr(
                        self._last_screen_obs,
                        "success",
                        False,
                    ):
                        _audit_transcript_parts.append("✓ screen_observation: present")
                        _cycle_signals_present.append("screen observation")
                    elif _screen_state == "disabled":
                        _cycle_signals_absent.append("screen observation (disabled by policy)")
                    elif _screen_state == "unavailable":
                        _cycle_signals_absent.append("screen observation (endpoint unreachable)")
                    else:
                        _cycle_signals_absent.append("screen observation")
                    if self._last_calendar_snap is not None and getattr(
                        self._last_calendar_snap, "success", False
                    ):
                        _audit_transcript_parts.append("✓ calendar_snapshot: present")
                        _cycle_signals_present.append("calendar")
                    else:
                        _cycle_signals_absent.append("calendar")
                    _cycle_signals_present.append("system stats")
                    _audit_transcript = "\n".join(_audit_transcript_parts)
                    from core.self_claim_audit import audit as _sc_audit

                    _audit_result = _sc_audit(
                        result,
                        surface="daemon_cycle",
                        transcript=_audit_transcript,
                        signals_present=_cycle_signals_present,
                        signals_absent=_cycle_signals_absent,
                        evidence_envelope=getattr(
                            self,
                            "_last_cycle_evidence_envelope",
                            None,
                        ),
                    )
                    _buffer_cycle_audit_flags(_audit_result)
                    if _audit_result.rewritten:
                        logger.info(
                            "Cycle %d: audit rewrote fabrication (kinds=%s)",
                            self.cycle_count,
                            ",".join(sorted({f.kind for f in _audit_result.flags})),
                        )
                        self._s1b_note_residue_event("audit_rewrite")
                        result = _audit_result.text
                except Exception as _audit_err:
                    logger.debug(
                        "cycle-response audit failed (continuing): %s",
                        _audit_err,
                    )

                try:
                    self._metacognitive_watchdog.observe_tokens(result.split())
                except Exception as halt:
                    from core.health.metacognitive_watchdog import WatchdogHalt

                    if isinstance(halt, WatchdogHalt):
                        self._enter_watchdog_safe_standby(halt)
                        break
                    raise

                logger.info("Cycle %d response:\n%s", self.cycle_count, result)
                # Retain the daemon's actual last utterance in memory (bound
                # length) so the cockpit reads a real thought, not a log scrape.
                self._last_cycle_text = (result or "")[:2000]
                # Store response with full perception snapshot. Screen context
                # is v1a ephemeral-only: it may shape the in-cycle prompt, but
                # it is not appended to durable memory or metadata here.
                screen_activity = "unknown"
                focus_level = "unknown"

                next_event = "calendar_unavailable"

                full_thought = result

                self._s1b_flush_residue_events()

                mem_metadata = {
                    "cpu_pct": snap["cpu"]["percent"],
                    "ram_pct": snap["ram"]["percent"],
                    "gpu_pct": snap["gpu"]["utilization_pct"] if snap.get("gpu") else -1,
                    "gpu_temp": snap["gpu"]["temperature_c"] if snap.get("gpu") else -1,
                    "time_of_day": snap["time_of_day"],
                    "day_of_week": snap["day_of_week"],
                    "screen_activity": screen_activity,
                    "focus_level": focus_level,
                    "next_event": next_event,
                }
                self._mark_cycle_stage("memory_store")
                self.memory.store(
                    full_thought,
                    cycle=self.cycle_count,
                    snapshot=snap,
                    metadata=mem_metadata,
                    provenance_source="introspection",
                    trust_tier="lived",
                )

                # Broadcast cycle end with thought to UI
                self._ws_broadcast(
                    {
                        "type": "cycle_end",
                        "cycle": self.cycle_count,
                        "thought": result,
                    }
                )
                _s1b_optional_payload = self._s1b_optional_presentation_payload(result)
                if _s1b_optional_payload is not None:
                    self._ws_broadcast(_s1b_optional_payload)

                # 2026-04-25 fixation patches: thought stored — push
                # axes into history (Patch A's stale-field detector)
                # and reset the floor counter (Patch B's gate).
                self._recent_thought_axes.append(current_axes)
                _cycle_apply_quiet_counter_result(
                    self,
                    gate_decision=_cycle_doorman_gate,
                    result=result,
                )

            # Exploratory mind — advance one wondering with remaining budget.
            # _reason() ran first. If there's no room left in the cycle, the
            # wondering step skips this pass so the primary loop never degrades.
            try:
                self._mark_cycle_stage("wondering")
                cycle_deadline = cycle_start + LOOP_INTERVAL - 2.0
                if not cycle_preempted and time.time() < cycle_deadline - 10:
                    from daemon.wondering_cycle import advance_one

                    w_result = advance_one(self, deadline=cycle_deadline)
                    if w_result:
                        logger.info("Wondering advance: %s", w_result)
                    if _want_pursuit_enabled():
                        try:
                            from core.evolution import want_pursuit_bridge as _wpb
                            from core.evolution.wonderings import get_store as _w_get_store
                            from core.evolution.wants import is_hard_want as _is_hard_want

                            _w_store = _w_get_store()
                            _cards = self._want_pursuit_card_store()
                            if _cards is not None:
                                _wpb.maybe_propose_terminal(w_result, _w_store, _cards)
                                _wants = getattr(self, "wants", None)
                                if _wants is not None:
                                    _picked = _wpb.select_want(
                                        _wants,
                                        _w_store,
                                        _cards,
                                        cooldown_s=WANT_PURSUIT_COOLDOWN_S,
                                        now=time.time(),
                                        is_hard_want=_is_hard_want,
                                    )
                                    if _picked is not None:
                                        _wpb.seed_work_order(_w_store, _picked)
                        except Exception:
                            logger.warning(
                                "want-pursuit bridge step failed; skipping",
                                exc_info=True,
                            )
            except BrainPreempted:
                logger.info(
                    "Cycle %d: wondering preempted by foreground; yielding cycle",
                    self.cycle_count,
                )
                cycle_preempted = True
            except Exception as e:
                logger.debug("wondering cycle failed: %s", e)

            # Continuity checkpoint + orientation expiry
            self._mark_cycle_stage("continuity")
            if result:
                self._continuity_checkpoint_counter += 1
                if self._continuity_checkpoint_counter >= CONTINUITY_CHECKPOINT_INTERVAL:
                    self._continuity_checkpoint_counter = 0
                    try:
                        continuity_checkpoint(
                            last_thought={
                                "text": result[:200],
                                "cycle": self.cycle_count,
                            }
                        )
                    except Exception as e:
                        logger.debug("Continuity checkpoint failed: %s", e)

                # Expire continuity orientation
                if self._continuity_active:
                    self._continuity_cycles_remaining -= 1
                    if self._continuity_cycles_remaining <= 0:
                        self._continuity_active = False
                        self._continuity_capsule = None
                        try:
                            continuity_archive()
                        except Exception:
                            pass
                        logger.info("Continuity orientation complete. Resuming normal operation.")

            # Proactive search if thought shows knowledge gap
            self._mark_cycle_stage("proactive_search")
            if result:
                sq = self._should_search(result)
                if sq:
                    try:
                        from skills.web_search import search as _ws

                        sr = _ws(sq, max_results=2)
                        if sr.get("success") and sr["results"]:
                            self._proactive_search_context = (
                                f"[PROACTIVE SEARCH: '{sq}']\n  {sr['results'][0]['snippet'][:200]}"
                            )
                            logger.info("Proactive search queued: %s", sq[:60])
                    except Exception as e:
                        logger.debug("Proactive search failed: %s", e)

            # Check system thresholds for alerts (runs even if reasoning failed)
            self._mark_cycle_stage("threshold_alerts")
            self._check_and_alert(snap)

            # Follow-up delivery — every 5 cycles
            #
            # Session 11y: this path used to ask the LLM to "deliver on
            # your promise" given only the text of an earlier "I'll check"
            # phrase and the current perception snapshot. The LLM had no
            # grounded evidence and would fabricate a completion ("I've
            # finished installing maez-cli" for an install that never ran).
            # That was a direct trust-breaking failure.
            #
            # The new contract: get_pending() only returns rows with a
            # non-null action_id. For each one, look up the real action
            # result (outcome + output) from action_engine's action log
            # or pending list, and send a grounded report. If the action
            # hasn't completed yet, skip — try again next window. No LLM
            # role-play.
            self._mark_cycle_stage("followup_delivery")
            if self.cycle_count % 5 == 0:
                try:
                    self.followup_queue.expire_old()
                    pending = self.followup_queue.get_pending()
                    for fu in pending:
                        action_id = fu.get("action_id")
                        if not action_id:
                            continue
                        # Look up the real action outcome from the quality
                        # tracker (persisted across restarts) rather than
                        # re-asking the LLM what happened.
                        try:
                            from memory.quality_tracker import QualityTracker

                            qt = QualityTracker()
                            outcome = (
                                qt.get_outcome(action_id) if hasattr(qt, "get_outcome") else None
                            )
                        except Exception:
                            outcome = None
                        if not outcome or outcome.get("status") not in (
                            "executed",
                            "cancelled",
                            "failed",
                        ):
                            # Action still pending — wait for next window.
                            continue
                        status = outcome.get("status", "unknown")
                        output = (outcome.get("output") or outcome.get("error") or "").strip()[:600]
                        desc = fu.get("task", "the action you asked about")
                        if status == "executed":
                            msg = (
                                f"Done — {desc}\n\nResult: {output}" if output else f"Done — {desc}"
                            )
                        elif status == "cancelled":
                            msg = f"Cancelled — {desc}"
                        else:
                            msg = f"Failed — {desc}\n\n{output or 'No error detail.'}"
                        try:
                            self._send_telegram_notice(
                                msg,
                                source_ref="daemon:followup_queue",
                            )
                            self.followup_queue.mark_delivered(fu["id"])
                            logger.info(
                                "[FOLLOWUP] Delivered (grounded): %s → %s", action_id, status
                            )
                        except Exception as e:
                            logger.error("[FOLLOWUP] Delivery send failed: %s", e)
                except Exception as e:
                    logger.debug("Followup check failed: %s", e)

            # Proactive opinion — every 50 cycles
            self._mark_cycle_stage("proactive_opinion")
            if not cycle_preempted and self.cycle_count % 50 == 0:
                self._check_proactive_opinion()

            # Session 11o: dream cycle trigger. Fires when the owner has been
            # AFK for >30 min, rate-limited to >=10 min between dreams.
            # Runs in a BACKGROUND thread so the main 30s reasoning loop
            # never blocks on it — even under daemon/dream GPU contention
            # where a cycle can take 30-60s. The dream sets its own cooldown
            # timestamp at the top of run_dream_cycle (pre-work), so the
            # next loop tick sees should_run_now() == False and won't
            # re-spawn while an earlier dream is still in flight.
            try:
                self._mark_cycle_stage("dream_check")
                _now = time.time()
                if (
                    not cycle_preempted
                    and _dream_idle_gate_open(self, now=_now)
                    and self.dream.should_run_now(_now)
                ):
                    logger.info("Dream cycle triggered — idle gate open")

                    def _run_dream_bg():
                        try:
                            _insight = self.dream.run_dream_cycle()
                            if _insight:
                                logger.info("Dream insight: %s", _insight[:120])
                            # Session 11u: training self-evaluation
                            # (rate-limited to 1 per 24h inside the method)
                            _train_id = self.dream.maybe_propose_training()
                            if _train_id:
                                logger.info("Training proposal #%d submitted", _train_id)
                        except Exception as _e:
                            logger.error("Dream cycle worker failed: %s", _e)

                    # Slice 1.3: bounded singleton — submit() refuses if
                    # a previous worker is still in flight (cycle longer
                    # than DREAM_COOLDOWN_S) or if the daemon is shutting
                    # down. Cooldown gate above (should_run_now) is the
                    # cadence guard; this is the concurrency guard.
                    # NOTE on coupling: the cooldown gate's correctness
                    # depends on dream_state.run_dream_cycle() updating
                    # _last_dream_at at the START of the cycle (see
                    # core/evolution/dream_state.py:242). If that ever
                    # moves to the end of the cycle, this submit-skip
                    # behavior becomes load-bearing for re-spawn safety.
                    if not self._dream_worker.submit(_run_dream_bg):
                        logger.debug(
                            "Dream cycle skipped — previous worker "
                            "still running or daemon shutting down"
                        )
            except Exception as e:
                logger.debug("Dream cycle check failed: %s", e)

            _maybe_read_cycle_valence(
                self,
                gate_decision=_cycle_doorman_gate,
                open_wants_count=_cycle_open_wants_count,
                now=datetime.now(timezone.utc).isoformat(),
            )

            # Sleep in small increments so shutdown is responsive
            self._reset_cycle_failure_counter()
            self._mark_cycle_stage("cycle_sleep")
            for _ in range(LOOP_INTERVAL):
                if not self.running:
                    break
                time.sleep(1)

        logger.info("Reasoning loop stopped.")

    def start(self):
        """Start the daemon: verify model, launch loop and health server."""
        logger.info("=== Maez Daemon starting ===")
        from core.memory.recall_activation_config import log_activation_startup_state

        log_activation_startup_state()
        log_recall_stack_posture()
        self.boot_time = datetime.now(timezone.utc).isoformat()
        self._write_pid()

        # Verify LLM backend connectivity
        if not self._check_ollama():
            logger.error("Cannot reach LLM backend or model %s — aborting.", MODEL)
            self._remove_pid()
            sys.exit(1)
        # 2026-04-22: brain identity now comes from core.model_config
        # (/etc/maez/model.env), not a hardcoded string. Keeps this log
        # line honest as the primary model rotates. llm_client ignores
        # the model identifier for llamacpp — it uses the model the
        # server was started with — so this is cosmetic only, but a
        # wrong cosmetic is worse than no cosmetic.
        _backend = os.environ.get("MAEZ_LLM_BACKEND", "ollama").lower()
        if _backend == "llamacpp":
            try:
                from core.model_config import (
                    PRIMARY_MODEL as _pm,
                    PRIMARY_BASE_URL as _pb,
                )

                logger.info(
                    "Runtime brain confirmed: %s via llama.cpp (%s)",
                    _pm,
                    _pb,
                )
            except Exception as _mc_e:
                # self-dev review on 5d27884 flagged: import failure
                # here means model identity is unknown at startup —
                # a genuine anomaly. Warn so it surfaces in normal
                # log filtering without requiring debug level.
                logger.warning(
                    "Runtime brain confirmed: <model_config unavailable: %s>",
                    _mc_e,
                )
        else:
            logger.info("Model %s confirmed available.", MODEL)

        self.running = True

        # Connect action engine to Telegram and start bots
        self.telegram.actions = self.actions
        self.telegram.start()
        self.public_bot.start()

        # Vendored surface adapter in `skills/surface/` owns inbound
        # Telegram polling as of 2026-04-20. Legacy TelegramVoice
        # above keeps its loop alive only for outbound
        # `send_message()` / `_send_card_message()` calls from other
        # daemon subsystems. All safety rails still apply — the new
        # adapter's `MaezMessageHandler` routes through the same
        # decision pipeline + brain_loop + audit + organism blocks.
        #
        # `MAEZ_DISABLE_SURFACE_V2=1` is the kill switch for rollback.
        self._surface_v2_adapter = None
        self._surface_v2_loop = None
        self._surface_v2_thread = None
        if os.environ.get("MAEZ_DISABLE_SURFACE_V2") != "1":
            try:
                tg_token = self.telegram.token if self.telegram else None
                tg_user = self.telegram.authorized_user if self.telegram else None
                if tg_token and tg_user:
                    self._start_surface_v2(tg_token, tg_user)
                else:
                    logger.warning(
                        "Telegram token/user not available — surface "
                        "v2 will not start; messages will not reach Maez"
                    )
            except Exception as e:
                logger.warning("surface v2 bootstrap failed: %s", e)

        # Load continuity capsule BEFORE greeting/session-resume logic
        self._continuity_capsule = continuity_load()
        if self._continuity_capsule:
            self._continuity_active = True
            self._continuity_cycles_remaining = POST_RESTART_INJECTION_CYCLES
            logger.info(
                "Continuity active: %d orientation cycles, mode=%s",
                self._continuity_cycles_remaining,
                self._continuity_capsule.get("current_mode", "?"),
            )

        # Detect offline duration from last shutdown timestamp
        stats = self.memory.memory_stats()
        is_restart = stats["total"] > 0 and self.cycle_count == 0
        offline_seconds = 0
        last_shutdown = None

        try:
            if SHUTDOWN_FILE.exists():
                last_shutdown = datetime.fromisoformat(SHUTDOWN_FILE.read_text().strip())
                offline_seconds = (datetime.now(timezone.utc) - last_shutdown).total_seconds()
                logger.info(
                    "Last shutdown: %s (offline %.0fs)", last_shutdown.isoformat(), offline_seconds
                )
        except Exception as e:
            logger.warning("Could not read last shutdown time: %s", e)

        # Build startup message
        snap = perception_snapshot()
        gpu = snap.get("gpu") or {}

        if offline_seconds > 3600:
            hours = offline_seconds / 3600
            status_label = f"Maez back online. Was offline for {hours:.1f} hours."
        elif is_restart:
            status_label = "Maez restarted."
        else:
            status_label = "Maez online."

        startup_msg = (
            f"{status_label}\n"
            f"{snap['timestamp']}\n"
            f"CPU: {snap['cpu']['percent']}% | RAM: {snap['ram']['percent']}%\n"
            f"GPU: {gpu.get('utilization_pct', 'N/A')}% | {gpu.get('temperature_c', 'N/A')}°C\n"
            f"Memory: {stats['raw']} raw, {stats['daily']} daily, {stats['core']} core"
        )
        time.sleep(2)
        if not self._continuity_active:
            send_dev(startup_msg)
        else:
            logger.info("Startup message suppressed — continuity orientation active")

        # Check if daily consolidation was missed while offline
        self._missed_consolidation = False
        if last_shutdown and offline_seconds > 3600:
            now_local = datetime.now().astimezone()
            shutdown_local = last_shutdown.astimezone()
            # Check if 3:00 AM passed between shutdown and now
            check = shutdown_local.replace(hour=3, minute=0, second=0, microsecond=0)
            if check <= shutdown_local:
                check += timedelta(days=1)
            if check <= now_local:
                # 3 AM was missed — check if consolidation exists for that date
                missed_date = check.strftime("%Y-%m-%d")
                has_consolidation = False
                try:
                    daily_results = self.memory.daily.get(include=["metadatas"])
                    for meta in daily_results.get("metadatas", []):
                        if meta.get("date") == missed_date:
                            has_consolidation = True
                            break
                except Exception:
                    pass

                if not has_consolidation:
                    self._missed_consolidation = True
                    logger.info("Missed consolidation for %s — will run on startup", missed_date)

        # Start reasoning loop in background thread. The target is an external
        # supervisor around the historical loop body, so a stage exception
        # cannot kill cognition while leaving the daemon process alive.
        loop_thread = threading.Thread(
            target=self._run_reasoning_loop_supervised,
            daemon=True,
            name="reasoning-loop",
        )
        self._reasoning_loop_thread = loop_thread
        loop_thread.start()
        self._start_cognition_liveness_sentinel()

        # Start daily consolidation thread (3:00 AM)
        consol_thread = threading.Thread(
            target=self._consolidation_loop, daemon=True, name="consolidation"
        )
        consol_thread.start()

        # Start nightly journal thread (11:00 PM)
        journal_thread = threading.Thread(
            target=self._nightly_journal_loop, daemon=True, name="journal"
        )
        journal_thread.start()

        # D20 Stage-5: hourly capability-acquisition planner poller.
        # Walks the queue, generates integration plans, surfaces
        # them for owner review via PendingCard. Failure-isolated
        # in its own thread so a planner exception never affects
        # the reasoning loop or consolidation.
        planning_thread = threading.Thread(
            target=self._capability_planning_loop,
            daemon=True,
            name="capability-planning",
        )
        planning_thread.start()

        # Start proposal worker thread
        try:
            from skills.evolution_engine import start_proposal_worker

            start_proposal_worker()
        except Exception as e:
            logger.debug("Proposal worker start failed: %s", e)

        # Start soul.md hot-reload watcher
        threading.Thread(target=self._watch_soul, daemon=True, name="soul-watcher").start()

        # Start WebSocket server
        ws_thread = threading.Thread(target=self._run_ws_server, daemon=True, name="ws-server")
        ws_thread.start()

        # Start health broadcast thread
        hb_thread = threading.Thread(
            target=self._start_health_broadcast, daemon=True, name="health-broadcast"
        )
        hb_thread.start()

        # Voice disabled — re-enable when voice pipeline is stable
        VOICE_ENABLED = False
        if VOICE_ENABLED:
            # Voice output — Kokoro TTS
            if voice_output_init():
                logger.info("Voice output online")
                speak("Maez is online.")
            else:
                logger.warning("Voice output unavailable")

            # Unified audio pipeline — wake word + transcription on single mic stream
            def _on_voice_command(text: str):
                """Called by unified pipeline with transcribed command text."""
                with self._voice_lock:
                    if self._voice_active:
                        return
                    self._voice_active = True

                logger.info("Voice command received: '%s'", text)

                def _handle():
                    try:
                        clean = text.lower()
                        text_cmd = text
                        for phrase in [
                            "hey maez",
                            "hey maze",
                            "hey maz",
                            "maez",
                            "maze",
                            "hey jarvis",
                        ]:
                            if clean.startswith(phrase):
                                text_cmd = text[len(phrase) :].strip(" ,.!?")
                                break

                        if not text_cmd:
                            text_cmd = "status"

                        logger.info("Processing voice command: '%s'", text_cmd)
                        self.handle_voice_stream(text_cmd)
                    except Exception as e:
                        logger.error("Voice handler error: %s", e)
                    finally:
                        with self._voice_lock:
                            self._voice_active = False

                threading.Thread(target=_handle, daemon=True, name="maez-voice-handler").start()

            if wake_word_start(_on_voice_command):
                logger.info("Unified audio pipeline active — say 'Hey Maez'")
            else:
                logger.warning("Audio pipeline unavailable")
        else:
            logger.info("Voice pipeline disabled — set VOICE_ENABLED=True to re-enable")

        # Start health check server (blocks main thread)
        logger.info("Health endpoint starting on port %d", HEALTH_PORT)
        self._run_health_server()

    def _start_surface_v2(self, token: str, authorized_user: int) -> None:
        """Spin up the vendored TelegramAdapter on its own asyncio loop
        in a daemon thread. Mirrors the legacy start() threading shape
        so the two paths have identical lifecycle semantics."""
        import asyncio as _asyncio
        import threading as _threading
        from skills.surface.maez_adapter import build_telegram_adapter

        def _runner():
            try:
                # Attach a handler to the root logger so INFO-level logs
                # from vendored modules (httpx, telegram.ext,
                # skills.surface.*) surface in the daemon log. The
                # daemon's own handlers are attached to the "maez"
                # logger only, so without this, everything outside
                # that namespace silently drops.
                import logging as _lg

                _root = _lg.getLogger()
                if not _root.handlers:
                    _h = _lg.StreamHandler()
                    _h.setFormatter(
                        _lg.Formatter(
                            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S",
                        )
                    )
                    _root.addHandler(_h)
                    _root.setLevel(_lg.INFO)
                # Scope noise: vendored HTTP/telegram stacks talk a lot
                # at INFO (every poll = 2 httpx lines). We only need
                # WARNING from them — errors still surface, the routine
                # "POST getUpdates 200 OK" chatter doesn't. Maez and
                # skills.surface stay at INFO for visibility.
                for _name in (
                    "httpx",
                    "httpcore",
                    "telegram",
                    "telegram.ext",
                    "telegram.ext.Application",
                    "telegram.ext.Updater",
                ):
                    _lg.getLogger(_name).setLevel(_lg.WARNING)

                async def _run():
                    adapter = build_telegram_adapter(
                        token=token,
                        authorized_users=[int(authorized_user)],
                        daemon=self,
                    )
                    self._surface_v2_adapter = adapter
                    try:
                        ok = await adapter.connect()
                    except Exception as ce:
                        logger.exception("surface v2 connect() raised: %s", ce)
                        return
                    if not ok:
                        logger.warning("surface v2 connect() returned False")
                        return
                    import asyncio as __a

                    self._surface_v2_loop = __a.get_running_loop()
                    logger.info("surface v2 live (tasks=%d)", len(__a.all_tasks()))
                    _hb = 0
                    while self.running:
                        await _asyncio.sleep(1.0)
                        _hb += 1
                        if _hb % 60 == 0:
                            logger.info(
                                "surface v2 heartbeat: %dm uptime",
                                _hb // 60,
                            )
                    try:
                        await adapter.disconnect()
                    except Exception as e:
                        logger.debug("surface v2 disconnect: %s", e)

                # asyncio.run() manages the loop lifecycle correctly
                # for this thread; manual loop management caused PTB
                # polling tasks to be scheduled but never fire HTTP.
                _asyncio.run(_run())
            except Exception as e:
                logger.exception("surface v2 runner crashed: %s", e)

        self._surface_v2_thread = _threading.Thread(
            target=_runner,
            daemon=True,
            name="surface-v2",
        )
        self._surface_v2_thread.start()

    def stop(self, signum=None, frame=None):
        """Graceful shutdown."""
        if self._shutdown_started.is_set():
            logger.info("Shutdown already in progress; ignoring duplicate signal %s", signum)
            return
        self._shutdown_started.set()
        logger.info("=== Maez Daemon shutting down (signal: %s) ===", signum)
        self.running = False
        # Write continuity capsule before anything else
        try:
            continuity_shutdown()
        except Exception as e:
            logger.debug("Continuity shutdown write failed: %s", e)
        try:
            wake_word_stop()
            voice_output_shutdown()
        except Exception:
            pass  # Voice may not be initialized
        # Slice 1.3: bounded shutdown of dream worker. Wait up to 5s
        # for an in-flight dream cycle to finish (writes to memory.db
        # mid-cycle would otherwise tear). After this, submit() refuses
        # any stale callers that might still be in the loop's tail.
        try:
            if not self._dream_worker.shutdown(timeout=5.0):
                logger.warning("Dream worker did not finish within shutdown timeout")
        except Exception as e:
            logger.debug("Dream worker shutdown failed: %s", e)
        try:
            if not self._presence_worker.shutdown(timeout=1.0):
                logger.warning("Presence worker did not finish within shutdown timeout")
                self._camera_presence_state = self._camera_presence_state.unavailable(
                    error_class="native_shutdown_timeout",
                )
        except Exception as e:
            logger.debug("Presence worker shutdown failed: %s", e)
        try:
            if not self._ensure_recall_shadow_worker().shutdown(timeout=1.0):
                logger.warning("Recall shadow worker did not finish within shutdown timeout")
        except Exception as e:
            logger.debug("Recall shadow worker shutdown failed: %s", e)
        try:
            if self._presence_native_initialized:
                from skills.presence_perception import shutdown as presence_shutdown

                presence_shutdown()
        except Exception as e:
            logger.debug("Presence native shutdown failed: %s", e)
        try:
            self.telegram.stop()
        except Exception as e:
            logger.debug("Telegram bot stop failed: %s", e)
        # Stop the v2 surface adapter if we launched it.
        #
        # T1.9 hygiene (Codex deploy verification 2026-05-04 + 05):
        # The morning's fix (10220d9) added a thread.join(timeout=5)
        # after `_loop.call_soon_threadsafe(_loop.stop)` to bound
        # the shutdown wait. Live deploy verification confirmed
        # the join didn't actually prevent the surface-v2
        # traceback — `_loop.stop()` interrupts the runner's
        # `await _asyncio.sleep(1.0)` mid-await, asyncio.run()
        # raises RuntimeError("Event loop stopped before Future
        # completed"), and only THEN does the join sit for an
        # already-dead thread.
        #
        # The runner already cooperates: its `while self.running:`
        # loop exits within ≤1s on the next sleep boundary. The
        # explicit loop.stop() is redundant and harmful — it
        # produces the traceback without giving the runner time
        # to exit cleanly via `await adapter.disconnect()`. We
        # keep the thread.join (still load-bearing — bounds the
        # wait against systemd SIGKILL) but drop the loop.stop.
        #
        # If the runner ever hangs past 5s in a future bug
        # (e.g. adapter.disconnect awaiting hung network I/O),
        # the join's WARNING surfaces it and a force-stop can be
        # reintroduced THEN with explicit RuntimeError handling
        # inside the runner. Today the cooperative path is
        # sufficient and quiet.
        try:
            _thread = getattr(self, "_surface_v2_thread", None)
            if _thread is not None and _thread.is_alive():
                _thread.join(timeout=5.0)
                if _thread.is_alive():
                    logger.warning(
                        "surface_v2 thread did not exit within "
                        "5s of self.running=False — runner may be "
                        "blocked on adapter shutdown; connections "
                        "may leak"
                    )
        except Exception as e:
            logger.debug("surface v2 stop failed: %s", e)
        try:
            self.public_bot.stop()
        except Exception as e:
            logger.debug("Public bot stop failed: %s", e)
        # Slice 1.6: shut down the shared ThreadPoolExecutor AFTER all
        # surfaces (telegram, surface_v2, public_bot) have stopped
        # submitting. Placing it earlier could leave a late submission
        # racing the shutdown and raising
        # RuntimeError: cannot schedule new futures after shutdown.
        #
        # wait=False: a sync LLM call wedged on a dead llama.cpp would
        # block stop() forever with wait=True. With wait=False, the
        # daemon proceeds with the rest of the shutdown ladder; the
        # stuck workers remain in the process until either they
        # complete naturally or systemd's TimeoutStopSec sends SIGKILL.
        #
        # cancel_futures=True: queued (not-yet-running) work is
        # dropped immediately. Running sync work cannot be cancelled
        # in Python.
        try:
            from core.health.shared_executor import shutdown_shared_executor

            shutdown_shared_executor(wait=False, cancel_futures=True)
        except Exception as e:
            logger.debug("Shared executor shutdown failed: %s", e)
        try:
            if self._ws_loop is not None:
                self._ws_loop.call_soon_threadsafe(self._ws_loop.stop)
        except Exception as e:
            logger.debug("WebSocket loop stop failed: %s", e)
        try:
            if self._health_server is not None:

                def _shutdown_health():
                    try:
                        self._health_server.shutdown()
                    except Exception as inner:
                        logger.debug("Health server shutdown failed: %s", inner)

                threading.Thread(
                    target=_shutdown_health,
                    name="health-server-shutdown",
                    daemon=True,
                ).start()
        except Exception as e:
            logger.debug("Health server stop trigger failed: %s", e)
        try:
            self.memory.close()
        except Exception as e:
            logger.debug("Memory manager close failed: %s", e)
        try:
            SHUTDOWN_FILE.write_text(datetime.now(timezone.utc).isoformat())
        except OSError:
            pass
        self._remove_pid()
        # When stop() is invoked by SIGTERM/SIGINT, the graceful ladder
        # above has already written continuity, stopped surfaces, closed
        # memory clients, and removed the PID. Native libraries such as
        # Chroma's Tokio/SQLx runtime can still keep non-Python workers
        # alive after Python work is complete. Exit the process explicitly
        # so systemd records a clean stop instead of escalating to SIGKILL.
        if signum is not None:
            logging.shutdown()
            os._exit(0)

    def _run_health_server(self):
        """Minimal Flask health check endpoint."""
        app = Flask("maez-health")

        @app.before_request
        def local_origin_write_guard():
            return reject_untrusted_browser_write(request)

        @app.after_request
        def cors(response):
            return apply_local_cors_headers(response, request)

        # Suppress Flask request logging — we have our own
        logging.getLogger("werkzeug").setLevel(logging.WARNING)

        @app.route("/health")
        def health():
            snap = perception_snapshot()
            gpu = snap.get("gpu") or {}
            _memory_stats = self.memory.memory_stats()
            _reasoning_loop = self._cycle_heartbeat_health()
            _camera_presence = self._camera_presence_health()
            _desktop_presence = self._desktop_presence_health()
            _system = {
                "cpu_percent": snap["cpu"]["percent"],
                "ram_percent": snap["ram"]["percent"],
                "gpu_percent": gpu.get("utilization_pct"),
                "gpu_temp_c": gpu.get("temperature_c"),
            }
            return jsonify(
                {
                    "status": self._health_status_from_reasoning_loop(_reasoning_loop),
                    "model": MODEL,
                    "boot_time": self.boot_time,
                    "cycle_count": self.cycle_count,
                    "last_cycle": self.last_cycle_time,
                    "reasoning_loop": _reasoning_loop,
                    "resource_forensics": getattr(self, "_last_fd_forensics", {}) or {},
                    "metacognitive_watchdog": self._watchdog_health(),
                    "uptime_seconds": int(
                        time.time() - datetime.fromisoformat(self.boot_time).timestamp()
                    ),
                    "memory": _memory_stats,
                    "lived_episodes": {
                        "staleness": self._m1_staleness_health(),
                        "m1": self._m1_status_health(),
                    },
                    "calendar": self._calendar_health(),
                    "github_v1": self._github_health(),
                    "camera_presence": _camera_presence,
                    "credentials": _credential_health(),
                    "temporal_spine": temporal_spine_health(),
                    "clinical_boundary": clinical_boundary_health(),
                    "voice_continuity": self._voice_continuity_health(),
                    "successor_governance": successor_governance_health(),
                    "system": _system,
                    "body": self._body_health(
                        camera_presence=_camera_presence,
                        desktop_presence=_desktop_presence,
                        memory_stats=_memory_stats,
                        reasoning_loop=_reasoning_loop,
                        system=_system,
                    ),
                }
            )

        @app.route("/internal/cockpit/state")
        def cockpit_state():
            if not _s7_internal_channel_trusted(request):
                return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 403
            # FAST real-state read for the cockpit face: true-by-construction
            # off the daemon's retained in-memory attrs. No perception_snapshot
            # / nvidia-smi here (that is what keeps /health ~1.7s). Never
            # fabricates mood/uncertainty — they have no organ, so they are
            # omitted entirely.
            return jsonify(_build_cockpit_state(self))

        @app.route("/operator/health")
        def operator_health():
            payload = dict(self._operator_health())
            payload["metacognitive_watchdog"] = self._watchdog_health(operator=True)
            return jsonify(payload)

        @app.route("/internal/s7/webauthn/status", methods=["GET"])
        def s7_webauthn_status():
            service = S7LocalWebAuthnCeremonyService(
                verifier=S7ProductionWebAuthnVerifier(),
                store_factory=lambda: S7WebAuthnBootstrapStore(_s7_webauthn_store_root()),
            )
            result = service.status(now=datetime.now(timezone.utc).isoformat())
            return jsonify(result.body), result.status_code

        @app.route("/internal/s7/webauthn/register/begin", methods=["POST"])
        def s7_webauthn_register_begin():
            if live_webauthn_ceremony_enabled():
                if not _s7_internal_channel_trusted(request):
                    return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 403
                _record_owner_interaction(self)
                now = datetime.now(timezone.utc).isoformat()
                store = S7WebAuthnBootstrapStore(_s7_webauthn_store_root())
                authorization = _s7_backup_registration_authorization(
                    self,
                    request,
                    now=now,
                    store=store,
                )
                if authorization.ok is not True:
                    return jsonify(authorization.body), authorization.status_code
                service = S7LocalWebAuthnCeremonyService(
                    verifier=S7ProductionWebAuthnVerifier(),
                    store_factory=lambda: store,
                )
                result = service.register_begin(
                    now=now,
                    request_json=request.get_json(silent=True) or {},
                    s7_execution_authorization=authorization.kwargs["s7_execution_authorization"],
                )
                return jsonify(result.body), result.status_code
            return jsonify(
                s7_ceremony_deferred_response(
                    surface="daemon",
                    route="/internal/s7/webauthn/register/begin",
                )
            ), 503

        @app.route("/internal/s7/webauthn/register/finish", methods=["POST"])
        def s7_webauthn_register_finish():
            if live_webauthn_ceremony_enabled():
                if not _s7_internal_channel_trusted(request):
                    return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 403
                _record_owner_interaction(self)
                service = S7LocalWebAuthnCeremonyService(
                    verifier=S7ProductionWebAuthnVerifier(),
                    store_factory=lambda: S7WebAuthnBootstrapStore(_s7_webauthn_store_root()),
                )
                result = service.register_finish(
                    now=datetime.now(timezone.utc).isoformat(),
                    request_json=request.get_json(silent=True) or {},
                )
                return jsonify(result.body), result.status_code
            return jsonify(
                s7_ceremony_deferred_response(
                    surface="daemon",
                    route="/internal/s7/webauthn/register/finish",
                )
            ), 503

        @app.route("/internal/s7/webauthn/register/backup-card", methods=["POST"])
        def s7_webauthn_register_backup_card():
            if live_webauthn_ceremony_enabled():
                if not _s7_internal_channel_trusted(request):
                    return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 403
                _record_owner_interaction(self)
                result = _s7_create_backup_registration_card(self)
                return jsonify(result.body), result.status_code
            return jsonify(
                s7_ceremony_deferred_response(
                    surface="daemon",
                    route="/internal/s7/webauthn/register/backup-card",
                )
            ), 503

        @app.route("/internal/s7/webauthn/proof/disable-card", methods=["POST"])
        def s7_webauthn_proof_disable_card():
            if live_webauthn_ceremony_enabled():
                if not _s7_internal_channel_trusted(request):
                    return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 403
                _record_owner_interaction(self)
                if not _s7_webauthn_proof_routes_enabled():
                    return jsonify({"ok": False, "error": "s7_proof_route_disabled"}), 404
                result = _s7_create_disable_credential_card(
                    self,
                    request,
                    now=datetime.now(timezone.utc).isoformat(),
                )
                return jsonify(result.body), result.status_code
            return jsonify(
                s7_ceremony_deferred_response(
                    surface="daemon",
                    route="/internal/s7/webauthn/proof/disable-card",
                )
            ), 503

        @app.route("/internal/s7/webauthn/proof/disable-credential", methods=["POST"])
        def s7_webauthn_proof_disable_credential():
            if live_webauthn_ceremony_enabled():
                if not _s7_internal_channel_trusted(request):
                    return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 403
                _record_owner_interaction(self)
                if not _s7_webauthn_proof_routes_enabled():
                    return jsonify({"ok": False, "error": "s7_proof_route_disabled"}), 404
                store = S7WebAuthnBootstrapStore(_s7_webauthn_store_root())
                result = _s7_disable_credential_for_proof(
                    self,
                    request,
                    now=datetime.now(timezone.utc).isoformat(),
                    store=store,
                )
                return jsonify(result.body), result.status_code
            return jsonify(
                s7_ceremony_deferred_response(
                    surface="daemon",
                    route="/internal/s7/webauthn/proof/disable-credential",
                )
            ), 503

        @app.route("/internal/s7/cards/<request_id>/webauthn/begin", methods=["POST"])
        def s7_webauthn_authorize_begin(request_id: str):
            if live_webauthn_ceremony_enabled():
                if not _s7_internal_channel_trusted(request):
                    return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 403
                _record_owner_interaction(self)
                now = datetime.now(timezone.utc).isoformat()
                store = S7WebAuthnBootstrapStore(_s7_webauthn_store_root())
                material = _s7_authorization_route_material(
                    self,
                    request,
                    request_id=request_id,
                    now=now,
                    store=store,
                )
                if material.ok is not True:
                    return jsonify(material.body), material.status_code
                service = S7LocalWebAuthnCeremonyService(
                    verifier=S7ProductionWebAuthnVerifier(),
                    store_factory=lambda: store,
                )
                result = service.authorize_begin(
                    now=now,
                    rendered_statement=material.kwargs["rendered_statement"],
                    precondition_hash=material.kwargs["precondition_hash"],
                    session_binding=material.kwargs["session_binding"],
                    internal_channel_binding=material.kwargs["internal_channel_binding"],
                    allow_degraded_primary_only=material.kwargs["allow_degraded_primary_only"],
                    allow_degraded_backup_only=material.kwargs["allow_degraded_backup_only"],
                )
                if (
                    result.status_code == 200
                    and material.kwargs["envelope"].derived_work_class
                    in VOICE_SEAT_WORK_CLASSES
                ):
                    if not _s7_persist_voice_source_bundle_for_material(
                        store=store,
                        material=material,
                        now=now,
                    ):
                        return jsonify(
                            {
                                "ok": False,
                                "error": "s7_guarded_source_bundle_required",
                                "detail": "source_bundle_unavailable",
                            }
                        ), 409
                    result.body.update(_s7_founder_visible_voice_payload_for_material(material))
                return jsonify(result.body), result.status_code
            return jsonify(
                s7_ceremony_deferred_response(
                    surface="daemon",
                    route=f"/internal/s7/cards/{request_id}/webauthn/begin",
                )
            ), 503

        @app.route("/internal/s7/cards/<request_id>/webauthn/finish", methods=["POST"])
        def s7_webauthn_authorize_finish(request_id: str):
            if live_webauthn_ceremony_enabled():
                if not _s7_internal_channel_trusted(request):
                    return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 403
                _record_owner_interaction(self)
                now = datetime.now(timezone.utc).isoformat()
                store = S7WebAuthnBootstrapStore(_s7_webauthn_store_root())
                material = _s7_authorization_route_material(
                    self,
                    request,
                    request_id=request_id,
                    now=now,
                    store=store,
                )
                if material.ok is not True:
                    return jsonify(material.body), material.status_code
                voice_source = _s7_route_material()
                if (
                    material.kwargs["envelope"].derived_work_class
                    in VOICE_SEAT_WORK_CLASSES
                ):
                    if not _s7_founder_seen_voice_hash_valid(material, store=store):
                        return jsonify(
                            {
                                "ok": False,
                                "error": "s7_founder_seen_maez_voice_hash_required",
                            }
                        ), 409
                    voice_source = _s7_voice_source_validation_for_material(
                        store=store,
                        material=material,
                        now=now,
                    )
                    validation = voice_source.kwargs["source_bundle_validation"]
                    valid_absent = (
                        validation.status == "valid_absent"
                        and validation.source_bundle_valid is True
                        and validation.mint_eligible is True
                        and validation.authority_projection == "valid_absent"
                        and validation.failure_reason_code is None
                    )
                    grounded_refusal = (
                        validation.status == "blocking_present"
                        and validation.source_bundle_valid is True
                        and validation.mint_eligible is False
                        and validation.authority_projection == "grounded_refusal"
                        and validation.failure_reason_code is None
                    )
                    if not (valid_absent or grounded_refusal):
                        return jsonify(
                            {
                                "ok": False,
                                "error": "s7_guarded_source_bundle_required",
                                "detail": validation.status,
                            }
                        ), 409
                service = S7LocalWebAuthnCeremonyService(
                    verifier=S7ProductionWebAuthnVerifier(),
                    store_factory=lambda: store,
                )
                result = service.authorize_finish(
                    now=now,
                    envelope=material.kwargs["envelope"],
                    rendered_statement=material.kwargs["rendered_statement"],
                    precondition_hash=material.kwargs["precondition_hash"],
                    maez_voice_consultation=material.kwargs["maez_voice_consultation"],
                    session_binding=material.kwargs["session_binding"],
                    internal_channel_binding=material.kwargs["internal_channel_binding"],
                    request_json=material.kwargs["request_json"],
                    guarded_store=voice_source.kwargs.get("guarded_store"),
                    source_bundle_validation=voice_source.kwargs.get("source_bundle_validation"),
                    source_ref_hash=voice_source.kwargs.get("source_ref_hash"),
                    reservation_token=voice_source.kwargs.get("reservation_token"),
                )
                return jsonify(result.body), result.status_code
            return jsonify(
                s7_ceremony_deferred_response(
                    surface="daemon",
                    route=f"/internal/s7/cards/{request_id}/webauthn/finish",
                )
            ), 503

        @app.route("/internal/s7/cards/<request_id>/execute", methods=["POST"])
        def s7_guarded_card_execute(request_id: str):
            if live_webauthn_ceremony_enabled():
                if not _s7_internal_channel_trusted(request):
                    return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 403
                _record_owner_interaction(self)
                now = datetime.now(timezone.utc).isoformat()
                store = S7WebAuthnBootstrapStore(_s7_webauthn_store_root())
                authorization = _s7_guarded_card_execution_authorization(
                    self,
                    request,
                    request_id=request_id,
                    now=now,
                    store=store,
                )
                if authorization.ok is not True:
                    return jsonify(authorization.body), authorization.status_code
                pipe = _s7_route_pipeline_for_daemon(self)
                if pipe is None or getattr(pipe, "card_store", None) is None:
                    return jsonify({"ok": False, "error": "s7_execution_edge_unavailable"}), 503
                card = pipe.card_store.get(request_id)
                if card is None:
                    return jsonify({"ok": False, "error": "s7_request_not_found"}), 404
                if not callable(getattr(pipe, "_is_pending_dialog_card", None)):
                    return jsonify({"ok": False, "error": "s7_execution_edge_unavailable"}), 503
                if pipe._is_pending_dialog_card(card) is not True:
                    return jsonify(
                        {
                            "ok": False,
                            "error": "s7_narrow_path_required",
                            "detail": "S7.3 live execution is limited to founder-present self-mod dialog cards",
                        }
                    ), 409
                result = pipe._handle_pending_dialog_input(
                    card=card,
                    text=authorization.kwargs["text"],
                    user_id=getattr(card, "user_id", None) or "owner",
                    s7_execution_authorization=authorization.kwargs[
                        "s7_execution_authorization"
                    ],
                )
                if result is None:
                    return jsonify({"ok": False, "error": "s7_execution_unrelated"}), 409
                status = getattr(getattr(result, "status", None), "value", str(getattr(result, "status", "")))
                ok = status == "executed" and bool(getattr(result, "execution_success", False))
                status_code = 200 if ok else 409
                return jsonify(
                    {
                        "ok": ok,
                        "status": status,
                        "message": getattr(result, "message", ""),
                        "output": (getattr(result, "execution_output", "") or "")[:2000],
                        "error": getattr(result, "execution_error", None),
                    }
                ), status_code
            return jsonify(
                s7_ceremony_deferred_response(
                    surface="daemon",
                    route=f"/internal/s7/cards/{request_id}/execute",
                )
            ), 503

        @app.route("/internal/limb/reddit/session", methods=["POST"])
        def reddit_limb_session():
            # auth-before-envelope: handle_handoff checks the secret BEFORE
            # body_loader() is ever called, so the token-bearing JSON body is
            # not read on an auth failure.
            tile, status = _reddit_limb_mod.handle_handoff(
                headers=request.headers,
                body_loader=lambda: request.get_json(silent=True) or {},
                limb=_REDDIT_LIMB,
            )
            return jsonify(tile), status

        @app.route("/internal/limb/github/session", methods=["POST"])
        def github_limb_session():
            # auth-before-envelope (same as reddit): handle_handoff verifies the
            # secret BEFORE body_loader() reads the token-bearing JSON body.
            tile, status = _github_limb_mod.handle_handoff(
                headers=request.headers,
                body_loader=lambda: request.get_json(silent=True) or {},
                limb=_GITHUB_LIMB,
            )
            return jsonify(tile), status

        @app.route("/internal/limb/github/ingest", methods=["POST"])
        def github_limb_ingest():
            result, status = _github_v1_mod.handle_ingest(
                headers=request.headers,
                mode=self._github_mode,
                limb=_GITHUB_LIMB,
                store=self._github_store,
                memory=self.memory,
                fetch_batch_id_factory=lambda: f"fb-{uuid.uuid4().hex[:12]}",
            )
            return jsonify(result), status

        @app.route("/message", methods=["POST"])
        def message():
            if not _s7_internal_channel_trusted(request):
                return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 403
            data = request.get_json(silent=True) or {}
            text = data.get("text", "").strip()
            if not text:
                return jsonify({"error": "empty message"}), 400
            # Accept optional history list ({role, content} dicts) so
            # the UI can thread prior turns into synthesis. Without
            # this, "Hi" mid-session re-greets because handle_message
            # has no chat_history. Each adjacent (user, assistant)
            # pair becomes one chat_history entry in the
            # "<display>: <msg>\nMaez: <reply>" shape that
            # core.brain.conversation_history.history_to_messages
            # expects. 2026-04-27 incident fix.
            raw_history = data.get("history") or []
            chat_history = _pair_history_for_chat_threading(raw_history) if raw_history else None
            # SLICE 2 strangler seam — flag-gated delegation to the
            # surface-agnostic inbound core. DEFAULT OFF. When ON, the cockpit
            # routes through run_inbound_turn so the S4 clinical boundary fires
            # on the cockpit owner surface (which source="UI" silently bypassed)
            # and synthesis runs the unified path. Minimal scope: no M1
            # PROMOTION (cockpit is excluded from M1_ALLOWED_PROMOTION_SOURCES);
            # raw conversation is still stored as ordinary lived memory, same as
            # the legacy UI path — whether cockpit should write lived memory at
            # all is an open owner covenant decision. Felt-time OFF, NO
            # cards/proposals/search/tools (get_pipeline=action_engine=None).
            # When OFF (default), the existing source="UI" path runs UNTOUCHED.
            if cockpit_core_enabled():
                from daemon.inbound_core import run_inbound_turn

                # The Flask route is sync; run_inbound_turn is async. asyncio.run
                # creates and manages a fresh event loop for this turn (no daemon
                # loop is running on the Flask request thread); inside the
                # coroutine, run_inbound_turn's own asyncio.get_event_loop()
                # returns that running loop for its run_in_executor offloads.
                owner_authenticated = (
                    request.headers.get(_OWNER_AUTHENTICATED_HEADER) == "1"
                )
                descriptor = _build_cockpit_inbound_descriptor(
                    self,
                    text=text,
                    chat_history=chat_history,
                    owner_authenticated=owner_authenticated,
                )
                # Degrade honestly: an S4/early exception from run_inbound_turn
                # (before its own internal try/except wraps synthesis) returns a
                # JSON error rather than a raw 500 traceback — mirrors the
                # internal-error handling inside run_inbound_turn.
                try:
                    reply = asyncio.run(run_inbound_turn(**descriptor))
                except Exception:
                    logger.warning("cockpit inbound core turn failed", exc_info=True)
                    return jsonify({"reply": "(internal error)"})
                return jsonify({"reply": reply})
            reply = self.handle_message(
                text,
                source="UI",
                chat_history=chat_history,
            )
            return jsonify({"reply": reply})

        @app.route("/internal/brain_loop", methods=["POST"])
        def internal_brain_loop():
            """Run a brain-loop iteration for a non-Telegram surface.

            2026-04-23 Commit 5 — web body parity. The web process
            (maez-web.service) lives in a separate process from the
            daemon and therefore cannot touch ActionEngine directly.
            This endpoint bridges the gap: web POSTs the owner's
            message here, the daemon runs the full Jarvis tool-use
            loop against its own ActionEngine, and returns the
            transcript of what actually ran (or an empty string if
            no tools were used). Approval-gated actions are handed
            off to the card store; the caller is responsible for
            telling the user "I've proposed X — waiting on your
            approval" if the transcript contains ⏳ card markers.

            Payload: {"text": "...", "chat_id": "...", "user_id": "rohit"}
            Response: {"transcript": "..."} (empty string when no tools ran)

            Localhost-only by the service's bind, consistent with the
            existing /internal/* endpoints. Fails open: any exception
            returns an empty transcript with a 200 so the caller's
            fallback path (non-tool LLM synthesis) still works.
            """
            data = request.get_json(silent=True) or {}
            text = (data.get("text") or "").strip()
            if not text:
                return jsonify({"transcript": "", "error": "empty text"}), 400
            try:
                _record_owner_interaction(self)
            except Exception as _activity_exc:
                logger.debug("owner interaction tracker skipped: %s", _activity_exc)
            try:
                telegram = getattr(self, "telegram", None)
                get_pipeline_fn = telegram._get_pipeline if telegram else None
                action_engine_ref = getattr(self, "actions", None)
                if action_engine_ref is None or get_pipeline_fn is None:
                    return jsonify(
                        {
                            "transcript": "",
                            "error": "action_engine or pipeline unavailable",
                        }
                    ), 503
                from core import brain_loop as _bl

                # Slice 3 of trace work: request the structured result
                # so the JSON response can include tool_calls for the
                # web surface to forward into its trace path. Backward
                # compatible — legacy callers still see "transcript".
                _result = _bl.run_brain_loop(
                    text,
                    action_engine=action_engine_ref,
                    get_pipeline=get_pipeline_fn,
                    user_id=data.get("user_id") or "rohit",
                    chat_id=str(data.get("chat_id") or ""),
                    surface="web",
                    send_intermediate=None,  # web has no out-of-band card surface
                    return_structured=True,
                )
                if hasattr(_result, "transcript"):
                    return jsonify(
                        {
                            "transcript": _result.transcript or "",
                            "tool_calls": list(_result.tool_calls or []),
                        }
                    )
                # Legacy string fallback (if a future change reverts the
                # structured API). Kept for safety; not currently
                # reachable.
                return jsonify({"transcript": _result or "", "tool_calls": []})
            except Exception as e:
                logger.warning("/internal/brain_loop failed: %s", e)
                # Fail open — empty transcript lets the web caller
                # fall through to non-tool LLM synthesis rather than
                # degrade the whole turn.
                return jsonify(
                    {
                        "transcript": "",
                        "tool_calls": [],
                        "error": str(e),
                    }
                ), 200

        @app.route("/internal/approve_card/<request_id>", methods=["POST", "OPTIONS"])
        def approve_card(request_id: str):
            """Cockpit approval surface. Runs the full decision_pipeline
            approve path (_on_approve → will-I check → execute →
            card_store.mark_done) in the daemon process where
            ActionEngine lives. Safe equivalent of the Telegram
            'yes' keyword — same auth model (localhost only), same
            execution path."""
            if request.method == "OPTIONS":
                return ("", 204)
            _record_owner_interaction(self)
            try:
                telegram = getattr(self, "telegram", None)
                pipe = telegram._get_pipeline() if telegram else None
                if pipe is None:
                    return jsonify({"ok": False, "error": "pipeline unavailable"}), 503
                card = pipe.card_store.get(request_id)
                if card is None:
                    return jsonify({"ok": False, "error": f"no such card: {request_id}"}), 404
                from core.pending_cards import CardStatus

                if card.status not in {CardStatus.OPEN.value, CardStatus.DEFERRED.value}:
                    return jsonify(
                        {
                            "ok": False,
                            "error": f"card status is {card.status!r}, not approvable",
                        }
                    ), 409
                if (
                    pipe._is_pending_dialog_card(card)
                    or pipe._card_requires_s7_authorization(card)
                ):
                    return jsonify(
                        {
                            "ok": False,
                            "error": "s7_authorization_required",
                            "status": "blocked",
                            "message": (
                                "This card changes Maez's guarded substrate "
                                "and cannot be approved by the cockpit legacy "
                                "endpoint."
                            ),
                        }
                    ), 403

                class _CockpitCls:
                    source = "cockpit"
                    reasoning = "approved from cockpit UI"

                result = pipe._on_approve(card, _CockpitCls(), card.user_id or "owner")
                # PipelineResult may be the executed card result or a
                # refusal (e.g., covenant / will-I / stale state).
                ok = bool(getattr(result, "execution_success", None))
                return jsonify(
                    {
                        "ok": ok,
                        "status": getattr(
                            getattr(result, "status", None),
                            "value",
                            str(getattr(result, "status", "")),
                        ),
                        "message": getattr(result, "message", ""),
                        "output": (getattr(result, "execution_output", "") or "")[:2000],
                        "error": getattr(result, "execution_error", None),
                    }
                )
            except Exception as e:
                logger.warning("cockpit approve_card %s failed: %s", request_id, e)
                return jsonify({"ok": False, "error": str(e)}), 500

        @app.route("/dashboard")
        def dashboard():
            """Local-only interactive dashboard. Bound to 127.0.0.1, never nginx-proxied."""
            return send_file(str(BASE_DIR / "ui" / "dashboard_local.html"))

        @app.route("/project-panel")
        def project_panel():
            """Local-only work tracker for the owner. Never nginx-proxied."""
            return send_file(str(BASE_DIR / "ui" / "project_panel.html"))

        @app.route("/project-panel/state")
        def project_panel_state():
            """Small tracked state file for the project panel."""
            return send_file(
                str(BASE_DIR / "docs" / "project-panel" / "state.json"),
                mimetype="application/json",
            )

        @app.route("/project-panel/doc/<path:doc_path>")
        def project_panel_doc(doc_path: str):
            """Read-only docs viewer for project-panel links."""
            docs_root = (BASE_DIR / "docs").resolve()
            target = (BASE_DIR / doc_path).resolve()
            try:
                target.relative_to(docs_root)
            except ValueError:
                return jsonify({"error": "outside_docs"}), 404
            if not target.is_file():
                return jsonify({"error": "not_found"}), 404
            return send_file(str(target), mimetype="text/plain; charset=utf-8")

        @app.route("/")
        def root():
            return jsonify({"name": "Maez", "status": "running"})

        try:
            from werkzeug.serving import make_server

            srv = make_server("127.0.0.1", HEALTH_PORT, app)
            srv.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._health_server = srv
            # The backend probe (_check_ollama) already passed in start() and
            # the health socket is now bound — only now is "active" honest. Tell
            # systemd (Type=notify) we are really serving. No-op outside systemd
            # (NOTIFY_SOCKET unset) or when MAEZ_SYSTEMD_NOTIFY is off; never
            # raises, so a missing/closed notify socket can't fault a daemon that
            # is otherwise up.
            try:
                from core.infra.systemd_notify import sd_notify

                if not sd_notify("READY=1"):
                    logger.debug("sd_notify READY=1 skipped (no NOTIFY_SOCKET or flag off).")
            except Exception as e:  # pragma: no cover - defensive, must not block serving
                logger.debug("sd_notify READY=1 failed, proceeding: %s", e)
            srv.serve_forever()
            logger.info("Health endpoint stopped.")
        except KeyboardInterrupt:
            self.stop()
        finally:
            try:
                if self._health_server is not None:
                    self._health_server.server_close()
            except Exception:
                pass
            self._health_server = None


def daemonize():
    """Fork into background as a proper daemon process."""
    if os.fork() > 0:
        sys.exit(0)

    os.setsid()

    if os.fork() > 0:
        sys.exit(0)

    # Redirect stdio to /dev/null
    sys.stdin = open(os.devnull, "r")
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")


def main():
    if _CREDENTIAL_BOOTSTRAP_ERROR is not None:
        raise SystemExit(f"credential bootstrap failed: {_CREDENTIAL_BOOTSTRAP_ERROR}")
    try:
        _load_secrets_for_process(
            required={"MAEZ_TELEGRAM_TOKEN"},
            optional=set(_MAEZ_SECRET_NAMES) - {"MAEZ_TELEGRAM_TOKEN"},
            populate_environ=True,
        )
    except _SecretLoadError as exc:
        raise SystemExit(str(exc)) from exc

    daemon = MaezDaemon()

    # Handle signals for graceful shutdown
    signal.signal(signal.SIGTERM, daemon.stop)
    signal.signal(signal.SIGINT, daemon.stop)

    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        daemonize()

    daemon.start()


if __name__ == "__main__":
    main()
