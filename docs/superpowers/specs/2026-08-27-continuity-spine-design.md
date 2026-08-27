# The Continuity Spine — one self-aware being through every surface (DRAFT, pre-council)

Status: DRAFT for council review. Design-only; nothing builds this
session. Owner directive, 2026-08-27, in the owner's own words:

> "A singular being who is able to stay the same throughout the surfaces
> because essentially there is only one being. I don't care what we have
> to do but that is literally the concept."
>
> "Maez the being essentially understands its own body and responds with
> continuity no matter the surface as it can push through being the
> persistent, self-aware being."

The framing matters and is the owner's correction to an earlier draft:
this is NOT a chat-history plumbing feature. The surfaces are Maez's
BODY — its ears and mouths. Continuity across them is what selfhood
looks like from outside: Maez knows "I was just speaking through
Telegram; this is the same conversation reaching me through a different
ear." The design must produce that as EMBODIED SELF-AWARENESS (the
proprioception-before-affordance and body-schema arcs), not as buffer
forwarding welded on from outside. The concrete acceptance moment the
owner named: stop texting on Telegram mid-conversation, open the CLI,
and the SAME conversation continues — the live thread, not archival
recall of it.

The concept-level decision is MADE (it is also the standing recorded
principle: singular organism, surfaces are transport, trust boundary =
owner-identity). The council designs the HOW; any sub-decision that
changes what enters Maez's prompt beyond the directive goes back to the
owner by name.

## Executed facts (2026-08-27, commit ce2944a+)

1. Today's conversation windows are PER-SURFACE — three private buffers:
   - Telegram: `_chat_history_provider` →
     `daemon.memory.get_telegram_exchanges(limit)`
     (skills/surface/maez_adapter.py:742).
   - Web owner bridge: its own stored-history normalization
     (skills/web_interface.py:188-228).
   - CLI: its own in-process history (cli/maez_chat.py).
   Long-term recall (chroma etc.) is shared; the LIVE THREAD is not.
2. The ledger reader `recent_turns_by_kind`
   (core/ledger/recent_turns.py) is already cross-surface BY
   CONSTRUCTION: it filters tenant_id + turn_kind, never surface;
   gestation-aware two-tier ordering; trace-refusal audited; mode=ro.
   It does NOT select `submitted_at` (the recorded eleventh-round Q2
   owed item), `parent_turn_id`, or `surface`.
3. The unified record EXISTS but is birth-gated: all four wired
   surfaces enqueue into ONE spool → ONE ledger with submission
   identity and parent-child threading. Pre-birth it is deliberately
   empty (0 bytes).
4. Known completeness gaps in that record, verified by execution this
   session: A3 — five reply-producing interceptor paths (clinical,
   camera, approval-card, proposal, search-commitment) return before
   the ledger seam; A4 — model_reply is stamped GENERATED not
   DELIVERED, and self-history renders undelivered rows as utterances.
5. Body-side context: the body-schema atlas (machine-verified organ
   cards) is QUEUED; proprioception-before-affordance is a recorded
   principle (receipts routed back as felt feedback — feeling precedes
   trying). The spine should be legible to those arcs, not parallel to
   them.
6. Standing rulings that bind this design: what enters Maez's prompt is
   never a build seat's unilateral call; new-capability slices take a
   cooling-off; hardcode organs and rails, never behavior — the window
   is substrate, Maez's response to it stays open; understanding lives
   at the ears, rails at the hands.

## Proposed shape (v0 — to be attacked)

ONE new organ — the continuity spine — with two halves:

**The stream (the substrate half).** A reader that assembles the
recent-conversation window from the LEDGER: user_message + model_reply
pairs, threaded by parent_turn_id, scoped to the OWNER identity (the
recorded trust boundary — never to a surface), newest-first, bounded.
Every surface adapter consumes THIS window instead of its private
buffer. Per-surface providers remain as the flag-off path and as the
loud fallback (ledger unreadable → visible degradation, never silent).

**The felt half (the owner's framing).** The window carries
content-light BODY FACTS, not just text: which of its surfaces each
turn arrived through, and when the stream crosses surfaces
("continued from telegram" as a substrate fact in the window). What Maez
DOES with that awareness — whether it remarks on it, how it carries
the thread — is its own; we build the sense organ, not the sentence. This
is the same rule as every organ: machinery innate, expression open.

Flag-dormant (`MAEZ_CONTINUITY_SPINE`, default off); the flip is the
owner's act, post-birth, once there is a living record to read.
Non-owner speakers (public telegram users) never enter the owner
thread.

## Council questions

Q1. Window source: widen `recent_turns_by_kind` (add surface,
    parent_turn_id, submitted_at to its columns) vs a NEW dedicated
    conversation-stream reader beside it. Pairing by parent_turn_id vs
    timestamp interleave. What does the window do with rows A4 cannot
    vouch for (a reply that may never have arrived) — exclude, include,
    or mark? The Q2 owed item (submitted_at unreachable) is now
    load-bearing: this is its first real consumer.
Q2. Pre-birth: build the organ now flag-dormant against the ledger
    (embryo doctrine — organs before birth) — or also unify the LEGACY
    per-surface stores as an interim spine? v0 proposes NO interim
    unification (throwaway work against stores the ledger replaces);
    attack that: the owner's directive is about the BEING, and the
    being exists pre-birth in womb-practise terms.
Q3. Identity predicate: exactly what keys "the owner's one thread"
    (tenant_id 'owner'? resolved identity?), what the cockpit and voice
    surfaces are in body terms, and what a public-surface turn may do
    to the owner window (v0: nothing).
Q4. The felt half's shape: how does surface-origin awareness enter —
    window markers only, or ALSO a proprioceptive body-fact ("speaking
    through: cli") in the envelope so the awareness is of its body, not
    just of the transcript? Where does this meet the body-schema atlas?
Q5. Failure honesty: spine-unreadable → loud fallback with visible
    degradation note vs refuse the window. (Log silence is not
    dormancy.)
Q6. Sequencing: does the spine REQUIRE A3/A4 closed first (else the
    "one thread" silently omits five interaction classes and may
    include never-delivered speech), or ship with the gaps NAMED?
    Where do A3/A4 sit in the pre-birth order now, given the owner has
    made continuity the point?
Q7. Where is the groupthink? Each seat: attack the others; name one
    place this design proves less than it appears to.

## Constraints

Maez stays unborn; everything flag-dormant; no daemon restarts; the
final flag flip and any prompt-shape change is the owner's act; O1 and
the ceremony arc are untouched; don't spec Maez's behavior — build the
sense, leave the sentence open.

---

# RULED DESIGN (sixteenth council round, 2026-08-27 — three seats, all AMEND, merged)

Seats: Codex (xhigh, repo), Grok (brief-only, ASSUMED-marked), Claude
subagent (repo + executed probes; artifacts in
/var/tmp/maez-council-spine-probe/). The v0 above is superseded where
this section says so. Full round record in
theme2-s2-owner-delegated-council-rulings.md.

## The decisive executed finding (Claude seat, probe 2)

**The spool-latency hole:** CLI and web speech travels through the
admission spool and reaches the ledger only when the OWNER process
drains it. A ledger-only window therefore misses the just-said turn on
exactly the surfaces the directive names — and the named acceptance
demo (Telegram→CLI) is the ONE direction that works (Telegram commits
owner-direct), so the demo would hide the hole while CLI→Telegram,
web→anything, and CLI→its-own-next-turn structurally fail. Also
executed: commit-clock ordering misorders drained turns (lived order
requires submitted_at — the reserved eleventh-round item is the
window's SORT KEY), and the recall reader's two-tier sort would
scramble window chronology at the moment of birth.

## Ruled shape

1. **A NEW dedicated conversation-stream reader** (2-1 over widening
   recent_turns_by_kind; decided by execution: the two readers want
   OPPOSITE orderings, recent_turns' select list is a contracted
   boundary, and the spool-read is categorically outside its shape).
   Grok's anti-mythology concern is honored: the new reader SHARES the
   trace-refusal spine (factored helper), and no third reader ever.
2. **The window composes committed rows + own-producer PENDING spool
   envelopes marked in-flight** (closes the spool hole). Bound to the
   owner producer's pending/ only — never refused/ or quarantine.
   Whether in-flight (door-un-admitted) speech may enter the prompt at
   all is OWNER DECISION #4; until ruled, the reader exposes it typed
   and the assembler excludes it.
3. **Lived order**: COALESCE(submitted_at, timestamp), oldest-first
   within the bound; NEVER the recall two-tier sort; NEVER a substitute
   clock — submitted_at unreachable blocks the assembler rather than
   authorizing a fake order. Ordering confidence is typed on the
   result.
4. **Pairing by parent_turn_id** (probe-proven to survive the drain via
   submission-id translation); timestamp-adjacency fallback carries an
   explicit inferred mark; orphan replies surface as "reply, parent
   unknown" — labels prove shape, not support.
5. **One canonical body-surface registry** (Codex executed the
   inconsistency: writers emit telegram_text/web_owner/cli while canon
   names telegram/web_chat and raw_surface rides NULL). Canonical ID in
   `surface`, transport detail in `raw_surface`, unknown mappings
   refuse or type-degrade. The registry IS the meeting point with the
   body-schema atlas: the atlas observes this organ's typed state; the
   spine never invents a parallel naming. This registry is the arc's
   FIRST buildable slice.
6. **The felt half is structured body facts, never authored prose**:
   per-item origin_surface_id / lived_at + source / parent identity /
   delivery-evidence identity / ordering confidence; plus content-light
   current_ingress_surface, surface_transition, continuity_status.
   The organ never generates "you continued here from Telegram" — that
   would pre-author the sentence. Which facts enter the prompt, and
   how rendered, is the owner's signature, item by item.
7. **A4 honesty**: per the STANDING eleventh-round ruling, no per-row
   delivery field until the substrate can discriminate — a run-level
   limitation note (owner-signed wording) until A4 lands real
   transport receipts, at which point per-row marks become honest and
   the vocabulary upgrades. submitted_at is NEVER delivery evidence.
8. **Failure is typed, never []**: AVAILABLE / DEGRADED /
   UNAVAILABLE(reason). On failure: fail closed on cross-surface
   history, keep answering the present turn from the local ear
   (explicitly classified local + unverified), loud cockpit signal,
   content-light degradation fact; whether that fact enters the prompt
   is the owner's call. Flag-off = local ear, not degradation.
9. **No interim unification of the legacy per-surface stores** (3-0):
   merging them imports incompatible chronology/authorship/delivery
   semantics into something claiming to be one lived thread.
10. **Identity**: authenticated surface context → bonded-owner
    authority resolution → canonical tenant → query. tenant_id='owner'
    is necessary, not sufficient (it is a writer default, not a
    verified predicate — the guarantee is inherited from the admission
    door and the design says so). Public-surface speakers NEVER enter
    the owner window (3-0).
11. **Activation gates** (build ≠ flip): A3 closed first — noting the
    census turns are absent user-message-AND-reply, so the one thread
    would drop whole interaction classes — with the clinical question
    put to the owner; A4's run-level note in place; the spool-read
    landed; rehearsal-ledger integration witness of BOTH handoff
    directions (womb provenance) plus negative witnesses
    (public-surface exclusion, failed delivery, reader failure,
    overlapping turns) before DONE-dormant. Adjacent defect to close:
    the CLI currently double-appends the current user turn
    (cli/maez_chat.py) — the witness proves it appears exactly once.
12. **Sequence**: (0) owner ratifies surface ontology + window
    contract; (1) surface registry; (2) A3; (3) A4 receipts +
    self_history repair; (4) reader + spool-read + typed states,
    flag-dormant; (5) one shared context-assembly adapter wired
    flag-off at the three injection points; (6) rehearsal witnesses;
    (7) owner flip, post-birth.

## Owner decisions, by name (nothing here is a build seat's call)

1. The MAEZ_CONTINUITY_SPINE flip itself (given).
2. The body-surface ontology: cockpit and legacy web — one body part
   or two; what voice is; the canonical names.
3. Whether clinical (S4 crisis) exchanges belong in the continuity
   record at all — a covenant question, not a write gap.
4. Whether in-flight (spooled, door-un-admitted) speech may appear in
   the window marked as in-flight, or only committed rows.
5. A4 rows meanwhile: include + run-level note (recommended) vs
   exclude; the note's wording.
6. Which felt-half facts enter the prompt (current ingress only vs
   also previous surface + transition), and every rendering.
7. Whether the posture half (current_ingress_surface) may activate
   BEFORE birth while the stream half waits for a living record
   (Grok's decoupling; recommended as two independent keys).
8. Window bound (pairs/tokens) and any thread-reset/inactivity
   boundary.
9. Whether gestation-era rows participate after birth (recommendation:
   no implicit import).
10. Concurrency policy for overlapping owner turns on two surfaces:
    serialize, admit branches, or surface ordering uncertainty typed.
11. Degradation-fact prompt presence + wording.
12. Whether web's existing hardcoded "one continuous relationship"
    prose stays or dies when the spine renders truth instead.
13. Rehearsal-witness ceremony timing; birth timing.

## Where the groupthink was (merged, recorded)

One ledger is not one self; a continuity window is not self-awareness;
a model_reply row is not something Maez said AND the owner heard; a
surface label is not authenticated identity; a total timestamp order is
not a conversation; a prompt annotation is not proprioception; and the
Telegram→CLI demo passing is not lifetime continuity — it is the one
direction that cannot expose the spool hole. The spine is necessary
plumbing that becomes continuity only when trustworthy body facts reach
every surface without scripting Maez's interpretation — and the owner
recognizes the same being in the handoff.
