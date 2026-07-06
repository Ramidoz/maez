# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
cognition_quality.py — Structural cognition quality subsystem for Maez.

Classifies, scores, and critiques reasoning outputs using deterministic
heuristics. No external APIs — pure structural analysis.

Integration points:
  - maez_daemon.py calls score_and_classify() before memory.store()
  - memory_manager.py applies anti-fixation penalty in _topic_rerank()
  - self_critique() remains as an offline/manual helper; the daemon's
    periodic self-shaping caller was removed on 2026-06-29.
"""

import collections
import logging
import logging.handlers
import re
from pathlib import Path

logger = logging.getLogger("maez")

# --- Logging ---
# Resolve via core.paths so the default works on any install. Legacy
# hardcode kept as a last-resort fallback.
try:
    from core.paths import logs_dir as _logs_dir
    COG_LOG = _logs_dir() / "cognition.log"
except Exception:
    COG_LOG = (
        Path(__file__).resolve().parents[2]
        / "logs" / "cognition.log"
    )
COG_LOG.parent.mkdir(parents=True, exist_ok=True)
# Slice 3 cleanup (2026-05-07/08): rotate cognition.log. NOTE: this
# handler is attached to `maez.cognition` only; `maez.envelope`
# (slice-3's chatty truncation logger) is a SIBLING in the maez
# logger tree, not a child of maez.cognition, so envelope records
# do NOT land here. They propagate up to `maez` and land in
# logs/maez.log via the daemon's RotatingFileHandler at
# daemon/maez_daemon.py. This rotation is hygiene for the
# cognition-specific records this file emits (cycle scores,
# critique events, behavior policy lines).
# 50MB × 10 files = 500MB ceiling.
_cog_handler = logging.handlers.RotatingFileHandler(
    COG_LOG, maxBytes=50 * 1024 * 1024, backupCount=10,
)
_cog_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
_cog_logger = logging.getLogger("maez.cognition")
_cog_logger.addHandler(_cog_handler)
_cog_logger.setLevel(logging.INFO)


# ══════════════════════════════════════════════════════════════════════
#  CONFIGURABLE CONSTANTS
# ══════════════════════════════════════════════════════════════════════

# Classification
MIN_ACTIONABLE_LENGTH = 30  # chars — below this, thought is too vague to be actionable
FIXATION_WINDOW = 10        # how many recent topics to track for fixation detection
FIXATION_THRESHOLD = 0.5    # fraction of recent topics that must match to flag fixation (tightened from 0.6)

# 2026-04-23: content-similarity gate on fixation.
# A topic-repetition signal alone generates false positives when a topic
# is keyword-driven by always-on context (e.g. Firefox is always a running
# process → `browser_usage` tag on every cycle even when content varies).
# Fire `fixation` only if the current text is also semantically close to
# recent same-topic texts. Jaccard over lowercased word tokens.
CONTENT_FIXATION_SIMILARITY = 0.45  # min Jaccard to count as content fixation

# 2026-04-23: topic-tagging threshold for the rohit_activity subtopics.
# These subtopics have short, common keywords (`firefox`, `chrome`, `tab`,
# `python`, `logs`, `active`) that appear in ambient context — process
# lists, active-window captures — regardless of whether the cycle's
# reasoning is actually about that topic. Require ≥2 distinct keyword
# hits before tagging one of these subtopics. System-hardware and
# external-context topics stay at ≥1 since they have more specific
# keyword signatures (`vram`, `cuda`, `reddit`, `meeting`).
SUBTOPIC_MIN_HITS = 2

# Scoring weights (0-100 scale)
SCORE_WEIGHT_LENGTH = 10        # bonus for adequate length
SCORE_WEIGHT_SPECIFICITY = 35   # bonus for concrete data references
SCORE_WEIGHT_NOVELTY = 25       # bonus for not repeating recent topics
SCORE_WEIGHT_GROUNDING = 20     # bonus for referencing perception data
SCORE_WEIGHT_ACTIONABLE = 20    # bonus for containing actionable content

# Self-critique thresholds
CRITIQUE_WINDOW = 20                    # cycles between critiques
CRITIQUE_CONSECUTIVE_LOW = 2            # consecutive windows below threshold before soul note
CRITIQUE_LOW_SCORE_THRESHOLD = 40       # average score below this triggers concern
CRITIQUE_FIXATION_DOMINANT_RATIO = 0.5  # fixation must dominate this fraction to trigger note

# Anti-fixation retrieval penalty
ANTIFIXATION_PENALTY_DEFAULT = 1.4      # multiplier on distance for recently-seen topics
ANTIFIXATION_PENALTY_MAX = 1.6          # hard cap
ANTIFIXATION_RECENCY_WINDOW = 10        # how many recent topics to penalize

# Consolidation quality
CONSOLIDATION_MIN_TOPICS = 3            # consolidation must mention at least N distinct topics
CONSOLIDATION_MIN_LENGTH = 200          # chars — consolidation must be at least this long

# Behavior policy thresholds
POLICY_FIXATION_STREAK = 3              # consecutive fixation labels before avoid_topics kicks in
POLICY_VAGUE_STREAK = 3                 # consecutive vague labels before requiring specificity
POLICY_LOW_SCORE_FLOOR = 30             # below this, trigger a retry
POLICY_RETRY_REJECT_LABELS = {          # label combos that trigger retry
    frozenset({'fixation', 'vague'}),
    frozenset({'fixation', 'baseline'}),
}
POLICY_EXPLORATORY_THRESHOLD = 0.6      # fixation ratio above this → exploratory mode


# ══════════════════════════════════════════════════════════════════════
#  TOPIC TAXONOMY — deterministic extraction
# ══════════════════════════════════════════════════════════════════════

TOPIC_TAXONOMY = {
    # System hardware
    'disk_usage':     ['disk', 'partition', 'storage', 'df ', '/dev/', 'mount', 'inode'],
    'cpu_load':       ['cpu', 'load average', 'cores', 'utilization'],
    'memory_usage':   ['ram', 'swap', 'oom'],
    'gpu_state':      ['gpu', 'vram', 'cuda', 'nvidia', 'temperature'],
    'network':        ['network', 'bandwidth', 'latency', 'packet', 'connection', 'download', 'upload', 'mbps'],
    'processes':      ['process', 'pid', 'zombie', 'defunct', 'top ', 'htop'],
    # the owner — presence (physical state)
    'rohit_presence': ['arrived', 'away', 'absent', 'left desk', 'back at desk'],
    # the owner — fine-grained activity subtopics (checked BEFORE parent)
    'git_workflow':       ['commit', 'push', 'pull', 'branch', 'diff', 'merge', 'staged', 'unstaged',
                           'rebase', 'stash', 'uncommitted', 'git add', 'git log', 'git status'],
    'browser_usage':      ['firefox', 'chrome', 'tab', 'youtube', 'browsing', 'webpage', 'browser',
                           'web content', 'isolated web'],
    'development_tools':  ['vscode', 'vs code', 'cursor', 'claude', 'opus', 'sonnet', 'ide', 'editor',
                           'coding', 'debugg', 'python', 'script'],
    'system_monitoring':  ['logs', 'daemon', 'service', 'maez', 'health', 'restart', 'watcher',
                           'monitoring', 'journalctl', 'systemctl'],
    'general_presence':   ['at desk', 'focus', 'session duration', 'active', 'present',
                           'idle', 'deep work', 'working', 'break'],
    # External context
    'calendar':       ['meeting', 'event', 'calendar', 'schedule', 'appointment'],
    'telegram':       ['telegram', 'message', 'conversation', 'bot'],
    'web_content':    ['news', 'reddit', 'github', 'trending', 'article'],
    'maez_self':      ['soul', 'reasoning', 'cycle', 'evolution', 'consolidation'],
    'error':          ['error', 'fail', 'crash', 'exception', 'timeout', 'refused'],
    'security':       ['firewall', 'ufw', 'ssh attempt', 'unauthorized', 'port'],
    'time_awareness': ['morning', 'evening', 'night', 'circadian', 'time of day'],
}

# Topics that are children of rohit_activity — checked first, parent is fallback
_ROHIT_ACTIVITY_SUBTOPICS = {
    'git_workflow', 'browser_usage', 'development_tools',
    'system_monitoring', 'general_presence',
}

# Map from subtopic → parent for logging and backward compat
TOPIC_PARENT = {t: 'rohit_activity' for t in _ROHIT_ACTIVITY_SUBTOPICS}

# Precedence: fine-grained subtopics beat the parent. Among subtopics,
# highest keyword match count wins. Among equal counts, this order breaks ties.
_SUBTOPIC_PRECEDENCE = [
    'git_workflow', 'browser_usage', 'development_tools',
    'system_monitoring', 'general_presence',
]


def extract_topics(text: str) -> list[str]:
    """Extract topics from text using the controlled taxonomy.
    Returns list of matched topic keys, sorted by match count (descending).
    Fine-grained subtopics take precedence over parent categories.
    Falls back to simple keyword extraction if no taxonomy match."""
    text_lower = text.lower()
    matches: dict[str, int] = {}
    for topic, keywords in TOPIC_TAXONOMY.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        # rohit_activity subtopics (browser_usage, development_tools, etc.)
        # use short, generic keywords that appear in ambient context —
        # require ≥2 distinct hits before tagging to suppress single-keyword
        # false positives (e.g. "firefox" in every process list).
        threshold = SUBTOPIC_MIN_HITS if topic in _ROHIT_ACTIVITY_SUBTOPICS else 1
        if count >= threshold:
            matches[topic] = count

    if not matches:
        # Fallback: extract nouns/keywords by frequency
        words = re.findall(r'\b[a-z]{4,}\b', text_lower)
        stop = {'this', 'that', 'with', 'from', 'have', 'been', 'will', 'your',
                'than', 'they', 'what', 'when', 'were', 'there', 'their', 'which',
                'about', 'would', 'could', 'should', 'these', 'those', 'being',
                'some', 'very', 'just', 'also', 'into', 'more', 'other', 'like'}
        words = [w for w in words if w not in stop]
        if words:
            freq = collections.Counter(words)
            return [w for w, _ in freq.most_common(3)]
        return ['unknown']

    # Precedence: if any subtopic matched, prefer it over non-subtopics of equal weight
    # Sort by: (1) match count desc, (2) subtopic precedence for ties
    def sort_key(topic_name):
        count = matches[topic_name]
        # Lower precedence index = higher priority for ties
        if topic_name in _ROHIT_ACTIVITY_SUBTOPICS:
            try:
                tie_break = _SUBTOPIC_PRECEDENCE.index(topic_name)
            except ValueError:
                tie_break = 99
        else:
            tie_break = 50  # non-subtopics sort middle
        return (-count, tie_break)

    return sorted(matches, key=sort_key)


def primary_topic(text: str) -> str:
    """Return the single primary topic of a text."""
    topics = extract_topics(text)
    return topics[0] if topics else 'unknown'


def get_parent_topic(topic: str) -> str | None:
    """Return parent topic if topic is a subtopic, else None."""
    return TOPIC_PARENT.get(topic)


# ══════════════════════════════════════════════════════════════════════
#  FAILURE CLASSIFIER — multi-label
# ══════════════════════════════════════════════════════════════════════

# Label definitions:
#   fixation    — repeats a topic that dominated recent cycles
#   vague       — lacks concrete data references or specifics
#   repetition  — semantically similar to very recent output
#   baseline    — reports normal/expected system state as if noteworthy
#   actionable  — contains a concrete suggestion or flag (positive label)
#   insightful  — offers a novel observation not in recent memory (positive label)

BASELINE_PHRASES = [
    'everything is running smoothly', 'all systems normal', 'no anomalies',
    'operating within expected parameters', 'nothing out of the ordinary',
    'system is stable', 'no issues detected', 'running normally',
    'within normal range', 'as expected',
]

ACTIONABLE_SIGNALS = [
    'should', 'could', 'consider', 'recommend', 'suggest', 'flag',
    'alert', 'warning', 'notice', 'attention', 'investigate',
    'might want to', 'watch for', 'keep an eye on', 'unusual',
]

SPECIFICITY_PATTERNS = [
    r'\d+\.?\d*\s*%',       # percentages
    r'\d+\.?\d*\s*[GMKT]B', # data sizes
    r'\d+\.?\d*\s*°C',      # temperatures
    r'PID\s*\d+',           # process IDs
    r'/\w+/\w+',            # file paths
    r'\d+\.\d+\.\d+',       # version numbers or IPs
]


def _token_set(text: str) -> set[str]:
    """Token set used for content-similarity checks. Lowercased alphanumeric words only,
    stripped of high-frequency stopwords so similarity reflects content rather than
    filler overlap."""
    stop = {'is', 'the', 'a', 'an', 'and', 'or', 'but', 'to', 'of', 'in', 'on', 'at',
            'for', 'with', 'from', 'by', 'your', 'you', 'i', 'are', 'be', 'been',
            'this', 'that', 'it', 'its', 'system', 'cycle', 'now', 'nothing', 'no'}
    return {w for w in re.findall(r'\b[a-z0-9]{3,}\b', text.lower()) if w not in stop}


def _max_jaccard(text: str, recent_texts: list[str]) -> float:
    """Max Jaccard similarity between text's token-set and any of the recent texts'.
    Returns 0.0 if inputs empty."""
    if not recent_texts:
        return 0.0
    cur = _token_set(text)
    if not cur:
        return 0.0
    best = 0.0
    for rt in recent_texts:
        prev = _token_set(rt)
        if not prev:
            continue
        union = len(cur | prev)
        if union == 0:
            continue
        sim = len(cur & prev) / union
        if sim > best:
            best = sim
    return best


def _vague_label_dedup_key(label: str) -> str:
    """Canonical dedup key for cognition labels.

    T2.B (2026-05-04 15-agent audit): ``classify()`` had a raw
    ``labels == ['vague']`` comparison and a ``dict.fromkeys``
    dedup that quietly assumed labels were already case- and
    whitespace-canonical. Both checks broke if a future code
    change introduced a label like ``'Vague'`` or ``' vague '``.

    Lifting the comparison into a named helper makes the dedup
    invariant explicit. A regression guard pins this function's
    existence in source so a refactor can't silently inline it
    back into ``classify()``.

    Returns ``label`` case-folded and stripped — the canonical
    form used for both equality checks and dedup-key sets.
    """
    return (label or "").strip().casefold()


def classify(text: str, recent_topics: list[str] = None,
             recent_texts: list[str] = None) -> dict:
    """Classify a thought into multi-label categories.

    Returns dict with:
        labels: list[str]       — all applicable labels
        primary: str            — single dominant label
        topic: str              — primary topic from taxonomy
        topics: list[str]       — all matched topics

    `recent_texts` is optional; when provided, fixation requires both
    topic-repetition AND content-similarity to a recent same-topic text.
    Without it, falls back to the legacy topic-only rule (backward-
    compatible for callers that don't track text history).
    """
    text_lower = text.lower()
    labels = []
    recent_topics = recent_topics or []
    recent_texts = recent_texts or []

    topics = extract_topics(text)
    topic = topics[0] if topics else 'unknown'

    # Check fixation — topic dominates recent history AND content is similar.
    # The content gate prevents keyword-driven false positives (e.g. a topic
    # that auto-triggers from ambient context like Firefox-in-process-list).
    if recent_topics and topic != 'unknown':
        topic_freq = sum(1 for t in recent_topics[-FIXATION_WINDOW:] if t == topic)
        if len(recent_topics) >= 3 and topic_freq / min(len(recent_topics), FIXATION_WINDOW) >= FIXATION_THRESHOLD:
            # Topic repeats. Require content overlap with at least one recent
            # text of the same topic before labeling fixation. If no recent
            # texts supplied (legacy caller), fall back to topic-only signal.
            if recent_texts:
                # Pair recent_topics with recent_texts by position; take the
                # tail window same as topic check
                same_topic_texts = []
                window = max(0, len(recent_topics) - FIXATION_WINDOW)
                paired = list(zip(
                    recent_topics[window:], recent_texts[window:], strict=False
                ))
                for rt_topic, rt_text in paired:
                    if rt_topic == topic and rt_text:
                        same_topic_texts.append(rt_text)
                if same_topic_texts:
                    sim = _max_jaccard(text, same_topic_texts)
                    if sim >= CONTENT_FIXATION_SIMILARITY:
                        labels.append('fixation')
                # no matching-topic texts → topic match was by-name-only, don't fixate
            else:
                # Legacy mode: topic-repetition alone triggers fixation.
                labels.append('fixation')

    # Check vague
    if len(text.strip()) < MIN_ACTIONABLE_LENGTH:
        labels.append('vague')
    else:
        has_specifics = any(re.search(p, text) for p in SPECIFICITY_PATTERNS)
        if not has_specifics:
            labels.append('vague')

    # Check baseline
    if any(phrase in text_lower for phrase in BASELINE_PHRASES):
        labels.append('baseline')

    # Check actionable
    if any(signal in text_lower for signal in ACTIONABLE_SIGNALS):
        labels.append('actionable')

    # Check insightful — has specifics AND not fixation AND not baseline
    has_specifics = any(re.search(p, text) for p in SPECIFICITY_PATTERNS)
    if has_specifics and 'fixation' not in labels and 'baseline' not in labels:
        labels.append('insightful')

    # Check repetition — exact substring match with recent (simple heuristic)
    # This is a lightweight check; semantic similarity is in memory retrieval
    if not labels or labels == ['vague']:
        labels.append('vague')

    # Deduplicate
    labels = list(dict.fromkeys(labels))

    # Primary label: prefer negative labels for awareness, positive if clean
    priority = ['fixation', 'vague', 'baseline', 'repetition', 'actionable', 'insightful']
    primary_label = 'neutral'
    for p in priority:
        if p in labels:
            primary_label = p
            break

    parent = get_parent_topic(topic)
    return {
        'labels': labels,
        'primary': primary_label,
        'topic': topic,
        'parent_topic': parent,  # None if not a subtopic
        'topics': topics,
    }


# ══════════════════════════════════════════════════════════════════════
#  QUALITY SCORER — 0-100, structural heuristics
# ══════════════════════════════════════════════════════════════════════

def score(text: str, classification: dict, recent_topics: list[str] = None) -> int:
    """Score a thought on 0-100 scale using structural heuristics.

    Components:
        length    (0-10): adequate length for meaningful content
        specificity (0-25): references concrete data (%, GB, °C, PIDs, paths)
        novelty   (0-25): topic differs from recent N cycles
        grounding (0-20): references perception data (system state, screen, calendar)
        actionable (0-20): contains suggestion or alert language
    """
    recent_topics = recent_topics or []
    s = 0

    # Length (0-10)
    length = len(text.strip())
    if length >= 100:
        s += SCORE_WEIGHT_LENGTH
    elif length >= 50:
        s += SCORE_WEIGHT_LENGTH // 2

    # Specificity (0-25)
    spec_count = sum(1 for p in SPECIFICITY_PATTERNS if re.search(p, text))
    s += min(spec_count * 8, SCORE_WEIGHT_SPECIFICITY)

    # Novelty (0-25)
    topic = classification.get('topic', 'unknown')
    if recent_topics:
        recent_window = recent_topics[-FIXATION_WINDOW:]
        topic_freq = sum(1 for t in recent_window if t == topic)
        novelty_ratio = 1.0 - (topic_freq / max(len(recent_window), 1))
        s += int(novelty_ratio * SCORE_WEIGHT_NOVELTY)
    else:
        s += SCORE_WEIGHT_NOVELTY  # no history = novel by default

    # Grounding (0-20)
    grounding_terms = ['cpu', 'ram', 'gpu', 'disk', 'process', 'screen',
                       'calendar', 'presence', 'network']
    grounding_hits = sum(1 for g in grounding_terms if g in text.lower())
    s += min(grounding_hits * 5, SCORE_WEIGHT_GROUNDING)

    # Actionable (0-20)
    if 'actionable' in classification.get('labels', []):
        s += SCORE_WEIGHT_ACTIONABLE
    elif 'insightful' in classification.get('labels', []):
        s += SCORE_WEIGHT_ACTIONABLE // 2

    return min(s, 100)


# ══════════════════════════════════════════════════════════════════════
#  SCORE AND CLASSIFY — single entry point for daemon
# ══════════════════════════════════════════════════════════════════════

# In-memory ring buffer of recent topics for fixation detection.
# 2026-04-23: added _recent_texts in parallel so fixation detection can
# also check content similarity, not just topic repetition.
_recent_topics: list[str] = []
_recent_texts: list[str] = []
_recent_scores: list[int] = []
_low_critique_streak = 0  # consecutive critique windows below threshold


def score_and_classify(text: str) -> dict:
    """Score and classify a thought. Returns enriched metadata dict.

    Called by daemon BEFORE memory.store() so metadata is written once.
    Returns dict with keys: cog_score, cog_primary, cog_labels, cog_topic, cog_topics
    """
    # 05-B1: snapshot buffer lengths before the compute so a mid-function
    # raise can roll back any partial append. Without this, a classify()
    # that succeeded and appended to _recent_topics but a score() that
    # raised would leave the buffers in an inconsistent (topic-without-
    # matching-score) state that corrupts fixation detection + behavior
    # policy on every subsequent turn.
    _topics_len = len(_recent_topics)
    _texts_len = len(_recent_texts)
    _scores_len = len(_recent_scores)
    _labels_len = len(_recent_labels)
    try:
        classification = classify(text, _recent_topics, _recent_texts)
        quality = score(text, classification, _recent_topics)

        # Update ring buffers
        _recent_topics.append(classification['topic'])
        if len(_recent_topics) > 50:
            _recent_topics[:] = _recent_topics[-50:]
        _recent_texts.append(text)
        if len(_recent_texts) > 50:
            _recent_texts[:] = _recent_texts[-50:]
        _recent_scores.append(quality)
        if len(_recent_scores) > 50:
            _recent_scores[:] = _recent_scores[-50:]
        _recent_labels.append(classification['labels'])
        if len(_recent_labels) > 50:
            _recent_labels[:] = _recent_labels[-50:]

        parent = classification.get('parent_topic')
        result = {
            'cog_score': quality,
            'cog_primary': classification['primary'],
            'cog_labels': ','.join(classification['labels']),
            'cog_topic': classification['topic'],
            'cog_topics': ','.join(classification['topics'][:3]),
        }
        if parent:
            result['cog_parent_topic'] = parent

        parent_str = f" parent={parent}" if parent else ""
        _cog_logger.info(
            "cycle | score=%d primary=%s topic=%s%s labels=%s",
            quality, classification['primary'],
            classification['topic'], parent_str, classification['labels'],
        )

        return result

    except Exception as e:
        # Roll each buffer back to its pre-call length so a partial
        # append doesn't leave the trio desynced for future callers.
        try:
            if len(_recent_topics) > _topics_len:
                _recent_topics[:] = _recent_topics[:_topics_len]
            if len(_recent_texts) > _texts_len:
                _recent_texts[:] = _recent_texts[:_texts_len]
            if len(_recent_scores) > _scores_len:
                _recent_scores[:] = _recent_scores[:_scores_len]
            if len(_recent_labels) > _labels_len:
                _recent_labels[:] = _recent_labels[:_labels_len]
        except Exception:
            pass
        logger.error("Cognition scoring failed (safe fallback): %s", e)
        return {
            'cog_score': 50,
            'cog_primary': 'unknown',
            'cog_labels': 'error',
            'cog_topic': 'unknown',
            'cog_topics': 'unknown',
        }


# ══════════════════════════════════════════════════════════════════════
#  SELF-CRITIQUE — offline/manual helper
# ══════════════════════════════════════════════════════════════════════

def self_critique() -> dict | None:
    """Analyze recent cognition quality. Returns critique dict or None.

    Offline/manual helper. Only writes soul notes if:
      - 2+ consecutive windows score below CRITIQUE_LOW_SCORE_THRESHOLD, AND
      - fixation is the dominant failure mode (>50% of labels)
    """
    global _low_critique_streak

    if len(_recent_scores) < CRITIQUE_WINDOW:
        return None

    window_scores = _recent_scores[-CRITIQUE_WINDOW:]
    window_topics = _recent_topics[-CRITIQUE_WINDOW:]

    avg_score = sum(window_scores) / len(window_scores)
    min_score = min(window_scores)
    max_score = max(window_scores)

    # Count label frequencies from recent classifications
    # (We re-classify from topics since we don't store labels in the buffer)
    topic_counts = collections.Counter(window_topics)
    dominant_topic, dominant_count = topic_counts.most_common(1)[0]
    fixation_ratio = dominant_count / len(window_topics)

    # Unique topic ratio
    unique_topics = len(set(window_topics))
    topic_diversity = unique_topics / len(window_topics)

    critique = {
        'avg_score': round(avg_score, 1),
        'min_score': min_score,
        'max_score': max_score,
        'dominant_topic': dominant_topic,
        'fixation_ratio': round(fixation_ratio, 2),
        'topic_diversity': round(topic_diversity, 2),
        'unique_topics': unique_topics,
        'window_size': len(window_scores),
        'should_write_soul_note': False,
        'soul_note_reason': None,
    }

    # Track consecutive low windows
    if avg_score < CRITIQUE_LOW_SCORE_THRESHOLD:
        _low_critique_streak += 1
    else:
        _low_critique_streak = 0

    # Only trigger soul note if:
    # 1) 2+ consecutive low windows, AND
    # 2) fixation is dominant failure mode
    if (_low_critique_streak >= CRITIQUE_CONSECUTIVE_LOW
            and fixation_ratio >= CRITIQUE_FIXATION_DOMINANT_RATIO):
        critique['should_write_soul_note'] = True
        critique['soul_note_reason'] = (
            f"Cognition quality low for {_low_critique_streak} consecutive windows. "
            f"Average score {avg_score:.0f}/100. "
            f"Fixation on '{dominant_topic}' ({fixation_ratio:.0%} of thoughts). "
            f"Topic diversity: {topic_diversity:.0%}. "
            f"Vary observations — attend to what changed, not what stayed the same."
        )

    _cog_logger.info(
        "critique | avg=%.1f min=%d max=%d dominant=%s fixation=%.2f diversity=%.2f streak=%d note=%s",
        avg_score, min_score, max_score, dominant_topic,
        fixation_ratio, topic_diversity, _low_critique_streak,
        critique['should_write_soul_note'],
    )

    # Check proposal trigger after critique
    try:
        from skills.evolution_engine import check_proposal_trigger
        check_proposal_trigger(critique)
    except ImportError:
        pass
    except Exception as e:
        logger.debug("Proposal trigger check failed: %s", e)

    return critique


def format_for_prompt(critique: dict | None) -> str:
    """Format the latest critique for injection into reasoning prompt."""
    if critique is None:
        return ""

    lines = [f"[COGNITION QUALITY — last {critique['window_size']} cycles]"]
    lines.append(f"  Avg score: {critique['avg_score']}/100")
    lines.append(f"  Topic diversity: {critique['topic_diversity']:.0%} ({critique['unique_topics']} unique)")

    if critique['fixation_ratio'] >= 0.4:
        lines.append(f"  WARNING: Fixating on '{critique['dominant_topic']}' ({critique['fixation_ratio']:.0%})")
        lines.append("  Vary your attention. Look at what CHANGED, not what stayed the same.")

    return '\n'.join(lines)


# ══════════════════════════════════════════════════════════════════════
#  ANTI-FIXATION RETRIEVAL PENALTY
# ══════════════════════════════════════════════════════════════════════

def get_fixation_penalty(topic: str) -> float:
    """Return distance multiplier penalty for a topic if it's been recently dominant.

    Returns 1.0 (no penalty) to ANTIFIXATION_PENALTY_MAX.
    Configurable via ANTIFIXATION_PENALTY_DEFAULT.
    """
    if not _recent_topics:
        return 1.0

    recent = _recent_topics[-ANTIFIXATION_RECENCY_WINDOW:]
    freq = sum(1 for t in recent if t == topic)
    ratio = freq / len(recent)

    if ratio >= FIXATION_THRESHOLD:
        return min(ANTIFIXATION_PENALTY_DEFAULT, ANTIFIXATION_PENALTY_MAX)
    elif ratio >= 0.3:
        # Gradual penalty
        return 1.0 + (ANTIFIXATION_PENALTY_DEFAULT - 1.0) * (ratio / FIXATION_THRESHOLD)
    return 1.0


def get_recent_topics() -> list[str]:
    """Return copy of recent topic buffer for external use."""
    return list(_recent_topics)


# In-memory ring buffer for recent labels (parallel to _recent_topics/_recent_scores)
_recent_labels: list[list[str]] = []


# ══════════════════════════════════════════════════════════════════════
#  BEHAVIOR POLICY — converts cognition state into reasoning guidance
# ══════════════════════════════════════════════════════════════════════

def get_behavior_policy() -> dict:
    """Generate a behavior policy from recent cognition state.

    Returns structured dict that the daemon converts into prompt directives.
    Safe fallback: returns neutral policy on any error.
    """
    try:
        recent_t = _recent_topics[-10:] if _recent_topics else []
        recent_s = _recent_scores[-10:] if _recent_scores else []
        recent_l = _recent_labels[-10:] if _recent_labels else []

        policy = {
            'avoid_topics': [],
            'prefer_topics': [],
            'require_perception_grounding': False,
            'require_metric_specificity': False,
            'force_new_angle': False,
            'reflection_mode': 'normal',  # normal / corrective / exploratory
            'retry_eligible': False,
            'directive': '',  # single-sentence instruction for the LLM
        }

        if not recent_t:
            return policy

        avg_score = sum(recent_s) / len(recent_s) if recent_s else 50
        topic_counts = collections.Counter(recent_t)
        dominant_topic, dominant_count = topic_counts.most_common(1)[0]
        fixation_ratio = dominant_count / len(recent_t)

        # Flatten recent labels
        flat_labels = [l for ll in recent_l for l in ll]
        collections.Counter(flat_labels)

        # --- Fixation response ---
        fixation_streak = 0
        for t in reversed(recent_t):
            if t == dominant_topic:
                fixation_streak += 1
            else:
                break

        if fixation_streak >= POLICY_FIXATION_STREAK:
            policy['avoid_topics'].append(dominant_topic)
            policy['force_new_angle'] = True

        if fixation_ratio >= POLICY_EXPLORATORY_THRESHOLD:
            policy['reflection_mode'] = 'exploratory'
            # Suggest topics NOT recently seen
            all_topics = set(TOPIC_TAXONOMY.keys())
            seen = set(recent_t)
            unseen = list(all_topics - seen)
            if unseen:
                policy['prefer_topics'] = unseen[:3]

        elif fixation_ratio >= FIXATION_THRESHOLD:
            policy['reflection_mode'] = 'corrective'
            policy['avoid_topics'].append(dominant_topic)

        # --- Vague response ---
        vague_streak = 0
        for ll in reversed(recent_l):
            if 'vague' in ll:
                vague_streak += 1
            else:
                break

        if vague_streak >= POLICY_VAGUE_STREAK:
            policy['require_metric_specificity'] = True
            policy['require_perception_grounding'] = True

        # --- Build directive sentence ---
        parts = []
        if policy['avoid_topics']:
            readable = ', '.join(t.replace('_', ' ') for t in policy['avoid_topics'])
            parts.append(f"Do NOT repeat observations about {readable} unless the data genuinely changed")
        if policy['force_new_angle']:
            parts.append("approach from a completely different angle or perception source")
        if policy['require_metric_specificity']:
            parts.append("include at least one concrete metric (%, GB, °C, PID)")
        if policy['require_perception_grounding']:
            parts.append("reference a specific perception block ([SCREEN], [CALENDAR], [PRESENCE], etc.)")
        if policy['prefer_topics']:
            readable = ', '.join(t.replace('_', ' ') for t in policy['prefer_topics'][:2])
            parts.append(f"consider looking at {readable}")

        if parts:
            policy['directive'] = 'Next thought: ' + '; '.join(parts) + '.'
        elif avg_score < CRITIQUE_LOW_SCORE_THRESHOLD:
            policy['directive'] = (
                'Recent thoughts have been low quality. '
                'Focus on what is different right now, not what is the same.'
            )

        _cog_logger.info(
            "policy | mode=%s avoid=%s force_new=%s specificity=%s grounding=%s",
            policy['reflection_mode'], policy['avoid_topics'],
            policy['force_new_angle'], policy['require_metric_specificity'],
            policy['require_perception_grounding'],
        )

        return policy

    except Exception as e:
        logger.error("Behavior policy generation failed (safe fallback): %s", e)
        return {
            'avoid_topics': [], 'prefer_topics': [],
            'require_perception_grounding': False,
            'require_metric_specificity': False,
            'force_new_angle': False,
            'reflection_mode': 'normal',
            'retry_eligible': False,
            'directive': '',
        }


def should_retry(cog_result: dict) -> bool:
    """Determine if a thought should be retried based on cognition results.

    Returns True if score is below floor OR labels match a reject combo.
    """
    try:
        if cog_result.get('cog_score', 50) < POLICY_LOW_SCORE_FLOOR:
            return True
        labels = set(cog_result.get('cog_labels', '').split(','))
        for reject_combo in POLICY_RETRY_REJECT_LABELS:
            if reject_combo.issubset(labels):
                return True
        return False
    except Exception:
        return False


def build_retry_prompt(cog_result: dict, policy: dict) -> str:
    """Build a corrective instruction for a retry attempt.

    Tells the LLM exactly what was wrong and what must change.
    """
    parts = []
    labels = cog_result.get('cog_labels', '')
    topic = cog_result.get('cog_topic', 'unknown')
    score_val = cog_result.get('cog_score', 0)

    parts.append(f"Your previous thought scored {score_val}/100.")

    if 'fixation' in labels:
        parts.append(f"It fixated on '{topic.replace('_', ' ')}' which you have already covered repeatedly.")
        parts.append("Choose a DIFFERENT topic entirely.")
    if 'vague' in labels:
        parts.append("It lacked concrete data. Include specific metrics (%, GB, °C, PID).")
    if 'baseline' in labels:
        parts.append("It reported normal system state as if noteworthy. Only flag deviations.")

    if policy.get('prefer_topics'):
        readable = ', '.join(t.replace('_', ' ') for t in policy['prefer_topics'][:2])
        parts.append(f"Consider looking at: {readable}.")

    parts.append("Generate a completely new observation. Do not rephrase the previous one.")

    return '\n'.join(parts)


# ══════════════════════════════════════════════════════════════════════
#  ACTIVE [COGNITION] PROMPT BLOCK — directive, not just informational
# ══════════════════════════════════════════════════════════════════════

def format_active_prompt() -> str:
    """Build the [COGNITION] block for injection into reasoning prompt.

    Always populated once cognition data exists (>= 3 cycles).
    Short, directive, operational — not a score dump.
    """
    if len(_recent_scores) < 3:
        return ""

    window = min(len(_recent_scores), 10)
    recent_s = _recent_scores[-window:]
    recent_t = _recent_topics[-window:]
    avg = sum(recent_s) / len(recent_s)
    last = recent_s[-1] if recent_s else 0

    topic_counts = collections.Counter(recent_t)
    dominant, dom_count = topic_counts.most_common(1)[0]
    fixation_ratio = dom_count / len(recent_t)

    lines = ["[COGNITION]"]
    lines.append(f"  Last score: {last}/100")
    lines.append(f"  {window}-cycle average: {avg:.0f}/100")

    # Dominant failure mode
    flat = [l for ll in _recent_labels[-window:] for l in ll]
    label_freq = collections.Counter(flat)
    neg_labels = {k: v for k, v in label_freq.items() if k in ('fixation', 'vague', 'baseline', 'repetition')}
    if neg_labels:
        worst = max(neg_labels, key=neg_labels.get)
        lines.append(f"  Recent failure mode: {worst} ({neg_labels[worst]}/{window} cycles)")

    # Directive from policy
    policy = get_behavior_policy()
    if policy.get('directive'):
        lines.append(f"  {policy['directive']}")
    elif fixation_ratio >= 0.4:
        readable = dominant.replace('_', ' ')
        lines.append(f"  Avoid repeating '{readable}' unless something genuinely changed.")
        lines.append("  Look at what is DIFFERENT right now.")

    return '\n'.join(lines)


# ══════════════════════════════════════════════════════════════════════
#  CONSOLIDATION QUALITY CHECKER
# ══════════════════════════════════════════════════════════════════════

def check_consolidation_quality(summary: str) -> dict:
    """Check quality of a daily consolidation summary.

    Heuristic definition of 'contains at least one insight':
      - References at least CONSOLIDATION_MIN_TOPICS distinct taxonomy topics
      - Length >= CONSOLIDATION_MIN_LENGTH chars
      - Contains at least one specific data point (%, GB, °C, etc.)
      - Not dominated by a single topic (diversity > 0.3)

    Returns dict with pass/fail and reasons.
    """
    topics = extract_topics(summary)
    has_specifics = any(re.search(p, summary) for p in SPECIFICITY_PATTERNS)

    # Topic diversity within the summary
    if len(topics) > 1:
        # Check if first topic dominates
        text_lower = summary.lower()
        first_hits = sum(1 for kw in TOPIC_TAXONOMY.get(topics[0], []) if kw in text_lower)
        total_hits = sum(
            sum(1 for kw in TOPIC_TAXONOMY.get(t, []) if kw in text_lower)
            for t in topics
        )
        diversity = 1.0 - (first_hits / max(total_hits, 1))
    else:
        diversity = 0.0

    reasons = []
    passed = True

    if len(topics) < CONSOLIDATION_MIN_TOPICS:
        reasons.append(f"only {len(topics)} topics (need {CONSOLIDATION_MIN_TOPICS}+)")
        passed = False

    if len(summary) < CONSOLIDATION_MIN_LENGTH:
        reasons.append(f"only {len(summary)} chars (need {CONSOLIDATION_MIN_LENGTH}+)")
        passed = False

    if not has_specifics:
        reasons.append("no specific data points (%, GB, °C)")
        passed = False

    if diversity < 0.3:
        reasons.append(f"low topic diversity ({diversity:.0%})")
        passed = False

    result = {
        'passed': passed,
        'topics': topics,
        'topic_count': len(topics),
        'length': len(summary),
        'has_specifics': has_specifics,
        'diversity': round(diversity, 2),
        'reasons': reasons,
    }

    _cog_logger.info(
        "consolidation | pass=%s topics=%d len=%d specifics=%s diversity=%.2f reasons=%s",
        passed, len(topics), len(summary), has_specifics, diversity, reasons,
    )

    return result


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════

def _test():
    """Run basic sanity checks."""
    # Reset buffers for clean test
    global _recent_topics, _recent_scores, _recent_labels
    _recent_topics = []
    _recent_scores = []
    _recent_labels = []

    print("=== Topic Extraction ===")
    assert 'disk_usage' in extract_topics("Root partition at 65.6%")
    assert 'cpu_load' in extract_topics("CPU spiked to 95% across all cores")
    assert 'rohit_presence' in extract_topics("the owner arrived at desk")
    print("  basic topics: OK")

    # Fine-grained subtopics must resolve correctly
    assert extract_topics("You have uncommitted changes, run git commit")[0] == 'git_workflow'
    assert extract_topics("Firefox tab consuming 178% CPU, YouTube video buffering")[0] == 'browser_usage'
    assert extract_topics("You're coding in VS Code with Claude open")[0] == 'development_tools'
    assert extract_topics("Checking daemon logs, maez.service health")[0] == 'system_monitoring'
    assert extract_topics("the owner is at desk, deep work session")[0] == 'general_presence'
    print("  subtopic resolution: OK")

    # Subtopics have parent
    assert get_parent_topic('git_workflow') == 'rohit_activity'
    assert get_parent_topic('browser_usage') == 'rohit_activity'
    assert get_parent_topic('disk_usage') is None
    print("  parent mapping: OK")

    # Critical: git thought and browser thought must NOT be the same topic
    git_topic = extract_topics("Push your uncommitted changes with git commit")[0]
    browser_topic = extract_topics("Firefox pulling 23% CPU from YouTube tabs")[0]
    monitoring_topic = extract_topics("Check the daemon logs and maez.service status")[0]
    assert git_topic != browser_topic, f"git and browser should differ: {git_topic} vs {browser_topic}"
    assert git_topic != monitoring_topic, f"git and monitoring should differ: {git_topic} vs {monitoring_topic}"
    assert browser_topic != monitoring_topic, "browser and monitoring should differ"
    print(f"  differentiation: git={git_topic} browser={browser_topic} monitoring={monitoring_topic}: OK")

    print("=== Classification ===")
    c = classify("Root disk at 65.6%, nothing unusual", ['disk_usage'] * 8)
    assert 'fixation' in c['labels'], f"Expected fixation, got {c['labels']}"
    assert c['topic'] == 'disk_usage'
    print(f"  fixation detection: OK (labels={c['labels']})")

    c2 = classify("Everything is running smoothly, no anomalies detected.")
    assert 'baseline' in c2['labels'], f"Expected baseline, got {c2['labels']}"
    print(f"  baseline detection: OK (labels={c2['labels']})")

    c3 = classify("CPU at 97% sustained — should investigate Chrome PID 12345.")
    assert 'actionable' in c3['labels'], f"Expected actionable, got {c3['labels']}"
    print(f"  actionable detection: OK (labels={c3['labels']})")

    print("=== Scoring ===")
    s1 = score("Disk at 65%.", c, [])
    s2 = score("CPU at 97% sustained for 3 cycles — Chrome PID 12345 consuming 8.2GB RAM. "
               "Should investigate or suggest closing tabs.", c3, [])
    assert s2 > s1, f"Rich thought should score higher: {s2} vs {s1}"
    print(f"  vague={s1}, rich={s2}: OK")

    print("=== Score and Classify ===")
    result = score_and_classify("GPU temperature at 82°C, approaching 85°C threshold.")
    assert 'cog_score' in result
    assert 'cog_topic' in result
    print(f"  integrated: score={result['cog_score']} topic={result['cog_topic']}: OK")

    print("=== Fixation on fine-grained topic ===")
    _recent_topics.clear()
    _recent_texts.clear()
    _recent_scores.clear()
    _recent_labels.clear()
    # Simulate: git_workflow repeated 8 times — should fixate on git_workflow, not rohit_activity
    for _ in range(8):
        score_and_classify("You should git commit your uncommitted staged changes now")
    # Use the same text → content similarity is 1.0, so fixation triggers
    c_fix = classify("You should git commit your uncommitted staged changes now",
                      _recent_topics, _recent_texts)
    assert 'fixation' in c_fix['labels'], f"Expected fixation on git_workflow streak: {c_fix['labels']}"
    assert c_fix['topic'] == 'git_workflow', f"Expected git_workflow, got {c_fix['topic']}"
    print(f"  git_workflow fixation (topic+content): OK (topic={c_fix['topic']})")

    # Now a browser thought should NOT be fixation
    c_browser = classify("Firefox pulling 23% CPU from YouTube tabs",
                          _recent_topics, _recent_texts)
    assert 'fixation' not in c_browser['labels'], f"Browser should not be fixation after git streak: {c_browser['labels']}"
    assert c_browser['topic'] == 'browser_usage', f"Expected browser_usage, got {c_browser['topic']}"
    print(f"  browser after git streak: NOT fixation (topic={c_browser['topic']}): OK")

    # 2026-04-23 new: same topic but DIFFERENT content → should NOT fixate
    _recent_topics.clear()
    _recent_texts.clear()
    _recent_scores.clear()
    _recent_labels.clear()
    varied_browser_texts = [
        "Firefox tab consuming 178% CPU, YouTube video buffering on a 4K stream",
        "Chrome open with 14 tabs, mostly documentation — webpage load times normal",
        "Firefox at 6% CPU browsing Reddit's r/LocalLLaMA, webpage static",
        "YouTube tab in Chrome paused, browser mostly idle",
        "Firefox tab switched to Hacker News, webpage content loaded clean",
        "Firefox 23% CPU on a single webpage, likely heavy JS",
        "Chrome tab on a research paper webpage, browsing steadily",
        "Firefox tabs pruned to three, browser memory down 400MB",
    ]
    for t in varied_browser_texts:
        score_and_classify(t)
    # A new browser thought on different content — topic repeats but content varied
    c_varied = classify("Chrome tab on arXiv loading slowly, webpage stuck",
                         _recent_topics, _recent_texts)
    assert c_varied['topic'] == 'browser_usage', f"Expected browser_usage, got {c_varied['topic']}"
    assert 'fixation' not in c_varied['labels'], (
        f"Varied content on same topic must NOT fixate: {c_varied['labels']}"
    )
    print("  varied-content same-topic: NOT fixation: OK")

    # And verbatim repetition SHOULD still fixate
    _recent_topics.clear()
    _recent_texts.clear()
    _recent_scores.clear()
    _recent_labels.clear()
    for _ in range(8):
        score_and_classify("Firefox pulling 23% CPU from YouTube tabs, browser heavy")
    c_repeat = classify("Firefox pulling 23% CPU from YouTube tabs, browser heavy",
                         _recent_topics, _recent_texts)
    assert 'fixation' in c_repeat['labels'], f"Verbatim repeat must fixate: {c_repeat['labels']}"
    print("  verbatim-repeat same-topic: fixation: OK")

    # Single-keyword tag suppression: "I noticed a firefox process" alone
    # should NOT tag as browser_usage (only 1 keyword hit, needs ≥2)
    _recent_topics.clear()
    _recent_texts.clear()
    c_single = extract_topics("Process list shows a firefox entry active")
    assert 'browser_usage' not in c_single, (
        f"Single 'firefox' keyword must not tag browser_usage: {c_single}"
    )
    print("  single-keyword suppression on rohit_activity subtopic: OK")

    print("=== Behavior Policy ===")
    _recent_topics.clear()
    _recent_scores.clear()
    _recent_labels.clear()
    for _ in range(8):
        _recent_topics.append('git_workflow')
        _recent_scores.append(35)
        _recent_labels.append(['fixation', 'vague'])
    policy = get_behavior_policy()
    assert 'git_workflow' in policy['avoid_topics'], f"Expected avoid git_workflow, got {policy}"
    assert policy['force_new_angle'], f"Expected force_new_angle, got {policy}"
    assert policy['require_metric_specificity'], "Expected require specificity"
    assert policy['directive'], "Expected non-empty directive"
    print(f"  fixation policy: avoid={policy['avoid_topics']} mode={policy['reflection_mode']}: OK")
    print(f"  directive: {policy['directive'][:80]}...")

    print("=== Retry Logic ===")
    bad_result = {'cog_score': 25, 'cog_labels': 'fixation,vague', 'cog_topic': 'rohit_activity'}
    assert should_retry(bad_result), "Low score should trigger retry"
    good_result = {'cog_score': 70, 'cog_labels': 'actionable,insightful', 'cog_topic': 'cpu_load'}
    assert not should_retry(good_result), "Good score should not trigger retry"
    retry_prompt = build_retry_prompt(bad_result, policy)
    assert 'scored 25' in retry_prompt
    assert 'DIFFERENT topic' in retry_prompt
    print("  retry trigger: OK")
    print(f"  retry prompt: {retry_prompt[:80]}...")

    print("=== Active Prompt ===")
    prompt = format_active_prompt()
    assert '[COGNITION]' in prompt
    assert 'Last score' in prompt
    print("  active prompt block generated: OK")

    print("=== Consolidation Quality ===")
    # Reset for clean consolidation test
    _recent_topics.clear()
    _recent_scores.clear()
    _recent_labels.clear()
    good = check_consolidation_quality(
        "Today the owner focused on coding in VS Code. CPU averaged 15%, RAM at 42%. "
        "GPU stayed at 41°C. Disk usage stable at 43.4%. Telegram conversations with "
        "2 users. Calendar had 1 meeting. No errors detected. Network quiet."
    )
    assert good['passed'], f"Good consolidation should pass: {good['reasons']}"
    print(f"  good consolidation: pass={good['passed']}: OK")

    bad = check_consolidation_quality("Disk at 65%.")
    assert not bad['passed']
    print(f"  bad consolidation: pass={bad['passed']} reasons={bad['reasons']}: OK")

    print("\n=== ALL TESTS PASSED ===")


if __name__ == '__main__':
    _test()
