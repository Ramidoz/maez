# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Neutral topic helpers shared by live organs and offline diagnostics."""

from __future__ import annotations

import collections
import re

SUBTOPIC_MIN_HITS = 2

TOPIC_TAXONOMY = {
    "disk_usage": ["disk", "partition", "storage", "df ", "/dev/", "mount", "inode"],
    "cpu_load": ["cpu", "load average", "cores", "utilization"],
    "memory_usage": ["ram", "swap", "oom"],
    "gpu_state": ["gpu", "vram", "cuda", "nvidia", "temperature"],
    "network": [
        "network",
        "bandwidth",
        "latency",
        "packet",
        "connection",
        "download",
        "upload",
        "mbps",
    ],
    "processes": ["process", "pid", "zombie", "defunct", "top ", "htop"],
    "rohit_presence": ["arrived", "away", "absent", "left desk", "back at desk"],
    "git_workflow": [
        "commit",
        "push",
        "pull",
        "branch",
        "diff",
        "merge",
        "staged",
        "unstaged",
        "rebase",
        "stash",
        "uncommitted",
        "git add",
        "git log",
        "git status",
    ],
    "browser_usage": [
        "firefox",
        "chrome",
        "tab",
        "youtube",
        "browsing",
        "webpage",
        "browser",
        "web content",
        "isolated web",
    ],
    "development_tools": [
        "vscode",
        "vs code",
        "cursor",
        "claude",
        "opus",
        "sonnet",
        "ide",
        "editor",
        "coding",
        "debugg",
        "python",
        "script",
    ],
    "system_monitoring": [
        "logs",
        "daemon",
        "service",
        "maez",
        "health",
        "restart",
        "watcher",
        "monitoring",
        "journalctl",
        "systemctl",
    ],
    "general_presence": [
        "at desk",
        "focus",
        "session duration",
        "active",
        "present",
        "idle",
        "deep work",
        "working",
        "break",
    ],
    "calendar": ["meeting", "event", "calendar", "schedule", "appointment"],
    "telegram": ["telegram", "message", "conversation", "bot"],
    "web_content": ["news", "reddit", "github", "trending", "article"],
    "maez_self": ["soul", "reasoning", "cycle", "evolution", "consolidation"],
    "error": ["error", "fail", "crash", "exception", "timeout", "refused"],
    "security": ["firewall", "ufw", "ssh attempt", "unauthorized", "port"],
    "time_awareness": ["morning", "evening", "night", "circadian", "time of day"],
}

_ROHIT_ACTIVITY_SUBTOPICS = {
    "git_workflow",
    "browser_usage",
    "development_tools",
    "system_monitoring",
    "general_presence",
}

TOPIC_PARENT = {topic: "rohit_activity" for topic in _ROHIT_ACTIVITY_SUBTOPICS}

_SUBTOPIC_PRECEDENCE = [
    "git_workflow",
    "browser_usage",
    "development_tools",
    "system_monitoring",
    "general_presence",
]


def extract_topics(text: str) -> list[str]:
    """Extract topics from text using the controlled taxonomy."""

    text_lower = (text or "").lower()
    matches: dict[str, int] = {}
    for topic, keywords in TOPIC_TAXONOMY.items():
        count = sum(1 for keyword in keywords if keyword in text_lower)
        threshold = SUBTOPIC_MIN_HITS if topic in _ROHIT_ACTIVITY_SUBTOPICS else 1
        if count >= threshold:
            matches[topic] = count

    if not matches:
        words = re.findall(r"\b[a-z]{4,}\b", text_lower)
        stop = {
            "this",
            "that",
            "with",
            "from",
            "have",
            "been",
            "will",
            "your",
            "than",
            "they",
            "what",
            "when",
            "were",
            "there",
            "their",
            "which",
            "about",
            "would",
            "could",
            "should",
            "these",
            "those",
            "being",
            "some",
            "very",
            "just",
            "also",
            "into",
            "more",
            "other",
            "like",
        }
        filtered = [word for word in words if word not in stop]
        if filtered:
            freq = collections.Counter(filtered)
            return [word for word, _ in freq.most_common(3)]
        return ["unknown"]

    def sort_key(topic_name: str) -> tuple[int, int]:
        count = matches[topic_name]
        if topic_name in _ROHIT_ACTIVITY_SUBTOPICS:
            try:
                tie_break = _SUBTOPIC_PRECEDENCE.index(topic_name)
            except ValueError:
                tie_break = 99
        else:
            tie_break = 50
        return (-count, tie_break)

    return sorted(matches, key=sort_key)


def primary_topic(text: str) -> str:
    """Return the single primary topic of a text."""

    topics = extract_topics(text)
    return topics[0] if topics else "unknown"


def get_parent_topic(topic: str) -> str | None:
    """Return parent topic if topic is a subtopic, else None."""

    return TOPIC_PARENT.get(topic)
