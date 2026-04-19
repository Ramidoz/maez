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
from typing import Optional

import requests
import yaml

logger = logging.getLogger('maez.reddit')

# Safe generic defaults — used only if neither config nor template is found.
_DEFAULT_SUBREDDITS = [
    'artificial', 'MachineLearning', 'LocalLLaMA',
    'programming', 'technology',
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

HEADERS = {'User-Agent': 'Maez-Personal-Agent/1.0 (personal use)'}


class RedditSkill:

    def __init__(self):
        self._cache = {}
        self._cache_time = {}
        self.cache_ttl = 450
        logger.info("Reddit skill initialized: %d subreddits", len(SUBREDDITS))

    def _fetch_subreddit(self, subreddit: str, limit: int = 3) -> list:
        cache_key = f'reddit_{subreddit}'
        if cache_key in self._cache:
            age = (datetime.now() - self._cache_time[cache_key]).total_seconds()
            if age < self.cache_ttl:
                return self._cache[cache_key]
        try:
            url = f'https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}'
            r = requests.get(url, headers=HEADERS, timeout=8)
            r.raise_for_status()
            data = r.json()
            posts = []
            for child in data.get('data', {}).get('children', []):
                post = child.get('data', {})
                if post.get('stickied'):
                    continue
                posts.append({
                    'title': post.get('title', '')[:120],
                    'score': post.get('score', 0),
                    'comments': post.get('num_comments', 0),
                    'flair': post.get('link_flair_text', '') or '',
                })
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


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    r = RedditSkill()
    print(r.get_context_block())
