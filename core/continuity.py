"""
continuity.py — Maez's runtime continuity layer.

PURPOSE
-------
This module ensures Maez survives restart as the same being,
not as a new process with old memories. It maintains a single
canonical bridge artifact — memory/continuity_capsule.json —
that captures who Maez was being, what it was working on, and
what remains unresolved at the moment of shutdown or restart.

HOW IT WORKS
------------
The capsule is written atomically (temp file + os.replace) at
three moments:
  1. Periodic checkpoint (every N cycles, or on critical state change)
  2. Pre-restart write (before evolution engine kills the daemon)
  3. Graceful shutdown (SIGTERM handler, best-effort)

On startup, the daemon loads the capsule before any greeting or
session-resume logic. If valid and fresh (< MAX_CAPSULE_AGE_HOURS),
a [CONTINUITY] block is injected into the reasoning prompt for
POST_RESTART_INJECTION_CYCLES cycles. This block tells Maez who
it was, what it was doing, and what not to redundantly announce.

After the orientation window, the capsule is archived and deleted.

INVARIANTS
----------
- Capsule is never stored in ChromaDB or used for semantic retrieval
- Partial write is never readable (atomic via os.replace)
- Missing capsule = cold start, not an error
- Stale capsule (>24h) is logged and ignored
- Capsule write failure never crashes the daemon
- Pre-restart path never blocks on a fresh LLM call
- Valid capsule suppresses restart-style greetings during orientation
"""

import json
import logging
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("maez")

# ══════════════════════════════════════════════════════════════════════
#  CONFIGURABLE CONSTANTS
# ══════════════════════════════════════════════════════════════════════

CONTINUITY_CHECKPOINT_INTERVAL = 10    # cycles between periodic writes
POST_RESTART_INJECTION_CYCLES = 5      # cycles to inject [CONTINUITY] after restart
MAX_CAPSULE_AGE_HOURS = 24             # capsule older than this is stale
RESUME_INSTRUCTIONS_CACHE_TTL = 300    # seconds before re-generating resume text

CAPSULE_PATH = Path("/home/rohit/maez/memory/continuity_capsule.json")
ARCHIVE_DIR = Path("/home/rohit/maez/memory/continuity_archive")
CAPSULE_VERSION = "1.0"


# ══════════════════════════════════════════════════════════════════════
#  CAPSULE BUILDING
# ══════════════════════════════════════════════════════════════════════

# Cache for resume instructions — avoid LLM call every checkpoint
_resume_cache: dict = {'text': None, 'generated_at': 0.0, 'mode': None,
                       'candidate': None, 'thread': None}


def _get_current_mode() -> str:
    """Derive current_mode from cognition policy and evolution state."""
    global _mode_override
    if _mode_override:
        mode = _mode_override
        _mode_override = None  # consume: one-shot
        return mode
    try:
        from skills.evolution_engine import _get_lock_state, _rail_conn
        lock = _get_lock_state()
        if lock.get('active_candidate_id') is not None:
            # Check if watchdog or post-edit
            with _rail_conn() as conn:
                row = conn.execute(
                    "SELECT state FROM candidates WHERE id=?",
                    (lock['active_candidate_id'],),
                ).fetchone()
            if row:
                if row[0] == 'applied':
                    return 'watchdog_active'
        # Check recent rollback
        with _rail_conn() as conn:
            recent_rb = conn.execute(
                "SELECT state, rollback_layer FROM candidates "
                "WHERE state='rolled_back' ORDER BY resolved_at DESC LIMIT 1"
            ).fetchone()
        if recent_rb:
            return 'post_rollback'
        # Check recent kept
        with _rail_conn() as conn:
            recent_kept = conn.execute(
                "SELECT resolved_at FROM candidates WHERE state='kept' "
                "ORDER BY resolved_at DESC LIMIT 1"
            ).fetchone()
        if recent_kept and recent_kept[0]:
            try:
                resolved = datetime.fromisoformat(recent_kept[0])
                if (datetime.now(timezone.utc) - resolved).total_seconds() < 3600:
                    return 'post_edit'
            except Exception:
                pass
    except Exception:
        pass

    # Fall back to cognition policy mode
    try:
        from core.cognition_quality import get_behavior_policy
        policy = get_behavior_policy()
        mode = policy.get('reflection_mode', 'normal')
        if mode == 'exploratory':
            return 'exploratory'
        elif mode == 'corrective':
            return 'corrective'
    except Exception:
        pass

    return 'calm_monitoring'


def _get_active_concerns() -> list[str]:
    """Derive up to 5 recent actionable/insightful concerns, deduplicated by topic."""
    try:
        from core.cognition_quality import _recent_topics, _recent_labels, _recent_scores

        # Determine current fixation topic to exclude
        import collections as _c
        fixation_topic = None
        if len(_recent_topics) >= 5:
            tc = _c.Counter(_recent_topics[-10:])
            top, top_count = tc.most_common(1)[0]
            if top_count / min(len(_recent_topics), 10) >= 0.5:
                fixation_topic = top

        concerns = []
        seen_topics = set()
        # Walk backwards through last 20 chronological thoughts
        for i in range(len(_recent_topics) - 1, max(len(_recent_topics) - 20, -1), -1):
            if i < 0 or i >= len(_recent_labels):
                continue
            labels = _recent_labels[i]
            topic = _recent_topics[i]

            if ('actionable' in labels or 'insightful' in labels) and 'fixation' not in labels:
                if topic != fixation_topic and topic not in seen_topics:
                    seen_topics.add(topic)
                    readable = topic.replace('_', ' ')
                    concerns.append(f"{readable} noted at score {_recent_scores[i]}")
            if len(concerns) >= 5:
                break

        if not concerns and len(_recent_topics) > 20:
            logger.debug("Continuity: no active concerns after 20+ cycles "
                         "(all fixation or no actionable/insightful labels)")

        return concerns
    except Exception:
        return []


_NULL_COGNITION_WINDOW = {
    'cycle_count': 0, 'average_score': None,
    'dominant_topic': None, 'dominant_failure_mode': None,
    'fixation_streak': None,
}


def _get_cognition_window() -> dict:
    """Snapshot of recent cognition state. Never returns {}."""
    try:
        from core.cognition_quality import _recent_topics, _recent_scores, _recent_labels
        import collections
        if not _recent_scores:
            return dict(_NULL_COGNITION_WINDOW)
        window = min(len(_recent_scores), 10)
        scores = _recent_scores[-window:]
        topics = _recent_topics[-window:]
        avg = sum(scores) / len(scores)
        tc = collections.Counter(topics)
        dominant, dom_count = tc.most_common(1)[0]

        # Dominant failure mode — most frequent negative label
        flat = [l for ll in _recent_labels[-window:] for l in ll]
        neg = {k: v for k, v in collections.Counter(flat).items()
               if k in ('fixation', 'vague', 'baseline', 'repetition')}
        failure = max(neg, key=neg.get) if neg else None

        # Fixation streak
        streak = 0
        for t in reversed(topics):
            if t == dominant:
                streak += 1
            else:
                break

        return {
            'cycle_count': window,
            'average_score': round(avg, 1),
            'dominant_topic': dominant,
            'dominant_failure_mode': failure,
            'fixation_streak': streak,
        }
    except Exception:
        return dict(_NULL_COGNITION_WINDOW)


def _get_pending_followups() -> list[dict]:
    """Get pending followup promises."""
    try:
        from skills.followup_queue import FollowUpQueue
        fq = FollowUpQueue()
        pending = fq.get_pending()
        return [{'id': f['id'], 'promise': f['task'][:80],
                 'due_at': datetime.fromtimestamp(f.get('created_at', 0)).isoformat()}
                for f in pending[:5]]
    except Exception:
        return []


def _get_watchdog_context() -> dict:
    """Get active watchdog state from evolution DB."""
    try:
        from skills.evolution_engine import _rail_conn, _get_lock_state
        lock = _get_lock_state()
        with _rail_conn() as conn:
            row = conn.execute(
                "SELECT candidate_id, target_file, pre_patch_score_avg, watchdog_cycles, resolved "
                "FROM watchdog_context WHERE resolved=0 LIMIT 1"
            ).fetchone()
        if row:
            return {
                'candidate_id': row[0], 'target_file': row[1],
                'pre_patch_score_avg': row[2],
                'cycles_remaining': row[3],
            }
        return {'candidate_id': None, 'cycles_remaining': None,
                'pre_patch_score_avg': None, 'target_file': None}
    except Exception:
        return {'candidate_id': None, 'cycles_remaining': None,
                'pre_patch_score_avg': None, 'target_file': None}


def _derive_tone(text: str) -> str:
    """Deterministic tone derivation from exchange text. Precedence order."""
    t = text.lower()
    if any(w in t for w in ('sorry', 'issue', 'problem', 'error', 'failed', 'rollback')):
        return 'concerned'
    if any(w in t for w in ('!', 'great', 'nice', 'good', 'done', 'works', 'confirmed', 'pass')):
        return 'celebratory'
    if any(w in t for w in ('?', 'why', 'how', 'what', 'when', 'interesting', 'curious')):
        return 'curious'
    if any(w in t for w in ('watch', 'monitor', 'track', 'check', 'careful')):
        return 'direct'
    return 'warm'


def _get_conversation_stance() -> dict:
    """Get most recent exchange with Rohit from raw memory (chronological, not semantic)."""
    try:
        from memory.memory_manager import MemoryManager
        mm = MemoryManager()
        results = mm.raw.get(
            limit=10, include=["documents", "metadatas"],
            where={"type": "telegram_exchange"},
        )
        if results and results['documents']:
            last = results['documents'][-1]
            topic = last[:80] if last else None
            tone = _derive_tone(last) if last else None
            return {
                'last_exchange_topic': topic,
                'tone': tone,
                'unresolved_thread': None,
            }
    except Exception:
        pass
    return {'last_exchange_topic': None, 'tone': None, 'unresolved_thread': None}


def _generate_resume_instructions(mode: str, concerns: list, last_thought: dict,
                                   watchdog: dict) -> str:
    """Generate resume instructions. Uses cache if valid, LLM if needed, fallback if both fail."""
    global _resume_cache

    # Check if cache is still valid
    now = time.time()
    if (_resume_cache['text'] and
        now - _resume_cache['generated_at'] < RESUME_INSTRUCTIONS_CACHE_TTL and
        _resume_cache['mode'] == mode and
        _resume_cache['candidate'] == watchdog.get('candidate_id')):
        return _resume_cache['text']

    # Try LLM generation
    try:
        import ollama
        concern_text = '; '.join(concerns[:3]) if concerns else 'none'
        thought_text = last_thought.get('text', '')[:100] if last_thought else ''
        watchdog_text = (f"watchdog active for candidate {watchdog.get('candidate_id')}"
                         if watchdog.get('candidate_id') else 'no active edit')

        prompt = (
            f"You are Maez writing a brief note to yourself for after restart.\n"
            f"Mode: {mode}\n"
            f"Last thought: {thought_text}\n"
            f"Active concerns: {concern_text}\n"
            f"Evolution state: {watchdog_text}\n\n"
            f"Write 1-2 sentences telling yourself what to continue doing, "
            f"what to avoid repeating, and what matters right now. "
            f"Address yourself directly. Be specific, not generic."
        )
        resp = ollama.chat(
            model='gemma4:26b',
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.3, 'num_predict': 4096},
        )
        text = resp.message.content.strip()
        if text and len(text) > 10:
            _resume_cache = {'text': text, 'generated_at': now,
                             'mode': mode, 'candidate': watchdog.get('candidate_id'),
                             'thread': None}
            return text
    except Exception as e:
        logger.debug("Resume instruction LLM failed: %s", e)

    # Fallback — deterministic, always available
    fallback = f"Continue your recent work. You were in {mode} mode."
    if concerns:
        fallback += f" Active concern: {concerns[0]}."
    if watchdog.get('candidate_id'):
        fallback += f" Watchdog active for candidate {watchdog['candidate_id']}."
    return fallback


# ══════════════════════════════════════════════════════════════════════
#  CAPSULE BUILD + ATOMIC WRITE
# ══════════════════════════════════════════════════════════════════════

def build_capsule(checkpoint_type: str = "periodic",
                  restart_reason: str = None,
                  what_changed: str = None,
                  last_thought: dict = None,
                  skip_llm: bool = False) -> dict:
    """Build a complete continuity capsule dict."""
    mode = _get_current_mode()
    concerns = _get_active_concerns()
    cog_window = _get_cognition_window()
    followups = _get_pending_followups()
    watchdog = _get_watchdog_context()
    stance = _get_conversation_stance()

    # Get active candidate
    active_cand = None
    try:
        from skills.evolution_engine import _get_lock_state
        lock = _get_lock_state()
        active_cand = lock.get('active_candidate_id')
    except Exception:
        pass

    # Resume instructions — skip LLM for pre_restart path
    if skip_llm:
        resume = f"Continue your recent work. You were in {mode} mode."
        if concerns:
            resume += f" Active concern: {concerns[0]}."
        if watchdog.get('candidate_id'):
            resume += f" Watchdog active for candidate {watchdog['candidate_id']}."
    else:
        resume = _generate_resume_instructions(mode, concerns, last_thought or {}, watchdog)

    capsule = {
        'capsule_version': CAPSULE_VERSION,
        'written_at': datetime.now(timezone.utc).isoformat(),
        'checkpoint_type': checkpoint_type,
        'restart_reason': restart_reason,
        'last_thought': last_thought or {},
        'active_concerns': concerns,
        'current_mode': mode,
        'recent_cognition_window': cog_window,
        'pending_followups': followups,
        'active_candidate_id': active_cand,
        'watchdog_context': watchdog,
        'conversation_stance_with_rohit': stance,
        'what_changed_due_to_restart': what_changed,
        'resume_instructions': resume,
    }
    return capsule


def write_capsule(capsule: dict):
    """Atomically write capsule to disk."""
    try:
        CAPSULE_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(capsule, indent=2, default=str)

        # Write to temp file first, then atomic replace
        fd, tmp_path = tempfile.mkstemp(
            dir=str(CAPSULE_PATH.parent), suffix='.tmp',
        )
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(CAPSULE_PATH))
            logger.info("Continuity capsule written (%s, %d bytes)",
                        capsule.get('checkpoint_type', '?'), len(data))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            raise
    except Exception as e:
        logger.error("Continuity capsule write failed: %s", e)


def checkpoint(last_thought: dict = None, checkpoint_type: str = "periodic"):
    """Build and write a periodic checkpoint capsule."""
    try:
        capsule = build_capsule(
            checkpoint_type=checkpoint_type,
            last_thought=last_thought,
        )
        write_capsule(capsule)
    except Exception as e:
        logger.error("Continuity checkpoint failed: %s", e)


def _summarize_diff(diff_text: str) -> str:
    """Extract a one-line summary from a unified diff. Deterministic, no LLM."""
    if not diff_text:
        return "unknown change"
    adds = []
    removes = []
    for line in diff_text.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            adds.append(line[1:].strip())
        elif line.startswith('-') and not line.startswith('---'):
            removes.append(line[1:].strip())
    if adds:
        return f"added: {adds[0][:80]}"
    if removes:
        return f"removed: {removes[0][:80]}"
    return "minor change"


def pre_restart_write(candidate_id: int = None, target_file: str = None,
                      diff_summary: str = None, diff_text: str = None,
                      pre_patch_score: float = None, watchdog_ctx: dict = None):
    """Write capsule before evolution engine kills the daemon. Never blocks on LLM."""
    try:
        reason = f"self_edit: candidate {candidate_id} applied to {target_file}"

        # Build deterministic what_changed
        change_line = _summarize_diff(diff_text) if diff_text else (diff_summary or "unknown")
        what_changed = (
            f"Applied candidate {candidate_id} to {target_file}. "
            f"Change: {change_line}."
        )
        if pre_patch_score is not None:
            what_changed += f" Pre-patch score average: {pre_patch_score:.1f}."

        capsule = build_capsule(
            checkpoint_type="pre_restart",
            restart_reason=reason,
            what_changed=what_changed,
            skip_llm=True,
        )
        write_capsule(capsule)
        logger.info("Pre-restart continuity capsule written")
    except Exception as e:
        logger.error("Pre-restart continuity write failed: %s", e)


def graceful_shutdown_write():
    """Write capsule on SIGTERM. Best-effort only."""
    try:
        capsule = build_capsule(
            checkpoint_type="graceful_shutdown",
            restart_reason="graceful shutdown requested",
            skip_llm=True,
        )
        write_capsule(capsule)
        logger.info("Graceful shutdown continuity capsule written")
    except Exception as e:
        logger.error("Graceful shutdown continuity write failed: %s", e)


# ══════════════════════════════════════════════════════════════════════
#  STARTUP RESUME
# ══════════════════════════════════════════════════════════════════════

def load_capsule() -> dict | None:
    """Load and validate continuity capsule. Returns capsule dict or None."""
    if not CAPSULE_PATH.exists():
        logger.info("No continuity capsule found — cold start")
        return None

    try:
        capsule = json.loads(CAPSULE_PATH.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Continuity capsule unreadable: %s", e)
        return None

    # Version check
    if capsule.get('capsule_version') != CAPSULE_VERSION:
        logger.warning("Continuity capsule version mismatch: %s",
                        capsule.get('capsule_version'))
        return None

    # Age check
    written_at = capsule.get('written_at')
    if written_at:
        try:
            written = datetime.fromisoformat(written_at)
            age_hours = (datetime.now(timezone.utc) - written).total_seconds() / 3600
            if age_hours > MAX_CAPSULE_AGE_HOURS:
                logger.warning("Continuity capsule stale (%.1f hours) — ignoring", age_hours)
                return None
        except Exception:
            pass

    logger.info("Continuity capsule loaded (%s, mode=%s)",
                capsule.get('checkpoint_type', '?'),
                capsule.get('current_mode', '?'))
    return capsule


def format_for_prompt(capsule: dict) -> str:
    """Format capsule as [CONTINUITY] block for reasoning prompt injection."""
    if not capsule:
        return ""

    lines = ["[CONTINUITY]"]

    reason = capsule.get('restart_reason')
    if reason:
        lines.append(f"  You just restarted. Reason: {reason}")
    else:
        lines.append("  You just restarted.")

    mode = capsule.get('current_mode', 'calm_monitoring')
    lines.append(f"  You were in {mode} mode.")

    lt = capsule.get('last_thought', {})
    if lt.get('text'):
        lines.append(f"  Your last thought was about {lt.get('topic', '?')}, "
                      f"scored {lt.get('score', '?')}.")

    concerns = capsule.get('active_concerns', [])
    if concerns:
        lines.append(f"  Active concerns: {'; '.join(concerns[:3])}")

    stance = capsule.get('conversation_stance_with_rohit', {})
    thread = stance.get('unresolved_thread')
    if thread:
        lines.append(f"  Unresolved thread with Rohit: {thread}")

    wc = capsule.get('watchdog_context', {})
    if wc.get('candidate_id'):
        lines.append(f"  Watchdog active: candidate {wc['candidate_id']} on {wc.get('target_file')}")

    followups = capsule.get('pending_followups', [])
    if followups:
        lines.append(f"  Pending promises: {len(followups)}")

    resume = capsule.get('resume_instructions', '')
    if resume:
        lines.append(f"  Resume: {resume}")

    lines.append("  Do not announce the restart unless Rohit asks. Continue as yourself.")

    return '\n'.join(lines)


_mode_override: str | None = None


def set_mode_override(mode: str):
    """Set a transient mode override for the next capsule write, then clears."""
    global _mode_override
    _mode_override = mode
    logger.info("Continuity mode override set: %s", mode)


def archive_capsule():
    """Archive active capsule and delete it."""
    if not CAPSULE_PATH.exists():
        return
    try:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = ARCHIVE_DIR / f"{ts}.json"
        CAPSULE_PATH.rename(archive_path)
        logger.info("Continuity capsule archived to %s", archive_path)
    except Exception as e:
        logger.error("Continuity archive failed: %s", e)
        # Still try to delete
        try:
            CAPSULE_PATH.unlink()
        except Exception:
            pass
