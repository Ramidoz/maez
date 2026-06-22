# Lean Conversation Arc A Task 0 Proof Gate

Date: 2026-06-22

Scope: docs-only proof for `docs/superpowers/plans/2026-06-22-lean-conversational-path-arc-a.md` Task 0. No production code or tests were modified.

Worktree: `/home/rohit/.config/superpowers/worktrees/maez/lean-conversational-path-arc-a`

Runner note: this worktree does not have `.venv/bin/python`, so unittest commands used `/home/rohit/maez/.venv/bin/python` from the main checkout, per the task instruction.

## Focused-local seam

Verdict: GO.

Production call:
- `daemon/maez_daemon.py:6920` enters ordinary focused synthesis only when `_reply_decision.mode is ReplyMode.FOCUSED`.
- `daemon/maez_daemon.py:6961` calls `_focused_synthesize(_focused_working_set, surface=source)`.
- `rg -n "_focused_synthesize\\(|focused_synthesize\\(" daemon/maez_daemon.py core/routing tests` found one production daemon call, at `daemon/maez_daemon.py:6961`, plus the implementation and tests.

Prompt assembly:
- `core/routing/focused_cognition.py:1034` defines `focused_synthesize(...)`.
- `core/routing/focused_cognition.py:1056-1066` builds the full focused system prompt from the voice card, citation instruction, trust-tier instruction, origin-trust instruction, and ordered evidence text.

Decision:
- Arc A can add optional lean rendering inside `focused_synthesize(...)` without changing `resolve_reply_mode`.

## Self-capability/body question seam

Verdict: GO with exact reuse.

Current predicate:
- `_QUESTION_SHAPE_RE` is defined at `core/dispatcher/layer0.py:97-100`.
- `_SELF_CAPABILITY_RE` is defined at `core/dispatcher/layer0.py:110-116`.
- `_is_self_capability_question(...)` is defined at `core/dispatcher/layer0.py:515-518`; it requires question shape first, then the self-capability regex.

Current production use:
- `Layer0Dispatcher.emit_spec(...)` sets `self_capability_question` from `evidence_precedence_enabled() and _is_self_capability_question(utterance)` at `core/dispatcher/layer0.py:242-244`.

Golden sample preservation:
- Extra witness command:

```text
/home/rohit/maez/.venv/bin/python - <<'PY'
from core.dispatcher.layer0 import _is_self_capability_question
samples = [
    "what can you do?",
    "can you read pages right now?",
    "can your search tools read this page?",
]
for sample in samples:
    print(f"{sample!r}: {_is_self_capability_question(sample)}")
PY
```

Output:

```text
'what can you do?': False
'can you read pages right now?': False
'can your search tools read this page?': True
```

Arc A plan:
- Extract the predicate into `core/routing/self_capability_question.py`.
- Keep `core/dispatcher/layer0.py` behavior byte-equivalent by delegating its private function to the shared predicate.
- Focused lean eligibility uses the shared predicate and fails body/capability questions toward FULL.
- The shared predicate must preserve today's predicate: broad "what can you do?" and "can you read pages right now?" remain `False`, not widened.

## Fresh/web authority seam

Verdict: GO.

Fresh predicate:
- `core/routing/focused_cognition.py:89` defines `_FRESH_SOURCE_TYPES = ("fresh_evidence", "web_context")`.
- `turn_has_fresh_evidence(working_set)` starts at `core/routing/focused_cognition.py:101` and reads working-set item source types.

Support scope:
- `daemon/maez_daemon.py:1086` imports `turn_has_fresh_evidence`.
- `daemon/maez_daemon.py:1087-1091` computes `_fresh` from the working set and returns without MiniCheck when it is false.

Test witness:

```text
/home/rohit/maez/.venv/bin/python -m unittest tests.test_turn_has_fresh_evidence tests.test_support_gate_scope_seam -v
```

Output:

```text
Ran 8 tests in 0.002s

OK
```

The eight passing tests were:
- `tests.test_turn_has_fresh_evidence`: empty, fresh evidence, mixed recall/web, none, recall-only, and web-context cases.
- `tests.test_support_gate_scope_seam`: fresh web convenes the gate; recall-only skips MiniCheck and leaves reply unchanged.

## Cold-open boundary

Verdict: NAMED OUT-OF-SCOPE FOR V0.

Reason:
- Arc A lives inside focused cognition.
- `assemble_working_set(...)` starts at `core/routing/focused_cognition.py:827`.
- If there is no evidence, no dialogue anchor, no date cue, and no structured recall item, the guard at `core/routing/focused_cognition.py:870-876` returns `None`.
- If a continuity/fail-safe turn needs dialogue but has no anchor and is not date-addressed, `core/routing/focused_cognition.py:863-868` also returns `None`.

Owner witness note:
- A fresh-session contextless greeting may still hit legacy synthesis. That is not an Arc A regression; it belongs to Arc B core-dump defuser or a future lean-legacy pass.

## Must-rail path exclusion

Verdict: GO.

Reply-mode order:
- `ReplyMode` includes `CLINICAL`, `CAMERA`, `TOOL`, `ECHO`, `HONEST_EMPTY`, `FOCUSED`, and `LEGACY` at `core/routing/reply_mode.py:17-24`.
- `resolve_reply_mode(...)` returns `CLINICAL`, `CAMERA`, `TOOL`, and `ECHO` before `FOCUSED` at `core/routing/reply_mode.py:65-84`.
- The daemon's pre-tail decision returns clinical and camera answers before the rest of the reply pipeline at `daemon/maez_daemon.py:5705-5716`.
- The daemon handles authoritative tool and echo replies before honest-empty/photo/focused synthesis at `daemon/maez_daemon.py:6809-6812`.

Honest-empty:
- Honest-empty is a distinct path: `daemon/maez_daemon.py:6817-6828` calls `build_honest_empty_reply(...)`, not `focused_synthesize(...)`.
- The resolver checks focused before honest-empty, but the daemon candidates are structurally disjoint for the zero-evidence honest-empty case: `_focused_candidate` requires evidence, dialogue uncertainty, or a date-addressed turn at `daemon/maez_daemon.py:6602-6611`; `_honest_empty_candidate` requires no photo, no evidence, no dialogue uncertainty, no echo, and no authoritative tool reply at `daemon/maez_daemon.py:6612-6619`.

Photo/vision:
- Photo turns use their own focused-photo path: `daemon/maez_daemon.py:6866-6876` imports and calls `synthesize_photo_turn(...)`.
- The photo branch sets `_focused_used = True` when it produces a reply at `daemon/maez_daemon.py:6890-6893`.
- Ordinary focused synthesis only runs after that when `not _focused_used and _reply_decision.mode is ReplyMode.FOCUSED` at `daemon/maez_daemon.py:6920`.
- The photo working-set item uses source type `photo_vision` inside `synthesize_photo_turn(...)` at `core/routing/focused_cognition.py:1321-1324`.

Decision:
- Lean eligibility still checks fresh/date/self-capability, but tool-authoritative, clinical, camera, echo, honest-empty, and photo turns are excluded structurally by the production call path. If a future reply-mode change routes those through `focused_synthesize(...)`, Task 0 must be revisited.

## Daemon metadata scope

Verdict: GO.

In-scope variables at the focused call:
- `_date_addressed_turn`: defined before reply-mode resolution at `daemon/maez_daemon.py:6562-6564` and passed into the `ReplyDecisionSignals` at `daemon/maez_daemon.py:6620-6627`.
- `_rk_turn_kind`: defined before focused synthesis at `daemon/maez_daemon.py:6653-6661`.
- `_legacy_prompt_chars`: computed immediately before `_focused_synthesize(...)` at `daemon/maez_daemon.py:6950-6954`.

Focused call witness:
- `_focused_synthesize(...)` is called at `daemon/maez_daemon.py:6961-6964`.
- `_rk_turn_kind` is already used in the focused timing/support path at `daemon/maez_daemon.py:6965-6980` and `daemon/maez_daemon.py:7001-7005`.
- `_legacy_prompt_chars` is already recorded after focused synthesis at `daemon/maez_daemon.py:7016-7020`.

Decision:
- Task 3 may thread these variables into `focused_synthesize(...)` without stale or guessed values.

## Commands Run

Task 0 commands were run from the isolated worktree, with `/home/rohit/maez/.venv/bin/python` substituted only for `.venv/bin/python` because the worktree venv was missing.

```text
rg -n "_focused_synthesize\\(|focused_synthesize\\(" daemon/maez_daemon.py core/routing tests
sed -n '6960,7035p' daemon/maez_daemon.py
sed -n '1020,1095p' core/routing/focused_cognition.py
sed -n '90,120p' core/dispatcher/layer0.py
sed -n '238,278p' core/dispatcher/layer0.py
sed -n '510,522p' core/dispatcher/layer0.py
rg -n "_is_self_capability_question|_SELF_CAPABILITY_RE|_QUESTION_SHAPE_RE" core/dispatcher/layer0.py tests
/home/rohit/maez/.venv/bin/python - <<'PY'
from core.dispatcher.layer0 import _is_self_capability_question
samples = [
    "what can you do?",
    "can you read pages right now?",
    "can your search tools read this page?",
]
for sample in samples:
    print(f"{sample!r}: {_is_self_capability_question(sample)}")
PY
sed -n '70,105p' core/routing/focused_cognition.py
sed -n '1076,1110p' daemon/maez_daemon.py
/home/rohit/maez/.venv/bin/python -m unittest tests.test_turn_has_fresh_evidence tests.test_support_gate_scope_seam -v
rg -n "return None" core/routing/focused_cognition.py | head -20
sed -n '827,905p' core/routing/focused_cognition.py
sed -n '1,90p' core/routing/reply_mode.py
sed -n '6600,6665p' daemon/maez_daemon.py
rg -n "_reply_decision.mode is ReplyMode.FOCUSED|ReplyMode.HONEST_EMPTY|ReplyMode.TOOL|ReplyMode.CLINICAL|ReplyMode.CAMERA|ReplyMode.ECHO|photo_vision|focused_synthesize" daemon/maez_daemon.py core/routing tests | head -120
sed -n '6625,6665p' daemon/maez_daemon.py
sed -n '6960,7030p' daemon/maez_daemon.py
rg -n "_legacy_prompt_chars|_date_addressed_turn|_rk_turn_kind" daemon/maez_daemon.py | head -40
```

Additional line-number witnesses:

```text
nl -ba daemon/maez_daemon.py | sed -n '5688,5722p'
nl -ba daemon/maez_daemon.py | sed -n '6556,6578p'
nl -ba daemon/maez_daemon.py | sed -n '6600,6628p'
nl -ba daemon/maez_daemon.py | sed -n '6625,6665p'
nl -ba daemon/maez_daemon.py | sed -n '6788,6830p'
nl -ba daemon/maez_daemon.py | sed -n '6850,6922p'
nl -ba daemon/maez_daemon.py | sed -n '6916,6970p'
nl -ba core/dispatcher/layer0.py | sed -n '94,118p'
nl -ba core/dispatcher/layer0.py | sed -n '238,258p'
nl -ba core/dispatcher/layer0.py | sed -n '512,520p'
nl -ba core/routing/focused_cognition.py | sed -n '72,100p'
nl -ba core/routing/focused_cognition.py | sed -n '827,878p'
nl -ba core/routing/focused_cognition.py | sed -n '1030,1075p'
nl -ba core/routing/focused_cognition.py | sed -n '1300,1345p'
nl -ba core/routing/reply_mode.py | sed -n '16,90p'
```
