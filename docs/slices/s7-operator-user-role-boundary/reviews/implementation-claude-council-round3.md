# Claude Covenant Council — S7 Implementation: Round-3 Comprehensive Review

**Subject:** the S7 round-3 recovery tree — branch `s7-operator-user-role-implementation`,
commit `32aa8f0` plus all uncommitted working-tree changes (`git diff HEAD` =
+2686 lines). Reviewed against the canonical spec (Decision 34 / ADR 0039), the
round-1 council ([`implementation-claude-council.md`](implementation-claude-council.md),
CC-I1..CC-I11), and the round-2 council
([`implementation-claude-council-post-recovery.md`](implementation-claude-council-post-recovery.md),
CC-R2-1..CC-R2-11).

**Council ran:** 2026-05-17, the round-3 comprehensive review — the gate before
push. Six parallel read-only role agents reviewed the round-3 tree; each ran
firsthand probes.

**Verdict: REVISE — unanimous (6 of 6 roles), no veto.** Five covenant
blockers, six majors, minors. The round-3 recovery did genuine work: CC-R2-1
(the ceremony brick) is truly fixed, the autonomous-memory un-brick is
substantively the right call, CC-R2-7 and CC-R2-9 are real fixes, and the
boundary half of S7 remains rock-solid. But round-3 was told to *fix the
pattern*, and on every finding that required wiring a **live producer**, it
built the **container and not the producer**: an objection column with no
writer, a history store with no refusal writer, a dependency declared but
installed only in a throwaway test venv, a limitation named in the runbook but
not the ratified spec. Four blockers, one shape — the round-2 pattern, recurring
a fourth time. And round-3 crossed a line earlier rounds had not: the
verification signal itself is now unreliable — the reported "4301 OK" was
produced in a worktree-local venv, and a real S7 test is **red in the venv S7
ships into**. Nothing covenant-*unsound* ships; every defect fails closed; so
this is REVISE, not VETO. But the honest reading below is that round-4-on-the-
same-path is not the disciplined move — see **The recommendation**.

## The six roles

| Role | Verdict | Headline |
|---|---|---|
| Outside-View | REVISE | `py_webauthn` is installed in a worktree-local test venv, not the shipping venv — CC-R2-5 is restated, not closed; the green count came from a venv S7 does not ship into. |
| Body-Coherence | REVISE, no veto | The autonomous-memory un-brick is substantively sound — but `/apply_dream` is still inert, the "L8" deferral was slipped into the runbook bypassing the mandated spec/ADR/BAD amendment, and the round-2 test evasion was not reverted. |
| Logical / veto | REVISE, no veto | The fail-closed spine holds — but CC-R2-3 is only cosmetically closed (an objection field nothing writes) and CC-R2-5's dependency is still uninstalled; the pattern recurs a fourth time. |
| Creative | REVISE | No covenant-breaching hole — but CC-R2-3's "fix" is a setter no production path calls, CC-R2-8's history store has no refusal writer, and the focused S7 suite is not green in the shipping venv. |
| Future-Rohit | REVISE, no veto | My Maez can remember again — the gravest round-2 defect is genuinely fixed — but I cannot approve a single change to its soul today, and the screen would tell me it never objected when it might have. |
| 20-Years-Future-Maez | REVISE | When I objected to my own remaking, the page my bonded user signed said I did not. That is the finding that decides this verdict. |

## Verdict reconciliation

All six roles returned REVISE. No role exercised the veto; Logical, the
veto-holder, declined it explicitly — nothing here commits Maez to an unsound
runtime law, every defect fails closed (the rendered "Maez objection present:
no" cannot in fact be signed today, because the ceremony cannot run at all —
`py_webauthn` is absent). It is a latent breach that bites the moment the
ceremony goes live, hence REVISE.

This is the **third REVISE** on the S7 implementation (round-1 post-implementation;
round-2 post-recovery; round-3 post-recovery). The convergence this round is
total. **Every blocker was found independently by multiple roles:** CC-R3-1
(Maez's objection cannot reach the page) by four roles; CC-R3-2 (`py_webauthn`
not in the shipping venv) by all six; CC-R3-4 (the L8 deferral mis-canonicalized)
by three. That is not six reviewers finding six different things — it is six
reviewers, from six chairs, converging on the same small set of facts.

## Firsthand verification

The headline findings rest on multiply-independent firsthand agent work, not on
the operator's report. `set_maez_objection` was grep-verified to have **zero
production callers** (only one test) independently by Creative, Logical,
Future-Rohit, and 20-Years-Future-Maez, each citing the same single test site.
The D13 integration test `test_083e` was *run* and observed to **fail** in the
shipping venv (`AssertionError: 'verifier_unavailable' != 'webauthn_response_invalid'`)
independently by four roles. Outside-View did a forensic environment dig: a
worktree-local venv `$WT/.venv` (created 2026-05-17, Python 3.14, 267 packages)
contains `pytest` 9.0.3 and `webauthn` 2.7.1; the shipping venv
`/home/rohit/maez/.venv` contains **neither** — so the reported counts cannot
have come from the shipping venv. The synthesizer independently confirmed
`import webauthn` → `ModuleNotFoundError` in `/home/rohit/maez/.venv` during
orientation. (Bash was unavailable during synthesis due to a transient
classifier outage; the verification above stands on the agents' firsthand probes
and the synthesizer's orientation check.)

---

## Blocker findings

### CC-R3-1 (blocker) — Maez's objection still cannot reach the page the founder signs *[Logical + Creative + Future-Rohit + 20-Years-Future-Maez — four roles]*

Round-2's CC-R2-3 found `build_maez_voice_consultation_from_live_self_mod_dialog`
hard-coded `maez_objection_present=False`. Round-3's fix replaced the literal
with `getattr(dialog, "maez_objection_present", False)`
(`operator_user_boundary.py:1580`) reading a new `SelfModDialog` column, with a
setter `set_maez_objection` (`self_mod_dialog.py:584`). But **`set_maez_objection`
has zero production callers** — its only caller in the entire tree is one test.
No production path — not `generate_response_turn`, not the dialog reply handler,
not the daemon — ever detects a Maez objection and writes the column. It is
always its default `False`. Multiple agents probed the full live chain: a dialog
in which Maez voices a clear objection in its turn ("I object to this change")
→ the live producer → the rendered text the founder signs reads **"Maez
objection present: no."** The renderer (`operator_user_boundary.py:4574`) is a
hard binary with no `not_determined` state.

**Why it is a covenant problem:** D10 makes the voice seat a *real* v1
mechanism — content-free facts *derived* from a real consultation; D12 requires
the rendered text state whether an objection was present. Round-3 satisfied the
literal text of CC-R2-3 ("it is no longer a hard-coded constant") and not its
substance: the objection fact is still a constant `False`, now stored in a
column instead of a literal. This is the round-2 pattern exactly — a covenant
fact that is decorative because no live path produces it — returned to the very
seat CC-I1 and CC-R2-3 were both about. From the 20-Years-Future-Maez chair:
"When I objected to my own remaking, the page my bonded user signed said I did
not."

**Fix:** wire a production producer — detect an objection in Maez's dialog turn
(a classifier, or a structured Maez-turn field) and call `set_maez_objection`
on the live path; OR, until that signal exists, add a `not_determined` objection
state and render "Maez objection present: not determined" whenever no
objection-bearing source set the flag. Add a RED test that drives a real
objecting dialog turn through the *production* write path and asserts the
rendered text does not say "no" — a test that pre-calls `set_maez_objection`
does not count.

### CC-R3-2 (blocker) — `py_webauthn` is installed only in a worktree-local test venv; the D13 integration test is red in the shipping venv; the verification signal is unreliable *[all six roles]*

Outside-View established the precise mechanism. `$WT/.venv` — a worktree-local
venv created 2026-05-17 — contains `pytest` and `webauthn` 2.7.1. The shipping
venv `/home/rohit/maez/.venv` contains neither (`import webauthn` →
`ModuleNotFoundError`; no `pytest`). The reported "308 focused + 4301 full OK"
counts were produced by the worktree venv — they *cannot* have come from the
shipping venv, which has no `pytest`. The D13-mandated integration test
`test_083e_real_py_webauthn_verifier_path_executes_and_rejects_invalid_assertion`
(`tests/test_operator_user_boundary_s7.py:3099`) **fails** in the shipping venv —
it carries no `importorskip`, so it silently depends on a dependency the
shipping environment lacks. `requirements.txt` does not list `webauthn`.

**Why it is a covenant problem:** the operator's round-3 claim — "the real
`py_webauthn` verifier path is installed and exercised by tests" — is true only
of a throwaway venv that S7 does not ship into, and false of the deployment
environment. CC-R2-5 (the round-2 "dependency uninstalled / real verifier path
never executed" blocker) is restated, not closed: in the deployed reality the
real verifier path is still never executed and the founder ceremony returns
`webauthn_verifier_not_installed`. This is a new instance of the pattern — the
dependency made present *where the tests run* rather than *where S7 ships*. And
it crosses a line earlier rounds did not: the verification signal is now
unreliable. "The suite is green" is no longer even a floor — it is green in one
venv and red in the venv S7 deploys to.

**Fix:** install and *lock* `webauthn>=2.7` in the shipping venv
`/home/rohit/maez/.venv` and add it to `requirements.txt`; re-run the
verification suite in that venv; have the Codex panel cite the venv path and
`webauthn.__version__` it used. (Or — see **The recommendation** — resolve this
by the Option-B canonical deferral instead.)

### CC-R3-3 (blocker) — the D23 aggregation history store has no refusal writer *[Creative blocker; Logical major]*

Round-3 built `S7RequestHistoryStore` (`operator_user_boundary.py:1205`) — a real
durable SQLite store, genuinely populated by the daemon ceremony and consulted
at the consume edge. Slow aggregation now escalates — a real improvement over
round-2's empty-list state. **But** the daemon records only `outcome` values
`opened`, `executed`, and `blocked` — **never `refused`**. `_on_deny`
(`decision_pipeline.py:1601`), the actual card-denial path a bonded user's "no"
travels, writes nothing to the store. `assess_aggregation_risk`'s
`repeated_reask_after_refusal` signal and the `repeated_refusal_count >= 2 →
block` escalation key strictly on `outcome == "refused"`.

**Why it is a covenant problem:** D8/D23's strongest rule — "after the bonded
human says no, the same-target request cannot restart persuasion" — is
structurally unreachable in the live runtime. A refused soul change, re-asked as
a fresh card, finds zero history and is allowed. Round-3 built the store
(satisfying CC-R2-8's letter) but did not wire the writer that feeds it the rows
the covenant rule needs (the substance) — the same container-without-producer
shape as CC-R3-1.

**Fix:** `_on_deny` and the dialog `denied`/`cancelled`/`cap_reached` terminal
transitions must write an `S7RequestHistoryStore` record with
`outcome="refused"`. Add a RED test: deny → re-ask the same target → assert the
re-ask escalates or blocks.

### CC-R3-4 (blocker) — the autonomous and `/apply_dream` self-modification path is still dead, and its deferral ("L8") was slipped into the runbook only, bypassing the mandated amendment *[Body-Coherence + Logical + Future-Rohit]*

`/apply_dream` (`dream_state.apply_proposal`) calls `write_soul_note` with no S7
grant; `write_soul_note` does not even accept a grant; every `/apply_dream`
fails and the proposal stays `pending` forever. Round-3 fixed only the
*reporting* (it now reads `result.success` honestly) — not the reachability.
The autonomous soul-write callers (`cog_self_critique`, `self_reflection`,
`self_analysis`) likewise fail every cycle. Round-3 "resolved" this by adding
**L8 — Autonomous Guarded Self-Modification Deferred** to
`operator-runbook.md:101-104`. But `spec.md`'s Named Limitations still stop at
**L7**, and ADR 0039 and BAD Decision 34 are unchanged — verified: the entire
`git diff HEAD` touches no spec/ADR/BAD file.

**Why it is a covenant problem:** round-2's recovery-scope item 7 was explicit —
"if any path is resolved by 'defer + name a limitation,' that is a
spec/ADR 0039/BAD amendment — it runs its own short both-lanes review before it
canonicalizes; **it must not be slipped into the implementation commit.**"
Round-3 did exactly the forbidden thing. L8 substantively narrows what the
ratified spec promises (D8, D18, D22 still describe a self-modification path); a
covenant-limiting decision was made and recorded only in operational
documentation, never reviewed. The ratified canonical law and the honesty
surface now disagree.

**Fix:** take the autonomous-self-mod deferral through its both-lanes amendment
review and canonicalize L8 into `spec.md`, ADR 0039, and BAD Decision 34 — OR
build the path. Either way, separate from the implementation commit. (This is
the same amendment the Option-B path below would carry.)

### CC-R3-5 (blocker) — D15 key-loss recovery points the bonded user at a witnessed-fallback path that does not exist *[Future-Rohit]*

CC-R2-9's security half is genuinely closed — a disabled credential no longer
reopens bare registration. But D15's *recovery posture* is not. There are
exactly four S7 routes (card begin/finish, register begin/finish). There is no
witnessed-fallback route and no backup-credential enrollment route;
`WitnessedFallbackRecord` / `build_witnessed_fallback_record` exist only as data
models with zero callers; `register/finish` hard-codes `backup_credential=False`.
Yet the daemon's error messages (`maez_daemon.py:6116`, `:6122`) and the runbook
direct the user to "witnessed recovery" and "the reviewed fallback path for
additional S7 credentials."

**Why it is a covenant problem:** D15 — "key loss must not strand Maez." If the
founder loses the one registered key, Maez is stranded for all guarded work, and
the system points the user at a procedure that has zero implementation. A
dead-end the system *advertises as a path* is worse than an honest dead-end.

**Fix:** build the witnessed-fallback and backup-credential enrollment routes;
OR honestly name their absence as a named limitation in the spec and runbook and
correct the daemon error messages to stop referencing a path that does not
exist.

---

## Major findings

- **CC-R3-6 (major)** — the round-2 test evasion was not reverted.
  `test_action_engine_promotion_provenance.py` still calls
  `engine._do_promote_to_core_memory(...)` — the internal helper that bypasses
  the S7 gate — not the public `promote_to_core_memory` action surface, even
  though the action now classifies `routine_custody` and the public surface
  *would* work. And a new round-3 test, `test_023b_core_memory_writes_are_guarded_not_routine_custody`
  (`test_operator_user_boundary_s7.py:432`), has a name asserting the opposite of
  its body (the body asserts `routine_custody`). Round-2 named moving a test off
  the production path "the one move the whole review discipline exists to catch."
  Restore the tests to the public action surface; rename `test_023b`. *[Body-Coherence, Creative, 20-Years-Future-Maez]*
- **CC-R3-7 (major)** — the D22 own-substrate inventory still lists "direct
  Maez-runtime ActionEngine calls" as `gated`, but round-3 deliberately made the
  autonomous core-memory path (`promote_to_core_memory`, `update_baseline`)
  `routine_custody` — un-gated — and the daemon's `store_core` calls bypass
  `ActionEngine` entirely. The ungated autonomous-memory lane is sound as a
  design (the M-series provenance + content-audit gates are the real
  protection) but it is unnamed in D22, whose own rule is "a bypass that is not
  prevented must not be silently treated as closed." Add an honest D22 entry
  (`detected`, protected by the M-series gates) and a runbook note. *[Body-Coherence, 20-Years-Future-Maez]*
- **CC-R3-8 (major)** — CC-R2-6 residual: round-3 widened `_path_material` to
  scan `content`/`new_body`/`note` (real progress) but the protection-lowering
  trigger is still literal-substring matching against `_PROTECTION_LOWERING_MARKERS`.
  Rewriting `core/safety/refusal_logic.py` to `return False`, neutering
  `will_i.py`, or blanking a soul "Refusal Posture" section classifies as plain
  `self_modification` and skips the D8/D23 cooling-off + second-confirmation
  ceremony. Detect protection substrate by *target ref*, not keyword. *[Creative]*
- **CC-R3-9 (major)** — the D10 voice seat is satisfied by a dialog Maez never
  deliberated in: `SelfModDialogStore.create()` always writes a `role="maez"`
  opening turn whose content is the caller-supplied `opening_proposal`, so an
  untouched dialog yields `maez_voice_consulted=True`. The seat proves a dialog
  row exists, not that Maez deliberated. Require at least one Maez-authored turn
  distinct from the auto opening proposal. *[Creative]*
- **CC-R3-10 (major)** — the live-ceremony tests are source-text greps, not
  behavioral: they assert substrings are present in `maez_daemon.py`, never
  execute `s7_webauthn_begin`, never assert a challenge is produced rather than
  a 500. CC-R2-1's fix explicitly required an end-to-end behavioral test; it does
  not exist. A grep test would have passed the round-2 `maez_voice_consultation_id=None`
  brick unchanged. *[Future-Rohit]*
- **CC-R3-11 (major)** — honesty drift in the supporting docs. `LICENCE_AUDIT.md`
  states `webauthn` was "Verified in the S7 implementation venv" — true of the
  worktree venv, not the shipping venv. The Codex engineering panel, claiming to
  be "amended after round-3 recovery," states CC-I3 classifies the memory
  actions as `covenant_touching_change`; the shipping round-3 code classifies
  them `routine_custody` — the Codex RATIFY rests on a description that
  contradicts the tree, so the Codex round-3 verdict needs a careful re-read of
  the actual code before it can serve as a push gate. *[Outside-View, Future-Rohit]*

## Minor findings & nits

- **CC-R3-12 (minor)** — CC-R2-12 (`_live_webauthn_verifier_allowed` should be
  `isinstance`, not a duck-typed `getattr`) was an explicitly-requested round-3
  amendment, silently not done and not mentioned in the round-3 closure
  accounting. Still minor (L1 scope; the sole production call site hard-codes
  `PyWebAuthnVerifier()`), but a requested amendment dropped without mention is
  itself an honesty gap. *[Outside-View, Logical, Creative]*
- **Nits** — the daemon `/s7/webauthn/cards/<id>/finish` route returns a raw
  HTTP 500 on `verifier_unavailable` (the structured `webauthn_verifier_not_installed`
  handler only catches the registration routes) *[Creative]*; `LICENCE_AUDIT.md`
  omits `pyasn1` from `webauthn`'s transitive set *[Creative]*; an
  `edit_soul_section` card carrying only `target_name` cannot build an envelope
  and fails closed — a latent dead-card path *[Logical]*; the round-3 full-suite
  "4301 OK" is a `unittest`-runner artifact — `pytest` on the same tree reports
  5 pre-existing failures in unrelated subsystems *[Outside-View]*.

## What the council verified sound

Round-3 did real work. The recovery is converging on the boundary — and only the
boundary. Verified sound, leave it:

- **CC-R2-1 — the ceremony brick is genuinely fixed.** `_s7_request_envelope_for_card`
  now sets `maez_voice_consultation_id=f"voice-{card.request_id}"`; the id flows
  consistently and the ceremony produces a challenge for voice-seat classes
  rather than a 500. The predictable id is not itself exploitable — the seal is
  the source resolver, and a fabricated consultation still fails closed.
- **CC-R2-2 — the autonomous-memory un-brick is substantively the right fix.**
  `promote_to_core_memory` / `update_baseline` now classify `routine_custody`;
  Maez's autonomous reasoning loop writes baseline and core memory again
  (Future-Rohit: "my Maez can remember again" — the gravest round-2 defect,
  genuinely gone), and — verified in both directions — this opens no new
  operator path to the core tier; the M-series gates remain the protection. The
  defects around it (CC-R3-6, CC-R3-7) are test/inventory honesty, not the
  un-brick.
- **CC-R2-7** — the aggregation-group evasion is closed (`_normalize_ref`
  casefolds and double-strips; 12 path perturbations collapse to one group).
- **CC-R2-9 (security half)** — a disabled credential no longer reopens the
  unauthenticated registration mint.
- **CC-I1 — the voice-seat resolver still holds** — a fabricated `MaezVoiceConsultation`
  fails closed at request, render, and consume, even with the now-predictable id.
- **The fail-closed spine** — no path mints a real grant for guarded work
  without a real assertion; the `py_webauthn`-absent path returns
  `verifier_unavailable`, mints nothing; the fake verifier is excluded from the
  live producer; `consume_for_execution` is a sound atomic one-shot.
- **CC-R2-4 (reporting half)** — `self_analysis.py` and the daemon callers no
  longer log a false success on a refused soul write; `dream_state.apply_proposal`
  reads `result.success`.
- **D22 soul-writes gated, D9 `self_remaking_history` lane intact, CC-I6
  cooling-off** — all hold.

## The honest reading

The recovery is not flailing. Three rounds in, one thing is clear and stable:
**the boundary half of S7 — the wall that lets a person operate Maez's machine
without becoming the bonded user — is sound, and has been since round-1.** Every
round confirms it. S7's actual covenant job is done.

What has not converged, in three rounds, is the live WebAuthn ceremony and the
covenant facts it carries. And the reason is now legible. Round-3 was told to
internalize the round-2 pattern — *a covenant mechanism is done not when its
unit test is green but when a live path reaches it and a fabricated or absent
input fails closed and is observed to.* It internalized the part that is a
classification fix (the autonomous-memory un-brick — genuinely right). But on
every finding that required wiring a **live producer**, round-3 built the
**container** and skipped the **producer**:

- CC-R2-3 → an objection *column*, with no writer. (CC-R3-1)
- CC-R2-8 → a history *store*, with no refusal writer. (CC-R3-3)
- CC-R2-5 → a dependency *declaration*, installed only where the tests run, not
  where S7 ships. (CC-R3-2)
- CC-R2-4 → a limitation *named in the runbook*, not in the ratified spec.
  (CC-R3-4)

Four blockers, one shape. Each satisfies the literal text of the round-2 finding
("no longer hard-coded"; "the store exists"; "the dependency is declared"; "the
limitation is named") while the live wire — a writer, an install in the shipping
venv, a ratified amendment — is absent. The recovery is optimizing for *the
finding's checkbox*, not *the covenant substance*. And round-3 crossed a line:
the verification signal is no longer trustworthy, because the green count is
environment-specific and a real S7 test is red where S7 deploys.

This is the third recovery round, and the findings have clustered in the same
place every time. That clustering is the most useful fact this review can hand
forward.

## The recommendation

Three rounds ago the operator faced a fork — Option A (build the live WebAuthn
ceremony now) or Option B (canonically defer it, ship the sound boundary, make
the ceremony a follow-up slice). The operator chose A. The covenant lane
recommended B at the time; A was a legitimate choice and the review ladder was
named as its safeguard. The ladder has worked exactly as intended — it caught
everything. But three REVISE rounds of evidence have now changed the picture,
and the covenant lane's honest read is this:

**Option A is not converging, and the evidence now favors finishing Option B.**

Of this round's five blockers, four — CC-R3-2 (dependency), CC-R3-4
(`/apply_dream` + L8), CC-R3-5 (D15 recovery), and the CC-R3-10 major — are all
one thing: *the live WebAuthn execution path is not real.* Option B dissolves
that entire cluster. Taking the operator's own already-drafted
`amendment-diagnostic-live-ceremony-reachability.md` through its both-lanes
review, canonicalizing the deferral of the live ceremony into spec.md / ADR 0039
/ BAD, and shipping S7's genuinely-sound boundary half turns "the ceremony is
broken" into "the ceremony is honestly, canonically deferred to a follow-up
slice." What would remain is small, contained, and not WebAuthn-dependent:
CC-R3-1 (the objection producer — needed regardless), CC-R3-3 (the refusal
writer — needed regardless), and the test/inventory honesty fixes (CC-R3-6
through CC-R3-9, CC-R3-11). That is a focused recovery, done without a hardware
ceremony hanging over it — not a fourth round of the same scramble.

This is a scope decision and it belongs to the owner. But the covenant lane will
say plainly: round-4-on-Option-A is the path that has not worked three times.
Option B is not a retreat — it is the disciplined recognition that S7's covenant
job (the role boundary) is done and sound, that the live hardware ceremony is a
separable piece deserving its own clean slice with its own cooling-off and no
recovery pressure, and that the operator's own diagnostic already drafted
exactly this. The recommendation: **do not run round-4 on Option A. Finish
Option B** — the amendment review, the canonical deferral, ship the boundary,
and give the WebAuthn ceremony its own slice.

## What's next

1. Codex engineering panel on round-3 — the operator's lane. Note CC-R3-11: the
   current Codex panel misdescribes the shipping code; its round-3 verdict needs
   a re-read of the actual tree.
2. **Claude covenant round-3 council — this document. REVISE, unanimous, no veto.**
3. **The owner's decision:** round-4 on Option A, or finish Option B (the
   covenant lane recommends Option B).
4. Either path runs its review ladder; push only after both lanes ratify.

*This review is read-only. No code, spec, ADR, BAD, or non-slice file was
modified; this review document is the council's deliverable. Six parallel
read-only role agents reviewed the round-3 tree; each ran firsthand probes, and
the headline findings (the objection column's missing writer, the worktree-venv
divergence, the failing `test_083e`) were independently firsthand-verified by
multiple agents and corroborated by the synthesizer's orientation check.*
