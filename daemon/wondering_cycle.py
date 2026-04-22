# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
wondering_cycle.py — one exploratory probe per daemon cycle.

Called from daemon/maez_daemon.py after _reason() + store. Picks one open
wondering, asks the LLM for a single shell command that would advance it,
gates the command through safety + read-only checks, runs it (or queues a
pending card), synthesizes an evidence-tied learning, records the probe.

Hard contract:
  - At most ONE probe per daemon cycle. No inner loop.
  - Primary-first ordering: if the passed `deadline` doesn't leave room,
    skip this cycle and return. The primary daemon loop never degrades.
  - Never fabricate a learning. If evidence-tied synthesis fails, store
    the LEARNING_SYNTH_BLOCKED sentinel verbatim.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from core import llm_client as _llm_client
from core import tool_loop
from core import wonderings as _wonderings
from core.ambient_format import ambient_prompt_block

logger = logging.getLogger("maez.wondering_cycle")
# One-line outcome emits land on the cognition logger so all per-cycle
# quality signals live in a single file (cognition.log). Logger name
# matches the one set up in core/cognition_quality.py (its file handler
# is attached to "maez.cognition") — use the same name so our lines
# flow into the same file without needing our own handler.
_cog_logger = logging.getLogger("maez.cognition")


def _emit_outcome(
    *,
    wondering: Optional[dict],
    action: str,
    evidence_tied: bool = False,
    synth_state: str = "na",
    rc: Optional[int] = None,
    cmd: str = "",
) -> None:
    """One INFO line per advance_one() return path. Greppable shape:
    `wondering | wid=... action=... evidence_tied=0/1 synth_state=... rc=... cmd=...`
    When no probe ran (lock-busy / budget-skip) include `q=<question>`
    so starvation of a specific wondering is obvious at a glance.
    """
    wid = wondering.get("id") if wondering else None
    # Shape matches existing cognition.log lines (`| cycle | ...`,
    # `| policy | ...`) so a grep on `| wondering |` picks up only
    # our rows cleanly.
    # The cognition.log formatter already writes `<ts> | <msg>`, so we
    # start with `wondering |` — resulting line is `<ts> | wondering | ...`
    parts = [
        "wondering |",
        f"wid={wid}",
        f"action={action}",
        f"evidence_tied={1 if evidence_tied else 0}",
        f"synth_state={synth_state}",
        f"rc={rc if rc is not None else 'null'}",
    ]
    if cmd:
        parts.append(f"cmd={cmd[:60].replace(chr(10), ' ')}")
    if action in ("skipped_lock_busy", "skipped_budget") and wondering:
        q = (wondering.get("question") or "").strip().replace("\n", " ")
        parts.append(f"q={q[:50]}")
    _cog_logger.info(" ".join(parts))

# Internal budget. The outer `deadline` param can shrink this further; we
# never extend past it.
_INTERNAL_CAP_SEC = 25.0
_PROBE_LLM_TOKENS = 500
_SYNTH_LLM_TOKENS = 120
_MIN_REMAINING_FOR_ADVANCE = 10.0  # skip if less than this available


def _probe_prompt(wondering: dict, prior_probes: list[dict]) -> str:
    """Build the single-probe prompt. Short on purpose."""
    lines: list[str] = []
    ambient = ambient_prompt_block()
    if ambient:
        lines.append(ambient)
        lines.append("")
    lines.append("You are advancing ONE open wondering with ONE shell probe.")
    lines.append("")
    lines.append(f"Wondering #{wondering['id']}: {wondering['question']}")
    lines.append(f"Status: {wondering['status']}  advances: "
                 f"{wondering['advance_count']}")
    if prior_probes:
        lines.append("")
        lines.append("Prior probes (most recent last):")
        for p in reversed(prior_probes):
            cmd = (p.get("cmd") or "").strip().splitlines()[0][:120]
            learn = (p.get("learning") or "").strip()[:160]
            rc = p.get("returncode")
            lines.append(f"  - `{cmd}` (rc={rc}) → {learn}")
    lines.append("")
    lines.append("Reply with EXACTLY ONE of:")
    lines.append("  1. A single ```bash fenced command (one line, no "
                 "explanation before or after) that would meaningfully "
                 "advance the question.")
    lines.append("  2. `RESOLVED: <one-sentence conclusion>` if the "
                 "question is now answered by the probes above.")
    lines.append("  3. `ABANDON: <one-sentence reason>` if the question "
                 "turned out to be unanswerable from this vantage.")
    lines.append("")
    lines.append("Prefer read-only probes (ps, ls, grep, cat, systemctl "
                 "is-active, journalctl, free, du, df, find). Writes and "
                 "sudo will be routed to the owner for approval — that is "
                 "fine when truly needed but costs a cycle.")
    return "\n".join(lines)


def _synthesis_prompt(wondering: dict, cmd: str, stdout: str, stderr: str,
                       rc: int) -> str:
    lines: list[str] = []
    lines.append(f"Wondering: {wondering['question']}")
    lines.append(f"Probe: {cmd}")
    lines.append(f"exit code: {rc}")
    if stdout.strip():
        lines.append("stdout:")
        lines.append(stdout.strip()[:1500])
    if stderr.strip():
        lines.append("stderr:")
        lines.append(stderr.strip()[:600])
    lines.append("")
    lines.append("In ONE sentence: what did this probe actually show about "
                 "the wondering? Quote or paraphrase concrete tokens from "
                 "the output. Do NOT say 'I've noted' or 'I've recorded' "
                 "or 'manifest'. Do NOT invent fields that aren't in the "
                 "output. If the output is empty, reply exactly: "
                 "probe returned no output")
    return "\n".join(lines)


def _call_llm(system_prompt: str, user_prompt: str,
               num_predict: int, model: str) -> str:
    try:
        resp = _llm_client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            think=False,
            options={"temperature": 0.6, "num_predict": num_predict},
        )
        return (resp.message.content or "").strip()
    except Exception as e:
        logger.warning("wondering LLM call failed: %s", e)
        return ""


def _parse_decision(text: str) -> tuple[str, Optional[str]]:
    """Returns (kind, payload). kind ∈ {resolve, abandon, probe, none}."""
    t = text.strip()
    if not t:
        return "none", None
    # Check RESOLVED / ABANDON first — case-insensitive at line starts
    for line in t.splitlines():
        s = line.strip()
        up = s.upper()
        if up.startswith("RESOLVED:"):
            return "resolve", s.split(":", 1)[1].strip()
        if up.startswith("ABANDON:") or up.startswith("ABANDONED:"):
            return "abandon", s.split(":", 1)[1].strip()
    cmds = tool_loop.extract_shell_commands(t)
    if cmds:
        # One probe only — first line of the first block
        first = cmds[0].strip().splitlines()[0].strip()
        if first:
            return "probe", first
    return "none", None


def _queue_card(cmd: str, wondering_id: int, daemon) -> Optional[int]:
    """Queue a pending_card with a wondering_id link. Returns card id."""
    try:
        pipe = (daemon.telegram._get_pipeline()
                if hasattr(daemon, "telegram")
                and hasattr(daemon.telegram, "_get_pipeline")
                else None)
        store = pipe.card_store if pipe else None
        if store is None:
            from core.pending_cards import PendingCardStore
            store = PendingCardStore()
        card = store.create_card(
            action="run_shell",
            params={"cmd": cmd, "wondering_id": wondering_id},
            reason=f"wondering #{wondering_id} probe needs approval",
            plain_english=f"Run `{cmd}` to advance a wondering.",
        )
        return getattr(card, "request_id", None) or getattr(card, "id", None)
    except Exception as e:
        logger.warning("could not queue pending card: %s", e)
        return None


def advance_one(daemon, deadline: Optional[float] = None) -> Optional[dict]:
    """Advance one wondering by one probe. Returns a small result dict
    (for logging / UI) or None if nothing was done.

    `daemon` is the MaezDaemon instance — we need it for system_prompt,
    telegram/pending-card access, LLM backend lock, and the model name.
    `deadline` is an absolute time.time() bound from the caller; we stop
    if we don't have at least _MIN_REMAINING_FOR_ADVANCE seconds.

    Invariants enforced here:
      1. Additive cadence: if the daemon's ollama lock is held (primary
         cycle / voice / retry path), we yield the cycle entirely.
         Curiosity never waits on the brain's main lane.
      2. Evidence-tied learning: synthesis-timeout (no time left) and
         synthesis-invalidated (LLM fabricated) write distinct sentinels
         so the second is independently watchable.
      3. One log line per return path on the cognition.log seam.
    """
    start = time.time()
    internal_deadline = start + _INTERNAL_CAP_SEC
    effective_deadline = min(internal_deadline,
                             deadline) if deadline else internal_deadline

    if effective_deadline - start < _MIN_REMAINING_FOR_ADVANCE:
        # No wondering picked yet — no wid to attach. Still emit so
        # starvation-by-budget shows up in the cognition log.
        _emit_outcome(wondering=None, action="skipped_budget")
        return None

    store = _wonderings.get_store()
    wondering = store.pick_next()
    if not wondering:
        return None

    # Invariant #1: non-blocking acquire of the daemon's LLM lane lock.
    # If we can't get it instantly, the primary cycle / voice / retry
    # path is using the backend — yield this cycle entirely rather than
    # compete. A held lock also means llama-server/ollama is already
    # busy; waiting would just stretch the heartbeat.
    ollama_lock = getattr(daemon, "_ollama_lock", None)
    acquired = True
    if ollama_lock is not None:
        acquired = ollama_lock.acquire(timeout=0)
    if not acquired:
        _emit_outcome(wondering=wondering, action="skipped_lock_busy")
        return {"wondering_id": wondering["id"],
                "action": "skipped_lock_busy"}

    try:
        return _advance_one_locked(
            daemon, store, wondering, effective_deadline,
        )
    finally:
        if ollama_lock is not None and acquired:
            try:
                ollama_lock.release()
            except RuntimeError:
                # Already released somewhere in error recovery.
                pass


def _advance_one_locked(daemon, store, wondering, effective_deadline):
    """Body of advance_one, run with the ollama lock held. Split out so
    the lock try/finally stays narrow and the normal code path reads
    linearly."""
    wid = wondering["id"]
    prior = store.recent_probes(wid, limit=5)
    system_prompt = getattr(daemon, "system_prompt", "") or ""
    # Model alias flows from core.model_config (/etc/maez/model.env); no
    # hardcoded names. daemon.maez_daemon.MODEL is itself an import of
    # PRIMARY_MODEL from that module — kept as a stable attribute for
    # legacy callers but resolves to the same value.
    from core.model_config import PRIMARY_MODEL as _default_model
    model = getattr(__import__("daemon.maez_daemon", fromlist=["MODEL"]),
                    "MODEL", _default_model)

    # 1) Ask for a probe (or resolve/abandon)
    probe_prompt = _probe_prompt(wondering, prior)
    reply = _call_llm(system_prompt, probe_prompt,
                      _PROBE_LLM_TOKENS, model)
    kind, payload = _parse_decision(reply)

    if kind == "resolve":
        store.resolve(wid, payload or "(no conclusion text)")
        _emit_outcome(wondering=wondering, action="resolved")
        logger.info("wondering #%d resolved by daemon", wid)
        return {"wondering_id": wid, "action": "resolved",
                "text": payload}
    if kind == "abandon":
        store.abandon(wid, payload or "(no reason text)")
        _emit_outcome(wondering=wondering, action="abandoned")
        logger.info("wondering #%d abandoned by daemon", wid)
        return {"wondering_id": wid, "action": "abandoned",
                "text": payload}
    if kind == "none" or not payload:
        store.record_probe(
            wid, cmd="(no command proposed)", stdout="", stderr="",
            rc=0, learning="no probe proposed this cycle",
            evidence_tied=False, deferred=True,
        )
        _emit_outcome(wondering=wondering, action="no_probe")
        return {"wondering_id": wid, "action": "no_probe"}

    cmd = payload

    # 2) Safety gate — covenant + destructive dirs
    refused = tool_loop.safety_check(cmd)
    if refused:
        store.record_probe(
            wid, cmd=cmd, stdout="", stderr=f"refused: {refused}",
            rc=0, learning=_wonderings.LEARNING_SYNTH_BLOCKED,
            evidence_tied=False, deferred=True,
        )
        logger.info("wondering #%d probe refused by safety: %s",
                    wid, refused)
        if store.should_block(wid):
            store.mark_blocked(wid, pending_card_id=0)
        _emit_outcome(wondering=wondering, action="safety_refused",
                       synth_state="na", cmd=cmd)
        return {"wondering_id": wid, "action": "safety_refused",
                "cmd": cmd, "reason": refused}

    # 3) Read-only gate — auto-exec, else queue a card
    if not tool_loop.is_read_only(cmd):
        card_id = _queue_card(cmd, wid, daemon)
        probe_id = store.record_probe(
            wid, cmd=cmd, stdout="", stderr="",
            rc=0, learning=_wonderings.LEARNING_SYNTH_BLOCKED,
            evidence_tied=False, deferred=True,
            pending_card_id=card_id if isinstance(card_id, int) else None,
        )
        if store.should_block(wid):
            store.mark_blocked(
                wid,
                pending_card_id=card_id if isinstance(card_id, int) else 0,
            )
        logger.info("wondering #%d probe queued as card: %s",
                    wid, cmd[:120])
        _emit_outcome(wondering=wondering, action="card_queued",
                       synth_state="na", cmd=cmd)
        return {"wondering_id": wid, "action": "card_queued",
                "cmd": cmd, "probe_id": probe_id}

    # 4) Auto-exec read-only probe
    remaining = effective_deadline - time.time()
    if remaining < 5.0:
        logger.debug("wondering cycle: not enough time left (%.1fs) to run "
                     "probe — skipping store-side recording", remaining)
        _emit_outcome(wondering=wondering, action="skipped_budget",
                       cmd=cmd)
        return None
    exec_timeout = max(3, min(int(remaining - 2), tool_loop.TOOL_TIMEOUT_SEC))
    stdout, stderr, rc = tool_loop.run_shell(cmd, timeout=exec_timeout)
    logger.info("wondering #%d probe ran: `%s` (rc=%d, %d bytes stdout)",
                wid, cmd[:100], rc, len(stdout))

    # 5) Synthesis — evidence-tied learning, split sentinels:
    #    - LEARNING_SYNTH_TIMEOUT: no synth call, out of budget (benign)
    #    - LEARNING_SYNTH_BLOCKED: synth ran, validate_learning rejected
    #      the response (the real drift signal — LLM tried to fabricate)
    remaining = effective_deadline - time.time()
    learning = ""
    evidence_tied = False
    synth_state: str
    if remaining >= 3.0:
        synth_prompt = _synthesis_prompt(wondering, cmd, stdout, stderr, rc)
        synth_reply = _call_llm(system_prompt, synth_prompt,
                                 _SYNTH_LLM_TOKENS, model)
        candidate = (synth_reply or "").strip().splitlines()
        candidate = candidate[0].strip() if candidate else ""
        if candidate and _wonderings.validate_learning(
            candidate, stdout, stderr, rc,
        ):
            learning = candidate
            evidence_tied = True
            synth_state = "tied"
        else:
            learning = _wonderings.LEARNING_SYNTH_BLOCKED
            evidence_tied = False
            synth_state = "invalidated"
    else:
        learning = _wonderings.LEARNING_SYNTH_TIMEOUT
        evidence_tied = False
        synth_state = "timeout"

    probe_id = store.record_probe(
        wid, cmd=cmd, stdout=stdout, stderr=stderr, rc=rc,
        learning=learning, evidence_tied=evidence_tied, deferred=False,
    )

    # 6) Mirror the learning into long-term memory when we actually tied
    # it to evidence. This lets recall_for_cycle surface earned probes
    # alongside other cycle thoughts.
    if evidence_tied:
        try:
            mem = getattr(daemon, "memory", None)
            if mem is not None:
                mem.store(
                    f"wondering #{wid}: {wondering['question']}\n"
                    f"probe: {cmd}\nlearning: {learning}",
                    cycle=getattr(daemon, "cycle_count", 0),
                    snapshot={},
                    metadata={
                        "type": "wondering_advance",
                        "wondering_id": wid,
                    },
                )
        except Exception as e:
            logger.debug("memory mirror of wondering failed: %s", e)

    _emit_outcome(wondering=wondering, action="advanced",
                   evidence_tied=evidence_tied, synth_state=synth_state,
                   rc=rc, cmd=cmd)
    return {
        "wondering_id": wid, "action": "advanced",
        "cmd": cmd, "rc": rc, "evidence_tied": evidence_tied,
        "probe_id": probe_id, "learning": learning,
    }
