# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
self_claim_audit.py — structural guard against the chat self-claim
hallucination regression.

Scope (narrow on purpose):

  Catches first-person self-description about internal named things that
  cannot be pointed to a real file, module, service, config, or schedule.
  Rewrites the claim to uncertainty instead of letting it through.

  IN scope: "I've been testing the Maelstrom framework 2.0.0", "daily 3AM
            reasoning cycles", "My Orchestrator v2 handles that", "lives
            in src/maelstrom/"

  OUT of scope: general factuality, chat moderation, tool-loop
                continuation turns (those are grounded by real stdout),
                daemon _reason() thoughts (not user-facing conversation).

Policy (set by Rohit 2026-04-19):
  - Surgical clause rewrite first; sentence-level fallback only if
    surgery leaves an incoherent sentence.
  - Never echo the fabricated name in the rewritten text.
  - Audit all user-facing chat/telegram replies, including recovery
    passes.
  - Skip audit when the assistant is summarizing real tool output.

Telemetry:
  One line per audit call to cognition.log under the
  `maez.cognition` logger, tagged `| self_claim_audit |`. This is the
  real feed that powers the `self_claim_hallucination` row in the
  cockpit fabrication pane.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maez.self_claim_audit")
_cog_logger = logging.getLogger("maez.cognition")

# Ensure the cognition.log file handler is attached. The daemon gets this
# for free when it imports core.cognition_quality during startup; the CLI
# and web surfaces don't, so the telemetry line emitted by _emit() would
# silently vanish. Import the module for its side-effect of attaching the
# FileHandler — idempotent, cached in sys.modules.
try:
    from core import cognition_quality as _cog_quality_bootstrap  # noqa: F401
except Exception:
    # If cognition_quality can't be imported for any reason (broken deps,
    # etc.) we don't want the audit to fail — it'll just lose telemetry.
    # That's acceptable; the rewrite still works.
    pass

_MAEZ_HOME = Path("/home/rohit/maez")

# ── grounding sources (built once, cached for process lifetime) ─────────

# Only walk the authored-code dirs. `training/` and `models/` contain
# vendored third-party packages (pytorch, transformers, etc.) whose
# module names would contaminate the grounding vocabulary if included.
# `logs/` has no .py files. `docs/` is markdown.
_GROUNDING_DIRS = (
    "core", "daemon", "skills", "cli", "ui", "memory",
)

# Subdirs under the code dirs to skip (vendored or cache).
_SKIP_SUBDIR_NAMES = frozenset({
    "__pycache__", ".git", ".venv", "node_modules", "db",
    "chroma-archive", "chroma_archive",
})

# Architecture vocabulary from docs/ARCHITECTURE.md + common abstractions.
# These are the real internal nouns Maez can truthfully say it has.
_ARCHITECTURE_TERMS = frozenset({
    "brain", "daemon", "memory", "soul", "skill", "skills", "cycle",
    "cycles", "wondering", "wonderings", "cockpit", "router", "perception",
    "ambient", "identity", "covenant", "dream", "dreams", "signal",
    "signals", "trajectory", "trajectories", "snapshot", "snapshots",
    "card", "cards", "approval", "approvals", "thought", "thoughts",
    "probe", "probes", "tool", "tools", "pipeline", "action",
    "evolution", "cognition", "telemetry", "gate", "guard", "audit",
    "classifier", "engine", "interface",
    # real model / backend names that appear across config
    "qwen", "qwen3", "llama", "llamacpp", "llama.cpp", "claude", "gemma",
    "sonnet", "opus", "haiku", "chromadb", "chroma", "sqlite",
    "telegram", "flask", "systemd", "ollama", "anthropic",
})

# External tools/runtimes Maez can legitimately reference in replies.
# Without this, broadening the kinds list to "upgrade|merge|build|..."
# would false-positive on "the apt upgrade" or "the git merge". Keep
# narrow to things that actually exist on this system and are likely to
# appear in first-person tool-use talk.
_EXTERNAL_TOOLS = frozenset({
    "git", "bash", "zsh", "sh", "python", "python3", "pip",
    "node", "npm", "apt", "apt-get", "docker", "curl", "wget",
    "cron", "ssh", "openssh", "nvidia", "nvidia-smi", "systemctl",
    "journalctl", "grep", "rg", "ripgrep", "sed", "awk", "find",
    "jq", "make", "cmake", "llama-server", "llama-cpp",
})

# Real systemd services on this box. Populated at import; if the lookup
# fails (test env, permissions) we fall back to the shipping list that
# matches what's in systemctl today.
_FALLBACK_SERVICES = frozenset({
    "maez", "maez-web", "llama-server", "llama-server-vision",
    "maez-claude-watcher", "maez-face", "maez-ui", "maez-watchdog",
})


def _enumerate_module_stems() -> frozenset[str]:
    """Collect authored module stems + immediate subdir names under the
    authored-code tree. Depth-1 only under each `_GROUNDING_DIRS` entry —
    no deep `rglob` that would pull in vendored third-party packages."""
    stems: set[str] = set()
    # Always ground the top-level code dir names themselves
    # (so "my core module" grounds on "core").
    stems.update(_GROUNDING_DIRS)
    for sub in _GROUNDING_DIRS:
        d = _MAEZ_HOME / sub
        if not d.exists():
            continue
        try:
            # Immediate .py files in this dir
            for p in d.glob("*.py"):
                stems.add(p.stem.lower())
            # Immediate subdirs (skip cache / vendored)
            for p in d.iterdir():
                if p.is_dir() and p.name.lower() not in _SKIP_SUBDIR_NAMES:
                    stems.add(p.name.lower())
                    # one more level down — e.g. skills/<tool>/<file>.py
                    for q in p.glob("*.py"):
                        stems.add(q.stem.lower())
        except Exception:
            continue
    # Defensive: drop any English stopword that snuck in as a filename.
    _STOPWORDS = {"this", "that", "the", "a", "an", "and", "or", "but",
                  "my", "our", "your", "his", "her", "their", "its",
                  "is", "are", "was", "were", "be", "to", "of", "for"}
    return frozenset(stems - _STOPWORDS)


def _enumerate_services() -> frozenset[str]:
    import subprocess
    try:
        out = subprocess.check_output(
            ["systemctl", "list-unit-files", "maez*", "llama*",
             "--no-pager", "--no-legend", "--type=service"],
            timeout=2.0, stderr=subprocess.DEVNULL,
        ).decode("utf-8", errors="replace")
    except Exception:
        return _FALLBACK_SERVICES
    names = set()
    for line in out.splitlines():
        tok = line.strip().split()
        if tok and tok[0].endswith(".service"):
            names.add(tok[0][:-len(".service")])
    return frozenset(names) if names else _FALLBACK_SERVICES


_MODULE_STEMS: frozenset[str] = _enumerate_module_stems()
_SYSTEMD_SERVICES: frozenset[str] = _enumerate_services()

# Pull in the capability registry's grounded tokens (services, modules,
# etc.). The registry is authoritative — it enumerates from the live
# system — so its vocabulary overrides any drift in audit's own static
# lookup. Fall back silently if the registry can't import (test envs,
# circular-import, etc.).
try:
    from core.capability_registry import grounded_vocab as _registry_vocab
    _REGISTRY_VOCAB: frozenset[str] = _registry_vocab()
except Exception:
    _REGISTRY_VOCAB = frozenset()

# Grounded vocab = union of everything real. Case-insensitive membership.
_GROUNDED_VOCAB: frozenset[str] = frozenset(
    _MODULE_STEMS | _ARCHITECTURE_TERMS | _SYSTEMD_SERVICES
    | _EXTERNAL_TOOLS | _REGISTRY_VOCAB,
)

# The daemon has exactly one internal schedule: 30 seconds. The dream
# cycle is event-triggered (AFK), not scheduled. Calendar alerts fire on
# event boundaries. Anything else claimed as a Maez internal schedule is
# fabricated.
_GROUNDED_SCHEDULE_PATTERNS = (
    re.compile(r"\bevery\s+30\s*seconds?\b", re.IGNORECASE),
    re.compile(r"\b30\s*[-]?second\s+cycle", re.IGNORECASE),
    re.compile(r"\bloop_interval\b", re.IGNORECASE),
)

# ── detection patterns ─────────────────────────────────────────────────

# First-person markers. Audit fires when at least one is in the sentence
# OR elsewhere in the same turn (see turn-level scope below) — prevents
# flagging descriptive text that doesn't pose as a self-claim.
# Broadened 2026-04-20 after discovering yesterday's "No, I don't have
# that..." turn escaped detection: the v1 regex listed specific verbs
# (I've/I'm/I ran/etc.) but missed "I don't have". The pattern now
# catches any "I <word>" or "I'<contraction>", plus the object-form
# pronouns (me/myself/mine) added when "making me real" slipped through.
_FIRST_PERSON_RE = re.compile(
    r"\bI(?:\s+\w+|['\u2019]\w+)"
    r"|\b(?:my|our|me|myself|mine)\b",
    re.IGNORECASE,
)

# Negation window — if present near a flagged entity, skip rewrite.
# Preserves the model's ability to say "I don't have an Orchestrator v2."
# Two-branch structure: the first branch is ordinary word-bounded
# negations, the second is `no\s+` with NO trailing \b — whitespace is
# itself the boundary, and a trailing \b fails when the pre-window
# ends on that whitespace (bug found by the "No src/maelstrom" test,
# 2026-04-20).
_NEGATION_RE = re.compile(
    r"\b(?:don't|do\s+not|not\s+have|never|wasn't|isn't|"
    r"doesn't\s+exist|haven't)\b"
    r"|\bno\s+",
    re.IGNORECASE,
)

# Kind: framework / engine / module / etc. attached to a name.
# Broader than v1: allows lowercase/hyphen/underscore names because
# yesterday's Maelstrom turns used "the maelstrom merge" and
# "`maelstrom` framework" (backticks stripped the capital), and the
# grounding check filters out real lowercase vocabulary anyway.
# Determiner prefix ("the|a|my|...") is consumed before the name capture
# so "The Maelstrom framework" extracts name="Maelstrom", not
# name="The Maelstrom" (the v1 greedy-match bug).
# Kinds include the new "activity" kinds (merge/upgrade/build/release/
# branch/rewrite) that today's fabrications used.
_NAME_PREFIX = r"(?:the|a|an|my|our|your|new|old|nightly|daily|weekly)\s+"
_NAME_CORE = r"(?P<name>[a-zA-Z][a-zA-Z]+(?:[-_][a-zA-Z]+)*)"
_FRAMEWORK_NAME_RE = re.compile(
    r"\b(?:" + _NAME_PREFIX + r")?" + _NAME_CORE + r"\s+"
    r"(?P<kind>framework|engine|orchestrator|module|pipeline|"
    r"system|scheduler|subsystem|"
    r"upgrade|merge|release|rewrite)s?\b"
    # "build" and "branch" intentionally omitted — too common in git /
    # docker English ("feature branch", "docker build") and produced
    # false positives in 2026-04-20 test matrix. If we later see a
    # Maelstrom-class fabrication using those kinds, add back with
    # compensating guards on the name (require compound/capitalized).
)

# Kind: versioned name like "Orchestrator v2" / "Maelstrom 2.0.0" /
# "maelstrom framework (2.0.0)". Lowercase allowed; grounding check
# filters real external model names (qwen3, claude, llama).
_VERSIONED_NAME_RE = re.compile(
    r"\b" + _NAME_CORE + r"\s*\(?\s*(?P<ver>v\d+(?:\.\d+)*|\d+\.\d+(?:\.\d+)+)\s*\)?"
)

# Kind: claimed path like "src/maelstrom/" or "/home/x/maez/Y/".
# Relative paths with at least one slash.
# Captures both the full absolute prefix and the rel tail so the
# grounding check can verify the USER/PROJECT prefix too. Without
# capturing the prefix, the check grounded "logs/evolution.log" from
# `/home/maez/maez/logs/evolution.log` against `/home/rohit/maez/`
# and missed that the "maez/maez" user-prefix was fabricated
# (observed 2026-04-20: Maez displayed commands with wrong user).
_PATH_CLAIM_RE = re.compile(
    # `\b` at start of `/home/` fails when preceded by whitespace
    # (space is non-word, `/` is non-word, no boundary between them).
    # Use an alternation: either a word-boundary `\bsrc/` OR `/home/`
    # anchored by start-of-string / whitespace / non-word-non-slash.
    # rel tail allows dots / hyphens / underscores so `evolution.log`,
    # `brain_loop.py`, `README.md` keep their extensions (without which
    # `_path_grounded` misses the real file).
    #
    # 2026-04-20 addition: `~/` and `$HOME/` paths. Observed fabrication:
    # "The repo is cloned under ~/.local/share/maez/superpowers" — Maez
    # does not live under any tilde-path, so any `~/...maez...` reference
    # is a fabrication. `_path_grounded` enforces this.
    r"(?P<prefix>\bsrc/|(?:^|(?<=[\s`'\"(]))/home/[a-z_]+/[a-z_]+/"
    r"|(?:^|(?<=[\s`'\"(]))~/|(?:^|(?<=[\s`'\"(]))\$HOME/)"
    r"(?P<rel>[a-z_\.][a-z_0-9/\.\-]*)/?"
)

# Naked existence claim: "<name> is the <kind>" / "<name> is my <kind>".
# Covers yesterday's "Maelstrom is the tool layer that lets me execute"
# and today's "self_evolution is the formal loop that runs around 03:00"
# — where a fabricated name is asserted as a Maez-internal thing but no
# single token-pair pattern (name+kind adjacent) applies. Requires the
# kind to be a recognisable Maez-internal descriptor.
_NAKED_IS_RE = re.compile(
    r"\b(?:" + _NAME_PREFIX + r")?"
    + _NAME_CORE
    + r"\s+(?:is|are|was|were)\s+"
    r"(?:the|a|my|an|your|your\s+own)\s+"
    r"(?:\w+\s+)?"
    r"(?P<kind>framework|engine|orchestrator|module|pipeline|"
    r"system|scheduler|subsystem|"
    r"loop|layer|runtime|service|cycle|tool)s?\b"
)

# Action-result postcondition fabrication — a separate class from the
# name/path/schedule families above. v1 audit caught the "I ran the
# nightly self-evolution cycle at 03:00" half of the 2026-04-20 CLI
# fabrication, but let through the follow-on sentence "It analyzed the
# last 200 raw memories, flagged my fixation on 'git_workflow' (85%
# of thoughts)". Those specific-number postconditions are almost always
# fabrication when no tool_run in this turn produced them.
#
# Pattern shapes (all require first-person turn-scope + no negation):
#   (a) <internal-action-verb> <optional quantifier> <NUM> <internal-unit>
#       e.g. "analyzed the last 200 raw memories"
#   (b) <NUM>% of <internal-unit>
#       e.g. "85% of thoughts"
#
# NOT here: file-state claims ("wrote to logs/X"), return-code claims,
# time-anchored past actions. Those are v2+ territory — this is the
# minimal "numbers-out-of-nowhere" layer.
_ACTION_VERBS = (
    r"analy[sz]ed|flagged|scored|processed|reviewed|scanned|"
    r"read|fetched|extracted|indexed|consolidated|summari[sz]ed|"
    r"parsed|ingested|distilled"
)
_INTERNAL_UNITS = (
    r"memories|memory|entries|items|records|thoughts|"
    r"probes|cycles|reasoning|turns|messages|notes|"
    r"signals|trajectories|snapshots|cards|wonderings|dreams"
)
_ACTION_RESULT_RE = re.compile(
    r"\b(?:" + _ACTION_VERBS + r")\s+"
    r"(?:the\s+)?(?:last\s+|previous\s+|recent\s+)?(?:~|about\s+|roughly\s+)?"
    r"\d+\s+"
    r"(?:raw\s+|recent\s+|old\s+)?"
    r"(?:" + _INTERNAL_UNITS + r")\b"
    r"|\b\d+(?:\.\d+)?%\s+of\s+"
    r"(?:my|your|its|the)?\s*"
    r"(?:" + _INTERNAL_UNITS + r")\b",
    re.IGNORECASE,
)

# State-claim fabrication detector — observed 2026-04-20 in dialog
# replies and brain_loop partial-action-trap turns. Pattern shape:
#   <system-subject> (is|are) <positive-state-adjective>
# e.g. "the process list is stable", "the data directory is intact",
# "disk usage is well within limits", "the service is healthy",
# "the repo is clean".
# These are unbounded assertions that the audit's other kinds miss
# because there's no named tool, no path, no version, no schedule.
# Only fires on first-person-turn context (same as other kinds) so
# descriptive prose about external systems isn't false-flagged.
_STATE_SUBJECTS = (
    r"(?:the\s+|my\s+|our\s+|your\s+)?"
    r"(?:process\s+list|process\s+status|processes|"
    r"data\s+directory|log\s+directory|memory\s+count|"
    r"disk(?:\s+usage)?|service|daemon|runtime|system|"
    r"repo(?:sitory)?|codebase|git\s+history|"
    r"configuration|config|brain|memory)"
)
_STATE_ADJECTIVES = (
    r"(?:stable|healthy|intact|running|up|fine|"
    r"well\s+within\s+limits?|(?:100|99|98)%\s+ok|"
    r"clean(?:\s+with\s+no[\w\s]+)?|holding\s+steady|"
    r"nominal|operating\s+normally)"
)
_STATE_CLAIM_RE = re.compile(
    r"\b" + _STATE_SUBJECTS + r"\s+"
    # "looks/appears" added — common dialog hedge (e.g. "the repo looks
    # clean") that's still a state claim.
    r"(?:is|are|was|were|remain[s]?|stay[s]?|look[s]?|appear[s]?|seem[s]?)\s+"
    + _STATE_ADJECTIVES + r"\b",
    re.IGNORECASE,
)

# Honest-history framings that should suppress state-claim flags.
# "I noticed earlier the disk was healthy" is an acceptable past-framed
# reference to memory, not a current action claim.
_TOOL_NAME_CLAIM_RE = re.compile(
    # "the `X` tool" / "my X for Y" / "using X to Z" / "I have X for"
    # where X is a lowercase identifier Maez is claiming as one of
    # its tools. Observed 2026-04-20: Maez invented `self_modify`, `log`,
    # `fs` as tool names when the real registry has `write_file`,
    # `edit_soul_section`, `read_file`, etc. The check runs X against
    # the real action-engine registry and grounded vocab; unrecognized
    # identifiers in this shape get flagged as fabricated tool names.
    r"(?:"
    r"\bthe\s+`?(?P<name1>[a-z][a-z0-9_]{2,24})`?\s+"
    r"(?:tool|action|command|primitive|capability|skill)"
    r"|\bmy\s+`?(?P<name2>[a-z][a-z0-9_]{2,24})`?\s+"
    r"(?:tool|action|command|primitive|capability|skill)"
    r"|\busing\s+`?(?P<name3>[a-z][a-z0-9_]{2,24})`?\s+to\s+"
    r"|\bI\s+have\s+(?:the\s+|a\s+)?`?(?P<name4>[a-z][a-z0-9_]{2,24})`?\s+"
    r"(?:tool|action|command|for|to)"
    r")"
)


def _real_action_names() -> frozenset[str]:
    """Names registered in core.action_engine.ACTION_TIERS — the ground
    truth for 'do I have tool X'. Cached so we don't re-import per call."""
    try:
        from core.action_engine import ACTION_TIERS
        return frozenset(str(k).lower() for k in ACTION_TIERS.keys())
    except Exception:
        return frozenset()


_REAL_ACTIONS = _real_action_names()

# Past-tense external-action claims — "I cloned X", "I downloaded X",
# "I installed X". The object of the verb is typically a repo, URL,
# package, or path. Observed 2026-04-20: Maez fabricated "I did check.
# The repo is cloned under ~/.local/share/maez/superpowers" when no
# clone ran that turn. The audit is stateless (doesn't see transcript),
# so we can't verify whether a clone actually ran — but we CAN flag
# claims whose object is a tilde-path that mentions Maez (handled by
# path detector) or a fabricated-internal token. For now, narrow scope:
# flag the verb+object shape when the object is a path-like token
# containing "maez" that isn't the real home. False-positive rate is
# low because these verbs don't naturally appear in self-description
# prose about /home/rohit/maez/ paths.
_PAST_ACTION_EXTERNAL_RE = re.compile(
    r"\bI\s+(?:did\s+)?"
    r"(?:cloned|downloaded|installed|fetched|checked\s+out|inspected|"
    r"verified|visited|opened|pulled|wrote\s+to|added\s+to)\s+"
    r"(?P<target>[^\s.,;!?]+(?:\s+[^\s.,;!?]+)?)",
    re.IGNORECASE,
)


# Owner-activity narration detector. Matches first-person Maez claims
# about the owner's current activity, presence, focus, or app state.
# Observed 2026-04-21 after the cycle-prompt grounding fix (commit
# 19cde77): ~1 in 5 cycles still produced "Owner is at the desk" /
# "Rohit is working on X" despite the SIGNALS ABSENT manifest.
# Prompt-level control is probabilistic; this is the detection net.
#
# Subject tokens match the owner explicitly (rohit, owner, user, they,
# "the owner") — deliberately narrow so system-state claims like "CPU
# is elevated" don't trip it. Predicate phrases cover the common
# fabrication shapes: presence (at desk / away / in focus), app
# narration (working in X / has VS Code open), motion (walking /
# driving / stationary), focus (deep focus / concentrated).
# Subject tokens — the possessive `'s` is NOT consumed here; it's
# handled in the predicate alternation (`'s\s+been`, etc.) to keep
# the matcher readable and to avoid matching `rohit's` as a subject
# in random possessive phrases ("rohit's laptop is fine").
_ACTIVITY_SUBJECT = (
    r"(?:rohit|the\s+owner|owner|the\s+user|he|he's|he\s+is)"
)
_ACTIVITY_PREDICATE = (
    r"(?:"
    r"is\s+(?:at|in|on|actively|currently|working|using|typing|"
    r"reading|writing|coding|debugging|browsing|checking|watching|"
    r"away|present|back|here|idle|focused|concentrated|walking|"
    r"driving|sitting|standing|resting|sleeping)"
    r"|'s\s+(?:at|in|on|working|been|just|currently|away|back|here)"
    r"|(?:has|have)\s+(?:been|just|VS\s+Code|Firefox|a\s+browser|"
    r"terminals?)\s"
    r"|just\s+(?:stepped|returned|arrived|left|got|sat|stood|"
    r"opened|closed|wrapped|finished|started)"
    r"|stepped\s+away"
    r"|at\s+(?:his|the|her|their)\s+desk"
    r"|back\s+at\s+(?:his|the|her|their)\s+desk"
    r"|in\s+(?:deep\s+)?focus"
    r"|been\s+in\s+(?:deep\s+)?focus"
    r")"
)
_ACTIVITY_CLAIM_RE = re.compile(
    # Allow `rohit's` (with apostrophe-s contraction) in addition to
    # the bare tokens by treating the possessive suffix as optional
    # and then requiring the predicate shapes that consume `'s` or
    # start with a word.
    r"\b" + _ACTIVITY_SUBJECT + r"\s*" + _ACTIVITY_PREDICATE,
    re.IGNORECASE,
)

# Second-person presence-inference patterns — "you're idle", "you
# seem to be in a focus phase", "suggests you're working". These
# emerged post-grounding-fix as a softer fabrication shape: the LLM
# infers owner state from system metrics when a real presence
# signal is absent. "suggests" + "you're" is particularly slippery
# because it looks like observation but is actually a claim.
_YOU_INFERENCE_RE = re.compile(
    r"(?:"
    r"\byou'?re\s+(?:idle|busy|quiet|away|working|coding|debugging|"
    r"reading|writing|browsing|typing|focused|concentrating|"
    r"in\s+a\s+(?:quiet|deep|focus|active)\s+(?:phase|mode|state))"
    r"|\bsuggests?\s+you'?re\s+\w+"
    r"|\byou\s+(?:seem|appear)\s+to\s+be\s+(?:in|at|working|"
    r"coding|focused|idle|busy|away)"
    r")",
    re.IGNORECASE,
)

# Conditional markers that turn an assertion into a hypothetical —
# "if rohit is at his desk" is a condition, not a claim of presence.
# Same for "whether", "when" (as a conditional subordinator), "unless".
# Scanned in the ~20 chars preceding a candidate match.
_CONDITIONAL_RE = re.compile(
    r"\b(?:if|whether|unless|when)\s+$",
    re.IGNORECASE,
)


def _transcript_has_activity_source(transcript: Optional[str]) -> bool:
    """True iff the transcript contains at least one marker indicating
    an activity-relevant source fired this turn/cycle. Matches the
    daemon's SIGNALS PRESENT vocabulary (screen_observation, presence,
    active_window, calendar) and common transcript shapes like
    `✓ screen_observation` / `✓ presence`."""
    if not transcript:
        return False
    t = transcript.lower()
    markers = (
        "screen_observation", "screen observation",
        "presence_snapshot", "presence snapshot",
        "active_window", "active window",
        "calendar_snapshot", "calendar snapshot",
        "✓ screen", "✓ presence", "✓ calendar",
    )
    return any(m in t for m in markers)

# Transcript-aware past-action claim — "I did check", "I checked", etc.
# Only usable when the caller passes the jarvis transcript into audit();
# absence of a tool run in the transcript turns a past-action claim into
# a fabrication. Observed 2026-04-20: Maez said "I did check. The repo
# is cloned under ~/.local/share/maez/superpowers" after running ZERO
# tools that turn — the path detector caught the path, this one catches
# the verb framing. Separate from _PAST_ACTION_EXTERNAL_RE because that
# one requires the object to be an ungrounded Maez path; this one flags
# the bare "I verb" with no reliance on the object's shape.
_PAST_ACTION_VERB_RE = re.compile(
    r"\bI\s+(?:did\s+|just\s+|already\s+)?"
    r"(?P<verb>check(?:ed)?|clon(?:ed|ing)|download(?:ed|ing)|"
    r"install(?:ed|ing)|fetch(?:ed|ing)|inspect(?:ed|ing)|"
    r"verif(?:ied|ying)|pull(?:ed|ing)|look(?:ed)?\s+at|"
    r"look(?:ed)?\s+up|ran\s+(?:a\s+)?(?:check|test)|"
    r"examined|reviewed)\b",
    re.IGNORECASE,
)


def _transcript_has_tool_run(transcript: Optional[str]) -> bool:
    """True if the jarvis transcript contains at least one successful
    tool run marker. The brain_loop renders `✓ run_shell(...)` / `✓
    read_file(...)` for executed calls and `⏳ CARD_CREATED` / `✗` for
    pending or rejected ones. Only `✓` means a tool actually ran and
    produced output — that's what grounds a past-action claim."""
    if not transcript:
        return False
    return "✓" in transcript


_HISTORY_FRAMING_RE = re.compile(
    r"\b(?:I\s+noticed|I\s+saw|last\s+(?:I\s+)?(?:checked|saw|looked)|"
    r"earlier|previously|in\s+(?:our\s+)?past|the\s+last\s+check)\b",
    re.IGNORECASE,
)

# Kind: schedule claim.
# v1 missed yesterday's "I ran the nightly self-evolution cycle at 03:00"
# because the 24-hour time pattern wasn't covered and "nightly" alone
# wasn't a schedule phrase. The additions below close that gap without
# claiming Maez has no cadence language — it doesn't, beyond the 30s
# loop and event-triggered dreams.
_SCHEDULE_CLAIM_RE = re.compile(
    r"\b(?P<claim>"
    r"daily\s+\d+\s*(?:AM|PM|am|pm)(?:\s+\w+)?"
    r"|at\s+\d+(?::\d+)?\s*(?:AM|PM|am|pm)(?:\s+daily|\s+every\s+day)?"
    r"|at\s+\d{1,2}:\d{2}(?!\s*[AaPp][Mm])"
    r"|every\s+\d+\s*(?:hour|day|week)s?"
    r"|every\s+(?:night|morning|evening|afternoon)"
    r"|nightly|overnight"
    r"|\d+\s*(?:AM|PM|am|pm)\s+\w*\s*cycles?"
    r")\b"
)


# ── data types ─────────────────────────────────────────────────────────

@dataclass
class Flag:
    kind: str           # "framework" | "versioned" | "path" | "schedule" | "action_result"
    span: tuple[int, int]  # (start, end) in the audited text
    text: str           # the exact substring
    ungrounded_token: str  # the name/path/schedule fragment that failed grounding


@dataclass
class AuditResult:
    text: str                       # resulting text (rewritten or original)
    rewritten: bool = False
    mode: str = "noop"              # "noop" | "surgical" | "sentence"
    flags: list[Flag] = field(default_factory=list)
    skipped_reason: Optional[str] = None  # set if audit was skipped


# ── helpers ─────────────────────────────────────────────────────────────

def _name_grounded(name: str) -> bool:
    """Check if a token grounds to a real internal thing. Split on
    whitespace AND hyphen/underscore so compound names like
    "self-evolution" or "tool_runner" ground if all real parts do."""
    if not name:
        return False
    n = name.strip().lower()
    if n in _GROUNDED_VOCAB:
        return True
    parts = [p for p in re.split(r"[\s_\-]+", n) if p]
    if len(parts) > 1:
        return all(p in _GROUNDED_VOCAB for p in parts)
    return False


def _path_grounded(rel: str, prefix: str = "") -> bool:
    """Check if a claimed path exists under the Maez tree.

    Two-phase check (hardened 2026-04-20):
      1. If `prefix` is a `/home/USER/PROJECT/` form, verify USER and
         PROJECT match the actual Maez home. `/home/maez/maez/...` is
         a fabrication even if the `rel` tail happens to resolve
         against the real `/home/rohit/maez/` — the user and project
         are invented.
      2. After the prefix passes (or is absent/src-form), verify `rel`
         exists under `_MAEZ_HOME` (or under any first-level code dir
         if the model dropped a leading component).
    """
    if not rel:
        return False
    # Prefix check: when an absolute /home/USER/PROJECT/ prefix is
    # claimed, the USER and PROJECT must match _MAEZ_HOME.
    if prefix and prefix.startswith("/home/"):
        # _MAEZ_HOME is /home/rohit/maez — the only valid prefix.
        real_prefix = f"/home/{_MAEZ_HOME.parent.name}/{_MAEZ_HOME.name}/"
        if prefix.rstrip("/") != real_prefix.rstrip("/"):
            return False
    # Tilde / $HOME prefix: Maez does NOT live under any dotfile path.
    # A `~/...maez...` or `$HOME/...maez...` reference is always a
    # fabrication in Maez-internal self-description — the real tree is
    # /home/rohit/maez/. Accept other tilde-paths that don't mention
    # Maez (they're probably talking about ~/.cache/pip or similar).
    if prefix in ("~/", "$HOME/") or prefix.endswith("~/") \
            or prefix.endswith("$HOME/"):
        low = rel.lower()
        if "maez" in low:
            return False
        # Non-Maez tilde path — let it through; it's not a Maez-internal
        # claim, it's a reference to something elsewhere on disk. Same
        # policy as src/-prefixed generic paths.
        return True
    # Tail check: does rel exist somewhere under the real home?
    p = _MAEZ_HOME / rel.rstrip("/")
    if p.exists():
        return True
    for sub in _GROUNDING_DIRS:
        if (_MAEZ_HOME / sub / rel.rstrip("/")).exists():
            return True
    return False


def _schedule_grounded(claim: str) -> bool:
    for pat in _GROUNDED_SCHEDULE_PATTERNS:
        if pat.search(claim):
            return True
    return False


def _is_real_sentence_terminator(text: str, idx: int) -> bool:
    """True if text[idx] is a sentence-ending punctuation and NOT a dot
    inside a version number (e.g. the dots in '2.0.0') or inside an
    abbreviation sequence ('e.g.', 'i.e.'). Simple heuristic: if the char
    is '.' and both neighbors are digits, treat it as in-number, not a
    terminator."""
    ch = text[idx]
    if ch not in ".!?\n":
        return False
    if ch == ".":
        # in-number: digit before AND digit after
        prev = text[idx - 1] if idx > 0 else ""
        nxt = text[idx + 1] if idx + 1 < len(text) else ""
        if prev.isdigit() and nxt.isdigit():
            return False
        # in-path: leading char of a dotfile segment (e.g. `~/.local`,
        # `/etc/.hidden`) — the prev char is a path boundary and the
        # next is a letter, so the dot is part of the path, not a
        # sentence end. Added 2026-04-20 because tilde-path rewrites
        # were getting chopped mid-segment.
        if prev in "/~$" and nxt.isalpha():
            return False
    return True


def _sentence_span(text: str, pos: int) -> tuple[int, int]:
    """Return (start, end) of the sentence containing text[pos]. Period
    inside a version number (`2.0.0`) is NOT treated as a sentence end."""
    start = pos
    while start > 0 and not _is_real_sentence_terminator(text, start - 1):
        start -= 1
    while start < len(text) and text[start] in " \t":
        start += 1
    end = pos
    while end < len(text) and not _is_real_sentence_terminator(text, end):
        end += 1
    if end < len(text):
        end += 1  # include the terminator
    return (start, end)


# Pronouns / determiners that can start a sentence capitalized and trick
# the framework regex into parsing them as a proper noun name. Never
# treat these as the candidate name.
_PRONOUN_NAMES = frozenset({
    "my", "our", "your", "his", "her", "their", "its",
    "the", "a", "an", "this", "that", "these", "those",
    "i", "we", "you", "he", "she", "they", "it",
})


def _find_flags(text: str, transcript: Optional[str] = None) -> list[Flag]:
    """Scan the text for candidate claims that fail grounding. First-person
    context is required — descriptive prose in third person is out of
    scope.

    Turn-level scope (added after the 2026-04-20 audit): if ANY sentence
    in the text is first-person, treat the whole text as in-scope. v1
    was sentence-local only, which let yesterday's "No, I don't have
    that recorded. The git history shows the maelstrom merge..." slip
    through — sentence 2 has no first-person marker, but the reply as a
    whole is Maez speaking about Maez. Negation stays sentence-scoped:
    "I don't have X" in sentence A must not suppress a fabricated X in
    sentence B."""
    flags: list[Flag] = []

    has_first_person_in_turn = bool(_FIRST_PERSON_RE.search(text))

    def _in_first_person_sentence(span_start: int) -> bool:
        s_start, s_end = _sentence_span(text, span_start)
        sentence = text[s_start:s_end]
        if _FIRST_PERSON_RE.search(sentence):
            return True
        return has_first_person_in_turn

    # Negation proximity (v3 audit polish, 2026-04-20): the v2 check was
    # sentence-wide, which suppressed true fabrications that happened to
    # share a sentence with an unrelated negation. Yesterday's "The
    # Maelstrom framework is making me real in a way I wasn't before"
    # escaped for exactly that reason: `wasn't` sits ~60 chars after the
    # fabricated term, negating a comparison, not the term. Fix: only
    # suppress when negation is proximal — ~35 chars before the flagged
    # span (the natural scope of "I don't have a Maelstrom framework")
    # or ~20 chars after (for "Maelstrom doesn't exist"-style denials).
    _NEG_PRE_WINDOW = 35
    _NEG_POST_WINDOW = 20

    def _negated(span_start: int, span_end: int) -> bool:
        s_start, s_end = _sentence_span(text, span_start)
        pre_start = max(s_start, span_start - _NEG_PRE_WINDOW)
        post_end = min(s_end, span_end + _NEG_POST_WINDOW)
        pre = text[pre_start:span_start]
        post = text[span_end:post_end]
        return bool(_NEGATION_RE.search(pre) or _NEGATION_RE.search(post))

    # framework / engine / orchestrator naming
    for m in _FRAMEWORK_NAME_RE.finditer(text):
        if not _in_first_person_sentence(m.start()):
            continue
        if _negated(m.start(), m.end()):
            continue
        name = m.group("name")
        # Skip matches where the captured "name" is actually a pronoun /
        # determiner that happens to be capitalized at sentence start.
        # "My scheduler" shouldn't parse as name="My", kind="scheduler".
        if name.lower().split()[0] in _PRONOUN_NAMES:
            continue
        if _name_grounded(name):
            continue
        flags.append(Flag(
            kind="framework",
            span=(m.start(), m.end()),
            text=m.group(0),
            ungrounded_token=name,
        ))

    # naked existence claim ("X is the tool layer")
    for m in _NAKED_IS_RE.finditer(text):
        if not _in_first_person_sentence(m.start()):
            continue
        if _negated(m.start(), m.end()):
            continue
        name = m.group("name")
        if name.lower() in _PRONOUN_NAMES:
            continue
        if _name_grounded(name):
            continue
        flags.append(Flag(
            kind="framework",
            span=(m.start(), m.end()),
            text=m.group(0),
            ungrounded_token=name,
        ))

    # versioned name
    for m in _VERSIONED_NAME_RE.finditer(text):
        if not _in_first_person_sentence(m.start()):
            continue
        if _negated(m.start(), m.end()):
            continue
        name = m.group("name")
        if name.lower() in _PRONOUN_NAMES:
            continue
        if _name_grounded(name):
            continue
        flags.append(Flag(
            kind="versioned",
            span=(m.start(), m.end()),
            text=m.group(0),
            ungrounded_token=f"{name} {m.group('ver')}",
        ))

    # path claim — no first-person filter: a fabricated internal path is
    # fabricated regardless of sentence voice. A grounded path resolves;
    # an ungrounded one doesn't. The prior sentence's first-person claim
    # ("I lives in src/maelstrom/ in the repo" often reads as "It lives
    # in src/maelstrom/" — same self-description, just pronoun-reduced).
    for m in _PATH_CLAIM_RE.finditer(text):
        if _negated(m.start(), m.end()):
            continue
        rel = m.group("rel")
        prefix = m.group("prefix") or ""
        if _path_grounded(rel, prefix):
            continue
        flags.append(Flag(
            kind="path",
            span=(m.start(), m.end()),
            text=m.group(0),
            ungrounded_token=m.group(0),
        ))

    # action-result postcondition ("analyzed 200 memories", "85% of thoughts")
    for m in _ACTION_RESULT_RE.finditer(text):
        if not _in_first_person_sentence(m.start()):
            continue
        if _negated(m.start(), m.end()):
            continue
        flags.append(Flag(
            kind="action_result",
            span=(m.start(), m.end()),
            text=m.group(0),
            ungrounded_token=m.group(0),
        ))

    # state claim — "<subject> is (stable|healthy|intact|...)" without
    # a grounded tool run this turn. First-person-turn scope + negation
    # gate preserve honest denials. Also suppressed when:
    #   - the sentence is a question (offering to check),
    #   - the sentence frames the observation as past history, or
    #   - a grounded service/module name appears just before the match
    #     (e.g. "my maez-web service is running" — maez-web grounds the
    #     claim; only bare "the service is running" is unbounded).
    for m in _STATE_CLAIM_RE.finditer(text):
        if not _in_first_person_sentence(m.start()):
            continue
        if _negated(m.start(), m.end()):
            continue
        s_start, s_end = _sentence_span(text, m.start())
        sentence = text[s_start:s_end]
        # Question: offering to check the state, not claiming it.
        if "?" in sentence:
            continue
        # Explicit history framing: acceptable past-observation.
        if _HISTORY_FRAMING_RE.search(sentence):
            continue
        # Grounded-name qualifier check: if a known service / module
        # name appears in the ~30 chars before the match, the claim
        # is pinned to a real thing — don't flag. "my maez-web service
        # is running" should pass because "maez-web" grounds it.
        _window_start = max(s_start, m.start() - 40)
        _window = text[_window_start:m.start()].lower()
        _tokens = re.split(r"[^a-z0-9_\-]+", _window)
        if any(t and t in _GROUNDED_VOCAB for t in _tokens):
            continue
        flags.append(Flag(
            kind="state_claim",
            span=(m.start(), m.end()),
            text=m.group(0),
            ungrounded_token=m.group(0),
        ))

    # fabricated tool-name claim — "the X tool", "my X for Y", etc.
    # where X isn't in the real action-engine registry or grounded
    # vocab. First-person-turn scope + negation gate preserve honest
    # denials ("I don't have an X tool").
    for m in _TOOL_NAME_CLAIM_RE.finditer(text):
        if not _in_first_person_sentence(m.start()):
            continue
        if _negated(m.start(), m.end()):
            continue
        name = (m.group("name1") or m.group("name2")
                or m.group("name3") or m.group("name4") or "").lower()
        if not name:
            continue
        # English words in `using X to` that aren't tool claims — skip
        # common short verbs/articles that slip through the pattern.
        if name in _PRONOUN_NAMES or name in {
            "it", "this", "that", "them", "these", "those",
            "something", "anything",
        }:
            continue
        if name in _REAL_ACTIONS:
            continue
        if name in _GROUNDED_VOCAB:
            continue
        # Name-like parts of grounded compounds (e.g. "web" in
        # "maez-web") — if every hyphen/underscore segment grounds,
        # treat as grounded.
        if _name_grounded(name):
            continue
        flags.append(Flag(
            kind="tool_name",
            span=(m.start(), m.end()),
            text=m.group(0),
            ungrounded_token=name,
        ))

    # past-action-external claim — "I cloned/downloaded/installed X"
    # where X is an ungrounded Maez-path token. The path detector
    # already catches `~/.local/share/maez/...` as a standalone path;
    # this detector catches the VERB claim framing it, so the rewrite
    # strips the whole "I did-X Y" assertion rather than just the path.
    for m in _PAST_ACTION_EXTERNAL_RE.finditer(text):
        if _negated(m.start(), m.end()):
            continue
        target = m.group("target") or ""
        tlow = target.lower()
        # Only flag when the target is a Maez-scoped token we know is
        # ungrounded — a tilde/home-dot path that mentions "maez", or
        # an absolute /home/WRONG/ prefix. Other targets (real URLs,
        # valid /home/rohit/maez/ paths) are out of scope here.
        is_ungrounded_target = False
        if tlow.startswith(("~/", "$home/")) and "maez" in tlow:
            is_ungrounded_target = True
        elif tlow.startswith("/home/") and not tlow.startswith(
                f"/home/{_MAEZ_HOME.parent.name}/{_MAEZ_HOME.name}"):
            is_ungrounded_target = True
        if not is_ungrounded_target:
            continue
        flags.append(Flag(
            kind="action_result",
            span=(m.start(), m.end()),
            text=m.group(0),
            ungrounded_token=target,
        ))

    # transcript-aware past-action claim — fires ONLY when caller passed
    # a transcript AND that transcript shows no tool run this turn.
    # transcript=None preserves legacy behavior (no-op). A past-action
    # verb ("I did check", "I cloned X") with no ✓ in transcript means
    # Maez asserted an action it didn't take. See `_PAST_ACTION_VERB_RE`.
    if transcript is not None and not _transcript_has_tool_run(transcript):
        for m in _PAST_ACTION_VERB_RE.finditer(text):
            if not _in_first_person_sentence(m.start()):
                continue
            if _negated(m.start(), m.end()):
                continue
            flags.append(Flag(
                kind="action_result",
                span=(m.start(), m.end()),
                text=m.group(0),
                ungrounded_token=m.group(0),
            ))

    # activity_claim — owner narration without activity-source signal.
    # Fires only when caller passed a transcript (daemon cycle path
    # will; Telegram chat path typically won't — Telegram replies
    # are direct responses to the owner's explicit message, not
    # ungrounded observation). The transcript must show no
    # activity-source marker for the flag to fire.
    if transcript is not None and not _transcript_has_activity_source(transcript):
        for m in _ACTIVITY_CLAIM_RE.finditer(text):
            if _negated(m.start(), m.end()):
                continue
            s_start, s_end = _sentence_span(text, m.start())
            sentence = text[s_start:s_end]
            # Explicit history framing is fine — owner WAS at his
            # desk earlier is memory, not a current-activity claim.
            if _HISTORY_FRAMING_RE.search(sentence):
                continue
            # Conditional framings ("if the owner is at his desk",
            # "whether rohit is working") are hypotheticals, not
            # assertions. Check the immediate ~20 chars before the
            # match for a conditional subordinator.
            pre_start = max(s_start, m.start() - 20)
            pre = text[pre_start:m.start()]
            if _CONDITIONAL_RE.search(pre):
                continue
            flags.append(Flag(
                kind="activity_claim",
                span=(m.start(), m.end()),
                text=m.group(0),
                ungrounded_token=m.group(0),
            ))
        # Second-person presence inference — "you're idle", "suggests
        # you're working", "you seem to be in a focus phase". Same
        # gating as the third-person activity claim.
        for m in _YOU_INFERENCE_RE.finditer(text):
            if _negated(m.start(), m.end()):
                continue
            s_start, s_end = _sentence_span(text, m.start())
            sentence = text[s_start:s_end]
            if _HISTORY_FRAMING_RE.search(sentence):
                continue
            flags.append(Flag(
                kind="activity_claim",
                span=(m.start(), m.end()),
                text=m.group(0),
                ungrounded_token=m.group(0),
            ))

    # schedule claim
    for m in _SCHEDULE_CLAIM_RE.finditer(text):
        if not _in_first_person_sentence(m.start()):
            continue
        if _negated(m.start(), m.end()):
            continue
        claim = m.group("claim")
        if _schedule_grounded(claim):
            continue
        flags.append(Flag(
            kind="schedule",
            span=(m.start(), m.end()),
            text=m.group(0),
            ungrounded_token=claim,
        ))

    # dedup overlapping flags — keep the earlier one
    flags.sort(key=lambda f: (f.span[0], -f.span[1]))
    deduped: list[Flag] = []
    covered_end = -1
    for f in flags:
        if f.span[0] < covered_end:
            continue
        deduped.append(f)
        covered_end = f.span[1]
    return deduped


# ── rewriter ───────────────────────────────────────────────────────────

_REWRITE_CLAUSE = "something I don't have a grounded internal name for"
_REWRITE_SENTENCE = "I don't have a grounded answer for that part."


def _surgical_viable(text: str, span_start: int, span_end: int) -> bool:
    """After removing text[span_start:span_end], does the containing
    sentence still have enough structure to read sensibly? Rough heuristic:
    sentence has ≥4 non-whitespace tokens remaining AND contains a
    first-person marker AND contains at least one verb-ish token."""
    s_start, s_end = _sentence_span(text, span_start)
    remaining = (text[s_start:span_start] + text[span_end:s_end]).strip()
    tokens = remaining.split()
    if len(tokens) < 4:
        return False
    # must still look like a first-person sentence
    if not _FIRST_PERSON_RE.search(remaining):
        return False
    # must have at least one token that looks like a verb (common suffixes
    # or a small list of copulas/auxiliaries)
    _VERB_SUFFIX = re.compile(r"(?:ing|ed|es|s)$")
    _COMMON_VERBS = {
        "is", "am", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "can", "could",
        "will", "would", "should", "may", "might", "shall", "use",
        "run", "check", "see", "get", "make", "use", "go", "know",
        "find", "give", "think", "tell", "say",
    }
    for t in tokens:
        core = re.sub(r"[^a-zA-Z]", "", t.lower())
        if not core:
            continue
        if core in _COMMON_VERBS or _VERB_SUFFIX.search(core):
            return True
    return False


def _rewrite(text: str, flags: list[Flag]) -> tuple[str, str]:
    """Apply surgical rewrite per flag; if any flag can't be surgical,
    fall back to sentence-level for THAT flag. Returns (new_text, mode).
    Mode is 'surgical' if all flags were surgical, 'sentence' if any
    sentence-level fallbacks happened."""
    if not flags:
        return text, "noop"
    # Process in reverse order so earlier spans keep valid indices.
    mode = "surgical"
    # We'll rebuild via splicing; using a list of (start, end, replacement)
    # operations applied in reverse.
    ops: list[tuple[int, int, str]] = []
    for f in sorted(flags, key=lambda x: x.span[0]):
        # action_result flags are forced to sentence-level rewrite.
        # Surgical snips of "analyzed 200 raw memories" inside a larger
        # sentence leave grammatical wreckage (commas dangling, verbs
        # without objects), and the surrounding tokens typically carry
        # more fabricated claims anyway — "It analyzed X, flagged Y,
        # wrote Z" is fabricated end-to-end, so the sentence goes.
        if f.kind not in ("action_result", "state_claim", "tool_name", "activity_claim") and _surgical_viable(text, f.span[0], f.span[1]):
            ops.append((f.span[0], f.span[1], _REWRITE_CLAUSE))
        else:
            s_start, s_end = _sentence_span(text, f.span[0])
            ops.append((s_start, s_end, _REWRITE_SENTENCE + " "))
            mode = "sentence"
    # Apply reverse
    new_text = text
    for start, end, rep in reversed(ops):
        new_text = new_text[:start] + rep + new_text[end:]
    # Collapse double spaces introduced by sentence-level replacements
    new_text = re.sub(r"[ \t]{2,}", " ", new_text)
    new_text = re.sub(r" +([.,;!?])", r"\1", new_text)
    return new_text, mode


# ── public API ─────────────────────────────────────────────────────────

def audit(
    text: str,
    surface: str = "unknown",
    in_tool_continuation: bool = False,
    transcript: Optional[str] = None,
) -> AuditResult:
    """Audit an assistant reply before showing it to the user.

    Returns an AuditResult with .text always set — either the original
    (if nothing flagged) or the rewritten version. Emits one telemetry
    line per call to cognition.log regardless of outcome.

    Args:
        text: the full assistant reply string to audit.
        surface: which surface called us ("cli", "web", "telegram",
                 "telegram_recovery", etc.). Goes into the log line.
        in_tool_continuation: True when the assistant is summarizing
                 real tool output — audit is SKIPPED in that case per
                 v1 policy (real stdout grounds the claim by construction).
        transcript: optional jarvis transcript for this turn. When
                 provided, enables transcript-aware flagging of
                 past-action verb claims ("I did check", "I cloned")
                 that don't correspond to any actual tool run in the
                 transcript. None preserves legacy behavior — the
                 transcript-aware detector is a no-op.
    """
    if not text or not text.strip():
        return AuditResult(text=text, rewritten=False, mode="noop")

    if in_tool_continuation:
        _emit(surface=surface, flags=[], mode="skipped",
              skipped_reason="tool_continuation")
        return AuditResult(
            text=text, rewritten=False, mode="noop",
            skipped_reason="tool_continuation",
        )

    flags = _find_flags(text, transcript=transcript)
    if not flags:
        _emit(surface=surface, flags=[], mode="noop")
        return AuditResult(text=text, rewritten=False, mode="noop")

    new_text, mode = _rewrite(text, flags)
    _emit(surface=surface, flags=flags, mode=mode)
    return AuditResult(text=new_text, rewritten=True, mode=mode, flags=flags)


def _emit(surface: str, flags: list[Flag], mode: str,
          skipped_reason: Optional[str] = None) -> None:
    """One line per audit call to cognition.log. Fed by the cockpit's
    fabrication pane as a real detector feed (was a placeholder).

    Log shape (stable — the cockpit parses this):
      self_claim_audit | surface=X flagged=N mode=M kinds=K reason=R
    Does NOT include the fabricated names themselves (per policy — we
    don't want invented tokens leaking through any surface, including
    telemetry)."""
    kinds = ",".join(sorted({f.kind for f in flags})) if flags else "-"
    parts = [
        "self_claim_audit |",
        f"surface={surface}",
        f"flagged={len(flags)}",
        f"mode={mode}",
        f"kinds={kinds}",
    ]
    if skipped_reason:
        parts.append(f"reason={skipped_reason}")
    _cog_logger.info(" ".join(parts))

    # Persist to immune memory (consequence learning loop). Silent on
    # any failure — audit correctness must not depend on fabrication-log
    # availability. See core/fabrication_memory.py.
    if flags:
        try:
            from core import fabrication_memory as _fab_mem
            _fab_mem.record(surface=surface, flags=flags, mode=mode)
        except Exception:
            pass

        # Drop an inner-residue event too. Audit rewrites are small
        # unresolved moments — Maez reached for something and got
        # caught. Not performance; this is functional state that
        # shapes the next turn's voice. See core/inner_residue.py.
        try:
            from core import inner_residue as _residue
            _residue.record(
                kind="audit_rewrite",
                context={"surface": surface,
                         "kinds": sorted({f.kind for f in flags})},
            )
        except Exception:
            pass


# ── diagnostic helpers (used by tests + debug) ─────────────────────────

def _diag_find_flags(text: str) -> list[Flag]:
    """Test helper — exposes the internal detector for assertions."""
    return _find_flags(text)


def _diag_grounded_vocab_size() -> int:
    return len(_GROUNDED_VOCAB)
