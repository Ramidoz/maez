# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Evidence-envelope builder (Slice 3 proper, 2026-05-07).

Implements the ratified contracts from
``docs/SLICE_3_0d_TOKEN_BUDGET_MEMO.md``:

  §1   3K-token total cap → 12K-char enforcement (chars_per_token=4)
  §2   Per-section caps (tool_results 8x200, claimable 15x100,
       forbidden 8x80, self_history 5x200, signals 12x30 each)
  §3   Truncation order: tool_result body → claimable → self_history,
       preserving forbidden + signals.
  §3a  Minimal-envelope fallback when steps 1-5 still over cap.
  §4   ``maez.envelope`` WARNING log per truncation event.
  §5   Tool-result entry shape: ``name``, ``status``, ``tool_call_id``,
       ``summary``.
  §6   Builder owns caps + telemetry; class-level ``MAX_*`` constants
       so audit can introspect; ``envelope_chars_final`` stamped.
  §7   ``MAEZ_EVIDENCE_ENVELOPE_BUDGET_TOKENS`` (default 3000) and
       ``MAEZ_EVIDENCE_ENVELOPE_DISABLED`` honored.

The output dict passes :func:`core.ledger.envelope_schema.validate_envelope`.
A backward-compat free function :func:`build_envelope` instantiates
the class once per call — earlier callers (slice 3 foundation) keep
working unchanged.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Iterable

from core.ledger import envelope_schema as _es
from core.ledger import recent_turns as _rt

__all__ = [
    "BoundedEnvelopeBuilder",
    "build_envelope",
    "default_ledger_db_path",
    "render_envelope_for_prompt",
    "resolve_recall_cap_chars",
    "DEFAULT_SELF_HISTORY_LIMIT",
    "ENVELOPE_SCHEMA_VERSION",
]


def default_ledger_db_path() -> str | None:
    """Resolve the canonical ledger DB path for callers that don't
    already have a daemon-scoped reference.

    Returns ``MAEZ_LEDGER_DB_PATH`` if set and the file exists; else
    ``<maez_home>/memory/ledger.db`` if it exists; else ``None``.
    Builder semantics treat ``None`` as "no self_history available
    this turn" — best-effort grounding, never raises.
    """
    raw = os.environ.get("MAEZ_LEDGER_DB_PATH")
    if raw and os.path.exists(raw):
        return raw
    try:
        from pathlib import Path as _Path
        from core.infra.paths import home as _maez_home
        path = _Path(_maez_home()) / "memory" / "ledger.db"
        return str(path) if path.exists() else None
    except Exception:
        return None


def render_envelope_for_prompt(envelope: dict | None) -> str:
    """Render the LEDGER_ENVELOPE_SCHEMA §3.2 constraint block.

    The block is what the daemon injects into the LLM's generation
    prompt so the model sees, BEFORE generating, what's permitted and
    what's forbidden. Returns ``""`` when the envelope is None
    (disabled bypass) or carries no constraints — keeps the prompt
    identical to legacy in those cases. The block itself looks like::

        [EVIDENCE ENVELOPE — TURN <turn_id>]
        You may claim:
          - "owner is at his desk"  (observed)
          - "owner asked about X"   (owner-said)
        You may NOT claim:
          - anything about the calendar (signal absent: calendar)
        If you must speak about a forbidden topic, name the absence
        instead of confabulating.
        [END ENVELOPE]
    """
    if envelope is None:
        return ""

    claimable = envelope.get("claimable") or []
    forbidden = envelope.get("forbidden") or []
    signals_absent = envelope.get("signals_absent") or []
    truncated = envelope.get("_truncated") is True

    if not claimable and not forbidden and not signals_absent and not truncated:
        return ""

    turn_id = envelope.get("turn_id") or ""
    header = (
        f"[EVIDENCE ENVELOPE — TURN {turn_id}]" if turn_id
        else "[EVIDENCE ENVELOPE]"
    )
    if truncated:
        header += " (truncated)"

    lines = [header]

    if claimable:
        claimable_lines = []
        for c in claimable:
            text = c.get("text") or c.get("fact") or ""
            if not text:
                # Skip degenerate entries — emitting `  - ""` produces
                # a malformed prompt-block line the model has no way
                # to act on. Reviewer-flagged 2026-05-07.
                continue
            prov = c.get("provenance") or ""
            evidence = c.get("evidence") or c.get("evidence_refs") or ""
            tail_bits = []
            if prov:
                tail_bits.append(str(prov))
            if evidence:
                # JSON-shape structured evidence (dict/list) for the
                # model rather than Python repr — single-quoted keys
                # confuse downstream JSON-aware tooling. Fall back to
                # str() for non-JSON-able payloads.
                if isinstance(evidence, (dict, list)):
                    try:
                        tail_bits.append(
                            json.dumps(evidence, default=str,
                                       ensure_ascii=False),
                        )
                    except (TypeError, ValueError):
                        tail_bits.append(str(evidence))
                else:
                    tail_bits.append(str(evidence))
            tail = f"  ({'; '.join(tail_bits)})" if tail_bits else ""
            claimable_lines.append(f'  - "{text}"{tail}')
        if claimable_lines:
            lines.append("You may claim:")
            lines.extend(claimable_lines)

    forbidden_lines = []
    for f in forbidden:
        topic = f.get("topic") or f.get("text") or f.get("fact") or ""
        reason = f.get("reason") or ""
        if topic:
            tail = f" (signal absent: {reason})" if reason else ""
            forbidden_lines.append(f"  - anything about {topic}{tail}")
    for s in signals_absent:
        if s and not any(s in line for line in forbidden_lines):
            forbidden_lines.append(
                f"  - anything about {s} (signal absent: {s})"
            )

    if forbidden_lines:
        lines.append("You may NOT claim:")
        lines.extend(forbidden_lines)
        lines.append(
            "If you must speak about a forbidden topic, name the absence "
            "instead of confabulating."
        )

    lines.append("[END ENVELOPE]")
    return "\n".join(lines)


# Matches the ledger meta.schema_version (see migrations/0001_init.sql
# and core.ledger.migrate). Bumped only when the envelope wire shape
# breaks back-compat. Slice 3 proper (2026-05-07) keeps version 1.
ENVELOPE_SCHEMA_VERSION = 1


# Slice 3.0d §1: the recall cap reduces from 60K → 52K when an
# envelope will be present in the prompt. Disabled mode reverts to
# the legacy 60K. Single decision point so daemon recall builder and
# any other caller produce the same number for the same condition.
def resolve_recall_cap_chars() -> int:
    """Return the recall-block char cap to use this turn.

    Per SLICE_3_0d §1: 52_000 chars (≈13K tokens) when an envelope
    will appear in the prompt; 60_000 chars (legacy) when
    ``MAEZ_EVIDENCE_ENVELOPE_DISABLED=1``. Override the with-envelope
    value via ``MAEZ_RECALL_CAP_WITH_ENVELOPE_CHARS``. Invalid values
    fall back to the default.
    """
    if os.environ.get("MAEZ_EVIDENCE_ENVELOPE_DISABLED") == "1":
        return 60_000
    raw = os.environ.get("MAEZ_RECALL_CAP_WITH_ENVELOPE_CHARS")
    if raw is None:
        return 52_000
    try:
        value = int(raw)
    except ValueError:
        _log.warning(
            "maez.envelope: invalid "
            "MAEZ_RECALL_CAP_WITH_ENVELOPE_CHARS=%r — using default 52000",
            raw,
        )
        return 52_000
    if value < 0:
        # Negative values were silently clamped to 0 pre-2026-05-07,
        # producing an empty memory block with no operator signal.
        # Reviewer-flagged: warn + return the default rather than
        # honor a nonsensical override.
        _log.warning(
            "maez.envelope: invalid negative "
            "MAEZ_RECALL_CAP_WITH_ENVELOPE_CHARS=%d — using default 52000",
            value,
        )
        return 52_000
    return value


_log = logging.getLogger("maez.envelope")


# Slice 3.0d §2 cap for self_history rows when builder populates
# from the ledger. Same as MAX_SELF_HISTORY on the class — kept as
# a module-level alias for the free-function call sites.
DEFAULT_SELF_HISTORY_LIMIT = 5


def _truncate(text: str, n: int) -> str:
    text = text.strip() if isinstance(text, str) else ""
    if len(text) <= n:
        return text
    return text[: n - 1] + "…"


class BoundedEnvelopeBuilder:
    """Single source of truth for envelope construction + budget
    enforcement. Per memo §6, all caps live on this class as
    ``MAX_*`` constants so the audit layer can introspect them
    without parsing the memo.

    The class is stateless across builds — each :meth:`build` call is
    a self-contained construction. Reusing one instance is fine; so
    is constructing fresh per call. The free function
    :func:`build_envelope` does the latter.
    """

    # ── §2 per-section caps ────────────────────────────────────────
    MAX_TOOL_RESULTS = 8
    MAX_TOOL_RESULT_SUMMARY_CHARS = 200
    MAX_CLAIMABLE = 15
    MAX_CLAIMABLE_ENTRY_CHARS = 100
    MAX_FORBIDDEN = 8
    MAX_FORBIDDEN_ENTRY_CHARS = 80
    MAX_SELF_HISTORY = 5
    MAX_SELF_HISTORY_SUMMARY_CHARS = _es.SELF_HISTORY_SUMMARY_MAX  # 200
    MAX_SIGNALS = 12
    MAX_SIGNAL_ENTRY_CHARS = 30

    # ── §3a minimal-envelope fallback floor caps ───────────────────
    MAX_FALLBACK_TOOLS = 8
    MAX_FALLBACK_FORBIDDEN = 8
    MAX_FALLBACK_SIGNALS_CHARS = 480

    # ── §7 conversion + defaults ───────────────────────────────────
    CHARS_PER_TOKEN = 4
    DEFAULT_TOKEN_CAP = 3000

    def _resolved_token_cap(self, override: int | None) -> int:
        if override is not None:
            return max(0, int(override))
        env = os.environ.get("MAEZ_EVIDENCE_ENVELOPE_BUDGET_TOKENS")
        if env:
            try:
                return max(0, int(env))
            except ValueError:
                _log.warning(
                    "maez.envelope: invalid "
                    "MAEZ_EVIDENCE_ENVELOPE_BUDGET_TOKENS=%r — using default",
                    env,
                )
        return self.DEFAULT_TOKEN_CAP

    @staticmethod
    def _disabled_env() -> bool:
        return os.environ.get("MAEZ_EVIDENCE_ENVELOPE_DISABLED") == "1"

    def build(
        self,
        *,
        ledger_db_path: str | None,
        signals_present: Iterable[str],
        signals_absent: Iterable[str],
        tool_results: Iterable[dict],
        claimable: Iterable[dict] | None = None,
        forbidden: Iterable[dict] | None = None,
        self_history_limit: int | None = None,
        tenant_id: str = "owner",
        turn_id: str | None = None,
        token_cap: int | None = None,
        char_cap: int | None = None,
    ) -> dict | None:
        """Build a §3-shape evidence envelope with all caps applied.

        Returns a dict that always passes ``validate_envelope`` —
        EXCEPT when the bypass env var is set, in which case returns
        ``None`` (per memo §7: "skip envelope construction entirely").
        Callers MUST check for ``None`` and fall through to the legacy
        signals path; passing a degenerate empty envelope under
        ``judge()``'s full-takeover semantics would erase legacy
        signals — the opposite of what an emergency bypass should do.

        ``turn_id`` flows into telemetry (§4 required field). ``token_cap``
        / ``char_cap`` override env-var configuration (test ergonomics);
        ``char_cap`` wins if both supplied.
        """
        if self._disabled_env():
            return None

        # ── resolve cap arithmetic (tokens → chars) ────────────────
        if char_cap is None:
            tcap = self._resolved_token_cap(token_cap)
            ccap = tcap * self.CHARS_PER_TOKEN
        else:
            ccap = max(0, int(char_cap))
            tcap = ccap // self.CHARS_PER_TOKEN

        sh_limit = (
            self.MAX_SELF_HISTORY if self_history_limit is None
            else min(self_history_limit, self.MAX_SELF_HISTORY)
        )

        # ── §2 per-section soft caps (count + per-entry text) ──────
        # Each normalizer returns (capped, uncapped, drops). The
        # uncapped variant is the same shape-cleaned list with NO
        # count/text caps applied — used to compute real
        # envelope_chars_before for telemetry (§4 contract: per-
        # section logs must carry actual envelope sizes, not -1
        # sentinels).
        tr_cap, tr_un, tr_drops = self._normalize_tool_results(tool_results)
        cl_cap, cl_un, cl_drops = self._normalize_claimable(claimable or [])
        fb_cap, fb_un, fb_drops = self._normalize_forbidden(forbidden or [])
        sh_cap = self._populate_self_history(
            ledger_db_path, limit=sh_limit, tenant_id=tenant_id,
        )
        sp_cap, sp_un, sp_drops = self._normalize_signals(signals_present)
        sa_cap, sa_un, sa_drops = self._normalize_signals(signals_absent)

        # §3.1 schema-doc metadata: schema_version always present;
        # built_at always present (build-time wall clock);
        # turn_id when supplied. Permissive validate_envelope tolerates
        # these unknowns even though they're not in its slot list.
        env: dict = {
            "schema_version": ENVELOPE_SCHEMA_VERSION,
            "built_at": time.time(),
            "tool_results": tr_cap,
            "claimable": cl_cap,
            "forbidden": fb_cap,
            "self_history": sh_cap,
            "signals_present": sp_cap,
            "signals_absent": sa_cap,
        }
        if turn_id:
            env["turn_id"] = turn_id
        before_chars = self._envelope_chars(env)

        # Per-section telemetry: for each section that took a cap,
        # envelope_chars_before = total chars if THIS section were
        # uncapped (other sections at their capped size);
        # envelope_chars_after = current envelope chars.
        for name, uncapped, drops in (
            ("tool_results", tr_un, tr_drops),
            ("claimable", cl_un, cl_drops),
            ("forbidden", fb_un, fb_drops),
            ("signals_present", sp_un, sp_drops),
            ("signals_absent", sa_un, sa_drops),
        ):
            if drops["entries"] == 0 and drops["chars"] == 0:
                continue
            hyp = dict(env)
            hyp[name] = uncapped
            chars_before_sec = self._envelope_chars(hyp)
            self._emit_truncation(
                section=name,
                truncation_kind="per_section_cap",
                dropped_entries=drops["entries"],
                dropped_chars=drops["chars"],
                envelope_chars_before=chars_before_sec,
                envelope_chars_after=before_chars,
                char_cap=ccap, token_cap=tcap,
                cap_hit="per_section",
                turn_id=turn_id,
            )

        # ── §3 total-cap truncation ────────────────────────────────
        if before_chars > ccap:
            env = self._apply_total_cap_order(
                env, char_cap=ccap, token_cap=tcap, turn_id=turn_id,
            )

        # ── §3a minimal fallback if still over ─────────────────────
        after_chars = self._envelope_chars(env)
        if after_chars > ccap:
            env = self._minimal_fallback(
                env, char_cap=ccap, token_cap=tcap,
                turn_id=turn_id, before_chars=after_chars,
            )

        self._stamp_chars_final(env)
        return env

    @staticmethod
    def _stamp_chars_final(env: dict) -> None:
        """Per memo §6, ``envelope_chars_final`` records the actual
        delivered envelope size — i.e. the JSON length INCLUDING the
        stamp itself. The value depends on its own digit count, so we
        fixed-point iterate until stable. Converges in ≤ 2 iterations
        for any envelope under ~10^9 chars."""
        env["envelope_chars_final"] = 0
        for _ in range(4):
            measured = len(json.dumps(env, sort_keys=True, ensure_ascii=False))
            if measured == env["envelope_chars_final"]:
                return
            env["envelope_chars_final"] = measured

    # SLICE_3_0d §5: tool_results.summary compression.
    # Limits applied per summary type:
    MAX_DICT_VALUE_CHARS = 80
    MAX_LIST_ITEMS = 3

    @classmethod
    def _compress_summary(cls, raw):
        """Compress a single tool_result.summary per memo §5.

        Returns (compressed_value, chars_dropped).
          * dict  → keep keys; truncate each str value past 80 chars
          * list  → keep first 3 items; append "(+M more dropped)"
          * str   → head-truncate to 200 chars + "…"
          * other → coerce via str() then string rule
        """
        if isinstance(raw, dict):
            saved = 0
            out = {}
            for k, v in raw.items():
                if isinstance(v, str) and len(v) > cls.MAX_DICT_VALUE_CHARS:
                    saved += len(v) - cls.MAX_DICT_VALUE_CHARS
                    out[k] = _truncate(v, cls.MAX_DICT_VALUE_CHARS)
                else:
                    out[k] = v
            return out, saved
        if isinstance(raw, list):
            if len(raw) <= cls.MAX_LIST_ITEMS:
                return list(raw), 0
            kept = list(raw[: cls.MAX_LIST_ITEMS])
            dropped_count = len(raw) - cls.MAX_LIST_ITEMS
            kept.append(f"(+{dropped_count} more dropped)")
            # "saved" tracks chars not delivered (rough estimate via
            # JSON length of the dropped tail) so per-section
            # telemetry stays honest.
            saved = len(json.dumps(raw[cls.MAX_LIST_ITEMS:],
                                   ensure_ascii=False))
            return kept, saved
        if isinstance(raw, str):
            if len(raw) > cls.MAX_TOOL_RESULT_SUMMARY_CHARS:
                saved = len(raw) - cls.MAX_TOOL_RESULT_SUMMARY_CHARS
                return _truncate(raw, cls.MAX_TOOL_RESULT_SUMMARY_CHARS), saved
            return raw, 0
        return cls._compress_summary(str(raw))

    # ── per-section normalizers ────────────────────────────────────
    # All normalizers return (capped, uncapped, drops). They do NOT
    # emit telemetry — the orchestrator in build() does that with
    # real envelope_chars_before/after computed via substitution.
    def _normalize_tool_results(
        self, items,
    ) -> tuple[list[dict], list[dict], dict]:
        items_list = list(items or [])
        # Uncapped: shape-cleaned, no count/summary caps. Same shape
        # rules as capped (drop non-dicts, keep memo §5 keys) so the
        # substitution measurement is apples-to-apples.
        uncapped: list[dict] = []
        for it in items_list:
            if not isinstance(it, dict):
                continue
            entry: dict = {}
            for key in ("name", "status", "tool_call_id"):
                if key in it:
                    entry[key] = it[key]
            if "summary" in it:
                entry["summary"] = it["summary"]
            uncapped.append(entry)

        dropped_n = max(0, len(uncapped) - self.MAX_TOOL_RESULTS)
        kept = uncapped[: self.MAX_TOOL_RESULTS]
        body_truncated_chars = 0
        capped: list[dict] = []
        for entry in kept:
            new = dict(entry)
            if "summary" in new:
                compressed, saved = self._compress_summary(new["summary"])
                new["summary"] = compressed
                body_truncated_chars += saved
            capped.append(new)
        return capped, uncapped, {
            "entries": dropped_n, "chars": body_truncated_chars,
        }

    def _normalize_claimable(
        self, items,
    ) -> tuple[list[dict], list[dict], dict]:
        uncapped = [dict(i) for i in items if isinstance(i, dict)]
        dropped_n = max(0, len(uncapped) - self.MAX_CLAIMABLE)
        # §3.2 — drop OLDEST first, keep most recent. Caller emits
        # oldest→newest, so preserve the tail.
        kept = uncapped[-self.MAX_CLAIMABLE:] if uncapped else []
        truncated_chars = 0
        capped: list[dict] = []
        for it in kept:
            entry = dict(it)
            if "text" in entry and isinstance(entry["text"], str):
                if len(entry["text"]) > self.MAX_CLAIMABLE_ENTRY_CHARS:
                    truncated_chars += (
                        len(entry["text"]) - self.MAX_CLAIMABLE_ENTRY_CHARS
                    )
                    entry["text"] = _truncate(
                        entry["text"], self.MAX_CLAIMABLE_ENTRY_CHARS,
                    )
            capped.append(entry)
        return capped, uncapped, {
            "entries": dropped_n, "chars": truncated_chars,
        }

    def _normalize_forbidden(
        self, items,
    ) -> tuple[list[dict], list[dict], dict]:
        uncapped = [dict(i) for i in items if isinstance(i, dict)]
        dropped_n = max(0, len(uncapped) - self.MAX_FORBIDDEN)
        kept = uncapped[: self.MAX_FORBIDDEN]
        truncated_chars = 0
        capped: list[dict] = []
        for it in kept:
            entry = dict(it)
            for field in ("text", "topic", "reason"):
                v = entry.get(field)
                if (isinstance(v, str)
                        and len(v) > self.MAX_FORBIDDEN_ENTRY_CHARS):
                    truncated_chars += (
                        len(v) - self.MAX_FORBIDDEN_ENTRY_CHARS
                    )
                    entry[field] = _truncate(
                        v, self.MAX_FORBIDDEN_ENTRY_CHARS,
                    )
            capped.append(entry)
        return capped, uncapped, {
            "entries": dropped_n, "chars": truncated_chars,
        }

    def _normalize_signals(
        self, items,
    ) -> tuple[list[str], list[str], dict]:
        # Uncapped: dedup-only (no count/per-entry caps). Capped also
        # dedups (the operating-envelope shape) — drops counted are
        # the increment from cap enforcement, not from dedup.
        seen_un: set[str] = set()
        uncapped: list[str] = []
        for v in items or []:
            if not isinstance(v, str) or v in seen_un:
                continue
            seen_un.add(v)
            uncapped.append(v)

        seen: set[str] = set()
        capped: list[str] = []
        dropped_n = 0
        truncated_chars = 0
        for v in uncapped:
            t = v
            if len(t) > self.MAX_SIGNAL_ENTRY_CHARS:
                truncated_chars += len(t) - self.MAX_SIGNAL_ENTRY_CHARS
                t = _truncate(t, self.MAX_SIGNAL_ENTRY_CHARS)
            if t in seen:
                # post-truncation collision (rare): treat as a drop.
                dropped_n += 1
                continue
            if len(capped) >= self.MAX_SIGNALS:
                dropped_n += 1
                continue
            seen.add(t)
            capped.append(t)
        return capped, uncapped, {
            "entries": dropped_n, "chars": truncated_chars,
        }

    # ── §3 total-cap truncation order ──────────────────────────────
    def _apply_total_cap_order(
        self, env: dict, *, char_cap: int, token_cap: int, turn_id,
    ) -> dict:
        """§3: drop bulk first. tool_result body bytes → claimable
        entries → self_history entries → preserve forbidden + signals."""
        before = self._envelope_chars(env)

        # Step 1: zero out tool_result bodies (keep name+status).
        if self._envelope_chars(env) > char_cap and env.get("tool_results"):
            stripped = []
            saved = 0
            for tr in env["tool_results"]:
                new = {k: v for k, v in tr.items() if k != "summary"}
                saved += len(str(tr.get("summary", "")))
                stripped.append(new)
            env["tool_results"] = stripped
            self._emit_truncation(
                section="tool_results",
                truncation_kind="total_cap",
                dropped_entries=0,
                dropped_chars=saved,
                envelope_chars_before=before,
                envelope_chars_after=self._envelope_chars(env),
                char_cap=char_cap, token_cap=token_cap,
                cap_hit="total",
                turn_id=turn_id,
            )

        # Step 2: drop claimable oldest-first until under cap.
        while (self._envelope_chars(env) > char_cap
               and env.get("claimable")):
            dropped = env["claimable"].pop(0)
            self._emit_truncation(
                section="claimable",
                truncation_kind="total_cap",
                dropped_entries=1,
                dropped_chars=len(json.dumps(dropped, ensure_ascii=False)),
                envelope_chars_before=before,
                envelope_chars_after=self._envelope_chars(env),
                char_cap=char_cap, token_cap=token_cap,
                cap_hit="total",
                turn_id=turn_id,
            )

        # Step 3: drop self_history oldest-first.
        while (self._envelope_chars(env) > char_cap
               and env.get("self_history")):
            dropped = env["self_history"].pop()  # oldest = end (DESC order)
            self._emit_truncation(
                section="self_history",
                truncation_kind="total_cap",
                dropped_entries=1,
                dropped_chars=len(json.dumps(dropped, ensure_ascii=False)),
                envelope_chars_before=before,
                envelope_chars_after=self._envelope_chars(env),
                char_cap=char_cap, token_cap=token_cap,
                cap_hit="total",
                turn_id=turn_id,
            )

        return env

    # ── §3a minimal-envelope fallback ──────────────────────────────
    def _minimal_fallback(
        self, env: dict, *, char_cap: int, token_cap: int,
        turn_id, before_chars: int,
    ) -> dict:
        # Tool results: status-only, MAX_FALLBACK_TOOLS.
        tools_min = []
        for tr in env.get("tool_results", [])[: self.MAX_FALLBACK_TOOLS]:
            row = {}
            if "name" in tr:
                row["name"] = tr["name"]
            if "status" in tr:
                row["status"] = tr["status"]
            tools_min.append(row)

        forbidden_min = env.get("forbidden", [])[: self.MAX_FALLBACK_FORBIDDEN]

        # Combined signals limit.
        sp_chars = 0
        sa_chars = 0
        sp_min: list[str] = []
        sa_min: list[str] = []
        budget = self.MAX_FALLBACK_SIGNALS_CHARS
        for s in env.get("signals_present", []):
            cost = len(s)
            if sp_chars + sa_chars + cost > budget:
                break
            sp_min.append(s)
            sp_chars += cost
        for s in env.get("signals_absent", []):
            cost = len(s)
            if sp_chars + sa_chars + cost > budget:
                break
            sa_min.append(s)
            sa_chars += cost

        minimal: dict = {
            "schema_version": ENVELOPE_SCHEMA_VERSION,
            "tool_results": tools_min,
            "claimable": [],
            "forbidden": forbidden_min,
            "self_history": [],
            "signals_present": sp_min,
            "signals_absent": sa_min,
            "_truncated": True,
            "_truncation_reason": "preserved-sections exceeded cap",
        }
        # If even the minimal shape exceeds char_cap (extreme override
        # like BUDGET_TOKENS=10, or char_cap=0), emit unrenderable
        # shape per §3a. char_cap=0 is included intentionally: the
        # earlier `> 0` short-circuit was a bug — zero cap means
        # nothing fits, which IS the unrenderable case.
        if self._envelope_chars(minimal) > char_cap:
            minimal = {
                "schema_version": ENVELOPE_SCHEMA_VERSION,
                "tool_results": [],
                "claimable": [],
                "forbidden": [],
                "self_history": [],
                "signals_present": [],
                "signals_absent": [],
                "_truncated": True,
                "_truncation_reason": "envelope unrenderable",
            }
            _log.error(
                "maez.envelope: configured char_cap=%d below minimal "
                "fallback floor — emitting unrenderable envelope",
                char_cap,
            )

        after_chars = self._envelope_chars(minimal)
        self._emit_truncation(
            section="envelope",
            truncation_kind="minimal_fallback",
            dropped_entries=-1,  # entry count not meaningful here
            # Clamp to 0: minimal envelope can be larger than the
            # post-§3 env when defaults add back fields, but reporting
            # negative drops is semantically wrong.
            dropped_chars=max(0, before_chars - after_chars),
            envelope_chars_before=before_chars,
            envelope_chars_after=after_chars,
            char_cap=char_cap, token_cap=token_cap,
            cap_hit="minimal_fallback",
            turn_id=turn_id,
        )
        return minimal

    # ── self_history population (best-effort, ledger lookback) ─────
    def _populate_self_history(
        self, db_path: str | None, *, limit: int, tenant_id: str,
    ) -> list[dict]:
        if db_path is None or limit <= 0:
            return []
        try:
            rows = _rt.recent_turns_by_kind(
                db_path,
                kinds=list(_es.SELF_HISTORY_KINDS),
                limit=limit,
                tenant_id=tenant_id,
            )
        except Exception as exc:
            # Best-effort: ledger unreachable / locked / schema drift
            # produces an empty self_history rather than blocking
            # generation. Pre-2026-05-07 this swallowed the exception
            # silently — operators couldn't tell self-history
            # population was failing. Debug-log the cause; behavior
            # unchanged (still returns []).
            _log.debug(
                "self_history population skipped (ledger lookup "
                "failed for db_path=%r): %s",
                db_path, exc,
            )
            return []
        out: list[dict] = []
        for row in rows:
            out.append({
                "turn_id": row["turn_id"],
                "timestamp": row["timestamp"],
                "kind": row["turn_kind"],
                "utterance_summary": _truncate(
                    row["raw_text"] or "",
                    self.MAX_SELF_HISTORY_SUMMARY_CHARS,
                ),
            })
        return out

    # ── helpers ────────────────────────────────────────────────────
    @staticmethod
    def _envelope_chars(env: dict) -> int:
        # Stable, deterministic measure: canonical JSON length.
        # Excludes the envelope_chars_final stamp itself.
        if "envelope_chars_final" in env:
            env = {k: v for k, v in env.items() if k != "envelope_chars_final"}
        return len(json.dumps(env, sort_keys=True, ensure_ascii=False))

    def _emit_truncation(
        self, *, section, truncation_kind, dropped_entries, dropped_chars,
        envelope_chars_before, envelope_chars_after, char_cap, token_cap,
        cap_hit, turn_id,
    ) -> None:
        toks_before = (
            envelope_chars_before // self.CHARS_PER_TOKEN
            if envelope_chars_before >= 0 else -1
        )
        toks_after = (
            envelope_chars_after // self.CHARS_PER_TOKEN
            if envelope_chars_after >= 0 else -1
        )
        extra = {
            "section": section,
            "truncation_kind": truncation_kind,
            "dropped_entries": dropped_entries,
            "dropped_chars": dropped_chars,
            "envelope_chars_before": envelope_chars_before,
            "envelope_chars_after": envelope_chars_after,
            "envelope_tokens_estimated_before": toks_before,
            "envelope_tokens_estimated_after": toks_after,
            "char_cap": char_cap,
            "token_cap": token_cap,
            "cap_hit": cap_hit,
            "turn_id": turn_id or "",
        }
        _log.warning(
            "envelope_truncated section=%s kind=%s dropped_entries=%s "
            "dropped_chars=%s before=%s after=%s cap=%s",
            section, truncation_kind, dropped_entries, dropped_chars,
            envelope_chars_before, envelope_chars_after, char_cap,
            extra=extra,
        )


# ── module-level free function (compat shim for foundation tests) ──
def build_envelope(
    *,
    ledger_db_path: str | None,
    signals_present: Iterable[str],
    signals_absent: Iterable[str],
    tool_results: Iterable[dict],
    claimable: Iterable[dict] | None = None,
    forbidden: Iterable[dict] | None = None,
    self_history_limit: int = DEFAULT_SELF_HISTORY_LIMIT,
    tenant_id: str = "owner",
    turn_id: str | None = None,
    token_cap: int | None = None,
    char_cap: int | None = None,
) -> dict | None:
    """Convenience wrapper around :class:`BoundedEnvelopeBuilder`.

    Returns ``None`` when ``MAEZ_EVIDENCE_ENVELOPE_DISABLED=1`` per
    memo §7. See :meth:`BoundedEnvelopeBuilder.build`.
    """
    builder = BoundedEnvelopeBuilder()
    return builder.build(
        ledger_db_path=ledger_db_path,
        signals_present=signals_present,
        signals_absent=signals_absent,
        tool_results=tool_results,
        claimable=claimable,
        forbidden=forbidden,
        self_history_limit=self_history_limit,
        tenant_id=tenant_id,
        turn_id=turn_id,
        token_cap=token_cap,
        char_cap=char_cap,
    )
