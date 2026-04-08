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

# Behavior policy thresholds
POLICY_FIXATION_STREAK = 3              # consecutive fixation labels before avoid_topics kicks in
POLICY_VAGUE_STREAK = 3                 # consecutive vague labels before requiring specificity
POLICY_LOW_SCORE_FLOOR = 30             # below this, trigger a retry
POLICY_RETRY_REJECT_LABELS = {          # label combos that trigger retry
    frozenset({'fixation', 'vague'}),
    frozenset({'fixation', 'baseline'}),
}
POLICY_EXPLORATORY_THRESHOLD = 0.7      # fixation ratio above this → exploratory mode


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
        _recent_labels.append(classification['labels'])
        if len(_recent_labels) > 50:
            _recent_labels[:] = _recent_labels[-50:]

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
        label_counts = collections.Counter(flat_labels)

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
        lines.append(f"  Look at what is DIFFERENT right now.")

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

    print("=== Behavior Policy ===")
    # Simulate fixation streak
    _recent_topics.clear()
    _recent_scores.clear()
    _recent_labels.clear()
    for _ in range(8):
        _recent_topics.append('rohit_activity')
        _recent_scores.append(35)
        _recent_labels.append(['fixation', 'vague'])
    policy = get_behavior_policy()
    assert 'rohit_activity' in policy['avoid_topics'], f"Expected avoid rohit_activity, got {policy}"
    assert policy['force_new_angle'], f"Expected force_new_angle, got {policy}"
    assert policy['require_metric_specificity'], f"Expected require specificity"
    assert policy['directive'], f"Expected non-empty directive"
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
    print(f"  retry trigger: OK")
    print(f"  retry prompt: {retry_prompt[:80]}...")

    print("=== Active Prompt ===")
    prompt = format_active_prompt()
    assert '[COGNITION]' in prompt
    assert 'Last score' in prompt
    print(f"  active prompt block generated: OK")

    print("=== Consolidation Quality ===")
    # Reset for clean consolidation test
    _recent_topics.clear()
    _recent_scores.clear()
    _recent_labels.clear()
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
