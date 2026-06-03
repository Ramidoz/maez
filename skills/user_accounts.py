# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
user_accounts.py — Universal identity system for Maez.
One account, multiple channels. Username + password auth.
"""

import hashlib
import json
import logging
import os
import secrets
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger("maez")

try:
    from core.infra import paths as _paths
    _MAEZ_HOME_PATH = _paths.home()
except Exception:
    from pathlib import Path as _Path
    _MAEZ_HOME_PATH = _Path(__file__).resolve().parent.parent
DB_PATH = str(_MAEZ_HOME_PATH / "memory" / "users.db")
PRIVATE_OWNER_PROFILE_ID = "private_owner"
ENV_PATH = str(_MAEZ_HOME_PATH / "config" / ".env")

try:
    import bcrypt
    _USE_BCRYPT = True
except ImportError:
    _USE_BCRYPT = False
    logger.warning("bcrypt not available — using sha256 fallback")


def _hash_password(password: str) -> str:
    if _USE_BCRYPT:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"sha256:{salt}:{h}"


def _check_password(password: str, hashed: str) -> bool:
    if _USE_BCRYPT and not hashed.startswith("sha256:"):
        return bcrypt.checkpw(password.encode(), hashed.encode())
    if hashed.startswith("sha256:"):
        _, salt, h = hashed.split(":")
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    return False


def _owner_telegram_id() -> str:
    owner_id = os.environ.get("MAEZ_TELEGRAM_USER_ID", "").strip()
    if owner_id:
        return owner_id
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_PATH)
        owner_id = os.environ.get("MAEZ_TELEGRAM_USER_ID", "").strip()
        if owner_id:
            return owner_id
    except Exception:
        pass
    try:
        with open(ENV_PATH) as f:
            for line in f:
                if line.startswith("MAEZ_TELEGRAM_USER_ID="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    except Exception:
        pass
    return ""


class UserAccounts:

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uuid         TEXT PRIMARY KEY,
                    username     TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    display_name TEXT,
                    created_at   REAL NOT NULL,
                    last_seen    REAL,
                    telegram_id  TEXT UNIQUE,
                    whatsapp_id  TEXT UNIQUE,
                    web_token    TEXT UNIQUE
                )
            """)
            conn.commit()
        self._migrate()

    def _migrate(self):
        """Add new columns if they don't exist."""
        new_cols = {
            'trust_tier': 'INTEGER DEFAULT 0',
            'relationship': 'TEXT',
            'rohit_confirmed': 'INTEGER DEFAULT 0',
            'share_config': "TEXT DEFAULT '{}'",
            'telegram_profile_id': 'TEXT',
            'notes': 'TEXT',
        }
        with self._conn() as conn:
            existing = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
            for col, typedef in new_cols.items():
                if col not in existing:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {col} {typedef}")
            conn.commit()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:  # transaction: commit on success / rollback on error
                yield conn
        finally:
            conn.close()

    def register(self, username: str, password: str, display_name: str = "") -> dict:
        username = username.lower().strip()
        if not self.username_available(username):
            raise ValueError(f"Username '{username}' is taken")
        uid = secrets.token_hex(8)
        token = secrets.token_urlsafe(32)
        pw_hash = _hash_password(password)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO users (uuid, username, password_hash, display_name, "
                "created_at, last_seen, web_token) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (uid, username, pw_hash, display_name or username, time.time(), time.time(), token),
            )
            conn.commit()
        logger.info("User registered: %s (%s)", username, uid)
        # Sync to public_users chromadb so daemon's _get_public_context() can
        # resolve display names instead of raw uuid hex strings in its prompt.
        try:
            from skills.telegram_public import UserProfileStore
            UserProfileStore().get_or_create_profile(
                user_id=uid,
                username=username,
                first_name=display_name or username,
            )
        except Exception as e:
            logger.debug("Profile store sync skipped for %s: %s", username, e)
        return {"uuid": uid, "web_token": token, "display_name": display_name or username}

    def login(self, username: str, password: str) -> Optional[dict]:
        username = username.lower().strip()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT uuid, password_hash, display_name, web_token FROM users WHERE username=?",
                (username,),
            ).fetchone()
        if not row:
            return None
        uid, pw_hash, display, token = row
        if not _check_password(password, pw_hash):
            return None
        self.update_last_seen(uid)
        return {"uuid": uid, "web_token": token, "display_name": display}

    def get_by_token(self, token: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT uuid, username, display_name FROM users WHERE web_token=?",
                (token,),
            ).fetchone()
        if not row:
            return None
        self.update_last_seen(row[0])
        return {"uuid": row[0], "username": row[1], "display_name": row[2]}

    def get_by_telegram_id(self, telegram_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT uuid, username, display_name FROM users WHERE telegram_id=?",
                (telegram_id,),
            ).fetchone()
        return {"uuid": row[0], "username": row[1], "display_name": row[2]} if row else None

    def link_telegram(self, uid: str, telegram_id: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET telegram_id=?, telegram_profile_id=? WHERE uuid=?",
                (telegram_id, telegram_id, uid),
            )
            conn.commit()
        logger.info("Telegram linked for %s", uid)

    def link_private_owner(self, uid: str):
        owner_telegram_id = _owner_telegram_id()
        if not owner_telegram_id:
            raise ValueError("MAEZ_TELEGRAM_USER_ID is not configured")
        share_config = self.get_share_config(uid) or _default_share_config(3, "owner")
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET telegram_id=?, telegram_profile_id=?, rohit_confirmed=1, "
                "relationship='owner', trust_tier=3, share_config=? WHERE uuid=?",
                (
                    owner_telegram_id,
                    PRIVATE_OWNER_PROFILE_ID,
                    json.dumps(share_config),
                    uid,
                ),
            )
            conn.commit()
        logger.info("Private owner bridge linked for %s", uid)

    def update_last_seen(self, uid: str):
        with self._conn() as conn:
            conn.execute("UPDATE users SET last_seen=? WHERE uuid=?", (time.time(), uid))
            conn.commit()

    def username_available(self, username: str) -> bool:
        with self._conn() as conn:
            row = conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
        return row is None

    def count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def get_by_username(self, username: str) -> Optional[dict]:
        username = username.lower().strip()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT uuid, username, display_name, trust_tier, relationship FROM users WHERE username=?",
                (username,),
            ).fetchone()
        if not row:
            return None
        return {"uuid": row[0], "username": row[1], "display_name": row[2],
                "trust_tier": row[3], "relationship": row[4]}

    def get_user_record(self, uid: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT uuid, username, display_name, trust_tier, relationship, "
                "rohit_confirmed, share_config, telegram_id, telegram_profile_id "
                "FROM users WHERE uuid=?",
                (uid,),
            ).fetchone()
        if not row:
            return None
        try:
            share_config = json.loads(row[6]) if row[6] else {}
        except Exception:
            share_config = {}
        owner_telegram_id = _owner_telegram_id()
        private_owner_bridge = bool(
            row[7]
            and owner_telegram_id
            and str(row[7]) == owner_telegram_id
            and row[8] == PRIVATE_OWNER_PROFILE_ID
        )
        return {
            "uuid": row[0],
            "username": row[1],
            "display_name": row[2],
            "trust_tier": row[3],
            "relationship": row[4],
            "rohit_confirmed": bool(row[5]),
            "share_config": share_config,
            "telegram_id": row[7],
            "telegram_profile_id": row[8],
            "private_owner_bridge": private_owner_bridge,
        }

    def has_private_owner_bridge(self, uid: str) -> bool:
        record = self.get_user_record(uid)
        return bool(record and record.get("private_owner_bridge"))

    def get_by_display_name(self, name: str) -> Optional[dict]:
        """Fuzzy match by display name (case insensitive)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT uuid, username, display_name, trust_tier, relationship FROM users "
                "WHERE LOWER(display_name) = LOWER(?)", (name,),
            ).fetchone()
        if not row:
            return None
        return {"uuid": row[0], "username": row[1], "display_name": row[2],
                "trust_tier": row[3], "relationship": row[4]}

    def set_trust(self, uid: str, tier: int, relationship: str = None, share_config: dict = None):
        with self._conn() as conn:
            if relationship:
                conn.execute("UPDATE users SET trust_tier=?, relationship=? WHERE uuid=?",
                             (tier, relationship, uid))
            else:
                conn.execute("UPDATE users SET trust_tier=? WHERE uuid=?", (tier, uid))
            if share_config:
                conn.execute("UPDATE users SET share_config=? WHERE uuid=?",
                             (json.dumps(share_config), uid))
            conn.commit()

    def confirm_user(self, uid: str, relationship: str, tier: int, share_config: dict):
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET rohit_confirmed=1, relationship=?, trust_tier=?, share_config=? WHERE uuid=?",
                (relationship, tier, json.dumps(share_config), uid),
            )
            conn.commit()
        logger.info("User %s confirmed: %s tier %d", uid, relationship, tier)

    def get_unconfirmed_users(self, since_hours: int = 24) -> list:
        cutoff = time.time() - (since_hours * 3600)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT uuid, username, display_name, created_at, notes FROM users "
                "WHERE rohit_confirmed=0 AND created_at > ?", (cutoff,),
            ).fetchall()
        return [{"uuid": r[0], "username": r[1], "display_name": r[2],
                 "created_at": r[3], "notes": r[4] or ""} for r in rows]

    def get_share_config(self, uid: str) -> dict:
        with self._conn() as conn:
            row = conn.execute("SELECT share_config FROM users WHERE uuid=?", (uid,)).fetchone()
        if not row or not row[0]:
            return {}
        try:
            return json.loads(row[0])
        except Exception:
            return {}

    def find_possible_telegram_match(
        self,
        display_name: str,
        username: str = None,
        exclude_user_id: str = None,
    ) -> Optional[dict]:
        """Check public_users ChromaDB for a name match (fuzzy, case-insensitive)."""
        try:
            import chromadb
            from chromadb.config import Settings
            client = chromadb.PersistentClient(
                str(_MAEZ_HOME_PATH / "memory" / "db" / "public_users"),
                settings=Settings(anonymized_telemetry=False),
            )
            profiles = client.get_or_create_collection("user_profiles")
            results = profiles.get(include=["metadatas"])

            check_names = [n.lower() for n in [display_name, username] if n]

            for meta in results.get("metadatas", []):
                telegram_id = str(meta.get("user_id", "") or "").strip()
                message_count = int(meta.get("message_count", 0) or 0)

                # Only suggest real Telegram identities with actual history.
                if not telegram_id or telegram_id == str(exclude_user_id or ""):
                    continue
                if not telegram_id.isdigit() or message_count <= 0:
                    continue

                first_name = meta.get("first_name", "").lower()
                tg_username = meta.get("username", "").lower()

                for name in check_names:
                    if (name in first_name or first_name in name or
                            name in tg_username or tg_username in name):
                        return {
                            "telegram_id": telegram_id,
                            "name": meta.get("first_name"),
                            "message_count": message_count,
                            "suggestion": (
                                f"I think I've spoken with you on Telegram before "
                                f"as {meta.get('first_name')}. Want to link those conversations?"
                            ),
                        }
        except Exception as e:
            logger.debug("Telegram match error: %s", e)
        return None


def _default_share_config(tier: int, relationship: str = "") -> dict:
    configs = {
        0: {},
        1: {"work_status": True},
        2: {"work_status": True, "mood": True, "availability": True},
        3: {"work_status": True, "mood": True, "availability": True,
            "projects": True, "general_updates": True},
    }
    return configs.get(tier, {})
