"""
GitHub awareness skill for Maez.
Rohit's repos + trending AI repos. Injected as [GITHUB] every 10 cycles.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv('/home/rohit/maez/config/.env')
logger = logging.getLogger('maez.github')


class GitHubSkill:

    TRENDING_TOPICS = ['llm', 'agent', 'rag', 'ollama', 'local-llm', 'ai-agent']

    def __init__(self):
        self.token = os.environ.get('MAEZ_GITHUB_TOKEN', '')
        self.username = os.environ.get('MAEZ_GITHUB_USERNAME', 'Ramidoz')
        self.enabled = bool(self.token)
        self._cache = {}
        self._cache_time = {}
        self.cache_ttl = 300
        if self.enabled:
            logger.info("GitHub skill initialized for user: %s", self.username)
        else:
            logger.warning("GitHub skill disabled: MAEZ_GITHUB_TOKEN not set")

    def _headers(self):
        return {'Authorization': f'token {self.token}',
                'Accept': 'application/vnd.github.v3+json'}

    def _get(self, url: str, cache_key: str = None, ttl: int = None) -> Optional[dict]:
        if not self.enabled:
            return None
        if cache_key and cache_key in self._cache:
            age = (datetime.now() - self._cache_time[cache_key]).total_seconds()
            if age < (ttl or self.cache_ttl):
                return self._cache[cache_key]
        try:
            r = requests.get(url, headers=self._headers(), timeout=10)
            r.raise_for_status()
            data = r.json()
            if cache_key:
                self._cache[cache_key] = data
                self._cache_time[cache_key] = datetime.now()
            return data
        except Exception as e:
            logger.debug("GitHub GET %s failed: %s", url, e)
            return None

    def get_user_repos(self) -> list:
        data = self._get(
            f'https://api.github.com/user/repos?per_page=100&sort=updated&affiliation=owner',
            cache_key='user_repos', ttl=300,
        )
        return data if isinstance(data, list) else []

    def get_recent_commits(self, repo_name: str, limit: int = 3) -> list:
        data = self._get(
            f'https://api.github.com/repos/{self.username}/{repo_name}/commits?per_page={limit}',
            cache_key=f'commits_{repo_name}', ttl=180,
        )
        if not data or not isinstance(data, list):
            return []
        return [{'sha': c['sha'][:7],
                 'message': c['commit']['message'].split('\n')[0][:80],
                 'date': c['commit']['author']['date'][:10]}
                for c in data]

    def get_trending_ai_repos(self, limit: int = 6) -> list:
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
        trending = []
        seen = set()
        for topic in self.TRENDING_TOPICS[:3]:
            data = self._get(
                f'https://api.github.com/search/repositories?q=topic:{topic}+pushed:>{week_ago}'
                f'&sort=stars&order=desc&per_page=3',
                cache_key=f'trending_{topic}', ttl=600,
            )
            if not data or 'items' not in data:
                continue
            for item in data['items']:
                if item['full_name'] not in seen:
                    seen.add(item['full_name'])
                    trending.append({
                        'name': item['full_name'],
                        'description': (item.get('description') or '')[:100],
                        'stars': item['stargazers_count'],
                        'url': item['html_url'],
                    })
        trending.sort(key=lambda x: x['stars'], reverse=True)
        return trending[:limit]

    def get_user_activity(self) -> list:
        data = self._get(
            f'https://api.github.com/users/{self.username}/events?per_page=15',
            cache_key='user_events', ttl=180,
        )
        if not data or not isinstance(data, list):
            return []
        activity = []
        seen = set()
        for ev in data:
            repo = ev.get('repo', {}).get('name', '')
            etype = ev.get('type', '')
            if repo in seen:
                continue
            seen.add(repo)
            if etype == 'PushEvent':
                commits = ev.get('payload', {}).get('commits', [])
                msg = commits[0]['message'].split('\n')[0][:60] if commits else ''
                activity.append(f"Pushed to {repo}: {msg}")
            elif etype == 'CreateEvent':
                activity.append(f"Created {ev.get('payload', {}).get('ref_type', '')} in {repo}")
            elif etype == 'WatchEvent':
                activity.append(f"Starred {repo}")
        return activity[:6]

    def get_context_block(self) -> str:
        if not self.enabled:
            return ""
        try:
            repos = self.get_user_repos()
            active = sorted(repos, key=lambda r: r.get('updated_at', ''), reverse=True)[:5]
            activity = self.get_user_activity()
            trending = self.get_trending_ai_repos(5)

            lines = [f"[GITHUB] Rohit has {len(repos)} repos."]

            if active:
                lines.append("Active repos:")
                for r in active:
                    vis = "private" if r.get('private') else "public"
                    desc = f" — {r.get('description', '')}" if r.get('description') else ""
                    lines.append(f"  {r['name']} ({r.get('language', '?')}, {vis}){desc}")
                    commits = self.get_recent_commits(r['name'], 1)
                    if commits:
                        lines.append(f"    Last: {commits[0]['date']} {commits[0]['message']}")

            if activity:
                lines.append("Recent activity:")
                for a in activity[:4]:
                    lines.append(f"  {a}")

            if trending:
                lines.append("Trending AI this week:")
                for t in trending[:4]:
                    lines.append(f"  {t['name']} ({t['stars']:,} stars) — {t['description'][:60]}")

            return "\n".join(lines)
        except Exception as e:
            logger.error("GitHub context failed: %s", e)
            return "[GITHUB] Unavailable."


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    g = GitHubSkill()
    print(g.get_context_block())
