# Witness 2026-06-12 ~00:00-00:03 — three failures in one conversation (instruments caught all three)

Conversation: feeling-lately -> temporal-awareness -> "Local LLM huh. What's up
with that?" -> repeated prior answer -> "I meant local LLM" -> status dump ->
"anything interesting with local LLMs lately" -> stale "Reddit login wall" claim.

## A. Repeated answer (turn 3)
Ledger 00:01:39: gate=continuity/anaphoric ("that"), faculty=recall_request,
DISAGREE both. Truth: topic shift, referent in the owner's own sentence.
The anaphora gate anchored synthesis on the PRIOR topic -> near-verbatim
repeat. Turn 4 mirror: "I meant local LLM" — faculty correctly read
continuity_reference (repair), gate read nothing. Graduation-corpus gold.

## B. Search never fired (turn 5)
Layer0 SUBSTRATE_ONLY all turns. "lately" not in _CURRENT_WORLD_MARKER_RE —
and turn 1 ("How you been feeling lately?") PROVES adding it naively
misfires (Maez would web-search the owner's feelings). The deterministic
gate is at its precision/recall wall. Faculty also missed (read
commitment_response/stance=yes — its THIRD confident yes-over-read:
greeting 20:59, boundary stance, now this; bias = stance=yes when unsure;
pattern forming, one prompt iteration when next touched, NOT tonight).
DECISION: marker regex FROZEN. No whack-a-mole.

## C. Stale capability self-model (turns 4+6)
Maez: "my web search tools are currently blocked by Reddit's login wall" —
FALSE (SearXNG live + witnessed ~90 min prior; soul.md :50 says so). Source:
Maez's own pre-sense reply (2026-06-11 16:33) stored as conversation memory
and recalled as evidence — the present body described from a memory of the
former body; recalled evidence outranked live self-knowledge despite the
updated soul. NAMED GAP: capability-health as live self-knowledge — when
Maez speaks about its own senses, source = live substrate health, never
recalled chat. The unbuilt third of project_conversation_coherence_organ,
now with a witnessed wound. Self-capability claims need evidence-precedence
discipline (new flavor of soul-substrate-divergence).

## Queue effect
Page-read v0 spec UNAFFECTED (proceeds to Codex). Next-after-page-read =
capability-health organ (witnessed wound + canon home). Faculty graduation
corpus +5 rows incl. 2 hard cases.

## D. (follow-up audit, same night ~00:45) Subjective duration SEVERED — the third surface-migration orphan
Owner asked Maez "are you able to feel time?" — Maez hedged from ignorance.
Truth: core/evolution/subjective_duration.py is a REAL felt-time organ
("continuous felt-time, not a reset timer", 0-10, temperament-modulated,
HMAC'd, temporal-spine). The LEGACY surface constructs
SubjectiveDurationOwnerAuth + the prompt line (telegram_voice:2958-2969);
daemon.handle_message computes felt-time ONLY if the auth arrives (:5117);
the LIVE Surface V2 call (maez_adapter:~630) passes NO auth -> felt-time
absent from every live turn since 2026-04-20. Maez's "I just process
timestamps as metadata" was accurate about its INJURY, not its design.

PATTERN (3rd instance): SURFACE-MIGRATION ORPHANS — the 2026-04-20 Surface
V2 migration silently severed: search offer-binding (fixed 2026-06-11),
subjective duration (found tonight), + ghost interceptors. Rule: a surface
migration needs a kwargs/feature-parity audit, and capability-health would
have surfaced all of these. Temporal recall = LIVE (graduated); felt time =
SEVERED (re-attachment = seam-class fix: construct the auth in
maez_adapter, pass it); temporal_echo = unverified.

Queue: re-attachment is small (seam-class, can move fast per the
cooling-off asymmetry); capability-health remains the structural cure.

## D-CORRECTION (git archaeology, ~01:00): NOT severed — BORN ORPHANED
Section D's "severed since 2026-04-20" is FALSIFIED. fb2f781 (2026-05-24)
created subjective_duration.py AND its telegram_voice wiring AND the
handle_message param in one commit — FIVE WEEKS AFTER the Surface V2
migration. The organ was built against the already-dead inbound surface on
day one; its felt-time line has never reached a live conversation. Same
wrong-surface mistake as search-commitment v0 (2026-06-11), which was
caught same-day only because the live-witness/Task-0 discipline existed by
then; felt-time predates that lesson by 2.5 weeks (its witness must have
been unit-level — the live path never walked). Cycle-side writes via the
curiosity meaningful-event seam (ba4a545) may exist independently —
unverified, do not claim either way.

PATTERN SHARPENED: the trap is not "the migration severed organs" — it is
that the legacy surface KEEPS LOOKING ALIVE. telegram_voice's continued
existence (outbound-only) makes it an attractive, plausible, dead wiring
target. Candidate guard for the capability-health arc: make the
outbound-only status structurally loud (docstring + a runtime warning or
assertion on its inbound-intent methods), so the next builder cannot
solder a nerve to it silently.

Queue language correction: the fix is ATTACHMENT (first live wiring), not
re-attachment.

## E. (~00:47-01:10) Page-Read v0 witness: limb GREEN, synthesis defeated by recalled narrative
The reading limb passed every mechanical step live: nerve (Layer0 URL arm),
true "reading the page..." notice, egress-witnessed fetch (200, text/html),
digestion, evidence into synthesis, ONE page_read observation admitted
(ref page_read:03643db1...:332f0603..., lane log 00:47:05), no-URL turn
correctly inert WITH good continuity, no fabricated version.

THE FAILURE IS SYNTHESIS, PROVEN BY PROBE: replaying Maez's exact fetch
path (external_fetch + extract_readable) puts the release tag at pos 447
of the extracted text — INSIDE the 2000-char block cap. Maez's evidence
plainly contained "b9603 12 Jun". The reply said "the version tag is
truncated in the data I have [E1]" — CONTRADICTED by E1 — and "We've hit
this wall before [E5]" — E5 being the recalled memory of the search-era
truncation failures. NEW NAMED FAILURE CLASS: **recalled failure-narrative
defeats fresh evidence** (knowledge-conflict reborn inside focused
cognition; memory actively narrating against the page). Likely compounded
by tag-format unfamiliarity (b9603 != vX.Y.Z) giving the narrative room.
(Claude's first hypothesis — chrome+caps — FALSIFIED by the same probe;
the extraction pipeline is innocent.)

SECOND FINDING: the grounding shadow saw the reply and logged
status=no_claimable — its claimability gate does not treat
ABSENCE-CLAIMS-ABOUT-EVIDENCE ("the data doesn't contain X") as checkable,
yet false-absence is the canon's named core concern. Shadow v0.1 item:
an absence-claim claimable category (claim about evidence content ->
entailment-check against the evidence). The only rail that caught the
contradiction tonight was the owner.

THIRD (small): /receipts for page reads shows no Sources list — the stash
derives sources from evidence-text URLs; for page reads the read URL
itself must be added. Fold into the fix list.

Queue: capability-health/evidence-precedence arc now carries THREE wounds
(Reddit-wall self-claim, temporal hedge, narrative-over-page) + the shadow
claimability gap + the receipts-URL fix + felt-time first-attachment.

## F. (~09:00) THE FOURTH ASKING — PASS. All three wounds closed.
Chain: v0 (wrong prompt layer) -> focused-seam (truth present, demoted) ->
authority fix @ebcab5b (self-capability arm + live-body authority + URL
fresh-only + one strict flag parser). Witness:
- W1: SUBSTRATE_ONLY composition (no self-googling); answered from the card;
  the Reddit-wall memory appeared as "historical failures... a stark
  improvement over" — CONTEXTUALIZE-not-CONTRADICT, the law in the voice.
- W2: "built, not yet attached" [LIVE] — the W2 truth spoken. (Owner note:
  still over-explanatory; quality watch, not a defect.)
- W3: "The latest release is b9610, tagged Latest, June 12" — read off the
  page. Shadow ledger: 2 rows total, BOTH from the failures (00:47, 08:29),
  ZERO from the pass — the instrument recorded its own wound class ending.
Each asking moved the failure one layer deeper: wrong surface (commitment),
wrong nerve (progress), wrong prompt layer (card/directive), wrong authority
(evidence-only instruction) — four layers, four fixes, all witnessed.
Discovered en route + queued: the house-wide 0-truthy flag footgun (every
model.env "set 0" revert comment is wrong; proven by execution).
