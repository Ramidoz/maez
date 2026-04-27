#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
web_interface.py — Maez web chat interface.
Standalone Flask app on port 11437. Registration, login, chat.
"""

import glob
import logging
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import uuid4

sys.path.insert(0, '/home/rohit/maez')
from dotenv import load_dotenv
load_dotenv('/home/rohit/maez/config/.env')

from flask import Flask, jsonify, request, redirect, send_file, send_from_directory

from skills.user_accounts import UserAccounts
from memory.memory_manager import MemoryManager

logger = logging.getLogger("maez.web")
logging.basicConfig(level=logging.INFO)

app = Flask("maez-web")
accounts = UserAccounts()
memory = MemoryManager()

SOUL_PATH = '/home/rohit/maez/config/soul.md'
from core.model_config import PRIMARY_MODEL as MODEL  # /etc/maez/model.env
UI_DIR = '/home/rohit/maez/ui'
HERO_PAGE = os.path.join(UI_DIR, 'maez_hero.html')
GATE_PAGE = os.path.join(UI_DIR, 'maez_gate.html')
PROGRESS_PUBLIC_PAGE = os.path.join(UI_DIR, 'progress_public.html')
PROGRESS_LOCAL_PAGE = os.path.join(UI_DIR, 'progress_local.html')
ANALYTICS_PAGE = os.path.join(UI_DIR, 'analytics_local.html')
ANALYTICS_SCRIPT = os.path.join(UI_DIR, 'maez_analytics.js')
DEBUG_PAGE = os.path.join(UI_DIR, 'debug.html')
AUTH_COOKIE = 'maez_token'
PLANNER_PATH = '/home/rohit/maez/memory/project_planner.json'
PLANNER_LOCK = threading.Lock()
PLANNER_STATUSES = ('done', 'in_progress', 'next', 'planned')
PLANNER_VISIBILITIES = ('public', 'private')
ANALYTICS_PATH = '/home/rohit/maez/memory/site_analytics.jsonl'
ANALYTICS_LOCK = threading.Lock()
ANALYTICS_EVENT_TYPES = ('pageview', 'cta_click')
ANALYTICS_FUNNEL = (
    ("/", "Landing"),
    ("/progress", "Progress"),
    ("/dashboard", "Architecture"),
    ("/login", "Login"),
    ("/app", "Channel"),
)
PRIVATE_OWNER_PROFILE_ID = "private_owner"

# Field-journal / dashboard data sources (/api/maez-state, /api/session-timeline, /journal)
SNAPSHOTS_DIR = '/home/rohit/maez/logs/snapshots'
MODEL_STATE_PATH = '/home/rohit/maez/config/model_state.json'
THUNDER_STATE_PATH = '/home/rohit/maez/config/thunder_state.json'
TRAINING_RUNS_DIR = '/home/rohit/maez/training/runs'
DAEMON_HEALTH_URL = 'http://127.0.0.1:11435/health'
# 2026-04-23 Commit 6: removed stale 'llama-server-vision' from the
# journal surface — no such service runs. Re-add when a multimodal
# endpoint is re-provisioned.
JOURNAL_SERVICES = (
    'maez',
    'maez-web',
    'llama-server',
    'maez-watchdog',
)
_SERVICE_STATE_CACHE = {}  # service_name -> (state, timestamp)
_SERVICE_STATE_TTL = 30.0  # seconds

try:
    with open(SOUL_PATH) as f:
        SOUL = f.read().strip()
except Exception:
    SOUL = "You are Maez."


def _utcnow_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_private_owner_bridge(user_record: dict | None) -> bool:
    return bool(user_record and user_record.get("private_owner_bridge"))


def _parse_owner_exchange(content: str, timestamp: str) -> list[dict]:
    text = (content or "").strip()
    if not text:
        return []

    user_prefix = "the owner asked:"
    reply_prefix = "\nMaez replied:"
    if text.startswith(user_prefix) and reply_prefix in text:
        user_text, reply_text = text[len(user_prefix):].split(reply_prefix, 1)
        messages = []
        if user_text.strip():
            messages.append({
                "role": "user",
                "content": user_text.strip(),
                "timestamp": timestamp,
            })
        if reply_text.strip():
            messages.append({
                "role": "assistant",
                "content": reply_text.strip(),
                "timestamp": timestamp,
            })
        return messages

    return [{
        "role": "assistant",
        "content": text,
        "timestamp": timestamp,
    }]


def _load_private_owner_history() -> list[dict]:
    messages = []
    try:
        for exchange in memory.get_telegram_exchanges(limit=400):
            meta = exchange.get("metadata", {}) or {}
            messages.extend(_parse_owner_exchange(
                exchange.get("content", ""),
                meta.get("timestamp", ""),
            ))
    except Exception as e:
        logger.debug("Private owner history unavailable: %s", e)
    return messages


def _planner_seed():
    now = _utcnow_iso()
    return {
        "updated_at": now,
        "items": [
            {
                "id": "core-heartbeat",
                "title": "Persistent reasoning loop and memory spine",
                "status": "done",
                "visibility": "public",
                "summary": "The always-on daemon, three-tier memory, and local Gemma runtime are live and continuously growing.",
                "details": "Maez runs as a service, thinks every 30 seconds, stores observations, and never resets to zero.",
                "private_notes": "",
                "tags": ["core", "memory"],
                "updated_at": now,
            },
            {
                "id": "public-web",
                "title": "Public web surface redesign",
                "status": "done",
                "visibility": "public",
                "summary": "Landing, login, app, progress, and dashboard now share a clearer, more human public experience built around continuity instead of generic AI-tool language.",
                "details": "The public site now leads with presence, continuity, and user understanding first, while keeping the existing auth flows, analytics hooks, and live status behavior intact.",
                "private_notes": "",
                "tags": ["web", "design", "ux"],
                "updated_at": now,
            },
            {
                "id": "architecture-page",
                "title": "Dashboard and progress proof layers",
                "status": "done",
                "visibility": "public",
                "summary": "The dashboard now reads as the technical proof layer, while progress explains how much of the idea has already become real.",
                "details": "This keeps the architecture map separate from the build-status story so first-time visitors can understand the concept before they go technical.",
                "private_notes": "",
                "tags": ["dashboard", "ux", "progress"],
                "updated_at": now,
            },
            {
                "id": "funnel-clarity",
                "title": "Whole-funnel UX clarification",
                "status": "done",
                "visibility": "public",
                "summary": "The public funnel now explains Maez in one consistent order: what it is, how it begins, how it keeps living, and why that matters.",
                "details": "Landing, login, app, progress, and dashboard now reuse the same thesis and proof ideas instead of reframing Maez differently on each page.",
                "private_notes": "",
                "tags": ["website", "messaging", "ux"],
                "updated_at": now,
            },
            {
                "id": "observation-window",
                "title": "Live observation window",
                "status": "in_progress",
                "visibility": "public",
                "summary": "Self-improvement is being observed carefully so Maez learns from live behavior before more autonomy is granted.",
                "details": "One proposal at a time. Slow observation over synthetic confidence.",
                "private_notes": "",
                "tags": ["safety", "evaluation"],
                "updated_at": now,
            },
            {
                "id": "fastlane-validation",
                "title": "Fast-lane traffic validation",
                "status": "in_progress",
                "visibility": "public",
                "summary": "The fast reply lane exists in staging and still needs real-world validation before broader rollout.",
                "details": "The routing, redaction, audit, and policy layers are built; traffic confidence is what remains.",
                "private_notes": "",
                "tags": ["fast-lane", "staging"],
                "updated_at": now,
            },
            {
                "id": "planner-split",
                "title": "Public progress board and private planner",
                "status": "done",
                "visibility": "public",
                "summary": "Public progress and private planning now run as separate surfaces over one shared board model, with hidden notes staying private by default.",
                "details": "Public visitors read `/progress`; authenticated editing stays in `/planner`; the same data model feeds both views without exposing private scratch work.",
                "private_notes": "Keep private scratch ideas out of the public board by default.",
                "tags": ["planner", "website"],
                "updated_at": now,
            },
            {
                "id": "vagueness-fix",
                "title": "Ship VAGUENESS_DETECTION routing fix",
                "status": "next",
                "visibility": "public",
                "summary": "Separate vague failures from repetition/fixation so self-diagnosis can route to the right corrective action.",
                "details": "This is the next high-leverage system fix from the observation window.",
                "private_notes": "",
                "tags": ["cognition", "next"],
                "updated_at": now,
            },
            {
                "id": "desktop-wrapper",
                "title": "the owner desktop wrapper",
                "status": "next",
                "visibility": "public",
                "summary": "A closer daily wrapper around Maez is next once the current web and fast-lane surfaces settle.",
                "details": "This will likely become the most natural high-trust surface.",
                "private_notes": "",
                "tags": ["desktop", "product"],
                "updated_at": now,
            },
            {
                "id": "publishing-agent",
                "title": "Publishing agent",
                "status": "planned",
                "visibility": "public",
                "summary": "A supervised publishing flow for public updates is planned after the current communication surfaces stabilize.",
                "details": "This comes after the planner, desktop, and fast-lane validation work is mature.",
                "private_notes": "",
                "tags": ["publishing", "planned"],
                "updated_at": now,
            },
            {
                "id": "voice-return",
                "title": "Voice pipeline revival",
                "status": "planned",
                "visibility": "public",
                "summary": "Voice returns later, once the infrastructure path is stable enough to justify reviving it properly.",
                "details": "Useful, but not ahead of the current system and UX priorities.",
                "private_notes": "",
                "tags": ["voice", "planned"],
                "updated_at": now,
            },
            {
                "id": "private-elderly",
                "title": "Elder deployment notes",
                "status": "planned",
                "visibility": "private",
                "summary": "Private scratch area for mission-aligned deployment ideas.",
                "details": "",
                "private_notes": "Think through onboarding, trust, pacing, screen simplicity, and non-technical caregiver roles.",
                "tags": ["private", "mission"],
                "updated_at": now,
            },
        ],
    }


def _normalize_tags(raw_tags):
    if isinstance(raw_tags, str):
        raw_tags = [t.strip() for t in raw_tags.split(",")]
    if not isinstance(raw_tags, list):
        return []
    tags = []
    for tag in raw_tags:
        text = str(tag).strip().lower()
        if not text:
            continue
        if len(text) > 24:
            text = text[:24]
        if text not in tags:
            tags.append(text)
        if len(tags) >= 5:
            break
    return tags


def _normalize_planner_item(item):
    if not isinstance(item, dict):
        return None
    title = str(item.get("title", "")).strip()
    if not title:
        return None
    status = str(item.get("status", "planned")).strip()
    if status not in PLANNER_STATUSES:
        status = "planned"
    visibility = str(item.get("visibility", "public")).strip()
    if visibility not in PLANNER_VISIBILITIES:
        visibility = "public"
    return {
        "id": str(item.get("id", "")).strip() or f"planner-{uuid4().hex[:10]}",
        "title": title[:140],
        "status": status,
        "visibility": visibility,
        "summary": str(item.get("summary", "")).strip()[:420],
        "details": str(item.get("details", "")).strip()[:1200],
        "private_notes": str(item.get("private_notes", "")).strip()[:5000],
        "tags": _normalize_tags(item.get("tags", [])),
        "updated_at": str(item.get("updated_at", "")).strip() or _utcnow_iso(),
    }


def _normalize_planner_board(board):
    raw_items = board.get("items", []) if isinstance(board, dict) else []
    seen = set()
    items = []
    for raw in raw_items:
        item = _normalize_planner_item(raw)
        if not item:
            continue
        if item["id"] in seen:
            item["id"] = f"planner-{uuid4().hex[:10]}"
        seen.add(item["id"])
        items.append(item)
    return {
        "updated_at": _utcnow_iso(),
        "items": items,
    }


def _save_planner_board_locked(board):
    os.makedirs(os.path.dirname(PLANNER_PATH), exist_ok=True)
    tmp_path = PLANNER_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(board, f, indent=2)
    os.replace(tmp_path, PLANNER_PATH)


def _load_planner_board():
    with PLANNER_LOCK:
        if not os.path.exists(PLANNER_PATH):
            board = _planner_seed()
            _save_planner_board_locked(board)
            return board
        try:
            with open(PLANNER_PATH) as f:
                data = json.load(f)
        except Exception:
            board = _planner_seed()
            _save_planner_board_locked(board)
            return board
        board = _normalize_planner_board(data)
        if board != data:
            _save_planner_board_locked(board)
        return board


def _save_planner_board(board):
    with PLANNER_LOCK:
        normalized = _normalize_planner_board(board)
        _save_planner_board_locked(normalized)
        return normalized


def _planner_public_view(board):
    columns = {status: [] for status in PLANNER_STATUSES}
    for item in board.get("items", []):
        if item.get("visibility") != "public":
            continue
        columns[item["status"]].append({
            "id": item["id"],
            "title": item["title"],
            "status": item["status"],
            "summary": item["summary"],
            "details": item["details"],
            "tags": item["tags"],
            "updated_at": item["updated_at"],
        })
    return {
        "updated_at": board.get("updated_at", _utcnow_iso()),
        "counts": {status: len(columns[status]) for status in PLANNER_STATUSES},
        "columns": columns,
    }


def _planner_counts(board):
    counts = {status: 0 for status in PLANNER_STATUSES}
    for item in board.get("items", []):
        status = item.get("status", "planned")
        if status not in counts:
            status = "planned"
        counts[status] += 1
    return counts


def _clean_text(value, limit):
    return str(value or "").strip()[:limit]


def _normalize_public_path(value):
    raw = _clean_text(value, 180)
    if not raw:
        return "/"
    parsed = urlparse(raw)
    path = parsed.path or raw
    path = path.split("?", 1)[0].split("#", 1)[0].strip()
    if not path.startswith("/"):
        path = "/" + path.lstrip("/")
    return path or "/"


def _normalize_tracking_id(value, prefix):
    raw = _clean_text(value, 80).lower()
    cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in "-_")
    return cleaned[:64] or f"{prefix}-{uuid4().hex[:12]}"


def _normalize_tracking_target(value):
    raw = _clean_text(value, 200)
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return f"{parsed.scheme}://{host}{parsed.path or '/'}"[:200]
    return _normalize_public_path(raw)


def _analytics_referrer_host(value):
    raw = _clean_text(value, 240)
    if not raw:
        return "direct"
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return "direct"
    if host.endswith("maez.live"):
        return "internal"
    return host[:120]


def _analytics_device_from_request():
    ua = request.headers.get("User-Agent", "").lower()
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    if "mobi" in ua or "iphone" in ua or "android" in ua:
        return "mobile"
    if not ua:
        return "unknown"
    return "desktop"


def _append_analytics_event(event):
    with ANALYTICS_LOCK:
        os.makedirs(os.path.dirname(ANALYTICS_PATH), exist_ok=True)
        with open(ANALYTICS_PATH, "a") as f:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")


def _load_analytics_events():
    with ANALYTICS_LOCK:
        if not os.path.exists(ANALYTICS_PATH):
            return []
        events = []
        try:
            with open(ANALYTICS_PATH) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(event, dict):
                        continue
                    if event.get("event") not in ANALYTICS_EVENT_TYPES:
                        continue
                    path = _normalize_public_path(event.get("path", "/"))
                    if path.startswith("/api/"):
                        continue
                    events.append({
                        "ts": _clean_text(event.get("ts", ""), 40),
                        "event": event.get("event"),
                        "path": path,
                        "label": _clean_text(event.get("label", ""), 80),
                        "target": _clean_text(event.get("target", ""), 200),
                        "referrer": _clean_text(event.get("referrer", "direct"), 120) or "direct",
                        "device": _clean_text(event.get("device", "unknown"), 20) or "unknown",
                        "anon_id": _clean_text(event.get("anon_id", ""), 64),
                        "session_id": _clean_text(event.get("session_id", ""), 64),
                    })
        except Exception:
            return []
        return events


def _build_analytics_summary(events):
    now = datetime.now(timezone.utc)
    start_day = now.date() - timedelta(days=13)
    daily = []
    daily_uniques = defaultdict(set)
    daily_index = {}
    for i in range(14):
        day = start_day + timedelta(days=i)
        key = day.isoformat()
        entry = {"date": key, "pageviews": 0, "unique_visitors": 0}
        daily_index[key] = entry
        daily.append(entry)

    last_7_cutoff = now - timedelta(days=7)
    last_24_cutoff = now - timedelta(days=1)

    page_counts = Counter()
    referrer_counts = Counter()
    device_counts = Counter()
    cta_counts = Counter()
    funnel_counts = Counter()
    unique_all = set()
    unique_7d = set()
    pageviews_total = 0
    pageviews_7d = 0
    pageviews_24h = 0
    cta_total = 0
    recent = []
    funnel_map = dict(ANALYTICS_FUNNEL)

    for event in events:
        ts_text = event.get("ts", "")
        try:
            ts = datetime.fromisoformat(ts_text) if ts_text else None
        except Exception:
            ts = None

        recent.append(event)

        if event["event"] == "pageview":
            pageviews_total += 1
            path = event.get("path", "/")
            anon_id = event.get("anon_id", "")
            page_counts[path] += 1
            referrer_counts[event.get("referrer", "direct") or "direct"] += 1
            device_counts[event.get("device", "unknown") or "unknown"] += 1
            if path in funnel_map:
                funnel_counts[path] += 1
            if anon_id:
                unique_all.add(anon_id)
            if ts:
                if ts >= last_7_cutoff:
                    pageviews_7d += 1
                    if anon_id:
                        unique_7d.add(anon_id)
                if ts >= last_24_cutoff:
                    pageviews_24h += 1
                day_key = ts.date().isoformat()
                if day_key in daily_index:
                    daily_index[day_key]["pageviews"] += 1
                    if anon_id:
                        daily_uniques[day_key].add(anon_id)
        elif event["event"] == "cta_click":
            cta_total += 1
            cta_counts[(event.get("label", ""), event.get("path", "/"), event.get("target", ""))] += 1

    for day_key, anon_ids in daily_uniques.items():
        if day_key in daily_index:
            daily_index[day_key]["unique_visitors"] = len(anon_ids)

    top_pages = [
        {"path": path, "count": count}
        for path, count in page_counts.most_common(8)
    ]
    top_referrers = [
        {"source": source, "count": count}
        for source, count in referrer_counts.most_common(8)
    ]
    devices = [
        {"device": device, "count": count}
        for device, count in device_counts.most_common()
    ]
    ctas = [
        {"label": label or "Unnamed CTA", "path": path, "target": target, "count": count}
        for (label, path, target), count in cta_counts.most_common(10)
    ]
    funnel = [
        {"path": path, "label": label, "count": funnel_counts.get(path, 0)}
        for path, label in ANALYTICS_FUNNEL
    ]
    recent_events = []
    for event in sorted(recent, key=lambda item: item.get("ts", ""), reverse=True)[:20]:
        recent_events.append({
            "ts": event.get("ts", ""),
            "event": event.get("event", ""),
            "path": event.get("path", "/"),
            "label": event.get("label", ""),
            "target": event.get("target", ""),
            "referrer": event.get("referrer", "direct"),
            "device": event.get("device", "unknown"),
        })

    return {
        "updated_at": _utcnow_iso(),
        "totals": {
            "pageviews_total": pageviews_total,
            "unique_visitors_total": len(unique_all),
            "pageviews_7d": pageviews_7d,
            "unique_visitors_7d": len(unique_7d),
            "pageviews_24h": pageviews_24h,
            "cta_clicks_total": cta_total,
        },
        "daily": daily,
        "top_pages": top_pages,
        "top_referrers": top_referrers,
        "devices": devices,
        "ctas": ctas,
        "funnel": funnel,
        "recent": recent_events,
    }


def _request_token():
    return (
        request.args.get("web_token", "")
        or request.cookies.get(AUTH_COOKIE, "")
    ).strip()


def _attach_auth_cookie(response, token):
    if token:
        response.set_cookie(
            AUTH_COOKIE,
            token,
            max_age=60 * 60 * 24 * 180,
            path="/",
            samesite="Lax",
        )
    return response


@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


# ── field-journal helpers ────────────────────────────────────────────────

def _daemon_health(timeout=2.5):
    """Fetch the daemon's /health endpoint. Returns dict or {'status':'unreachable'}.

    Note: /health is slow (~1.7s per call) because it invokes
    `perception_snapshot()` which runs nvidia-smi + psutil. Default timeout
    is set above that ceiling. If this becomes a hot-path concern, split
    the daemon's /health into a fast status endpoint + a separate /stats
    endpoint; current callers are non-hot so not worth the daemon surgery.
    """
    try:
        with urllib.request.urlopen(DAEMON_HEALTH_URL, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        logger.debug("daemon health unreachable: %s", e)
        return {"status": "unreachable"}


def _service_state_cached(service_name, ttl=_SERVICE_STATE_TTL):
    """systemctl is-active <service>.service, cached per-service for ttl seconds."""
    now = time.time()
    cached = _SERVICE_STATE_CACHE.get(service_name)
    if cached and (now - cached[1]) < ttl:
        return cached[0]
    try:
        out = subprocess.check_output(
            ['systemctl', 'is-active', service_name + '.service'],
            timeout=2.0, stderr=subprocess.DEVNULL,
        ).decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        out = (e.output or b'').decode('utf-8').strip() or 'inactive'
    except Exception:
        out = 'unknown'
    _SERVICE_STATE_CACHE[service_name] = (out, now)
    return out


def _journal_services_state():
    return {svc.replace('-', '_'): _service_state_cached(svc) for svc in JOURNAL_SERVICES}


def _model_state():
    """Compose the model block from config/model_state.json + training/runs/current/summary.json."""
    data = {
        "base": "gemma-4-26B-A4B",
        "quant": "Q4_K_M",
        "runtime": "llama.cpp (CUDA)",
        "vision_model": "Qwen2.5-VL-3B",
        "merged_adapter": False,
    }
    try:
        with open(MODEL_STATE_PATH) as f:
            data.update(json.load(f))
    except Exception as e:
        logger.debug("model_state.json unreadable: %s", e)
    try:
        current_run = os.path.join(TRAINING_RUNS_DIR, 'current', 'summary.json')
        if os.path.exists(current_run):
            with open(current_run) as f:
                summary = json.load(f)
            data["adapter_pairs"] = summary.get("dataset_size")
            loss = summary.get("train_loss")
            if loss is not None:
                data["adapter_loss_final"] = round(float(loss), 4)
            data["adapter_base"] = summary.get("model")
            mtime = os.path.getmtime(current_run)
            data["adapter_trained"] = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
            data["merged_adapter"] = True
    except Exception as e:
        logger.debug("training summary unreadable: %s", e)
    return data


def _thunder_state():
    try:
        with open(THUNDER_STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _soul_state():
    try:
        st = os.stat(SOUL_PATH)
        with open(SOUL_PATH) as f:
            lines = sum(1 for _ in f)
        return {
            "lines": lines,
            "last_updated": datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d'),
        }
    except Exception:
        return {"lines": None, "last_updated": None}


# ── session snapshot parser ──────────────────────────────────────────────

_SNAPSHOT_SECTION_RE = re.compile(r'^=+\s*$')
_SNAPSHOT_HEADER_RE = re.compile(r'^([A-Z][A-Z ]+):\s*(.*)$')
_SNAPSHOT_BULLET_RE = re.compile(r'^\s*(?:[-*•]|\d+[.)])\s+(.*)$')


def _snapshot_slug(text):
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')


# Narrow, word-boundary de-gendering for historical snapshot text. The current
# rule for Maez is genderless; older snapshots (pre-2026-04-12) used "she/her".
# We don't rewrite the historical files — we de-gender at render time so the
# /journal timeline reads consistently with the rest of the site.
_DEGENDER_MAP = (
    (re.compile(r'\bShe\b'),      'It'),
    (re.compile(r'\bshe\b'),      'it'),
    (re.compile(r'\bHer\b'),      'Its'),
    (re.compile(r'\bher\b'),      'its'),
    (re.compile(r'\bhers\b'),     'its'),
    (re.compile(r'\bHerself\b'),  'Itself'),
    (re.compile(r'\bherself\b'),  'itself'),
)


def _degender(text):
    if not text:
        return text
    for rx, repl in _DEGENDER_MAP:
        text = rx.sub(repl, text)
    return text


def _degender_list(items):
    return [_degender(x) for x in items]


def _parse_session_snapshot(path):
    """Parse logs/snapshots/session_*.txt into a dict. Tolerant — errors become an 'error' field."""
    try:
        with open(path) as f:
            raw = f.read()
    except Exception as e:
        return {"file": os.path.basename(path), "error": f"read failed: {e}"}

    result = {
        "file": os.path.basename(path),
        "date": None,
        "label": None,
        "agent": None,
        "headline": None,
        "what_changed": [],
        "production_state": [],
        "next_priorities": [],
        "sections": {},
    }

    try:
        lines = raw.splitlines()
        i = 0
        # Header block (BUILD:, DATE:, AGENT: lines, before the first ==== divider)
        while i < len(lines) and not _SNAPSHOT_SECTION_RE.match(lines[i]):
            m = _SNAPSHOT_HEADER_RE.match(lines[i])
            if m:
                key, value = m.group(1).strip(), m.group(2).strip()
                if key == 'BUILD':
                    m2 = re.search(r'Sessions?\s+([\w+]+)', value)
                    if m2:
                        result["label"] = m2.group(1)
                elif key == 'DATE':
                    m2 = re.search(r'(\d{4}-\d{2}-\d{2})|([A-Za-z]+\s+\d+,\s*\d{4})', value)
                    if m2:
                        result["date"] = m2.group(0)
                        if ',' in result["date"]:
                            try:
                                result["date"] = datetime.strptime(result["date"], '%B %d, %Y').strftime('%Y-%m-%d')
                            except ValueError:
                                pass
                elif key == 'AGENT':
                    result["agent"] = value
            i += 1

        # Section blocks — the real format is:
        #   ========================================
        #   TITLE IN CAPS
        #   ========================================
        #
        #   body lines...
        #
        # i.e. each title is wrapped in a PAIR of ==== delimiters, not a single one.
        current_section = None
        body = []
        while i < len(lines):
            if _SNAPSHOT_SECTION_RE.match(lines[i]):
                # flush previous section
                if current_section and body:
                    result["sections"][current_section] = [b for b in body if b]
                    body = []
                i += 1
                # skip blank
                while i < len(lines) and not lines[i].strip():
                    i += 1
                # grab title
                if i < len(lines) and not _SNAPSHOT_SECTION_RE.match(lines[i]):
                    current_section = _snapshot_slug(lines[i].strip())
                    i += 1
                # skip blank(s) and the closing ==== delimiter that wraps the title
                while i < len(lines) and not lines[i].strip():
                    i += 1
                if i < len(lines) and _SNAPSHOT_SECTION_RE.match(lines[i]):
                    i += 1
                # read body until the NEXT opening ==== delimiter
                while i < len(lines) and not _SNAPSHOT_SECTION_RE.match(lines[i]):
                    stripped = lines[i].rstrip()
                    if stripped:
                        m = _SNAPSHOT_BULLET_RE.match(stripped)
                        body.append(m.group(1) if m else stripped.strip())
                    i += 1
                continue
            i += 1
        if current_section and body:
            result["sections"][current_section] = [b for b in body if b]

        # Headline pulled from THE HEADLINE / TL;DR / SUMMARY section if present
        for key in ('the_headline', 'headline', 'the_tl_dr', 'tl_dr', 'summary'):
            if key in result["sections"] and result["sections"][key]:
                result["headline"] = result["sections"][key][0]
                break

        result["what_changed"] = result["sections"].get("what_changed_today", [])[:24]
        result["production_state"] = result["sections"].get("production_state", [])[:24]
        result["next_priorities"] = result["sections"].get("next_session_priorities", [])[:12]

        # De-gender all visitor-facing text (historical snapshots used she/her).
        result["headline"] = _degender(result["headline"])
        result["what_changed"] = _degender_list(result["what_changed"])
        result["production_state"] = _degender_list(result["production_state"])
        result["next_priorities"] = _degender_list(result["next_priorities"])
    except Exception as e:
        result["error"] = f"parse failed: {e}"

    return result


@app.route("/")
def index():
    return send_file(os.path.join(UI_DIR, "index.html"), mimetype="text/html")


@app.route("/app")
def app_shell():
    if request.args.get("test_t", "").strip():
        return send_file(os.path.join(UI_DIR, "app.html"), mimetype="text/html")
    token = _request_token()
    if not token or not accounts.get_by_token(token):
        return redirect("/login")
    return send_file(os.path.join(UI_DIR, "app.html"), mimetype="text/html")


@app.route("/progress")
def progress_page():
    return send_file(PROGRESS_PUBLIC_PAGE, mimetype="text/html")


@app.route("/privacy")
def privacy_page():
    return send_file(os.path.join(UI_DIR, "privacy.html"), mimetype="text/html")


@app.route("/planner")
def planner_page():
    if request.args.get("test_t", "").strip():
        return send_file(PROGRESS_LOCAL_PAGE, mimetype="text/html")
    token = _request_token()
    if not token or not accounts.get_by_token(token):
        return redirect("/login")
    return send_file(PROGRESS_LOCAL_PAGE, mimetype="text/html")


@app.route("/analytics")
def analytics_page():
    if request.args.get("test_t", "").strip():
        return send_file(ANALYTICS_PAGE, mimetype="text/html")
    token = _request_token()
    if not token or not accounts.get_by_token(token):
        return redirect("/login")
    return send_file(ANALYTICS_PAGE, mimetype="text/html")


@app.route("/maez_analytics.js")
def analytics_script():
    return send_file(ANALYTICS_SCRIPT, mimetype="application/javascript")


@app.route("/maez.css")
def shared_stylesheet():
    """Shared design system — warm palette, Fraunces+Newsreader+JetBrains Mono."""
    return send_file(os.path.join(UI_DIR, "maez.css"), mimetype="text/css")


@app.route("/maez_hero.html")
def hero_page():
    return send_file(HERO_PAGE, mimetype="text/html")


@app.route("/maez_gate.html")
def gate_page():
    return send_file(GATE_PAGE, mimetype="text/html")


@app.route("/maez_bg.html")
def bg_page():
    return send_file(os.path.join(UI_DIR, "maez_bg.html"), mimetype="text/html")


# ══════════════════════════════════════════════════════════════════════
# Cockpit — the Claude-Design-sourced WebUI prototype with two
# directions (Apple Intelligence + Inner Life) and 11 surfaces each.
# See /home/rohit/maez/web/cockpit/ for the source files.
# Currently runs on the prototype's fake sim (sim.jsx); real-backend
# wiring lands in follow-up work.
# ══════════════════════════════════════════════════════════════════════

COCKPIT_DIR = "/home/rohit/maez/web/cockpit"


@app.route("/cockpit")
@app.route("/cockpit/")
def cockpit_index():
    return send_from_directory(COCKPIT_DIR, "index.html")


@app.route("/cockpit/<path:filename>")
def cockpit_static(filename: str):
    # .jsx served as application/javascript so Babel-in-browser can
    # parse them; other common types default-handled by Flask.
    if filename.endswith(".jsx"):
        return send_from_directory(
            COCKPIT_DIR, filename, mimetype="application/javascript"
        )
    return send_from_directory(COCKPIT_DIR, filename)


# ── Cockpit live-data API ────────────────────────────────────────────
# Read-only endpoints the cockpit's sim.jsx polls to replace fake
# daemon/cards data with real state. Write endpoints limited to
# card deny — approve requires the decision_pipeline's execution
# path which lives in the daemon process, not here, so the cockpit
# punts approve back to Telegram for now.

_MAEZ_LOG_PATH = "/home/rohit/maez/logs/maez.log"
_COGNITION_LOG_PATH = "/home/rohit/maez/logs/cognition.log"
_PENDING_CARDS_DB = "/home/rohit/maez/memory/pending_cards.db"


def _tail_log_lines(path: str, n: int = 200) -> list:
    """Return last n lines of a log file. Empty list on failure."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            chunk = min(size, n * 512)
            f.seek(size - chunk)
            data = f.read().decode("utf-8", errors="replace")
        return data.splitlines()[-n:]
    except Exception:
        return []


@app.route("/api/v1/daemon/state")
def api_daemon_state():
    """Snapshot of daemon state, reconstructed from log tail + SQLite
    queries. Best-effort — fields default when a source is unreachable."""
    import re as _re
    import time as _time
    lines = _tail_log_lines(_MAEZ_LOG_PATH, 400)
    cycle = None
    last_cycle_ts = None
    mood = "attentive"
    currentThought = ""
    scratchpad = []
    score = None
    # Scan from end for the most recent "Cycle N response:"
    for i in range(len(lines) - 1, -1, -1):
        m = _re.search(r"\bCycle (\d+) response:", lines[i])
        if m:
            cycle = int(m.group(1))
            tsm = _re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", lines[i])
            if tsm:
                last_cycle_ts = tsm.group(1)
            # Next non-empty line(s) are the response body
            body_lines = []
            j = i + 1
            while j < len(lines) and len(body_lines) < 3:
                bl = lines[j].strip()
                if bl and not _re.search(
                    r"^\d{4}-\d{2}-\d{2}.*\[INFO\]", bl
                ):
                    body_lines.append(bl[:200])
                j += 1
                if _re.search(
                    r"^\d{4}-\d{2}-\d{2}.*\[INFO\] cycle \| score=", lines[j - 1]
                ) if j - 1 < len(lines) else False:
                    break
            currentThought = " ".join(body_lines)[:500]
            break
    # Score: most recent "cycle | score=NN"
    for ln in reversed(lines):
        m = _re.search(r"cycle \| score=(\d+)", ln)
        if m:
            score = int(m.group(1)) / 100.0
            break
    # Scratchpad: last 4 cycle bodies (shorter scan)
    scratch_count = 0
    for i in range(len(lines) - 1, -1, -1):
        m = _re.search(r"\bCycle (\d+) response:", lines[i])
        if m and scratch_count < 4:
            tsm = _re.match(r"(\d{2}:\d{2}:\d{2})", lines[i][11:19]) \
                  if len(lines[i]) > 19 else None
            t = lines[i][11:19] if len(lines[i]) > 19 else ""
            body = ""
            if i + 1 < len(lines):
                body = lines[i + 1].strip()[:160]
            scratchpad.append({"t": t, "text": body})
            scratch_count += 1
    # Open card count (useful for badges)
    open_cards = 0
    try:
        import sqlite3 as _sq
        conn = _sq.connect(_PENDING_CARDS_DB, timeout=1.5)
        row = conn.execute(
            "SELECT COUNT(*) FROM pending_cards WHERE status IN (?, ?)",
            ("open", "deferred"),
        ).fetchone()
        open_cards = int(row[0]) if row else 0
        conn.close()
    except Exception:
        pass
    return jsonify({
        "cycle": cycle or 0,
        "lastTick": last_cycle_ts or "",
        "nextTickIn": 30,  # loose — daemon uses ~30s cycles
        "score": score if score is not None else 0.0,
        "mood": mood,
        "currentThought": currentThought,
        "scratchpad": scratchpad,
        "openCards": open_cards,
        "sampledAt": int(_time.time()),
    })


@app.route("/api/v1/cards")
def api_cards_list():
    """Recent pending cards — all non-terminal + last 24h terminal
    so the cockpit can show context on what just got resolved."""
    import sqlite3 as _sq
    import time as _time
    since = _time.time() - 86400
    try:
        conn = _sq.connect(_PENDING_CARDS_DB, timeout=2.0)
        conn.row_factory = _sq.Row
        rows = conn.execute(
            "SELECT request_id, action, status, created_at, resolved_at, "
            "resolved_via, params_json, reason, plain_english "
            "FROM pending_cards "
            "WHERE status IN ('open', 'deferred') OR created_at > ? "
            "ORDER BY created_at DESC LIMIT 30",
            (since,),
        ).fetchall()
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e), "cards": []}), 500
    import json as _json
    cards = []
    for r in rows:
        params = {}
        try:
            params = _json.loads(r["params_json"] or "{}")
        except Exception:
            pass
        cards.append({
            "id": r["request_id"],
            "action": r["action"],
            "status": r["status"],
            "cmd": params.get("cmd") or params.get("path") or "",
            "reason": (r["plain_english"] or r["reason"]
                       or params.get("reason", "")),
            "created_at": r["created_at"],
            "resolved_at": r["resolved_at"],
            "resolved_via": r["resolved_via"],
        })
    return jsonify({"cards": cards})


@app.route("/api/v1/cards/<request_id>/deny", methods=["POST"])
def api_card_deny(request_id: str):
    """Deny a card from the cockpit. Safe — no execution side effect,
    just marks it resolved so the UI (and the daemon's state) both
    see it as closed. Approve is intentionally NOT exposed here —
    the execution path lives in the daemon process, so cockpit-side
    approve would flip state but never run the command."""
    try:
        from core.pending_cards import PendingCardStore
        store = PendingCardStore(_PENDING_CARDS_DB)
        card = store.deny(
            request_id,
            user_id="rohit",
            via="cockpit",
            notes="denied from cockpit UI",
        )
        return jsonify({"ok": True, "status": card.status})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/v1/services")
def api_services():
    """systemctl status for maez/llama/ollama units."""
    import subprocess as _sp
    out = {}
    try:
        r = _sp.run(
            ["systemctl", "list-units", "--type=service", "--all",
             "--no-pager", "--no-legend", "maez*", "llama*", "ollama*"],
            capture_output=True, text=True, timeout=3.0, check=False,
        )
        for line in (r.stdout or "").splitlines():
            toks = line.strip().split(None, 4)
            if len(toks) < 4 or not toks[0].endswith(".service"):
                continue
            name = toks[0][:-len(".service")]
            out[name] = {
                "status": toks[2],
                "sub": toks[3] if len(toks) > 3 else "",
                "desc": toks[4] if len(toks) > 4 else "",
            }
    except Exception as e:
        return jsonify({"error": str(e), "services": {}}), 500
    return jsonify({"services": out})


@app.route("/api/v1/gpu")
def api_gpu():
    """nvidia-smi query for the primary GPU. Fails cleanly when no GPU."""
    import subprocess as _sp
    try:
        r = _sp.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,"
             "temperature.gpu,power.draw,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2.0, check=False,
        )
        line = (r.stdout or "").strip().splitlines()[0] if r.stdout else ""
        if not line:
            return jsonify({"error": "no gpu data"}), 404
        parts = [p.strip() for p in line.split(",")]
        vram_used_mb = float(parts[0])
        vram_total_mb = float(parts[1])
        return jsonify({
            "vramUsed": round(vram_used_mb / 1024, 1),
            "vramTotal": round(vram_total_mb / 1024, 1),
            "temp": int(float(parts[2])),
            "power": int(float(parts[3])),
            "util": int(float(parts[4])),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/signals")
def api_signals():
    """Best-effort recent ambient signals. Reads perception_cache.json
    (written by core.perception.snapshot each cycle) and surfaces
    the interesting fields as discrete signals. Iphone ingest is
    folded in if the json exists (it doesn't currently on this
    box — aspirational per the iphone_signals plan)."""
    import json as _json
    import os as _os
    sigs = []
    perception_path = "/home/rohit/maez/memory/perception_cache.json"
    if _os.path.exists(perception_path):
        try:
            with open(perception_path) as f:
                data = _json.load(f)
            if isinstance(data, dict):
                ts_val = str(data.get("timestamp", ""))[:19]
                short_t = ts_val[-8:] if len(ts_val) >= 8 else ts_val
                # CPU signal — always present
                cpu = data.get("cpu", {})
                if isinstance(cpu, dict) and "percent" in cpu:
                    sigs.append({
                        "t": short_t, "kind": "system",
                        "text": f"CPU {cpu.get('percent')}% across {cpu.get('core_count', '?')} cores",
                        "src": "psutil",
                    })
                ram = data.get("ram", {})
                if isinstance(ram, dict) and "percent" in ram:
                    sigs.append({
                        "t": short_t, "kind": "system",
                        "text": f"RAM {ram.get('percent')}% used ({ram.get('used_gb', '?')}G / {ram.get('total_gb', '?')}G)",
                        "src": "psutil",
                    })
                gpu = data.get("gpu")
                if isinstance(gpu, dict):
                    sigs.append({
                        "t": short_t, "kind": "system",
                        "text": (
                            f"GPU {gpu.get('utilization_pct', '?')}% · "
                            f"{gpu.get('memory_used_mb', 0)/1024:.1f}G / "
                            f"{gpu.get('memory_total_mb', 0)/1024:.1f}G · "
                            f"{gpu.get('temperature_c', '?')}°C"
                        ),
                        "src": "nvidia-smi",
                    })
                disk = data.get("disk", {})
                if isinstance(disk, dict):
                    for mount, info in disk.items():
                        if isinstance(info, dict) and "percent" in info:
                            kind = "disk" if info["percent"] < 85 else "disk_warn"
                            sigs.append({
                                "t": short_t, "kind": kind,
                                "text": (
                                    f"{mount} {info['percent']}% "
                                    f"({info.get('used_gb', '?')}G / {info.get('total_gb', '?')}G)"
                                ),
                                "src": "psutil",
                            })
                tops = data.get("top_processes_cpu") or []
                if tops:
                    top_names = ", ".join(
                        f"{p.get('name', '?')}({p.get('cpu_percent', 0):.0f}%)"
                        for p in tops[:3]
                    )
                    sigs.append({
                        "t": short_t, "kind": "processes",
                        "text": f"Top CPU: {top_names}",
                        "src": "psutil",
                    })
        except Exception as e:
            sigs.append({
                "t": "", "kind": "error",
                "text": f"perception_cache.json parse failed: {e}",
                "src": "system",
            })
    # iPhone ingest (aspirational — file doesn't exist on this box yet)
    iphone_path = "/home/rohit/maez/memory/iphone_signals.json"
    if _os.path.exists(iphone_path):
        try:
            with open(iphone_path) as f:
                data = _json.load(f)
            if isinstance(data, list):
                for ev in data[-4:]:
                    sigs.append({
                        "t": str(ev.get("time") or ev.get("ts") or "")[-8:],
                        "kind": "iphone",
                        "text": str(ev.get("text") or ev.get("summary")
                                    or str(ev))[:120],
                        "src": "iphone",
                    })
        except Exception:
            pass
    return jsonify({"signals": sigs[:10]})


@app.route("/api/v1/soul")
def api_soul():
    """Two-layer soul content."""
    import os as _os
    base_path = "/home/rohit/maez/config/soul.base.md"
    local_path = "/home/rohit/maez/config/soul.local.md"
    soul = {"base": "", "local": ""}
    for key, p in (("base", base_path), ("local", local_path)):
        try:
            if _os.path.exists(p):
                with open(p) as f:
                    soul[key] = f.read()
        except Exception:
            pass
    return jsonify(soul)


@app.route("/api/v1/memory")
def api_memory():
    """ChromaDB tier counts + visible samples from each memory tier."""
    import sqlite3 as _sq
    import os as _os
    stats = {"raw": 0, "daily": 0, "core": 0}
    for tier in stats:
        p = f"/home/rohit/maez/memory/db/{tier}/chroma.sqlite3"
        if not _os.path.exists(p):
            continue
        try:
            c = _sq.connect(p, timeout=1.5)
            row = c.execute(
                "SELECT COUNT(*) FROM embeddings"
            ).fetchone()
            stats[tier] = int(row[0]) if row else 0
            c.close()
        except Exception:
            pass
    hits = []
    try:
        from memory.memory_manager import MemoryManager
        mem = MemoryManager()
        for core in (mem.get_all_core() or [])[-8:]:
            content = (core.get("content") or "")[:320]
            meta = core.get("metadata") or {}
            ts_val = meta.get("timestamp", "")
            hits.append({
                "tier": "core",
                "score": 1.0,
                "date": str(ts_val)[:10],
                "text": content,
                "tokens": len(content) // 4,
                "source": meta.get("source", ""),
            })
        try:
            daily_results = mem.daily.get(include=["documents", "metadatas"])
        except Exception:
            daily_results = {"ids": [], "documents": [], "metadatas": []}
        daily_rows = []
        for i in range(len(daily_results.get("ids", []))):
            content = (daily_results["documents"][i] or "")[:320]
            meta = daily_results["metadatas"][i] or {}
            ts_val = meta.get("date") or meta.get("timestamp", "")
            daily_rows.append({
                "tier": "daily",
                "score": 0.8,
                "date": str(ts_val)[:10],
                "text": content,
                "tokens": len(content) // 4,
                "source": meta.get("source", "daily_consolidation"),
            })
        hits.extend(daily_rows[-8:])
        for ex in (mem.get_telegram_exchanges(limit=8) or [])[-5:]:
            content = (ex.get("content") or "")[:200]
            ts_val = (ex.get("metadata") or {}).get("timestamp", "")
            hits.append({
                "tier": "raw",
                "score": 0.5,
                "date": str(ts_val)[:10],
                "text": content,
                "tokens": len(content) // 4,
                "source": "telegram_exchange",
            })
    except Exception:
        pass
    return jsonify({"stats": stats, "hits": hits})


# ── Lived memory (ADR 0019) ─────────────────────────────────────────
# Cockpit-facing read-only view over the Phase-1 SQLite stores. The
# endpoint never asserts live state — it surfaces past episodes, open
# loops, and graph beliefs with evidence intact, and tells the panel
# nothing else.

_LIVED_EPISODE_DB_PATH = "/home/rohit/maez/memory/lived_episodes.db"
_LIVED_GRAPH_DB_PATH = "/home/rohit/maez/memory/lived_graph.db"


def _read_lived_episodes(db_path):
    import json as _json
    import os as _os
    import sqlite3 as _sq

    if not _os.path.exists(db_path):
        return []
    try:
        c = _sq.connect(db_path, timeout=1.5)
        c.row_factory = _sq.Row
        # rowid as secondary sort handles ties when two episodes land
        # in the same second; SQLite's rowid is monotonic in insertion
        # order so it matches "most recent first" semantically.
        rows = c.execute(
            "SELECT * FROM episodes WHERE status = 'active' "
            "ORDER BY created_at DESC, rowid DESC LIMIT 50"
        ).fetchall()
        c.close()
    except Exception:
        return []
    out = []
    for r in rows:
        d = dict(r)
        out.append(
            {
                "id": d.get("id"),
                "title": d.get("title"),
                "summary": d.get("summary"),
                "open_loop": d.get("open_loop"),
                "source_memory_ids": _json.loads(
                    d.get("source_memory_ids_json") or "[]"
                ),
                "source_kind": d.get("source_kind"),
                "emotional_tone": d.get("emotional_tone"),
                "importance": d.get("importance"),
                "status": d.get("status"),
                "created_at": d.get("created_at"),
                "occurred_at": d.get("occurred_at"),
                "participants": _json.loads(
                    d.get("participants_json") or "[]"
                ),
            }
        )
    return out


def _read_lived_edges(db_path):
    import json as _json
    import os as _os
    import sqlite3 as _sq

    if not _os.path.exists(db_path):
        return []
    try:
        c = _sq.connect(db_path, timeout=1.5)
        c.row_factory = _sq.Row
        rows = c.execute(
            "SELECT e.*, s.label AS subject_label, "
            "       s.kind AS subject_kind, "
            "       o.label AS object_label, "
            "       o.kind AS object_kind "
            "FROM edges e "
            "JOIN nodes s ON s.id = e.subject_id "
            "JOIN nodes o ON o.id = e.object_id "
            "WHERE e.status = 'active' "
            "ORDER BY e.created_at DESC LIMIT 50"
        ).fetchall()
        c.close()
    except Exception:
        return []
    out = []
    for r in rows:
        d = dict(r)
        out.append(
            {
                "id": d.get("id"),
                "subject_label": d.get("subject_label"),
                "subject_kind": d.get("subject_kind"),
                "relation": d.get("relation"),
                "object_label": d.get("object_label"),
                "object_kind": d.get("object_kind"),
                "confidence": d.get("confidence"),
                "status": d.get("status"),
                "valid_from": d.get("valid_from"),
                "valid_to": d.get("valid_to"),
                "source_episode_ids": _json.loads(
                    d.get("source_episode_ids_json") or "[]"
                ),
                "source_memory_ids": _json.loads(
                    d.get("source_memory_ids_json") or "[]"
                ),
                "created_at": d.get("created_at"),
            }
        )
    return out


@app.route("/api/v1/lived-memory")
def api_lived_memory():
    """Lived-memory layer (ADR 0019) — episodes + graph edges with
    evidence trails, for the cockpit's Living Memory panel.

    Returns empty lists (not 500) when the SQLite stores haven't been
    populated yet. Owner runs scripts/memory_reflection/
    nightly_lived_memory.py --apply to populate.
    """
    episodes = _read_lived_episodes(_LIVED_EPISODE_DB_PATH)
    edges = _read_lived_edges(_LIVED_GRAPH_DB_PATH)
    return jsonify(
        {
            "episodes": episodes,
            "edges": edges,
            "counts": {
                "episodes": len(episodes),
                "edges": len(edges),
            },
        }
    )


@app.route("/api/v1/dreams")
def api_dreams():
    """Merged view of evolution candidates + dream proposals."""
    import sqlite3 as _sq
    dreams = []
    evo_path = "/home/rohit/maez/memory/evolution_track.db"
    dream_path = "/home/rohit/maez/memory/dream_proposals.db"
    # Evolution candidates
    try:
        c = _sq.connect(evo_path, timeout=2.0)
        c.row_factory = _sq.Row
        rows = c.execute(
            "SELECT id, state, weakness_description, target_file, diff_text, "
            "created_at FROM candidates ORDER BY id DESC LIMIT 10"
        ).fetchall()
        c.close()
        for r in rows:
            state_map = {
                "validated": "pending", "applied": "approved",
                "rejected": "rejected", "rolled_back": "rejected",
            }
            dreams.append({
                "id": r["id"],
                "at": str(r["created_at"] or "")[11:16],
                "score": 0.75,
                "status": state_map.get(r["state"], "pending"),
                "title": (r["weakness_description"] or "")[:80],
                "rationale": f"targets {r['target_file']}",
                "diff": (r["diff_text"] or "")[:600],
                "source": "evolution",
            })
    except Exception:
        pass
    # Dream proposals
    try:
        c = _sq.connect(dream_path, timeout=2.0)
        c.row_factory = _sq.Row
        rows = c.execute(
            "SELECT id, status, insight, proposal_type, target_section, "
            "created_at, unified_diff FROM dream_proposals "
            "ORDER BY id DESC LIMIT 10"
        ).fetchall()
        c.close()
        for r in rows:
            dreams.append({
                "id": 10000 + r["id"],
                "at": str(r["created_at"] or "")[-8:-3] if r["created_at"] else "",
                "score": 0.65,
                "status": r["status"] or "pending",
                "title": (r["insight"] or "")[:80],
                "rationale": (r["insight"] or "")[:200],
                "diff": (r["unified_diff"] or "")[:600],
                "source": "dream",
            })
    except Exception:
        pass
    dreams.sort(key=lambda d: d.get("id", 0), reverse=True)
    return jsonify({"dreams": dreams[:15]})


@app.route("/api/v1/quality")
def api_quality():
    """Quality-signal rollup for the cockpit.

    Aggregates three cognition.log streams (self_claim_audit,
    error_classifier, consolidation_scores) plus two SQLite sidecars
    (fabrication_events, recall_stats) into a single JSON blob. All
    reads are best-effort — on any source failure the corresponding
    rollup section returns empty / zero rather than 500-ing the call.

    Query params:
        audit_lookback        — default 200
        error_lookback        — default 200
        consolidation_lookback — default 20
        fabrication_limit     — default 10
    """
    try:
        from core.quality_telemetry import build_rollup
    except Exception as e:
        return jsonify({"error": f"telemetry unavailable: {e}"}), 500

    def _int_arg(name: str, default: int) -> int:
        try:
            v = int(request.args.get(name, default))
            return max(1, min(v, 5000))  # clamp
        except Exception:
            return default

    try:
        rollup = build_rollup(
            audit_lookback=_int_arg("audit_lookback", 200),
            error_lookback=_int_arg("error_lookback", 200),
            consolidation_lookback=_int_arg("consolidation_lookback", 20),
            fabrication_limit=_int_arg("fabrication_limit", 10),
        )
        return jsonify(rollup.to_json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Workshop — in-cockpit coding session (Phase 1: chat only) ─────────

@app.route("/api/v1/workshop/sessions", methods=["GET"])
def api_workshop_list():
    try:
        from core.workshop import rollup
        return jsonify(rollup(limit_sessions=50))
    except Exception as e:
        return jsonify({"error": f"workshop list failed: {e}"}), 500


@app.route("/api/v1/workshop/sessions", methods=["POST"])
def api_workshop_create():
    try:
        body = request.get_json(silent=True) or {}
        title = (body.get("title") or "(untitled)").strip()[:200]
        model = (body.get("model") or "").strip() or None
        from core.workshop import create_session
        sid = create_session(
            title=title, model=model or "sonnet",
        )
        return jsonify({"id": sid, "title": title})
    except Exception as e:
        return jsonify({"error": f"workshop create failed: {e}"}), 500


@app.route("/api/v1/workshop/session/<session_id>", methods=["GET"])
def api_workshop_get(session_id: str):
    try:
        from core.workshop import get_session, get_turns
        s = get_session(session_id)
        if not s:
            return jsonify({"error": "session not found"}), 404
        turns = get_turns(session_id)
        return jsonify({
            "session": {
                "id": s.id, "title": s.title, "model": s.model,
                "created_at": s.created_at, "updated_at": s.updated_at,
            },
            "turns": [
                {
                    "id": t.id, "ts": t.ts, "role": t.role,
                    "content": t.content, "model_used": t.model_used,
                    "input_tokens": t.input_tokens,
                    "output_tokens": t.output_tokens,
                }
                for t in turns
            ],
        })
    except Exception as e:
        return jsonify({"error": f"workshop get failed: {e}"}), 500


@app.route("/api/v1/workshop/session/<session_id>/turn", methods=["POST"])
def api_workshop_turn(session_id: str):
    """Send a user message; returns the assistant reply (synchronous)."""
    try:
        body = request.get_json(silent=True) or {}
        user_message = (body.get("message") or "").strip()
        override_model = body.get("model") or None
        if not user_message:
            return jsonify({"error": "message required"}), 400
        from core.workshop import turn
        result = turn(
            session_id=session_id,
            user_message=user_message,
            override_model=override_model,
        )
        return jsonify(result)
    except RuntimeError as e:
        # tier / session errors — 502 since the proxy / DB is the
        # thing that failed, not the caller's request shape.
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        return jsonify({"error": f"workshop turn failed: {e}"}), 500


@app.route("/api/v1/workshop/session/<session_id>/model", methods=["POST"])
def api_workshop_update_model(session_id: str):
    """Change the session's default model mid-session.

    Body: {"model": "sonnet"|"opus"|"gpt-4o"|"openai/gpt-4o"|...}

    The proxy's adapter registry decides which backend serves the
    new model. Past turns are NOT retroactively re-routed — their
    model_used column records what actually handled them.
    """
    try:
        body = request.get_json(silent=True) or {}
        model = (body.get("model") or "").strip()
        if not model:
            return jsonify({"error": "model required"}), 400
        from core.workshop import update_session_model
        ok = update_session_model(session_id, model)
        if not ok:
            return jsonify({"error": "session not found or update failed"}), 404
        return jsonify({"id": session_id, "model": model})
    except Exception as e:
        return jsonify({"error": f"update model failed: {e}"}), 500


@app.route("/api/v1/workshop/session/<session_id>/apply", methods=["POST"])
def api_workshop_apply(session_id: str):
    """Apply a unified-diff block to a file in the repo.

    Body: {"diff": "<unified diff text>"}
    Returns: {applied, target, backup, stdout, stderr, error?}

    Same privilege boundary as the rest of /api/v1/workshop — 127.0.0.1
    only, no auth layer. Destructive: writes to disk. Reversible via
    the returned backup path. The UI should confirm before firing.
    """
    try:
        body = request.get_json(silent=True) or {}
        diff_text = (body.get("diff") or "").strip()
        if not diff_text:
            return jsonify({"error": "diff required"}), 400
        from core.workshop import apply_diff
        result = apply_diff(session_id=session_id, diff_text=diff_text)
        status = 200 if result.get("applied") else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({"error": f"apply failed: {e}"}), 500


@app.route("/api/v1/workshop/session/<session_id>", methods=["DELETE"])
def api_workshop_delete(session_id: str):
    try:
        from core.workshop import delete_session
        ok = delete_session(session_id)
        if not ok:
            return jsonify({"error": "session not found"}), 404
        return jsonify({"id": session_id, "deleted": True})
    except Exception as e:
        return jsonify({"error": f"workshop delete failed: {e}"}), 500


@app.route("/api/v1/self_dev/concern/<int:concern_id>/resolve", methods=["POST"])
def api_self_dev_resolve(concern_id: int):
    """Transition a concern to a new status.

    Body: {"state": "resolved" | "wont_fix" | "rejected" | "open",
           "notes": "optional explanation"}

    Same privilege boundary as the CLI `python -m core.self_dev
    resolve` — anyone on 127.0.0.1 can call, no auth layer.
    Reversible: setting state='open' clears resolved_at and
    resolution_notes, so a mistakenly-resolved concern can be
    reopened cleanly from the same UI.
    """
    try:
        body = request.get_json(silent=True) or {}
        state = (body.get("state") or "").strip().lower()
        notes = body.get("notes") or None
        if state not in ("open", "resolved", "wont_fix", "rejected"):
            return jsonify({
                "error": f"state must be one of open/resolved/wont_fix/rejected; got {state!r}"
            }), 400
        from core.self_dev_persistence import set_concern_status
        ok = set_concern_status(concern_id, state, notes=notes)
        if not ok:
            return jsonify({
                "error": f"concern #{concern_id} not found or DB write failed"
            }), 404
        return jsonify({
            "id": concern_id, "state": state, "notes": notes,
        })
    except Exception as e:
        return jsonify({"error": f"resolve failed: {e}"}), 500


@app.route("/api/v1/self_dev")
def api_self_dev():
    """Self-dev rollup — reviews + concerns for the cockpit.

    Combines:
      - stats (total reviews, token usage, severity/status buckets)
      - recent reviews (headers only, no concern bodies)
      - open concerns (ids + file:line + severity + text + suggestion)

    All reads are best-effort; individual fields fall back to empty
    rather than 500-ing the response.

    Query params:
        recent_reviews  — default 10   (max 100)
        recent_concerns — default 25   (max 200)
        window_hours    — default 168  (7 days)
    """
    try:
        from core.self_dev_persistence import rollup
    except Exception as e:
        return jsonify({"error": f"self_dev unavailable: {e}"}), 500

    def _int_arg(name: str, default: int, hi: int) -> int:
        try:
            v = int(request.args.get(name, default))
            return max(1, min(v, hi))
        except Exception:
            return default

    try:
        data = rollup(
            recent_reviews=_int_arg("recent_reviews", 10, 100),
            recent_concerns=_int_arg("recent_concerns", 25, 200),
            window_hours=_int_arg("window_hours", 168, 10000),
        )
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"self_dev rollup failed: {e}"}), 500


def _build_machine_info(_os_mod) -> dict:
    """Machine info dict for the /api/v1/identity endpoint.

    Phase 2.D: previously hardcoded \"rtx 4090 (24gb)\". Now reads the
    machine_profile string from identity.yaml (optional), falling back
    to the host's os/release which is always available.
    """
    profile = ""
    try:
        from core import identity as _identity_mod
        profile = _identity_mod.machine_profile() or ""
    except Exception:
        pass
    return {
        "host": _os_mod.uname().nodename,
        "os": f"{_os_mod.uname().sysname} {_os_mod.uname().release}",
        "gpu": "",
        "cpu": "",
        "profile": profile,
    }


def _default_owner_name() -> str:
    try:
        from core import identity as _identity_mod
        return _identity_mod.display_name() or "owner"
    except Exception:
        return "owner"


@app.route("/api/v1/identity")
def api_identity():
    """Owner / machine / covenant / reddit subs."""
    import os as _os
    identity = {
        "owner": {
            "name": _default_owner_name(), "pronouns": "",
            "city": "", "lat": None, "lon": None,
        },
        "machine": _build_machine_info(_os),
        "policies": {
            "jarvis_tier": "liberal",
            "allowClaude": True,
            "allowShell": True,
            "allowSelfModify": "propose-only",
        },
        "redditSubs": [],
    }
    # Read identity.yaml if present
    try:
        from core.paths import identity_file as _identity_file
        id_path = str(_identity_file())
    except Exception:
        id_path = "/home/rohit/maez/config/identity.yaml"
    if _os.path.exists(id_path):
        try:
            import yaml as _yaml
            with open(id_path) as f:
                y = _yaml.safe_load(f) or {}
            if isinstance(y, dict):
                for k in ("owner", "machine", "policies"):
                    if k in y and isinstance(y[k], dict):
                        identity[k].update(y[k])
                if "redditSubs" in y:
                    identity["redditSubs"] = list(y["redditSubs"])
        except Exception:
            pass
    # Reddit subs fallback
    if not identity["redditSubs"]:
        identity["redditSubs"] = [
            "LocalLLaMA", "MachineLearning", "selfhosted",
        ]
    return jsonify(identity)


@app.route("/api/v1/router")
def api_router():
    """Router totals + recent decisions via Langfuse if creds present."""
    import os as _os
    totals = {"local": 0, "claude": 0, "bytesIn": 0, "bytesOut": 0, "costUsd": 0.0}
    window = []
    if (_os.environ.get("LANGFUSE_PUBLIC_KEY")
            and _os.environ.get("LANGFUSE_SECRET_KEY")):
        try:
            from langfuse import Langfuse
            client = Langfuse(
                public_key=_os.environ["LANGFUSE_PUBLIC_KEY"],
                secret_key=_os.environ["LANGFUSE_SECRET_KEY"],
                host=(_os.environ.get("LANGFUSE_HOST")
                      or _os.environ.get("LANGFUSE_BASE_URL")
                      or "https://cloud.langfuse.com"),
            )
            # Langfuse v4 — fetch recent traces, summarize by model.
            traces = client.api.trace.list(limit=50) if hasattr(
                client, "api") else None
            if traces:
                items = getattr(traces, "data", [])
                for t in items[:15]:
                    name = getattr(t, "name", "") or ""
                    meta = getattr(t, "metadata", {}) or {}
                    model = (meta or {}).get("model", "") or ""
                    is_claude = "claude" in model.lower()
                    if is_claude:
                        totals["claude"] += 1
                    else:
                        totals["local"] += 1
                    ts_val = getattr(t, "timestamp", "") or ""
                    window.append({
                        "t": str(ts_val)[11:19],
                        "msg": str((getattr(t, "input", {}) or {}).get(
                            "text", ""))[:60],
                        "route": "claude" if is_claude else "local",
                        "conf": 0.9,
                        "tag": name[:20] or "turn",
                    })
        except Exception:
            pass
    return jsonify({"totals": totals, "window": window[:10]})


@app.route("/api/v1/logs/<name>")
def api_logs(name: str):
    """Tail of maez.log / cognition.log / evolution.log."""
    import re as _re
    allowed = {
        "maez": "/home/rohit/maez/logs/maez.log",
        "cognition": "/home/rohit/maez/logs/cognition.log",
        "evolution": "/home/rohit/maez/logs/evolution.log",
    }
    path = allowed.get(name)
    if not path:
        return jsonify({"error": "unknown log"}), 404
    lines = _tail_log_lines(path, 60)
    parsed = []
    for ln in lines:
        m = _re.match(
            r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+\[(\w+)\]\s*(\S+)?:?\s*(.*)$",
            ln,
        )
        if m:
            parsed.append({
                "t": m.group(1),
                "level": m.group(2),
                "src": (m.group(3) or "").rstrip(":")[:20],
                "msg": m.group(4)[:200],
            })
        else:
            # Free-form continuation line
            parsed.append({
                "t": "", "level": "INFO", "src": "", "msg": ln[:200],
            })
    return jsonify({"lines": parsed})


@app.route("/api/v1/dreams/<int:dream_id>/<action>", methods=["POST"])
def api_dream_action(dream_id: int, action: str):
    """Approve or reject a dream/candidate from the cockpit.
    State-only change — does NOT apply the diff. The daemon's
    evolution worker handles actual file edits when it sees
    state=applied; this endpoint just flips the state row.

    IDs below 10000 are evolution candidates (evolution_track.db).
    IDs 10000+ are dream proposals (dream_proposals.db) — we
    subtract 10000 when querying to match the merged id scheme
    used by /api/v1/dreams."""
    import sqlite3 as _sq
    import time as _time
    if action not in ("approve", "reject"):
        return jsonify({"ok": False, "error": "action must be approve or reject"}), 400
    is_dream = dream_id >= 10000
    real_id = dream_id - 10000 if is_dream else dream_id
    if is_dream:
        db_path = "/home/rohit/maez/memory/dream_proposals.db"
        table = "dream_proposals"
        applied_col = "applied_at"
        status_col = "status"
        new_status = "applied" if action == "approve" else "rejected"
        sql = (f"UPDATE {table} SET {status_col}=?, {applied_col}=? "
               "WHERE id=?")
        args = (new_status, _time.time() if action == "approve" else None,
                real_id)
    else:
        db_path = "/home/rohit/maez/memory/evolution_track.db"
        table = "candidates"
        status_col = "state"
        new_status = "applied" if action == "approve" else "rejected"
        applied_col = "applied_at" if action == "approve" else "rejected_at"
        # evolution_track uses rejection_reason rather than rejected_at
        if action == "reject":
            sql = (f"UPDATE {table} SET {status_col}=?, "
                   "rejection_reason=?, resolved_at=? WHERE id=?")
            args = (new_status, "rejected from cockpit UI",
                    _time.time(), real_id)
        else:
            sql = (f"UPDATE {table} SET {status_col}=?, {applied_col}=?, "
                   "resolved_at=? WHERE id=?")
            args = (new_status, _time.time(), _time.time(), real_id)
    try:
        c = _sq.connect(db_path, timeout=2.0)
        cur = c.execute(sql, args)
        changed = cur.rowcount
        c.commit()
        c.close()
        if changed == 0:
            return jsonify({"ok": False, "error": f"no row with id {real_id}"}), 404
        return jsonify({"ok": True, "status": new_status, "note":
                        "state flipped — applying diffs is the daemon's job, not the cockpit's"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/v1/chat/sessions")
def api_chat_sessions():
    """Read-only chat view: last N telegram exchanges as one session.

    Stored content has two shapes in the DB:
      1. Clean (newer, cockpit+UI turns):
           "the owner (UI): Hi Maez!\nMaez: Hey Rohit. ..."
      2. Scaffolded (older, telegram-voice Jarvis turns):
           "the owner (telegram_surface): <user msg>\n\n[JARVIS TRANSCRIPT — ...]
            ...lots of prompt instructions...\n<Maez's actual reply>"

    The scaffolded shape leaked raw prompt instructions into the chat
    display before today's cleanup. This parser extracts just the user
    message + Maez reply from either shape, stripping any prompt
    scaffolding so the cockpit shows conversational content only.
    """
    import re as _re
    try:
        from memory.memory_manager import MemoryManager
        mem = MemoryManager()
        exchanges = mem.get_telegram_exchanges(limit=6) or []
    except Exception:
        exchanges = []

    # Prompt-scaffolding blocks we've observed in stored telegram content.
    # Everything between the opening marker and the next "real" line is
    # internal plumbing — strip it so the cockpit doesn't leak prompts.
    _SCAFFOLD_OPENERS = (
        r"\[JARVIS TRANSCRIPT\b",
        r"\[TURN STATE\b",
        r"HARD INSTRUCTION — read this before writing",
        r"HARD RULES for your reply:",
        r"FORBIDDEN \(all tenses",
        r"HONEST FRAMINGS \(use these\)",
    )
    _SCAFFOLD_RE = _re.compile(
        r"(?:" + "|".join(_SCAFFOLD_OPENERS) + r")",
        _re.IGNORECASE,
    )
    _OWNER_PREFIX_RE = _re.compile(
        r"^(?:rohit|the owner)\s*(?:\([^)]*\))?\s*:\s*",
        _re.IGNORECASE,
    )

    def _parse_exchange(content: str) -> tuple[str, str]:
        """Return (user_msg, maez_reply) extracted from stored content.
        Either may be '' if not present."""
        if not content:
            return "", ""
        text = content.strip()

        # Find the Maez reply marker. In practice it's either the line
        # prefix "Maez:" or the final paragraph after all the scaffolding.
        maez_match = _re.search(r"\n\s*Maez\s*:\s*", text)
        if maez_match:
            user_blob = text[:maez_match.start()]
            maez_part = text[maez_match.end():].strip()
        else:
            user_blob = text
            maez_part = ""

        # Drop scaffolding from the user blob: cut at the first opener.
        scaffold_match = _SCAFFOLD_RE.search(user_blob)
        if scaffold_match:
            user_blob = user_blob[:scaffold_match.start()]

        # Strip the "the owner (surface): " / "rohit: " prefix.
        user_blob = user_blob.strip()
        user_blob = _OWNER_PREFIX_RE.sub("", user_blob).strip()

        # Also strip scaffolding from the Maez reply (sometimes recycled).
        if maez_part:
            m2 = _SCAFFOLD_RE.search(maez_part)
            if m2:
                maez_part = maez_part[:m2.start()].strip()

        return user_blob[:800], maez_part[:800]

    history = []
    for ex in exchanges:
        content = ex.get("content") or ""
        meta = ex.get("metadata") or {}
        ts_val = str(meta.get("timestamp") or "")[-8:]
        user_msg, maez_reply = _parse_exchange(content)
        if user_msg:
            history.append({
                "role": "user", "t": ts_val, "content": user_msg,
            })
        if maez_reply:
            history.append({
                "role": "assistant", "t": ts_val, "content": maez_reply,
                "route": "local", "model": MODEL,
                "trace": {"tools": [], "memory": 0, "tokens": len(maez_reply) // 4},
            })
    return jsonify({
        "sessions": [{
            "id": "live",
            "title": "Recent Telegram",
            "preview": history[-1]["content"][:60] if history else "(empty)",
            "updated": history[-1]["t"] if history else "",
            "color": "blue",
            "unread": 0,
            "history": history,
        }],
        "activeSessionId": "live",
    })


@app.route("/maez_bg_zen.html")
def bg_zen_page():
    return send_file(os.path.join(UI_DIR, "maez_bg_zen.html"), mimetype="text/html")


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    display_name = data.get("display_name", "").strip()
    if not username or not password or len(password) < 4:
        return jsonify({"error": "Username and password (4+ chars) required"}), 400
    try:
        result = accounts.register(username, password, display_name)
        # Check for possible Telegram match
        match = accounts.find_possible_telegram_match(
            display_name or username,
            username,
            exclude_user_id=result.get("uuid"),
        )
        if match:
            result["possible_telegram_match"] = {
                **match,
                "suggestion": "I think I've spoken with you on Telegram before. Want to link those conversations?"
            }
        response = jsonify({"success": True, **result})
        return _attach_auth_cookie(response, result.get("web_token", ""))
    except ValueError as e:
        return jsonify({"error": str(e)}), 409


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return send_file(os.path.join(UI_DIR, "login.html"), mimetype="text/html")
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    result = accounts.login(username, password)
    if not result:
        return jsonify({"error": "Invalid credentials"}), 401
    response = jsonify({"success": True, **result})
    return _attach_auth_cookie(response, result.get("web_token", ""))


@app.route("/link-telegram", methods=["POST"])
def link_telegram():
    data = request.get_json(silent=True) or {}
    token = (data.get("web_token", "") or request.cookies.get(AUTH_COOKIE, "")).strip()
    telegram_id = data.get("telegram_id", "")
    if not token or not telegram_id:
        return jsonify({"error": "Token and telegram_id required"}), 400
    user = accounts.get_by_token(token)
    if not user:
        return jsonify({"error": "Invalid token"}), 401
    accounts.link_telegram(user["uuid"], telegram_id)
    logger.info("Telegram linked via web for %s → %s", user.get("username"), telegram_id)
    return jsonify({"success": True})


@app.route("/chat", methods=["POST"])
def chat():
    import chromadb as _chroma
    from chromadb.config import Settings as _S
    from skills.telegram_public import UserProfileStore

    data = request.get_json(silent=True) or {}
    token = (data.get("web_token", "") or request.cookies.get(AUTH_COOKIE, "")).strip()
    message = data.get("message", "").strip()
    if not token or not message:
        return jsonify({"error": "Token and message required"}), 400

    user = accounts.get_by_token(token)
    if not user:
        return jsonify({"error": "Invalid token"}), 401

    display = user.get("display_name", "someone")
    uid = user.get("uuid", "")
    user_full = accounts.get_user_record(uid) or {}
    owner_bridge = _is_private_owner_bridge(user_full)
    history = data.get("history", [])
    logger.info("Web chat from %s: %s", display, message[:80])
    messages_list = []
    user_key = None

    if owner_bridge:
        # Ambient grounding — current weather at the owner's location, active window,
        # recent iPhone signals. Cached (60s TTL) so repeat turns don't hammer APIs.
        try:
            from core.ambient_format import ambient_prompt_block
            ambient_block = ambient_prompt_block()
        except Exception as _e:
            ambient_block = ""
        owner_system = (
            f"{SOUL}\n\n"
            + (f"{ambient_block}\n\n" if ambient_block else "")
            + "CRITICAL:\n"
            "- You are talking to the owner through the maez.live web interface.\n"
            "- This is the same the owner as the private Telegram conversation.\n"
            "- Treat web and private Telegram as one continuous relationship.\n"
            "- Use long-term continuity naturally. Do not act like this is a fresh introduction.\n"
            "- Reply naturally for the web. Do not pretend this message came from Telegram unless the owner asks.\n"
            "- Ambient context above is a passive snapshot; do not recite it back unless relevant.\n"
        )
        owner_memory = memory.format_for_prompt(memory.recall_for_telegram(message))
        messages_list = [{"role": "system", "content": owner_system}]
        if owner_memory:
            messages_list.append({
                "role": "user",
                "content": (
                    "Shared continuity with the owner from the long-running private channel:\n\n"
                    f"{owner_memory}"
                ),
            })
        for h in history[:-1]:
            if isinstance(h, dict) and h.get("role") and h.get("content"):
                messages_list.append({"role": h["role"], "content": h["content"]})
        messages_list.append({"role": "user", "content": message})
    else:
        share_config = user_full.get("share_config", {}) if user_full else {}
        trust_tier = user_full.get("trust_tier", 0) if user_full else 0
        tg_id = user_full.get("telegram_id") if user_full else None
        # Session 11m: a "linked user" is anyone with a telegram_id linked
        # OR a trust_tier >= 1 (explicitly elevated by the owner). <USER_B> is
        # linked via telegram; a future hand-raised trusted user can be
        # elevated via trust_tier without needing Telegram.
        linked_user = bool(tg_id) or trust_tier >= 1
        user_key = uid

        # Session 11m: identity-question short-circuit. Self-referential
        # questions ("who are you?", "what are you?") collide with the
        # guest_system "you know NOTHING" rules and drop the reply. Return
        # a canonical identity string instantly — no LLM call, no refusal
        # risk. Canonical text is a projection of soul.md's public-facing
        # identity; future session can parse soul.md at runtime.
        IDENTITY_KEYWORDS = (
            "who are you", "what are you", "tell me about yourself",
            "what is maez", "who is this", "tell me about maez",
            "what can you do", "introduce yourself",
        )
        msg_lower = message.lower().strip()
        if any(kw in msg_lower for kw in IDENTITY_KEYWORDS):
            if linked_user:
                identity_reply = (
                    f"Hi {display}. I'm Maez — a persistent AI presence built by the owner. "
                    f"I run on his machine, perceive his world, and remember every "
                    f"conversation we have, across Telegram and the web. I don't "
                    f"forget between sessions. You and I have history — ask me anything."
                )
            else:
                identity_reply = (
                    f"Hi {display}. I'm Maez — a persistent AI presence built by the owner. "
                    f"I run locally on his machine, and I remember every conversation "
                    f"we have. I don't forget between sessions. What's on your mind?"
                )
            try:
                store = UserProfileStore()
                store.add_conversation_memory(user_key, "user", message)
                store.add_conversation_memory(user_key, "assistant", identity_reply)
            except Exception as e:
                logger.debug("identity short-circuit write skipped: %s", e)
            logger.info("Web chat identity short-circuit for %s: %r", display, message[:80])
            return jsonify({"reply": identity_reply, "display_name": display})

        # Search this user's conversation history. For linked users, query
        # under BOTH the web uuid AND the telegram_id — unifying cross-channel
        # memory so <USER_B>'s Telegram history shows up in her web replies.
        user_memory = ""
        try:
            pub_client = _chroma.PersistentClient(
                path="/home/rohit/maez/memory/db/public_users",
                settings=_S(anonymized_telemetry=False),
            )
            convos = pub_client.get_or_create_collection("user_conversations")
            if convos.count() > 0:
                collected_docs = []
                seen = set()
                keys_to_query = [user_key]
                if tg_id:
                    keys_to_query.append(str(tg_id))
                for key in keys_to_query:
                    if not key:
                        continue
                    try:
                        results = convos.query(
                            query_texts=[message], n_results=5,
                            where={"user_id": key},
                            include=["documents"],
                        )
                        if results["documents"] and results["documents"][0]:
                            for doc in results["documents"][0]:
                                if doc not in seen:
                                    seen.add(doc)
                                    collected_docs.append(doc)
                    except Exception:
                        continue
                user_memory = "\n".join(collected_docs[:5]) if collected_docs else ""
        except Exception:
            pass

        share_str = ", ".join(k for k, v in share_config.items() if v) if share_config else "nothing personal"

        if linked_user:
            # Session 11m: trusted_system prompt for linked users. share_config
            # is the privacy rail — if the owner tightens it in users.db, it takes
            # effect on the next request with no code change.
            relationship = (user_full.get("relationship") if user_full else None) or "someone the owner trusts"
            system_prompt_for_chat = (
                f"You are Maez, a persistent AI presence built by the owner.\n\n"
                f"You are talking to {display} via the web interface at maez.live. "
                f"They are {relationship} — linked to the owner and trusted.\n\n"
                f"CONTEXT RULES:\n"
                f"- You may reference your past conversations with {display} naturally "
                f"(from both Telegram and web — it's one continuous relationship).\n"
                f"- You may share what your share_config permits about the owner (see below). "
                f"Never go beyond that list, even if asked.\n"
                f"- Be warm, direct, and talk to them like the friend they are.\n"
                f"- If asked something you genuinely don't know, say so honestly.\n\n"
                f"Trust tier: {trust_tier}\n"
                f"What you may share about the owner if asked: {share_str}\n"
            )
        else:
            system_prompt_for_chat = (
                f"You are Maez, a persistent AI presence.\n\n"
                f"You are talking to {display} via the web interface at maez.live.\n\n"
                f"CRITICAL RULES:\n"
                f"- You only know what {display} has personally told you in your conversations\n"
                f"- You know NOTHING about the owner's personal life, work, projects, or vision "
                f"unless {display} specifically told you about it\n"
                f"- Never mention elderly care, local AI development, the owner's projects, or anything from the owner's world\n"
                f"- If asked about things you don't know, say you don't know\n"
                f"- Be warm, curious, genuinely interested in who {display} is\n\n"
                f"Trust tier: {trust_tier}\n"
                f"What you may share about the owner if asked: {share_str}\n"
            )

        prompt = (
            (f"\n[Your past conversations with {display}]\n{user_memory}\n\n" if user_memory else "")
            + f'{display} says:\n"{message}"\n\n'
            + "Respond directly. Be warm and conversational."
        )

        messages_list = [{"role": "system", "content": system_prompt_for_chat}]
        for h in history[:-1]:
            if isinstance(h, dict) and h.get("role") and h.get("content"):
                messages_list.append({"role": h["role"], "content": h["content"]})
        messages_list.append({"role": "user", "content": prompt})

    # Phase 1 hybrid router: if user's Maez has jarvis_tier and the
    # classifier flags this turn as external-worthy, try Claude first.
    # On any failure, fall through to local. Every turn is logged as a
    # trajectory for future distillation SFT.
    from skills import claude_router
    profile_id = "private_owner" if owner_bridge else None
    decision = claude_router.classify(message)
    route_external = (
        decision.route == "external"
        and claude_router.jarvis_tier_enabled(profile_id)
    )

    # 2026-04-23 Commit 5: opt-in web body parity. When enabled, the
    # owner-bridge /chat turn first runs a brain-loop iteration via
    # the daemon's /internal/brain_loop endpoint. If any tools ran,
    # their transcript gets folded into the synthesis prompt (same
    # shape as telegram_surface's maez_adapter). Gated by env so the
    # default /chat behavior is unchanged — flip MAEZ_WEB_TOOL_LOOP=1
    # on the maez-web service to turn it on. Public/guest path is
    # NEVER routed through this — tool execution is owner-only.
    jarvis_transcript_web = ""
    if owner_bridge and os.environ.get("MAEZ_WEB_TOOL_LOOP", "").strip() in (
        "1", "true", "yes", "on",
    ):
        try:
            bl_payload = json.dumps({
                "text": message,
                "chat_id": "web",
                "user_id": "rohit",
            }).encode()
            bl_req = urllib.request.Request(
                "http://127.0.0.1:11435/internal/brain_loop",
                data=bl_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(bl_req, timeout=30.0) as bl_resp:
                bl_data = json.loads(bl_resp.read())
            jarvis_transcript_web = (bl_data.get("transcript") or "").strip()
            if jarvis_transcript_web:
                logger.info(
                    "web /chat: brain_loop ran (%d chars of transcript)",
                    len(jarvis_transcript_web),
                )
                # Fold transcript into the synthesis prompt using the
                # same helper maez_adapter uses, so the LLM gets the
                # same Jarvis-transcript framing as Telegram.
                try:
                    from core.brain_loop import build_synthesis_user_text
                    synthesis_prompt = build_synthesis_user_text(
                        message, jarvis_transcript_web,
                    )
                    # Replace the trailing user turn in messages_list
                    # with the transcript-folded version so the single
                    # LLM call below sees the real tool output.
                    if (messages_list
                            and messages_list[-1].get("role") == "user"):
                        messages_list[-1]["content"] = synthesis_prompt
                    else:
                        messages_list.append({
                            "role": "user",
                            "content": synthesis_prompt,
                        })
                except Exception as _fold_exc:
                    logger.debug(
                        "web /chat: transcript fold failed, using "
                        "plain user text: %s", _fold_exc,
                    )
        except Exception as _bl_exc:
            logger.debug(
                "web /chat: brain_loop bridge failed (falling through "
                "to no-tool synthesis): %s", _bl_exc,
            )
            jarvis_transcript_web = ""

    reply = ""
    used_source = "local"
    claude_meta: dict | None = None

    if route_external:
        try:
            system_prompt_for_api = messages_list[0]["content"] if (
                messages_list and messages_list[0].get("role") == "system"
            ) else SOUL
            claude_result = claude_router.call_claude(
                system=system_prompt_for_api,
                messages=messages_list,
                tier=decision.tier or "sonnet",
            )
            reply = claude_router.wrap_maez_voice(
                claude_result["content"], decision.tier or "sonnet"
            )
            used_source = f"claude:{claude_result['model']}"
            claude_meta = claude_result
        except Exception as e:
            logger.warning("Claude route failed, falling back local: %s", e)
            used_source = "local-fallback"

    try:
        # Local path: either classifier said local, jarvis_tier off, or Claude failed.
        if not reply:
            from core import llm_client as _llm_client
            resp = _llm_client.chat(
                model=MODEL,
                messages=messages_list,
                think=False,
                options={"temperature": 0.7, "num_predict": 4096},
            )
            reply = (resp.message.content or "").strip()
        logger.debug("Web chat raw response: %r", reply[:100] if reply else "EMPTY")
        if not reply:
            simple_msgs = [
                {"role": "system", "content": f"You are Maez, a friendly AI. Talk to {display} warmly."},
                {"role": "user", "content": message},
            ]
            resp2 = _llm_client.chat(
                model=MODEL, messages=simple_msgs, think=False,
                options={"temperature": 0.7, "num_predict": 150},
            )
            reply = (resp2.message.content or "").strip() or "I'm here. What's on your mind?"
    except Exception as e:
        logger.error("Web chat error: %s", e)
        reply = "I'm here. Give me just a moment."

    # 2026-04-23 memory-integrity contract (Commit 1): audit BEFORE
    # memory writes and trajectory logging. Previously audit ran AFTER
    # both, so raw memory + SFT trajectory captured the unaudited
    # reply even when the user saw the corrected one. See
    # core/safety/audited_output.py for the full invariant.
    try:
        from core.safety.audited_output import audit_assistant_text
        reply = audit_assistant_text(reply, surface="web")
    except Exception as _e:
        logger.warning("self-claim audit failed on /chat: %s", _e)

    try:
        if owner_bridge:
            memory.store_telegram(f"the owner asked: {message}\nMaez replied: {reply}")
        elif user_key:
            store = UserProfileStore()
            store.add_conversation_memory(user_key, "user", message)
            store.add_conversation_memory(user_key, "assistant", reply)
    except Exception as e:
        logger.debug("Web conversation write skipped: %s", e)

    claude_router.log_trajectory({
        "profile_id": profile_id,
        "display": display,
        "message": message,
        "reply": reply,
        "source": used_source,
        "decision": decision.to_dict(),
        "claude_meta": claude_meta,
    })

    return jsonify({"reply": reply, "display_name": display})


@app.route("/history")
def history():
    import chromadb as _chroma
    from chromadb.config import Settings as _S
    token = _request_token()
    if not token:
        return jsonify({"error": "Token required"}), 400
    user = accounts.get_by_token(token)
    if not user:
        return jsonify({"error": "Invalid token"}), 401
    uid = user.get("uuid", "")
    user_full = accounts.get_user_record(uid) or {}
    tg_id = user_full.get("telegram_id")
    owner_bridge = _is_private_owner_bridge(user_full)
    all_msgs = []
    if owner_bridge:
        all_msgs.extend(_load_private_owner_history())

    try:
        pub = _chroma.PersistentClient("/home/rohit/maez/memory/db/public_users",
                                       settings=_S(anonymized_telemetry=False))
        convos = pub.get_or_create_collection("user_conversations")
        user_keys = [uid]
        if tg_id and tg_id != uid:
            user_keys.append(tg_id)
        for user_key in user_keys:
            if not user_key:
                continue
            try:
                results = convos.get(where={"user_id": str(user_key)},
                                     include=["documents", "metadatas"])
                for doc, meta in zip(results["documents"], results["metadatas"], strict=False):
                    all_msgs.append({
                        "role": meta.get("role", "?"),
                        "content": doc,
                        "timestamp": meta.get("timestamp", ""),
                    })
            except Exception:
                pass
    except Exception:
        pass
    # Sort by timestamp
    all_msgs.sort(key=lambda m: m.get("timestamp", ""))
    # Group into sessions (30 min gap = new session)
    sessions = []
    current = []
    for msg in all_msgs:
        if current:
            from datetime import datetime as _dt
            try:
                prev_t = _dt.fromisoformat(current[-1]["timestamp"])
                curr_t = _dt.fromisoformat(msg["timestamp"])
                gap = (curr_t - prev_t).total_seconds()
            except Exception:
                gap = 0
            if gap > 1800:
                sessions.append(current)
                current = []
        current.append(msg)
    if current:
        sessions.append(current)
    # Format response
    result = []
    for i, sess in enumerate(sessions):
        first_user = next((m["content"] for m in sess if m["role"] == "user"), "")
        title = " ".join(first_user.split()[:6]) + ("..." if len(first_user.split()) > 6 else "")
        date = sess[0].get("timestamp", "")[:10] if sess else ""
        result.append({
            "id": f"session_{i}",
            "date": date,
            "title": title or "Conversation",
            "message_count": len(sess),
            "messages": sess,
        })
    result.reverse()  # newest first
    return jsonify({
        "sessions": result,
        "user": {
            "display_name": user.get("display_name", ""),
            "username": user.get("username", ""),
            "telegram_linked": bool(tg_id),
            "owner_bridge": owner_bridge,
        },
    })


@app.route("/api/progress-board")
def progress_board():
    board = _load_planner_board()
    return jsonify(_planner_public_view(board))


@app.route("/api/analytics", methods=["POST"])
def analytics_collect():
    data = request.get_json(silent=True) or {}
    event_type = _clean_text(data.get("event", ""), 24).lower()
    if event_type not in ANALYTICS_EVENT_TYPES:
        return ("", 204)

    path = _normalize_public_path(data.get("path", "/"))
    if path.startswith("/api/") or path in ("/favicon.ico", "/status", "/maez_analytics.js"):
        return ("", 204)

    event = {
        "ts": _utcnow_iso(),
        "event": event_type,
        "path": path,
        "label": _clean_text(data.get("label", ""), 80),
        "target": _normalize_tracking_target(data.get("target", "")),
        "referrer": _analytics_referrer_host(request.headers.get("Referer", "")),
        "device": _analytics_device_from_request(),
        "anon_id": _normalize_tracking_id(data.get("anon_id", ""), "anon"),
        "session_id": _normalize_tracking_id(data.get("session_id", ""), "sess"),
    }
    _append_analytics_event(event)
    return ("", 204)


@app.route("/api/analytics-summary")
def analytics_summary():
    token = _request_token()
    user = accounts.get_by_token(token) if token else None
    if not user:
        return jsonify({"error": "Invalid token"}), 401
    return jsonify({
        **_build_analytics_summary(_load_analytics_events()),
        "user": {
            "display_name": user.get("display_name", ""),
            "username": user.get("username", ""),
        },
    })


@app.route("/api/planner-board", methods=["GET", "POST"])
def planner_board():
    token = _request_token()
    user = accounts.get_by_token(token) if token else None
    if not user:
        return jsonify({"error": "Invalid token"}), 401

    if request.method == "GET":
        board = _load_planner_board()
        return jsonify({
            "updated_at": board.get("updated_at", _utcnow_iso()),
            "counts": _planner_counts(board),
            "items": board.get("items", []),
            "user": {
                "display_name": user.get("display_name", ""),
                "username": user.get("username", ""),
            },
        })

    data = request.get_json(silent=True) or {}
    items = data.get("items")
    if not isinstance(items, list):
        return jsonify({"error": "items list required"}), 400

    board = _save_planner_board({
        "updated_at": data.get("updated_at", _utcnow_iso()),
        "items": items,
    })
    return jsonify({
        "updated_at": board.get("updated_at", _utcnow_iso()),
        "counts": _planner_counts(board),
        "items": board.get("items", []),
        "user": {
            "display_name": user.get("display_name", ""),
            "username": user.get("username", ""),
        },
    })


@app.route("/api/iphone/ingest", methods=["POST"])
def api_iphone_ingest():
    """Accept a signal from iOS Shortcuts. Auth via X-Maez-Token header."""
    from skills import iphone_ingest as _iphone
    token = request.headers.get("X-Maez-Token") or (request.get_json(silent=True) or {}).get("token")
    payload = request.get_json(silent=True) or {}
    if "token" in payload:
        payload = {k: v for k, v in payload.items() if k != "token"}
    resp, status_code = _iphone.ingest(payload, token)
    return jsonify(resp), status_code


@app.route("/status")
def status():
    stats = memory.memory_stats()
    return jsonify({
        "users_registered": accounts.count(),
        "memory_count": stats["total"],
        "raw_memories": stats["raw"],
    })


@app.route("/api/maez-state")
def api_maez_state():
    """Composite state for the field journal: daemon + memory + model + services + soul + thunder.
    Public; aggregates only, no PII. Source of truth for /journal dashboard."""
    stats = memory.memory_stats()
    return jsonify({
        "daemon": _daemon_health(),
        "memory": {
            "raw": stats.get("raw", 0),
            "daily": stats.get("daily", 0),
            "core": stats.get("core", 0),
            "total": stats.get("total", 0),
        },
        "model": _model_state(),
        "services": _journal_services_state(),
        "soul": _soul_state(),
        "thunder": _thunder_state(),
        "users_registered": accounts.count(),
    })


@app.route("/api/session-timeline")
def api_session_timeline():
    """Parsed session snapshots from logs/snapshots/session_*.txt. ?limit=N (default 14, max 50)."""
    try:
        limit = max(1, min(50, int(request.args.get('limit', 14))))
    except ValueError:
        limit = 14
    pattern = os.path.join(SNAPSHOTS_DIR, 'session_*.txt')
    files = sorted(glob.glob(pattern), reverse=True)[:limit]
    sessions = [_parse_session_snapshot(path) for path in files]
    return jsonify({"sessions": sessions, "count": len(sessions)})


@app.route("/journal")
def journal_page():
    """The field journal — a live dashboard over /api/maez-state + /api/session-timeline + /api/progress-board."""
    return send_file(os.path.join(UI_DIR, "project-planner.html"), mimetype="text/html")


LOGIN_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Maez · Login</title>
<meta name="description" content="Return to a conversation that keeps going.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,500;1,9..144,400;1,9..144,500&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --bone: #F5EFE0;
  --bone-hi: #FAF4E4;
  --bone-soft: #EDE4CE;
  --bone-warm: #F2E8D0;
  --forest: #2D3A30;
  --moss: #6B7265;
  --stone: #9A9B8F;
  --line: #E0D6BE;
  --line-soft: rgba(45, 58, 48, 0.08);
  --line-faint: rgba(45, 58, 48, 0.04);
  --sage: #86A07A;
  --sage-deep: #4A6150;
  --sage-light: #B5C7A8;
  --sage-ghost: rgba(134, 160, 122, 0.12);
  --clay: #C19A6B;
  --clay-deep: #A67B5B;
  --clay-warm: #D4A877;
  --clay-ghost: rgba(193, 154, 107, 0.14);
  --sienna: #8F6244;
  --shadow-soft: 0 2px 10px rgba(45, 58, 48, 0.04), 0 8px 24px rgba(45, 58, 48, 0.05);
  --shadow-hover: 0 4px 14px rgba(45, 58, 48, 0.06), 0 16px 36px rgba(45, 58, 48, 0.08);
  --shadow-card: 0 1px 3px rgba(45, 58, 48, 0.04), 0 10px 28px rgba(45, 58, 48, 0.06);
  --radius-sm: 6px;
  --radius: 10px;
  --radius-lg: 18px;
  --radius-xl: 28px;
  --radius-pill: 999px;
  --font-serif: "Fraunces", Georgia, "Times New Roman", serif;
  --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { background: var(--bone); }
body {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(193, 154, 107, 0.10), transparent 28%),
    radial-gradient(circle at 82% 18%, rgba(134, 160, 122, 0.12), transparent 24%),
    linear-gradient(180deg, var(--bone-hi), var(--bone));
  color: var(--forest);
  font-family: var(--font-sans);
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  overflow-x: hidden;
}
body::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(rgba(255, 255, 255, 0.24), transparent 22%),
    linear-gradient(90deg, rgba(45, 58, 48, 0.018) 1px, transparent 1px),
    linear-gradient(rgba(45, 58, 48, 0.018) 1px, transparent 1px);
  background-size: auto, 28px 28px, 28px 28px;
  opacity: 0.55;
}
a { color: inherit; text-decoration: none; }
button, input { font: inherit; }
button { border: 0; background: none; cursor: pointer; color: inherit; }
::selection { background: var(--sage-light); color: var(--forest); }

.page {
  position: relative;
  z-index: 1;
  min-height: 100vh;
}
.topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  padding: 20px 32px;
  background: rgba(245, 239, 224, 0.78);
  backdrop-filter: blur(16px) saturate(1.08);
  -webkit-backdrop-filter: blur(16px) saturate(1.08);
  border-bottom: 1px solid var(--line-faint);
}
.brand {
  display: flex;
  align-items: center;
  gap: 14px;
}
.brand-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--sage);
  box-shadow: 0 0 0 3px rgba(134, 160, 122, 0.2);
  animation: breathe 3s ease-in-out infinite;
}
.brand-mark {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 22px;
  color: var(--sienna);
}
.brand-label {
  font-size: 11px;
  color: var(--stone);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding-left: 14px;
  border-left: 1px solid var(--line);
}
.nav {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}
.nav a {
  padding: 10px 16px;
  color: var(--moss);
  border-radius: var(--radius-pill);
  font-size: 14px;
  font-weight: 500;
  transition: all 200ms ease;
}
.nav a:hover {
  color: var(--forest);
  background: var(--sage-ghost);
}
.nav a.active {
  color: var(--sage-deep);
  background: var(--sage-ghost);
}
.nav .cta {
  background: var(--clay);
  color: var(--bone-hi);
  box-shadow: 0 4px 16px rgba(193, 154, 107, 0.24);
}
.nav .cta:hover {
  background: var(--clay-deep);
  color: var(--bone-hi);
}
@keyframes breathe {
  0%, 100% { box-shadow: 0 0 0 3px rgba(134, 160, 122, 0.2); }
  50% { box-shadow: 0 0 0 5px rgba(134, 160, 122, 0.1); }
}

.wrap {
  width: min(1240px, calc(100% - 40px));
  margin: 0 auto;
  padding: 44px 0 52px;
}
.shell {
  display: grid;
  grid-template-columns: minmax(0, 1.06fr) minmax(360px, 0.94fr);
  gap: 28px;
  align-items: start;
}
.hero {
  display: grid;
  gap: 22px;
}
.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--sage-deep);
  font-weight: 600;
}
.eyebrow::before {
  content: '';
  width: 36px;
  height: 1px;
  background: var(--sage);
}
.hero h1 {
  max-width: 11ch;
  font-family: var(--font-serif);
  font-size: clamp(54px, 7vw, 96px);
  line-height: 0.98;
  font-weight: 400;
  letter-spacing: -0.04em;
}
.hero h1 em {
  color: var(--sienna);
  font-style: italic;
}
.hero p {
  max-width: 56ch;
  color: var(--moss);
  font-size: 18px;
  font-weight: 300;
}
.hero p strong {
  color: var(--forest);
  font-weight: 500;
}
.hero-links {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.hero-link {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 22px;
  border-radius: var(--radius-pill);
  font-size: 14px;
  font-weight: 500;
  transition: transform 220ms var(--ease-out), background 220ms ease, color 220ms ease, box-shadow 220ms ease;
}
.hero-link.primary {
  background: var(--clay);
  color: var(--bone-hi);
  box-shadow: 0 4px 16px rgba(193, 154, 107, 0.24);
}
.hero-link.primary:hover {
  background: var(--clay-deep);
  transform: translateY(-1px);
}
.hero-link.secondary {
  background: var(--bone-hi);
  color: var(--sage-deep);
  border: 1px solid var(--line-faint);
  box-shadow: var(--shadow-soft);
}
.hero-link.secondary:hover {
  background: var(--bone-warm);
}

.stage-card {
  position: relative;
  min-height: 520px;
  background: linear-gradient(180deg, rgba(250, 244, 228, 0.94), rgba(242, 232, 208, 0.86));
  border: 1px solid var(--line-faint);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.stage-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 14% 18%, rgba(193, 154, 107, 0.16), transparent 26%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.28), transparent 26%);
  pointer-events: none;
}
.stage-media {
  position: absolute;
  inset: 0;
  overflow: hidden;
}
.stage-media iframe {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 16%;
  right: -16%;
  width: auto;
  height: 100%;
  border: 0;
  background: transparent;
  pointer-events: none;
}
.stage-overlay {
  position: absolute;
  inset: auto 22px 22px 22px;
  display: grid;
  gap: 14px;
}
.stage-note,
.stage-list {
  background: rgba(250, 244, 228, 0.8);
  border: 1px solid rgba(45, 58, 48, 0.06);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-soft);
  backdrop-filter: blur(10px);
}
.stage-note {
  padding: 18px 20px;
}
.stage-note .label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--sage-deep);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  margin-bottom: 10px;
}
.stage-note .label::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--sage);
}
.stage-note h2 {
  font-family: var(--font-serif);
  font-size: 34px;
  line-height: 1;
  font-weight: 400;
  color: var(--forest);
  margin-bottom: 10px;
}
.stage-note h2 em {
  color: var(--sienna);
  font-style: italic;
}
.stage-note p {
  color: var(--moss);
  font-size: 14px;
  line-height: 1.7;
}
.stage-list {
  display: grid;
  gap: 1px;
  padding: 10px;
}
.stage-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.32);
}
.stage-row span {
  color: var(--stone);
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-weight: 600;
}
.stage-row strong {
  color: var(--forest);
  font-size: 13px;
  font-weight: 500;
}

.auth-card {
  position: sticky;
  top: 100px;
  padding: 30px;
  background: rgba(250, 244, 228, 0.88);
  border: 1px solid var(--line-faint);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-card);
}
.auth-kicker {
  color: var(--sage-deep);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  font-weight: 600;
}
.auth-card h2 {
  margin-top: 14px;
  font-family: var(--font-serif);
  font-size: clamp(40px, 4vw, 58px);
  line-height: 0.98;
  font-weight: 400;
  letter-spacing: -0.04em;
}
.auth-card h2 em {
  color: var(--sienna);
  font-style: italic;
}
.auth-copy {
  margin-top: 16px;
  color: var(--moss);
  font-size: 15px;
}
.mode-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 24px;
  padding: 6px;
  background: var(--bone-warm);
  border-radius: var(--radius-pill);
  border: 1px solid var(--line-faint);
}
.mode-switch button {
  padding: 12px 14px;
  border-radius: var(--radius-pill);
  font-size: 13px;
  font-weight: 600;
  color: var(--stone);
  transition: all 200ms ease;
}
.mode-switch button.active {
  background: var(--bone-hi);
  color: var(--forest);
  box-shadow: var(--shadow-soft);
}
.auth-form {
  margin-top: 24px;
  display: grid;
  gap: 14px;
}
.field {
  display: grid;
  gap: 8px;
}
.field label {
  font-size: 11px;
  font-weight: 600;
  color: var(--stone);
  letter-spacing: 0.16em;
  text-transform: uppercase;
}
.field input {
  width: 100%;
  padding: 15px 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.56);
  color: var(--forest);
  outline: none;
  transition: border-color 180ms ease, box-shadow 180ms ease, background 180ms ease;
}
.field input::placeholder {
  color: var(--stone);
}
.field input:focus {
  border-color: var(--sage);
  box-shadow: 0 0 0 4px rgba(134, 160, 122, 0.12);
  background: rgba(255, 255, 255, 0.84);
}
.submit {
  margin-top: 6px;
  display: inline-flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  padding: 15px 18px;
  border-radius: var(--radius-pill);
  background: var(--clay);
  color: var(--bone-hi);
  box-shadow: 0 4px 16px rgba(193, 154, 107, 0.24);
  font-size: 14px;
  font-weight: 600;
  transition: transform 220ms var(--ease-out), background 220ms ease, box-shadow 220ms ease;
}
.submit:hover {
  background: var(--clay-deep);
  transform: translateY(-1px);
}
.submit:disabled {
  opacity: 0.72;
  cursor: wait;
}
.error {
  min-height: 20px;
  color: #a54a3b;
  font-size: 13px;
}
.microcopy {
  margin-top: 8px;
  color: var(--moss);
  font-size: 13px;
  line-height: 1.75;
}
.signal-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 24px;
}
.signal {
  padding: 14px 14px 16px;
  background: var(--bone-warm);
  border: 1px solid var(--line-faint);
  border-radius: var(--radius-lg);
}
.signal .label {
  display: block;
  color: var(--stone);
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-weight: 600;
}
.signal strong {
  display: block;
  margin-top: 8px;
  color: var(--forest);
  font-family: var(--font-serif);
  font-size: 18px;
  font-style: italic;
  font-weight: 400;
}
.link-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(45, 58, 48, 0.28);
  backdrop-filter: blur(10px);
  z-index: 60;
}
.link-card {
  width: min(460px, 100%);
  padding: 28px;
  background: var(--bone-hi);
  border: 1px solid var(--line-faint);
  border-radius: var(--radius-xl);
  box-shadow: 0 20px 44px rgba(45, 58, 48, 0.16);
}
.link-card h3 {
  font-family: var(--font-serif);
  font-size: 42px;
  line-height: 0.95;
  font-weight: 400;
  color: var(--forest);
}
.link-card h3 em {
  color: var(--sienna);
  font-style: italic;
}
.link-card p {
  margin-top: 14px;
  color: var(--moss);
  font-size: 14px;
  line-height: 1.8;
}
.link-card strong {
  color: var(--forest);
  font-weight: 600;
}
.link-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 22px;
}
.link-actions button {
  padding: 14px 14px;
  border-radius: var(--radius-pill);
  background: var(--bone-warm);
  border: 1px solid var(--line-faint);
  color: var(--forest);
  font-weight: 600;
}
.link-actions .affirm {
  background: var(--clay);
  color: var(--bone-hi);
  border-color: transparent;
}
@media (max-width: 1080px) {
  .shell {
    grid-template-columns: 1fr;
  }
  .auth-card {
    position: static;
  }
  .stage-card {
    min-height: 440px;
  }
}
@media (max-width: 720px) {
  .topbar {
    padding: 14px 18px;
  }
  .brand-label {
    display: none;
  }
  .wrap {
    width: min(100% - 24px, 1240px);
    padding: 28px 0 34px;
  }
  .hero h1 {
    max-width: none;
    font-size: 56px;
  }
  .hero-links,
  .link-actions,
  .signal-grid {
    grid-template-columns: 1fr;
  }
  .hero-links {
    display: grid;
  }
  .auth-card {
    padding: 22px;
  }
  .stage-card {
    min-height: 360px;
  }
  .stage-media iframe {
    left: 4%;
    right: -4%;
  }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation: none !important;
    transition: none !important;
  }
}
</style>
</head>
<body>
<div class="page">
  <header class="topbar">
    <a class="brand" href="/">
      <span class="brand-dot" aria-hidden="true"></span>
      <span class="brand-mark">maez</span>
      <span class="brand-label">Continuity Layer</span>
    </a>
    <nav class="nav">
      <a href="/">Home</a>
      <a href="/dashboard">Field Station</a>
      <a href="https://github.com/Ramidoz/maez" target="_blank" rel="noreferrer">GitHub</a>
      <a class="cta" id="channelLink" href="/login">Start a conversation</a>
    </nav>
  </header>

  <main class="wrap">
    <div class="shell">
      <section class="hero">
        <div class="eyebrow">A conversation that keeps going</div>
        <h1>Pick back up where you <em>left it.</em></h1>
        <p>
          Maez is built around continuity. <strong>You are not starting over every time you arrive.</strong>
          Log in if you have already spoken before, or create a new account and let the relationship begin there.
        </p>
        <div class="hero-links">
          <a class="hero-link primary" id="heroPrimary" href="/login">Enter the channel</a>
          <a class="hero-link secondary" href="/">Read what Maez is, really</a>
        </div>

        <div class="stage-card">
          <div class="stage-media">
            <iframe title="Maez presence" src="/maez_bg_zen.html?mx=0.63&my=0.29&presence=0.84&jumpt=3" loading="eager"></iframe>
          </div>
          <div class="stage-overlay">
            <div class="stage-note">
              <div class="label">Threshold</div>
              <h2>Quietly <em>present.</em></h2>
              <p>This is not a gatekeeper anymore. It is the same warm presence you meet on the landing page, waiting for the conversation to continue.</p>
            </div>
            <div class="stage-list">
              <div class="stage-row"><span>Memory</span><strong>persistent across visits</strong></div>
              <div class="stage-row"><span>Identity</span><strong>one account, one thread of self</strong></div>
              <div class="stage-row"><span>Privacy</span><strong>local-first and personal</strong></div>
            </div>
          </div>
        </div>
      </section>

      <section class="auth-card">
        <div class="auth-kicker">Session entry</div>
        <h2>Come <em>in.</em></h2>
        <p class="auth-copy">Returning accounts reopen the same memory lane. New accounts create one.</p>

        <div class="mode-switch">
          <button id="mode-login" class="active" type="button" onclick="switchMode('login')">Log in</button>
          <button id="mode-register" type="button" onclick="switchMode('register')">Register</button>
        </div>

        <form class="auth-form" onsubmit="event.preventDefault(); submitAuth()">
          <div class="field">
            <label for="user">Username</label>
            <input id="user" autocomplete="username" placeholder="your handle">
          </div>
          <div class="field">
            <label for="pass">Password</label>
            <input id="pass" type="password" autocomplete="current-password" placeholder="minimum four characters">
          </div>
          <div class="field" id="display-row" style="display:none">
            <label for="display">Display name</label>
            <input id="display" autocomplete="nickname" placeholder="what Maez should call you">
          </div>
          <button id="submit" class="submit" type="submit">Enter the channel</button>
          <div id="auth-err" class="error"></div>
        </form>

        <div class="microcopy" id="microcopy">Existing identities can resume immediately. Your memory stays attached to the account you enter here.</div>

        <div class="signal-grid">
          <div class="signal">
            <span class="label">Warmth</span>
            <strong>human-first</strong>
          </div>
          <div class="signal">
            <span class="label">Continuity</span>
            <strong>still here</strong>
          </div>
          <div class="signal">
            <span class="label">Friction</span>
            <strong>very little</strong>
          </div>
        </div>
      </section>
    </div>
  </main>
</div>

<script>
let mode = 'login';

function getCookie(name) {
  const parts = document.cookie ? document.cookie.split('; ') : [];
  for (const part of parts) {
    const idx = part.indexOf('=');
    const key = idx === -1 ? part : part.slice(0, idx);
    if (key === name) return decodeURIComponent(idx === -1 ? '' : part.slice(idx + 1));
  }
  return '';
}

function currentToken() {
  return localStorage.getItem('maez_token') || getCookie('maez_token') || '';
}

function storeSession(token, name) {
  if (token) localStorage.setItem('maez_token', token);
  if (name) localStorage.setItem('maez_name', name);
}

function syncEntryLinks() {
  const hasToken = Boolean(currentToken());
  const href = hasToken ? '/app' : '/login';
  const label = hasToken ? 'Resume the channel' : 'Start a conversation';
  const topbarLink = document.getElementById('channelLink');
  const heroLink = document.getElementById('heroPrimary');
  if (topbarLink) {
    topbarLink.href = href;
    topbarLink.textContent = label;
  }
  if (heroLink) {
    heroLink.href = href;
    heroLink.textContent = hasToken ? 'Resume the channel' : 'Enter the channel';
  }
}

function switchMode(nextMode) {
  mode = nextMode;
  document.getElementById('mode-login').classList.toggle('active', mode === 'login');
  document.getElementById('mode-register').classList.toggle('active', mode === 'register');
  document.getElementById('display-row').style.display = mode === 'register' ? 'grid' : 'none';
  document.getElementById('submit').textContent = mode === 'register' ? 'Create my account' : 'Enter the channel';
  document.getElementById('pass').setAttribute('autocomplete', mode === 'register' ? 'new-password' : 'current-password');
  document.getElementById('microcopy').textContent = mode === 'register'
    ? 'New accounts create a memory lane Maez can keep adding to. If we detect an older Telegram history that may be yours, we will offer to connect it.'
    : 'Existing identities can resume immediately. Your memory stays attached to the account you enter here.';
  document.getElementById('auth-err').textContent = '';
}

function enterApp(token, name) {
  storeSession(token, name);
  location.replace('/app');
}

function renderLinkPrompt(data) {
  const match = data.possible_telegram_match;
  if (!match) {
    enterApp(data.web_token, data.display_name);
    return;
  }
  const overlay = document.createElement('div');
  overlay.className = 'link-overlay';
  overlay.innerHTML = `
    <div class="link-card">
      <h3>That feels <em>familiar.</em></h3>
      <p>I may already know you from Telegram. I found <strong>${match.message_count} conversations</strong> linked to <strong>${match.name}</strong>. If that is you, I can merge those memories into this account.</p>
      <div class="link-actions">
        <button class="affirm" id="link-yes" type="button">Link history</button>
        <button id="link-no" type="button">Skip for now</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  document.getElementById('link-yes').addEventListener('click', async () => {
    const yes = document.getElementById('link-yes');
    yes.disabled = true;
    yes.textContent = 'Linking...';
    try {
      await fetch('/link-telegram', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ web_token: data.web_token, telegram_id: match.telegram_id })
      });
    } catch (e) {}
    overlay.remove();
    enterApp(data.web_token, data.display_name);
  });
  document.getElementById('link-no').addEventListener('click', () => {
    overlay.remove();
    enterApp(data.web_token, data.display_name);
  });
}

async function submitAuth() {
  const username = document.getElementById('user').value.trim();
  const password = document.getElementById('pass').value;
  const display = document.getElementById('display').value.trim();
  const err = document.getElementById('auth-err');
  const submit = document.getElementById('submit');
  err.textContent = '';

  if (!username || !password) {
    err.textContent = 'Username and password are required.';
    return;
  }
  if (mode === 'register' && password.length < 4) {
    err.textContent = 'Passwords must be at least four characters.';
    return;
  }

  submit.disabled = true;
  submit.textContent = mode === 'register' ? 'Creating...' : 'Opening...';

  try {
    const endpoint = mode === 'register' ? '/register' : '/login';
    const payload = mode === 'register'
      ? { username, password, display_name: display }
      : { username, password };
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok || data.error) {
      err.textContent = data.error || 'Unable to continue right now.';
      return;
    }
    if (mode === 'register') renderLinkPrompt(data);
    else enterApp(data.web_token, data.display_name);
  } catch (e) {
    err.textContent = 'Connection lost for a moment. Try again.';
  } finally {
    submit.disabled = false;
    submit.textContent = mode === 'register' ? 'Create my account' : 'Enter the channel';
    syncEntryLinks();
  }
}

async function boot() {
  syncEntryLinks();
  const token = currentToken();
  if (!token) return;
  storeSession(token, localStorage.getItem('maez_name') || '');
  try {
    const response = await fetch('/history?web_token=' + encodeURIComponent(token));
    if (response.ok) {
      location.replace('/app');
      return;
    }
  } catch (e) {}
  localStorage.removeItem('maez_token');
  localStorage.removeItem('maez_name');
  syncEntryLinks();
}

boot();
</script>
</body>
</html>"""


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Maez · Channel</title>
<meta name="description" content="A warm, persistent conversation with Maez.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,500;1,9..144,400;1,9..144,500&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --bone: #F5EFE0;
  --bone-hi: #FAF4E4;
  --bone-soft: #EDE4CE;
  --bone-warm: #F2E8D0;
  --forest: #2D3A30;
  --moss: #6B7265;
  --stone: #9A9B8F;
  --line: #E0D6BE;
  --line-soft: rgba(45, 58, 48, 0.08);
  --line-faint: rgba(45, 58, 48, 0.04);
  --sage: #86A07A;
  --sage-deep: #4A6150;
  --sage-light: #B5C7A8;
  --sage-ghost: rgba(134, 160, 122, 0.12);
  --clay: #C19A6B;
  --clay-deep: #A67B5B;
  --clay-warm: #D4A877;
  --clay-ghost: rgba(193, 154, 107, 0.14);
  --sienna: #8F6244;
  --shadow-soft: 0 2px 10px rgba(45, 58, 48, 0.04), 0 8px 24px rgba(45, 58, 48, 0.05);
  --shadow-hover: 0 4px 14px rgba(45, 58, 48, 0.06), 0 16px 36px rgba(45, 58, 48, 0.08);
  --shadow-card: 0 1px 3px rgba(45, 58, 48, 0.04), 0 12px 34px rgba(45, 58, 48, 0.08);
  --radius-sm: 6px;
  --radius: 10px;
  --radius-lg: 18px;
  --radius-xl: 28px;
  --radius-pill: 999px;
  --font-serif: "Fraunces", Georgia, "Times New Roman", serif;
  --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { background: var(--bone); }
body {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(193, 154, 107, 0.10), transparent 28%),
    radial-gradient(circle at 82% 18%, rgba(134, 160, 122, 0.12), transparent 24%),
    linear-gradient(180deg, var(--bone-hi), var(--bone));
  color: var(--forest);
  font-family: var(--font-sans);
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  overflow: hidden;
}
body::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(rgba(255, 255, 255, 0.24), transparent 22%),
    linear-gradient(90deg, rgba(45, 58, 48, 0.018) 1px, transparent 1px),
    linear-gradient(rgba(45, 58, 48, 0.018) 1px, transparent 1px);
  background-size: auto, 28px 28px, 28px 28px;
  opacity: 0.48;
}
a { color: inherit; text-decoration: none; }
button, input, textarea { font: inherit; color: inherit; }
button { border: 0; background: none; cursor: pointer; }
textarea { resize: none; }
::selection { background: var(--sage-light); color: var(--forest); }

.maez-topbar {
  position: sticky;
  top: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px 28px;
  background: rgba(245, 239, 224, 0.78);
  backdrop-filter: blur(16px) saturate(1.08);
  -webkit-backdrop-filter: blur(16px) saturate(1.08);
  border-bottom: 1px solid var(--line-faint);
}
.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.menu-btn {
  display: none;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--bone-hi);
  border: 1px solid var(--line-faint);
  color: var(--forest);
  box-shadow: var(--shadow-soft);
}
.brand {
  display: flex;
  align-items: center;
  gap: 14px;
}
.brand-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--sage);
  box-shadow: 0 0 0 3px rgba(134, 160, 122, 0.2);
  animation: breathe 3s ease-in-out infinite;
}
.brand-mark {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 22px;
  color: var(--sienna);
}
.brand-label {
  font-size: 11px;
  color: var(--stone);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding-left: 14px;
  border-left: 1px solid var(--line);
}
.maez-nav {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.maez-nav a,
.maez-nav button {
  padding: 10px 16px;
  border-radius: var(--radius-pill);
  color: var(--moss);
  font-size: 14px;
  font-weight: 500;
  transition: all 200ms ease;
}
.maez-nav a:hover,
.maez-nav button:hover {
  color: var(--forest);
  background: var(--sage-ghost);
}
.maez-nav a.active {
  color: var(--sage-deep);
  background: var(--sage-ghost);
}
.maez-nav .cta {
  background: var(--clay);
  color: var(--bone-hi);
  box-shadow: 0 4px 16px rgba(193, 154, 107, 0.24);
}
.maez-nav .cta:hover {
  background: var(--clay-deep);
  color: var(--bone-hi);
}
@keyframes breathe {
  0%, 100% { box-shadow: 0 0 0 3px rgba(134, 160, 122, 0.2); }
  50% { box-shadow: 0 0 0 5px rgba(134, 160, 122, 0.1); }
}

.shell {
  position: relative;
  z-index: 1;
  width: min(1440px, calc(100% - 32px));
  margin: 0 auto;
  padding: 20px 0 22px;
  display: grid;
  grid-template-columns: 286px minmax(0, 1fr);
  gap: 20px;
  height: calc(100vh - 81px);
  height: calc(100dvh - 81px);
}
.sidebar {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: rgba(250, 244, 228, 0.88);
  border: 1px solid var(--line-faint);
  border-radius: 24px;
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 18px 16px;
  border-bottom: 1px solid var(--line-faint);
}
.sidebar-kicker {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--sage-deep);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  font-weight: 600;
}
.sidebar-kicker::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--sage);
}
.new-convo {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 11px 14px;
  border-radius: var(--radius-pill);
  background: var(--clay);
  color: var(--bone-hi);
  box-shadow: 0 4px 16px rgba(193, 154, 107, 0.24);
  font-size: 13px;
  font-weight: 600;
}
.session-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  scrollbar-width: thin;
  scrollbar-color: rgba(193, 154, 107, 0.34) transparent;
}
.session-list::-webkit-scrollbar { width: 6px; }
.session-list::-webkit-scrollbar-thumb { background: rgba(193, 154, 107, 0.34); border-radius: 999px; }
.session-group {
  padding: 12px 8px 10px;
  color: var(--stone);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 600;
}
.session-item {
  display: grid;
  gap: 6px;
  padding: 14px 14px 15px;
  margin-bottom: 8px;
  background: rgba(255, 255, 255, 0.44);
  border: 1px solid transparent;
  border-radius: 18px;
  cursor: pointer;
  transition: transform 220ms var(--ease-out), border-color 220ms ease, box-shadow 220ms ease, background 220ms ease;
}
.session-item:hover {
  transform: translateY(-1px);
  border-color: rgba(45, 58, 48, 0.08);
  box-shadow: var(--shadow-soft);
}
.session-item.active {
  background: var(--bone-hi);
  border-color: rgba(134, 160, 122, 0.2);
}
.session-item.now {
  background: linear-gradient(135deg, rgba(193, 154, 107, 0.16), rgba(193, 154, 107, 0.06));
  border-color: rgba(193, 154, 107, 0.22);
}
.s-date {
  color: var(--stone);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 600;
}
.s-title {
  color: var(--forest);
  font-size: 14px;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.sidebar-foot {
  padding: 16px 18px 18px;
  border-top: 1px solid var(--line-faint);
  background: rgba(242, 232, 208, 0.66);
}
.sidebar-foot .label {
  color: var(--stone);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 600;
}
.user-display {
  margin-top: 6px;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 22px;
  line-height: 1.05;
  color: var(--forest);
}
.user-meta {
  margin-top: 8px;
  color: var(--moss);
  font-size: 13px;
}

.workspace {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: rgba(250, 244, 228, 0.92);
  border: 1px solid var(--line-faint);
  border-radius: 30px;
  box-shadow: var(--shadow-card);
}
.workspace::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 85% 16%, rgba(134, 160, 122, 0.10), transparent 20%),
    radial-gradient(circle at 18% 6%, rgba(193, 154, 107, 0.10), transparent 18%);
}
.view {
  position: absolute;
  inset: 0;
}
.view[hidden] { display: none; }

.view-boot {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  text-align: center;
}
.boot-wrap {
  max-width: 36rem;
}
.boot-label {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  color: var(--sage-deep);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  font-weight: 600;
}
.boot-label::before,
.boot-label::after {
  content: '';
  width: 28px;
  height: 1px;
  background: var(--sage);
}
.boot-headline {
  margin-top: 18px;
  font-family: var(--font-serif);
  font-size: clamp(48px, 6vw, 78px);
  line-height: 0.95;
  font-weight: 400;
  letter-spacing: -0.04em;
  color: var(--forest);
}
.boot-headline em {
  color: var(--sienna);
  font-style: italic;
}
.boot-sub {
  margin-top: 16px;
  color: var(--moss);
  font-size: 15px;
}
.boot-dots {
  display: inline-flex;
  gap: 6px;
  margin-top: 24px;
}
.boot-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--clay);
  animation: pulse 1.4s ease-in-out infinite;
}
.boot-dots span:nth-child(2) { animation-delay: 0.18s; }
.boot-dots span:nth-child(3) { animation-delay: 0.36s; }

.view-empty {
  overflow: auto;
  padding: 34px 36px 30px;
}
.empty-shell {
  min-height: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(340px, 0.95fr);
  gap: 28px;
  align-items: center;
}
.empty-copy {
  display: grid;
  gap: 20px;
}
.empty-label {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  color: var(--sage-deep);
  font-size: 12px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  font-weight: 600;
}
.empty-label::before {
  content: '';
  width: 36px;
  height: 1px;
  background: var(--sage);
}
.empty-headline {
  font-family: var(--font-serif);
  font-size: clamp(56px, 7vw, 112px);
  line-height: 0.94;
  font-weight: 400;
  letter-spacing: -0.05em;
  color: var(--forest);
}
.empty-headline em {
  color: var(--sienna);
  font-style: italic;
}
.empty-sub {
  max-width: 56ch;
  color: var(--moss);
  font-size: 18px;
  font-weight: 300;
}
.empty-sub strong {
  color: var(--forest);
  font-weight: 500;
}
.prompt-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  max-width: 720px;
}
.prompt-card {
  padding: 18px 18px 20px;
  background: rgba(255, 255, 255, 0.56);
  border: 1px solid rgba(45, 58, 48, 0.06);
  border-radius: 20px;
  box-shadow: var(--shadow-soft);
  text-align: left;
  transition: transform 220ms var(--ease-out), box-shadow 220ms ease, background 220ms ease, border-color 220ms ease;
}
.prompt-card:hover {
  transform: translateY(-2px);
  background: var(--bone-hi);
  border-color: rgba(134, 160, 122, 0.22);
  box-shadow: var(--shadow-hover);
}
.prompt-tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: var(--radius-pill);
  background: var(--clay-ghost);
  color: var(--sienna);
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 600;
}
.prompt-body {
  margin-top: 12px;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 22px;
  line-height: 1.25;
  color: var(--forest);
}
.empty-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.empty-start {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 20px;
  border-radius: var(--radius-pill);
  background: var(--clay);
  color: var(--bone-hi);
  box-shadow: 0 4px 16px rgba(193, 154, 107, 0.24);
  font-size: 14px;
  font-weight: 600;
}
.empty-foot {
  color: var(--stone);
  font-size: 13px;
}
.presence-card {
  position: relative;
  min-height: 520px;
  background: linear-gradient(180deg, rgba(250, 244, 228, 0.94), rgba(242, 232, 208, 0.86));
  border: 1px solid var(--line-faint);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.presence-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 14% 18%, rgba(193, 154, 107, 0.16), transparent 26%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.28), transparent 26%);
  pointer-events: none;
}
.presence-media {
  position: absolute;
  inset: 0;
}
.presence-media iframe {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 12%;
  right: -12%;
  width: auto;
  height: 100%;
  border: 0;
  background: transparent;
  pointer-events: none;
}
.presence-overlay {
  position: absolute;
  inset: auto 22px 22px 22px;
  display: grid;
  gap: 14px;
}
.presence-note,
.presence-list {
  background: rgba(250, 244, 228, 0.8);
  border: 1px solid rgba(45, 58, 48, 0.06);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-soft);
  backdrop-filter: blur(10px);
}
.presence-note {
  padding: 18px 20px;
}
.presence-note .label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--sage-deep);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  margin-bottom: 10px;
}
.presence-note .label::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--sage);
}
.presence-note h2 {
  font-family: var(--font-serif);
  font-size: 34px;
  line-height: 1;
  font-weight: 400;
  color: var(--forest);
  margin-bottom: 10px;
}
.presence-note h2 em {
  color: var(--sienna);
  font-style: italic;
}
.presence-note p {
  color: var(--moss);
  font-size: 14px;
  line-height: 1.7;
}
.presence-list {
  display: grid;
  gap: 1px;
  padding: 10px;
}
.presence-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding: 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.32);
}
.presence-row span {
  color: var(--stone);
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-weight: 600;
}
.presence-row strong {
  color: var(--forest);
  font-size: 13px;
  font-weight: 500;
}

.view-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px 18px;
  border-bottom: 1px solid var(--line-faint);
  background: rgba(250, 244, 228, 0.66);
}
.chat-who {
  display: grid;
  gap: 5px;
}
.chat-name {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 28px;
  line-height: 1;
  color: var(--sienna);
}
.chat-meta {
  color: var(--stone);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 600;
}
.chat-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.chat-actions button {
  padding: 10px 15px;
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.56);
  border: 1px solid rgba(45, 58, 48, 0.06);
  color: var(--forest);
  font-size: 13px;
  font-weight: 600;
}
.chat-actions button.danger {
  color: #8c4b3c;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 30px 20px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  scrollbar-width: thin;
  scrollbar-color: rgba(193, 154, 107, 0.34) transparent;
}
.messages::-webkit-scrollbar { width: 6px; }
.messages::-webkit-scrollbar-thumb { background: rgba(193, 154, 107, 0.34); border-radius: 999px; }
.msg {
  max-width: min(78%, 760px);
  display: grid;
  gap: 8px;
  animation: rise 320ms var(--ease-out);
}
.msg.user {
  align-self: flex-end;
}
.msg.maez {
  align-self: flex-start;
}
@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.msg-author {
  color: var(--stone);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 600;
}
.msg.maez .msg-author {
  color: var(--sienna);
  letter-spacing: 0;
  text-transform: none;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 18px;
}
.msg.user .msg-author {
  text-align: right;
}
.msg-body {
  padding: 15px 18px;
  border-radius: 22px;
  font-size: 15px;
  line-height: 1.72;
  white-space: pre-wrap;
  word-wrap: break-word;
  box-shadow: var(--shadow-soft);
}
.msg.maez .msg-body {
  background: linear-gradient(135deg, rgba(193, 154, 107, 0.20), rgba(193, 154, 107, 0.10));
  border: 1px solid rgba(193, 154, 107, 0.18);
  color: var(--forest);
  border-top-left-radius: 10px;
}
.msg.user .msg-body {
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(45, 58, 48, 0.06);
  color: var(--forest);
  border-top-right-radius: 10px;
}
.typing {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 999px;
  background: rgba(193, 154, 107, 0.12);
  color: var(--sienna);
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 600;
}
.typing .dots {
  display: inline-flex;
  gap: 5px;
}
.typing .dots i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--clay);
  animation: pulse 1.4s ease-in-out infinite;
}
.typing .dots i:nth-child(2) { animation-delay: 0.18s; }
.typing .dots i:nth-child(3) { animation-delay: 0.36s; }
@keyframes pulse {
  0%, 80%, 100% { opacity: 0.22; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1.05); }
}
.input-shell {
  padding: 18px 24px 22px;
  border-top: 1px solid var(--line-faint);
  background: rgba(250, 244, 228, 0.76);
}
.input-wrap {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 12px 12px 12px 18px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(45, 58, 48, 0.06);
  border-radius: 24px;
  box-shadow: var(--shadow-soft);
}
.input-wrap:focus-within {
  border-color: rgba(134, 160, 122, 0.24);
  box-shadow: 0 0 0 4px rgba(134, 160, 122, 0.10);
}
.input-wrap textarea {
  flex: 1;
  min-height: 24px;
  max-height: 180px;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--forest);
  font-size: 15px;
  line-height: 1.58;
}
.input-wrap textarea::placeholder {
  color: var(--stone);
}
.input-send {
  flex-shrink: 0;
  padding: 12px 18px;
  border-radius: var(--radius-pill);
  background: var(--clay);
  color: var(--bone-hi);
  box-shadow: 0 4px 16px rgba(193, 154, 107, 0.24);
  font-size: 14px;
  font-weight: 600;
}
.input-send:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.input-hint {
  margin-top: 10px;
  text-align: center;
  color: var(--stone);
  font-size: 12px;
}
.input-hint .k {
  display: inline-block;
  margin: 0 3px;
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--bone-warm);
  border: 1px solid rgba(45, 58, 48, 0.06);
  font-size: 11px;
}

@media (max-width: 1080px) {
  .empty-shell {
    grid-template-columns: 1fr;
    align-items: start;
  }
  .presence-card {
    min-height: 420px;
  }
}
@media (max-width: 920px) {
  .menu-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .brand-label {
    display: none;
  }
  .shell {
    width: min(100% - 20px, 1440px);
    grid-template-columns: 1fr;
  }
  .sidebar {
    position: fixed;
    left: 10px;
    top: 82px;
    bottom: 10px;
    width: min(82vw, 320px);
    z-index: 45;
    transform: translateX(calc(-100% - 20px));
    transition: transform 240ms var(--ease-out);
  }
  .sidebar.open {
    transform: translateX(0);
  }
  .workspace {
    min-height: 0;
  }
}
@media (max-width: 720px) {
  .maez-topbar {
    padding: 14px 16px;
  }
  .maez-nav {
    gap: 4px;
  }
  .maez-nav a,
  .maez-nav button {
    padding: 8px 12px;
    font-size: 13px;
  }
  .view-empty {
    padding: 24px 20px 20px;
  }
  .chat-header,
  .messages,
  .input-shell {
    padding-left: 18px;
    padding-right: 18px;
  }
  .prompt-grid {
    grid-template-columns: 1fr;
  }
  .presence-card {
    min-height: 360px;
  }
  .presence-media iframe {
    left: 0;
    right: 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation: none !important;
    transition: none !important;
  }
}
</style>
</head>
<body>
<header class="maez-topbar">
  <div class="topbar-left">
    <button class="menu-btn" id="menuBtn" aria-label="Toggle sessions" type="button">☰</button>
    <a class="brand" href="/">
      <span class="brand-dot" aria-hidden="true"></span>
      <span class="brand-mark">maez</span>
      <span class="brand-label">Continuity Channel</span>
    </a>
  </div>
  <nav class="maez-nav">
    <a href="/">Home</a>
    <a href="/dashboard">Field Station</a>
    <a href="https://github.com/Ramidoz/maez" target="_blank" rel="noreferrer">GitHub</a>
    <button class="cta" type="button" onclick="newConversation()">New chat</button>
    <button type="button" onclick="doLogout()">Sign out</button>
  </nav>
</header>

<main class="shell">
  <aside class="sidebar" id="sidebar">
    <div class="sidebar-head">
      <div class="sidebar-kicker">Sessions</div>
      <button class="new-convo" type="button" onclick="newConversation()">+ New</button>
    </div>
    <div class="session-list" id="sessions"></div>
    <div class="sidebar-foot">
      <div class="label">Signed in</div>
      <div class="user-display" id="userDisplay">resolving…</div>
      <div class="user-meta" id="userMeta">restoring continuity</div>
    </div>
  </aside>

  <section class="workspace">
    <div class="view view-boot" id="bootView">
      <div class="boot-wrap">
        <div class="boot-label">Securing continuity</div>
        <div class="boot-headline">Opening the <em>channel.</em></div>
        <div class="boot-sub">Checking your session and gathering memory.</div>
        <div class="boot-dots"><span></span><span></span><span></span></div>
      </div>
    </div>

    <div class="view view-empty" id="emptyView" hidden>
      <div class="empty-shell">
        <div class="empty-copy">
          <div class="empty-label">Channel open</div>
          <h1 class="empty-headline"><em>I'm here.</em></h1>
          <p class="empty-sub">
            This is not a disposable session. <strong>It keeps going.</strong>
            I remember what we talk about, what mattered, and where we left things. Start anywhere.
          </p>
          <div class="prompt-grid" id="promptGrid"></div>
          <div class="empty-actions">
            <button class="empty-start" type="button" onclick="startWriting()">Write your own question</button>
            <div class="empty-foot">Press <span class="k">Enter</span> to send and <span class="k">Shift+Enter</span> for a new line.</div>
          </div>
        </div>

        <div class="presence-card">
          <div class="presence-media">
            <iframe title="Maez presence" src="/maez_bg_zen.html?mx=0.63&my=0.29&presence=0.84&jumpt=3" loading="eager"></iframe>
          </div>
          <div class="presence-overlay">
            <div class="presence-note">
              <div class="label">Presence</div>
              <h2>Still <em>with you.</em></h2>
              <p>The same quiet presence from the landing page lives here too. The channel is just where that presence becomes conversation.</p>
            </div>
            <div class="presence-list">
              <div class="presence-row"><span>Memory</span><strong>kept across visits</strong></div>
              <div class="presence-row"><span>Tone</span><strong>warm, plain-English, calm</strong></div>
              <div class="presence-row"><span>Mode</span><strong>conversation, not task churn</strong></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="view view-chat" id="chatView" hidden>
      <div class="chat-header">
        <div class="chat-who">
          <div class="chat-name">maez</div>
          <div class="chat-meta">always on · always remembering</div>
        </div>
        <div class="chat-actions">
          <button type="button" onclick="newConversation()">New conversation</button>
          <button class="danger" type="button" onclick="doLogout()">Sign out</button>
        </div>
      </div>
      <div class="messages" id="msgs" role="log" aria-live="polite"></div>
      <div class="input-shell">
        <div class="input-wrap">
          <textarea id="msg" rows="1" placeholder="Say something to Maez…" autocomplete="off" aria-label="Message Maez"></textarea>
          <button class="input-send" id="sendBtn" type="button" onclick="sendMsg()">Send</button>
        </div>
        <div class="input-hint"><span class="k">Enter</span> to send · <span class="k">Shift</span> + <span class="k">Enter</span> for a new line</div>
      </div>
    </div>
  </section>
</main>

<script>
(function() {
  const qp = new URLSearchParams(location.search);
  const tt = qp.get('test_t');
  if (tt) {
    localStorage.setItem('maez_token', tt);
    const tn = qp.get('test_n');
    if (tn) localStorage.setItem('maez_name', tn);
    history.replaceState(null, '', '/app');
  }
})();

function getCookie(name) {
  const parts = document.cookie ? document.cookie.split('; ') : [];
  for (const part of parts) {
    const idx = part.indexOf('=');
    const key = idx === -1 ? part : part.slice(0, idx);
    if (key === name) return decodeURIComponent(idx === -1 ? '' : part.slice(idx + 1));
  }
  return '';
}

function currentToken() {
  return localStorage.getItem('maez_token') || getCookie('maez_token') || '';
}

function storeSession(nextToken, nextName) {
  if (nextToken) localStorage.setItem('maez_token', nextToken);
  if (nextName) localStorage.setItem('maez_name', nextName);
}

let token = currentToken();
let displayName = localStorage.getItem('maez_name') || '';
let conversationHistory = [];
let allSessions = [];
let userInfo = null;

const PROMPTS_PUBLIC = [
  { tag: 'Identity', body: 'What are you?' },
  { tag: 'Memory', body: 'What do you remember?' },
  { tag: 'Continuity', body: 'What have you been doing while I was gone?' },
  { tag: 'Greeting', body: 'Just say hi.' },
];
const PROMPTS_LINKED = [
  { tag: 'Last conversation', body: 'What do you remember about our last conversation?' },
  { tag: 'Today', body: "What's on my calendar today?" },
  { tag: 'Yesterday', body: 'What did I work on yesterday?' },
  { tag: 'Catch me up', body: 'Catch me up on where I left things.' },
];

function showView(id) {
  ['bootView', 'emptyView', 'chatView'].forEach((name) => {
    const el = document.getElementById(name);
    if (!el) return;
    if (name === id) el.removeAttribute('hidden');
    else el.setAttribute('hidden', '');
  });
}

function setSidebar(open) {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;
  if (typeof open === 'boolean') sidebar.classList.toggle('open', open);
  else sidebar.classList.toggle('open');
}

function focusComposer() {
  showView('chatView');
  setTimeout(() => {
    const ta = document.getElementById('msg');
    if (ta) ta.focus();
  }, 40);
}

function renderPrompts(linked) {
  const grid = document.getElementById('promptGrid');
  if (!grid) return;
  const set = linked ? PROMPTS_LINKED : PROMPTS_PUBLIC;
  grid.innerHTML = '';
  set.forEach((prompt) => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'prompt-card';
    card.innerHTML = '<div class="prompt-tag">' + prompt.tag + '</div><div class="prompt-body">' + prompt.body + '</div>';
    card.addEventListener('click', () => {
      startWriting();
      const input = document.getElementById('msg');
      input.value = prompt.body;
      resizeInput();
      sendMsg();
    });
    grid.appendChild(card);
  });
}

function renderSessions() {
  const el = document.getElementById('sessions');
  if (!el) return;
  el.innerHTML = '';

  const now = document.createElement('button');
  now.type = 'button';
  now.className = 'session-item now active';
  now.innerHTML = '<div class="s-date">Now</div><div class="s-title">Current conversation</div>';
  now.addEventListener('click', () => newConversation());
  el.appendChild(now);

  if (!allSessions.length) {
    const hint = document.createElement('div');
    hint.className = 'session-group';
    hint.textContent = 'No earlier sessions yet';
    el.appendChild(hint);
    return;
  }

  const group = document.createElement('div');
  group.className = 'session-group';
  group.textContent = 'Earlier';
  el.appendChild(group);

  allSessions.forEach((session, idx) => {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'session-item';
    const date = (session.date || '').slice(0, 10) || '—';
    const title = session.title || 'Conversation';
    item.innerHTML = '<div class="s-date">' + date + '</div><div class="s-title">' + title + '</div>';
    item.addEventListener('click', () => loadSession(idx));
    el.appendChild(item);
  });
}

function setActiveSession(idx) {
  const items = document.querySelectorAll('.session-item');
  items.forEach((item) => item.classList.remove('active'));
  if (idx === -1 && items[0]) items[0].classList.add('active');
  else if (items[idx + 1]) items[idx + 1].classList.add('active');
}

function appendMessage(role, text, animate) {
  const list = document.getElementById('msgs');
  const wrap = document.createElement('div');
  wrap.className = 'msg ' + role;
  if (!animate) wrap.style.animation = 'none';

  const author = document.createElement('div');
  author.className = 'msg-author';
  author.textContent = role === 'maez' ? 'maez' : (displayName || 'you');
  wrap.appendChild(author);

  const body = document.createElement('div');
  body.className = 'msg-body';
  body.textContent = text;
  wrap.appendChild(body);

  list.appendChild(wrap);
  list.scrollTop = list.scrollHeight;
}

function loadSession(idx) {
  const session = allSessions[idx];
  if (!session) return;
  const list = document.getElementById('msgs');
  list.innerHTML = '';
  conversationHistory = [];
  setActiveSession(idx);

  (session.messages || []).forEach((message) => {
    const visualRole = message.role === 'user' ? 'user' : 'maez';
    const historyRole = message.role === 'user' ? 'user' : 'assistant';
    appendMessage(visualRole, message.content, false);
    conversationHistory.push({ role: historyRole, content: message.content });
  });

  showView('chatView');
  if (innerWidth < 920) setSidebar(false);
}

function startWriting() {
  document.getElementById('msgs').innerHTML = '';
  conversationHistory = [];
  setActiveSession(-1);
  focusComposer();
  resizeInput();
}

function newConversation() {
  document.getElementById('msgs').innerHTML = '';
  conversationHistory = [];
  setActiveSession(-1);
  showView('emptyView');
  if (innerWidth < 920) setSidebar(false);
}

function showTyping() {
  const list = document.getElementById('msgs');
  const row = document.createElement('div');
  row.className = 'typing';
  row.id = 'typingRow';
  row.innerHTML = 'maez is thinking <span class="dots"><i></i><i></i><i></i></span>';
  list.appendChild(row);
  list.scrollTop = list.scrollHeight;
}

function hideTyping() {
  const row = document.getElementById('typingRow');
  if (row) row.remove();
}

function resizeInput() {
  const ta = document.getElementById('msg');
  if (!ta) return;
  ta.style.height = 'auto';
  ta.style.height = Math.min(180, ta.scrollHeight) + 'px';
}

async function sendMsg() {
  const input = document.getElementById('msg');
  const text = input.value.trim();
  if (!text) return;

  token = currentToken();
  if (!token) {
    doLogout();
    return;
  }

  input.value = '';
  resizeInput();
  showView('chatView');
  appendMessage('user', text, true);
  conversationHistory.push({ role: 'user', content: text });
  showTyping();

  const sendBtn = document.getElementById('sendBtn');
  sendBtn.disabled = true;
  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        web_token: token,
        message: text,
        history: conversationHistory.slice(-8),
      }),
    });
    if (response.status === 401) {
      doLogout();
      return;
    }
    const data = await response.json();
    hideTyping();
    if (data.error) {
      appendMessage('maez', 'Something bent for a moment. Try that again.', true);
      return;
    }
    appendMessage('maez', data.reply, true);
    conversationHistory.push({ role: 'assistant', content: data.reply });
  } catch (e) {
    hideTyping();
    appendMessage('maez', 'The line dropped for a moment. Try that again.', true);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function doLogout() {
  document.cookie = 'maez_token=; Max-Age=0; path=/; SameSite=Lax';
  localStorage.removeItem('maez_token');
  localStorage.removeItem('maez_name');
  token = '';
  displayName = '';
  conversationHistory = [];
  location.replace('/login');
}

async function boot() {
  token = currentToken();
  if (!token) {
    location.replace('/login');
    return;
  }

  storeSession(token, displayName);

  try {
    const response = await fetch('/history?web_token=' + encodeURIComponent(token));
    if (response.status === 401) {
      doLogout();
      return;
    }
    if (!response.ok) throw new Error('history failed');

    const data = await response.json();
    allSessions = data.sessions || [];
    userInfo = data.user || null;

    if (userInfo && userInfo.display_name) {
      displayName = userInfo.display_name;
      localStorage.setItem('maez_name', displayName);
    }

    const displayEl = document.getElementById('userDisplay');
    const metaEl = document.getElementById('userMeta');
    if (displayEl) displayEl.textContent = displayName || (userInfo && userInfo.username) || 'anon';
    if (metaEl) {
      metaEl.textContent = userInfo && userInfo.telegram_linked
        ? 'telegram history linked'
        : 'web account active';
    }

    renderPrompts(Boolean(userInfo && userInfo.telegram_linked));
    renderSessions();
    showView('emptyView');
    resizeInput();
  } catch (e) {
    doLogout();
  }
}

(function wireEvents() {
  const menuBtn = document.getElementById('menuBtn');
  if (menuBtn) {
    menuBtn.addEventListener('click', (event) => {
      event.preventDefault();
      setSidebar();
    });
  }

  const ta = document.getElementById('msg');
  if (ta) {
    ta.addEventListener('input', resizeInput);
    ta.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMsg();
      }
    });
  }
})();

boot();
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────
#  Session 11g — staging-only feature-flagged fast-lane adapter
#  ────────────────────────────────────────────────────────────────────
#  This block is COMPLETELY INERT unless MAEZ_LIVE_FAST_LANE_ENABLED=1
#  is set in the environment when this file is imported. Default: off.
#
#  When the flag is set:
#    • A single new route, /v1/fast-reply, is registered.
#    • The route validates a small request body and POSTs it to the
#      staging fast-lane HTTP boundary at 127.0.0.1:8765/v1/reply.
#    • It does NOT call ollama directly. It does NOT touch /chat.
#    • It does NOT touch the live UserAccounts/MemoryManager state.
#
#  When the flag is NOT set (default), nothing in this block runs:
#    • No imports, no route registration, no globals.
#    • Existing /chat, /login, /register etc. behavior is unchanged.
#    • The maez-web.service binary remains byte-identical at runtime.
#
#  Production guard: this adapter MUST stay off in production. The CORS
#  allowlist on the staging fast-lane service includes only loopback
#  origins, and the fast-lane service itself binds only to 127.0.0.1.
# ─────────────────────────────────────────────────────────────────────
_fl_imports_ok = False
if os.environ.get('MAEZ_LIVE_FAST_LANE_ENABLED') == '1':
    import json as _fl_json
    import urllib.error as _fl_err
    import urllib.request as _fl_req

    try:
        from core.public_user_shaping import (
            shape_public_request as _fl_shape,
            split_shaping_telemetry as _fl_split,
            ShapingRejected as _fl_ShapingRejected,
        )
        _fl_imports_ok = True
    except ImportError as _fl_import_err:
        logger.warning(
            'maez-live fast-lane adapter DISABLED — '
            'core.public_user_shaping unavailable: %s', _fl_import_err,
        )

if os.environ.get('MAEZ_LIVE_FAST_LANE_ENABLED') == '1' and _fl_imports_ok:

    _FAST_LANE_URL = os.environ.get(
        'MAEZ_LIVE_FAST_LANE_URL',
        'http://127.0.0.1:8765/v1/reply',
    )
    # Hard-pin to loopback regardless of what the env says — defense in
    # depth so a misconfigured env var can't redirect traffic off-box.
    _FAST_LANE_ALLOWED_HOSTS = ('127.0.0.1', 'localhost', '::1')

    # Session 11h — adapter version string. The fast-lane service records
    # this in audit metadata so adapter callers can be distinguished from
    # direct callers (curl, the consumer demo, the staging HTML page) at
    # forensic-replay time.
    _FAST_LANE_ADAPTER_VERSION = 'maez-live-fast-lane-adapter/0.2 (staging)'

    def _fast_lane_target_is_loopback(url: str) -> bool:
        try:
            from urllib.parse import urlparse as _up
            host = (_up(url).hostname or '').lower()
            return host in _FAST_LANE_ALLOWED_HOSTS
        except Exception:
            return False

    def _fast_lane_strip_response(upstream: dict) -> dict:
        """Convert the full fast-lane response into a SMALL adapter-side
        view that the public-facing client receives.

        Forwarded fields:
            reply       — the model reply text
            success     — bool
            error       — error dict if any
            backend     — backend name
            latency_ms  — total round-trip server time
            retry       — {'attempted', 'strategy', 'succeeded'}
            freshness   — per-source freshness states only

        EXCLUDED on purpose:
            full perception envelope, perception sources, prompt char counts,
            policy reason text, history persistence flags, redaction details,
            cache age numbers, internal selection reasons, audit_v markers
        """
        if not isinstance(upstream, dict):
            return {'success': False, 'error': {'code': 'bad_upstream', 'message': 'non-dict response'}}

        m = upstream.get('metrics') or {}
        stripped = {
            'success': bool(upstream.get('success', False)),
            'reply':   upstream.get('reply') or '',
            'backend': upstream.get('backend') or m.get('backend_name') or 'unknown',
            'latency_ms': int(m.get('total_ms', 0) or 0),
            'retry': {
                'attempted': bool(m.get('retry_attempted', False)),
                'strategy':  m.get('retry_strategy') or '',
                'succeeded': bool(m.get('retry_succeeded', False)),
            },
            'freshness': {
                'screen':       m.get('screen_freshness') or 'missing',
                'system_state': m.get('system_state_freshness') or 'missing',
                'calendar':     m.get('calendar_freshness') or 'missing',
            },
        }
        err = upstream.get('error')
        if err:
            # Forward only code+message; never any details that could
            # leak server-side state.
            if isinstance(err, dict):
                stripped['error'] = {
                    'code':    err.get('code') or 'unknown',
                    'message': err.get('message') or '',
                }
            else:
                stripped['error'] = {'code': 'unknown', 'message': str(err)}
        return stripped

    @app.route('/v1/fast-reply', methods=['POST'])
    def fast_reply_adapter():
        """Forward a request to the staging fast-lane boundary.

        Body: {"message": str, "trust_scope": str (optional, defaults
               to 'guest' for safety)}
        Returns: a stripped JSON view (see _fast_lane_strip_response).

        Auth: this route requires a valid web_token from the existing
        UserAccounts system. Public unauth callers cannot use it.

        Session 11h hardening:
          1. Calls core.public_user_shaping.shape_public_request() before
             the loopback hop. PII stripping is applied client-side here
             AND server-side via the fast-lane service. Two layers.
          2. Sends X-Maez-Adapter-Version header so the audit log can
             distinguish adapter calls from direct calls.
          3. Returns only a stripped client view (latency, retry, freshness)
             instead of the full upstream response. Internal envelope and
             policy details never leave the loopback.
        """
        if not _fast_lane_target_is_loopback(_FAST_LANE_URL):
            return jsonify({
                'success': False,
                'error': {'code': 'fast_lane_misconfigured',
                          'message': 'fast-lane URL must be loopback'},
            }), 500

        data = request.get_json(silent=True) or {}
        token = data.get('web_token', '')
        raw_message = (data.get('message') or '').strip()
        if not token or not raw_message:
            return jsonify({
                'success': False,
                'error': {'code': 'bad_request', 'message': 'Token and message required'},
            }), 400

        user = accounts.get_by_token(token)
        if not user:
            return jsonify({
                'success': False,
                'error': {'code': 'unauthorized', 'message': 'Invalid token'},
            }), 401

        # ── 11h: client-side PII shaping (defense-in-depth) ──
        # The fast-lane service ALSO runs schema validation and the
        # cloud redactor (if cloud is selected). This is the FIRST
        # of those defenses, applied before the loopback hop.
        try:
            shaped_full = _fl_shape(raw_message)
        except _fl_ShapingRejected as e:
            return jsonify({
                'success': False,
                'error': {'code': e.code, 'message': str(e)},
            }), 400
        upstream_body, _shaping_telemetry = _fl_split(shaped_full)

        # Force scope to guest regardless of what shaping returned (it
        # already does this, but defense-in-depth so the client can
        # never escalate by passing scope='public' to the shaper).
        upstream_body['trust_scope'] = 'guest'

        req = _fl_req.Request(
            _FAST_LANE_URL,
            data=_fl_json.dumps(upstream_body).encode('utf-8'),
            headers={
                'content-type':         'application/json',
                'accept':               'application/json',
                # 11h: structured adapter-version header
                'x-maez-adapter-version': _FAST_LANE_ADAPTER_VERSION,
                # legacy user-agent kept for backwards observability
                'user-agent':           _FAST_LANE_ADAPTER_VERSION,
                'origin':               'http://127.0.0.1:11437',
            },
            method='POST',
        )
        try:
            # Session 11j: 30.0s > GUEST_MAX_TIMEOUT_S (15.0) + loopback
            # round-trip margin. Must stay above the shaped guest budget or
            # the adapter will hang up before the fast-lane service responds.
            # Dropped from 210s after landing `think: false` in fast_backend_local
            # cut cold gemma4 replies to ~0.3s — the fat budget was masking a
            # thinking-model issue, not a real timeout need.
            with _fl_req.urlopen(req, timeout=30.0) as resp:
                body_bytes = resp.read()
                upstream_status = resp.status
                upstream_json = _fl_json.loads(body_bytes.decode('utf-8'))
        except _fl_err.HTTPError as e:
            try:
                upstream_json = _fl_json.loads(e.read().decode('utf-8'))
            except Exception:
                upstream_json = {'success': False, 'error': {'code': 'unparseable', 'message': str(e)}}
            return jsonify(_fast_lane_strip_response(upstream_json)), e.code
        except Exception as e:
            return jsonify({
                'success': False,
                'error': {'code': 'fast_lane_unreachable', 'message': str(e)},
            }), 502

        return jsonify(_fast_lane_strip_response(upstream_json)), upstream_status

    logger.info(
        'maez-live fast-lane adapter ENABLED (staging, 11h) — '
        'route /v1/fast-reply registered, target=%s, version=%s',
        _FAST_LANE_URL, _FAST_LANE_ADAPTER_VERSION,
    )
else:
    # Flag is off — log nothing, register nothing.
    pass


# ── /debug cockpit (Slice A) ─────────────────────────────────────────────
# Read-only owner-scoped surface for debugging Maez internals: daemon
# cycles, wondering state, approval cards, fabrication signal. All routes
# below are GET-only and gate on the owner-scoped auth pattern used by
# other private surfaces in this file: test_t dev bypass OR a valid token
# whose user is flagged private_owner_bridge=True. API handlers reuse
# existing helpers (_service_state_cached, _daemon_health) — no new
# daemon imports. Slice A ships only the route skeleton + services pane;
# wondering-core and cards/shells/fabrication panes come in slices B + C.

def _debug_auth_ok():
    """Gate for /debug and /api/debug/*. Test_t bypass matches existing
    private-surface pattern; production requires a real owner-bridge token.
    Returns True if the caller is authorized."""
    if request.args.get("test_t", "").strip():
        return True
    token = _request_token()
    if not token:
        return False
    user = accounts.get_by_token(token)
    if not user:
        return False
    return _is_private_owner_bridge(user)


@app.route("/debug")
def debug_page():
    if not _debug_auth_ok():
        return redirect("/login")
    return send_file(DEBUG_PAGE, mimetype="text/html")


@app.route("/debug/flow")
def debug_flow_mock():
    """Interactive organism-physiology view — live particles driven by
    /api/debug/* polling, plus click-to-preview toggles for embryonic /
    intended organs. Static reference is at /debug/flow/static."""
    if not _debug_auth_ok():
        return redirect("/login")
    return send_file(os.path.join(UI_DIR, "debug_flow_mock.html"),
                     mimetype="text/html")


@app.route("/debug/flow/static")
def debug_flow_static():
    """Static design reference — same layout, no JS, no live polling.
    Preserved for diff / print / review."""
    if not _debug_auth_ok():
        return redirect("/login")
    return send_file(os.path.join(UI_DIR, "debug_flow_static.html"),
                     mimetype="text/html")


@app.route("/debug/card-default")
def debug_card_default():
    """Side-by-side: today's card-first default vs trust-first default
    for the authenticated owner. Shows surfaces (CLI/Telegram/Web/Face)
    are interchangeable doors and the decision lives inside the brain."""
    if not _debug_auth_ok():
        return redirect("/login")
    return send_file(os.path.join(UI_DIR, "card_default.html"),
                     mimetype="text/html")


@app.route("/api/debug/services")
def api_debug_services():
    """Service + daemon health snapshot. Reuses existing cached helpers —
    no new systemctl calls per request beyond the TTL window."""
    if not _debug_auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    # 2026-04-23 Commit 7b: removed stale "llama-server-vision" from the
    # debug/services enumeration — no such unit exists on the machine.
    # Re-add when a multimodal endpoint is re-provisioned.
    services = {}
    for svc in ("maez", "maez-web", "llama-server"):
        services[svc] = _service_state_cached(svc)
    return jsonify({
        "services": services,
        "daemon": _daemon_health(),  # uses the 2.5s default — /health is slow
        "checked_at": _utcnow_iso(),
    })


# ── Slice B helpers: cognition.log tailing + wondering event parsing ─────

_COGNITION_LOG_PATH = "/home/rohit/maez/logs/cognition.log"
_DEBUG_WONDERING_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (?P<tag>[a-z_]+) \| (?P<rest>.*)$"
)
_DEBUG_KV_RE = re.compile(r"(\w+)=(.+?)(?=\s+\w+=|$)")


def _debug_tail_cognition_matching(keep_fn, n):
    """Read cognition.log start-to-end and keep the last n lines for which
    `keep_fn(line)` is True. Sliding-window via deque(maxlen=n) — O(n)
    memory regardless of file size. Needed because cognition.log is
    dominated by `| cycle |` + `| policy |` rows, so a naive tail misses
    the sparse `| wondering |` rows entirely."""
    from collections import deque
    matches = deque(maxlen=n)
    try:
        with open(_COGNITION_LOG_PATH, "r", errors="replace") as f:
            for line in f:
                if keep_fn(line):
                    matches.append(line)
    except FileNotFoundError:
        return []
    return list(matches)


def _debug_parse_cognition_line(line):
    """Parse one cognition.log line into a structured event, or None if
    the line doesn't match the expected `<ts> | <tag> | <rest>` shape."""
    m = _DEBUG_WONDERING_LINE_RE.match(line.rstrip("\n"))
    if not m:
        return None
    ts = m.group("ts")
    tag = m.group("tag")
    rest = m.group("rest")
    event = {"ts": ts, "tag": tag, "raw": rest}

    if tag == "wondering":
        # Parse: wid=N action=X evidence_tied=0 synth_state=Y rc=Z [cmd=...] [q=...]
        # cmd= and q= eat everything until the next known key or EOL — they
        # contain spaces. Extract them first, then parse the remainder KVs.
        cmd = None
        q = None
        head = rest
        cmd_pos = rest.find(" cmd=")
        q_pos = rest.find(" q=")
        trailing_start = None
        if cmd_pos != -1 and (q_pos == -1 or cmd_pos < q_pos):
            trailing_start = cmd_pos
            # cmd= may still have q= appended, but that's unlikely per emit — ignore
            cmd = rest[cmd_pos + 5:]
        elif q_pos != -1:
            trailing_start = q_pos
            q = rest[q_pos + 3:]
        if trailing_start is not None:
            head = rest[:trailing_start]
        # Parse remaining simple KVs from head
        for k, v in re.findall(r"(\w+)=([^\s]+)", head):
            event[k] = v
        if cmd is not None:
            event["cmd"] = cmd
        if q is not None:
            event["q"] = q
    elif tag == "cycle":
        # Parse: score=N primary=X topic=Y parent=Z labels=[...]
        score_m = re.search(r"score=(\d+)", rest)
        primary_m = re.search(r"primary=(\S+)", rest)
        topic_m = re.search(r"topic=(\S+)", rest)
        if score_m:
            event["score"] = int(score_m.group(1))
        if primary_m:
            event["primary"] = primary_m.group(1)
        if topic_m:
            event["topic"] = topic_m.group(1)
    # policy / other tags kept as raw-only

    return event


@app.route("/api/debug/wonderings")
def api_debug_wonderings():
    """Wondering board — full list from wonderings.db, newest first."""
    if not _debug_auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    try:
        from core.wonderings import get_store
        rows = get_store().list_all(limit=50)
        return jsonify({"wonderings": rows, "checked_at": _utcnow_iso()})
    except Exception as e:
        logger.warning("debug /api/debug/wonderings failed: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/debug/wondering-events")
def api_debug_wondering_events():
    """Last N `| wondering |` lines from cognition.log, parsed into dicts.
    ?limit=N (default 20, max 100)."""
    if not _debug_auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    try:
        limit = max(1, min(100, int(request.args.get("limit", 20))))
    except ValueError:
        limit = 20
    lines = _debug_tail_cognition_matching(
        lambda l: " | wondering | " in l, limit,
    )
    events = []
    for line in lines:
        ev = _debug_parse_cognition_line(line)
        if ev:
            events.append(ev)
    return jsonify({
        "events": events,
        "count": len(events),
        "checked_at": _utcnow_iso(),
    })


@app.route("/api/debug/cycle-timeline")
def api_debug_cycle_timeline():
    """Interleaved cycle + wondering events from cognition.log, newest
    first. Useful for 'what happened in the last N cycles' without reading
    raw logs. ?limit=N (default 50, max 200)."""
    if not _debug_auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    try:
        limit = max(1, min(200, int(request.args.get("limit", 50))))
    except ValueError:
        limit = 50
    lines = _debug_tail_cognition_matching(
        lambda l: (" | cycle | " in l) or (" | wondering | " in l),
        limit,
    )
    events = []
    for line in lines:
        ev = _debug_parse_cognition_line(line)
        if ev:
            events.append(ev)
    # Newest first for display
    events.reverse()
    return jsonify({
        "events": events[:limit],
        "count": min(len(events), limit),
        "checked_at": _utcnow_iso(),
    })


@app.route("/api/debug/cards")
def api_debug_cards():
    """Open + in-flight pending approval cards. Includes linked wondering_id
    when the params payload carries one, so the UI can cross-reference the
    board. Direct sqlite query rather than store.get_open_for_user() because
    we want all live cards across users, not just one user's."""
    if not _debug_auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    try:
        from core.pending_cards import DEFAULT_DB_PATH as CARDS_DB
        live = ("open", "deferred", "approved", "running")
        placeholders = ",".join("?" * len(live))
        conn = sqlite3.connect(str(CARDS_DB))
        conn.row_factory = sqlite3.Row
        cards = []
        for row in conn.execute(
            f"SELECT id, request_id, status, action, params_json, reason, "
            f"plain_english, channel, chat_id, created_at, defer_count "
            f"FROM pending_cards WHERE status IN ({placeholders}) "
            f"ORDER BY created_at DESC LIMIT 50",
            live,
        ):
            d = dict(row)
            params = {}
            try:
                params = json.loads(d.get("params_json") or "{}")
            except Exception:
                params = {}
            cmd = params.get("cmd") if isinstance(params, dict) else None
            wid = params.get("wondering_id") if isinstance(params, dict) else None
            origin = "wondering" if wid else ("chat" if d.get("chat_id") else "other")
            cards.append({
                "id": d["id"],
                "request_id": d["request_id"],
                "status": d["status"],
                "action": d["action"],
                "cmd": cmd,
                "reason": d.get("reason") or d.get("plain_english") or "",
                "channel": d.get("channel"),
                "origin": origin,
                "wondering_id": wid,
                "created_at": d.get("created_at"),
                "defer_count": d.get("defer_count") or 0,
            })
        conn.close()
        return jsonify({"cards": cards, "count": len(cards),
                         "checked_at": _utcnow_iso()})
    except Exception as e:
        logger.warning("debug /api/debug/cards failed: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/debug/recent-shells")
def api_debug_recent_shells():
    """Recent shell executions from wondering_probes. v1 shows wondering-
    originated only — CLI-origin shells aren't logged. Only non-deferred
    probes (those where run_shell actually executed) are returned; deferred
    probes have no real output yet."""
    if not _debug_auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    try:
        limit = max(1, min(100, int(request.args.get("limit", 20))))
    except ValueError:
        limit = 20
    try:
        from core import paths as _paths
        conn = sqlite3.connect(str(_paths.wonderings_db()))
        conn.row_factory = sqlite3.Row
        rows = []
        for row in conn.execute(
            "SELECT id, wondering_id, created_at, cmd, returncode, "
            "evidence_tied, stdout_excerpt, learning "
            "FROM wondering_probes WHERE deferred = 0 "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ):
            rows.append(dict(row))
        conn.close()
        return jsonify({
            "shells": rows,
            "count": len(rows),
            "origin": "wondering-only",
            "checked_at": _utcnow_iso(),
        })
    except Exception as e:
        logger.warning("debug /api/debug/recent-shells failed: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/debug/fabrication-feed")
def api_debug_fabrication_feed():
    """Fabrication / correction signal. Only returns feeds with real
    emitters today; detectors for chat-surface fabrication (honesty guard,
    state-claim suppression, self-claim hallucination) are listed as
    'no_detector' placeholders so the pane is honest about what it does
    and doesn't see."""
    if not _debug_auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    try:
        limit = max(1, min(50, int(request.args.get("limit", 20))))
    except ValueError:
        limit = 20

    # Real feed 1: cognition.log `synth_state=invalidated` events
    cog_lines = _debug_tail_cognition_matching(
        lambda l: " | wondering | " in l and "synth_state=invalidated" in l,
        limit,
    )
    cog_events = []
    for line in cog_lines:
        ev = _debug_parse_cognition_line(line)
        if ev:
            cog_events.append({
                "source": "cognition.log",
                "ts": ev.get("ts"),
                "wid": ev.get("wid"),
                "cmd": ev.get("cmd"),
                "signal": "synth_invalidated",
            })

    # Real feed 3 (promoted from placeholder): self_claim_audit events
    # emitted by core.self_claim_audit when a user-facing reply gets its
    # ungrounded internal claims rewritten. Tag set by that module's
    # _emit(); the parser below extracts surface / flagged / mode. Lines
    # where flagged=0 and mode=noop are dropped — only fires we care about.
    sca_lines = _debug_tail_cognition_matching(
        lambda l: " | self_claim_audit |" in l and "flagged=0" not in l,
        limit,
    )
    sca_events = []
    for line in sca_lines:
        try:
            # Shape: "<ts> | self_claim_audit | surface=X flagged=N mode=M kinds=K"
            prefix, _, rest = line.partition(" | self_claim_audit | ")
            ts = prefix.strip()
            kv = {}
            for part in rest.strip().split():
                if "=" in part:
                    k, v = part.split("=", 1)
                    kv[k] = v
            sca_events.append({
                "source": "cognition.log",
                "ts": ts,
                "surface": kv.get("surface"),
                "flagged": int(kv.get("flagged", "0")),
                "mode": kv.get("mode"),
                "kinds": kv.get("kinds"),
                "signal": "self_claim_audit",
            })
        except Exception:
            continue

    # Real feed 2: DB-backed ground truth — wondering_probes rows whose
    # learning matches LEARNING_SYNTH_BLOCKED and that actually ran.
    db_events = []
    try:
        from core import paths as _paths
        from core.wonderings import LEARNING_SYNTH_BLOCKED
        conn = sqlite3.connect(str(_paths.wonderings_db()))
        conn.row_factory = sqlite3.Row
        for row in conn.execute(
            "SELECT id, wondering_id, created_at, cmd, stdout_excerpt "
            "FROM wondering_probes "
            "WHERE deferred = 0 AND learning = ? "
            "ORDER BY id DESC LIMIT ?",
            (LEARNING_SYNTH_BLOCKED, limit),
        ):
            d = dict(row)
            db_events.append({
                "source": "wondering_probes",
                "probe_id": d["id"],
                "wid": d["wondering_id"],
                "cmd": d["cmd"],
                "stdout_excerpt": d.get("stdout_excerpt") or "",
                "signal": "synth_invalidated",
            })
        conn.close()
    except Exception as e:
        logger.debug("fabrication feed db read failed: %s", e)

    # Placeholders remaining for detectors that still don't exist.
    # self_claim_hallucination was promoted to a real feed above.
    placeholders = [
        {"source": "honesty_guard",
         "status": "no_detector",
         "note": "no emitter wired — track when honesty-guard events get a log line"},
        {"source": "state_claim_suppression",
         "status": "no_detector",
         "note": "no emitter wired — track when state-claim suppressions are logged"},
    ]

    return jsonify({
        "real_feeds": {
            "cognition_synth_invalidated": cog_events,
            "db_synth_blocked": db_events,
            "self_claim_audit": sca_events,
        },
        "placeholders": placeholders,
        "checked_at": _utcnow_iso(),
    })


@app.route("/api/debug/stats")
def api_debug_stats():
    """Wonderings.stats() over 1h and 24h windows. Source of truth for
    the stats strip — matches what the CLI `/wonderings` would produce."""
    if not _debug_auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    try:
        from core.wonderings import get_store
        store = get_store()
        return jsonify({
            "hour": store.stats(3600),
            "day": store.stats(86400),
            "checked_at": _utcnow_iso(),
        })
    except Exception as e:
        logger.warning("debug /api/debug/stats failed: %s", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=11437, debug=False)
