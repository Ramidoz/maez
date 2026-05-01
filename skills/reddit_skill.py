# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
Reddit awareness for Maez. Each user's subreddit list is per-user config.
No API key — uses public JSON endpoints. Injected as [REDDIT] every 15 cycles.

Subreddit list lives in config/reddit_subs.yaml (gitignored — per user).
A config/reddit_subs.template.yaml ships with generic AI/tech defaults;
each user copies and personalizes after install.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

import requests
import yaml

logger = logging.getLogger("maez.reddit")

# Safe generic defaults — used only if neither config nor template is found.
_DEFAULT_SUBREDDITS = [
    "artificial",
    "MachineLearning",
    "LocalLLaMA",
    "programming",
    "technology",
]


def _load_subreddits() -> list:
    """Load per-user subreddit list from config. Defaults to generic if absent."""
    config_dir = Path(os.environ.get("MAEZ_CONFIG_DIR", "/home/rohit/maez/config"))
    user_path = config_dir / "reddit_subs.yaml"
    template_path = config_dir / "reddit_subs.template.yaml"
    for path in (user_path, template_path):
        try:
            if path.exists():
                data = yaml.safe_load(path.read_text()) or {}
                subs = data.get("subreddits")
                if isinstance(subs, list) and subs:
                    return [str(s).strip() for s in subs if s]
        except Exception as e:
            logger.warning("failed to load %s: %s", path, e)
    return list(_DEFAULT_SUBREDDITS)


SUBREDDITS = _load_subreddits()

HEADERS = {"User-Agent": "Maez-Personal-Agent/1.0 (personal use)"}


class RedditSkill:
    def __init__(self):
        # Cache shape: subreddit -> list[post_dict]; post_dict has
        # the audit-relevant fields (id, title, score, comments,
        # flair, subreddit) so persist_to_memory can write each
        # post with stable provenance.
        self._cache = {}
        self._cache_time = {}
        self.cache_ttl = 450
        # Per-process dedup of persisted post IDs. Survives within
        # one daemon lifetime; a restart accepts limited re-writes
        # of currently-hot posts (bounded by post lifetime in /hot).
        self._persisted_ids: set[str] = set()
        logger.info("Reddit skill initialized: %d subreddits", len(SUBREDDITS))

    def _fetch_subreddit(self, subreddit: str, limit: int = 3) -> list:
        cache_key = f"reddit_{subreddit}"
        if cache_key in self._cache:
            age = (datetime.now() - self._cache_time[cache_key]).total_seconds()
            if age < self.cache_ttl:
                return self._cache[cache_key]
        try:
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
            r = requests.get(url, headers=HEADERS, timeout=8)
            r.raise_for_status()
            data = r.json()
            posts = []
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                if post.get("stickied"):
                    continue
                posts.append(
                    {
                        # Reddit's stable post id (e.g. "abc123"). Used
                        # by persist_to_memory for audit-pipeline filter
                        # and dedup. Without this, the 21:35 TRELLIS-
                        # incident class of unverifiable Reddit
                        # references stays open. 2026-04-27 closure.
                        "id": post.get("id", ""),
                        "subreddit": subreddit,
                        "title": post.get("title", "")[:120],
                        "score": post.get("score", 0),
                        "comments": post.get("num_comments", 0),
                        "flair": post.get("link_flair_text", "") or "",
                    }
                )
            self._cache[cache_key] = posts
            self._cache_time[cache_key] = datetime.now()
            return posts
        except Exception as e:
            logger.debug("Reddit r/%s failed: %s", subreddit, e)
            return []

    def get_context_block(self) -> str:
        lines = ["[REDDIT]"]
        any_content = False
        for sub in SUBREDDITS:
            posts = self._fetch_subreddit(sub, limit=3)
            if not posts:
                continue
            any_content = True
            lines.append(f"r/{sub}:")
            for p in posts[:2]:
                lines.append(f"  [{p['score']}pts {p['comments']}c] {p['title']}")
        if not any_content:
            return "[REDDIT] Unavailable."
        return "\n".join(lines)

    def persist_to_memory(self, memory_manager, cycle: int = 0) -> int:
        """Persist cached Reddit posts to raw memory so audit pipelines
        can verify references.

        2026-04-27 incident closure: the 21:35 cycle thought referenced
        a real TRELLIS.2 post on r/LocalLLaMA, but no Reddit signal was
        in raw memory. Audit checks that filter by ``source=reddit``
        false-negatively concluded the reference was fabricated. Real
        cause: signals were only injected as in-cycle context, never
        persisted. This method closes the gap.

        Walks ``self._cache``, persists each post with audit-friendly
        metadata (``type='reddit_post'``, ``source='reddit/r/<sub>'``,
        ``reddit_post_id=<id>``), and dedupes via the in-memory
        ``_persisted_ids`` set so the same post is not re-written when
        the daemon's cycle re-uses the 450s cache.

        Returns the number of new entries written. Never raises;
        storage failures are logged at debug.
        """
        written = 0
        for subreddit, posts in self._cache.items():
            sub_name = subreddit.replace("reddit_", "", 1)
            for post in posts or []:
                pid = (post.get("id") or "").strip()
                if not pid or pid in self._persisted_ids:
                    continue
                title = post.get("title", "")
                score = post.get("score", 0)
                comments = post.get("comments", 0)
                flair = post.get("flair", "")
                # Document text includes id + subreddit + title so a
                # future lived-recall keyword query against
                # `r/LocalLLaMA TRELLIS` resolves correctly. Score and
                # comment count are useful signal context for the
                # synthesis path.
                doc = (
                    f"[REDDIT r/{sub_name} post {pid}] "
                    f"{title} "
                    f"({score} pts, {comments} comments"
                    + (f", flair: {flair}" if flair else "")
                    + ")"
                )
                # 5x.B Pass 2a: the freeform `source` key below is
                # descriptive ("reddit/r/<sub>") and routes topic
                # filters; it is intentionally NOT the provenance
                # enum. The provenance lineage rides on the separate
                # `provenance_source`/`trust_tier` kwargs to store()
                # below, so the two coexist without overload.
                metadata = {
                    "type": "reddit_post",
                    "source": f"reddit/r/{sub_name}",
                    "reddit_post_id": pid,
                    "reddit_subreddit": sub_name,
                    "reddit_score": score,
                    "reddit_comments": comments,
                    "reddit_flair": flair,
                }
                try:
                    # 5x.B Pass 2a: external_web/untrusted. This is
                    # the canonical adversarial-content ingress per
                    # the Zombie Agents threat model — promotion
                    # into core or SFT must require ancestor opt-in
                    # (5x.D), never the flat tag alone.
                    memory_manager.store(
                        doc,
                        cycle=cycle,
                        metadata=metadata,
                        provenance_source="external_web",
                        trust_tier="untrusted",
                    )
                    self._persisted_ids.add(pid)
                    written += 1
                except Exception as e:  # pragma: no cover — defensive
                    logger.debug(
                        "reddit persist failed for %s: %s",
                        pid,
                        e,
                    )
        return written


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    r = RedditSkill()
    print(r.get_context_block())
