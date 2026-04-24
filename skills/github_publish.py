# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
github_publish.py — Maez publishes its own life to GitHub.
Runs nightly after journal entry. Commits only technical content.
Never publishes personal conversations, names, or private context.
"""

import logging
import os
import re
import subprocess

import requests
from dotenv import load_dotenv

# 2026-04-23 Commit 7b: commit-message generation now tracks the
# current primary brain, not hardcoded "gemma4:26b".
from core.model_config import PRIMARY_MODEL as _PRIMARY_MODEL

load_dotenv('/home/rohit/maez/config/.env')
logger = logging.getLogger("maez")

MAEZ_ROOT = '/home/rohit/maez'
REPO_NAME = 'maez'


class GitHubPublisher:

    def __init__(self):
        self.token = os.environ.get('MAEZ_GITHUB_TOKEN', '')
        _default_user = ""
        try:
            from core import identity as _identity
            _default_user = _identity.git_handle()
        except Exception:
            pass
        self.username = os.environ.get('MAEZ_GITHUB_USERNAME') or _default_user
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
        """Ask the primary brain for a commit message. Session 11r:
        via llm_client (was missed in 11p batch migration).
        2026-04-23 Commit 7b: model now tracks current primary.
        2026-04-24: scope narrowed to reflect what publish_nightly
        actually stages (README is no longer auto-written; see
        `_write_readme` removal below)."""
        try:
            from core import llm_client as _llm_client
            r = _llm_client.chat(
                model=_PRIMARY_MODEL,
                messages=[{
                    'role': 'user',
                    'content': (
                        'Write a one-line git commit message for updating '
                        'PROGRESS_PUBLIC.md and config/soul.base.md in an AI '
                        'agent project. Be specific about what the nightly '
                        'publish brings forward. No personal content. '
                        'Max 72 chars.'
                    ),
                }],
                think=False,
                options={'temperature': 0.3, 'num_predict': 30},
            )
            msg = (r.message.content or '').strip().strip('"').strip("'")
            # 2026-04-24 autonomous-surface audit F5: commit messages
            # are public GitHub output generated by the model. Run them
            # through the same output guard/self-claim wrapper used by
            # visible chat surfaces, then normalize back to a single
            # safe commit-summary line.
            try:
                from core.safety.audited_output import audit_assistant_text
                msg = audit_assistant_text(
                    msg, surface="github_publish_commit_message",
                )
            except Exception as _aud_exc:
                logger.debug("[GITHUB] Commit-message audit fail-open: %s", _aud_exc)
            msg = " ".join(msg.split())[:72]
            return msg if msg else "nightly publish: PROGRESS + soul"
        except Exception:
            return "nightly publish: PROGRESS + soul"

    # `_write_readme` removed 2026-04-24. The method used to regenerate
    # README.md from a hardcoded template every night at 23:00 CDT,
    # wiping out deliberate voice work (grandmother framing, Stand-
    # from-JoJo framing, launch-prep polish, CI badges). The template
    # also carried the role-label leak ("Built By: the owner") that
    # the 2026-04-24 voice-fix pass closed elsewhere in the codebase.
    # Nightly publish now touches PROGRESS_PUBLIC.md and
    # config/soul.base.md only; README edits flow through the normal
    # commit path (human-authored, deliberate).

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

        # README is no longer auto-written. See `_write_readme`
        # removal note above for the 2026-04-24 voice-regression
        # rationale. README edits come from deliberate commits; the
        # nightly publish stages only PROGRESS_PUBLIC and soul.base.

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
                    "*.bak\n*.bak2\n/tmp/\n"
                )

        # Stage specific files only. README intentionally omitted as
        # of 2026-04-24 — see `_write_readme` removal note. `soul.md`
        # is gitignored so the add is a no-op there; `soul.base.md`
        # is the publicly-shipped layer and is staged explicitly.
        git('add', 'PROGRESS_PUBLIC.md')
        git('add', 'config/soul.base.md')
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
