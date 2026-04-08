"""
cognition_quality.py — Structural cognition quality subsystem for Maez.

Classifies, scores, and critiques reasoning outputs using deterministic
heuristics. No external APIs — pure structural analysis.

Integration points:
  - maez_daemon.py calls score_and_classify() before memory.store()
  - memory_manager.py applies anti-fixation penalty in _topic_rerank()
  - maez_daemon.py runs self_critique() every 20 cycles
"""

import collections
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("maez")

# --- Logging ---
COG_LOG = Path("/home/rohit/maez/logs/cognition.log")
COG_LOG.parent.mkdir(parents=True, exist_ok=True)
_cog_handler = logging.FileHandler(COG_LOG)
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
FIXATION_THRESHOLD = 0.6    # fraction of recent topics that must match to flag fixation

# Scoring weights (0-100 scale)
SCORE_WEIGHT_LENGTH = 10        # bonus for adequate length
SCORE_WEIGHT_SPECIFICITY = 25   # bonus for concrete data references
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


# ══════════════════════════════════════════════════════════════════════
#  TOPIC TAXONOMY — deterministic extraction
# ══════════════════════════════════════════════════════════════════════

TOPIC_TAXONOMY = {
    'disk_usage':     ['disk', 'partition', 'storage', 'df ', '/dev/', 'mount', 'inode'],
    'cpu_load':       ['cpu', 'load average', 'cores', 'utilization'],
    'memory_usage':   ['ram', 'memory', 'swap', 'oom'],
    'gpu_state':      ['gpu', 'vram', 'cuda', 'nvidia', 'temperature'],
    'network':        ['network', 'bandwidth', 'latency', 'packet', 'connection', 'ssh'],
    'processes':      ['process', 'pid', 'zombie', 'defunct', 'top ', 'htop'],
    'rohit_presence': ['rohit', 'desk', 'arrived', 'away', 'presence', 'absent'],
    'rohit_activity': ['working', 'coding', 'browsing', 'idle', 'focus', 'deep work', 'vs code', 'terminal'],
    'calendar':       ['meeting', 'event', 'calendar', 'schedule', 'appointment'],
    'telegram':       ['telegram', 'message', 'conversation', 'bot'],
    'web_content':    ['news', 'reddit', 'github', 'trending', 'article'],
    'maez_self':      ['soul', 'reasoning', 'cycle', 'evolution', 'memory', 'consolidation'],
    'error':          ['error', 'fail', 'crash', 'exception', 'timeout', 'refused'],
    'security':       ['firewall', 'ufw', 'ssh attempt', 'unauthorized', 'port'],
    'time_awareness': ['morning', 'evening', 'night', 'circadian', 'time of day'],
}


def extract_topics(text: str) -> list[str]:
    """Extract topics from text using the controlled taxonomy.
    Returns list of matched topic keys, sorted by match count (descending).
    Falls back to simple keyword extraction if no taxonomy match."""
    text_lower = text.lower()
    matches: dict[str, int] = {}
    for topic, keywords in TOPIC_TAXONOMY.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > 0:
            matches[topic] = count

    if matches:
        return sorted(matches, key=matches.get, reverse=True)

    # Fallback: extract nouns/keywords by frequency (simple heuristic)
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


def primary_topic(text: str) -> str:
    """Return the single primary topic of a text."""
    topics = extract_topics(text)
    return topics[0] if topics else 'unknown'


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


def classify(text: str, recent_topics: list[str] = None) -> dict:
    """Classify a thought into multi-label categories.

    Returns dict with:
        labels: list[str]       — all applicable labels
        primary: str            — single dominant label
        topic: str              — primary topic from taxonomy
        topics: list[str]       — all matched topics
    """
    text_lower = text.lower()
    labels = []
    recent_topics = recent_topics or []

    topics = extract_topics(text)
    topic = topics[0] if topics else 'unknown'

    # Check fixation — does primary topic dominate recent history?
    if recent_topics and topic != 'unknown':
        topic_freq = sum(1 for t in recent_topics[-FIXATION_WINDOW:] if t == topic)
        if len(recent_topics) >= 3 and topic_freq / min(len(recent_topics), FIXATION_WINDOW) >= FIXATION_THRESHOLD:
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

    return {
        'labels': labels,
        'primary': primary_label,
        'topic': topic,
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

# In-memory ring buffer of recent topics for fixation detection
_recent_topics: list[str] = []
_recent_scores: list[int] = []
_low_critique_streak = 0  # consecutive critique windows below threshold


def score_and_classify(text: str) -> dict:
    """Score and classify a thought. Returns enriched metadata dict.

    Called by daemon BEFORE memory.store() so metadata is written once.
    Returns dict with keys: cog_score, cog_primary, cog_labels, cog_topic, cog_topics
    """
    try:
        classification = classify(text, _recent_topics)
        quality = score(text, classification, _recent_topics)

        # Update ring buffers
        _recent_topics.append(classification['topic'])
        if len(_recent_topics) > 50:
            _recent_topics[:] = _recent_topics[-50:]
        _recent_scores.append(quality)
        if len(_recent_scores) > 50:
            _recent_scores[:] = _recent_scores[-50:]

        result = {
            'cog_score': quality,
            'cog_primary': classification['primary'],
            'cog_labels': ','.join(classification['labels']),
            'cog_topic': classification['topic'],
            'cog_topics': ','.join(classification['topics'][:3]),
        }

        _cog_logger.info(
            "cycle | score=%d primary=%s topic=%s labels=%s",
            quality, classification['primary'],
            classification['topic'], classification['labels'],
        )

        return result

    except Exception as e:
        logger.error("Cognition scoring failed (safe fallback): %s", e)
        return {
            'cog_score': 50,
            'cog_primary': 'unknown',
            'cog_labels': 'error',
            'cog_topic': 'unknown',
            'cog_topics': 'unknown',
        }


# ══════════════════════════════════════════════════════════════════════
#  SELF-CRITIQUE — runs every CRITIQUE_WINDOW cycles
# ══════════════════════════════════════════════════════════════════════

def self_critique() -> dict | None:
    """Analyze recent cognition quality. Returns critique dict or None.

    Called by daemon every 20 cycles. Only writes soul notes if:
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
        lines.append(f"  Vary your attention. Look at what CHANGED, not what stayed the same.")

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
    print("=== Topic Extraction ===")
    assert 'disk_usage' in extract_topics("Root partition at 65.6%")
    assert 'cpu_load' in extract_topics("CPU spiked to 95% across all cores")
    assert 'rohit_presence' in extract_topics("Rohit arrived at desk")
    print("  topic extraction: OK")

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

    print("=== Consolidation Quality ===")
    good = check_consolidation_quality(
        "Today Rohit focused on coding in VS Code. CPU averaged 15%, RAM at 42%. "
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
