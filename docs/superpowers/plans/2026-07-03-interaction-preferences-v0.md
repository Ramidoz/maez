# Interaction Preferences v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to execute this plan.

**Goal:** Persist explicit owner-stated interaction preferences as durable, inspectable relationship facts and render them prominently in future turns without converting them into policy, output suppression, or voice scripting.

**Architecture:** Add a dedicated `core.interaction_preferences` package with a testimony-shaped sqlite store, a narrow deterministic question-cadence detector, and a verbatim factual prompt renderer. Wire it into `daemon/maez_daemon.py` before prompt consolidation as a named background system part. Roll out with `MAEZ_INTERACTION_PREFERENCES_SHADOW` first, then `MAEZ_INTERACTION_PREFERENCES`; flag-off is byte-identical.

**Tech Stack:** Python 3, sqlite3, `unittest`, `core.infra.env_flags.strict_env_flag`, daemon prompt assembly, structural AST/grep guards.

---

## Task 0 - Pin The Live Seams Before Code

**Purpose:** Confirm the plan touches the real prompt path and does not inherit a guessed ID, policy-store, or suppressor seam.

**Implementation notes:**
- Prompt seam verified in `daemon/maez_daemon.py`: lived/temporal recall are appended first, ambient/capability follows, then turn-final directives land closest to the user message through `_compose_turn_final_system_part()` and `_consolidate_system_messages()`.
- The interaction-preference block lands as its own system message after temporal/lived recall and before ambient/capability. This makes it prominent background context without making it the closest-turn command.
- The block must also append `("interaction_preferences", block)` to `system_part_capture` so prompt-shape logs can witness it.
- Source refs use a minimal content-light turn ref because the live daemon path does not expose a durable owner-turn row id at that seam:
  - `owner_turn:{surface}:{sha256(owner_text)[:16]}:{created_at_ms}`
  - Store the full `statement_sha256` separately.
  - Store the verbatim bounded `owner_statement` because testimony is the point of the organ.
- Historical trace is not repaired in this slice. If the ordinary memory path already stores the owner turn, it remains history. If it does not, this plan does not add a second memory writer; that would be a separate slice.
- The new package path is `core/interaction_preferences/`, not `core/policies/` and not `core/memory/relationship_*`. This keeps the store out of policy composition and out of relevance-gated recall.

**TDD / verification checklist:**
- Add a test documenting the prompt placement by inspecting `handle_message` source:
  - `interaction_preferences` appears before `_combined_context_block`.
  - `interaction_preferences` appears before `_compose_turn_final_system_part`.
  - `system_part_capture.append(("interaction_preferences", ...))` exists.
- Add a test documenting that no code under `core/interaction_preferences` imports `core.policies.autonomy_preferences`.
- Add a test documenting that no code under `core/interaction_preferences` imports lived recall writers or episode stores.
- Add a short implementation note in the final review artifact naming the chosen source-ref shape and the historical-trace non-change.

---

## Task 1 - Build The Testimony-Shaped Store

**Purpose:** Create the dedicated fact store whose schema makes a preference testimony, not configuration.

**Files:**
- Add `core/interaction_preferences/__init__.py`
- Add `core/interaction_preferences/store.py`
- Add `tests/test_interaction_preferences_store.py`
- Add `core/infra/paths.py` helper `interaction_preferences_db()`

**Schema:**
Use sqlite table `interaction_preferences`:

```sql
CREATE TABLE IF NOT EXISTS interaction_preferences (
    preference_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'retracted', 'superseded')),
    preference_class TEXT NOT NULL CHECK (preference_class IN ('question_cadence')),
    owner_statement TEXT NOT NULL,
    normalized_fact TEXT,
    source_ref TEXT NOT NULL,
    surface TEXT NOT NULL,
    statement_sha256 TEXT NOT NULL,
    supersedes_preference_id TEXT,
    superseded_by_preference_id TEXT,
    retraction_reason TEXT,
    revision_statement TEXT
);
```

Indexes:
- `(status, preference_class)`
- `(statement_sha256, preference_class)`

**Store API:**
```python
class InteractionPreferencesStore:
    def record_capture(...)
    def record_retraction(...)
    def active_preferences(preference_class: str | None = None) -> list[InteractionPreference]
    def list_all() -> list[InteractionPreference]
    def get(preference_id: str) -> InteractionPreference | None
```

**Rules:**
- `owner_statement` is verbatim bounded testimony and is the only text rendered to Maez in v0.
- `normalized_fact` may be stored for inspection/search, but the store must reject normalizations that add known forbidden qualifiers from this incident class:
  - `unnecessary`
  - `needless`
  - `only when necessary`
- `record_retraction()` supersedes/deweights; it never deletes the old row.
- Status updates may update `status`, `updated_at`, `superseded_by_preference_id`, and retraction fields. They must never mutate `owner_statement`, `source_ref`, `created_at`, or `statement_sha256`.
- No boolean modifier columns, numeric policy weights, target-action fields, or command-shaped fields.

**TDD steps:**
1. RED: `test_capture_row_is_testimony_not_config`
   - Records `owner_statement="stop asking me so many questions"`.
   - Asserts exact owner statement is stored.
   - Asserts schema has no `fewer_questions`, `question_limit`, `policy_weight`, `target`, `modifier`, or `command` columns.
2. RED: `test_retraction_supersedes_without_deleting`
   - Captures then retracts.
   - Asserts original row still exists with original `owner_statement`.
   - Asserts active list no longer includes it.
3. RED: `test_normalized_fact_rejects_editorializing`
   - Passing a normalized fact containing `unnecessary`, `needless`, or `only when necessary` raises before write.
4. GREEN: implement store.

---

## Task 2 - Build The Deterministic Detector

**Purpose:** Capture only explicit owner-authored question-cadence preferences, and make conversational retraction at least as easy as capture.

**Files:**
- Add `core/interaction_preferences/detector.py`
- Add `tests/test_interaction_preferences_detector.py`

**API:**
```python
@dataclass(frozen=True)
class PreferenceDetection:
    action: Literal["capture", "retract"]
    preference_class: Literal["question_cadence"]
    owner_statement: str
    normalized_fact: str | None

def detect_interaction_preference(
    text: str,
    *,
    active_question_cadence: bool,
    surface: str,
) -> PreferenceDetection | None:
    ...
```

**Capture patterns must match:**
- `stop asking me so many questions`
- `please stop asking so many questions`
- `ask fewer questions`
- `don't ask so many follow-up questions`

**Retraction patterns must match when an active question-cadence preference exists:**
- `actually, ask away`
- `it's okay to ask questions again`
- `you can ask questions again`
- `ask away`

**Must not match:**
- `you ask good questions`
- `why are there so many questions in this spec?`
- `can you ask me three questions?`
- `I wonder why people ask so many questions`
- `don't stop asking questions if you need to understand`
- `ask fewer questions in the test fixture`
- quoted/non-owner text such as `the transcript says "stop asking me so many questions"`

**Rules:**
- Capture is high precision and under-fires on ambiguity.
- Retraction is easier only for direct un-saying patterns and only when an active preference exists.
- The detector never writes. It returns a candidate; daemon/store wiring decides shadow vs durable.
- The detector returns the verbatim owner statement as its renderable text.
- `normalized_fact` is optional and non-rendered. If present, it must be meaning-preserving and quote the owner statement rather than soften it.

**TDD steps:**
1. RED: parameterized exact-match tests for all capture phrases.
2. RED: parameterized near-miss tests for every must-not-match phrase.
3. RED: retraction patterns return `None` when no active question-cadence preference exists.
4. RED: retraction patterns return `action="retract"` when active preference exists.
5. GREEN: implement deterministic matcher.

---

## Task 3 - Render And Inspect Preferences

**Purpose:** Make active preferences visible as relationship facts and owner-inspectable without becoming commands.

**Files:**
- Add `core/interaction_preferences/render.py`
- Add `scripts/interaction_preferences.py`
- Add `tests/test_interaction_preferences_render.py`
- Add `tests/test_interaction_preferences_script.py`

**Renderer API:**
```python
def render_interaction_preferences(preferences: Sequence[InteractionPreference]) -> str:
    ...
```

**Output shape:**
```text
OWNER-STATED INTERACTION PREFERENCES (relationship facts, not commands)
- Rohit explicitly said: "stop asking me so many questions."
```

**Rules:**
- Render `owner_statement`, never `normalized_fact`.
- Do not render command language added by the scaffold:
  - `must`
  - `never`
  - `do not ask`
  - `don't ask`
  - `only ask`
- The owner's own words are preserved even if they contain imperative language; the scaffold must label them as testimony, not command. Tests should distinguish scaffold text from quoted owner text.
- Empty active list renders `""`.

**Script surface:**
`scripts/interaction_preferences.py`:
- `list --db PATH`
- `show <id> --db PATH`
- `retract <id> --reason TEXT --owner-approved --db PATH`

**Script rules:**
- Listing and showing are read-only.
- Retraction requires `--owner-approved`.
- CLI retraction is a safety valve; conversational retraction remains required in daemon wiring.

**TDD steps:**
1. RED: `test_renderer_uses_verbatim_owner_statement_not_normalized_fact`.
2. RED: `test_renderer_scaffold_contains_no_command_language`.
3. RED: `test_empty_active_preferences_render_empty`.
4. RED: `test_script_retract_requires_owner_approved`.
5. GREEN: implement renderer and script.

---

## Task 4 - Wire Shadow, Durable Writes, And Prompt Context Into The Daemon

**Purpose:** Make explicit preferences survive future turns while preserving flag-off behavior and making shadow review possible.

**Files:**
- Modify `daemon/maez_daemon.py`
- Add `tests/test_interaction_preferences_daemon.py`
- Add or extend `tests/test_daemon_prompt_seams.py`

**Flags:**
- `MAEZ_INTERACTION_PREFERENCES_SHADOW`
- `MAEZ_INTERACTION_PREFERENCES`

Both must use `core.infra.env_flags.strict_env_flag`.

**Daemon wiring design:**
- Near the start of `handle_message`, after owner `text` and `source` are known but before prompt assembly:
  - If either flag is on, instantiate/read `InteractionPreferencesStore`.
  - Run detector with `active_question_cadence=bool(store.active_preferences("question_cadence"))`.
  - In shadow mode:
    - log `interaction_preference_shadow action=would_capture|would_retract class=question_cadence source_ref=... statement_sha256=... owner_statement_preview=...`
    - write no preference row.
  - In enabled mode:
    - capture writes one active row.
    - retraction supersedes the active row.
    - failures are logged and do not break reply generation.
- During prompt assembly:
  - If `MAEZ_INTERACTION_PREFERENCES` is on, fetch active preferences and render them.
  - If rendered block is non-empty, append it as a system message after lived/temporal recall and before ambient/capability.
  - Append `("interaction_preferences", block)` to `system_part_capture`.
  - Shadow mode does not render.

**Source ref helper:**
Add a daemon-local or module helper:
```python
def owner_turn_source_ref(*, source: str, text: str, created_at_ms: int) -> str:
    return f"owner_turn:{source}:{sha256(text.encode()).hexdigest()[:16]}:{created_at_ms}"
```

**TDD steps:**
1. RED: flag-off byte-identical prompt test.
   - Patch store/detector to fail if called.
   - With both flags off, `handle_message` must not call detector/store/renderer and prompt parts remain unchanged.
2. RED: shadow logs would-capture but writes nothing and renders nothing.
3. RED: enabled capture writes one active row and renders the block on the next turn.
4. RED: conversational `actually, ask away` supersedes the active row and removes the block on a later turn.
   - Conversational retraction is as easy as capture: no CLI is required for the direct un-saying fixture.
5. RED: prompt-shape log includes `interaction_preferences` when rendered.
6. GREEN: implement daemon wiring.

**Integration caution:**
- Do not add any output-path code after model generation.
- Do not edit `_compose_turn_final_system_part()` to add the preference as closest-turn instruction.
- Do not change casual-presence renderer modules.

---

## Task 5 - Add Structural Covenant Guards

**Purpose:** Make the covenant boundaries mechanically hard to regress.

**Files:**
- Add `tests/test_interaction_preferences_guards.py`

**Guard 1 - no AutonomyPreferences:**
- Parse/read:
  - `core/interaction_preferences/**/*.py`
  - the added daemon preference region
  - `scripts/interaction_preferences.py`
- Assert none import or reference:
  - `core.policies.autonomy_preferences`
  - `AutonomyPreferences`
  - `autonomy_preferences_db`

**Guard 2 - no post-generation suppressor/filter:**
- Assert new package does not define or call APIs containing:
  - `suppress`
  - `filter_generated`
  - `rewrite_reply`
  - `delete_question`
  - `question_cap`
  - `post_generation`
- AST-check `daemon/maez_daemon.py` so calls to interaction-preference detector/render/store appear before `_consolidate_system_messages(...)` and before any `_bot_send_message` / generated-reply send path.
- Plant-test option: create a temporary source snippet with `interaction_preferences` called after a fake `_bot_send_message()` and assert the extractor catches it.

**Guard 3 - casual-presence non-duplication:**
- Assert no files matching the casual-presence renderer/routing area import `core.interaction_preferences`.
- Assert this slice does not modify the self-status/question-tail route.

**Guard 4 - no memory-recall feed:**
- Assert `core/interaction_preferences` does not import `EpisodeStore`, lived recall writers, or `core.memory.episode_builder`.
- The dedicated store may live under runtime `memory/`, but its rows are not recall candidates.

**TDD steps:**
1. RED: write guard tests and prove each guard trips on an injected sample string/helper.
2. GREEN: run guards against real code.

---

## Task 6 - Regression, Review Artifact, And Stop

**Purpose:** Leave the branch build-ready for covenant review, with no merge, no flag flip, and no live mutation.

**Test command:**
```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest \
  tests.test_interaction_preferences_store \
  tests.test_interaction_preferences_detector \
  tests.test_interaction_preferences_render \
  tests.test_interaction_preferences_script \
  tests.test_interaction_preferences_daemon \
  tests.test_interaction_preferences_guards \
  tests.test_daemon_prompt_seams \
  tests.test_memory_integrity_invariant
ruff check core/interaction_preferences scripts/interaction_preferences.py daemon/maez_daemon.py tests/test_interaction_preferences_*.py
```

If `ruff` is not available through the repo environment, use the repo's existing lint command and record the command in the review artifact.

**Review artifact:**
Write `docs/proof/2026-07-03-interaction-preferences-v0-review.md` with:
- chosen prompt seam and why it is prominent-but-not-command;
- chosen source-ref shape;
- detector match/reject fixture table;
- shadow-vs-enabled behavior summary;
- structural guard results:
  - no AutonomyPreferences;
  - no suppressor/post-generation call;
  - no casual-presence duplication;
  - no recall/memory writer feed;
- predicted live witness steps.

**Stop gate:**
- STOP after tests and review artifact.
- Do not merge.
- Do not push unless explicitly asked.
- Do not set `MAEZ_INTERACTION_PREFERENCES_SHADOW`.
- Do not set `MAEZ_INTERACTION_PREFERENCES`.
- Do not restart `maez.service`.

---

## Live Witness Sequence After Merge

Owner-run, after review and merge:

1. Shadow:
   - Set `MAEZ_INTERACTION_PREFERENCES_SHADOW=1`.
   - Restart `maez.service`.
   - Send `stop asking me so many questions`.
   - Confirm log has `would_capture`, source ref, bounded quote, and no DB row.
2. Enable:
   - Set `MAEZ_INTERACTION_PREFERENCES=1`.
   - Restart `maez.service`.
   - Send the same preference phrase.
   - Confirm exactly one active row.
3. Prompt witness:
   - Send an ordinary turn.
   - Confirm prompt-shape log includes `interaction_preferences`.
   - Confirm the rendered block uses the verbatim owner statement.
4. Retraction:
   - Say `actually, ask away`.
   - Confirm old row is superseded/retracted, no hard delete.
   - Confirm future prompt-shape logs no longer render the old active preference.

## Predicted Effect

After the slice is enabled, an explicit owner statement such as `stop asking me so many questions` persists as a relationship fact outside relevance-gated recall. Maez sees the owner's verbatim statement in future turns as context. The effect should be distributional: Maez weighs the stated preference more often, while still being free to ask a question it judges worth asking.
