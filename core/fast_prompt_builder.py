"""
core/fast_prompt_builder.py — Session 11c, staging-only.

Builds the SMALL deterministic prompt the fast-lane reply uses. The whole
point of this builder is what it DOES NOT include:

  EXCLUDED on purpose (handled by the slow nightly path, not the fast lane):
    • deep nightly reasoning blocks
    • self_critique() context
    • proposal machinery (candidates, evidence packets, validators)
    • consolidation context (recent vs nightly summaries)
    • raw archive retrieval / vector search
    • policy directives, behavior modes
    • soul notes, identity scripture, manifesto

  INCLUDED only:
    • compact Maez identity block (1 paragraph, hand-tuned)
    • user / trust scope placeholder line
    • last few conversation turns (max RECENT_TURNS, trimmed)
    • perception envelope summary (only USABLE sources, age-tagged)
    • the user's current message

PROMPT BUDGET (target / soft cap, characters):
    identity                  ~280
    scope line                ~120
    perception summary        ~600
    conversation history      ~1200  (4 turns × 300 chars)
    user message              ~600
    formatting / sections     ~200
    ─────────────────────────────────
    total target              ~3000 chars  (~750 tokens)
    hard cap                  ~6000 chars  (~1500 tokens)

The builder enforces the hard cap by trimming history first, then perception
detail. Identity and the user message are never trimmed.

Future fast-lane integration will add:
  • per-source max-age policy for hard exclusion
  • multi-turn streaming format support
  • model-specific prompt dialects (Gemma vs Claude vs GPT)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.perception_envelope import PerceptionEnvelope, EnvelopeSource
from core.perception_cache import FRESH, STALE, MISSING, ERROR


# Hard caps — see PROMPT BUDGET in module docstring
RECENT_TURNS         = 4
MAX_TURN_CHARS       = 300
MAX_PERCEPTION_CHARS = 600
HARD_CAP_CHARS       = 6000


# Compact identity — hand-tuned to be 1 paragraph, ~280 chars.
# Deliberately omits the long-form scripture and manifesto blocks the
# slow path uses; those don't earn their token cost on the fast lane.
COMPACT_IDENTITY = (
    "You are Maez, a persistent local AI companion built by Rohit. "
    "You remember past conversations, perceive Rohit's environment via "
    "background sensors, and respond directly. You are warm, concise, and "
    "useful. Your reply must be short unless depth is clearly required."
)


@dataclass
class TurnRecord:
    role: str           # 'user' | 'maez'
    text: str

    def trimmed(self, max_chars: int = MAX_TURN_CHARS) -> str:
        t = self.text.strip()
        if len(t) <= max_chars:
            return t
        return t[: max_chars - 1] + '…'


@dataclass
class BuiltPrompt:
    text: str
    char_count: int
    section_chars: dict[str, int] = field(default_factory=dict)
    truncated: bool = False
    used_perception_sources: list[str] = field(default_factory=list)
    skipped_perception_sources: list[str] = field(default_factory=list)


def _format_screen(src: EnvelopeSource) -> Optional[str]:
    """Render a usable screen source as a single line. Returns None if unusable."""
    if not src.is_usable:
        return None
    v = src.value
    # Tolerate either a ScreenObservation dataclass or a stub with the same fields
    activity    = getattr(v, 'activity',    '') or ''
    application = getattr(v, 'application', '') or ''
    detail      = getattr(v, 'detail',      '') or ''
    focus_level = getattr(v, 'focus_level', '') or ''
    age_s = max(0, src.age_ms // 1000)
    tag = src.freshness_state.upper()
    bits = []
    if application: bits.append(f"app={application}")
    if focus_level: bits.append(f"focus={focus_level}")
    if activity:    bits.append(f"activity={activity}")
    if detail and detail.lower() != 'none':
        bits.append(f"detail={detail}")
    body = " | ".join(bits) if bits else "(no fields)"
    return f"  screen        [{tag} {age_s}s ago] {body}"


def _format_system_state(src: EnvelopeSource) -> Optional[str]:
    if not src.is_usable:
        return None
    v = src.value
    # core.perception.snapshot returns a TypedDict; tolerate dict access
    def g(*path, default='?'):
        cur = v
        for p in path:
            try:
                cur = cur[p]
            except (KeyError, TypeError, IndexError):
                return default
        return cur
    age_s = max(0, src.age_ms // 1000)
    tag = src.freshness_state.upper()
    cpu_pct  = g('cpu', 'percent', default='?')
    ram_pct  = g('ram', 'percent', default='?')
    disk_pct = g('disk', 'percent', default='?')
    gpu      = v.get('gpu') if isinstance(v, dict) else getattr(v, 'gpu', None)
    parts = [f"cpu={cpu_pct}%", f"ram={ram_pct}%", f"disk={disk_pct}%"]
    if isinstance(gpu, dict):
        gpu_util = gpu.get('utilization_pct', '?')
        gpu_temp = gpu.get('temperature_c',   '?')
        parts.append(f"gpu={gpu_util}% {gpu_temp}C")
    return f"  system_state  [{tag} {age_s}s ago] " + ' '.join(parts)


def _format_calendar(src: EnvelopeSource) -> Optional[str]:
    """Render a usable calendar source as one or two compact lines."""
    if not src.is_usable:
        return None
    v = src.value
    age_s = max(0, src.age_ms // 1000)
    tag = src.freshness_state.upper()

    # CalendarSnapshot has .events (list), .current_event, .next_event
    events = getattr(v, 'events', None) or []
    current = getattr(v, 'current_event', None)
    next_ev = getattr(v, 'next_event', None)

    if not events and current is None and next_ev is None:
        return f"  calendar      [{tag} {age_s}s ago] (nothing scheduled)"

    bits = []
    if current is not None:
        title = getattr(current, 'title', '?')
        bits.append(f"now={title}")
    if next_ev is not None and next_ev is not current:
        title = getattr(next_ev, 'title', '?')
        mins = getattr(next_ev, 'minutes_until', None)
        if isinstance(mins, (int, float)):
            if mins < 60:
                when = f"in {int(mins)}m"
            else:
                when = f"in {mins/60:.1f}h"
            bits.append(f"next={title} ({when})")
        else:
            bits.append(f"next={title}")
    if not bits and events:
        # Fallback: just count
        bits.append(f"{len(events)} upcoming")
    body = " | ".join(bits) if bits else "(no parsed events)"
    return f"  calendar      [{tag} {age_s}s ago] {body}"


def _format_perception(envelope: PerceptionEnvelope) -> tuple[str, list[str], list[str]]:
    """Returns (block_text, used_sources, skipped_sources)."""
    used: list[str] = []
    skipped: list[str] = []
    lines: list[str] = []

    formatters = {
        'screen':       _format_screen,
        'system_state': _format_system_state,
        'calendar':     _format_calendar,
    }

    for name, src in envelope.sources.items():
        formatter = formatters.get(name)
        if formatter is None:
            skipped.append(f"{name}:no_formatter")
            continue
        line = formatter(src)
        if line is None:
            # Show a one-line "unavailable" marker so the model knows the
            # source exists but is currently empty/errored — this is what
            # lets the model say "my screen sensor is offline" honestly
            # instead of hallucinating.
            tag = src.freshness_state.upper()
            err_bit = f" err={src.error[:60]}" if src.error else ""
            lines.append(f"  {name:13s} [{tag}] (no value){err_bit}")
            skipped.append(name)
            continue
        lines.append(line)
        used.append(name)

    if not lines:
        block = "perception:\n  (no sources available)"
    else:
        block = "perception:\n" + "\n".join(lines)

    # Trim if it overshoots the perception budget
    if len(block) > MAX_PERCEPTION_CHARS:
        block = block[: MAX_PERCEPTION_CHARS - 1] + '…'

    return block, used, skipped


def _format_history(history: list[TurnRecord]) -> str:
    if not history:
        return "conversation:\n  (no prior turns)"
    take = history[-RECENT_TURNS:]
    lines = ["conversation:"]
    for turn in take:
        speaker = 'rohit' if turn.role == 'user' else 'maez'
        lines.append(f"  {speaker}: {turn.trimmed()}")
    return "\n".join(lines)


def build_fast_prompt(
    user_message: str,
    envelope: PerceptionEnvelope,
    history: Optional[list[TurnRecord]] = None,
    trust_scope: str = 'rohit',
) -> BuiltPrompt:
    """Build the deterministic fast-lane prompt.

    Hard contract:
      • Reads ONLY from `envelope` for perception data.
      • Never calls cache.get() directly.
      • Never invokes any perception module.
      • Identity and user_message are never trimmed.
      • If the assembled prompt exceeds HARD_CAP_CHARS, trim history first,
        then perception block, then mark `truncated=True`.
    """
    history = history or []

    identity_block   = "identity:\n  " + COMPACT_IDENTITY
    scope_block      = f"scope:\n  trust_scope={trust_scope}"
    perception_block, used, skipped = _format_perception(envelope)
    history_block    = _format_history(history)
    user_block       = "current_message:\n  " + (user_message or '').strip()

    sections = [identity_block, scope_block, perception_block, history_block, user_block]
    text = "\n\n".join(sections)
    truncated = False

    if len(text) > HARD_CAP_CHARS:
        # Step 1 — drop conversation turns from the front until budget fits
        trimmed_history = history[-RECENT_TURNS:]
        while len(text) > HARD_CAP_CHARS and len(trimmed_history) > 1:
            trimmed_history = trimmed_history[1:]
            history_block = _format_history(trimmed_history)
            text = "\n\n".join([
                identity_block, scope_block, perception_block, history_block, user_block
            ])
            truncated = True
        # Step 2 — trim perception block
        if len(text) > HARD_CAP_CHARS:
            shrink = HARD_CAP_CHARS - (len(text) - len(perception_block)) - 4
            if shrink > 0:
                perception_block = perception_block[:shrink] + '…'
            else:
                perception_block = "perception:\n  (omitted: budget)"
            text = "\n\n".join([
                identity_block, scope_block, perception_block, history_block, user_block
            ])
            truncated = True

    return BuiltPrompt(
        text=text,
        char_count=len(text),
        section_chars={
            'identity':   len(identity_block),
            'scope':      len(scope_block),
            'perception': len(perception_block),
            'history':    len(history_block),
            'user':       len(user_block),
        },
        truncated=truncated,
        used_perception_sources=used,
        skipped_perception_sources=skipped,
    )
