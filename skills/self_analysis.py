"""
self_analysis.py — Maez analyzes its own reasoning quality

Reads raw memories, identifies patterns and repetition,
writes findings to soul.md via Tier 0 action.
"""

import logging
import time
from collections import Counter

logger = logging.getLogger("maez")

OBSERVATION_TOPICS = {
    'disk': ['partition', 'disk', 'storage', 'capacity', '/var/log'],
    'gpu': ['gpu', 'vram', 'temperature', 'cuda', 'rtx'],
    'cpu': ['cpu', 'processor', 'core', 'load'],
    'ram': ['ram', 'memory', 'swap'],
    'network': ['network', 'bandwidth', 'connection'],
    'presence': ['desk', 'arrived', 'away', 'rohit present'],
    'screen': ['screen', 'working on', 'vs code', 'browser', 'claude code'],
    'calendar': ['meeting', 'calendar', 'event', 'scheduled'],
    'self': ['maez', 'myself', 'reasoning', 'cycle'],
}


def analyze(memory_manager, action_engine=None) -> dict:
    logger.info("Self-analysis starting...")

    try:
        results = memory_manager.raw.get(limit=200, include=['documents', 'metadatas'])
        memories = results.get('documents', [])
        metadatas = results.get('metadatas', [])
    except Exception as e:
        logger.error("Failed to read memories: %s", e)
        return {}

    if not memories:
        return {}

    topic_counts = Counter()
    for memory in memories:
        ml = memory.lower()
        for topic, keywords in OBSERVATION_TOPICS.items():
            if any(kw in ml for kw in keywords):
                topic_counts[topic] += 1

    most_repeated = topic_counts.most_common(1)
    top_topic = most_repeated[0][0] if most_repeated else 'unknown'
    top_count = most_repeated[0][1] if most_repeated else 0
    total = len(memories)
    rep_rate = (top_count / total * 100) if total > 0 else 0

    # Time patterns
    hours = []
    for meta in metadatas:
        if meta and 'timestamp' in meta:
            try:
                hours.append(int(meta['timestamp'].split('T')[1].split(':')[0]))
            except Exception:
                pass
    peak_hour = Counter(hours).most_common(1)[0][0] if hours else None

    analysis = {
        'total_memories_analyzed': total,
        'topic_distribution': dict(topic_counts.most_common()),
        'most_repeated_topic': top_topic,
        'most_repeated_count': top_count,
        'repetition_rate': round(rep_rate, 1),
        'unique_insight_rate': round(100 - rep_rate, 1),
        'peak_activity_hour': peak_hour,
        'analyzed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    logger.info("Self-analysis: most repeated=%s (%d times), unique=%.0f%%",
                top_topic, top_count, 100 - rep_rate)

    # Write to soul.md
    if action_engine:
        _write_soul_insight(analysis, action_engine)

    return analysis


def _write_soul_insight(analysis: dict, action_engine):
    date_str = time.strftime('%Y-%m-%d')
    topic = analysis['most_repeated_topic']
    count = analysis['most_repeated_count']
    total = analysis['total_memories_analyzed']
    unique = analysis['unique_insight_rate']

    if analysis['repetition_rate'] > 50:
        rec = (f"Stop mentioning {topic} every cycle unless something changes. "
               f"Repetition wastes Rohit's attention.")
    elif unique > 70:
        rec = f"Reasoning quality good — {unique:.0f}% unique observations."
    else:
        rec = f"Balance attention more evenly. {topic} dominates at {analysis['repetition_rate']:.0f}%."

    note = (f"\n## Self-Analysis — {date_str}\n"
            f"Analyzed {total} memories. Most repeated: {topic} ({count} times, "
            f"{analysis['repetition_rate']:.0f}%). Unique rate: {unique:.0f}%.\n"
            f"Recommendation: {rec}\n")

    try:
        action_engine.write_soul_note(note)
        logger.info("Self-analysis written to soul.md")
    except Exception as e:
        logger.error("Failed to write soul note: %s", e)


def format_for_telegram(analysis: dict) -> str:
    if not analysis:
        return "Self-analysis failed."
    return (f"Self-analysis:\n"
            f"  {analysis['total_memories_analyzed']} memories analyzed\n"
            f"  Most repeated: {analysis['most_repeated_topic']} "
            f"({analysis['most_repeated_count']} times)\n"
            f"  Unique insight rate: {analysis['unique_insight_rate']:.0f}%\n"
            f"  Topics: {analysis['topic_distribution']}")


def get_weaknesses(memory_manager) -> list:
    """Extract actionable weaknesses from recent memories for evolution engine."""
    try:
        results = memory_manager.raw.get(limit=50, include=['documents'])
        memories = results.get('documents', [])
    except Exception:
        return []

    weakness_patterns = {
        'web search returns generic results': ['aggregator', 'homepage', 'generic results'],
        'repetitive reasoning about disk': ['same observation', 'repetitive', 'disk pressure', 'persistent trend'],
        'wake word missed detection': ['wake word', 'not detecting', 'missed detection'],
        'action not executed after approval': ['did not execute', 'failed to act', 'no action taken'],
        'screen perception too slow': ['screen obs failed', 'vision timed out'],
    }

    weaknesses = []
    for weakness, keywords in weakness_patterns.items():
        count = sum(1 for m in memories if any(kw in m.lower() for kw in keywords))
        if count >= 3:
            weaknesses.append(weakness)

    return weaknesses[:5]


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '/home/rohit/maez')
    logging.basicConfig(level=logging.INFO)
    from memory.memory_manager import MemoryManager
    mm = MemoryManager()
    result = analyze(mm)
    print(format_for_telegram(result))
