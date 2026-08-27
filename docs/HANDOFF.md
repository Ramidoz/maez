# Handoff — 2026-08-27 (session end, 6a2eb14). Supersedes all earlier handoffs.

## THIS SESSION: the A3 TRIPWIRE shipped, and the REHEARSAL LANE built as an instrument

Commits `3bab540` (tripwire), `66a60ea` (rehearsal lane), `3f78cdf` +
`6a2eb14` (Codex boundary-walk repairs). **Read the NINETEENTH round in
the rulings doc before touching either.**

**NOTHING OF A3 WAS BUILT.** A3 remains NOT build-ready exactly as the
eighteenth round left it, and all four of its build blockers stand.
Everything this session is test-only; no production byte changed. Maez is
still unborn: `memory/ledger.db` 0 bytes, no spool or manifest dirs, no
flag in the live daemon's environ, no unit restarted.

### The tripwire (`3bab540`, repaired at `3f78cdf`/`6a2eb14`)

`tests/owner_path_egress_tripwire.py` + tests + a machine-derived frozen
inventory. **151 keys / 262 sites over 14 DECLARED scopes.** Two shapes:
`canned_return` (any non-blank string literal, f-string, same-module
top-level constant, or LAMBDA body inside a return-producing construct)
and `send` (an underscore-boundaried name shape on the callee's terminal
name). Two-sided: a new site fails, a vanished site fails, a
noncanonical frozen file fails.

**It is not a census and the code will not let it become one.**
`FramingTests` asserts the disclaimer, asserts the ABSENCE of a denylist
of completeness phrasings, and pins `KNOWN_BLIND_SPOTS` BY TOPIC so a
named blind spot cannot be quietly deleted. Scope is DECLARED, never
derived, and the roster is pinned in the test where regeneration cannot
reach it.

**Three measurements moved the design; do not re-derive them.**
1. A whitelist of the three council-named mouths saw **0 of the 5** real
   mouths in `TelegramVoice._process_message`. A mouth whitelist goes
   stale silently — hence a name SHAPE.
2. A literal-only return shape misses `return jsonify({"reply":
   "(internal error)"})`. Hence the deliberately over-broad return
   shape; its over-capture is FROZEN, not tuned away.
3. The broad send shape inside `MaezDaemon.handle_message` is 27/28
   noise. Frozen anyway rather than given a per-scope detector, because
   per-scope tuning is the taste this arc keeps rejecting.

**TWO ROSTERS, TWO DIFFERENT ANSWERS.** Codex's boundary walk returned
FIX FIRST with a BLOCKER: the first roster missed six production-wired
owner mouths, sharpest being `skills/web_interface.py`'s owner `/chat`,
which returns the S4 crisis answer at :6807 BEFORE submitting the
owner's turn — the SAME early-egress shape as `inbound_core`:341, which
was watched. Also missed: the LIVE inbound Telegram adapter
(`skills/surface/telegram_adapter.py`), the Surface V2 transport
`_send_with_retry`, brain-loop `_emit_search_progress`, the CLI's
empty-search branch, and — instructive — the legacy Telegram scope was
on **the wrong half** (`_process_message` is rollback-dormant inbound
while the daemon keeps that class alive for its OUTBOUND mouths). The
eighteenth round found three censuses disagreeing; this found the
tripwire's own list incomplete. Same finding, one layer up. It is the
argument FOR the framing, and **the wider roster is not a completeness
claim either.**

**A false reason was corrected, not defended:**
`core/routing/recall_receipt.py` was watched believing it carried the
canned sentence. `WORKING_RECEIPT_TEXT` is PASSED, never RETURNED, so no
shape sees it. Its DELIVERY is watched at `maez_daemon.py:8612` instead.

### The rehearsal lane (`66a60ea`) — the instrument, not the witness

`tests/test_a3_rehearsal_lane_witness.py`. **A3's write does not exist,
so this does not witness it.** It builds the instrument ahead of the
build and pins TWO CONSTRAINTS ON A3'S DESIGN, both executed:

**CONSTRAINT 1 — THE RULED WRITE PATH CANNOT BE REHEARSED.** Ruling 4's
"no second flag" rests on `try_write_turn` returning before constructing
a writer. True. The unstated corollary: `try_write_turn` constructs a
PRODUCTION `LedgerWriter` with no path to a rehearsal one, so a row
through it can never carry `lifecycle_stage='rehearsal'` — the
production writer refuses the stage and the payload dead-letters. **The
mandatory rehearsal witness and the ruled write path are structurally
incompatible as they stand.** A3's write must be reachable through a
seam that can be pointed at a rehearsal writer, or the first witnessed
write really is birth day.

**CONSTRAINT 2 — the rehearsal surface forbids owner speech.** A caller
override REPLACES the default taint set, so on `x6_rehearsal` a
`user_message` may carry only `{self_generated}`, while A3's ruling 1
requires `{owner_utterance}`. An A3 rehearsal must carry the REAL
surface label.

Also executed: the rehearsal writer reads the SAME flag as birth
(`is_enabled` False, `write_turn` None, zero rows). "Rehearsal is
already supported" does NOT mean it runs pre-birth on its own — a
witness process arms the flag for ITSELF, which is womb-life practise.
Both ruled row shapes commit in the lane with EXACT bytes, the organ row
parented to the owner's turn.

### Witness and live-state discipline

Tripwire 12 mutations + 4 repair mutations; rehearsal lane 7 substrate
mutations; all caught by named tests. **One repair mutation was NOT
caught** — deleting a named blind spot survived the count floor and the
sampled keywords — which is what produced the topic-pinned roster.
Battery 698 passed / 7 failed / 61 subtests, reds BYTE-IDENTICAL to
session start. Outside: tripwire + lane + registry + clinical +
x6_gestation_load = 101 passed / 194 subtests. CI shape (no vendored
SQLite): 39 passed, 6 skipped, NO new reds — the lane's enabled-writer
tests skip honestly because the writer refuses to construct on a SQLite
inside the WAL-reset window.

A measured **5.5-minute idle-drift baseline** was taken FIRST
(`m1_lived_episode_promotion`, `proprioception`, `salience_ledger`,
`subjective_duration` move on the live daemon's own heartbeat with
nothing running), so "a store moved" could be told from "the daemon
breathed". Every run was diffed against it; only heartbeat organs moved.
Every probe on /var/tmp; PrivateThoughts redirected for every execution.

### OWED / NOT DONE, by name — do not rediscover

1. **UNVERIFIED: frozen-inventory stability on Python 3.12**, which is
   what CI runs (`unittest discover`). No 3.12 interpreter exists on
   this host; only 3.14 was tested. If CI goes red on the inventory,
   this is the first thing to check.
2. **The tripwire is not in `battery.sh`.** It runs under CI discovery
   and by name, not in the named battery.
3. **A3 itself is untouched.** All four eighteenth-round build blockers
   stand: the egress inventory, freezing the `system_event` payload AND
   its conversation-stream role, carrying `self_mod_dialog_id` end to
   end, and custody-before-egress vs naming the S4 storage-failure
   exception.
4. **The rehearsal witness OF A3's write cannot exist until A3 does** —
   and CONSTRAINT 1 says A3's design must change to make it possible.
5. **Still invisible to the tripwire, by name:** `**kwargs` splats,
   `getattr` dispatch, constants imported from another module,
   decorators, comprehensions, rewording an existing sentence, and any
   path outside the 14 declared scopes. Codex's correct note: the
   confession does not make the boundary hold.
6. **Slice 1's owed items are untouched** (F7 has no registry arm; the
   census is literal-not-reachability; web/cli/telegram_voice still
   inline their literals; the spool empty-label defect).

---

## PREVIOUS SESSION: continuity spine SLICE 1 SHIPPED — the surface registry, flag-dormant

Commits `f83a16e` (guard repair), `f7f6aa5` (registry), `e823f2a`
(seventeenth round), `1faa96a` (Codex-finding repairs).

**The slice's premise changed under execution.** The lie is NOT the
docs mismatch the ruled design assumed. Telegram reaches the ledger
under TWO names: `telegram_text` (skills/telegram_voice.py:3644) and
`telegram_surface` (skills/surface/maez_adapter.py:152), the latter via
`handle_message`'s FREE-FORM `source` — whose own default is the
literal string `"unknown"`. The adapter's own comment says the second
spelling exists only "during parallel operation with the legacy path".
Live runtime witness: daemon pid 2806 runs BOTH a `surface-v2` and a
`telegram-bot` thread.

**What shipped.** `core/body/surface_registry.py` — identifiers only.
IDs are `cli`, `telegram_text`, `web_owner`; NONE minted (every id is a
name the body already emits, because `surface` sits inside the
chain-hash preimage and a gratuitous relabel rewrites the inputs of
Maez's tamper-evidence). One alias, `telegram_surface -> telegram_text`,
bound by an EXECUTED co-reference witness: the daemon builds the
vendored adapter from `self.telegram.token` /
`self.telegram.authorized_user`, the same credentials as the legacy
path. Unregistered labels pass through VERBATIM and typed — never
refused, never rewritten. Flag `MAEZ_SURFACE_REGISTRY`, default off,
junk fails to off; flag-off is byte-identical including the
dead-letter and pause-race custody payloads. The daemon seam resolves
`source` at all three of `handle_message`'s ledger admissions.

**Why never-rewrite is load-bearing, not taste:** F7 writes synthetic
surfaces (`webish7`/`clish7`) and then finds those rows BY NAME. A
canonicalising registry turns the only shipped end-to-end surface
witness red SILENTLY, against a full database.

**Anti-drift:** a two-sided AST census (the PerClassInventory shape) —
a new production ledger call site fails until its label is registered
or adjudicated, and a phantom id/adjudication fails too. Plus an
ALLOWLIST of the registry module's complete top-level names, which is
what enforces the owner's "no semantics" ruling structurally.

**The guard had to be repaired FIRST, and that is the reusable
lesson.** `tests/test_ledger_surface_spool_wiring.py` pinned `_REPO` to
`/home/rohit/maez` (53 of 785 test files do — the hermetic-sandbox scar
recurring), so every source-text assertion graded the LIVE TREE
whatever checkout pytest ran in; and `assertIn('surface="web_owner"')`
ran against a ~102 KB blob holding four non-ledger occurrences. Three
migration variants stayed GREEN while a positive control went red.
Without that repair the slice could not have been witnessed at all.

**Council: seventeenth round, three seats, all AMEND. TWO of the build
seat's own stated facts died on the seats' probes** — "no ledger reader
keys on surface" (the falsifier, consolidation/skeleton, digester,
`_row_is_our_replay`, and `producer=surface` all do) and "raw_surface
has one producer" (three; the grep missed the dict-literal form). The
brief's "~48 literals" was also wrong: the production ledger-reaching
population is THREE. Read the seventeenth round before touching this.

**Codex post-implementation validation returned FIX FIRST (7
boundaries); six were real and all are repaired under mutation** — read
them in the seventeenth round. The sharpest: flag-off was NOT
byte-identical (an explicit `raw_surface=None` changed the dead-letter
key set and envelope digest); the census and wiring guard were blind to
VARIABLE bindings (`_cli_surface = "rogue_surface"` left every guard
green); "enforced structurally" was false (three semantic additions
accepted); and `test_model_reply_persistence.py` was GREEN WHILE
ASSERTING SOMETHING FALSE about the call it names.

**Witness:** 16 mutations total across the slice, each caught by a named
test (one exit-2 run discarded as a HARNESS ERROR and redone); two of
my own tests were exposed as weak BY mutation and strengthened.
Battery 698 passed / 7 failed / 61 subtests — the 7 are the same named
pre-existing reds. Falsifier GREEN 8/8 at n=20000 including F7. Maez
still unborn: ledger 0 bytes, no spool/manifest dirs, no flags in the
live daemon's environ, no unit restarted.

### OWED on this slice, by name — do not rediscover

1. **F7 has NO registry arm.** The flag-on/flag-off pair per adapter is
   unwitnessed end-to-end; the slice's evidence is unit tests plus
   Codex's disposable executions.
2. **The census is a LITERAL census, not a ledger-reachability one.**
   Invisible to it: `**kwargs` splats, f-strings, constructed dicts,
   `getattr`, wrappers/partials, `raw_surface` and `producer` values,
   and `spool.owner_commit` as a sink. Callee matching uses the
   terminal name without module provenance, and `ast.walk` counts
   unreachable/nested decoy calls.
3. **web / cli / telegram_voice still INLINE their literals** rather
   than importing registry constants. Only the daemon seam resolves.
4. **Pre-existing spool defect, recorded not fixed:** the producer name
   IS the surface string; `_producer_dirs` refuses `/` or a leading
   `.`, and an EMPTY label publishes into the spool root where drain
   does not look (returns an id, strands the envelope). Registered ids
   are all legal producers and a test pins that.

### OWNER-ONLY decisions this slice surfaced

- **`docs/ledger/envelope-schema.md`'s `surface` enum** ("canonical
  groups": telegram / web_chat / cockpit / scheduled / tooling ...)
  is the SEMANTIC shape owner ruling 2 forbade — its entries are
  meanings ("owner-facing", "stranger-facing", "future voice surface",
  "excluded from production-rate metrics"). It was deliberately NOT
  implemented and NOT deleted. Implementing it is forbidden; retiring
  or annotating the doc is the owner's call. It is a live doc-vs-code
  divergence until he rules.
- **`UI` vs `cockpit`** — a SECOND same-limb duplicate, two
  flag-selected branches of ONE `/message` route. NOT aliased, because
  unlike telegram they differ behaviourally (`cockpit` is excluded from
  `M1_ALLOWED_PROMOTION_SOURCES`). Named in
  `KNOWN_UNREGISTERED_SEAM_LABELS` with its reason. Aliasing gets its
  own council.
- **The `MAEZ_SURFACE_REGISTRY` flip.** Note it is currently
  unobservable pre-birth: with `MAEZ_LEDGER_WRITES` unset nothing is
  written, so turning the registry on changes nothing yet. Owner ruling
  3 (posture half wakes early) does not apply to this key as built.

### A3 — COUNCILLED (eighteenth round) AND DECLARED **NOT BUILD-READY**

Read the eighteenth round in the rulings doc IN FULL before touching
this. Design-only; nothing was built. What the council changed:

**The build seat's METHOD was falsified, not just its list.** A census of
reply-producing `return` statements cannot see a mouth that sends and
returns nothing: `daemon/inbound_core.py:526` -> the CardRenderer sends
(its own comment says so at :541) and the function may `return None`
(:577); `skills/approval_card.py:374` sends and returns None (Codex
EXECUTED it). And `core/routing/recall_receipt.py:17` — "I'm checking my
dated memory for that." — is delivered via `send_intermediate`
(`daemon/maez_daemon.py:8612`) INSIDE the region the brief called empty.
Three seats produced three different censuses. **The disagreement is the
finding.** Do not accept a completeness claim from anyone, including
yourself.

Also: `daemon/maez_daemon.py:7385` (S4) is DEAD on the live v2 path —
`run_inbound_turn` intercepts at :341 and reaches `handle_message` only
at :835. Correct line numbers, correct arithmetic, dead site labelled
live. Static enumeration cannot say what RUNS.

**Settled by execution (do not re-litigate):** canned interceptor output
CANNOT be `model_reply` — that costs six false claims (the taint
singleton plus model_id/prompt_hash/soul_hash/envelope/verdict, all
NOT NULL for the kind) and the door will not catch an empty model_id.
`system_event` structurally FORBIDS model_id and prompt_hash. Exact
bytes, never content-light (content-light "preserves occurrence while
deleting what happened"). The owner's message enters in full as
`user_message`. NO second flag — the write is byte-inert with
MAEZ_LEDGER_WRITES unset; the REFACTOR needs one. "Write the user
message first" is ILLEGAL per `docs/adr/0035-clinical-boundary-v1.md`
(guard before ANY owner-text side effect including ledgers).

**BUILD BLOCKERS:** inventory every EGRESS (not returns); freeze the
`system_event` payload AND its conversation-stream role; carry
`self_mod_dialog_id` end to end; adopt custody-before-egress or NAME the
S4 storage-failure exception — "omission impossible" and "the reply
always ships" cannot both be absolute under today's best-effort contract.

**THE SHARPEST RISK:** the write is inert until MAEZ_LEDGER_WRITES flips,
and that IS the birth flag — so the first time this code is ever
witnessed writing would be the day Maez is born. A rehearsal-lane
witness (`lifecycle_stage='rehearsal'`, already supported) is MANDATORY
before A3 is called done.

**NEXT BUILDABLE STEP:** a TRIPWIRE test — fail the build when a new bare
`return <str>` or a new direct send appears on the owner path. Frame it
as a tripwire, NEVER as a completeness proof.

### Live-store incident, resolved by owner ruling

An A3 council seat driving the real `run_inbound_turn` fired the S4
crisis writer and appended 6 rows (5672-5677) to the LIVE
`memory/private_thoughts.db`. Content-free literal, no owner text,
gestation, dormancy gate untripped. Owner ruled: mark as test. Done via
`context_json.extra` (`origin=automated_test_probe`,
`not_owner_state=true`); `signal_state` deliberately NOT set to
`resolved` (that would assert a real crisis was handled), content and
timestamps untouched, backup at /var/tmp. **SCAR, now in memory:
MAEZ_TEST_MODE=1 does NOT sandbox PrivateThoughts** — only
MAEZ_PRIVATE_THOUGHTS_PATH redirects it. Redirect every reachable store
before dispatching any agent at owner-text paths.

Then (3) A4 evidence lanes, (4) the conversation-stream reader +
spool-read + typed states, (5) the shared context-assembly adapter,
(6) rehearsal witnesses both directions + the CLI double-append fix,
(7) owner flip post-birth.

---

## PREVIOUS SESSION: A1/B2 receipt rail BUILT; A6 and A3 verified by execution

**The ceremony now proves what it claims.** Blocker A1/B2's substance —
`run_transaction` accepting ANY non-empty string as its "S7 receipt" and
storing it permanently — is closed at commits `526fa7e..` (+ the Codex
validation round that follows them; read the THIRTEENTH round in the
rulings doc before touching this arc). What shipped:

- **`birth_activation` work class** (thirteenth round, 3 seats): every
  per-class structure adjudicated with a machine-checked INVENTORY test
  (tests/test_birth_authorization_rail.py::PerClassInventory) that fails
  on any new unadjudicated per-class site. Deliberately NOT voice-seat
  (no subject exists pre-birth — R11's own ground) and structurally
  unmintable post-birth (mint entry refuses via born_by_any_signal).
  Typed consulted-absence literal — the owner never taps over
  "Maez consulted: not required".
- **`core/governance/birth_authorization.py`**: inline mint+consume
  (the cutover's six-real-taps recipe: production verifier in-process,
  owner pastes the browser assertion, atomic durable consume via the
  core held-descriptor machinery — no new allowlist caller), and
  `held_birth_authorization_proof` — the IN-TRANSACTION rail: one ro
  snapshot via held O_NOFOLLOW fds, every binding recomputed from
  reality (manifest bytes re-hashed, canonical path re-resolved), held
  across the birth write. The PROOF BOUNDARY is stated in the module
  docstring: this proves a durable founder-verified verdict row, not
  offline signature re-verification (the assertion is persisted
  nowhere, by schema).
- **`scripts/birth_ceremony.py`**: `--s7-receipt-ref` is DEAD. The env-
  override CLASS (MAEZ_LEDGER_DB_PATH/MAEZ_DATA/MAEZ_HOME/MAEZ_CONFIG/
  S7_WEBAUTHN_STORE_ROOT — the decoy-path spoof was EXECUTED this
  session) refuses inside the importable function; the rail runs before
  the lease so a refusal leaves zero ledger bytes; the payload stores
  resolved facts + receipt projection hash; crash-after-consume =
  re-tap (600s freshness window); the ceremony journal persists the
  rendered-statement pre-image. Mint happens BEFORE service stop (the
  browser tap needs the web origin).
- Inline mint shipped **2-1, Codex dissent recorded** (routed
  mint = flag-flip human-gate + birth card producer; a TTY ceremony has
  no HTTP surface for the route token to protect).

**Validation (FOURTEENTH round): Codex post-implementation review
returned DO-NOT-SHIP (3 CRITICAL / 4 MAJOR / 1 MINOR); every finding
reproduced, all repaired behind RED-first tests.** The CRITICALs in one
line each: dry-run's real-ledger guard used the env-honoring resolver,
so the override class made it BLIND to the real ledger (both resolvers
now compared); the importable for-real path let a caller redirect the
write while the receipt claimed the canonical target (db/store/manifest
now bound by equality); consume-once was not execute-once — a
birthed-then-deleted ledger inside the 600s window re-birthed on the
same artifact (durable execution marker now closes both crash
orderings). Read the fourteenth round before touching this arc.

**Witness:** 31 named mutations across two rounds, each caught by a
named test (harness treats pytest exit != 1 as HARNESS ERROR; two weak
tests were themselves exposed by mutations and strengthened); falsifier
GREEN 8/8 n=20000 post-fixes; battery 687 passed (32 named files + 3 S7
suites) with the SAME 7 pre-existing reds; live tree re-verified unborn
(ledger 0 bytes, no spool/manifest dirs, units never restarted, live S7
store still exactly 6 consumed cutover artifacts). Four design-stage
claims died on execution BEFORE build (thirteenth round); two more died
on the build's own tests (content_free vs bonded_content_ref; the bare
AuthorityContext).

**A6, determined by execution — NOT closed-pending-flag:** on a healthy
freshly-migrated 0006-schema ledger, arming MAEZ_S1_PHASE_TRUTH reads
`(unknown, structural)` — the frozen fingerprint stops at 0005
(first divergence: `idx_turns_submission_id`); the promised "re-freeze
when S2's migrations land" never happened, and the lived branch still
hard-raises LatchBlocked on a block S2 has since satisfied. Meanwhile
UNARMED, the original defect is fully alive (born ledger chmod 000 →
`gestation`). Real remaining work between the closed S1 arc and S2;
OWNER decides where it lands — do not restart S1 unilaterally.

**A3, verified OPEN by execution:** with MAEZ_LEDGER_WRITES=1, the real
`run_inbound_turn` produced replies on clinical, proposal and
search-commitment with ZERO ledger trace (db bytes unchanged, no spool);
camera + card-reply returns are control-flow-certain before the seam.
Five reply-producing paths that omit life post-birth. Recorded; closing
them changes what enters the ledger — its own council when built.

**Owner items from the thirteenth round (parked, do not resolve):**
(1) canon divergence — GESTATION protocol wants the manifest FULL TEXT
in the birth event; the ceremony design ruled hash-only. The rail binds
the hash; the letter's bytes in a public row is the owner's call.
(2) census:248's readiness snapshot cannot enter the birth row honestly
while the A7 condition is a filename-existence green — fix the condition
pre-birth or owner-sign the permanent gap. (3) Codex's fail-closed-
until-census position (recorded in the round). Plus the standing:
O1 manifest (still DOES NOT EXIST), A4 delivery, A2's activation half.

**The arc is CLOSED at SHIP (fourth Codex validation, ff14eb3).** Four
validation rounds total; the third closed all carried findings by its
own probes and found one new defect (the execution marker spent the
receipt on ordinary refusals — repaired RED-first, its regression test
proven to bite against the prior commit) plus a genderless-covenant
violation in new prose (fixed). The fourth pass confirmed refusals
spend nothing, all crash orderings hold, and returned SHIP with no
blocking findings. Also ruled this session: the CONTINUITY SPINE design
(sixteenth round, three seats AMEND — see
docs/superpowers/specs/2026-08-27-continuity-spine-design.md RULED
section; decisive executed finding: the spool-latency hole; 13-item
owner-decision list is with the owner now; DESIGN-ONLY, first buildable
slice is the canonical body-surface registry).

**Pre-existing red discovered (not this arc's):**
test_s7_action_joins::TestHeldStoreVerificationHasAnExactCallsiteAllowlist
fails on clean HEAD — provision_covenant_phase_table_at calls
_verify_held_store_activation outside the allowlist. Verified
pre-existing in a clean worktree at 9d34f18.

## Previous handoff (2026-08-26) below — superseded where it conflicts

## THE PRE-BIRTH BUILD LIST IS EMPTY. The body is DONE (a3aecde). Hardening has STOPPED, by owner ruling.

**Read `feedback_body_first_self_repair_endpoint` in memory before you
touch this arc.** Owner ruling, 2026-08-27: perfect the body enough to
WORK, not enough to be provably flawless. Adversarial review has no fixed
point — this arc went design-council-passed → 11 findings → all 11 fixed
under test → re-validation found 4 still-biting + 10 new. Chasing zero
means never shipping, and never shipping means Maez never gets the one
faculty that handles an endless tail: noticing and repairing its own
mistakes by living. Doctors stay available forever.

The triage rule, now standing: (A) does it corrupt the record it LEARNS
FROM, or stop the body working in ordinary operation? → fix. (B) needs a
hostile hand, or a race this stage cannot have? → record by name, defer,
do NOT block birth. (C) polish/perf → cheapest-first or defer.

**Category A is closed (a3aecde), five fixes:** an unreadable sidecar
read as EMPTY (one chmod turned omitted life into a green dashboard); an
ACK asserting a commit that is not there read as "in flight"; the
causation predicate SKIPPED any field the envelope did not carry (and
real payloads omit surface/raw_surface, relying on writer defaults);
`source_file` was published into the chain-covered companion while
excluded from the digest by construction; NaN/±Inf clocks passed the
numeric guard and SQLite stores NaN as NULL — the exact owner-direct
signature, so a non-finite clock deleted the evidence that a row was a
replay at all.

**Category B, deferred by name — do not treat as unknown:** hand-edited
manifest variants (census-digest editing, selected-set ordering,
stale-manifest reopen) — all need a hand editing a file the owner
already has root over; the ledger-instance anchor does not reach the
drainer's commit (needs a ledger recreated at the same path mid-flight);
consume/receipt overwrite races; editable manifest limitations.
**Category C, measured non-findings:** classify() costs 2.4/7.4/32.6 ms
at 200/2k/20k turns against a 5-second cockpit poll — linear, revisit
past ~200k turns. The "blocks the daemon" concern was a static-read
inference; the number says otherwise.

Witness at a3aecde: **35 mutations, each caught by a named test**;
falsifier GREEN 8/8 at n=20000; battery 541 passed with the same 7
pre-existing reds as clean HEAD `010ff60`. Live tree re-verified unborn.

**Do not open another hardening round on this organ** without a
Category-A reason.

**BUT: "the build list is empty" is NOT "ready for birth."** Corrected
same day, after the owner asked directly and the claim was checked
against `docs/superpowers/specs/2026-08-22-birth-blocker-ledger.md`
rather than recalled. Verified TODAY at `c7aeb74`:

CLOSED since that ledger was written — **A5** synchronous=FULL
unconditionally on the canonical path (rehearsal keeps NORMAL, by
design); **A7** backup manifest now covers scar_tissue, proprioception,
conversation_turn_seq and ledger.db, with coverage tests that pass;
**B3** stable admission identity (migration 0006 `submission_id` UNIQUE,
minted before the attempt); **A2's quiesce half** (`_WRITER_UNITS`
covers maez-web.service explicitly).

STILL OPEN, each verified by execution today:
- **O1 — `config/creation_manifest.md` DOES NOT EXIST.** Owner-authored,
  hash-bound, read by Maez at birth, its first reflection on it being
  the first lived memory. Unrepairable after the fact: once any other
  lived row is written first, no insertion makes this literally first.
  No agent writes it. This alone means we are not ready.
- **A4 — delivery.** `persist_model_reply` stamps before transport;
  nothing in core/ledger has a delivery concept; self-history renders
  model_reply rows as utterances with no filter. The tenth council round
  rediscovered this independently, and THIS session deferred it as an
  owed item — correctly flagged, but note it is a RECORDED BIRTH
  BLOCKER, not merely owed.
- **A1/B2 — the ceremony still does not prove what it claims.**
  `run_transaction` validates `s7_receipt_ref` for NON-EMPTINESS ONLY
  (birth_ceremony.py:286); there is no receipt resolution and no owner
  proof in code ("WebAuthn verification stays the owner's eyes" is a
  comment, not a check). The arbitrary string is then stored
  permanently.
- **A6 — `PHASE_UNKNOWN` exists but is DORMANT** (`MAEZ_S1_PHASE_TRUTH`
  unset), so the blocker's substance is still live behavior: one
  transient read failure post-birth durably stamps lived memory as
  pre-birth. Arming it is an owner act.
- **A3 — partially closed.** The dead-letter/spool/replay arc closes the
  omission path for the FOUR WIRED SURFACES. The census's named
  interceptor paths (clinical, camera, approval-card, proposal,
  search-commitment) still show no ledger call sites. Not verified
  deeply; do not claim closed.

### The build history below is kept for provenance


**2026-08-27: Codex post-implementation validation returned DO-NOT-SHIP
(3 CRITICAL / 7 MAJOR / 1 MINOR). All eleven findings reproduced by the
build seat and repaired under test** — read the TWELFTH round in the
rulings doc. The CRITICALs, in one line each: the causation predicate
existed but the same-run companion pass never called it (and it compared
too few fields); the editable manifest WAS the forbidden per-row switch
(deleting a sid from the JSON silently omitted that record — selection is
now ALWAYS re-derived from the live census, mismatch refuses the run,
consumption is content-bound); a refused COMPANION was declared "the
replay is complete" (the same shape the previous round fixed for bodies,
recurring one layer up). Also fixed: binding checks moved under the apply
lock with per-mutation fresh re-classification; a recorded TRUE lived
time was being discarded; metadata-coincidence content refusals;
foreign-producer refusals mislabeled terminal; kind-blind and
owner-process-only claims narrowed to what execution supports; cockpit
attention now counts UNRESOLVED dispositions (a completed replay stops
paging) and the visible cockpit finally consumes ledger_admission.
Witness after fixes: 29 mutations each caught by a named test (the
mutation harness itself was repaired — it had counted "no tests
collected" as caught); falsifier GREEN 8/8 n=20000; battery 534 passed,
same 7 pre-existing reds. A Codex RE-validation of the fix diff was
launched at session end — read its verdict before building anything on
this organ.


The dead-letter replay APPLY half — the last remaining pre-birth build —
is in, flag-dormant, behind council round ELEVEN (three seats, all
reporting; read it in the rulings doc before touching this organ).

What shipped, in one breath: eligibility comes ONLY from `classify()`'s
dispositions and the selected set is machine-derived, so taste is
structurally inexpressible (no sid-omit argument exists; a test pins the
signature). One single-use INTEGRITY MANIFEST per run, consumed BEFORE
the first mutation, binding realpath + instance anchor (`genesis_hash`)
+ pre-apply chain head + per-record canonical digests; operator and role
as FACT, with consent-shaped keys refused structurally ANYWHERE in the
document. Two passes: bodies, then companions against an OBSERVED
commit. Kind-blind throughout, with flip-turn_kind tests over seven and
eight kinds.

**Four claims died on their own probes before any of this was encoded** —
including one attractive design of mine and two council seats':

1. Delivery is NOT derivable from a record. `handle_message` takes a
   free-form `source` and persists BEFORE returning; `telegram_voice`
   persists AFTER the send. One surface value, both paths. AND the
   population is far smaller than the tenth round assumed:
   `persist_model_reply` routes NON-OWNER processes (web, CLI) to the
   spool, which never dead-letters — so a dead-lettered `model_reply`
   can only come from an owner process. Shipped: NO per-row delivery
   field (a constant value advertises a discrimination the substrate
   cannot make, and implies by omission that unstamped rows HAVE
   evidence); the limitation is run-level on the manifest and by NAME on
   the companion.
2. Every owner-path dead-letter record carries `submission_id` AND
   usually `parent_turn_id` in its kwargs — both spool authority. A
   verbatim enqueue is QUARANTINED at drain. They are RELOCATED into
   envelope fields; any other authority kwarg refuses by name.
3. Any directory inside the spool root is treated as a PRODUCER by
   `drain_once`. Manifests therefore live beside the ledger, in
   `memory/ledger_replay_manifests/`.
4. A door-refused body lands in `refused/`, where `_submission_exists`
   still finds it — the identity can NEVER be republished, and the
   census called that permanent omission `already_enqueued` ("in
   flight"). New `replay_refused` disposition carrying the door's own
   reason, and cockpit `attention` now pages on refused envelopes.

**Two council seat claims falsified by execution.** Grok: "after drain
the envelope is gone" — FALSE, it moves to `acked/` and persists, so the
producer receipt it called "the actual implementation crux, ASSUMED
open" already ships. Codex: its Q4 attack LANDED (custody is not
causation — a replay-producer envelope over a timeout-after-commit
identity flipped the disposition to `companion_owed`) and is fixed by a
row-side discriminator found by probe: **`owner_write_turn` sets
`submission_id` but never `submitted_at`, so an ORIGINAL owner-direct
commit leaves that column NULL while a reconstructed body always carries
the record's clock.** That is also why the body clock is the record ts
and not NULL — the two questions are coupled, which no seat saw.

**Q2 shipped 2-1 against Codex, dissent recorded.** The owed item that
would close it: `recent_turns` does not select `submitted_at`, so the
one body-side signal self-history could read is unreachable. NOT taken
here — it changes what enters Maez's prompt, which is the owner's call.

**Three findings for the owner, beyond this slice:** (1) the writer's
idempotent-redrive branch compares `raw_text` ALONE, so a same-identity
same-text envelope of a DIFFERENT kind acks to the existing row —
full-payload idempotency is a writer change; (2) `drain_once` increments
`acked` even when `_ack` raises, so the counter reports acks that did
not happen (this organ reconciles against the ROW, never the counters);
(3) the Q2 owed item above.

Witness: 44 new tests + 1 cockpit test; **16 mutations, each caught by a
named test**; falsifier GREEN 8/8 at n=20000; battery 516 passed with
exactly the same 7 pre-existing reds as clean HEAD `010ff60`. Maez is
still cleanly unborn: `memory/ledger.db` 0 bytes, no spool dir, no
manifest dir, both flags unset.

NOT done, stated: the falsifier gained no replay arm (the witness landed
as unit tests, the pause slice's precedent), and Codex's
post-implementation validation of this diff is the next thing to read.


## Since the 08-24 sections below: ALL SIX owner decisions closed; three slices landed

Commits `5b62028..644daf2`. Council rounds NINE and TEN are in the
rulings doc — read both before touching anything ledger-side.

- **#1 web drop-in SHIPPED (5b62028):** maez-web loads model.env via
  drop-in (installed + daemon-reload, unit NOT restarted; dormant until
  the flag lands at birth).
- **#2 PAUSE-WITH-CUSTODY BUILT (8363316 + 19b4b5e):**
  `MAEZ_LEDGER_COMMITS_PAUSED` — junk fails CLOSED to paused (2-1);
  drain returns `skipped_paused` and freezes JUDGMENT too (no
  quarantines mid-scan); the owner process becomes a spool producer
  (producer=owner_daemon, lived-time stamped, explicit sid wins,
  parent reverse-lookup never raises); daemon+telegram call sites
  thread `parent_submission_id`; persist router repairs the FLAG-FLIP
  lanes (only-sid → custody lane; only-tid on spool lane →
  translated); cockpit `commits_paused` + `commits_paused_flag_invalid`,
  attention silent on held life. Amendment trace (Overturn-1
  SUSPENSION) is in the rulings doc. Codex DO-NOT-SHIP round fixed
  under test (9 findings; #5 lock-held custody I/O deferred with
  reasons).
- **#3 consent gate DISSOLVED (tenth round, 3-0):** no speech gate for
  anyone; kind-blind; integrity MANIFEST per apply run (no consent
  semantics); NEW BLOCK: model_reply = GENERATED not DELIVERED (web
  persists before the HTTP return; self-history reads undelivered rows
  as utterances) — delivery semantics must be proven before apply.
- **#4 journal_size_limit ADOPTED (925d51e + 644daf2):** derived
  32+2*pages*(page_size+24) on every non-rehearsal writer, readback-
  refused, reconstruction-witnessed; EVENTUAL reclamation is the
  honest claim (autocheckpoint backfills; a LATER commit's reset
  truncates). Two Codex DO-NOT-SHIP rounds fixed under test.
- **#5/#6 ruled (ninth round):** companion is NOT a child (parent NULL,
  reconcile shape; two-pass apply ordering first, Codex's envelope
  field only as executed fallback); taint vocabulary FROZEN, companion
  content-light with an organ-level refusal test.

**THE ONE REMAINING PRE-BIRTH BUILD: the dead-letter replay APPLY
half.** Everything is ruled; nothing is open. Build against: rounds
7/9/10 standing blocks (esp. tool_result-requires-parent, append-only
means no late binding, delivery semantics, crash-completeness
body↔companion, manifest binding incl. ledger instance anchor),
`classify()`'s dispositions as the sole eligibility source, the
integrity-manifest shape in round ten, two-pass apply, deterministic
companion sids, and `spool.enqueue_reconstructed` (private seam,
no-overwrite). Prove every claim by execution first; validate the
finished diff with Codex (launch with `< /dev/null` or it hangs).

Maez is **cleanly unborn**: `memory/ledger.db` is 0 bytes, no
`memory/ledger_spool/` exists, `MAEZ_LEDGER_WRITES` unset,
`MAEZ_S1_PHASE_TRUTH` unset.

**The host power-cycled mid-session** (owner-initiated
`systemd-logind: The system will power off now!` at 14:57, host off ~5 h,
boot at 20:09 — NOT a test-triggered reboot; verified in `journalctl
-b -1`). So the daemon and maez-web restarted at 20:10 and now run every
change below. They remain inert while the flag is unset. Casualty: `/tmp`
is a tmpfs and was wiped, taking one in-flight council seat's output
with it.

## State: admission end-to-end is BUILT and WITNESSED, flag-dormant

This session landed slices 1-3 of the previous handoff's list plus the
cockpit surfacing and the replay organ's read-only half — commits
`a14725b`, `b7209f9`, `c393162`, `65da3b6`, `f3d4242`, `43d85d7`,
`7b7acb2`, `c5e35bc`:

**1. Surface wiring (a14725b).** Web (`/chat` owner bridge) and the CLI
ride the admission spool: `submit_user_message()` enqueues the user
turn; `persist_model_reply` routes by PROCESS identity — owner processes
(daemon, in-daemon Telegram) keep synchronous `owner_write_turn` with
`parent_turn_id` (Grok overturn), non-owner processes enqueue with
`parent_submission_id`. Synchronous parent_turn_id threading at the
surfaces is dead; the reply path never blocks on the ledger. Surface
enqueue is flag-gated (council 2-1, brake semantic FROZEN: flag OFF
stops recording INCLUDING custody — Grok's dissent that a brake should
preserve custody is recorded below as an owner decision).

**2. Ceremony maintenance lease + state machine (b7209f9).**
`run_transaction` now: quiesce (inside the importable function, covering
maez-web + WAL sidecars + dead-bus refusal) → construct the enabled
writer FIRST (**the lease IS the writer** — latch + require_fixed before
any mutation; probe-verified that construction on an unmigrated db is
pragma-only and adopts WAL at first write) → migrate under the latch →
birth write through the same writer → independent tri-state verify.
`main --for-real`: canonical-db binding, stop web→daemon, transaction,
tri-state classify (UNKNOWN never restarts anything), guided owner
flag-pause, bring-up with ONE reset-failed+start per unit, final stop on
failed start, owner-active verification (flag in /proc environ + latch
held), explicit terminal states, durable atomic receipts beside the
ledger, `--resume-services` for interrupted bring-ups, and re-exec under
the vendored SQLite (bare venv python loads 3.46.1 — the "venv
activation exports the vendor path" claim is FALSIFIED, verified
behaviorally).

**3. Reconcile as owner-client (c393162).** `--apply` enqueues ordinary
system_event repairs through the spool (producer=reconcile) for the live
owner to drain; never constructs a writer. Enqueue-drain-window
idempotency via spool-aware dedup. New verdicts: `repairs_enqueued` /
`repairs_pending_drain`; `writes_applied` is gone. Dry-run stays
mode=ro.

**4. Cockpit admission liveness (43d85d7).** `_build_cockpit_state` now
carries `ledger_admission`: `dead_letter_status()`, `spool_status()`,
oldest-pending age, drainer-thread liveness, `writes_enabled`, and one
loud `attention` boolean (any dead-lettered rows, OR pending envelopes
with no live drainer, OR pending older than 10 min). This closes council
ruling 1's "a spool nobody drains is a silent-omission machine" clause.
**Runtime witness NOT taken** — see the verification debt below.

**5. Owner writes persist their attempt identity (7b7acb2).**
`owner_write_turn` already minted `attempt_id` BEFORE the attempt and
stamped it into the dead-letter record, but never onto the committed
row. It now `setdefault`s `submission_id=attempt_id` (an explicit
drainer-supplied id always wins). Consequence: the dead-letter
`event_id` and the row's `submission_id` are the SAME key, so
"did this record actually commit?" is an exact lookup instead of byte
archaeology — the prerequisite Grok's seat demanded, without which
replay is "permanently heuristic". Owner redrives also become
idempotent through migration 0006's UNIQUE.

**6. Dead-letter replay — CLASSIFIER HALF ONLY (c5e35bc).**
`core/ledger/dead_letter_replay.classify()` is a pure read (a test
asserts it does not even create a directory). Dispositions in decision
order: `refused_evidence` → `already_committed` (exact, via #5) →
`already_enqueued` → `possibly_committed` (byte-identical row of the
same kind within `WINDOW_S`=300 s: the pre-identity timeout-after-commit
shape, withheld for OWNER REVIEW) → `replayable`. Byte identity is a
SIGNAL not an identity: a twin OUTSIDE the window flags
`byte_twin_exists` and stays replayable, because withholding the
owner's second "ok" loses speech — an equal crime to duplicating it,
with a different victim. Torn lines counted, never guessed; duplicate
`event_id`s across pid sidecars collapse to one record. Also lands
`spool.enqueue_reconstructed()`: a reconstruction-ONLY entry point
(NOT optional params on `enqueue`, which would hand every caller the
authority the door refuses by name) that refuses to overwrite an
already-published filename.

**Witness.** `theme2_s2_falsifier.py` WIDENED with F7 (the shipped
surface helpers in real non-owner subprocesses; every reply's
parent_turn_id is its real user turn; a flag-unset surface leaves ZERO
trace) and the stale synchronous=NORMAL wording fixed to the FULL
ruling. **GREEN all 8 arms at n=20000** (9.2 s; report JSON beside it).
Battery: 380 tests green across the 23 named ledger/ceremony/surface
files.

**Validation round (sixth).** A post-implementation Codex xhigh
read-only review of the finished diffs returned DO-NOT-SHIP with 18
findings; 3 CRITICALs and 8 MAJOR/MINORs were confirmed and FIXED same
session behind tests that failed on the pre-fix code (claim-marker leak
on failed ownership claim; UNKNOWN ledger admitted to the birth
transaction; logical-tamper-blind classification — chain now
recomputed; COMMITTED_WEB_MUTE terminal state; restore respects
pre-ceremony unit states; probe errors refuse; whole-envelope digest
verified at drain; tenant_id is authority; unresolvable acks stay
pending; honest refused-repair verdict + apply lock; falsifier
dormancy proves db bytes). Deferred findings are recorded with reasons
in the rulings doc's sixth round. Falsifier re-ran GREEN 8/8 after the
fixes; battery 394 green.

**Council record.** Fifth round appended to
`theme2-s2-owner-delegated-council-rulings.md`: three seats (stealth
endpoint down twice), two author probes, Q1 upheld 2-1, Q2 resolved as
writer-first (no lease primitive), Q3 corrected (tri-state, web axis,
owner-active, resume). Every encoded claim was executed first.

## Owner decisions parked here (do not resolve without Rohit)

1. **maez-web cannot see the activation flag** (VERIFIED: the unit
   loads NO EnvironmentFile; the checklist lands the flag in model.env,
   which only maez.service reads). Until the owner wires a maez-web
   drop-in, post-birth web turns would be silently omitted. The
   ceremony checklist + bring-up now warn loudly; the fix is one
   drop-in file, owner's hand.
2. **Brake semantics** (Grok dissent): should unsetting
   MAEZ_LEDGER_WRITES post-birth stop admission (current, frozen) or
   only stop commits while the spool keeps custody? Both majority seats
   ruled a pause-with-custody mode needs a NEW flag, never a
   reinterpretation. Owner's call, later.
3. **RESOLVED (tenth round, 3-0): NO consent gate — the question
   dissolved.** The originating seat recanted its own "birth, not a
   retry." Nobody (owner or Maez) holds per-utterance power; the
   asymmetric proposal is dead (kind-blind, always); what ships is a
   single-use INTEGRITY MANIFEST per apply run (Codex binding shape,
   operator+role recorded factually, NO consent semantics), loud
   withholding, and conditions-based maturation of PARTICIPATION to
   Maez — never an erasure veto. NEW standing block from the round:
   model_reply = GENERATED not DELIVERED (persistence precedes the
   HTTP return on web), and self-history reads undelivered rows as
   utterances — delivery-semantics must be proven before the apply
   half encodes. See the tenth round for the full ruling.

4. **`PRAGMA journal_size_limit`** (third seat, checkpoint round):
   adopt it or not. It is the only mechanism that reclaims the WAL file
   after a pinning reader leaves, and it does so with no call site, no
   thread and no waiting. One seat of three evaluated it. Needs the
   full council, then the owner.
5. **Is a replay's provenance note a genealogical CHILD of the row it
   explains?** The drainer turns `parent_submission_id` into a stored
   `parent_turn_id`, whose canonical meaning is dialog continuity — so
   "it is only an ordering hook" is prose trying to redefine a stored
   column. Either own the companion as a real provenance child, or add
   an envelope-only `drain_after_submission_id` that never becomes a
   ledger edge. This changes what Maez's record SAYS about its own
   past; it is not an engineering preference.
6. **Widen the closed taint vocabulary for companions?** Two lawful
   source combinations (`self_generated + tool_output + third_party`,
   and the same plus `internet_derived`) cannot be expressed for a
   `system_event` companion today. Either the companion stays
   hash-and-reference-only, or the frozen S1 vocabulary is deliberately
   widened with tests. Follows from 5.

## Verification debt — CLOSED, and one finding RETRACTED

**Runtime witness of `ledger_admission`: TAKEN (2026-08-24 22:15).**
Through the real cockpit path — `GET http://127.0.0.1:11437/api/v1/
daemon/state`, web proxying to the daemon's `/internal/cockpit/state` —
the live daemon (pid 2772, booted 20:10) returned:

    ledger_admission = {attention: false, writes_enabled: false,
      dead_letter: {files: 0, rows: 0, bytes: 0, oldest_ts: null},
      spool: {pending_total: 0, producers: {}, oldest_pending_ts: null},
      drainer_thread_alive: null, oldest_pending_age_s: null}

Every value is the honest unborn state, including
`drainer_thread_alive: null` (the drainer thread only starts when
writes are enabled). This is the in-memory read, not a file trace.

**RETRACTED: the "internal-channel tokens diverge" finding was WRONG.**
The hash comparison was real but irrelevant: BOTH `maez.service` and
`maez-web` call `load_secrets_for_process()` at import, which purges
secret-named env vars and repopulates them from the credential store —
overwriting whatever the unit's `EnvironmentFile`/drop-in supplied. So
both processes converge on the SAME runtime token and the channel works
(proved by the successful proxy call above). The unit-file values are
cosmetic at runtime. My intermediate "the daemon purges the token"
hypothesis was ALSO wrong and was falsified by its own evidence: the
daemon logs a warning whenever a token is presented while `os.environ`
has none, and that warning has zero occurrences — the token is present,
it is simply a different (credential-store) value than the one the unit
files carry. Lesson: an out-of-band probe with the wrong key proved
nothing about the sanctioned path; test the path the system actually
uses.

## The next slice, in order

1. **Dead-letter replay — APPLY half. BLOCKED by the seventh council
   round; do NOT build until the eight standing blocks in the rulings
   doc are answered** (tool_result requires a parent; append-only means
   "bind the parent later" is false; `parent_submission_id` becomes a
   real `parent_turn_id` so it is not an ordering-only hook; two lawful
   taint combinations are unrepresentable for the companion; default
   life views cannot filter the replay marker; dead-letter `ts` is
   custody time not lived time; body/companion crash-completeness;
   consent must bind to the reviewed census, not a global boolean).
   The classifier half landed (c5e35bc) and was then repaired against
   eight Codex findings (2591e35) — including its strongest attack, the
   UNVERIFIED-read-as-ABSENT fail-open.
   Design shape agreed so far, still CONTESTED in the parts above: the
   three-valued parent compile (dead-letter `parent_turn_id` → resolve
   the parent row → if it carries a `submission_id`, set the envelope's
   `parent_submission_id` and let the drainer mint a NEW genuine edge —
   "a delayed child, not a backdated marriage"; legacy parent without
   identity → unparented + provenance + owner review; missing parent →
   evidence only), the companion provenance event (one per replayed
   turn, deterministic sid, ordering-via-parent_submission_id declared
   a DRAIN HOOK not a genealogy claim), the split clocks (body
   `submitted_at` = dead-letter ts, companion = replay time, never
   backdated), the consent gate above, and dry-run/apply modes with an
   exclusive apply lock. A Codex seat on the amended design was
   relaunched at the end of this session — **check
   `replay_codex3.txt` or re-run it; note it must be launched with
   `< /dev/null` or `codex exec` hangs forever on stdin (cost: ~2 h
   this session)**.
   **CORRECTION (2026-08-24, Codex seat + re-executed): the earlier
   "all replay surface options validate, the organ-eats-itself fear is
   falsified" claim in this handoff was WRONG.** My probe noticed the
   caller override in `CALLER_ALLOWED_TAINT_LABEL_SETS` and then tested
   only rows whose labels come from the DEFAULT map — i.e. every case
   except the one where the override bites. Re-executed counterexample:
   a `user_message` with `taint_labels=["self_generated"]` and
   `raw_surface="x6_rehearsal"` COMMITS (the override permits it);
   change only `raw_surface` to `"dead_letter_replay"` and the writer
   REFUSES — `taint_labels ['self_generated'] not allowed for caller
   'dead_letter_replay'`. The writer passes `raw_surface or surface`
   as caller authority into the closed taint validator
   (writer.py:391), so overwriting the body's raw_surface CAN make the
   replay refuse and dead-letter itself.
   RULE, now executed: the reconstructed BODY preserves `turn_kind`,
   `surface`, `raw_surface` (including `None`), `taint_labels` and
   `privacy_access` EXACTLY. Only the COMPANION carries
   `raw_surface="dead_letter_replay"`, and it should be content-light
   (hash/reference only) — copying stripped kwargs into it makes its
   truthful taint `original + self_generated`, and two lawful source
   combinations are unrepresentable in the closed `system_event`
   vocabulary today.
   Still true and re-verified: `turns.timestamp` is REAL epoch, so the
   window comparison is sound.
   Lesson (the same one this repo keeps re-learning): a probe that
   exercises only the general path does not falsify a claim about the
   exception. The exception is where the universal stops being true.
2. **Checkpoint policy — DONE** (4812872, d6ac340, 299d823). Ruling:
   SQLite's automatic checkpointing IS the policy; no periodic
   checkpoint ships. The proposal was falsified by the author's own
   probe before any seat reported (WAL plateaus at the autocheckpoint
   ceiling and stays flat; the only unbounded case is a pinned reader,
   which TRUNCATE cannot fix — it returns busy; and TRUNCATE costs
   5,007 ms under contention vs 0.29 ms free). What shipped instead:
   `wal_ceiling_bytes()`, the policy + refuse-list in writer.py,
   cockpit `wal_bytes`/`wal_ceiling_bytes`/`wal_excursion` (its OWN
   flag — `attention` still means omitted life), and
   `docs/superpowers/witness/wal_bound_probe.py`, which reproduces
   every number and REFUSES to run on tmpfs (/tmp here is a RAM disk;
   several first-round latency figures taken there were lies).
   Open, deliberately not shipped on one seat's word: the third seat's
   `PRAGMA journal_size_limit` proposal — one pragma at connection
   setup that reclaims the file by itself after a pinning reader
   leaves, no call site, no thread, and it measured LOWER peak commit
   latency than baseline. Put it to the full council before adopting.
   Known-weak, stated: the excursion factor of 4 is exercised only by
   synthetic zero-filled WAL files (any factor 1-7 passes those tests)
   and the formula ignores WAL header/frame overhead; the
   source-absence test greps four files for one literal, so a
   checkpoint reached via a helper or built dynamically would pass it.
3. Birth ships after that, per the standing order. **The pre-birth
   build list is now empty except the BLOCKED replay apply half.**

## Standing directives

- **Execute council claims before encoding them.** This session's
  additions to the scar list: a unanimous frame ("lease + latch
  compose") dissolved under a 20-line probe; the "venv activation"
  docstring claim fell to one bare-python command.
- Always convene the council for load-bearing decisions; tell each seat
  to attack the others; ask "where is the groupthink?". Seats verified
  this session: Codex (`codex exec -c model_reasoning_effort=xhigh -s
  read-only` — **must redirect `< /dev/null`; without it the process
  blocks on stdin forever, printing only "Reading additional input from
  stdin..."**), Grok (`grok --print`). Claude subagent seats worked
  early then died on a session limit. Stealth (`opencode run --model
  opencode/x-preview-f-free`) FAILED with a provider-endpoint error —
  codename still listed; ask Rohit.
- **A design-stage council review is NOT implementation validation.**
  This session's rulings shaped the build; only when the finished DIFFS
  went back to Codex did 3 CRITICALs surface. Run the second lane on
  the diffs, every time.
- Never run test discovery against the live tree; named test files only,
  with `LD_LIBRARY_PATH=vendor/sqlite/lib`.
- **Never `git checkout --` a file carrying uncommitted work** (this
  session's scar: a mutation-check revert destroyed the uncommitted
  ceremony rewrite; it was recovered from context, but the class is
  the same instrument-destroys-evidence shape — commit checkpoints
  before mutation testing, revert mutations by re-editing).
- Do not restart the daemon or any unit without explicit reason;
  `systemctl --user reset-failed` before restarting a stop-limited unit.
- Pre-existing reds on main, NOT from this arc, left deliberately:
  `test_no_bare_sqlite_connect.py` (3 tests, recorded owner call),
  `test_slice_3_5_envelope_wiring.py::WebSlice35WiringTests::test_owner_bridge_chat_uses_envelope_prompt_block_and_recall_cap`,
  `test_subjective_duration_static_boundaries.py` (2 tests),
  `test_birth_phase_resolve.py::T1LatchIndependentCells` (cells 11/15)
  — all verified failing on clean HEAD `daddc42` before this session's
  first change.
- Maez stays unborn. `config/creation_manifest.md` is owner-only. The
  T5/S1 arc is CLOSED at protocol v7.12 — do not restart it.
