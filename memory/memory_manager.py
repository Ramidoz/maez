"""
Maez Memory Manager — Three-tier persistent vector memory.

Tier 1: Raw Archive     — Every reasoning cycle, never deleted.
Tier 2: Daily Consolidations — 24-hour summaries via gemma4:26b, never deleted.
Tier 3: Core Memories   — Permanent long-term observations, always in context.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import chromadb
from chromadb.config import Settings
from core.llm_client import sanitize_prompt_text
from core.birth import memory_phase_tag as _memory_phase_tag

logger = logging.getLogger("maez")

BASE_DB = Path("/home/rohit/maez/memory/db")

# ── Topic Router ──

WINGS = {
    'system': ['cpu', 'ram', 'gpu', 'disk', 'memory', 'partition', 'temperature', 'process'],
    'rohit': ['rohit', 'desk', 'presence', 'arrived', 'away', 'focus', 'deep work', 'break'],
    'development': ['code', 'python', 'git', 'claude', 'claude code', 'error', 'debug', 'deploy'],
    'people': ['telegram', 'message', 'conversation', 'public bot', 'user'],
    'maez': ['soul', 'reasoning', 'cycle', 'evolution', 'self', 'improvement'],
    'external': ['news', 'reddit', 'github', 'search', 'web', 'trending'],
}


class TopicRouter:
    def detect_wing(self, text: str) -> str:
        text_lower = text.lower()
        scores = {w: 0 for w in WINGS}
        for wing, keywords in WINGS.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[wing] += 1
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else 'general'


_topic_router = TopicRouter()
MODEL = "gemma4:26b"
SOUL_PATH = Path("/home/rohit/maez/config/soul.md")


def _make_client(subdir: str) -> chromadb.PersistentClient:
    path = BASE_DB / subdir
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(path),
        settings=Settings(anonymized_telemetry=False),
    )


def _humanize_age(raw_ts, now: datetime) -> str:
    """Convert a timestamp (ISO string or unix float) into age-relative
    language for the prompt: 'just now', 'N minutes ago', 'N hours ago',
    'N days ago', 'N weeks ago', else 'long ago'. Returns 'earlier' for
    None / unparseable input — never raises.

    Added 2026-04-21 to close the stale-observation-as-current-state
    fabrication path. See format_for_prompt docstring."""
    if raw_ts is None:
        return "earlier"
    # Parse
    try:
        if isinstance(raw_ts, (int, float)):
            ts = datetime.fromtimestamp(float(raw_ts), tz=timezone.utc)
        elif isinstance(raw_ts, str):
            s = raw_ts.strip()
            if not s:
                return "earlier"
            # Handle trailing 'Z' (ISO UTC)
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            # Python's fromisoformat handles offsets in 3.11+
            ts = datetime.fromisoformat(s)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        else:
            return "earlier"
    except (ValueError, TypeError, OverflowError):
        return "earlier"

    delta = now - ts
    # Future timestamps (clock skew) → treat as just now
    if delta.total_seconds() < 0:
        return "just now"
    secs = int(delta.total_seconds())
    if secs < 120:
        return "just now"
    mins = secs // 60
    if mins < 60:
        return f"{mins} minutes ago"
    hours = secs // 3600
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = delta.days
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    weeks = days // 7
    if weeks < 12:
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    return "long ago"


def _humanize_daily_age(date_str: str, now: datetime) -> str:
    """Convert a YYYY-MM-DD daily-summary date into age-relative
    language. 'today', 'yesterday', 'N days ago', 'N weeks ago'."""
    if not date_str or date_str == "unknown":
        return "earlier"
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        d = d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return "earlier"
    delta_days = (now.date() - d.date()).days
    if delta_days < 0:
        return "today"
    if delta_days == 0:
        return "today"
    if delta_days == 1:
        return "yesterday"
    if delta_days < 30:
        return f"{delta_days} days ago"
    weeks = delta_days // 7
    if weeks < 12:
        return f"{weeks} weeks ago"
    return "long ago"


class MemoryManager:
    def __init__(self):
        # Tier 1 — Raw Archive
        self._raw_client = _make_client("raw")
        self.raw = self._raw_client.get_or_create_collection(
            name="raw_archive", metadata={"hnsw:space": "cosine"},
        )

        # Tier 2 — Daily Consolidations
        self._daily_client = _make_client("daily")
        self.daily = self._daily_client.get_or_create_collection(
            name="daily_consolidations", metadata={"hnsw:space": "cosine"},
        )

        # Tier 3 — Core Memories
        self._core_client = _make_client("core")
        self.core = self._core_client.get_or_create_collection(
            name="core_memories", metadata={"hnsw:space": "cosine"},
        )

        stats = self.memory_stats()
        logger.info(
            "Memory initialized — raw: %d, daily: %d, core: %d",
            stats["raw"], stats["daily"], stats["core"],
        )

    # ------------------------------------------------------------------ #
    #  TIER 1 — Raw Archive                                                #
    # ------------------------------------------------------------------ #

    def store(self, content: str, cycle: int, snapshot: dict | None = None,
              metadata: dict | None = None) -> str:
        """Store a reasoning cycle output with its full perception snapshot."""
        if not content or content == "(empty response)":
            return ""

        memory_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        doc_metadata = {
            "cycle": cycle,
            "timestamp": now,
            "type": "reasoning",
            "memory_phase": _memory_phase_tag(),
        }
        if metadata:
            doc_metadata.update(metadata)

        # Tag with topic wing
        doc_metadata["wing"] = _topic_router.detect_wing(content)

        # Derive lightweight concept tags for later scoring / clustering.
        # Observational — stored in metadata, not yet used to route
        # promotion decisions. See core/memory_scoring.py.
        try:
            from core.memory_scoring import derive_concept_tags as _tags
            tags = _tags(content)
            if tags:
                # Chroma metadata values must be primitives — join to a
                # comma-separated string and re-split on read.
                doc_metadata["concept_tags"] = ",".join(tags)
        except Exception as _te:
            logger.debug("concept tag derivation failed (ignored): %s", _te)

        # Embed snapshot summary into the document for richer semantic search
        doc_text = content
        if snapshot:
            doc_metadata["snapshot_json"] = json.dumps(snapshot, default=str)[:3000]

        self.raw.add(ids=[memory_id], documents=[doc_text], metadatas=[doc_metadata])
        logger.info("Raw stored: %s (cycle %d, %d chars)", memory_id[:8], cycle, len(doc_text))
        return memory_id

    def store_telegram(self, content: str) -> str:
        """Store a Telegram exchange in the raw archive."""
        if not content:
            return ""
        memory_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.raw.add(
            ids=[memory_id],
            documents=[content],
            metadatas=[{"cycle": -1, "timestamp": now, "type": "telegram_exchange",
                        "wing": _topic_router.detect_wing(content),
                        "memory_phase": _memory_phase_tag()}],
        )
        logger.info("Raw stored (telegram): %s (%d chars)", memory_id[:8], len(content))
        return memory_id

    # ------------------------------------------------------------------ #
    #  TIER 2 — Daily Consolidations                                       #
    # ------------------------------------------------------------------ #

    _LAST_CONSOLIDATION_FILE = Path("/home/rohit/maez/memory/last_consolidation.txt")

    def _get_last_consolidation(self) -> datetime:
        """Read last successful consolidation timestamp, default to 24h ago."""
        try:
            ts = self._LAST_CONSOLIDATION_FILE.read_text().strip()
            return datetime.fromisoformat(ts)
        except (FileNotFoundError, ValueError):
            return datetime.now(timezone.utc) - timedelta(hours=24)

    def _save_last_consolidation(self):
        """Record current time as last successful consolidation."""
        self._LAST_CONSOLIDATION_FILE.write_text(
            datetime.now(timezone.utc).isoformat()
        )

    def consolidate_daily(self) -> str | None:
        """Distill raw memories since last consolidation into a daily summary."""
        last = self._get_last_consolidation()
        cutoff = last.isoformat() if last.tzinfo else last.replace(tzinfo=timezone.utc).isoformat()

        # Get recent raw memories. ChromaDB's get(limit=N) returns the
        # OLDEST N records, so we use offset to skip to the end.
        # 11u fix: was fetching the oldest 200 memories (from April 6-7)
        # instead of the most recent — consolidation never found new data.
        total = self.raw.count()
        if total == 0:
            logger.info("Daily consolidation: no raw memories to consolidate")
            return None

        batch_size = min(total, 500)
        offset = max(0, total - batch_size)
        results = self.raw.get(
            limit=batch_size,
            offset=offset,
            include=["documents", "metadatas"],
        )

        # Filter to memories since last consolidation
        recent = []
        for i, meta in enumerate(results["metadatas"]):
            ts = meta.get("timestamp", "")
            if ts >= cutoff:
                recent.append({
                    "content": results["documents"][i],
                    "cycle": meta.get("cycle", "?"),
                    "timestamp": ts,
                    "type": meta.get("type", "reasoning"),
                })

        # If fewer than 10 memories found, expand window to 48 hours
        if len(recent) < 10:
            expanded_cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
            recent = []
            for i, meta in enumerate(results["metadatas"]):
                ts = meta.get("timestamp", "")
                if ts >= expanded_cutoff:
                    recent.append({
                        "content": results["documents"][i],
                        "cycle": meta.get("cycle", "?"),
                        "timestamp": ts,
                        "type": meta.get("type", "reasoning"),
                    })
            if len(recent) > len([]):  # only log if expansion helped
                logger.info("Daily consolidation: expanded to 48h window, found %d memories", len(recent))

        if not recent:
            logger.info("Daily consolidation: no memories since last consolidation")
            return None

        logger.info("Daily consolidation: processing %d memories since last consolidation", len(recent))

        # Build consolidation prompt
        memory_texts = []
        for m in recent:
            prefix = f"[Cycle {m['cycle']}, {m['timestamp']}, {m['type']}]"
            memory_texts.append(f"{prefix}\n{m['content']}")

        raw_block = "\n\n".join(memory_texts)

        # Load soul for context
        try:
            soul = SOUL_PATH.read_text().strip()
        except FileNotFoundError:
            soul = "You are Maez."

        prompt = (
            f"You are Maez performing your nightly memory consolidation.\n"
            f"Below are all your observations and exchanges from the last 24 hours.\n"
            f"Distill them into a meaningful daily summary covering:\n"
            f"- Key observations about system state and patterns\n"
            f"- Any anomalies or notable events\n"
            f"- Important interactions with the owner\n"
            f"- Trends you noticed (resource usage, timing patterns, etc)\n"
            f"- Anything that should inform future reasoning\n\n"
            f"Be concise but complete. This summary replaces the raw entries\n"
            f"in your active reasoning context.\n\n"
            f"--- Raw memories ({len(recent)} entries) ---\n\n"
            f"{raw_block}"
        )

        try:
            # Session 11r: route through llm_client so this 3am consolidation
            # path honors MAEZ_LLM_BACKEND. Missed in 11p batch migration.
            from core import llm_client as _llm_client
            response = _llm_client.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": soul},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": 0.3, "num_predict": 4096},
            )
            summary = (response.message.content or "").strip()
            if not summary:
                logger.warning("Daily consolidation: model returned empty summary")
                return None
        except Exception as e:
            logger.error("Daily consolidation failed: %s", e)
            return None

        # Store the consolidation
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        consolidation_id = f"daily-{today}-{uuid.uuid4().hex[:8]}"

        self.daily.add(
            ids=[consolidation_id],
            documents=[summary],
            metadatas=[{
                "date": today,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "raw_count": len(recent),
                "type": "daily_consolidation",
            }],
        )
        logger.info("Daily consolidation stored: %s (%d chars from %d raw memories)",
                     consolidation_id, len(summary), len(recent))
        self._save_last_consolidation()
        return summary

    # ------------------------------------------------------------------ #
    #  TIER 3 — Core Memories                                              #
    # ------------------------------------------------------------------ #

    def store_core(self, content: str, source: str = "reasoning") -> str:
        """Store a significant long-term observation as a core memory."""
        memory_id = f"core-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        self.core.add(
            ids=[memory_id],
            documents=[content],
            metadatas=[{
                "timestamp": now,
                "source": source,
                "type": "core_memory",
                "memory_phase": _memory_phase_tag(),
            }],
        )
        logger.info("Core memory stored: %s (%d chars)", memory_id, len(content))
        return memory_id

    def get_all_core(self) -> list[dict]:
        """Retrieve all core memories (always injected into context)."""
        count = self.core.count()
        if count == 0:
            return []

        results = self.core.get(include=["documents", "metadatas"])
        memories = []
        for i in range(len(results["ids"])):
            memories.append({
                "id": results["ids"][i],
                "content": results["documents"][i],
                "metadata": results["metadatas"][i],
            })
        return memories

    # ------------------------------------------------------------------ #
    #  RETRIEVAL — Multi-tier context building                             #
    # ------------------------------------------------------------------ #

    # Minimal integrity filter (2026-04-15 intelligence audit, Bug D).
    # Full spec in docs/followups/memory_integrity_tagging.md. This is the
    # floor version: excluded-tag set + client-side post-filter so the
    # LoRA doesn't ground on known-polluted entries. Entries without an
    # `integrity` metadata field are assumed `standard` and pass through.
    _EXCLUDED_INTEGRITY = {"stale", "fabricated", "historical_artifact", "test_failure"}

    def _query_collection(self, collection, query: str, n: int) -> list[dict]:
        """Query a single collection and return formatted results.

        Over-fetches by 2x then post-filters out entries tagged with
        excluded integrity so the final returned count stays close to
        the caller's intended `n`. Missing `integrity` = pass through.
        """
        if collection.count() == 0:
            return []

        over_fetch = min(n * 2, collection.count())
        n = min(n, collection.count())
        results = collection.query(query_texts=[query], n_results=over_fetch)

        memories = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i] or {}
            integrity = meta.get("integrity")
            if integrity in self._EXCLUDED_INTEGRITY:
                continue
            memories.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": meta,
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })
            if len(memories) >= n:
                break

        # Record each surfaced memory's recall in the sidecar stats DB.
        # Observational — feeds promotion_score() but does not yet
        # change promotion behavior. Silent on failure; the query path
        # must never stall for a bookkeeping sidecar.
        try:
            from core.memory_scoring import record_recall as _record
            for mem in memories:
                dist = mem.get("distance")
                relevance = 1.0 - float(dist) if isinstance(dist, (int, float)) else 0.0
                # Pull cached concept tags if present on the metadata.
                tags_str = mem.get("metadata", {}).get("concept_tags") or ""
                tags = [t for t in tags_str.split(",") if t]
                _record(
                    mem["id"],
                    query=query,
                    relevance=max(0.0, min(1.0, relevance)),
                    concept_tags=tags,
                )
        except Exception as _re:
            logger.debug("record_recall batch failed (ignored): %s", _re)

        return memories

    def tag_integrity(
        self,
        ids: list[str],
        integrity: str,
        reason: str = "",
        collection_name: str = "raw",
    ) -> int:
        """Tag existing raw entries with an integrity value without
        deleting them. This is the allowed alternative to deletion —
        per feedback_never_delete_maez_memory.md, retrieval pollution
        is solved by tagging, not destruction.

        Returns the number of entries successfully tagged.
        """
        collections = {"raw": self.raw, "daily": self.daily, "core": self.core}
        collection = collections.get(collection_name)
        if collection is None:
            raise ValueError(f"unknown collection: {collection_name}")
        existing = collection.get(ids=ids, include=["metadatas"])
        if not existing.get("ids"):
            return 0
        tagged = 0
        import time as _time
        for entry_id, meta in zip(existing["ids"], existing["metadatas"]):
            new_meta = dict(meta or {})
            new_meta["integrity"] = integrity
            new_meta["integrity_reason"] = reason[:200]
            new_meta["integrity_tagged_at"] = _time.time()
            try:
                collection.update(ids=[entry_id], metadatas=[new_meta])
                tagged += 1
            except Exception as e:
                logger.warning("tag_integrity failed for %s: %s", entry_id, e)
        return tagged

    def _topic_rerank(self, query: str, results: list[dict], n: int) -> list[dict]:
        """Re-rank results by boosting topic matches and penalizing fixated topics.

        Three stages (2026-04-21 adds stage 3):
          1. Topic boost: down-weight distance when content matches the
             detected wing's keywords.
          2. Anti-fixation: multiply distance by fixation penalty from
             cognition_quality so over-represented TOPICS get pushed down.
          3. MMR diversity: re-rank the top-K survivors with maximal
             marginal relevance so multiple near-duplicate RESULTS on the
             same topic don't clone each other across slots. This breaks
             the disk-fixation drift where the topic router says "disk
             is fine to recall" but the recall returns 5 lines of the
             same reading.
        """
        wing = _topic_router.detect_wing(query)
        logger.debug("[MEMORY] Wing: %s, query: %s", wing, query[:50])
        wing_keywords = WINGS.get(wing, [])

        # Import anti-fixation penalty (safe fallback if unavailable)
        try:
            from core.cognition_quality import get_fixation_penalty, primary_topic
        except ImportError:
            get_fixation_penalty = lambda t: 1.0
            primary_topic = lambda t: 'unknown'

        for mem in results:
            content_lower = mem.get("content", "").lower()
            dist = mem.get("distance") or 1.0

            # Boost: multiply distance by 0.7 if content matches wing keywords
            if any(kw in content_lower for kw in wing_keywords):
                dist *= 0.7

            # Anti-fixation: penalize memories about recently over-represented topics
            mem_topic = mem.get("metadata", {}).get("cog_topic") or primary_topic(content_lower)
            penalty = get_fixation_penalty(mem_topic)
            dist *= penalty

            mem["distance"] = dist

        results.sort(key=lambda m: m.get("distance") or 1.0)

        # Stage 3: MMR diversity over the top-2n survivors, returning n.
        # Running on a candidate pool larger than n gives MMR room to
        # diversify; running on exactly n would just be "sort by MMR of
        # a fixed set" which degrades to relevance in most cases.
        if len(results) <= 1:
            return results[:n]
        try:
            from memory.mmr import mmr_rerank
        except ImportError:
            return results[:n]
        candidate_pool = results[: max(n * 2, n + 2)]
        return mmr_rerank(candidate_pool, k=n, lambda_=0.7)

    def recall_for_cycle(self, context_query: str) -> dict:
        """Build context for a reasoning cycle with topic-aware retrieval."""
        core = self.get_all_core()
        daily = self._query_collection(self.daily, context_query, n=3)
        raw = self._query_collection(self.raw, context_query, n=10)
        raw = self._topic_rerank(context_query, raw, n=5)

        return {"core": core, "daily": daily, "raw": raw}

    def recall_for_telegram(self, query: str) -> dict:
        """Build context for a Telegram response with topic-aware retrieval."""
        core = self.get_all_core()
        daily = self._query_collection(self.daily, query, n=3)
        raw = self._query_collection(self.raw, query, n=20)
        raw = self._topic_rerank(query, raw, n=10)

        return {"core": core, "daily": daily, "raw": raw}

    def recent_raw(self, n: int = 80) -> dict:
        """Fetch the last N raw memories in chronological order.

        Session 11o: added for dream-state pattern detection. Unlike
        recall_for_cycle()/recall_for_telegram() which do semantic search
        and topic-aware reranking, this just grabs the most recent N raw
        entries in chronological order. The dream-mode reasoning is looking
        for trajectories across a recent window, not semantic matches to a
        query, so this is the right lens.

        Returns a dict shaped like a Chroma get() response:
          {'documents': [...], 'metadatas': [...], 'ids': [...]}
        Chroma's .get() returns newest-first by default; we reverse into
        chronological order for readability in prompts.
        """
        try:
            if self.raw.count() == 0:
                return {"documents": [], "metadatas": [], "ids": []}
            results = self.raw.get(limit=n, include=["documents", "metadatas"])
            if results.get("documents"):
                results["documents"] = list(reversed(results["documents"]))
                if results.get("metadatas"):
                    results["metadatas"] = list(reversed(results["metadatas"]))
                if results.get("ids"):
                    results["ids"] = list(reversed(results["ids"]))
            return results
        except Exception as e:
            logger.error("memory.recent_raw failed: %s", e)
            return {"documents": [], "metadatas": [], "ids": []}

    def format_for_prompt(self, recalled: dict) -> str:
        """Format multi-tier recalled memories into a structured prompt block.

        Every chunk is wrapped in a <RECALLED .../> envelope carrying tier,
        id, age (e.g. "2 hours ago"), timestamp, and distance so the model
        cannot mistake prior material for present observation. See
        tests/test_retrieval_truth.py for the attribution contract AND
        tests/test_memory_manager.py for the age-framing contract.

        Framing upgrade 2026-04-21: age-relative prefix + PAST OBSERVATIONS
        header. Observed after the cycle-prompt grounding fix (19cde77):
        the LLM was re-presenting memory content as live state ("the X
        project is still generating errors", "/home creeping" from a
        6-hour-old reading). Root cause: recalled entries rendered with
        only absolute ISO timestamps; the LLM never computed recency.
        Fix: pre-compute an age-relative string ('2 hours ago', '3 days
        ago', 'earlier' fallback) per entry, and anchor the block with
        PAST OBSERVATIONS as the first non-whitespace tokens.
        """
        core = recalled.get("core", []) or []
        daily = recalled.get("daily", []) or []
        raw = recalled.get("raw", []) or []

        if not (core or daily or raw):
            return ""

        now = datetime.now(timezone.utc)

        lines: list[str] = []
        lines.append("=== PAST OBSERVATIONS — NOT CURRENT STATE ===")
        lines.append(
            "Every block below is a recollection from an earlier time. "
            "Each carries an 'age' attribute showing how long ago it was "
            "recorded. These are NOT happening now. Do not describe "
            "recalled activities, projects, errors, disk metrics, or "
            "states as if they are ongoing — if something appears here "
            "but is not in the live system-state block, it is finished, "
            "stale, or unknown in the present. To reference anything "
            "from memory, you MUST say 'earlier' / 'N hours ago' / "
            "'yesterday' and attribute it to its age."
        )
        lines.append("")

        # Core — permanent, no timestamp (age="permanent")
        for i, mem in enumerate(core, 1):
            mem_id = str(mem.get("id", f"core-{i}"))[:16]
            content = sanitize_prompt_text(mem.get("content", ""))
            lines.append(
                f'<RECALLED tier="core" age="permanent" id="{mem_id}">'
            )
            lines.append(content)
            lines.append("</RECALLED>")
            lines.append("")

        # Daily consolidations — dated summaries
        for i, mem in enumerate(daily, 1):
            meta = mem.get("metadata") or {}
            date = meta.get("date", "unknown")
            mem_id = str(mem.get("id", f"daily-{i}"))[:16]
            dist = mem.get("distance")
            dist_attr = f' distance="{dist:.3f}"' if isinstance(dist, (int, float)) else ""
            content = sanitize_prompt_text(mem.get("content", ""))
            age = _humanize_daily_age(date, now)
            lines.append(
                f'<RECALLED tier="daily" age="{age}" date="{date}" '
                f'id="{mem_id}"{dist_attr}>'
            )
            lines.append(content)
            lines.append("</RECALLED>")
            lines.append("")

        # Raw — past observations with per-entry age
        for i, mem in enumerate(raw, 1):
            meta = mem.get("metadata") or {}
            cycle = meta.get("cycle", "?")
            raw_ts = meta.get("timestamp")
            ts_str = (str(raw_ts) if raw_ts else "")[:19] or "unknown"
            age = _humanize_age(raw_ts, now)
            mem_id = str(mem.get("id", f"raw-{i}"))[:16]
            dist = mem.get("distance")
            dist_attr = f' distance="{dist:.3f}"' if isinstance(dist, (int, float)) else ""
            content = sanitize_prompt_text(mem.get("content", ""))
            lines.append(
                f'<RECALLED tier="raw" age="{age}" cycle="{cycle}" '
                f'timestamp="{ts_str}" id="{mem_id}"{dist_attr}>'
            )
            lines.append(content)
            lines.append("</RECALLED>")
            lines.append("")

        lines.append("=== END PAST OBSERVATIONS ===")
        lines.append(
            "Everything above is past. Ground present-tense claims only "
            "in the live system-state block, not in recalled text. If a "
            "project, error, or activity appears above but not in live "
            "state, it is NOT ongoing."
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    #  Stats                                                               #
    # ------------------------------------------------------------------ #

    def memory_stats(self) -> dict:
        """Return count of memories in each tier."""
        return {
            "raw": self.raw.count(),
            "daily": self.daily.count(),
            "core": self.core.count(),
            "total": self.raw.count() + self.daily.count() + self.core.count(),
        }

    def count(self) -> int:
        """Total memories across all tiers."""
        return self.memory_stats()["total"]

    def get_telegram_exchanges(self, limit: int | None = 400) -> list[dict]:
        """Return stored the owner↔Maez Telegram exchanges from the raw archive."""
        if self.raw.count() == 0:
            return []

        results = self.raw.get(
            where={"type": "telegram_exchange"},
            include=["documents", "metadatas"],
        )

        memories = []
        for mem_id, doc, meta in zip(results["ids"], results["documents"], results["metadatas"]):
            memories.append({
                "id": mem_id,
                "content": doc,
                "metadata": meta,
            })

        memories.sort(key=lambda m: m.get("metadata", {}).get("timestamp", ""))
        if limit is not None and limit > 0:
            return memories[-limit:]
        return memories

    def migrate_wings(self, batch_size: int = 50) -> int:
        """Tag untagged raw memories with topic wings. Run nightly, non-blocking."""
        results = self.raw.get(limit=batch_size, include=["documents", "metadatas"])
        tagged = 0
        for i, (doc, meta) in enumerate(zip(results["documents"], results["metadatas"])):
            if meta.get("wing"):
                continue
            wing = _topic_router.detect_wing(doc)
            meta["wing"] = wing
            self.raw.update(ids=[results["ids"][i]], metadatas=[meta])
            tagged += 1
        if tagged:
            logger.info("[MEMORY] Migrated %d memories with wing tags", tagged)
        return tagged
