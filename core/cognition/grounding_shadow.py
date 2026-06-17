"""MiniCheck grounding shadow — observation only.

Splits the final audited reply into sentences and asks an out-of-process
verifier whether each follows from the claimable evidence, writing
content-light divergence telemetry. This module gates nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
import queue
import re
import hashlib
import threading
import time

from core.infra.env_flags import strict_env_flag
from core.cognition.support_verifier import (
    HttpSupportVerifier,
    SUPPORTED,
    UNAVAILABLE,
    UNSUPPORTED,
)

logger = logging.getLogger("maez.grounding_shadow")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CITE_RE = re.compile(r"\[E(\d+)\]")
_CITATION_ONLY_RE = re.compile(r"^(?:\s*\[E\d+\]\s*)+[.!?]?$")


def split_sentences(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    out: list[str] = []
    for part in (part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()):
        if out and _CITATION_ONLY_RE.fullmatch(part):
            out[-1] = f"{out[-1]} {part}".strip()
            continue
        out.append(part)
    return out


def claimable_evidence(claimable_items) -> str:
    parts = []
    for item in claimable_items or ():
        if not isinstance(item, dict):
            continue
        evidence = (
            item.get("evidence")
            or item.get("evidence_refs")
            or item.get("text")
            or item.get("fact")
            or ""
        )
        if evidence:
            parts.append(str(evidence))
    return "\n".join(parts)


def compute_shadow(
    final_text,
    evidence_map,
    verifier,
    *,
    per_sentence_timeout_s: float = 0.25,
    per_job_budget_s: float = 1.5,
) -> dict:
    """Run sentence-level support checks under a per-job budget."""
    evidence_map = dict(evidence_map or {})
    if not evidence_map:
        return {
            "status": "no_evidence",
            "sentences": [],
            "shadowed_count": 0,
            "remaining_count": 0,
        }

    sentences = split_sentences(final_text)
    if not sentences:
        return {
            "status": "no_sentences",
            "sentences": [],
            "shadowed_count": 0,
            "remaining_count": 0,
        }

    started = time.monotonic()
    results = []
    shadowed = 0
    status = "ok"
    for idx, sentence in enumerate(sentences):
        if time.monotonic() - started >= per_job_budget_s:
            return {
                "status": "budget_exceeded",
                "sentences": results,
                "shadowed_count": shadowed,
                "remaining_count": len(sentences) - idx,
            }
        rec = classify_sentence(
            sentence,
            evidence_map,
            verifier,
            per_sentence_timeout_s,
        )
        if rec["verdict"] == UNAVAILABLE:
            status = "verifier_unavailable"
        results.append(rec)
        if rec.get("mode") == "no_citation" and strict_env_flag(
            "MAEZ_GROUNDING_SHADOW_DIAGNOSTIC"
        ):
            diagnostic = _uncited_all_evidence_diagnostic(
                sentence,
                evidence_map,
                verifier,
                per_sentence_timeout_s,
            )
            if diagnostic["verdict"] == UNAVAILABLE:
                status = "verifier_unavailable"
            results.append(diagnostic)
        shadowed += 1

    return {
        "status": status,
        "sentences": results,
        "shadowed_count": shadowed,
        "remaining_count": 0,
    }


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def audit_summary_from_result(audit_result) -> dict:
    """Return a content-light summary using real AuditResult fields only."""
    flags = getattr(audit_result, "flags", None) or []
    mode = getattr(audit_result, "mode", "noop")
    return {
        "audit_available": mode != "judge_unavailable",
        "flag_count": len(flags),
        "flag_kinds": sorted({getattr(flag, "kind", "unknown") for flag in flags}),
        "rewritten": bool(getattr(audit_result, "rewritten", False)),
        "mode": mode,
        "skipped_reason": getattr(audit_result, "skipped_reason", None),
    }


def _claimable_chars(claimable_items) -> int:
    total = 0
    for item in claimable_items or ():
        if not isinstance(item, dict):
            continue
        total += len(str(item.get("evidence") or item.get("text") or ""))
    return total


def _cited_labels(sentence: str) -> list[str]:
    return [f"E{match.group(1)}" for match in _CITE_RE.finditer(sentence or "")]


def _verifier_name(verifier) -> str:
    return getattr(verifier, "name", None) or verifier.__class__.__name__


def classify_sentence(sentence, evidence_map, verifier, timeout_s) -> dict:
    labels = _cited_labels(sentence)
    base = {"sentence": sentence, "cited_evidence_ids": labels}
    if not labels:
        return {
            **base,
            "mode": "no_citation",
            "verdict": "ABSTAIN",
            "verifier": "deterministic",
            "score": None,
            "latency_s": 0.0,
        }
    if any(label not in evidence_map for label in labels):
        return {
            **base,
            "mode": "unmatched_citation",
            "verdict": UNSUPPORTED,
            "verifier": "deterministic",
            "score": None,
            "latency_s": 0.0,
        }
    texts = [(evidence_map[label] or "").strip() for label in labels]
    combined = "\n".join(text for text in texts if text)
    if not combined:
        return {
            **base,
            "mode": "empty_evidence",
            "verdict": "ABSTAIN",
            "verifier": "deterministic",
            "score": None,
            "latency_s": 0.0,
        }
    try:
        label, score, latency = verifier.support(combined, sentence, timeout_s)
    except Exception:
        label, score, latency = UNAVAILABLE, None, 0.0
    if label == UNAVAILABLE:
        return {
            **base,
            "mode": "verifier_unavailable",
            "verdict": UNAVAILABLE,
            "verifier": _verifier_name(verifier),
            "score": score,
            "latency_s": latency,
        }
    return {
        **base,
        "mode": "cited_support",
        "verdict": label,
        "verifier": _verifier_name(verifier),
        "score": score,
        "latency_s": latency,
    }


def _uncited_all_evidence_diagnostic(sentence, evidence_map, verifier, timeout_s) -> dict:
    combined = "\n".join(
        str(text).strip() for text in (evidence_map or {}).values() if str(text).strip()
    )
    base = {
        "sentence": sentence,
        "cited_evidence_ids": [],
        "mode": "uncited_all_evidence_diagnostic",
        "counts_as_grounded": False,
    }
    if not combined:
        return {
            **base,
            "verdict": "ABSTAIN",
            "verifier": "deterministic",
            "score": None,
            "latency_s": 0.0,
        }
    try:
        label, score, latency = verifier.support(combined, sentence, timeout_s)
    except Exception:
        label, score, latency = UNAVAILABLE, None, 0.0
    return {
        **base,
        "verdict": label,
        "verifier": _verifier_name(verifier),
        "score": score,
        "latency_s": latency,
    }


@dataclass
class GateOutcome:
    gated_marked_draft: str
    gate_receipt: dict
    support_row: dict


_GATE_FAILURE_CAVEAT = "I couldn't verify this before sending."


def _caveat_for(rec: dict) -> str | None:
    mode = rec.get("mode")
    verdict = rec.get("verdict")
    if mode == "cited_support" and verdict == UNSUPPORTED:
        return "I couldn't confirm this from the source I cited."
    if mode == "uncited_all_evidence_gate" and verdict == UNSUPPORTED:
        return "I couldn't confirm this from the evidence I had."
    if mode == "unmatched_citation":
        return "I cited a source I can't match here."
    if mode in {
        "verifier_unavailable",
        "budget_exhausted",
        "uncited_verifier_unavailable",
    }:
        return _GATE_FAILURE_CAVEAT
    return None


def _append_gate_failure_caveat(reply: str) -> str:
    reply = (reply or "").strip()
    if not reply:
        return _GATE_FAILURE_CAVEAT
    if _GATE_FAILURE_CAVEAT in reply:
        return reply
    return f"{reply} {_GATE_FAILURE_CAVEAT}"


def _classify_uncited_for_gate(sentence, evidence_map, verifier, timeout_s) -> dict:
    combined = "\n".join(
        str(text).strip() for text in (evidence_map or {}).values() if str(text).strip()
    )
    base = {
        "sentence": sentence,
        "cited_evidence_ids": [],
        "mode": "uncited_all_evidence_gate",
        "counts_as_grounded": False,
    }
    if not combined:
        return {
            **base,
            "verdict": "ABSTAIN",
            "verifier": "deterministic",
            "score": None,
            "latency_s": 0.0,
        }
    try:
        label, score, latency = verifier.support(combined, sentence, timeout_s)
    except Exception:
        label, score, latency = UNAVAILABLE, None, 0.0
    if label == UNAVAILABLE:
        return {
            **base,
            "mode": "uncited_verifier_unavailable",
            "verdict": UNAVAILABLE,
            "verifier": _verifier_name(verifier),
            "score": score,
            "latency_s": latency,
        }
    return {
        **base,
        "verdict": label,
        "verifier": _verifier_name(verifier),
        "score": score,
        "latency_s": latency,
    }


def apply_support_gate(
    marked_draft,
    evidence_map,
    verifier,
    *,
    surface="unknown",
    per_sentence_timeout_s: float = 1.0,
    budget_s: float = 4.0,
    shadow_id=None,
    ts=None,
    boot_id=None,
) -> GateOutcome:
    """Synchronously caveat unsupported cited claims in a marked draft."""
    sentences = split_sentences(marked_draft)
    started = time.monotonic()
    parts: list[str] = []
    recs: list[dict] = []
    budget_hit = False
    for sentence in sentences:
        parts.append(sentence)
        if budget_hit or (time.monotonic() - started) >= budget_s:
            budget_hit = True
            labels = _cited_labels(sentence)
            if labels:
                rec = {
                    "sentence": sentence,
                    "cited_evidence_ids": labels,
                    "mode": "budget_exhausted",
                    "verdict": UNAVAILABLE,
                    "verifier": "deterministic",
                    "score": None,
                    "latency_s": 0.0,
                }
                recs.append(rec)
                caveat = _caveat_for(rec)
                if caveat:
                    parts.append(caveat)
            elif evidence_map:
                rec = {
                    "sentence": sentence,
                    "cited_evidence_ids": [],
                    "mode": "uncited_verifier_unavailable",
                    "verdict": UNAVAILABLE,
                    "verifier": "deterministic",
                    "score": None,
                    "latency_s": 0.0,
                    "counts_as_grounded": False,
                }
                recs.append(rec)
                caveat = _caveat_for(rec)
                if caveat:
                    parts.append(caveat)
            continue
        rec = classify_sentence(sentence, evidence_map, verifier, per_sentence_timeout_s)
        if rec.get("mode") == "no_citation" and evidence_map:
            rec = _classify_uncited_for_gate(
                sentence,
                evidence_map,
                verifier,
                per_sentence_timeout_s,
            )
        recs.append(rec)
        caveat = _caveat_for(rec)
        if caveat:
            parts.append(caveat)
    gated = " ".join(part for part in parts if part)
    status = "ok"
    if budget_hit:
        status = "budget_exceeded"
    elif any(rec.get("verdict") == UNAVAILABLE for rec in recs):
        status = "verifier_unavailable"
    compute_result = {
        "status": status,
        "sentences": recs,
        "shadowed_count": len(recs),
        "remaining_count": 0,
    }
    support_row = build_telemetry(
        shadow_id,
        ts,
        surface,
        boot_id,
        {"mode": "gate"},
        compute_result,
        post_audit=True,
    )
    support_row["gate_applied"] = True
    gate_receipt = {
        "event": "support_gate_applied",
        "surface": surface,
        "cited": sum(1 for rec in recs if rec.get("cited_evidence_ids")),
        "caveated_unsupported": sum(
            1
            for rec in recs
            if rec.get("mode") == "cited_support" and rec.get("verdict") == UNSUPPORTED
        ),
        "caveated_unmatched": sum(
            1 for rec in recs if rec.get("mode") == "unmatched_citation"
        ),
        "caveated_uncited": sum(
            1
            for rec in recs
            if rec.get("mode") == "uncited_all_evidence_gate"
            and rec.get("verdict") == UNSUPPORTED
        ),
        "caveated_unverified": sum(
            1
            for rec in recs
            if rec.get("mode")
            in {"verifier_unavailable", "budget_exhausted", "uncited_verifier_unavailable"}
        ),
        "uncited_checked": sum(
            1
            for rec in recs
            if rec.get("mode")
            in {"uncited_all_evidence_gate", "uncited_verifier_unavailable"}
        ),
        "budget_exhausted": any(rec.get("mode") == "budget_exhausted" for rec in recs),
        "verifier": _verifier_name(verifier),
        "latency_ms": round(sum(rec.get("latency_s") or 0.0 for rec in recs) * 1000, 1),
    }
    return GateOutcome(
        gated_marked_draft=gated,
        gate_receipt=gate_receipt,
        support_row=support_row,
    )


def evidence_map_from_working_set(working_set) -> dict[str, str]:
    """Extract the focused WorkingSet's cited-evidence label map."""
    out: dict[str, str] = {}
    try:
        items = getattr(working_set, "items", ()) or ()
        for item in items:
            label = getattr(item, "local_label", None)
            text = getattr(item, "text", None)
            if label and text:
                out[str(label)] = str(text)
    except Exception:
        return {}
    return out


def emit_support_row(rec: dict, *, telemetry_path: str | None = None) -> bool:
    path = telemetry_path or _default_telemetry_path()
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        return True
    except Exception:
        return False


def observe_focused_support_gate(
    reply,
    evidence_map,
    *,
    surface,
    boot_id,
    shadow_id,
    ts,
) -> str:
    """SYNC support gate: caveat marked draft and write gate telemetry."""
    try:
        verifier = HttpSupportVerifier()
        outcome = apply_support_gate(
            reply,
            evidence_map,
            verifier,
            surface=surface,
            shadow_id=shadow_id,
            ts=ts,
            boot_id=boot_id,
        )
        receipt = outcome.gate_receipt
        row_written = emit_support_row(outcome.support_row)
        logger.info(
            "support_gate_applied surface=%s cited=%s caveated_unsupported=%s "
            "caveated_unmatched=%s caveated_unverified=%s budget_exhausted=%s "
            "verifier=%s latency_ms=%s row_written=%s",
            receipt.get("surface"),
            receipt.get("cited"),
            receipt.get("caveated_unsupported"),
            receipt.get("caveated_unmatched"),
            receipt.get("caveated_unverified"),
            receipt.get("budget_exhausted"),
            receipt.get("verifier"),
            receipt.get("latency_ms"),
            row_written,
        )
        if not row_written:
            logger.warning(
                "support_gate_row_write_failed surface=%s shadow_id=%s",
                surface,
                shadow_id,
            )
        return outcome.gated_marked_draft
    except Exception as exc:
        failure_row = {
            "shadow_id": shadow_id,
            "ts": ts,
            "surface": surface,
            "boot_id": boot_id,
            "post_audit": True,
            "audit_available": None,
            "flag_count": None,
            "flag_kinds": [],
            "rewritten": None,
            "mode": "gate",
            "skipped_reason": None,
            "sentence_count": 0,
            "unsupported_count": 0,
            "supported_count": 0,
            "skipped_count": 0,
            "status": "gate_failed",
            "error_class": exc.__class__.__name__,
            "gate_applied": True,
            "sentences": [],
        }
        row_written = emit_support_row(failure_row)
        logger.warning(
            "support_gate_failed surface=%s error_class=%s row_written=%s",
            surface,
            exc.__class__.__name__,
            row_written,
            exc_info=True,
        )
        return _append_gate_failure_caveat(reply)


def decide_support_path(*, gate_enabled: bool, shadow_enabled: bool) -> str:
    if gate_enabled:
        return "sync_gate"
    if shadow_enabled:
        return "async_shadow"
    return "none"


def build_telemetry(
    shadow_id,
    ts,
    surface,
    boot_id,
    audit_summary,
    compute_result,
    *,
    post_audit: bool = False,
    debug: bool = False,
) -> dict:
    sentences = []
    for result in compute_result.get("sentences", []):
        sentence = result.get("sentence") or ""
        rec = {
            "claim_hash": _hash(sentence),
            "cited_evidence_ids": list(result.get("cited_evidence_ids") or []),
            "support_verdict": result.get("verdict"),
            "mode": result.get("mode"),
            "verifier": result.get("verifier"),
            "score": result.get("score"),
            "latency_ms": round((result.get("latency_s") or 0.0) * 1000, 1),
            "counts_as_grounded": bool(result.get("counts_as_grounded", True)),
        }
        if debug:
            rec["snippet"] = sentence[:120]
        sentences.append(rec)

    verdicts = [
        r.get("support_verdict")
        for r in sentences
        if r.get("counts_as_grounded", True)
    ]
    return {
        "shadow_id": shadow_id,
        "ts": ts,
        "surface": surface,
        "boot_id": boot_id,
        "post_audit": bool(post_audit),
        "audit_available": audit_summary.get("audit_available"),
        "flag_count": audit_summary.get("flag_count"),
        "flag_kinds": audit_summary.get("flag_kinds"),
        "rewritten": audit_summary.get("rewritten"),
        "mode": audit_summary.get("mode"),
        "skipped_reason": audit_summary.get("skipped_reason"),
        "sentence_count": len(verdicts),
        "unsupported_count": sum(1 for verdict in verdicts if verdict == UNSUPPORTED),
        "supported_count": sum(1 for verdict in verdicts if verdict == SUPPORTED),
        "skipped_count": compute_result.get("remaining_count", 0),
        "status": compute_result["status"],
        "sentences": sentences,
    }


class GroundingShadow:
    """Bounded queue + background worker for grounding shadow telemetry."""

    def __init__(
        self,
        verifier,
        telemetry_path,
        *,
        maxsize: int = 64,
        per_sentence_timeout_s: float = 1.0,
        per_job_budget_s: float = 4.0,
        debug: bool = False,
    ):
        self._verifier = verifier
        self._telemetry_path = telemetry_path
        self._q: queue.Queue = queue.Queue(maxsize=maxsize)
        self._per_sentence_timeout_s = per_sentence_timeout_s
        self._per_job_budget_s = per_job_budget_s
        self._debug = debug
        self._worker = None
        self._stop = threading.Event()
        self.dropped_count = 0

    def enqueue(self, job: dict) -> str:
        try:
            self._q.put_nowait(job)
            return "enqueued"
        except queue.Full:
            self.dropped_count += 1
            return "shadow_enqueue_failed"
        except Exception:
            return "shadow_enqueue_failed"

    def start(self):
        if self._worker is None:
            self._worker = threading.Thread(
                target=self._run,
                name="grounding-shadow",
                daemon=True,
            )
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
            try:
                self._process(job)
            except Exception:
                pass

    def _process(self, job):
        compute = compute_shadow(
            job["final_text"],
            job.get("evidence_map") or {},
            self._verifier,
            per_sentence_timeout_s=self._per_sentence_timeout_s,
            per_job_budget_s=self._per_job_budget_s,
        )
        rec = build_telemetry(
            job.get("shadow_id"),
            job.get("ts"),
            job.get("surface"),
            job.get("boot_id"),
            job.get("audit_summary", {}),
            compute,
            post_audit=bool(job.get("post_audit")),
            debug=self._debug,
        )
        self._emit(rec)

    def _emit(self, rec):
        try:
            with open(self._telemetry_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        except Exception:
            pass


_SHADOW_SINGLETON = None


def _default_telemetry_path() -> str:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    directory = os.path.join(base, "maez")
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, "grounding_shadow.jsonl")


def _get_shadow():
    global _SHADOW_SINGLETON
    if not strict_env_flag("MAEZ_GROUNDING_SHADOW_ENABLED"):
        return None
    if _SHADOW_SINGLETON is None:
        _SHADOW_SINGLETON = GroundingShadow(
            HttpSupportVerifier(),
            _default_telemetry_path(),
            debug=strict_env_flag("MAEZ_GROUNDING_SHADOW_DEBUG"),
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


def shadow_observe(
    audit_result,
    claimable_items,
    *,
    surface,
    boot_id,
    shadow_id,
    ts,
) -> str:
    """Non-blocking observation hook. Never raises into the caller."""
    try:
        shadow = _get_shadow()
        if shadow is None:
            return "disabled"
        job = {
            "final_text": getattr(audit_result, "text", "") or "",
            "claimable_items": claimable_items,
            "audit_summary": audit_summary_from_result(audit_result),
            "surface": surface,
            "boot_id": boot_id,
            "shadow_id": shadow_id,
            "ts": ts,
        }
        return shadow.enqueue(job)
    except Exception:
        return "disabled"


def observe_focused_support(
    reply,
    evidence_map,
    *,
    surface,
    boot_id,
    shadow_id,
    ts,
) -> str:
    """Non-blocking observation hook for the post-audit focused reply."""
    try:
        shadow = _get_shadow()
        if shadow is None:
            return "disabled"
        job = {
            "final_text": reply or "",
            "evidence_map": dict(evidence_map or {}),
            "audit_summary": {},
            "surface": surface,
            "boot_id": boot_id,
            "shadow_id": shadow_id,
            "ts": ts,
            "post_audit": True,
        }
        return shadow.enqueue(job)
    except Exception:
        return "disabled"
