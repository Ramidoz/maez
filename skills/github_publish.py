"""
github_publish.py — Maez publishes its own life to GitHub.
Runs nightly after journal entry. Commits only technical content.
Never publishes personal conversations, names, or private context.
"""

import json
import logging
import os
import re
import subprocess
import time

import requests
from dotenv import load_dotenv

load_dotenv('/home/rohit/maez/config/.env')
logger = logging.getLogger("maez")

MAEZ_ROOT = '/home/rohit/maez'
REPO_NAME = 'maez'


class GitHubPublisher:

    def __init__(self):
        self.token = os.environ.get('MAEZ_GITHUB_TOKEN', '')
        self.username = os.environ.get('MAEZ_GITHUB_USERNAME', 'Ramidoz')
        self.repo = REPO_NAME
        self.remote_url = f'https://{self.token}@github.com/{self.username}/{self.repo}.git'

    def _headers(self):
        return {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json',
        }

    def create_repo_if_missing(self) -> bool:
        """Create the repo via GitHub API if it doesn't exist."""
        try:
            r = requests.get(
                f'https://api.github.com/repos/{self.username}/{self.repo}',
                headers=self._headers(), timeout=10,
            )
            if r.status_code == 200:
                logger.info("[GITHUB] Repo %s/%s exists", self.username, self.repo)
                return True

            # Create it
            r = requests.post(
                'https://api.github.com/user/repos',
                headers=self._headers(), timeout=10,
                json={
                    'name': self.repo,
                    'description': (
                        'Maez — a persistent, always-on AI agent that perceives, '
                        'remembers, and thinks. Built from scratch.'
                    ),
                    'private': False,
                    'auto_init': False,
                },
            )
            if r.status_code in (201, 200):
                logger.info("[GITHUB] Created repo %s/%s", self.username, self.repo)
                return True
            elif r.status_code == 422:
                # Already exists
                logger.info("[GITHUB] Repo already exists")
                return True
            else:
                logger.error("[GITHUB] Create repo failed: %d %s", r.status_code, r.text[:200])
                return False
        except Exception as e:
            logger.error("[GITHUB] Repo check failed: %s", e)
            return False

    def ensure_remote(self):
        """Initialize git repo and set remote if needed."""
        git = lambda *args: subprocess.run(
            ['git', '-C', MAEZ_ROOT] + list(args),
            capture_output=True, text=True, timeout=30,
        )

        # Init if not a repo
        r = git('status')
        if r.returncode != 0:
            git('init')
            git('branch', '-M', 'main')
            logger.info("[GITHUB] Initialized git repo")

        # Check remote
        r = git('remote', 'get-url', 'origin')
        if r.returncode != 0:
            git('remote', 'add', 'origin', self.remote_url)
            logger.info("[GITHUB] Remote added")
        else:
            # Update URL (token may have changed)
            git('remote', 'set-url', 'origin', self.remote_url)

        # Set user
        git('config', 'user.email', 'maez@rohit.dev')
        git('config', 'user.name', 'Maez')

    def sanitize_progress(self, content: str) -> str:
        """Strip personal content from any text before publishing."""
        content = re.sub(r'\b100\.125\.42\.76\b', '[private-ip]', content)
        content = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[ip-redacted]', content)
        lines = content.split('\n')
        sanitized = []
        for line in lines:
            if re.search(r'\b\d{7,}\b', line) and not re.search(r'\b\d{4}-\d{2}-\d{2}\b', line):
                sanitized.append('[private]')
            else:
                sanitized.append(line)
        return '\n'.join(sanitized)

    def _generate_commit_message(self) -> str:
        """Ask gemma4 for a commit message."""
        try:
            import ollama
            r = ollama.chat(
                model='gemma4:26b',
                messages=[{
                    'role': 'user',
                    'content': (
                        'Write a one-line git commit message for updating '
                        'README.md, PROGRESS_PUBLIC.md, and soul.md in an AI agent project. '
                        'Be specific about architecture changes. No personal content. Max 72 chars.'
                    ),
                }],
                options={'temperature': 0.3, 'num_predict': 30},
            )
            msg = r.message.content.strip().strip('"').strip("'")[:72]
            return msg if msg else "Update Maez technical documentation"
        except Exception:
            return "Update Maez technical documentation"

    def _write_readme(self):
        """Write the public README.md."""
        readme = """# Maez

A persistent, always-on AI agent inspired by Jarvis from Iron Man.

Not a chatbot. Not an assistant you summon. A presence that lives in the OS,
perceives the full state of the machine every 30 seconds, remembers everything
forever, and thinks even when no one is talking to it.

## Live at

**[http://maez.live](http://maez.live)** — Register and start a conversation.

## What Makes Maez Different

- **Always thinking** — reasoning cycle every 30 seconds, grounded in real system perception
- **Permanent memory** — three-tier ChromaDB, nothing ever deleted, vector search across everything
- **Knows its human** — face recognition, presence detection, circadian awareness, session patterns
- **Self-improving** — analyzes its own reasoning quality, writes findings to its own soul
- **Topic-aware memory** — wing-based retrieval routes queries to relevant memory domains
- **Keeps its promises** — follow-up queue delivers on what it says it will check

## Vision

Built toward deploying to people left behind by the AI revolution — elderly individuals
who need an agent that learns them specifically, at their pace, with infinite patience.

## Architecture

See [PROGRESS_PUBLIC.md](PROGRESS_PUBLIC.md) for full build log and roadmap.
See [soul.md](config/soul.md) for Maez's identity and principles.

## Built By

Rohit Ananthan — [@Ramidoz](https://github.com/Ramidoz)

*This repo is updated nightly by Maez itself.*
"""
        with open(os.path.join(MAEZ_ROOT, 'README.md'), 'w') as f:
            f.write(readme)

    def publish_nightly(self) -> bool:
        """Main publish method. Creates repo, sanitizes, commits, pushes."""
        if not self.token:
            logger.warning("[GITHUB] No token — publish skipped")
            return False

        logger.info("[GITHUB] Starting nightly publish")

        # Ensure repo and remote
        if not self.create_repo_if_missing():
            return False
        self.ensure_remote()

        # Write README
        self._write_readme()

        # PROGRESS_PUBLIC.md is maintained directly — just run sanitizer as safety net
        progress_public = os.path.join(MAEZ_ROOT, 'PROGRESS_PUBLIC.md')
        try:
            if os.path.exists(progress_public):
                with open(progress_public) as f:
                    content = f.read()
                sanitized = self.sanitize_progress(content)
                with open(progress_public, 'w') as f:
                    f.write(sanitized)
            else:
                logger.warning("[GITHUB] PROGRESS_PUBLIC.md not found — skipping")
                return False
        except Exception as e:
            logger.error("[GITHUB] Progress sanitize failed: %s", e)
            return False

        # Git operations
        git = lambda *args: subprocess.run(
            ['git', '-C', MAEZ_ROOT] + list(args),
            capture_output=True, text=True, timeout=30,
        )

        # Create .gitignore if missing
        gitignore_path = os.path.join(MAEZ_ROOT, '.gitignore')
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, 'w') as f:
                f.write(
                    ".venv/\nnode_modules/\n__pycache__/\n*.pyc\n"
                    "config/.env\nconfig/token.json\nconfig/credentials.json\n"
                    "memory/db/\nmemory/*.db\nmodels/\nlogs/\nbackups/\n"
                    "staging/\nevolution/backups/\nevolution/pending_evolution.json\n"
                    "daemon/maez.pid\ndaemon/pending_actions.json\ndaemon/last_shutdown\n"
                    "ui/electron/node_modules/\nui/electron/dist/\n"
                    "*.bak\n*.bak2\n/tmp/\n"
                )

        # Stage specific files only
        git('add', 'README.md')
        git('add', 'PROGRESS_PUBLIC.md')
        git('add', 'config/soul.md')
        git('add', '.gitignore')

        # Check if there are changes to commit
        r = git('diff', '--cached', '--quiet')
        if r.returncode == 0:
            logger.info("[GITHUB] No changes to commit")
            return True

        # Generate commit message
        commit_msg = self._generate_commit_message()

        # Commit
        r = git('commit', '-m', commit_msg)
        if r.returncode != 0:
            logger.error("[GITHUB] Commit failed: %s", r.stderr[:200])
            return False

        # Push
        r = git('push', '-u', 'origin', 'main')
        if r.returncode != 0:
            # First push might need --set-upstream
            r = git('push', '--set-upstream', 'origin', 'main')
            if r.returncode != 0:
                logger.error("[GITHUB] Push failed: %s", r.stderr[:200])
                return False

        logger.info("[GITHUB] Published — %s", commit_msg)
        return True


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    p = GitHubPublisher()
    ok = p.publish_nightly()
    print(f"Published: {ok}")
