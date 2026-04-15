r"""
Maez Card Reply Classifier — Session 11z Part 2, Step 9b.

Classifies a user message (text, reaction emoji, or both) against a
list of outstanding approval cards and decides what the user meant:
APPROVE, DENY, DEFER, MODIFY, RE_EXPLAIN, or UNRELATED.

This module is deliberately heuristic-first with a small LLM fallback,
so the common cases ("yes", "no", "wait an hour", 👍, 👎) resolve in
microseconds with zero LLM cost. Only ambiguous cases pay the LLM tax.

Design rules
────────────

1. If there are no open cards, short-circuit to UNRELATED immediately.
   The Jarvis loop should never call this module in that case, but we
   defend the call anyway so missed checks don't turn into latency
   regressions on every chat turn.

2. Reactions (emoji) are the highest-confidence channel:
      👍 ❤️ ✅ 👌 🙏          → APPROVE
      👎 ❌ 🚫 🙅              → DENY
      ⏸️ ⏳ 💤                 → DEFER (no deadline; sits in queue)
      🤔 ❓ ℹ️                 → RE_EXPLAIN
   Anything else on a card message is UNRELATED (the owner just reacted
   to the underlying content, not as an approval signal).

3. Text is matched in layers:
      a) Fast keyword match (handles ~80% of real cases)
      b) Duration extraction for DEFER ("in 5 min", "an hour",
         "remind me tomorrow")
      c) LLM fallback only when the heuristic layer returns UNCLEAR
         AND there's at least one open card to match against

4. When multiple cards are open, the classifier picks the target:
      - If the message is a reply to a known card message_id, that's
        the target (set by the caller, not inferred here).
      - If only one card is open, it's the target.
      - If multiple are open and no explicit reply threading, target
        the most recently created card. This is a pragmatic default —
        the owner can always say "cancel the cowsay one" to disambiguate,
        and that will route through the LLM fallback.

5. The classifier never mutates the store. It only CLASSIFIES. The
   caller (the Jarvis loop) decides what to do with the result.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.pending_cards import CardRecord


# ------------------------------------------------------------------ #
#  Result types                                                        #
# ------------------------------------------------------------------ #

class ReplyIntent(str, Enum):
    APPROVE     = "approve"
    DENY        = "deny"
    DEFER       = "defer"
    MODIFY      = "modify"
    RE_EXPLAIN  = "re_explain"
    UNRELATED   = "unrelated"
    UNCLEAR     = "unclear"      # only ever returned by heuristic-only pass


@dataclass
class ReplyClassification:
    intent: ReplyIntent
    target_request_id: Optional[str]
    confidence: float
    source: str                   # 'reaction', 'keyword', 'duration', 'llm', 'none'
    reasoning: str = ""
    # DEFER extras
    remind_at: Optional[float] = None
    defer_reason: Optional[str] = None
    # MODIFY extras
    modification_request: Optional[str] = None


# ------------------------------------------------------------------ #
#  Reaction mapping                                                    #
# ------------------------------------------------------------------ #

# Kept intentionally small — more emoji = more false positives from
# "the owner just reacted to the reasoning, not as approval."
APPROVE_EMOJI = {"👍", "❤️", "✅", "👌", "🙏", "🔥"}
DENY_EMOJI    = {"👎", "❌", "🚫", "🙅", "🙅‍♂️", "🙅‍♀️"}
DEFER_EMOJI   = {"⏸️", "⏳", "💤", "🕐"}
EXPLAIN_EMOJI = {"🤔", "❓", "❔", "ℹ️"}


def classify_reaction(emoji: str) -> Optional[ReplyIntent]:
    if emoji in APPROVE_EMOJI:
        return ReplyIntent.APPROVE
    if emoji in DENY_EMOJI:
        return ReplyIntent.DENY
    if emoji in DEFER_EMOJI:
        return ReplyIntent.DEFER
    if emoji in EXPLAIN_EMOJI:
        return ReplyIntent.RE_EXPLAIN
    return None


# ------------------------------------------------------------------ #
#  Text keyword matching                                               #
# ------------------------------------------------------------------ #

# Whole-phrase matches (case-insensitive). Longer phrases checked
# first so "go ahead" beats "go" — achieved by sorting at bind time.
_APPROVE_PHRASES = [
    "go ahead", "do it", "please do", "sounds good", "looks good",
    "ship it", "run it", "proceed", "approved", "confirm", "confirmed",
    "green light", "greenlit", "yes please", "yes do it", "yep", "yup",
    "yeah", "yes", "sure", "okay", "ok", "fine", "alright", "k", "kk",
]

_DENY_PHRASES = [
    "cancel that", "cancel it", "don't do it", "dont do it", "do not",
    "never mind", "nevermind", "stop", "skip it", "skip that", "not now",
    "not this one", "not that one", "hold off", "abort", "rejected",
    "no thanks", "no thank you", "nope", "nah", "no", "naw", "pass",
]

# "DEFER_WITH_DURATION" phrases imply "ask me again in X". "DEFER_OPEN"
# phrases mean "don't ask me again until I bring it up myself."
_DEFER_WITH_DURATION_HINT = [
    "wait", "hold on", "hold", "in a", "in ", "after ", "later today",
    "tomorrow", "next ", "tonight", "this evening", "this afternoon",
    "this morning", "remind me", "ask me", "ask me later", "come back",
    "check back", "let me", "give me",
]

_DEFER_OPEN = [
    "later", "not right now", "i'll think about it", "i'll decide later",
    "let me think", "let me think about it", "i'll tell you when",
    "i'll let you know", "hold it for now", "park it", "pause it",
]

_EXPLAIN_PHRASES = [
    "what does that do", "what does it do", "what does", "why do you",
    "why would", "why are you", "why is", "explain", "more info",
    "more detail", "more details", "tell me more", "what is this",
    "what is that", "what's this", "what's that", "how come", "what will",
    "what happens",
]

_MODIFY_PHRASES = [
    "instead of", "change it to", "change to", "but use", "but with",
    "actually use", "actually do", "rewrite", "rework", "tweak",
    "modify", "update it to", "make it use", "could you use",
]

# New-action-request starters. A reply that begins with one of these
# is a fresh command from the owner, NOT an approval for an existing open
# card — even when a stale card happens to be open. The LLM fallback
# has been observed mis-classifying "Install openrgb" as APPROVE on a
# 19-minute-old `history | tail -n 20` card, then the approval path
# re-audits the stale card and the whole flow explodes. This list
# short-circuits those mismatches before they reach the LLM.
_NEW_ACTION_STARTERS = [
    "install ", "uninstall ", "remove ", "reinstall ",
    "run ", "execute ", "exec ",
    "check ", "check if ", "check whether ",
    "search ", "search for ", "look for ", "look up ",
    "find ", "grep ", "locate ",
    "download ", "fetch ", "pull ", "clone ", "git clone",
    "update ", "upgrade ",
    "restart ", "reboot ", "start ", "stop ",
    "read ", "show me ", "list ", "cat ",
    "delete ", "rm ", "kill ",
    "build ", "compile ", "make ",
    "curl ", "wget ",
    "sudo ",
    "write ", "create ", "touch ", "mkdir ",
    "can you install", "can you run", "can you check",
    "please install", "please run", "please check",
]


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace for matching."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _whole_phrase_match(text: str, phrases: list[str]) -> Optional[str]:
    """Return the phrase that matched, or None. Longest-first."""
    norm = _normalize(text)
    for phrase in sorted(phrases, key=len, reverse=True):
        # Word-boundary-ish: the phrase must appear as a standalone segment
        pattern = r"(?:^|[^a-z0-9])" + re.escape(phrase) + r"(?:$|[^a-z0-9])"
        if re.search(pattern, " " + norm + " "):
            return phrase
    return None


def _starts_new_action_request(text: str) -> Optional[str]:
    """Return the starter that marks this as a fresh action request.

    This check intentionally runs late in the heuristic stack, after we
    have already given real approval/deny/defer/modify/explain phrases a
    chance to match. That keeps legitimate card replies like "run it"
    working while still short-circuiting fresh asks such as
    "install openrgb" before they hit the LLM fallback.
    """
    norm = _normalize(text)
    for starter in sorted(_NEW_ACTION_STARTERS, key=len, reverse=True):
        if norm.startswith(starter):
            return starter
    return None


# ------------------------------------------------------------------ #
#  Duration parsing                                                    #
# ------------------------------------------------------------------ #

# Recognized forms:
#   "5 min", "five min", "5min", "5 minute", "5 minutes"
#   "an hour", "1 hour", "two hours"
#   "30 sec", "30 seconds"
#   "a day", "2 days"
#   "tomorrow" (defaults to +24h)
#   "tonight" (defaults to +6h)
#   "this afternoon" (+4h)
#   "this evening" (+6h)
#   "after lunch" (+3h)
#   "in the morning" (~+16h if evening, ~+8h if morning — we use +16h default)

_WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15,
    "twenty": 20, "thirty": 30, "forty": 40, "forty-five": 45, "sixty": 60,
    "half": 0.5, "quarter": 0.25,
}

_DURATION_RE = re.compile(
    r"\b(?:in\s+)?"
    r"(?P<qty>\d+(?:\.\d+)?|a|an|one|two|three|four|five|six|seven|eight|nine|ten|fifteen|twenty|thirty|forty|sixty|half|quarter)"
    r"\s*-?\s*"
    r"(?P<unit>sec(?:ond)?s?|min(?:ute)?s?|hr|hour|hours|hrs|day|days|week|weeks)\b",
    re.IGNORECASE,
)

_NAMED_OFFSETS = {
    "tomorrow":         86400,
    "tonight":          6 * 3600,
    "this afternoon":   4 * 3600,
    "this evening":     6 * 3600,
    "in the morning":   16 * 3600,
    "after lunch":      3 * 3600,
    "after dinner":     5 * 3600,
    "next hour":        3600,
    "in an hour":       3600,
    "in a hour":        3600,
    "in half an hour":  1800,
    "in a half hour":   1800,
    "in a bit":         600,
    "in a minute":      60,
    "in a sec":         15,
    "in a second":      15,
    "later today":      4 * 3600,
    "eod":              8 * 3600,
}


def extract_defer_duration(text: str) -> Optional[int]:
    """Return seconds from now to defer. None if no duration extracted."""
    if not text:
        return None
    norm = _normalize(text)

    # Named offsets first
    for phrase, secs in sorted(_NAMED_OFFSETS.items(), key=lambda kv: len(kv[0]), reverse=True):
        if phrase in norm:
            return secs

    # Numeric forms
    m = _DURATION_RE.search(norm)
    if m:
        qty_raw = m.group("qty")
        try:
            qty = float(qty_raw)
        except ValueError:
            qty = _WORD_NUMBERS.get(qty_raw.lower(), None)
            if qty is None:
                return None
        unit = m.group("unit").lower()
        if unit.startswith("sec"):
            mult = 1
        elif unit.startswith("min"):
            mult = 60
        elif unit.startswith("hr") or unit.startswith("hour"):
            mult = 3600
        elif unit.startswith("day"):
            mult = 86400
        elif unit.startswith("week"):
            mult = 604800
        else:
            return None
        return int(qty * mult)

    return None


# ------------------------------------------------------------------ #
#  Target card picker                                                  #
# ------------------------------------------------------------------ #

def _pick_target(
    open_cards: list[CardRecord],
    explicit_target_id: Optional[str],
) -> Optional[CardRecord]:
    if not open_cards:
        return None
    if explicit_target_id:
        for c in open_cards:
            if c.request_id == explicit_target_id:
                return c
    # Default: most recently created card
    return max(open_cards, key=lambda c: c.created_at)


# ------------------------------------------------------------------ #
#  Main heuristic classify                                             #
# ------------------------------------------------------------------ #

def classify_reply_heuristic(
    *,
    text: Optional[str] = None,
    reaction_emoji: Optional[str] = None,
    open_cards: list[CardRecord],
    explicit_target_request_id: Optional[str] = None,
    now: Optional[float] = None,
) -> ReplyClassification:
    """Heuristic-only pass. Returns UNCLEAR if it can't decide; the
    caller can then escalate to an LLM fallback via classify_reply()."""

    if not open_cards:
        return ReplyClassification(
            intent=ReplyIntent.UNRELATED,
            target_request_id=None,
            confidence=1.0,
            source="none",
            reasoning="no open cards",
        )

    target = _pick_target(open_cards, explicit_target_request_id)
    target_id = target.request_id if target else None

    # ---- Reaction (highest confidence) ----
    if reaction_emoji:
        intent = classify_reaction(reaction_emoji)
        if intent is not None:
            defer_reason = None
            remind_at = None
            if intent == ReplyIntent.DEFER:
                defer_reason = "deferred via reaction (no deadline)"
            return ReplyClassification(
                intent=intent,
                target_request_id=target_id,
                confidence=0.99,
                source="reaction",
                reasoning=f"reaction {emoji} matched {intent.value}" if (emoji := reaction_emoji) else intent.value,
                remind_at=remind_at,
                defer_reason=defer_reason,
            )
        # Non-mapped reaction on a card message: treat as unrelated
        return ReplyClassification(
            intent=ReplyIntent.UNRELATED,
            target_request_id=None,
            confidence=0.9,
            source="reaction",
            reasoning=f"reaction {reaction_emoji!r} is not an approval signal",
        )

    # ---- Text path ----
    if not text or not text.strip():
        return ReplyClassification(
            intent=ReplyIntent.UNCLEAR,
            target_request_id=target_id,
            confidence=0.0,
            source="none",
            reasoning="empty text",
        )

    # Explain (checked before approve/deny because "what does that do?"
    # shouldn't accidentally match "do")
    explain_hit = _whole_phrase_match(text, _EXPLAIN_PHRASES)
    if explain_hit:
        return ReplyClassification(
            intent=ReplyIntent.RE_EXPLAIN,
            target_request_id=target_id,
            confidence=0.9,
            source="keyword",
            reasoning=f"matched explain phrase: {explain_hit!r}",
        )

    # Modify (checked early for the same reason)
    modify_hit = _whole_phrase_match(text, _MODIFY_PHRASES)
    if modify_hit:
        return ReplyClassification(
            intent=ReplyIntent.MODIFY,
            target_request_id=target_id,
            confidence=0.85,
            source="keyword",
            reasoning=f"matched modify phrase: {modify_hit!r}",
            modification_request=text.strip(),
        )

    # Defer with duration — check before approve/deny so "wait an hour"
    # doesn't accidentally count as approval
    duration_secs = extract_defer_duration(text)
    if duration_secs is not None:
        base = now if now is not None else time.time()
        return ReplyClassification(
            intent=ReplyIntent.DEFER,
            target_request_id=target_id,
            confidence=0.9,
            source="duration",
            reasoning=f"parsed duration: {duration_secs}s",
            remind_at=base + duration_secs,
            defer_reason=text.strip(),
        )

    # Defer (open-ended, no duration)
    defer_open_hit = _whole_phrase_match(text, _DEFER_OPEN)
    if defer_open_hit:
        return ReplyClassification(
            intent=ReplyIntent.DEFER,
            target_request_id=target_id,
            confidence=0.8,
            source="keyword",
            reasoning=f"matched open-defer phrase: {defer_open_hit!r}",
            remind_at=None,
            defer_reason=text.strip(),
        )

    # Defer (duration hint but no extractable value, e.g. "hold on a sec")
    defer_hint_hit = _whole_phrase_match(text, _DEFER_WITH_DURATION_HINT)
    if defer_hint_hit and not (_whole_phrase_match(text, _APPROVE_PHRASES) or _whole_phrase_match(text, _DENY_PHRASES)):
        return ReplyClassification(
            intent=ReplyIntent.DEFER,
            target_request_id=target_id,
            confidence=0.65,
            source="keyword",
            reasoning=f"matched defer hint without duration: {defer_hint_hit!r}",
            remind_at=None,
            defer_reason=text.strip(),
        )

    # Deny
    deny_hit = _whole_phrase_match(text, _DENY_PHRASES)
    if deny_hit:
        return ReplyClassification(
            intent=ReplyIntent.DENY,
            target_request_id=target_id,
            confidence=0.9,
            source="keyword",
            reasoning=f"matched deny phrase: {deny_hit!r}",
        )

    # Approve
    approve_hit = _whole_phrase_match(text, _APPROVE_PHRASES)
    if approve_hit:
        return ReplyClassification(
            intent=ReplyIntent.APPROVE,
            target_request_id=target_id,
            confidence=0.9,
            source="keyword",
            reasoning=f"matched approve phrase: {approve_hit!r}",
        )

    # Fresh action request while a stale card is open. Route it back to
    # the main conversation loop instead of letting the LLM misread it as
    # approval for the newest outstanding card.
    new_action_hit = _starts_new_action_request(text)
    if new_action_hit:
        return ReplyClassification(
            intent=ReplyIntent.UNRELATED,
            target_request_id=None,
            confidence=0.95,
            source="keyword",
            reasoning=f"fresh action request starts with: {new_action_hit!r}",
        )

    # Nothing matched deterministically
    return ReplyClassification(
        intent=ReplyIntent.UNCLEAR,
        target_request_id=target_id,
        confidence=0.0,
        source="none",
        reasoning="no heuristic matched",
    )


# ------------------------------------------------------------------ #
#  LLM fallback                                                        #
# ------------------------------------------------------------------ #

_LLM_SYSTEM = """You are a reply classifier for an approval-card system.

You will receive a user message and a summary of the currently outstanding approval card. Decide the user's intent.

Possible intents (pick exactly one):
  APPROVE     — user wants the action to run
  DENY        — user refuses the action
  DEFER       — user wants to be asked again later
  MODIFY      — user wants the action changed
  RE_EXPLAIN  — user wants more info before deciding
  UNRELATED   — user is talking about something else entirely

Return JSON ONLY in this exact shape:
{"intent": "APPROVE|DENY|DEFER|MODIFY|RE_EXPLAIN|UNRELATED", "confidence": 0.0-1.0, "reasoning": "one sentence"}

No prose, no code fences, no explanation outside the JSON."""


def _llm_fallback(
    text: str,
    target: CardRecord,
) -> ReplyClassification:
    """Last-resort LLM call when heuristics couldn't decide. Keeps the
    prompt tiny so latency stays low."""
    try:
        import json
        from core import llm_client
    except Exception:
        return ReplyClassification(
            intent=ReplyIntent.UNRELATED,
            target_request_id=target.request_id,
            confidence=0.0,
            source="llm",
            reasoning="llm_client unavailable; treated as unrelated",
        )

    card_summary = (
        f"Action: {target.action}\n"
        f"Params: {json.dumps(target.params)[:400]}\n"
        f"Audit reasoning: {target.audit_reasoning[:300]}"
    )
    user_msg = (
        f"CARD:\n{card_summary}\n\n"
        f"USER MESSAGE:\n{text}\n\n"
        f"Classify the user's intent."
    )
    try:
        resp = llm_client.chat(
            model=os.environ.get("MAEZ_AUDIT_MODEL", "gemma-4-26b"),
            messages=[
                {"role": "system", "content": _LLM_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            options={"temperature": 0.0, "num_predict": 120},
            think=False,
        )
        raw = (resp.message.content or "").strip()
    except Exception as e:
        return ReplyClassification(
            intent=ReplyIntent.UNRELATED,
            target_request_id=target.request_id,
            confidence=0.0,
            source="llm",
            reasoning=f"llm unreachable: {e!r}",
        )

    # Parse the JSON
    try:
        import json as _json
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            raise ValueError("no JSON in response")
        parsed = _json.loads(m.group(0))
    except Exception as e:
        return ReplyClassification(
            intent=ReplyIntent.UNRELATED,
            target_request_id=target.request_id,
            confidence=0.0,
            source="llm",
            reasoning=f"llm JSON parse failed: {e}",
        )

    intent_str = str(parsed.get("intent", "")).strip().upper()
    try:
        intent = ReplyIntent[intent_str] if intent_str in ReplyIntent.__members__ else ReplyIntent.UNRELATED
    except KeyError:
        intent = ReplyIntent.UNRELATED
    try:
        confidence = float(parsed.get("confidence", 0.5))
    except Exception:
        confidence = 0.5
    reasoning = str(parsed.get("reasoning", "")).strip() or "(llm returned no reasoning)"

    return ReplyClassification(
        intent=intent,
        target_request_id=target.request_id,
        confidence=max(0.0, min(1.0, confidence)),
        source="llm",
        reasoning=f"llm: {reasoning}",
    )


# ------------------------------------------------------------------ #
#  Public entry point                                                  #
# ------------------------------------------------------------------ #

def classify_reply(
    *,
    text: Optional[str] = None,
    reaction_emoji: Optional[str] = None,
    open_cards: list[CardRecord],
    explicit_target_request_id: Optional[str] = None,
    now: Optional[float] = None,
    use_llm_fallback: bool = True,
) -> ReplyClassification:
    """Full classify pipeline. Heuristic first, LLM fallback if needed
    AND use_llm_fallback is True."""
    result = classify_reply_heuristic(
        text=text,
        reaction_emoji=reaction_emoji,
        open_cards=open_cards,
        explicit_target_request_id=explicit_target_request_id,
        now=now,
    )
    if result.intent != ReplyIntent.UNCLEAR:
        return result

    if not use_llm_fallback or not text:
        # No LLM fallback — return UNRELATED so the Jarvis loop handles
        # it as a normal conversation turn (the card stays open).
        return ReplyClassification(
            intent=ReplyIntent.UNRELATED,
            target_request_id=result.target_request_id,
            confidence=0.3,
            source="none",
            reasoning="heuristic unclear, llm fallback disabled",
        )

    target = _pick_target(open_cards, explicit_target_request_id)
    if target is None:
        return ReplyClassification(
            intent=ReplyIntent.UNRELATED,
            target_request_id=None,
            confidence=0.3,
            source="none",
            reasoning="heuristic unclear, no target to llm-check against",
        )

    return _llm_fallback(text, target)


# ------------------------------------------------------------------ #
#  Self-test                                                           #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    from dataclasses import dataclass as _dc

    print("=== card_reply_classifier self-test ===\n")

    def make_card(request_id: str = "card1", action: str = "run_shell", created_at: float = 100.0):
        return CardRecord(
            request_id=request_id,
            created_at=created_at,
            updated_at=created_at,
            status="open",
            action=action,
            params={"cmd": "apt install cowsay"},
            audit_reasoning="installs cowsay via apt",
        )

    cards = [make_card()]
    fixed_now = 1000.0

    def check(label, expected_intent, **kwargs):
        kwargs.setdefault("open_cards", cards)
        kwargs.setdefault("now", fixed_now)
        kwargs.setdefault("use_llm_fallback", False)  # offline
        r = classify_reply(**kwargs)
        got = r.intent.value
        expected = expected_intent.value if isinstance(expected_intent, ReplyIntent) else expected_intent
        ok = got == expected
        mark = "✓" if ok else "✗"
        print(f"  {mark} [{label}] expected={expected} got={got} src={r.source} conf={r.confidence:.2f}")
        if r.remind_at is not None:
            print(f"      remind_at=+{int(r.remind_at - fixed_now)}s reason={r.defer_reason!r}")
        if r.modification_request:
            print(f"      modification_request={r.modification_request!r}")
        return ok

    counts = {"passed": 0, "failed": 0}
    def run(label, expected, **kwargs):
        if check(label, expected, **kwargs):
            counts["passed"] += 1
        else:
            counts["failed"] += 1

    # Reactions
    run("react 👍", ReplyIntent.APPROVE, reaction_emoji="👍")
    run("react 👎", ReplyIntent.DENY, reaction_emoji="👎")
    run("react 🤔", ReplyIntent.RE_EXPLAIN, reaction_emoji="🤔")
    run("react ⏸️", ReplyIntent.DEFER, reaction_emoji="⏸️")
    run("react 🌮 (unrelated)", ReplyIntent.UNRELATED, reaction_emoji="🌮")

    # Approve phrases
    run("text 'yes'", ReplyIntent.APPROVE, text="yes")
    run("text 'yep'", ReplyIntent.APPROVE, text="yep")
    run("text 'go ahead'", ReplyIntent.APPROVE, text="go ahead")
    run("text 'do it'", ReplyIntent.APPROVE, text="do it")
    run("text 'ok'", ReplyIntent.APPROVE, text="ok")
    run("text 'sure fine'", ReplyIntent.APPROVE, text="sure fine")
    run("text 'ship it'", ReplyIntent.APPROVE, text="ship it")

    # Deny phrases
    run("text 'no'", ReplyIntent.DENY, text="no")
    run("text 'cancel that'", ReplyIntent.DENY, text="cancel that")
    run("text 'nope'", ReplyIntent.DENY, text="nope")
    run("text 'never mind'", ReplyIntent.DENY, text="never mind")
    run("text 'abort'", ReplyIntent.DENY, text="abort")

    # Defer with duration
    run("text 'wait 5 min'", ReplyIntent.DEFER, text="wait 5 min")
    run("text 'in an hour'", ReplyIntent.DEFER, text="in an hour")
    run("text 'ask me in 30 minutes'", ReplyIntent.DEFER, text="ask me in 30 minutes")
    run("text 'tomorrow'", ReplyIntent.DEFER, text="tomorrow")
    run("text 'after lunch'", ReplyIntent.DEFER, text="after lunch")
    run("text 'in half an hour'", ReplyIntent.DEFER, text="in half an hour")
    run("text 'hold on a minute'", ReplyIntent.DEFER, text="hold on a minute")

    # Defer open-ended
    run("text 'later'", ReplyIntent.DEFER, text="later")
    run("text 'let me think'", ReplyIntent.DEFER, text="let me think about it")
    run("text 'not right now'", ReplyIntent.DEFER, text="not right now")

    # Explain
    run("text 'what does that do'", ReplyIntent.RE_EXPLAIN, text="what does that do")
    run("text 'why would you'", ReplyIntent.RE_EXPLAIN, text="why would you do that")
    run("text 'tell me more'", ReplyIntent.RE_EXPLAIN, text="tell me more")

    # Modify
    run("text 'change it to sudo'", ReplyIntent.MODIFY, text="change it to use sudo")
    run("text 'instead of cowsay'", ReplyIntent.MODIFY, text="instead of cowsay use fortune")
    run("text 'but with -y'", ReplyIntent.MODIFY, text="but with -y")

    # Fresh requests should not get mistaken for card approvals
    run("text 'install openrgb' stays unrelated", ReplyIntent.UNRELATED, text="Install openrgb")
    run("text 'can you check logs' stays unrelated", ReplyIntent.UNRELATED, text="Can you check logs")
    run("text 'run it' still approves", ReplyIntent.APPROVE, text="run it")

    # No open cards → UNRELATED
    r = classify_reply(text="yes", open_cards=[], use_llm_fallback=False)
    assert r.intent == ReplyIntent.UNRELATED
    print(f"  ✓ [no open cards] always UNRELATED")
    counts["passed"] += 1

    # Ambiguous → UNRELATED (llm fallback off)
    r = classify_reply(text="hmm interesting", open_cards=cards, use_llm_fallback=False)
    assert r.intent == ReplyIntent.UNRELATED
    print(f"  ✓ [ambiguous + no llm] UNRELATED")
    counts["passed"] += 1

    # Target selection with multiple cards
    multi = [make_card("cA", created_at=100.0), make_card("cB", created_at=200.0)]
    r = classify_reply(text="yes", open_cards=multi, use_llm_fallback=False)
    assert r.target_request_id == "cB", f"expected newest card, got {r.target_request_id}"
    print(f"  ✓ [multi cards] targets newest")
    counts["passed"] += 1

    r = classify_reply(text="yes", open_cards=multi, explicit_target_request_id="cA", use_llm_fallback=False)
    assert r.target_request_id == "cA", f"expected explicit target, got {r.target_request_id}"
    print(f"  ✓ [multi cards + explicit target] targets cA")
    counts["passed"] += 1

    # Duration extraction sanity
    assert extract_defer_duration("5 minutes") == 300
    assert extract_defer_duration("an hour") == 3600
    assert extract_defer_duration("2 hours") == 7200
    assert extract_defer_duration("half hour") == 1800
    assert extract_defer_duration("tomorrow") == 86400
    assert extract_defer_duration("in 15 min") == 900
    assert extract_defer_duration("in a second") == 15
    assert extract_defer_duration("hello world") is None
    print(f"  ✓ extract_defer_duration edge cases")
    counts["passed"] += 1

    print(f"\n{counts['passed']} passed, {counts['failed']} failed")
    print("=== card_reply_classifier self-test complete ===")
