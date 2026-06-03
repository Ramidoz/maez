# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S1b private-thoughts producer and behavior-safe reader.

This module is deliberately narrow. It wires only reasoning-residue
signals and exposes only a content-free recency bit to behavior.
"""

from __future__ import annotations
from contextlib import closing

import json
import logging
import os
import re
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from core.infra import paths
from core.infra.private_thoughts import (
    DEFAULT_DB_PATH,
    ENVELOPE_VERSION,
    SCHEMA_VERSION,
    AllowedFlow,
    ConsentTier,
    PrivateThoughts,
    ProducerId,
    RetentionRule,
    SignalClass,
    SignalKind,
    SignalState,
)

logger = logging.getLogger("maez")

S1B_SENTINEL_CONTENT = "s1b_reasoning_residue_event"
S1B_PRODUCER_VERSION = "s1b.1"
# A 30-minute recency window spans several daemon cycles without letting
# one transient retry shape the whole day of local presentation.
DEFAULT_ACTIVE_WINDOW_SECONDS = 30 * 60
DEFAULT_HOURLY_WRITE_CAP = 20
DEFAULT_OPTIONAL_OUTPUT_SENTENCE_CAP = 1
DEFAULT_BUSY_TIMEOUT_MS = 500
DEFAULT_CONFIG_PATH = paths.config_dir() / "private_thoughts_s1b.local.json"
DEFAULT_DUTY_CYCLE_WINDOW_SECONDS = 24 * 60 * 60
DEFAULT_DUTY_CYCLE_MIN_SAMPLES = 3
DEFAULT_DUTY_CYCLE_MAX_DAMPENED_RATIO = 0.80

S1B_EVENT_PRIORITY: tuple[str, ...] = (
    "retry_failed",
    "retry_triggered",
    "audit_rewrite",
    "low_cognition_score",
)
S1B_EVENT_INTENSITY_BANDS: dict[str, str] = {
    "retry_failed": "high",
    "retry_triggered": "medium",
    "audit_rewrite": "medium",
    "low_cognition_score": "low",
}

S1B_FORBIDDEN_CONTEXT_KEYS = frozenset(
    {
        "raw_text",
        "user_text",
        "model_output",
        "prompt_text",
        "tool_output",
        "approval_card_body",
        "rejection_wording",
        "trace_id",
        "trace_ids",
        "thought_id",
        "thought_ids",
        "topic",
        "topics",
        "forensic_handle",
        "forensic_handles",
    }
)

S1B_FORBIDDEN_USER_VISIBLE_SUBSTRINGS: tuple[str, ...] = (
    "I feel",
    "I'm feeling",
    "I am feeling",
    "I'm conflicted",
    "I'm anxious",
    "I'm worried",
    "I sense",
    "I can tell",
    "you seem",
    "you are upset",
    "you made me",
    "rupture",
    "repair pressure",
    "bond repair",
    "crisis",
    "soul objection",
    "private signal",
    "reasoning residue",
    "residue",
    "tension",
    "because I noticed",
)


@dataclass(frozen=True)
class S1bConfig:
    producer_enabled: bool = False
    consumer_enabled: bool = False
    active_window_seconds: int = DEFAULT_ACTIVE_WINDOW_SECONDS
    hourly_write_cap: int = DEFAULT_HOURLY_WRITE_CAP
    optional_output_sentence_cap: int = DEFAULT_OPTIONAL_OUTPUT_SENTENCE_CAP
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
    duty_cycle_window_seconds: int = DEFAULT_DUTY_CYCLE_WINDOW_SECONDS
    duty_cycle_min_samples: int = DEFAULT_DUTY_CYCLE_MIN_SAMPLES
    duty_cycle_max_dampened_ratio: float = DEFAULT_DUTY_CYCLE_MAX_DAMPENED_RATIO


@dataclass(frozen=True)
class S1bPacingDecision:
    mode: str = "neutral"
    optional_output_sentence_cap: int | None = None
    reason: str = "neutral"

    @classmethod
    def neutral(cls) -> "S1bPacingDecision":
        return cls()

    @classmethod
    def dampened(cls, *, sentence_cap: int = DEFAULT_OPTIONAL_OUTPUT_SENTENCE_CAP) -> "S1bPacingDecision":
        return cls(
            mode="optional_output_length_dampening",
            optional_output_sentence_cap=max(1, int(sentence_cap)),
            reason="private_signal_class_present",
        )

    @property
    def is_dampened(self) -> bool:
        return self.mode == "optional_output_length_dampening"


def _env_bool(name: str) -> bool | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return False


def _as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _as_positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _as_ratio(value: object, default: float) -> float:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return parsed if 0.0 <= parsed <= 1.0 else default


def load_s1b_config(*, config_path: Path | str | None = None) -> S1bConfig:
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    file_values: dict = {}
    malformed_file = False
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                file_values = loaded
            else:
                malformed_file = True
        except Exception:
            malformed_file = True

    env_producer = _env_bool("MAEZ_PRIVATE_THOUGHTS_S1B_PRODUCER")
    env_consumer = _env_bool("MAEZ_PRIVATE_THOUGHTS_S1B_CONSUMER")
    file_producer = (
        _as_bool(file_values["producer_enabled"], False)
        if "producer_enabled" in file_values
        else None
    )
    file_consumer = (
        _as_bool(file_values["consumer_enabled"], False)
        if "consumer_enabled" in file_values
        else None
    )

    producer_enabled = env_producer if env_producer is not None else False
    consumer_enabled = env_consumer if env_consumer is not None else False
    if file_producer is not None:
        producer_enabled = producer_enabled and file_producer if env_producer is not None else file_producer
    if file_consumer is not None:
        consumer_enabled = consumer_enabled and file_consumer if env_consumer is not None else file_consumer
    if malformed_file:
        logger.warning("S1b runtime config malformed; disabling consumer")
        consumer_enabled = False

    return S1bConfig(
        producer_enabled=producer_enabled,
        consumer_enabled=consumer_enabled,
        active_window_seconds=_as_positive_int(
            file_values.get("active_window_seconds"),
            DEFAULT_ACTIVE_WINDOW_SECONDS,
        ),
        hourly_write_cap=_as_positive_int(
            file_values.get("hourly_write_cap"),
            DEFAULT_HOURLY_WRITE_CAP,
        ),
        optional_output_sentence_cap=_as_positive_int(
            file_values.get("optional_output_sentence_cap"),
            DEFAULT_OPTIONAL_OUTPUT_SENTENCE_CAP,
        ),
        busy_timeout_ms=_as_positive_int(
            file_values.get("busy_timeout_ms"),
            DEFAULT_BUSY_TIMEOUT_MS,
        ),
        duty_cycle_window_seconds=_as_positive_int(
            file_values.get("duty_cycle_window_seconds"),
            DEFAULT_DUTY_CYCLE_WINDOW_SECONDS,
        ),
        duty_cycle_min_samples=_as_positive_int(
            file_values.get("duty_cycle_min_samples"),
            DEFAULT_DUTY_CYCLE_MIN_SAMPLES,
        ),
        duty_cycle_max_dampened_ratio=_as_ratio(
            file_values.get("duty_cycle_max_dampened_ratio"),
            DEFAULT_DUTY_CYCLE_MAX_DAMPENED_RATIO,
        ),
    )


def validate_s1b_context_extra(context_extra: dict | None) -> None:
    if context_extra is None:
        return
    if not isinstance(context_extra, dict):
        raise ValueError("S1b context_extra must be a dict")
    forbidden = S1B_FORBIDDEN_CONTEXT_KEYS.intersection(context_extra.keys())
    if forbidden:
        raise ValueError(f"S1b context_extra contains forbidden key(s): {sorted(forbidden)}")
    for key, value in context_extra.items():
        if isinstance(value, str) and any(
            marker in value.lower()
            for marker in (
                "rohit said",
                "owner said",
                "i feel",
                "i'm feeling",
                "trace:",
                "tool output",
            )
        ):
            raise ValueError(f"S1b context_extra value for {key!r} looks content-bearing")


def _coalesce_event(events: Iterable[str]) -> tuple[str | None, dict[str, int]]:
    counts = Counter(str(event) for event in events)
    invalid = sorted(set(counts) - set(S1B_EVENT_PRIORITY))
    if invalid:
        raise ValueError(f"unknown S1b event_kind(s): {invalid}")
    for event in S1B_EVENT_PRIORITY:
        if counts.get(event, 0) > 0:
            return event, dict(counts)
    return None, {}


class PrivateThoughtsS1bProducer:
    def __init__(
        self,
        *,
        db_path: Path | str | None = None,
        audit_db_path: Path | str | None = None,
        config_path: Path | str | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.audit_db_path = Path(audit_db_path) if audit_db_path is not None else None
        self.config_path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
        PrivateThoughts(db_path=self.db_path)

    def emit_cycle_residue(
        self,
        event_kinds: Iterable[str],
        *,
        cycle_id: int | None,
        now: float | None = None,
    ) -> int | None:
        cfg = load_s1b_config(config_path=self.config_path)
        if not cfg.producer_enabled:
            return None
        event_kind, counts = _coalesce_event(event_kinds)
        if event_kind is None:
            return None
        now = time.time() if now is None else float(now)
        context_extra = {
            "event_kind": event_kind,
            "cycle_id": cycle_id,
            "residue_intensity_band": S1B_EVENT_INTENSITY_BANDS[event_kind],
            "producer_version": S1B_PRODUCER_VERSION,
        }
        suppressed_counts = {k: v for k, v in counts.items() if k != event_kind and v > 0}
        if suppressed_counts:
            context_extra["coalesced_event_counts"] = suppressed_counts
        validate_s1b_context_extra(context_extra)
        return self._atomic_rate_limited_insert(now=now, cfg=cfg, context_extra=context_extra)

    def _atomic_rate_limited_insert(
        self,
        *,
        now: float,
        cfg: S1bConfig,
        context_extra: dict,
    ) -> int | None:
        cutoff = now - 3600
        store = PrivateThoughts(db_path=self.db_path)
        context = {
            "source": "daemon_cycle.reasoning_residue",
            "subject": "maez_internal_reasoning",
            "consent_tier": ConsentTier.OWNER_PRIVATE.value,
            "retention": RetentionRule.UNTIL_REVIEWED.value,
            "allowed_flows": [
                AllowedFlow.PRIVATE_READER.value,
                AllowedFlow.AUDIT_TRACE.value,
            ],
            "extra": context_extra,
        }
        conn = sqlite3.connect(self.db_path, timeout=max(0.001, cfg.busy_timeout_ms / 1000.0))
        try:
            conn.execute(f"PRAGMA busy_timeout={int(cfg.busy_timeout_ms)}")
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT context_json FROM private_thoughts
                WHERE ts >= ?
                  AND content = ?
                  AND producer_id = ?
                  AND signal_kind = ?
                  AND signal_class = ?
                """,
                (
                    cutoff,
                    S1B_SENTINEL_CONTENT,
                    ProducerId.REASONING_RESIDUE.value,
                    SignalKind.REASONING_RESIDUE.value,
                    SignalClass.REASONING_RESIDUE.value,
                ),
            ).fetchall()
            existing_count = len(existing)
            cycle_id = context_extra.get("cycle_id")
            if cycle_id is not None and any(
                _s1b_row_cycle_id(row[0]) == cycle_id for row in existing
            ):
                conn.rollback()
                return None
            if existing_count >= cfg.hourly_write_cap:
                conn.rollback()
                self._record_rate_limit_summary(now=now, suppressed_count=existing_count + 1)
                return None
            thought_id = store.insert_signal_in_transaction(
                conn,
                ts=now,
                content=S1B_SENTINEL_CONTENT,
                producer_id=ProducerId.REASONING_RESIDUE,
                signal_kind=SignalKind.REASONING_RESIDUE,
                source=context["source"],
                subject=context["subject"],
                consent_tier=context["consent_tier"],
                retention=context["retention"],
                allowed_flows=context["allowed_flows"],
                context_extra=context_extra,
                memory_phase="gestation",
            )
            conn.commit()
            return int(thought_id)
        except sqlite3.OperationalError as exc:
            logger.warning("S1b producer skipped write: %s", exc)
            try:
                conn.rollback()
            except Exception:
                pass
            return None
        finally:
            conn.close()

    def _record_rate_limit_summary(self, *, now: float, suppressed_count: int) -> None:
        try:
            from core.cognition.audit_log import AuditLog

            log = AuditLog(db_path=self.audit_db_path) if self.audit_db_path else AuditLog()
            window_start = int(now // 3600) * 3600
            if self._rate_limit_summary_exists(
                audit_db_path=log.db_path,
                window_start=window_start,
            ):
                return
            request_id = log.record(
                action="private_thoughts_s1b.rate_limited",
                params={
                    "producer_version": S1B_PRODUCER_VERSION,
                    "window_seconds": 3600,
                    "suppressed_count": int(suppressed_count),
                    "rate_limit_window_start_ts": float(window_start),
                    "rate_limit_window_end_ts": float(window_start + 3600),
                },
                classification=None,
                injection_matches=None,
                verdict=None,
                policy_rule_id="S1b.rate_limit",
            )
            log.record_outcome(
                request_id,
                outcome="recorded",
                notes="content-free S1b rate-limit summary",
            )
        except Exception as exc:
            logger.warning("S1b rate-limit audit summary skipped: %s", exc)

    def _rate_limit_summary_exists(self, *, audit_db_path: Path, window_start: int) -> bool:
        try:
            with closing(sqlite3.connect(audit_db_path)) as conn, conn:
                rows = conn.execute(
                    """
                    SELECT params_json FROM audit_log
                    WHERE action = ?
                    ORDER BY id DESC
                    LIMIT 20
                    """,
                    ("private_thoughts_s1b.rate_limited",),
                ).fetchall()
        except sqlite3.OperationalError:
            return False
        for (params_json,) in rows:
            try:
                params = json.loads(params_json or "{}")
            except Exception:
                continue
            if int(params.get("rate_limit_window_start_ts", -1)) == int(window_start):
                return True
        return False


def _neutral_recency(
    *,
    active_window_seconds: int,
    neutral_due_to_error: bool,
) -> dict:
    return {
        "recent_reasoning_residue_present": False,
        "active_window_seconds": int(active_window_seconds),
        "behavior_safe_count": 0,
        "neutral_due_to_error": bool(neutral_due_to_error),
    }


def _s1b_row_cycle_id(context_json: str | bytes | None) -> int | str | None:
    try:
        context = json.loads(context_json or "{}")
    except Exception:
        return None
    if not isinstance(context, dict):
        return None
    extra = context.get("extra")
    if not isinstance(extra, dict):
        return None
    return extra.get("cycle_id")


def behavior_safe_reasoning_residue_recency(
    db_path: Path | str | None = None,
    *,
    now: float | None = None,
    active_window_seconds: int = DEFAULT_ACTIVE_WINDOW_SECONDS,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    limit: int = 20,
) -> dict:
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    if not path.exists():
        return _neutral_recency(
            active_window_seconds=active_window_seconds,
            neutral_due_to_error=False,
        )
    now = time.time() if now is None else float(now)
    cutoff = now - int(active_window_seconds)
    try:
        conn = sqlite3.connect(path, timeout=max(0.001, busy_timeout_ms / 1000.0))
        try:
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
            conn.execute("PRAGMA query_only=ON")
            rows = conn.execute(
                """
                SELECT context_json, memory_phase, envelope_version, schema_version,
                       signal_class, signal_state
                FROM private_thoughts
                WHERE ts >= ?
                  AND signal_class = ?
                  AND signal_state = ?
                  AND envelope_version = ?
                  AND schema_version = ?
                ORDER BY thought_id DESC
                LIMIT ?
                """,
                (
                    cutoff,
                    SignalClass.REASONING_RESIDUE.value,
                    SignalState.ACTIVE.value,
                    ENVELOPE_VERSION,
                    SCHEMA_VERSION,
                    max(1, min(int(limit), 100)),
                ),
            ).fetchall()
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("S1b behavior-safe recency read returned neutral: %s", exc)
        return _neutral_recency(
            active_window_seconds=active_window_seconds,
            neutral_due_to_error=True,
        )

    count = 0
    for row in rows:
        try:
            context = json.loads(row["context_json"] or "{}")
        except Exception:
            continue
        flows = context.get("allowed_flows") if isinstance(context, dict) else None
        if isinstance(flows, list) and AllowedFlow.PRIVATE_READER.value in flows:
            count += 1
    return {
        "recent_reasoning_residue_present": count > 0,
        "active_window_seconds": int(active_window_seconds),
        "behavior_safe_count": count,
        "neutral_due_to_error": False,
    }


def apply_s1b_to_direct_reply(text: str) -> str:
    """Direct user replies are outside S1b's behavior surface."""
    return text


def _cap_sentences(text: str, sentence_cap: int) -> str:
    cap = max(1, int(sentence_cap))
    stripped = (text or "").strip()
    if not stripped:
        return stripped
    pieces = re.findall(r".*?(?:[.!?](?:\s+|$)|$)", stripped, flags=re.S)
    sentences = [piece.strip() for piece in pieces if piece.strip()]
    if not sentences:
        return stripped
    return " ".join(sentences[:cap]).strip()


def build_cycle_optional_presentation(
    *,
    cycle: int,
    canonical_text: str,
    decision: S1bPacingDecision,
) -> dict | None:
    if not decision.is_dampened:
        return None
    presentation_text = _cap_sentences(
        canonical_text,
        decision.optional_output_sentence_cap or DEFAULT_OPTIONAL_OUTPUT_SENTENCE_CAP,
    )
    visible_lower = presentation_text.lower()
    if any(forbidden.lower() in visible_lower for forbidden in S1B_FORBIDDEN_USER_VISIBLE_SUBSTRINGS):
        return None
    return {
        "type": "cycle_optional_presentation",
        "cycle": int(cycle),
        "presentation_text": presentation_text,
        "presentation_dampened": True,
        "presentation_policy": "s1b_optional_output_length_dampening",
        "canonical_thought_unchanged": True,
    }


class PrivateThoughtsS1bConsumer:
    def __init__(
        self,
        *,
        db_path: Path | str | None = None,
        audit_db_path: Path | str | None = None,
        config_path: Path | str | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.audit_db_path = Path(audit_db_path) if audit_db_path is not None else None
        self.config_path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
        self._spent_windows: set[int] = set()

    def pacing_decision(self, *, now: float | None = None) -> S1bPacingDecision:
        cfg = load_s1b_config(config_path=self.config_path)
        if not cfg.consumer_enabled:
            return S1bPacingDecision.neutral()
        now = time.time() if now is None else float(now)
        window_id = int(now // max(1, cfg.active_window_seconds))
        if window_id in self._spent_windows:
            return S1bPacingDecision.neutral()
        recency = behavior_safe_reasoning_residue_recency(
            self.db_path,
            now=now,
            active_window_seconds=cfg.active_window_seconds,
            busy_timeout_ms=cfg.busy_timeout_ms,
        )
        if not recency["recent_reasoning_residue_present"] or recency["neutral_due_to_error"]:
            return S1bPacingDecision.neutral()
        self._spent_windows.add(window_id)
        return S1bPacingDecision.dampened(sentence_cap=cfg.optional_output_sentence_cap)

    def should_record_optional_presentation_opportunity(self) -> bool:
        """Whether a cycle should count toward the active consumer duty denominator."""
        return load_s1b_config(config_path=self.config_path).consumer_enabled

    def record_optional_presentation(self, *, dampened: bool, now: float | None = None) -> None:
        """Record presentation duty cycle and self-disable on near-default dampening."""
        now = time.time() if now is None else float(now)
        self._record_consumer_audit(
            action="private_thoughts_s1b.optional_presentation",
            params={
                "producer_version": S1B_PRODUCER_VERSION,
                "dampened": bool(dampened),
            },
        )
        cfg = load_s1b_config(config_path=self.config_path)
        total, dampened_count = self._presentation_counts(now=now, cfg=cfg)
        if (
            total >= cfg.duty_cycle_min_samples
            and dampened_count / max(1, total) > cfg.duty_cycle_max_dampened_ratio
        ):
            self._disable_consumer_in_config()
            self._record_consumer_audit(
                action="private_thoughts_s1b.consumer_self_disabled",
                params={
                    "producer_version": S1B_PRODUCER_VERSION,
                    "window_seconds": cfg.duty_cycle_window_seconds,
                    "sample_count": total,
                    "dampened_count": dampened_count,
                    "max_dampened_ratio": cfg.duty_cycle_max_dampened_ratio,
                },
            )

    def _presentation_counts(self, *, now: float, cfg: S1bConfig) -> tuple[int, int]:
        audit_db_path = self._audit_db_path()
        if not audit_db_path.exists():
            return (0, 0)
        cutoff = now - cfg.duty_cycle_window_seconds
        try:
            with closing(sqlite3.connect(audit_db_path)) as conn, conn:
                rows = conn.execute(
                    """
                    SELECT params_json FROM audit_log
                    WHERE action = ?
                      AND ts >= ?
                    """,
                    ("private_thoughts_s1b.optional_presentation", cutoff),
                ).fetchall()
        except sqlite3.OperationalError:
            return (0, 0)
        total = 0
        dampened_count = 0
        for (params_json,) in rows:
            try:
                params = json.loads(params_json or "{}")
            except Exception:
                continue
            total += 1
            if bool(params.get("dampened")):
                dampened_count += 1
        return total, dampened_count

    def _audit_db_path(self) -> Path:
        if self.audit_db_path is not None:
            return self.audit_db_path
        from core.cognition.audit_log import DEFAULT_DB_PATH as DEFAULT_AUDIT_DB_PATH

        return DEFAULT_AUDIT_DB_PATH

    def _disable_consumer_in_config(self) -> None:
        data: dict = {}
        if self.config_path.exists():
            try:
                loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                data = {}
        data["consumer_enabled"] = False
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def _record_consumer_audit(self, *, action: str, params: dict) -> None:
        try:
            from core.cognition.audit_log import AuditLog

            log = AuditLog(db_path=self.audit_db_path) if self.audit_db_path else AuditLog()
            request_id = log.record(
                action=action,
                params=params,
                classification=None,
                injection_matches=None,
                verdict=None,
                policy_rule_id="S1b.consumer_duty_cycle",
            )
            log.record_outcome(
                request_id,
                outcome="recorded",
                notes="content-free S1b consumer duty-cycle event",
            )
        except Exception as exc:
            logger.warning("S1b consumer audit event skipped: %s", exc)
