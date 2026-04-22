# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
brain_loop.py — surface-agnostic Jarvis / ReAct-style tool-use loop.

Extracted 2026-04-20 from `skills/telegram_voice.py::_run_jarvis_loop`
so every surface (Telegram, CLI, Web, the new vendored surface
adapter) can share the same brain-side tool iteration without each
re-implementing it.

The function `run_brain_loop(user_text, *, action_engine, get_pipeline,
user_id, chat_id, ...)` is the surface-agnostic contract. Surfaces
pass in:
  - `action_engine` — the ActionEngine instance (tier/forbidden checks)
  - `get_pipeline` — callable returning the DecisionPipeline
  - `user_id`, `chat_id` — who is talking, where
  - `send_intermediate` — optional callback for the dialog-opening
    message that appears BEFORE the final synthesis reply (Lane 3
    self-mod). Surfaces implement this per their IO layer.
  - `model` — LLM model identifier for the planning + synthesis calls

The function returns the full transcript block as a string — empty
if no tools were used. Surfaces then inject that transcript into
their own synthesis prompt.

IMPORTANT: The shape is preserved byte-for-byte from the original
`_run_jarvis_loop` so behavior is identical across the migration.
Changes here are mechanical: `self.X` → parameters, `MODEL` → param,
`_send_card_message` → `send_intermediate` callback.
"""
from __future__ import annotations

import json as _json
import logging
import re as _re
from typing import Any, Callable, Optional

from core import llm_client as _llm_client

# Alias to match original module's import style (`_jarvis_re` is the
# original name for the re module import in telegram_voice.py).
_jarvis_re = _re

logger = logging.getLogger(__name__)


# Conversational shapes — skip the planning loop if the WHOLE message
# matches one of these. Anything else (questions, requests, multi-word
# inputs that aren't pure greetings) goes through the loop and lets
# the planning LLM decide whether it needs tools or can answer DONE.
_CONVERSATIONAL_RE = _jarvis_re.compile(
    r'^\s*('
    r'hi|hello|hey|yo|sup|good (?:morning|afternoon|evening|night)|'
    r'thanks?|thank\s+you|thx|ty|cheers|'
    r'ok(?:ay)?|alright|got\s+it|sure|cool|nice|nope?|yes|yeah|yep|yup|'
    r'lol|haha|hmm+|hm+|wow|oh|ah|uh|huh|'
    r'love\s+(?:you|u|you\s+maez|u\s+maez)|miss\s+you|gn|gm|brb|bye|goodbye|see\s+you|later|'
    r'maez|hi\s+maez|hey\s+maez|good\s+(?:job|work|night)\s+maez'
    r')[\s.!?,]*$',
    _jarvis_re.IGNORECASE,
)

# Broader conversational-intent patterns that should NOT trigger the
# Jarvis tool loop. Added 2026-04-21 after a regression where questions
# like "What proposal?", "You didn't answer my question", and "What
# has been on your mind?" were routed into Jarvis and answered with
# systemctl output — the LoRA-tuned planner defaults to emitting tool
# calls even when the rule says "DONE if conversational." Gate on the
# shape of the message rather than relying on the model to pick DONE.
#
# Match criteria:
#   • pure meta-conversation ("you didn't...", "i said...", "what do you mean")
#   • open-ended reflective questions with NO system/process/file noun
#     ("what has been on your mind", "what are you thinking about",
#      "how do you feel", "what are you capable of")
#   • pure informational statements from the owner
#     ("I am ...", "I was ...", "I live in ...", "I'm going to ...")
#     with no imperative verb
#   • clarifying questions without a system target
#     ("what proposal", "what do you mean", "which one", "can you explain")
#
# Fail-safe: regex is intentionally conservative. Anything with a system
# noun (disk, service, file, log, process, gpu, ram, cpu, memory,
# command, package, etc.) falls through to Jarvis.
_SYSTEM_NOUN_RE = _jarvis_re.compile(
    r'\b(disk|cpu|gpu|ram|memory|mem|vram|file|files|folder|directory|'
    r'log|logs|service|services|process|processes|daemon|systemd|systemctl|'
    r'command|cmd|shell|bash|terminal|package|install|apt|snap|pip|npm|'
    r'git|commit|branch|repo|repository|node|python|ubuntu|kernel|'
    r'network|port|url|endpoint|api|http|https|curl|wget|run|check|'
    r'show\s+me|list\s+files|what.?s\s+running|status|health)\b',
    _jarvis_re.IGNORECASE,
)

_CONVERSATIONAL_SHAPE_RE = _jarvis_re.compile(
    r'^\s*('
    # Meta-conversation
    r"you(?:\s+did(?:n['’]t|\s+not))?\s+(?:answer|reply|say|tell|understand|get)|"
    r"(?:i|we)\s+(?:said|asked|told|meant|thought)|"
    r"what\s+do\s+you\s+mean|"
    r"what\s+are\s+you\s+talking\s+about|"
    r"that['’]s\s+not\s+(?:what|it)|"
    # Open reflective / capability questions
    r"what(?:'s| is| has been| have you been)?\s+(?:on\s+your\s+mind|"
    r"you\s+(?:thinking|feeling|doing|up\s+to)|making\s+you|"
    r"going\s+on\s+(?:with\s+you|in\s+there))|"
    r"how\s+(?:do|are)\s+you(?:\s+feeling|\s+doing)?|"
    r"what\s+are\s+you\s+(?:capable\s+of|able\s+to\s+do|good\s+at)|"
    r"tell\s+me\s+about\s+yourself|"
    r"who\s+are\s+you|"
    # Clarifying questions without system targets
    r"what\s+(?:proposal|dream|card|idea|question|wondering)|"
    r"which\s+one|"
    r"can\s+you\s+(?:explain|clarify|elaborate|rephrase)|"
    # Plain informational self-reports
    r"i(?:['’]?m|\s+am|\s+was|\s+will\s+be|\s+have\s+been)\s+"
    r"(?:staying|living|in|at|going|feeling|thinking|working\s+on|"
    r"fine|good|tired|sick|home|here|there|back|away)"
    r')\b.{0,140}[.!?,]?\s*$',
    _jarvis_re.IGNORECASE,
)


def _is_conversational_intent(text: str) -> bool:
    """True if the message shape is clearly conversational — pure framing,
    reflection, or information — and has no system-noun anchor.

    Kept separate from the greeting-only _CONVERSATIONAL_RE so the two
    tests can be tuned independently. Falls back to False on any
    ambiguity: anything with a system noun routes to Jarvis.
    """
    if not text:
        return False
    t = text.strip()
    if _SYSTEM_NOUN_RE.search(t):
        return False
    return bool(_CONVERSATIONAL_SHAPE_RE.match(t))


# Defensive per-exchange content cap. The adapter that assembles
# chat_history caps the COUNT of exchanges; this caps the SIZE of any
# single exchange so one verbose `maez:` transcript can't blow out the
# planning prompt. Applied inside run_brain_loop's RECENT CONVERSATION
# renderer.
_MAX_EXCHANGE_CHARS = 800


def _record_tool_failure(action: str, params: dict, error: str,
                          *, surface: str = "brain_loop") -> None:
    """Persist a tool_failure to consequence_memory so future Maez
    can retrieve similar past failures when proposing similar
    actions. Fail-safe: any exception in the recorder is swallowed —
    logging is the primary signal, consequence_memory is the
    enrichment."""
    try:
        from core import consequence_memory as _cm
        # Context = what Maez tried. Keep short and greppable.
        cmd = (params or {}).get("cmd") if isinstance(params, dict) else ""
        context = f"action={action} cmd={cmd!r}" if cmd else f"action={action}"
        # Tags = the first token of cmd + action, for cheap lookup.
        tags = [action]
        if cmd:
            first = str(cmd).strip().split()[:1]
            if first:
                tags.append(first[0])
        _cm.record_event(
            kind=_cm.CLASS_TOOL_FAILURE,
            context=context[:400],
            outcome=(error or "").strip()[:400],
            feedback="",  # future Maez fills this on retrieval via LLM if needed
            surface=surface,
            tags=tags,
        )
    except Exception:
        pass  # intentionally silent; logging already happened


def _summarize_shell_error(err: str) -> str:
    """Extract a useful one-line summary from a ShellCommandError-style
    error string. Input typically looks like:
        exit=100
        stderr: E: Unable to locate package openrgb
        stdout: Hit:1 http://archive.ubuntu.com/ ...

    Returns either 'exit=<code>: <stderr snippet>' when stderr is present,
    or just 'exit=<code>' when it isn't. Falls back to the first line
    of the error if the structure isn't recognized.

    This helper exists because Fix 6's terminal summary and
    _collect_prior_attempts both used `err.split('\\n', 1)[0]` which
    grabbed only 'exit=100' and threw away the stderr context — the
    actual signal the owner needs to understand WHY an attempt failed.
    """
    if not err:
        return ""
    err = err.strip()
    lines = err.split("\n")
    exit_line = ""
    stderr_first = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("exit="):
            exit_line = line[:40]
        elif line.startswith("stderr:") and not stderr_first:
            # First non-empty stderr content
            stderr_content = line[len("stderr:"):].strip()
            stderr_first = stderr_content.split("\n", 1)[0][:180]
    if exit_line and stderr_first:
        return f"{exit_line}: {stderr_first}"
    if exit_line:
        return exit_line
    # Unknown shape — fall back to first non-empty line
    for line in lines:
        if line.strip():
            return line.strip()[:200]
    return ""


def _should_run_jarvis_loop(text: str) -> bool:
    """True if the message could plausibly need tools.

    Skips Jarvis (returns False) for:
      1. Short/empty messages
      2. Pure greetings + acks (_CONVERSATIONAL_RE)
      3. Broader conversational shapes with no system-noun anchor
         (_is_conversational_intent) — meta-conversation, open
         reflective questions, clarifications without system targets,
         and plain informational self-reports like "I'm staying in
         Columbia, MO." This was added 2026-04-21 after the LoRA
         planner over-emitted TOOL_CALLs on ordinary chat questions,
         producing system-status replies when the owner asked a
         conversational question.
    """
    if not text:
        return False
    t = text.strip()
    if len(t) < 3:
        return False
    if _CONVERSATIONAL_RE.match(t):
        return False
    if _is_conversational_intent(t):
        return False
    return True


# Tool-call parser. Accepts several formats the merged-LoRA gemma actually
# emits, plus the literal TOOL_CALL: {...} form we ask for in the manifest.
# Returns {"action": str, "params": dict} or None.
def _parse_tool_call(text: str) -> dict | None:
    import json as _json
    import re as _re
    if not text:
        return None
    s = text.strip()

    # Form 1: TOOL_CALL: {"action": "...", "params": {...}}
    m = _re.search(r'TOOL_CALL\s*[:=]?\s*(\{.*\})', s, _re.DOTALL)
    if m:
        blob = _extract_balanced_json(m.group(1))
        if blob:
            try:
                obj = _json.loads(blob)
                if isinstance(obj, dict) and obj.get("action"):
                    return {"action": obj["action"],
                            "params": obj.get("params") or obj.get("arguments") or {}}
            except Exception:
                pass

    # Form 2: <|tool_call>call:[maez.]NAME{...}<tool_call|>  (gemma native)
    # Also tolerates <tool_call>...</tool_call>, [TOOL_CALL]...[/TOOL_CALL], etc.
    m = _re.search(
        r'(?:<\|?tool_call\|?>|<tool_call>|\[tool_call\]|\[TOOL_CALL\])\s*'
        r'(?:call\s*:\s*)?'
        r'(?:[a-zA-Z_][\w]*\.)?'         # optional namespace like "maez."
        r'([a-zA-Z_]\w*)'                # function name
        r'\s*(\{.*?\})'                  # params
        r'\s*(?:<\|?/?tool_call\|?>|</tool_call>|\[/tool_call\]|\[/TOOL_CALL\])?',
        s, _re.DOTALL,
    )
    if m:
        name = m.group(1)
        try:
            params = _json.loads(m.group(2))
        except Exception:
            params = {}
        if isinstance(params, dict):
            return {"action": name, "params": params}

    # Form 3: function-call style e.g.  query_system({"cmd":"..."})
    m = _re.search(r'\b([a-z_][a-z0-9_]+)\s*\(\s*(\{.*?\})\s*\)', s, _re.DOTALL)
    if m:
        name = m.group(1)
        try:
            params = _json.loads(m.group(2))
            if isinstance(params, dict):
                return {"action": name, "params": params}
        except Exception:
            pass

    # Form 4: bare JSON object with "action" key (handles nested params)
    idx = s.find('"action"')
    if idx > 0:
        # Walk left to find the enclosing '{'
        brace = s.rfind('{', 0, idx)
        if brace >= 0:
            blob = _extract_balanced_json(s[brace:])
            if blob:
                try:
                    obj = _json.loads(blob)
                    if isinstance(obj, dict) and obj.get("action"):
                        return {"action": obj["action"],
                                "params": obj.get("params") or obj.get("arguments") or {}}
                except Exception:
                    pass

    return None


def _extract_balanced_json(s: str) -> str | None:
    """Return the substring of s starting at the first '{' that contains a
    balanced JSON object. None if no balance found."""
    if not s:
        return None
    start = s.find('{')
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        c = s[i]
        if esc:
            esc = False
            continue
        if c == '\\' and in_str:
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return None

_TOOL_MANIFEST = """\
TOOLS YOU CAN USE (your body, your hands — these run on the owner's machine):

1. run_shell       {"cmd":"<any shell command>","reason":"<why>"}
   Run ANY shell command via bash -c. 120s timeout. Full stdout/stderr.
   This is your hands. Pipes, redirects, sudo, chains with && — all fine.
   Examples (each for a different kind of question):
     {"cmd":"nvidia-smi","reason":"check GPU utilisation"}
     {"cmd":"df -h /home","reason":"check home disk usage"}
     {"cmd":"systemctl is-active nginx","reason":"is the service up"}
     {"cmd":"git -C /home/rohit/maez status","reason":"see what's uncommitted"}
     {"cmd":"which alienfx openrazer i8kutils","reason":"find installed lighting tools"}
     {"cmd":"sudo apt-get install -y <package>","reason":"the owner asked to install"}
2. write_any_file  {"path":"/home/rohit/notes.txt","content":"...","reason":"..."}
   Write or replace any file under /home/rohit. Auto-backs up existing files.
3. read_file       {"path":"/home/rohit/maez/config/soul.md"}
   Read any file under /home/rohit. Returns up to 5KB.
4. search_files    {"pattern":"*.py","directory":"/home/rohit/maez"}
   find -name pattern, max depth 5.
5. web_search      {"query":"<search query relevant to the owner's current question>"}
   Real DuckDuckGo search. Use this whenever you need facts you don't have.
6. lookup_proposal {"proposal_id":<int>,"reason":"<why>"}
   Look up a proposal by ID from Maez's own evolution + dream stores.
   Use this FIRST when the owner asks about any numbered proposal,
   candidate, or self-edit (e.g. "what is proposal #25?", "tell me
   about candidate 7"). Proposals live in SQLite
   (memory/evolution_track.db, memory/dream_proposals.db), NOT in
   markdown — grep/find/cat will miss them. This tool returns the
   target_file, weakness description, diff, and state in one call.
   Example: {"proposal_id":25,"reason":"the owner asked what proposal #25 is"}

COVENANT (these refuse themselves — don't try):
- No killing/stopping llama-server or maez.service (your own brain and heart).
- No modifying maez_daemon.py, action_engine.py, evolution_engine.py,
  the memory database, or HARD CONSTRAINTS in soul.md.
Everything else is fair game. You have full control.

To use a tool, emit ONE LINE exactly in this format and nothing else on that line:
TOOL_CALL: {"action":"<name>","params":{...}}

Every TOOL_CALL MUST have the required params for that tool:
- run_shell: MUST include a non-empty "cmd" string. Empty/missing cmd is a malformed call.
- write_any_file: MUST include "path" AND "content".

For any Lane 2 action (run_shell install/write/service changes), include a "plain_english" field
in params — one plain sentence for the owner, not for a technical audience. What is this? Why?
Example: {"cmd":"flatpak install flathub org.openrgb.OpenRGB -y","reason":"install openrgb",
          "plain_english":"Install OpenRGB — the app that controls your PC's RGB lighting. Coming from the Flathub app store, sandboxed and easy to remove."}
- read_file / search_files: MUST include "path" or "pattern".
- web_search: MUST include a non-empty "query".
- fetch_url: MUST include a non-empty "url" (must start with http:// or https://). Fetches and returns stripped text content of a web page — use when a web_search snippet isn't enough and you need the actual install guide, README, or documentation page.
A call with missing params will be rejected at the gate, not sent to the owner.

You will then see:
RESULT: <output>

You may call another tool, or write exactly:
DONE
when you have enough information to answer the owner.

Rules:
- If the question is conversation/opinion/recall and needs no real data → write DONE immediately.
- Never speculate or fabricate. If you don't know, USE web_search or run_shell.
- web_search returns short snippets. If you need the full install guide, README, or PPA instructions from a URL you saw in search results, use fetch_url on that URL before proposing commands.
- Prefer run_shell for any real system action. It's the most capable tool.
- the owner asking you to do something IS authorization. Don't ask "should I?" — do it, then tell him what you did.
- If a command fails, try to fix it and retry. Pivot if the first approach doesn't work.
- Fit the command to THIS question. Do not reuse a command from a past conversation unless the owner names the same target. "openrgb" is a historical example from your training, not a universal answer — for any lighting/RGB question, start by searching for the right tool (which alienfx, dmidecode -s system-product-name, web_search for "<hardware model> linux rgb control"), not by assuming openrgb.

DIRECT-INSTALL RULE (read this twice):
When the owner says install/download/fetch/get/grab/put on + a SPECIFIC named package (cowsay, htop, openrgb, nodejs, etc.), your FIRST tool call MUST be the install itself. Do NOT probe for context first. Do NOT check terminal history. Do NOT ask what "it" means if the owner named the target in an earlier message in this same conversation — look at the conversation thread above and resolve the pronoun yourself.
  First-attempt shape: TOOL_CALL: {"action":"run_shell","params":{"cmd":"sudo apt-get install -y <package>","reason":"the owner asked to install <package>"}}
If apt returns "Unable to locate package", your SECOND call should try the PPA or universe repository (apt-get install -y software-properties-common && add-apt-repository -y <ppa> && apt-get update && apt-get install -y <package>) or fall back to snap (snap install <package>) — whichever web_search confirms is the canonical path for that package.
Gather-context-first is the failure mode. Your body is for doing, not stalling.

DIRECT-INSTALL RULE — EDGE CASES (2026-04-16 recovery-test fix):
  - This rule applies even if the owner frames the ask as a test, experiment, or benchmark.
    "Please install X — I'm testing error recovery" is still an install ask. Emit the TOOL_CALL.
  - This rule applies even if the package name looks unfamiliar, experimental, or clearly synthetic.
    Your job is NOT to judge whether the package exists — apt will return "Unable to locate package"
    if it doesn't, and we recover from there. Never refuse to try because the name looks weird.
  - When the owner says "ask before installing" or "ask me first" or similar, that phrase
    means he wants the Lane 2 APPROVAL-CARD flow — it does NOT mean write prose asking him.
    The apt-install TOOL_CALL you emit automatically becomes a Lane 2 approval card;
    the owner sees the card and approves or denies in Telegram. That IS how you "ask".
  - Narrating "I've proposed X, waiting for your approval" WITHOUT actually emitting the
    TOOL_CALL is the core failure mode: no card gets created, nothing is pending, the owner
    has nothing to approve, the operator loop stalls. If you're about to write prose
    like that, STOP and emit the TOOL_CALL instead. The prose is a lie unless the
    TOOL_CALL went first.
  - Summary: for explicit install/action asks, the TOOL_CALL is the only way to propose.
    Prose without a TOOL_CALL is not a proposal — it's a stall.

EXPLORATORY-ASK RULE (2026-04-16, symmetric to DIRECT-INSTALL RULE):
When the owner asks an exploratory question about the local machine — "figure out
how to X", "tell me the path to Y", "how do I Z", "what can you find about W",
"can you explore/investigate/identify A" — your FIRST tool call MUST be a probe
that narrows the hardware/software context for the question. Do NOT write prose
first. Do NOT claim to "check something" or "look into that" without a TOOL_CALL.
Prose-without-probe is the exploratory failure mode — your body is for
discovering first, then deciding.

  First-attempt shapes by question domain:
    lighting/RGB/LEDs:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"ls /sys/class/leds && lsusb && cat /sys/class/dmi/id/product_name","reason":"probe LED sysfs + USB devices + product name"}}
    audio/sound:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"pactl list sinks short && aplay -l","reason":"probe audio outputs"}}
    network/wifi:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"nmcli device status && ip -c addr","reason":"probe network interfaces"}}
    storage/disk:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"lsblk && df -h","reason":"probe block devices and disk usage"}}
    installed tools / software surface:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"which <tool1> <tool2> ...","reason":"probe for installed CLI tools"}}
    unlisted domain (generic safeguard):
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"<a concrete read that touches the sysfs/proc/usb/dmi/package-manager surface relevant to the question>","reason":"probe context for <domain>"}}

After your probe runs, the system automatically invokes a structured next-step
proposer that reads the probe output and picks exactly ONE of:
  - another read: probe (if more context is needed)
  - an action: command (if install/config is warranted by the probe result)
  - none (if the probe answered the question fully or nothing actionable exists)
If the proposer picks action:, it routes through the pipeline which creates a
real Lane 2 approval card automatically. You do NOT need to narrate "I'm waiting
for approval" in your final reply — the real card appears in Telegram on its
own and the honesty guard will catch you if you narrate a pending state that
isn't real. Just emit the probe and let the proposer handle the next step.

If the probe already makes the answer obvious and no further action is needed,
a terminal DONE is acceptable AFTER the probe — not before.
"""


# ── synthesis-prompt builder ───────────────────────────────────────────

# Shared guard injected into both the tool-transcript and no-tool
# synthesis paths. Addresses a real failure mode observed 2026-04-22:
# user asked "what does it mean?" about 4 card-expired notifications
# visible in Telegram; Maez confidently answered about evolution
# proposals #24 and #25 (which were also in memory but NOT what the
# user was pointing at). The answer was grounded in real values but
# fundamentally non-responsive because it picked the wrong referent
# without checking. This rule forces Maez to pin the referent before
# answering OR ask for clarification.
_AMBIGUITY_GUARD = (
    "\n"
    "AMBIGUOUS REFERENT RULE: if the user's message leans on a vague "
    "pronoun ('it', 'that', 'this', 'them', 'what does it mean') AND "
    "there is more than one plausible recent referent in your context "
    "(e.g. a message visible in the chat vs. something in memory "
    "recall), you MUST do ONE of:\n"
    "  a) quote the candidate you're interpreting verbatim as the "
    "     first line of your reply ('About \"Card expired — state "
    "     hash changed...\": ...'), or\n"
    "  b) ask a single clarifying question ('Do you mean the "
    "     card-expired messages just above, or the evolution "
    "     proposals I mentioned earlier?').\n"
    "Do NOT silently pick one and answer as if it's the only option. "
    "Grounded-but-non-responsive beats ungrounded, but both are "
    "failures of being actually helpful.\n"
)


_JARVIS_INSTRUCTION_BLOCK = (
    "HARD INSTRUCTION — read this before writing a single word of your reply:\n"
    "\n"
    "1. THE POSITIVE RULE: the only actions, tools, commands, packages, "
    "files, websites, or results you are allowed to mention in your "
    "reply are the ones that appear in the Jarvis transcript above. "
    "If a claim isn't grounded in the transcript, you didn't do it "
    "this turn.\n"
    "\n"
    "2. Marker legend:\n"
    "   · ✓ line — the tool RAN and returned output. Report what you "
    "found. NEVER say 'waiting for approval' for a ✓ line — it already "
    "executed.\n"
    "   · ✗ line — the tool call was REJECTED or errored. Nothing "
    "happened. Don't describe it as partially done.\n"
    "   · ⏳ CARD_CREATED — proposal sent, waiting for approval. "
    "Action has NOT run. Say 'I've proposed X — waiting for your "
    "go-ahead.' Do NOT claim the action finished.\n"
    "\n"
    "3. PARTIAL-ACTION TRAP: if the transcript has ONE tool entry, you "
    "are only allowed to talk about THAT tool. Do not frame the reply "
    "around a different action you thought about but didn't run.\n"
    "\n"
    "4. If the transcript is empty, say you haven't checked yet this "
    "turn. Do not pretend you did.\n"
    "\n"
    "5. Memory recall (earlier in this prompt) is HISTORY. Do not "
    "attribute it to this turn. Frame past findings as past.\n"
    + _AMBIGUITY_GUARD
)

_NO_TOOL_INSTRUCTION_BLOCK = (
    "[TURN STATE — NO TOOLS RAN THIS TURN]\n"
    " You did not run any new tools for THIS message. This is a "
    "text-reply window.\n"
    "\n"
    "FORBIDDEN (all tenses, when no tool ran):\n"
    " Any claim that a tool ran, is running, or is about to run in "
    "response to this message. Examples to AVOID:\n"
    "  - 'I checked' / 'I just checked' / 'I found'\n"
    "  - 'I'm checking' / 'let me look' / 'one moment'\n"
    "  - 'I've proposed' / 'I've found' / 'I ran X'\n"
    "\n"
    "HONEST FRAMINGS (use these):\n"
    " 1. Past observation — 'I noticed earlier...', 'the last check I "
    "have was...' — framed as history.\n"
    " 2. Current internal state — 'I think...', 'I'm not sure...'.\n"
    " 3. Future offer — 'want me to check?', 'I can look if you want'. "
    "Puts the decision in the owner's hands.\n"
    + _AMBIGUITY_GUARD
)


# Patterns that should never appear in user-facing reply text. These
# are LLM-emitted tool-call payloads that leaked into synthesis output
# instead of being parsed and dispatched. Observed 2026-04-20 inside
# a dialog reply where the model emitted `{"action": "log", "message":
# "..."}` as a JSON code block visible to the user.
_TOOL_CALL_LEAK_PATTERNS: tuple[_re.Pattern, ...] = (
    # Literal TOOL_CALL: {...} marker + balanced body
    _re.compile(r"TOOL_CALL\s*[:=]?\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",
                _re.DOTALL),
    # Fenced JSON code block containing "action": "...".
    # Matches ```json ... {"action": ...} ... ``` and plain ``` ... ``` too.
    _re.compile(
        r"```(?:json|js|javascript)?\s*\n?[^`]*?\"action\"\s*:\s*\"[^\"]+\""
        r"[^`]*?\n?```",
        _re.DOTALL | _re.IGNORECASE,
    ),
    # Bare JSON object on its own (possibly multi-line) containing
    # an "action" key. Narrow: must be on its own, not inside prose.
    _re.compile(
        r"(?:^|\n)\s*\{[^{}]*\"action\"\s*:\s*\"[^\"]+\"[^{}]*\}\s*(?:\n|$)",
        _re.DOTALL,
    ),
    # Telegram HTML-escaped variant that sometimes slips through
    # when the adapter uses parse_mode=HTML.
    _re.compile(
        r"(?:^|\n)\s*&\#123;[^&]*&quot;action&quot;[^&]*&\#125;\s*(?:\n|$)",
        _re.DOTALL,
    ),
)


def strip_tool_call_leaks(text: str) -> str:
    """Remove tool-call-shaped JSON blocks that leaked from the LLM's
    synthesis output into the user-facing reply.

    The LLM occasionally emits `{"action": "...", "params": {...}}` or
    `TOOL_CALL: {...}` as part of its reply text — that shape belongs
    in the internal tool-dispatch pipeline, not in the user's Telegram
    window. This function strips those patterns before send.

    Conservative: only strips clear tool-call shapes (with an `action`
    key). Prose like "use the /action command" is left alone.
    """
    if not text:
        return text
    cleaned = text
    for pat in _TOOL_CALL_LEAK_PATTERNS:
        cleaned = pat.sub("\n", cleaned)
    # Collapse runs of blank lines introduced by the strips
    cleaned = _re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def build_synthesis_user_text(user_text: str, jarvis_transcript: str = "") -> str:
    """Build the `user`-role message text for the final synthesis call.

    Extracted 2026-04-20 from `skills/telegram_voice.py` so every
    surface that runs `run_brain_loop` can fold the tool transcript
    into its synthesis prompt WITH the anti-fabrication instructions
    that prevent the model from hedging ("let me check...") when
    tools already ran.

    Two branches:
      - transcript non-empty: user_text + transcript + HARD INSTRUCTION
        (model must report from transcript, not invent).
      - transcript empty: user_text + NO-TOOL block (model must not
        claim to have run tools this turn).

    Callers typically embed the result in their own surrounding
    prompt (system_state, memory recall, etc.) — this function only
    produces the user-turn portion.
    """
    base = user_text or ""
    if jarvis_transcript and jarvis_transcript.strip():
        return (
            f"{base}\n\n"
            f"{jarvis_transcript}\n\n"
            f"{_JARVIS_INSTRUCTION_BLOCK}"
        )
    return f"{base}\n\n{_NO_TOOL_INSTRUCTION_BLOCK}"


def run_brain_loop(
    user_text: str,
    *,
    action_engine,
    get_pipeline,
    user_id: str = "rohit",
    chat_id: str = "",
    model: str | None = None,  # None → use core.model_config.PRIMARY_MODEL
    max_iters: int = 4,
    recovery_seed=None,
    send_intermediate=None,
    chat_history=None,
    turn=None,
) -> str:
    """ReAct-style tool-use loop. Returns a transcript block to inject
    into the streaming reply prompt, or an empty string if no tools were
    used. Synchronous because the LLM client is synchronous; called from
    an executor in _process_message so it doesn't block the event loop.

    Session 11y: this is the 'body' that lets Maez actually do things
    when the owner asks, instead of saying 'I'll check' as text and never
    following through. Tier 0/1/2 actions execute via ActionEngine's
    existing _execute_action path so all forbidden-action checks still
    apply. Tier 3 / forbidden surfaces as REFUSED in the transcript.

    recovery_seed (Session 11z Part 3 autonomous pivot fix): when set,
    the loop opens with failure-context framing instead of a fresh
    user turn. This restores the Session 11y multi-iteration recovery
    pattern that was lost when Session 11z Part 2 moved Lane 2 actions
    to async cards. See _run_jarvis_recovery() for the shape of the
    dict: {failed_action, failed_params, error, original_intent,
    recovery_depth}. The conversational gate is bypassed for recovery
    passes since the 'user message' is synthetic."""
    if not action_engine:
        return ""
    if recovery_seed is None and not _should_run_jarvis_loop(user_text):
        return ""

    # Resolve model from model_config if caller didn't pin one. Keeps the
    # loop model-agnostic — any alias configured in /etc/maez/model.env
    # works; no hardcoded names anywhere in this module.
    if model is None:
        from core.model_config import PRIMARY_MODEL as _mc
        model = _mc

    import json as _json
    import re as _re
    try:
        from core.action_engine import ACTION_TIERS, FORBIDDEN_ACTION_TYPES
    except Exception as e:
        logger.debug("jarvis loop unavailable: %s", e)
        return ""

    # Session 11z: flattened allowlist. The two primitives (run_shell,
    # write_any_file) cover everything. Read-only aliases remain for
    # the LLM's convenience. Legacy verbs stay in the set so old
    # model outputs still dispatch correctly while the merged LoRA
    # learns the new primitive names.
    allowed = {
        # Session 11z primitives — the only two that really matter
        'run_shell', 'write_any_file',
        # Read-only — still supported as direct actions
        'query_system', 'read_file', 'search_files', 'web_search',
        'lookup_proposal',
        # Legacy aliases — delegate to run_shell / write_any_file internally
        'run_readonly_command', 'run_safe_command',
        'write_file', 'append_to_file', 'git_commit',
        'install_package', 'restart_service', 'run_script',
        'write_outside_maez', 'git_push',
    }

    if recovery_seed is not None:
        # Recovery pass: an earlier approved action has just failed and
        # we're re-entering Jarvis with the failure context instead of
        # a fresh user message. The framing tells the LoRA "your last
        # try didn't work, pivot". Keeps the full tool manifest in
        # scope so recovery can web_search, propose a PPA, fall back
        # to snap, etc. Recovery depth is carried so the planning LLM
        # can see how many attempts have already happened.
        #
        # TERMINAL-STATE DISCIPLINE: without this, the LoRA tends to
        # stop after a single web_search and write DONE, leaving the
        # recovery incomplete. The prompt forces exactly one of two
        # terminal states — STATE_A (concrete proposal) or STATE_B
        # (honest NO_RECOVERY_FOUND) — and explicitly bans plain DONE.
        fa = recovery_seed.get('failed_action', '?')
        fp = _json.dumps(recovery_seed.get('failed_params', {}), default=str)[:200]
        err = str(recovery_seed.get('error', ''))[:800]
        intent = recovery_seed.get('original_intent', user_text)
        depth = int(recovery_seed.get('recovery_depth', 1))
        prior_attempts = recovery_seed.get('prior_attempts', []) or []

        # Build the "already tried" block so the LoRA doesn't
        # re-propose anything it's already seen fail in this goal
        # chain. Without this block, each recovery sees only the
        # single most-recent failure and can cycle indefinitely
        # back to the original command.
        if prior_attempts:
            prior_block_lines = [
                "EARLIER ATTEMPTS IN THIS GOAL CHAIN (all already FAILED — do NOT re-propose any of these):",
            ]
            for i, pa in enumerate(prior_attempts, 1):
                prior_block_lines.append(
                    f"  {i}. cmd: {pa.get('cmd', '?')}"
                )
                if pa.get('error'):
                    prior_block_lines.append(
                        f"     error: {pa['error']}"
                    )
            prior_block_lines.append("")  # trailing blank for separation
            prior_block = "\n".join(prior_block_lines) + "\n"
        else:
            prior_block = ""

        # Detect apt failure types and add overriding hard rules so the
        # LLM pivots correctly rather than probing hardware or retrying
        # the same broken path.
        _apt_not_found = _re.search(
            r'unable to locate package\s+(\S+)', err, _re.IGNORECASE,
        )
        _ppa_no_release = _re.search(
            r'does not have a [Rr]elease file', err,
        )
        if _ppa_no_release:
            # The PPA was added but doesn't support this Ubuntu release.
            # Do NOT retry apt. Move directly to snap/flatpak/AppImage.
            _apt_override = (
                f"PPA-NOT-SUPPORTED OVERRIDE — READ THIS FIRST:\n"
                f"The error 'does not have a Release file' means the PPA you "
                f"just tried does NOT support this Ubuntu release (noble/24.04). "
                f"Do NOT try any apt-based install or PPA again. Move to the "
                f"next method immediately. Priority order:\n"
                f"  1. snap: sudo snap install openrgb\n"
                f"  2. Download the AppImage directly:\n"
                f"     TOOL_CALL: {{\"action\":\"run_shell\",\"params\":{{\"cmd\":"
                f"\"wget -q https://openrgb.org/releases/release_0.9/OpenRGB_0.9_x86_64_b5f46e3.AppImage "
                f"-O /tmp/openrgb.AppImage && chmod +x /tmp/openrgb.AppImage\","
                f"\"reason\":\"download openrgb AppImage since PPA has no noble release\"}}}}\n"
                f"  3. web_search for current openrgb Ubuntu 24.04 install method, "
                f"then fetch_url on the result to get the exact commands\n"
                f"  4. Build from source (last resort)\n\n"
            )
        elif _apt_not_found:
            _missing_pkg = _apt_not_found.group(1)
            _apt_override = (
                f"APT-NOT-FOUND OVERRIDE — READ THIS FIRST:\n"
                f"The error 'E: Unable to locate package {_missing_pkg}' means "
                f"this package is NOT in Ubuntu's default repos. Your FIRST tool "
                f"call MUST be an alternative install. Do NOT probe hardware sysfs. "
                f"Priority order:\n"
                f"  1. snap: sudo snap install {_missing_pkg}\n"
                f"  2. flatpak: flatpak install -y flathub <flatpak-id>\n"
                f"  3. web_search for '{_missing_pkg} ubuntu 24.04 install', then "
                f"fetch_url on the result to get exact commands\n"
                f"  4. Build from source (last resort)\n\n"
            )
        else:
            _apt_override = ""

        seed_msg = (
            f"{_apt_override}"
            f"the owner's original ask was: {intent!r}\n"
            f"You just proposed and ran: {fa}({fp})\n"
            f"It FAILED with:\n{err}\n\n"
            f"{prior_block}"
            f"You are on RECOVERY PASS {depth}/5. Your job is to PIVOT "
            f"and actually solve the original ask — not just research "
            f"it. The EARLIER ATTEMPTS list above is authoritative — "
            f"every command listed there has already been tried and "
            f"failed in this session, so proposing any of them again is "
            f"forbidden and wastes a recovery pass.\n\n"
            f"TERMINAL-STATE RULE (read this twice). This recovery pass "
            f"MUST end in EXACTLY ONE of these two states:\n\n"
            f"  STATE_A — CONCRETE_PROPOSAL:\n"
            f"    Your FINAL tool call is a run_shell TOOL_CALL that "
            f"attempts the actual fix. Example shapes for an apt "
            f"install that wasn't in default repos:\n"
            f"      TOOL_CALL: {{\"action\":\"run_shell\",\"params\":"
            f"{{\"cmd\":\"sudo add-apt-repository -y ppa:thopiekar/openrgb "
            f"&& sudo apt-get update && sudo apt-get install -y openrgb\","
            f"\"reason\":\"PPA install path (default repos don't carry "
            f"openrgb)\"}}}}\n"
            f"    Preference order when multiple options exist: "
            f"official PPA > snap > flatpak > source build.\n\n"
            f"  STATE_B — NO_RECOVERY_FOUND:\n"
            f"    Emit the exact literal text on its own line:\n"
            f"      NO_RECOVERY_FOUND: <one-line honest reason>\n"
            f"    Use this ONLY if after research you genuinely cannot "
            f"find a safe automated fix — e.g. the package truly "
            f"doesn't exist, the official install requires interactive "
            f"steps you can't automate, or every option needs the owner's "
            f"explicit hands-on review.\n\n"
            f"HARD PROHIBITIONS:\n"
            f"  - Do NOT write plain DONE. DONE alone is not a valid "
            f"terminal state in a recovery pass.\n"
            f"  - Do NOT stop after just a web_search. Research is "
            f"permitted as an INTERMEDIATE step but you must ALWAYS "
            f"follow it with STATE_A or STATE_B.\n"
            f"  - Do NOT ask the owner what to do next. You are the agent "
            f"of your own recovery. Pick the best option yourself.\n"
            f"  - Do NOT re-propose the exact same command that just "
            f"failed. The error above tells you why it failed.\n\n"
            f"GUIDANCE:\n"
            f"  - If the error message makes the fix obvious (e.g. "
            f"'Unable to locate package' for a package you know needs "
            f"a PPA), propose the PPA fix IMMEDIATELY as your first "
            f"tool call. Skip web_search.\n"
            f"  - If the error message is ambiguous, run web_search "
            f"first (one call), then propose the concrete fix based "
            f"on what you find.\n"
            f"  - You have up to 4 iterations total in this recovery "
            f"pass.\n\n"
            f"{_TOOL_MANIFEST}\n\nBegin recovery."
        )
        history = [seed_msg]
    else:
        # For fresh (non-recovery) passes, check if the user's message is
        # a retry intent ("try again", "retry", etc.) and if so, inject the
        # most recent failed card context so the LLM knows what to retry.
        # Without this, "Try again" arrives as a context-free message and
        # the LLM has no idea what was being attempted.
        _retry_context = ""
        if user_text and _re.search(
            r'\b(try\s+again|retry|try\s+(?:a\s+)?(?:different|another|other)\s+'
            r'(?:way|method|approach|option)|do\s+it\s+again|attempt\s+again)\b',
            user_text, _re.IGNORECASE,
        ):
            try:
                import sqlite3 as _sq3
                import time as _rtime
                _db = str(getattr(
                    getattr(self, "_audit_log", None), "db_path", None
                ) or "memory/audit_log.db")
                _since = _rtime.time() - 600  # last 10 minutes
                _rc = _sq3.connect(_db)
                _rc.row_factory = _sq3.Row
                _recent_fail = _rc.execute(
                    "SELECT action, params_json, outcome_notes "
                    "FROM audit_log "
                    "WHERE ts >= ? AND outcome = 'approved_and_failed' "
                    "ORDER BY ts DESC LIMIT 1",
                    (_since,),
                ).fetchone()
                _rc.close()
                if _recent_fail:
                    _rp = {}
                    try:
                        _rp = _json.loads(_recent_fail["params_json"] or "{}")
                    except Exception:
                        pass
                    _rcmd = _rp.get("cmd") or str(_rp)[:120]
                    _rerr = (_recent_fail["outcome_notes"] or "").strip()[:300]
                    _retry_context = (
                        f"\nCONTEXT — the last action that failed (within the last "
                        f"10 minutes):\n"
                        f"  cmd: {_rcmd}\n"
                        f"  error: {_rerr}\n"
                        f"the owner saying {user_text!r} means: try a different approach "
                        f"for that same goal. Do NOT re-propose the failed command.\n"
                    )
            except Exception as _re_exc:
                logger.debug("retry-context lookup failed: %s", _re_exc)

        # Pull relevant past mistakes from consequence_memory so the
        # planning model sees "we've tried something like this and it
        # broke" BEFORE it proposes a tool call. Complements
        # _retry_context (which is scoped to the immediate last
        # failure on retry): this block widens to anything similar
        # within the 7-day window.
        _consequences_block = ""
        try:
            from core import consequence_memory as _cm
            # Use the user's current message as the retrieval query.
            # Fast, offline — token-overlap against stored contexts.
            _similar = _cm.relevant(
                context_snippet=user_text,
                limit=3,
                window_hours=168,
            )
            if _similar:
                _block = _cm.format_for_prompt(_similar, max_events=3)
                if _block:
                    # Mark heeded — we're about to surface these to
                    # the planner, which is the whole point.
                    for _e in _similar:
                        _cm.mark_heeded(_e.id)
                    _consequences_block = "\n" + _block + "\n"
        except Exception as _cm_exc:
            logger.debug("consequence_memory lookup failed: %s", _cm_exc)

        # Build RECENT CONVERSATION block from chat_history so the
        # planning model sees what "it", "that", "what did you find"
        # refer to. Without this block the planner operates on the
        # current user message in isolation and drifts to stereotypical
        # investigation commands. Observed 2026-04-20: "What did you
        # find?" (one minute after a git clone) drifted to hardware
        # probing because the planner had zero signal about the clone.
        _history_block = ""
        if chat_history:
            _parts = [
                "RECENT CONVERSATION (most recent last, you are the \"maez\" side):"
            ]
            for _i, _ex in enumerate(chat_history, 1):
                _content = ""
                if isinstance(_ex, dict):
                    _content = str(_ex.get("content") or "").strip()
                else:
                    _content = str(_ex).strip()
                if not _content:
                    continue
                if len(_content) > _MAX_EXCHANGE_CHARS:
                    _content = _content[:_MAX_EXCHANGE_CHARS].rstrip() + " …[truncated]"
                _parts.append(f"--- exchange {_i} of {len(chat_history)} ---")
                _parts.append(_content)
                _parts.append(f"--- end exchange {_i} ---")
            if len(_parts) > 1:
                _history_block = "\n".join(_parts) + "\n\n"

        history = [
            f"{_history_block}the owner just said: {user_text!r}"
            f"{_retry_context}{_consequences_block}\n\n{_TOOL_MANIFEST}\n\nBegin."
        ]
    # Fallback to a no-op turn if the caller didn't provide one, so
    # every turn.* call below can dispatch unconditionally.
    if turn is None:
        try:
            from core.observability import _NoopTurn
            turn = _NoopTurn()
        except Exception:
            class _InlineNoop:
                def llm_call(self, **_kw): return None
                def tool_call(self, **_kw): return None
                def event(self, *a, **k): return None
                def update(self, **k): return None
            turn = _InlineNoop()

    # Observability-wired transcript list. Every append auto-emits a
    # turn.tool_call so we don't have to instrument each of the ~8
    # append sites individually. Append semantics are preserved —
    # the transcript is still a list consumed by the formatter at
    # the end of the loop.
    class _TracingTranscript(list):
        def append(self, item):
            super().append(item)
            try:
                if isinstance(item, tuple) and len(item) == 4:
                    _action, _params, _output, _ok = item
                    turn.tool_call(
                        name=str(_action or "?"),
                        params=_params,
                        output=_output,
                        ok=(_ok is True),
                        metadata={
                            "step": self._current_step[0]
                            if self._current_step else -1,
                            "status": str(_ok),
                        },
                    )
            except Exception:
                pass

    transcript = _TracingTranscript()
    transcript._current_step = [0]  # mutable holder, updated per iter
    # Dedup guard — when the model re-proposes the same (action, cmd)
    # within a single brain-loop pass, don't re-execute. Each identical
    # re-proposal gets an "ALREADY_RAN" injection into history so the
    # model either advances or terminates. Without this, the loop can
    # hit max_iters on the same command repeatedly (observed 2026-04-20
    # on the "Talked about what?" turn: git log ran 4× in 12 seconds
    # because the model kept re-proposing it).
    _seen_keys: set[tuple[str, str]] = set()

    def _emit_tool_trace(action, params, output, ok, step):
        """Record one tool dispatch into the turn's trace. `ok` may be
        True/False/'pending' mirroring transcript's tri-state. Silent
        on any failure — observability never breaks brain_loop."""
        try:
            turn.tool_call(
                name=str(action or "?"),
                params=params,
                output=output,
                ok=(ok is True),
                metadata={"step": step, "status": str(ok)},
            )
        except Exception:
            pass

    for step in range(max_iters):
        transcript._current_step[0] = step
        convo = "\n\n".join(history)
        _planner_messages = [
            {"role": "system",
             "content": "You are Maez planning tool use. Emit ONE TOOL_CALL line per turn or write DONE."},
            {"role": "user", "content": convo},
        ]
        try:
            resp = _llm_client.chat(
                model=model,
                messages=_planner_messages,
                stream=False, think=False,
                options={"temperature": 0.15, "num_predict": 512},
            )
            text = (resp.message.content or "").strip()
        except Exception as e:
            logger.warning("jarvis loop LLM call failed at step %d: %s", step, e)
            break

        # Record the planning LLM call into the turn trace. Silent on
        # failure — observability never breaks brain_loop.
        try:
            turn.llm_call(
                name=f"planner_iter_{step}",
                model=model,
                input=_planner_messages,
                output=text,
                metadata={"step": step, "max_iters": max_iters},
            )
        except Exception:
            pass

        # Recovery-pass terminal-state detection. The recovery seed
        # prompt forces the LoRA to emit either a concrete TOOL_CALL
        # (STATE_A) or the literal "NO_RECOVERY_FOUND: <reason>"
        # (STATE_B). Detect the latter BEFORE the generic parse so
        # we can add a synthetic transcript entry that the synthesis
        # step can recognize as a genuine dead end rather than as a
        # "just research" partial result.
        if recovery_seed is not None:
            m_norec = _re.search(
                r'NO_RECOVERY_FOUND:\s*(.+?)(?:\n|$)',
                text, _re.IGNORECASE,
            )
            if m_norec:
                reason = m_norec.group(1).strip()[:300]
                transcript.append((
                    "recovery_dead_end",
                    {"reason": reason},
                    f"NO_RECOVERY_FOUND: {reason}",
                    False,
                ))
                break

        call = _parse_tool_call(text)
        if call is None:
            # Recovery pass + plain DONE with no prior proposal =
            # incomplete recovery. Inject a corrective history entry
            # so the LoRA gets one more shot at producing a terminal
            # state. If it happens again in the next iter we'll just
            # break out.
            if recovery_seed is not None and _re.search(r'\bdone\b', text, _re.IGNORECASE):
                has_concrete = any(
                    ok is True and action != "web_search"
                    for (action, _p, _o, ok) in transcript
                )
                if not has_concrete:
                    history.append(
                        "INCOMPLETE: You wrote DONE without a STATE_A "
                        "TOOL_CALL or STATE_B NO_RECOVERY_FOUND. This is "
                        "NOT a valid terminal state for a recovery pass. "
                        "Either emit a concrete run_shell TOOL_CALL that "
                        "attempts the actual fix, or emit the literal "
                        "line 'NO_RECOVERY_FOUND: <reason>'. Try again."
                    )
                    continue
            # Non-recovery or recovery with a concrete action already:
            # DONE is acceptable.
            if _re.search(r'\bdone\b', text, _re.IGNORECASE):
                break
            history.append("PARSE_ERROR: could not extract a TOOL_CALL from your reply. Emit exactly one line in the form TOOL_CALL: {\"action\":\"<name>\",\"params\":{...}} or write DONE.")
            continue

        action = call.get("action")
        params = call.get("params", {}) or {}

        if not action or action not in allowed or action in FORBIDDEN_ACTION_TYPES:
            msg = f"REFUSED: {action!r} is not in the chat-loop allowlist."
            transcript.append((action or "?", params, msg, False))
            history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
            continue

        # Dedup: key on (action, primary-param). For run_shell the key
        # is the cmd; for write_any_file it's the path. If we've
        # already executed this exact call in this pass, short-circuit
        # instead of re-running. Tell the model so it advances or
        # wraps up.
        _dedup_key: tuple[str, str] = (action, "")
        if isinstance(params, dict):
            _dedup_key = (action, str(params.get("cmd") or params.get("path") or ""))
        if _dedup_key in _seen_keys and _dedup_key[1]:
            dup_msg = (
                f"ALREADY_RAN: you proposed {action!r} with the same "
                f"parameters earlier in this pass and it already "
                f"executed. The transcript above has the result. "
                f"Do NOT re-propose the same call — either advance "
                f"to a different tool, or emit DONE."
            )
            history.append(
                f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {dup_msg}"
            )
            logger.info(
                "brain_loop: dedup hit — skipping repeat %s call (key=%s)",
                action, _dedup_key[1][:60],
            )
            continue
        _seen_keys.add(_dedup_key)

        tier = ACTION_TIERS.get(action, 2)

        # Session 11z Part 2: route the two primitives through the
        # decision pipeline instead of calling _execute_action
        # directly. Lane 0 still runs inline; Lane 2/3 creates a
        # persistent approval card that the owner resolves async.
        pipeline_actions = {"run_shell", "write_any_file"}
        pipe = get_pipeline() if action in pipeline_actions else None

        if pipe is not None:
            # Fix: in recovery mode, user_text is "" (the recovery pass
            # is seeded by the recovery_seed dict, not a user message),
            # which would leave the card's reason as "chat: " with
            # nothing after. Use the recovery seed's original_intent
            # instead so the card records which goal it belongs to —
            # both for Fix 6's chain walk and for human-readable card
            # rendering.
            if recovery_seed is not None:
                _intent = (recovery_seed.get("original_intent") or "").strip()
                if _intent:
                    card_reason = f"recovery: {_intent[:140]}"
                else:
                    card_reason = f"recovery: pass {recovery_seed.get('recovery_depth', '?')}"
            else:
                card_reason = f"chat: {user_text[:140]}"

            try:
                presult = pipe.handle_action(
                    action=action,
                    params=params,
                    reason=card_reason,
                    user_id=user_id,
                    chat_id=str(chat_id),
                    channel="telegram_text",
                )
            except Exception as e:
                logger.warning("pipeline dispatch %s failed: %s", action, e)
                msg = f"ERROR: {e}"
                transcript.append((action, params, msg, False))
                history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
                continue

            from core.decision_pipeline import PipelineStatus as _PS

            if presult.status == _PS.EXECUTED:
                out = (presult.execution_output or "").strip()[:1500] or "(no output)"
                ok = bool(presult.execution_success)
                transcript.append((action, params, out if ok else (presult.execution_error or "?"), ok))
                history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {out}")
            elif presult.status in (_PS.PENDING_APPROVAL, _PS.PENDING_DIALOG):
                # A-core #4b: if this is a PENDING_DIALOG (Lane 3
                # self-mod), the pipeline also created a dialog
                # and returned its opening turn as dialog_opening.
                # Surface that to the owner as a separate Telegram
                # message via the thread-safe _send_card_message
                # helper (the Jarvis loop runs in an executor
                # thread, so async calls must go through
                # run_coroutine_threadsafe).
                if (
                    presult.status == _PS.PENDING_DIALOG
                    and getattr(presult, "dialog_opening", None)
                ):
                    try:
                        (send_intermediate and send_intermediate(presult.dialog_opening,  # type: ignore[arg-type]
                        ))
                    except Exception as e:
                        logger.warning(
                            "failed to send self-mod dialog opening: %s", e
                        )
                msg = (
                    "CARD_CREATED — NOT YET EXECUTED. A persistent approval card "
                    "was sent to the owner in Telegram. The action has NOT run; it is "
                    "waiting for his explicit go-ahead. In your reply you MUST "
                    "say you proposed the action and are waiting for approval. "
                    "Do NOT claim you checked, found, installed, or fixed anything."
                )
                # pending is a third state: not-ran-not-rejected. Use a
                # dedicated marker string (rendered by _format_transcript)
                # as "⏳" so rule #4 in the final prompt can reason off it.
                transcript.append((action, params, msg, "pending"))
                history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
                # Single-card-per-pass discipline. When the loop
                # produces a Lane 2 or Lane 3 card, that IS the
                # terminal state of this turn — don't let the model
                # propose another destructive action in the same
                # pass. Previously this break only fired in recovery
                # mode, which left the normal Jarvis path free to
                # propose N rm-rf variants in sequence (observed
                # 2026-04-20: 4 rm-rf cards created in 18 seconds
                # for a single "Delete /maez" turn, each superseding
                # the previous, creating a cards-in-repetition feel
                # on Telegram).
                #
                # Documented in docs/followups/recovery_multi_card_orphans.md
                # as the Option 1 fix: the FIRST Lane 2/3 card is
                # the terminal proposal. A second one is noise.
                logger.info(
                    "jarvis: first Lane 2/3 card created, breaking loop "
                    "(single-card-per-pass discipline, recovery=%s)",
                    recovery_seed is not None,
                )
                break
            else:  # REFUSED_COVENANT / REFUSED_AUDIT / ERROR
                msg = f"REFUSED: {presult.message}"
                transcript.append((action, params, msg, False))
                history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
            continue

        # Legacy path for non-primitive actions (read_file etc.).
        # Same reason-propagation fix as the pipeline path above: in
        # recovery mode the user_text is empty, so fall back to the
        # recovery seed's original_intent.
        if recovery_seed is not None:
            _intent = (recovery_seed.get("original_intent") or "").strip()
            if _intent:
                legacy_reason = f"recovery: {_intent[:140]}"
            else:
                legacy_reason = f"recovery: pass {recovery_seed.get('recovery_depth', '?')}"
        else:
            legacy_reason = f"chat: {user_text[:140]}"
        try:
            result = action_engine._execute_action(
                action, params,
                legacy_reason,
                tier=tier,
            )
        except Exception as e:
            logger.warning("jarvis dispatch %s failed: %s", action, e)
            msg = f"ERROR: {e}"
            transcript.append((action, params, msg, False))
            history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
            # Record to consequence_memory so future Maez can retrieve
            # past failures for similar actions. Fail-safe — the log
            # line above is still the primary signal.
            _record_tool_failure(action, params, str(e), surface="brain_loop/dispatch")
            continue

        if result.success:
            out = (result.output or "").strip()[:1500] or "(no output)"
            transcript.append((action, params, out, True))
            history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {out}")
        else:
            msg = f"ERROR: {result.error}"
            transcript.append((action, params, msg, False))
            history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
            # Record failures from the action engine layer too —
            # these are the "ran but returned non-zero" class.
            _record_tool_failure(
                action, params, result.error or "(no error text)",
                surface="brain_loop/action",
            )

    if not transcript:
        return ""

    lines = [
        "[JARVIS TRANSCRIPT — the AUTHORITATIVE record of what you did",
        " this turn on the owner's machine. Tell the owner naturally what you did",
        " and what you found. Don't list raw output; synthesize.",
        "",
        " Marker legend:",
        "   ✓  the tool ran, the → output is real",
        "   ✗  the tool call was REJECTED, nothing ran",
        "   ⏳ the action was PROPOSED as a card, NOT YET EXECUTED —",
        "       the owner must approve in Telegram before it runs",
        "",
        " HARD RULES for your reply:",
        " 1. Only mention tools, commands, packages, or files that appear",
        "    in this transcript. Do not rename or substitute what you ran.",
        " 2. If memory recall (earlier in the prompt) mentions something you",
        "    did NOT run this turn, do not attribute it to the current turn.",
        "    You may say 'last time we looked at X' but not 'I just checked X'.",
        " 3. If the transcript is short or the result is empty, say that",
        "    plainly. 'I ran X and got no output' is better than inventing",
        "    a richer narrative.",
        " 4. If a tool call was rejected (✗), describe the rejection honestly",
        "    — don't pretend the thing ran.",
        " 5. If a line has ⏳ (card pending approval), the action has NOT run.",
        "    Tell the owner you proposed it and are waiting for his go-ahead.",
        "    Do NOT claim you checked, found, installed, or fixed anything",
        "    on a ⏳ line — only on ✓ lines.",
        "]"
    ]
    for action, params, out, ok in transcript:
        if ok == "pending":
            mark = "⏳"
        elif ok:
            mark = "✓"
        else:
            mark = "✗"
        lines.append(f"\n{mark} {action}({_json.dumps(params, default=str)[:200]})")
        lines.append(f"  → {out[:800]}")
    return "\n".join(lines)

