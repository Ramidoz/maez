"""Intake Understanding Faculty shadow telemetry.

Default-off, observation-only. The live path may enqueue a job; all model work
and context fetching happen in the background worker.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import threading
import time
from typing import Any

from core.cognition.intake_faculty import HttpIntakeBackend, IntakeRead
from core.search.search_commitment import is_clear_yes, is_search_offer_worthy


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _bucket_latency(latency_s: float) -> float:
    return round(max(0.0, latency_s) * 1000.0, 1)


def offer_snapshot(offer) -> dict[str, Any] | None:
    if offer is None:
        return None
    if isinstance(offer, dict):
        if "offered_query_hash" in offer:
            return {
                "action_type": offer.get("action_type"),
                "stakes": offer.get("stakes"),
                "egress_class": offer.get("egress_class"),
                "executor": offer.get("executor"),
                "offered_query_hash": offer.get("offered_query_hash"),
            }
        query = offer.get("offered_query") or offer.get("query") or ""
        return {
            "action_type": offer.get("action_type"),
            "stakes": offer.get("stakes"),
            "egress_class": offer.get("egress_class"),
            "executor": offer.get("executor"),
            "offered_query_hash": _hash(str(query)),
        }
    query = getattr(offer, "offered_query", "") or ""
    return {
        "action_type": getattr(offer, "action_type", None),
        "stakes": getattr(offer, "stakes", None),
        "egress_class": getattr(offer, "egress_class", None),
        "executor": getattr(offer, "executor", None),
        "offered_query_hash": _hash(query),
    }


def _hard_want_verdict(text: str) -> str:
    try:
        from core.evolution.wants import is_hard_want

        return _bool(is_hard_want(text or ""))
    except Exception:
        return "unavailable"


def _continuity_verdict(text: str) -> str:
    try:
        from core.routing.focused_cognition import dialogue_continuity_state

        state = dialogue_continuity_state(text or "")
        return _bool(bool(getattr(state, "needs_dialogue", False)))
    except Exception:
        return "unavailable"


def _continuity_kind(text: str) -> str:
    try:
        from core.routing.focused_cognition import dialogue_continuity_state

        state = dialogue_continuity_state(text or "")
        kind = getattr(getattr(state, "kind", None), "value", None)
        return str(kind or "none")
    except Exception:
        return "unavailable"


def _recall_verdict(text: str) -> str:
    try:
        from core.memory.temporal_arithmetic import is_temporal_question
        from core.memory.temporal_anchor_recall import detect_temporal_anchor

        return _bool(bool(is_temporal_question(text) or getattr(detect_temporal_anchor(text), "anchor_kind", None)))
    except Exception:
        return "unavailable"


def gate_verdicts(text: str, *, controller, channel: str, chat_id: str) -> dict[str, str]:
    """Side-effect-free snapshots of today's gates.

    If a gate cannot be evaluated read-only, log unavailable. Never call a
    method that consumes/pops state.
    """
    verdicts = {
        "is_clear_yes": _bool(is_clear_yes(text or "")),
        "hard_want": _hard_want_verdict(text or ""),
        "continuity": _continuity_verdict(text or ""),
        "continuity_kind": _continuity_kind(text or ""),
        "recall_intent": _recall_verdict(text or ""),
        "search_worthy": _bool(is_search_offer_worthy(text or "")),
        "awaiting_card": "unavailable",
    }
    try:
        if controller is not None:
            verdicts["awaiting_card"] = _bool(controller.has_awaiting_card(channel, chat_id))
    except Exception:
        verdicts["awaiting_card"] = "unavailable"
    return verdicts


def _agreement(faculty_read: IntakeRead, gate_verdicts: dict[str, str]) -> dict[str, str]:
    def cmp(name: str, faculty_bool: bool | None, gate_key: str) -> str:
        del name
        gate = gate_verdicts.get(gate_key)
        if faculty_bool is None or gate not in {"true", "false"}:
            return "n_a"
        return "agree" if (gate == "true") == faculty_bool else "disagree"

    return {
        "commitment_response": cmp(
            "commitment_response",
            faculty_read.turn_kind == "commitment_response",
            "is_clear_yes",
        ),
        "boundary": cmp(
            "boundary",
            faculty_read.turn_kind == "boundary" or faculty_read.boundary_signal in {"soft", "hard"},
            "hard_want",
        ),
        "continuity": cmp("continuity", faculty_read.turn_kind == "continuity_reference", "continuity"),
        "recall": cmp("recall", faculty_read.turn_kind == "recall_request" or faculty_read.needs == "recall", "recall_intent"),
        "search": cmp("search", faculty_read.turn_kind == "search_request" or faculty_read.needs == "search", "search_worthy"),
    }


def build_telemetry(
    *,
    message: str,
    context_turns: list[str],
    pending_offer: dict | None,
    faculty_read: IntakeRead,
    gate_verdicts: dict[str, str],
    status: str,
    latency_s: float,
    debug: bool = False,
) -> dict[str, Any]:
    context_blob = "\n".join(context_turns or [])
    rec = {
        "ts": int(time.time()),
        "turn_hash": _hash(message),
        "context_hash": _hash(context_blob),
        "turn_len": len(message or ""),
        "context_turn_count": len(context_turns or []),
        "pending_offer": offer_snapshot(pending_offer),
        "faculty_read": faculty_read.to_telemetry(debug=debug),
        "gate_verdicts": dict(gate_verdicts or {}),
        "agreements": _agreement(faculty_read, gate_verdicts or {}),
        "faculty_latency_ms": _bucket_latency(latency_s),
        "status": status,
    }
    if debug:
        rec["turn_excerpt"] = (message or "")[:160]
        rec["context_summary"] = context_blob[:360]
    return rec


class IntakeShadow:
    """Bounded queue + one-in-flight background worker.

    The live path only calls enqueue(). Model work happens in _run().
    """

    def __init__(
        self,
        backend,
        telemetry_path,
        *,
        maxsize: int = 64,
        # 2026-06-11 hearing fix: the judge finishes the pre-closed-think
        # read in ~8-10s (CPU-offloaded prefill), so 8.0s timed out at the
        # finish line. 20s is safe: the worker is async/off-reply-path, and
        # the bounded queue + one-in-flight still protect the audit judge —
        # a slow read costs shadow throughput, never reply latency.
        timeout_s: float = 20.0,
        debug: bool = False,
        rotate_bytes: int = 2_000_000,
        rotate_keep: int = 3,
    ):
        self._backend = backend
        self._path = Path(telemetry_path)
        self._q: queue.Queue = queue.Queue(maxsize=maxsize)
        self._timeout_s = timeout_s
        self._debug = debug
        self._rotate_bytes = max(1024, int(rotate_bytes))
        self._rotate_keep = max(1, int(rotate_keep))
        self._worker = None
        self._stop = threading.Event()
        self._in_flight = threading.Lock()

    def enqueue(self, job: dict) -> str:
        try:
            self._q.put_nowait(dict(job or {}))
            return "enqueued"
        except queue.Full:
            self._emit({"ts": int(time.time()), "status": "enqueue_failed"})
            return "enqueue_failed"
        except Exception:
            return "enqueue_failed"

    def start(self):
        if self._worker is None:
            self._worker = threading.Thread(target=self._run, name="intake-shadow", daemon=True)
            self._worker.start()

    def stop(self):
        self._stop.set()
        try:
            self._q.put_nowait(None)
        except Exception:
            pass
        if self._worker is not None:
            self._worker.join(timeout=1.0)

    def _run(self):
        while not self._stop.is_set():
            try:
                job = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if job is None:
                break
            if not self._in_flight.acquire(blocking=False):
                self._emit({"ts": int(time.time()), "status": "judge_busy"})
                continue
            try:
                self._process(job)
            except Exception:
                self._emit({"ts": int(time.time()), "status": "backend_error"})
            finally:
                try:
                    self._in_flight.release()
                except Exception:
                    pass

    def _process(self, job: dict):
        provider = job.get("context_provider")
        try:
            context_turns = list(provider()) if callable(provider) else []
        except Exception:
            context_turns = []
        context = {
            "turns": context_turns,
            "pending_offer": job.get("pending_offer"),
            "surface": job.get("surface"),
        }
        read, latency_s = self._backend.read(job.get("message", ""), context, self._timeout_s)
        status = read.status if read.status != "ok" else "ok"
        rec = build_telemetry(
            message=job.get("message", ""),
            context_turns=context_turns,
            pending_offer=job.get("pending_offer"),
            faculty_read=read,
            gate_verdicts=job.get("gate_verdicts") or {},
            status=status,
            latency_s=latency_s,
            debug=self._debug,
        )
        self._emit(rec)

    def _rotate_if_needed(self):
        try:
            if not self._path.exists() or self._path.stat().st_size < self._rotate_bytes:
                return
            for idx in range(self._rotate_keep, 0, -1):
                src = self._path.with_name(self._path.name + f".{idx}")
                dst = self._path.with_name(self._path.name + f".{idx + 1}")
                if idx == self._rotate_keep:
                    if src.exists():
                        src.unlink()
                    continue
                if src.exists():
                    src.rename(dst)
            self._path.rename(self._path.with_name(self._path.name + ".1"))
        except Exception:
            pass

    def _emit(self, rec: dict):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed()
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, sort_keys=True) + "\n")
        except Exception:
            pass


_SHADOW_SINGLETON = None


def _default_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "maez" / "intake_shadow.jsonl"


def _enabled() -> bool:
    return bool(os.environ.get("MAEZ_INTAKE_FACULTY_SHADOW"))


def _debug_enabled() -> bool:
    return bool(os.environ.get("MAEZ_INTAKE_FACULTY_DEBUG"))


def _get_shadow():
    global _SHADOW_SINGLETON
    if not _enabled():
        return None
    if _SHADOW_SINGLETON is None:
        _SHADOW_SINGLETON = IntakeShadow(
            HttpIntakeBackend(),
            _default_path(),
            debug=_debug_enabled(),
        )
        _SHADOW_SINGLETON.start()
    return _SHADOW_SINGLETON


def set_shadow_singleton(shadow):
    global _SHADOW_SINGLETON
    _SHADOW_SINGLETON = shadow


def reset_shadow_singleton():
    global _SHADOW_SINGLETON
    if _SHADOW_SINGLETON is not None:
        try:
            _SHADOW_SINGLETON.stop()
        except Exception:
            pass
    _SHADOW_SINGLETON = None


def _context_provider(memory):
    def _load() -> list[str]:
        if memory is None:
            return []
        try:
            rows = memory.get_telegram_exchanges(limit=6)
        except Exception:
            return []
        out = []
        for row in rows or []:
            if isinstance(row, dict):
                content = row.get("content") or ""
            else:
                content = str(row or "")
            if content:
                out.append(str(content)[:1200])
        return out[:6]

    return _load


def observe_owner_turn(
    message: str,
    *,
    surface: str,
    chat_id: str,
    controller,
    memory,
    channel: str = "telegram_text",
) -> str:
    """Default-off, non-blocking owner-turn observation hook.

    Returns disabled/enqueued/enqueue_failed. Never raises into the surface.
    """
    try:
        shadow = _get_shadow()
        if shadow is None:
            return "disabled"
        try:
            offer = controller.get_search_offer(channel, chat_id) if controller is not None else None
        except Exception:
            offer = None
        job = {
            "message": message or "",
            "surface": surface,
            "chat_id": chat_id,
            "context_provider": _context_provider(memory),
            "pending_offer": offer_snapshot(offer),
            "gate_verdicts": gate_verdicts(
                message or "",
                controller=controller,
                channel=channel,
                chat_id=chat_id,
            ),
        }
        return shadow.enqueue(job)
    except Exception:
        return "enqueue_failed"
