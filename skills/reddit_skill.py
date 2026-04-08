"""
Reddit awareness for Maez. Rohit's actual subreddits.
No API key — uses public JSON endpoints. Injected as [REDDIT] every 15 cycles.
"""

import logging
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger('maez.reddit')

SUBREDDITS = [
    'stocks', 'h1b', 'pennystocks', 'tesla', 'f1visa',
    'artificial', 'MachineLearning', 'LocalLLaMA', 'datascience',
]

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
