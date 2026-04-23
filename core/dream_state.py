"""
core/dream_state.py — Session 11o.

Dream mode: autonomous pattern detection during idle time.

When the owner has been AFK for >30 minutes, the daemon's reasoning loop
occasionally runs a "dream cycle" instead of (or alongside) its normal
30-second perception cycle. In a dream cycle, Maez reviews her last ~80
raw memories, looks for patterns that individual memories didn't name
(trajectories, rhythms, contradictions, shifts), and synthesizes a short
paragraph of reflection.

If the reflection is genuinely novel (not a near-duplicate of existing
soul notes or recent dreams), it's stored as a proposal in a tiny SQLite
table and sent to the private Telegram bot with an approval id. the owner
reviews the proposal at his own pace and replies with /apply_dream <id>
(which calls action_engine.write_soul_note to append the insight to
soul.md, picked up within 10s by the soul watcher) or /reject_dream <id>.

Design notes
------------
* Dream cycles are rate-limited to at most one per 10 minutes, even when
  the owner has been AFK for hours.
* Dream cycles run IN-THREAD on the daemon's main reasoning loop. They
  cost one ollama.chat call (~3-5s with think=False on gemma4:26b).
  Blocking the main loop briefly during idle time is acceptable —
  interactive work isn't happening.
* Soul.md writes go through action_engine.write_soul_note, which is a
  Tier 0 action with existing safety rails (rejects edits containing
  HARD CONSTRAINTS or TRUST COVENANT substrings).
* The novelty check is a cheap Jaccard similarity over word sets (length
  >= 4) against the last 20 dream proposals + last ~10 soul notes parsed
  from soul.md. Rejects if max Jaccard > 0.4 with any prior. Good enough
  for first-pass uniqueness without adding an embedding dependency.
* Nothing reaches soul.md without the owner's explicit /apply_dream. The
  approval gate is the safety property that matters.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger("maez.dream")


# Reuse the same model constant the daemon uses. Import lazily at call
# time to avoid a hard dependency on daemon module load order.
MODEL = "gemma4:26b"

try:
    from core import paths as _paths
    DEFAULT_DB_PATH = str(_paths.memory_dir() / "dream_proposals.db")
    SOUL_PATH = _paths.soul_combined_path()
    QUALITY_DB_PATH = _paths.memory_dir() / "quality.db"
except Exception:
    DEFAULT_DB_PATH = "/home/rohit/maez/memory/dream_proposals.db"
    SOUL_PATH = Path("/home/rohit/maez/config/soul.md")
    QUALITY_DB_PATH = Path("/home/rohit/maez/memory/quality.db")

# Idle detection: the owner is AFK if presence says not-present AND absence
# has been at least this many seconds.
IDLE_THRESHOLD_S = 1800.0  # 30 minutes

# Rate limit: at most one dream cycle per this many seconds of idle time.
# 11u fix: 10 min was too aggressive — produced 16 near-identical
# proposals in 7 hours. 3600s (1 hour) bounds to at most 1 dream per
# hour of AFK time. The raw memories don't change fast enough to
# justify more frequent pattern detection.
DREAM_COOLDOWN_S = 3600.0  # 1 hour

# Dream cycle prompt budget: we read this many recent raw memories.
# 40 is a deliberate compromise: enough to surface multi-observation
# trajectories, small enough that prompt eval stays ~5-10s on gemma4:26b
# even under daemon contention (vs ~60-120s at window=80).
DREAM_MEMORY_WINDOW = 40

# Minimum visible chars for a dream insight to be considered valid.
# Shorter than this and it's probably a garbage refusal or the NOTHING
# sentinel that slipped through.
MIN_INSIGHT_CHARS = 30

# Novelty threshold: Jaccard similarity above this = too similar to a
# known note, reject as redundant.
# 11u fix: 0.4 was too lenient — paraphrases of "disk at 65%, Claude
# process" scored ~0.30-0.35 and slipped through. 0.25 catches them.
# 2026-04-22 fix: after 5 hourly dreams all about disk-oscillation
# and firefox/claude process rhythm slipped through at Jaccard 0.18-0.22,
# tightened further. Long-text Jaccard dilutes overlap on shared
# vocabulary; a stricter cap catches near-paraphrases that share
# topic but vary phrasing.
NOVELTY_JACCARD_MAX = 0.15

# Second-tier novelty: if the candidate's primary topic matches any
# of the last N dreams' primary topic, reject even when Jaccard is
# borderline. Prevents the same topic from being dreamed about over
# and over with different wording.
NOVELTY_TOPIC_LOOKBACK = 5
NOVELTY_TOPIC_JACCARD_MIN = 0.10

# How many prior dreams to compare against when checking novelty.
NOVELTY_DREAM_LOOKBACK = 20


TRAINING_EVAL_COOLDOWN_S = 86400.0  # 24 hours between training proposals


class DreamState:
    """Idle-time pattern detection + soul note proposal storage.

    Thread-safety: all SQLite access is guarded by self._lock. Main loop
    calls run_dream_cycle() from the daemon reasoning thread; Telegram
    handlers call list_pending/apply_proposal/reject_proposal from the
    Telegram bot thread. Two-thread access is fine under the RLock.
    """

    def __init__(
        self,
        memory: Any,
        telegram: Any,
        action_engine: Any,
        db_path: str = DEFAULT_DB_PATH,
    ) -> None:
        self.memory = memory
        self.telegram = telegram
        self.action_engine = action_engine
        self.db_path = db_path
        self._last_dream_at: float = 0.0
        self._last_training_eval_at: float = 0.0
        self._lock = threading.RLock()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ── SQLite schema ───────────────────────────────────────────────
    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path, check_same_thread=False)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _init_schema(self) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS dream_proposals (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at    REAL NOT NULL,
                    insight       TEXT NOT NULL,
                    status        TEXT NOT NULL DEFAULT 'pending',
                    applied_at    REAL,
                    reject_reason TEXT
                )
                """
            )
            # Session 11s: schema migration for soul section-replace
            # proposals. Backward compat — existing rows default to
            # proposal_type='append' and NULL target_section/new_body.
            existing_cols = {
                row[1] for row in c.execute("PRAGMA table_info(dream_proposals)")
            }
            if "proposal_type" not in existing_cols:
                c.execute(
                    "ALTER TABLE dream_proposals ADD COLUMN "
                    "proposal_type TEXT NOT NULL DEFAULT 'append'"
                )
            if "target_section" not in existing_cols:
                c.execute(
                    "ALTER TABLE dream_proposals ADD COLUMN "
                    "target_section TEXT"
                )
            if "proposed_new_body" not in existing_cols:
                c.execute(
                    "ALTER TABLE dream_proposals ADD COLUMN "
                    "proposed_new_body TEXT"
                )
            if "unified_diff" not in existing_cols:
                c.execute(
                    "ALTER TABLE dream_proposals ADD COLUMN "
                    "unified_diff TEXT"
                )
            c.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_dream_status
                ON dream_proposals (status, created_at)
                """
            )
            # Explicit commit: ALTER TABLE inside a `with conn:` block is
            # implicitly auto-committed in SQLite3 (DDL commits the
            # current transaction), but relying on that means the final
            # CREATE INDEX sits in a new transaction whose implicit commit
            # is not guaranteed across all sqlite3 builds / Python
            # versions. Commit explicitly so schema migration lands
            # atomically on every caller path.
            c.commit()

    # ── idle + cadence gates ────────────────────────────────────────
    def is_idle(self, presence_snap: Any, absence_secs: float) -> bool:
        """Return True iff the owner has been AFK for at least IDLE_THRESHOLD_S.

        `presence_snap` is the daemon's _last_presence_snap (may be None).
        `absence_secs` is the daemon's computed absence duration in seconds.
        """
        if presence_snap is None:
            return False
        rohit_present = getattr(presence_snap, "rohit_present", True)
        return (not rohit_present) and absence_secs >= IDLE_THRESHOLD_S

    def should_run_now(self, now: float) -> bool:
        """True if the cooldown since the last dream cycle has elapsed."""
        return (now - self._last_dream_at) >= DREAM_COOLDOWN_S

    # ── dream cycle ─────────────────────────────────────────────────
    def run_dream_cycle(self, force: bool = False) -> Optional[str]:
        """Execute one dream cycle. Returns the insight text if a novel
        proposal was stored, or None if the cycle produced nothing
        actionable (no memories, NOTHING response, novelty check failed).

        `force=True` bypasses the cooldown gate for test hooks. The caller
        is still responsible for the idle gate (run_dream_cycle doesn't
        check presence on its own — that's the daemon's job).
        """
        now = time.time()
        # Claim the cooldown slot IMMEDIATELY so should_run_now() starts
        # returning False the moment this cycle begins — even if we spawn
        # in a background thread and the main loop's next tick evaluates
        # the gate before this cycle finishes. Set even on early-return
        # paths below (NOTHING / too-short / novelty-fail) so failures
        # don't immediately re-spawn another cycle.
        self._last_dream_at = now

        # 1. Fetch recent raw memories (chronological)
        try:
            recent = self.memory.recent_raw(n=DREAM_MEMORY_WINDOW)
        except Exception as e:
            logger.error("dream: recent_raw failed: %s", e)
            return None
        docs = recent.get("documents") or []
        if len(docs) < 10:
            logger.info("dream: skipped — only %d raw memories available", len(docs))
            return None

        # 2. Build dream prompt
        joined = "\n".join(f"- {d[:300]}" for d in docs)
        prompt = (
            "You are entering a quiet reflective state. the owner is away from his desk.\n\n"
            "Review these recent observations you've had about his work, his system, "
            "his patterns:\n\n"
            f"{joined}\n\n"
            "What's a PATTERN you notice across multiple observations that NONE of\n"
            "the individual ones named? Not a single event — a trajectory, a rhythm,\n"
            "a contradiction, a shift.\n\n"
            "Respond in ONE short paragraph (2-4 sentences). Start with \"I notice...\"\n"
            "or \"A pattern:\" or similar. Be specific — name actual topics from the\n"
            "observations, not abstract categories.\n\n"
            "If nothing genuinely new emerges — respond with exactly: NOTHING"
        )

        # 3. Call llm_client (11r: routes through MAEZ_LLM_BACKEND — ollama
        # or llama.cpp CUDA. Fixes 11o bug where dream_state imported ollama
        # directly and was broken after the 11p llama.cpp migration.)
        # think=False for fast synthesis, no scratchpad needed for pattern work.
        try:
            from core import llm_client as _llm_client
            response = _llm_client.chat(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                think=False,
                options={"temperature": 0.7, "num_predict": 200},
            )
            insight = (response.message.content or "").strip()
        except Exception as e:
            logger.error("dream: llm_client call failed: %s", e)
            return None

        # 4. Sentinel / length filter
        if not insight:
            logger.info("dream: empty response")
            return None
        if insight.upper().strip() == "NOTHING":
            logger.info("dream: model returned NOTHING (no pattern detected)")
            return None
        if len(insight) < MIN_INSIGHT_CHARS:
            logger.info("dream: insight too short (%d chars), skipping", len(insight))
            return None

        # 5. Novelty check
        if not self._is_novel(insight):
            logger.info("dream: insight too similar to prior notes, skipping")
            return None

        # 6. Store as proposal
        prop_id = self._store_proposal(insight)
        self._last_dream_at = now
        logger.info("dream: proposal #%d stored — %s", prop_id, insight[:120])

        # 7. Send to private Telegram bot.
        # Wrap command hints in backticks so Telegram MarkdownV2
        # renders the underscores literally instead of converting
        # `_dream_` into italic text. The italic form caused the
        # command to arrive at the bot as "/apply dream 49" (space
        # instead of underscore), fell through the CommandHandler
        # match, and got routed to chat — the _process_message
        # variant-tolerant dispatch now catches that shape too, but
        # emitting proper code-formatted commands is the right fix
        # at the source.
        if self.telegram is not None:
            try:
                msg = (
                    f"💭 [DREAM #{prop_id}]\n\n{insight}\n\n"
                    f"`/apply_dream {prop_id}`  ·  `/reject_dream {prop_id}`"
                )
                self.telegram.send_message(msg)
            except Exception as e:
                logger.debug("dream: telegram send failed: %s", e)

        return insight

    # ── training self-evaluation ───────────────────────────────────
    def maybe_propose_training(self) -> Optional[int]:
        """Session 11u: check cognition quality and propose a training
        run if performance appears to be declining. Rate-limited to one
        proposal per 24 hours. Called from the daemon's dream cycle
        (idle time only).

        Returns the proposal id if a proposal was stored, None otherwise.
        """
        now = time.time()
        if (now - self._last_training_eval_at) < TRAINING_EVAL_COOLDOWN_S:
            return None
        self._last_training_eval_at = now

        # Check if there are already pending training proposals
        pending = self.list_pending(proposal_type="training_run")
        if pending:
            return None

        # Read recent cognition quality from quality.db
        try:
            import sqlite3 as _sql
            conn = _sql.connect(str(QUALITY_DB_PATH))
            rows = conn.execute(
                "SELECT score, primary_labels FROM cycle_scores "
                "ORDER BY id DESC LIMIT 50"
            ).fetchall()
            conn.close()
        except Exception as e:
            logger.debug("training eval: quality.db read failed: %s", e)
            return None

        if len(rows) < 20:
            return None

        scores = [r[0] for r in rows if r[0] is not None]
        if not scores:
            return None

        avg_recent = sum(scores[:20]) / 20
        avg_older = sum(scores[20:]) / max(len(scores[20:]), 1) if len(scores) > 20 else avg_recent

        # Count how many new telegram exchanges exist since the last
        # adapter was trained (rough proxy for "new signal available")
        try:
            if self.memory:
                exchanges = self.memory.get_telegram_exchanges(limit=None)
                new_exchange_count = len(exchanges) if exchanges else 0
            else:
                new_exchange_count = 0
        except Exception:
            new_exchange_count = 0

        # Heuristics for proposing training:
        # 1. Score declined by ≥5 points (recent 20 vs older 30)
        # 2. OR ≥200 new exchanges accumulated (new signal available)
        decline = avg_older - avg_recent
        should_propose = decline >= 5.0 or new_exchange_count >= 200

        if not should_propose:
            logger.debug(
                "training eval: no proposal — decline=%.1f, exchanges=%d",
                decline, new_exchange_count,
            )
            return None

        rationale_parts = []
        if decline >= 5.0:
            rationale_parts.append(
                f"Cognition quality dropped {decline:.1f} points "
                f"(recent 20 cycles avg {avg_recent:.0f} vs older avg {avg_older:.0f})"
            )
        if new_exchange_count >= 200:
            rationale_parts.append(
                f"{new_exchange_count} conversation exchanges available — "
                f"significant new signal since last training"
            )
        rationale = ". ".join(rationale_parts) + "."

        prop_id = self.store_training_proposal(
            rationale=rationale,
            corpus_window="all exchanges since last adapter",
            hyperparams='{"rank": 16, "epochs": 1, "max_seq_length": 2048}',
        )
        return prop_id

    # ── novelty heuristic ───────────────────────────────────────────
    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Word set for Jaccard similarity. Lowercase, strip punct,
        words of length >= 4 only (filters most stopwords)."""
        words = re.findall(r"[a-zA-Z]{4,}", text.lower())
        return set(words)

    def _is_novel(self, candidate: str) -> bool:
        """True if the candidate has max Jaccard <= NOVELTY_JACCARD_MAX
        against the last NOVELTY_DREAM_LOOKBACK dream proposals AND the
        last ~10 soul notes parsed from soul.md."""
        cand_set = self._tokenize(candidate)
        if not cand_set:
            return True  # can't judge, let it through

        # Collect prior texts: recent dreams + recent soul notes
        priors: list[str] = []
        try:
            with self._lock, self._conn() as c:
                cur = c.execute(
                    "SELECT insight FROM dream_proposals "
                    "ORDER BY id DESC LIMIT ?",
                    (NOVELTY_DREAM_LOOKBACK,),
                )
                priors.extend(row[0] for row in cur.fetchall())
        except Exception as e:
            logger.debug("dream novelty: prior-dream fetch failed: %s", e)

        try:
            if SOUL_PATH.exists():
                soul_text = SOUL_PATH.read_text()
                # Parse soul notes: lines like "[YYYY-MM-DD HH:MM] ..."
                # Keep the last 10 for comparison.
                note_lines = re.findall(
                    r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\][^\n]*",
                    soul_text,
                )
                priors.extend(note_lines[-10:])
                # Also compare against the full non-HARD-CONSTRAINT body
                # of soul.md. Dreams that echo content already pinned in
                # soul (e.g. applied #13 which put "65.6% frozen" into
                # identity) were slipping through because the note-line
                # regex misses prose-style additions. This prevents the
                # feedback loop: dream observation → applied to soul →
                # recalled next cycle → dream again about it.
                # Sliced into ~800-char windows so Jaccard isn't
                # dominated by unrelated soul material.
                body = soul_text
                for marker in ("HARD CONSTRAINTS", "TRUST COVENANT"):
                    idx = body.find(marker)
                    if idx > 0:
                        body = body[idx:]
                        break
                for i in range(0, len(body), 800):
                    chunk = body[i:i + 1600]  # 800-step with overlap
                    if chunk.strip():
                        priors.append(chunk)
        except Exception as e:
            logger.debug("dream novelty: soul-parse failed: %s", e)

        if not priors:
            return True  # nothing to compare against → novel

        max_overlap = 0.0
        for prior in priors:
            prior_set = self._tokenize(prior)
            if not prior_set:
                continue
            inter = len(cand_set & prior_set)
            union = len(cand_set | prior_set)
            if union == 0:
                continue
            jaccard = inter / union
            if jaccard > max_overlap:
                max_overlap = jaccard
                if max_overlap > NOVELTY_JACCARD_MAX:
                    break  # early exit — already too similar

        logger.debug("dream novelty: max_jaccard=%.3f threshold=%.3f",
                     max_overlap, NOVELTY_JACCARD_MAX)
        if max_overlap > NOVELTY_JACCARD_MAX:
            return False

        # Second-tier novelty: even when Jaccard is under threshold,
        # reject if the candidate's primary topic matches any of the
        # last NOVELTY_TOPIC_LOOKBACK dreams' primary topic AND the
        # Jaccard is still above the topic-level floor. Catches
        # "same topic rephrased" loops (e.g. five dreams about
        # disk-oscillation that each use different filler vocabulary).
        try:
            from core.cognition_quality import primary_topic as _primary_topic
        except Exception:
            return True  # topic module unavailable — pass on first-tier
        cand_topic = _primary_topic(candidate.lower())
        if not cand_topic or cand_topic == "unknown":
            return True
        try:
            with self._lock, self._conn() as c:
                cur = c.execute(
                    "SELECT insight FROM dream_proposals "
                    "ORDER BY id DESC LIMIT ?",
                    (NOVELTY_TOPIC_LOOKBACK,),
                )
                recent_topics = [
                    _primary_topic((row[0] or "").lower())
                    for row in cur.fetchall()
                ]
        except Exception as e:
            logger.debug("dream novelty: topic-lookback fetch failed: %s", e)
            return True
        if (cand_topic in recent_topics
                and max_overlap >= NOVELTY_TOPIC_JACCARD_MIN):
            logger.info(
                "dream novelty: rejected on topic='%s' jaccard=%.3f "
                "(recent topics=%s)",
                cand_topic, max_overlap, recent_topics,
            )
            return False
        return True

    # ── proposal storage + lifecycle ────────────────────────────────
    def _store_proposal(self, insight: str) -> int:
        with self._lock, self._conn() as c:
            cur = c.execute(
                "INSERT INTO dream_proposals "
                "(created_at, insight, status, proposal_type) "
                "VALUES (?, ?, 'pending', 'append')",
                (time.time(), insight),
            )
            c.commit()
            return int(cur.lastrowid)

    def store_section_edit_proposal(
        self,
        insight: str,
        target_section: str,
        proposed_new_body: str,
        unified_diff: str,
    ) -> int:
        """Session 11s: store a section-replace proposal. Distinct from
        the default append-type proposals (which just grow soul.md via
        ``write_soul_note``). Section edits rewrite an existing
        ``## Header`` body with diff preview + approval.

        ``insight`` is the human-readable summary/rationale shown in the
        Telegram ``/edit_proposals`` list. ``target_section`` names the
        ``##`` section to replace. ``proposed_new_body`` is the full new
        body text. ``unified_diff`` is the pre-computed diff (generated
        once at propose time and stored to avoid re-running the diff
        at display time)."""
        with self._lock, self._conn() as c:
            cur = c.execute(
                "INSERT INTO dream_proposals "
                "(created_at, insight, status, proposal_type, "
                " target_section, proposed_new_body, unified_diff) "
                "VALUES (?, ?, 'pending', 'section_replace', ?, ?, ?)",
                (time.time(), insight, target_section,
                 proposed_new_body, unified_diff),
            )
            c.commit()
            return int(cur.lastrowid)

    def store_training_proposal(
        self,
        rationale: str,
        corpus_window: str = "all since last adapter",
        hyperparams: str = "",
    ) -> int:
        """Session 11u: store a training-run proposal. Maez proposes
        when she believes weight-level retraining would improve her
        cognition. the owner reviews via ``/train_proposals`` on Telegram
        and manually executes approved runs.

        Reuses the existing schema columns with training-specific
        semantics: ``insight`` = rationale, ``target_section`` =
        corpus_window, ``proposed_new_body`` = hyperparams JSON."""
        with self._lock, self._conn() as c:
            cur = c.execute(
                "INSERT INTO dream_proposals "
                "(created_at, insight, status, proposal_type, "
                " target_section, proposed_new_body) "
                "VALUES (?, ?, 'pending', 'training_run', ?, ?)",
                (time.time(), rationale, corpus_window, hyperparams),
            )
            c.commit()
            prop_id = int(cur.lastrowid)

        logger.info(
            "dream: training proposal #%d stored — %s", prop_id, rationale[:120]
        )

        if self.telegram is not None:
            try:
                msg = (
                    f"🏋️ [TRAIN #{prop_id}]\n\n{rationale}\n\n"
                    f"Corpus: {corpus_window}\n"
                    f"/approve_train {prop_id}  ·  /reject_train {prop_id}"
                )
                self.telegram.send_message(msg)
            except Exception as e:
                logger.debug("dream: training proposal telegram send failed: %s", e)

        return prop_id

    def list_pending(
        self, proposal_type: Optional[str] = None
    ) -> list[tuple[int, str, str]]:
        """Return [(id, created_at_iso, insight)] for pending proposals,
        oldest first. If ``proposal_type`` is given (``'append'`` or
        ``'section_replace'``), only proposals of that type are returned.
        """
        sql = (
            "SELECT id, created_at, insight FROM dream_proposals "
            "WHERE status = 'pending'"
        )
        params: tuple = ()
        if proposal_type is not None:
            sql += " AND proposal_type = ?"
            params = (proposal_type,)
        sql += " ORDER BY created_at ASC"
        with self._lock, self._conn() as c:
            cur = c.execute(sql, params)
            rows = cur.fetchall()
        return [
            (
                int(row[0]),
                datetime.fromtimestamp(row[1]).strftime("%Y-%m-%d %H:%M"),
                row[2],
            )
            for row in rows
        ]

    def get_proposal(self, prop_id: int) -> Optional[dict]:
        """Fetch a single proposal's full row as a dict, or None if absent."""
        with self._lock, self._conn() as c:
            cur = c.execute(
                "SELECT id, created_at, insight, status, applied_at, "
                "reject_reason, proposal_type, target_section, "
                "proposed_new_body, unified_diff "
                "FROM dream_proposals WHERE id = ?",
                (prop_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return {
            "id": int(row[0]),
            "created_at": float(row[1]),
            "insight": row[2],
            "status": row[3],
            "applied_at": row[4],
            "reject_reason": row[5],
            "proposal_type": row[6] or "append",
            "target_section": row[7],
            "proposed_new_body": row[8],
            "unified_diff": row[9],
        }

    def apply_proposal(self, prop_id: int) -> tuple[bool, str]:
        """Apply a proposal: write it to soul.md via action_engine and
        mark the DB row as 'applied'. Returns (ok, message)."""
        prop = self.get_proposal(prop_id)
        if prop is None:
            return False, f"dream #{prop_id} not found"
        if prop["status"] != "pending":
            return False, f"dream #{prop_id} already {prop['status']}"

        insight = prop["insight"]
        note = f"[DREAM] {insight}"

        if self.action_engine is None:
            return False, "action_engine not available"

        try:
            result = self.action_engine.write_soul_note(note)
        except Exception as e:
            return False, f"write_soul_note failed: {e!r}"

        # The ActionEngine returns an ActionResult-ish object; treat
        # any non-falsy result that didn't raise as success. The existing
        # _do_write_soul_note returns a string on success, raises on
        # forbidden content.
        ok = result is not False and result is not None

        if ok:
            with self._lock, self._conn() as c:
                c.execute(
                    "UPDATE dream_proposals SET status = 'applied', "
                    "applied_at = ? WHERE id = ?",
                    (time.time(), prop_id),
                )
                c.commit()
            logger.info("dream: proposal #%d applied to soul.md", prop_id)
            return True, f"dream #{prop_id} applied to soul.md"
        return False, f"soul write rejected for #{prop_id}"

    def apply_section_edit_proposal(self, prop_id: int) -> tuple[bool, str]:
        """Session 11s: apply a section-replace proposal.

        Looks up a stored ``section_replace`` proposal, reconstructs a
        ``soul_editor.Proposal`` from the row, and delegates to
        ``action_engine.edit_soul_section`` (Tier 0 action). On success,
        marks the DB row as 'applied'. The soul watcher thread picks up
        the MD5 change within 10s and hot-reloads the system prompt.
        """
        prop = self.get_proposal(prop_id)
        if prop is None:
            return False, f"proposal #{prop_id} not found"
        if prop["status"] != "pending":
            return False, f"proposal #{prop_id} already {prop['status']}"
        if prop["proposal_type"] != "section_replace":
            return False, (
                f"proposal #{prop_id} is type {prop['proposal_type']!r}, "
                f"not 'section_replace' — use /apply_dream instead"
            )
        target_name = prop["target_section"]
        new_body = prop["proposed_new_body"]
        if not target_name or new_body is None:
            return False, f"proposal #{prop_id} is missing target/body"

        if self.action_engine is None:
            return False, "action_engine not available"

        # Delegate to ActionEngine.edit_soul_section — it re-runs
        # propose_replacement against the CURRENT soul.md through
        # soul_editor, which does its own stale-check, required-phrase
        # check, backup, and atomic write.
        try:
            result = self.action_engine.edit_soul_section(
                target_name=target_name,
                new_body=new_body,
                rationale=prop["insight"] or "",
            )
        except Exception as e:
            return False, f"edit_soul_section failed: {e!r}"

        ok = bool(getattr(result, "success", False))
        msg = (result.output if ok else result.error) or ""

        if ok:
            with self._lock, self._conn() as c:
                c.execute(
                    "UPDATE dream_proposals SET status = 'applied', "
                    "applied_at = ? WHERE id = ?",
                    (time.time(), prop_id),
                )
                c.commit()
            logger.info(
                "dream: section-edit proposal #%d applied to soul.md", prop_id
            )
            return True, f"edit #{prop_id} applied: {msg}"
        return False, f"section edit rejected for #{prop_id}: {msg}"

    def reject_proposal(
        self, prop_id: int, reason: str = "manual"
    ) -> tuple[bool, str]:
        """Mark a proposal as rejected. No soul edit."""
        prop = self.get_proposal(prop_id)
        if prop is None:
            return False, f"dream #{prop_id} not found"
        if prop["status"] != "pending":
            return False, f"dream #{prop_id} already {prop['status']}"
        with self._lock, self._conn() as c:
            c.execute(
                "UPDATE dream_proposals SET status = 'rejected', "
                "reject_reason = ? WHERE id = ?",
                (reason, prop_id),
            )
            c.commit()
        logger.info("dream: proposal #%d rejected (%s)", prop_id, reason)
        return True, f"dream #{prop_id} rejected"
