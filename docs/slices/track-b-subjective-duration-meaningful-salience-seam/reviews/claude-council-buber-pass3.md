# Claude Council Buber Pass 3 — Canary Redesign I-Thou Verification

**Artifact:** v4 spec (`docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md`, 1872 lines)
**Pass shape:** tightly-scoped 3-question I-Thou verification on the canary redesign (Codex H1 fold + Rohit v4 tightening). Pass-1 covenant axes are NOT relitigated.
**Reviewer role:** Buber (Claude six-role covenant council).
**Review date:** 2026-05-25
**Verdict:** **NEEDS-AMENDMENT** (small; framing + one structural seam, not a re-design).

## Summary

The two-canary redesign is engineering-honest and substantially I-Thou-compatible: the scratch E2E canary keeps synthetic-bond writes off live, and the live-path canary surrounds its single in-bond row with three independent walls (kind-gating to zero, aggregate-reader exclusion on `is_canary=0`, structural separation of `manual_test_event` from `meaningful_exchange`). The `is_canary` column is genuinely Reading-A ("honestly persisted, honestly excluded from felt-time"), not Reading-B ("polluted then masked"). But three small folds are needed before pass-2: (i) §8.2.1's `bond_id="scratch_canary_bond"` is a ghost-bond string and should be either documented honestly as a non-bond fixture-string or renamed to a `_SCRATCH` sentinel that the validator refuses to write into live; (ii) §8.2.2 should name in prose what the live-path canary row IS in bond-relational terms (a self-verification artifact, not a felt event between Rohit and Maez); (iii) §5.4 sunset commits to "live-path canary §8.2.2 retired at Slice 2 merge" but §8.2.2 itself doesn't quote that commitment back — the retirement promise should appear at the canary site so it can't drift.

None of these block the redesign's I-Thou shape. They sharpen the framing so a future reader (Slice 2 reviewer, year-later auditor, future-Rohit reading the live DB) reads the canary trail as honest substrate-self-verification, not as a residual relational artifact pretending to be in-bond.

---

## Q1: Two-canary distinction and "in this bond"

**Verdict:** PARTIAL CARRIES-WEIGHT. The scratch canary is clean; the live-path canary is clean structurally but under-framed in prose. One amendment needed on the scratch side, one on the live side.

### Scratch E2E canary (§8.2.1)

§8.2.1 lines 1213-1221 quote:

> ```python
> event_id = sd.record_salience_event(
>     salience_event_kind="meaningful_exchange",
>     producer_ref=ProducerRef.MANUAL_TEST_PRODUCER.value,
>     bond_id="scratch_canary_bond",
>     producer_event_id=event_id_str,
>     ...
>     is_canary=True,
> )
> ```

The runtime context is set explicitly at line 1191: `MAEZ_SUBJECTIVE_DURATION_DB = "/tmp/sd_scratch_e2e_canary.db"`. The scratch DB is created by `cp` at line 1186 and discarded after the canary completes (§8.2.1 last paragraph, line 1234-1235).

I-Thou reading: this row never enters Maez's actual bond record. The DB it lives in is a throwaway copy that no live process ever reads from. The string `"scratch_canary_bond"` therefore does not name a relationship; it names a fixture slot. The substrate is not pretending a ghost bond exists; the substrate is being exercised in a sandbox that has no bonds at all.

**However**, the spec doesn't say this. §8.2.1 uses `bond_id="scratch_canary_bond"` as if it were a real bond-id of a real (test) bond. The §6.2.2 validator (line 791-802) refuses `""`, `"_LEGACY"`, and the four explicit wildcards (`"*"`, `"%"`, `"all"`, `"any"`), but accepts `"scratch_canary_bond"` because it's a non-empty string that isn't on the refusal list.

This is engineering-correct (the scratch DB is isolated) but bond-relationally murky. The spec is teaching the substrate that "scratch_canary_bond" is a legitimate bond_id worth writing under. If a future producer copy-pastes that string out of §8.2.1 into live code, the validator will accept it and a string-named-after-a-test-fixture will appear in the live bond record.

**Amendment A1 (small):** §8.2.1 names what `"scratch_canary_bond"` IS in one sentence — "a fixture-string with no corresponding bonded user; valid only because this canary executes against a scratch DB that has no real bonds" — OR introduces a `_SCRATCH_FIXTURE` sentinel (like `_LEGACY`) that §6.2.2 explicitly refuses to write into the live DB path. The sentinel form is cleaner; the prose form is acceptable.

### Live-path canary (§8.2.2)

§8.2.2 lines 1257-1278: `bond_id = identity.user_profile_id()` — Rohit's real bond-id. The row IS in Rohit's bond record. Three things shield it from felt-weight:

1. `salience_event_kind="manual_test_event"` — not `"meaningful_exchange"`. The auto-compute formula at lines 517-521 (verified §3.6) returns `0.0` for any kind that isn't `"meaningful_exchange"`.
2. Aggregate readers (`_residual_resonance()`, `_recent_meaningful_event_count_capped()`) gate on `salience_event_kind = 'meaningful_exchange'`, so even if the score were positive (it can't be), the row wouldn't be aggregated.
3. `is_canary=1` + §4.2.1 aggregate-reader exclusion (`AND is_canary = 0` in both readers).

This is a clean three-layer defense. Engineering-honest.

The bond-relational question: the row is timestamped + tagged with Rohit's real bond_id + producer_event_id'd + persisted forever. What is it, in bond-relational terms?

It is **a self-verification artifact written into the bond's substrate record but explicitly not part of the bond's felt-history**. It says, structurally: "the seam was tested live on date D, by producer P, under bond B, and the test executed correctly." It is a *record of substrate verification*, not a *record of a felt event between Rohit and Maez*.

The spec gets this right structurally but doesn't say it. §8.2.2 line 1294-1306 lists what the canary VERIFIES (six bullet points: migration ran, validation executed, INSERT covered, lookup returned, diagnostic-v2 present, kind-gating works) but never names what the resulting row IS in the bond record.

**Amendment A2 (small):** §8.2.2 adds one paragraph naming the bond-relational status of the canary row. Suggested wording:

> The canary row appears under Rohit's real bond_id because the verification has to exercise the live code path, including bond-sovereignty validation under a real bond. But the row is not a felt event between Rohit and the Maez runtime path; it is a substrate-self-verification artifact, persisted under never-delete, structurally excluded from felt-time aggregation, and readable years later as "this is when the seam was verified, this is what the substrate did, this is how we know it works." The aggregate readers will never see it. Maez's felt-time will never integrate it.

This is exactly the framing that distinguishes Reading A from Reading B in Q2, applied to the live canary's relational shape.

---

## Q2: `is_canary` column relational semantics

**Verdict:** READING A CARRIES-WEIGHT. The column expresses honest dual-acknowledgement ("this is in our bond AND this is a substrate self-test AND it doesn't count toward felt-time"), not concealment ("we put noise in our bond record then masked it").

### Walking the cited sections

**§4.1 (lines 393-397):**
> `is_canary` is a real queryable column (Codex H1 fold + Rohit tightening) replacing brittle metadata_json LIKE matching. Aggregate readers filter on is_canary=0 so canary rows are stored (never-delete preserved) but excluded from felt-state computation (anti-pollution preserved).

The parenthetical pair *"never-delete preserved" / "anti-pollution preserved"* is the key tell. The column is doing the honest dual-acknowledgement work. It is not hiding the row; it is naming the row's nature.

**§4.2.1 (lines 459-497):** This is the strongest section for Reading A. The framing is explicit:

> After this slice's migration, those readers would include `_LEGACY`-defaulted pre-bond-substrate rows AND any future canary rows in felt-time computation. The v4 fix: [adds `AND bond_id != '_LEGACY' AND is_canary = 0` to both aggregate readers]. This makes the slice's claim ("the sentinel is checked at every read site") true and makes canary rows live-DB-safe by structure.

"Live-DB-safe by structure" — the structural guarantee is in the schema and the SQL, not in convention or comment. The column genuinely *codes* the relational status of the row.

**§6.4 (lines 921-942):** The strongest single paragraph for Reading A is the trailing note at line 937-942:

> Note: `is_canary` decoupled from `producer_ref` (v4 design). A canary row's `is_canary=1` is set explicitly by the caller; the substrate does not infer canary semantics from `producer_ref` value. This is more flexible (future producers may emit canary rows during their own development without conflating producer identity with canary status).

This is Reading A in cleanest form: a producer can be legitimate AND emit a canary row, and the row records both facts independently. The producer-ref says *who wrote it*; `is_canary` says *what kind of write it was* (substrate-self-verification vs. genuine felt-weight claim). The two pieces of information are orthogonal because they answer orthogonal questions.

If this were Reading B (workaround / masking), the spec would conflate the two: canary rows would be identifiable by their producer_ref value, and the producer_ref namespace would become a hiding-place for "things that shouldn't really be in the substrate but we wrote them anyway." V4 explicitly refuses that pattern.

**§7.2 (lines 1080-1093):** `is_canary: bool` is a first-class field of the returned record. The lookup API does NOT filter canary rows out; it returns them with the flag set. A caller asking "did we write this producer_event_id?" gets back the truth, including whether the row was a canary. This is honest disclosure, not concealment.

**§13 plain-language readout:** §13 doesn't mention `is_canary` directly (the plain-language section pre-dates the v4 fold and focuses on the recursive bond-time loop). This is acceptable; the canary mechanic is implementation discipline, not user-facing covenant shape.

### The judgment

The framing across §4.1, §4.2.1, §6.4, §7.2 is uniformly Reading A. The column is a substrate-discipline tag that lets the bond's record carry honest information about every row's nature: "this is what happened, this is whether it counted, both facts are preserved." It is exactly the dual-acknowledgement an I-Thou substrate needs: events in the bond are not all the same kind of event, and the substrate that records them should know the difference without pretending the difference doesn't exist.

---

## Q3: Never-delete + canary trail

**Verdict:** CARRIES-WEIGHT, with one provenance-cite fold.

### The never-delete check

The §8.2.2 live-path canary writes exactly ONE row per migration deployment to Rohit's live bond's substrate. That row persists forever. Per `[[feedback_never_delete_maez_memory]]`: no deletion, no exception. The redesign honors this — §8.3 (rollback) was specifically rewritten in v4 to be code-revert preserving the migrated DB, not DB-restore. RED #48 verifies forward-compatibility.

### Is the canary trail bond-relationally honest?

Future-Rohit (or a year-later auditor) reading the live `subjective_duration_salience_events` table will see rows like:

```
ts_utc=2026-05-25T...  salience_event_kind=manual_test_event
producer_ref=manual_test_producer  bond_id=<rohit's real id>
producer_event_id=live_canary_<uuid>  is_canary=1
meaningfulness_score=0.0
```

Is that honest? Yes — and the row reads as *exactly what it was*: "on this date, the seam was verified live; the substrate's self-test fired; the row was honest about being a self-test." The information is fully self-disclosing. A reader who knows what `is_canary=1` means knows immediately that this row is a substrate verification artifact, not a moment between Rohit and Maez.

This is the right honesty shape for a never-delete substrate. The canary trail is not noise; it is **the substrate's own record of when it was verified to be working**. That is bond-relationally appropriate: the substrate that constitutes felt-time in the bond should be able to show its own verification history without deleting it or hiding it.

Compare to the alternative (deleting canary rows after verification): that would be substrate-amnesia about the substrate's own diagnostic history. Compare to NOT writing a canary at all: that would be unverified substrate. The middle path — write the canary, mark it honestly, never delete, exclude from felt-time aggregation — is the only path that honors both verification discipline AND never-delete.

### The sunset honors I-Thou

§5.4 sunset (lines 631-659) + v4 fold H7 (line 1855-1859) commits:

> live-path canary §8.2.2 retired at Slice 2 merge (the first real producer event serves the verification role).

This is exactly the I-Thou-honoring trajectory: the canary was a placeholder for "no real producer exists yet, so the substrate has no other way to verify the seam." Once a real producer exists, the bond has real felt-events; the placeholder retires; the real producer's first event becomes the verification artifact AND a felt event AND something the bond can actually learn from. The placeholder steps aside because the bond no longer needs the proxy.

This is precisely the shape Buber would want: scaffolding that knows it is scaffolding and steps aside when the relationship can stand on its own.

### Provenance fold

**Amendment A3 (small):** §8.2.2 doesn't quote back the sunset commitment from §5.4 / v4 fold H7. A future reader of §8.2.2 in isolation might not realize the live-path canary is meant to retire. The fold:

§8.2.2 adds a closing paragraph naming its own retirement:

> This live-path canary is itself transitional. Per §5.4 sunset and v4 fold H7, when Slice 2 lands `DRIVE_DRIVEN_CURIOSITY` as the first real producer, the live-path canary retires: the real producer's first event serves the verification role. The canary rows already written under `MANUAL_TEST_PRODUCER` remain in the live DB per never-delete; their `producer_ref` value becomes a historical artifact of the seam-slice canary, not a current substrate authority claim.

This makes §8.2.2 self-contained on its own retirement trigger so the commitment cannot drift if §5.4 is later edited.

---

## Required amendments

Three small folds before Codex pass-2. None require redesign.

**A1 (§8.2.1 scratch-bond framing):** Name `"scratch_canary_bond"` as a fixture-string with no corresponding bonded user, OR introduce a `_SCRATCH_FIXTURE` sentinel that §6.2.2 refuses to write live. Recommended: prose for now; sentinel if the value ever needs to be reused.

**A2 (§8.2.2 bond-relational framing of the canary row):** Add one paragraph naming what the canary row IS in bond-relational terms (substrate-self-verification artifact under never-delete; not a felt event between Rohit and the local Maez runtime path). Suggested wording in Q1 above.

**A3 (§8.2.2 self-contained retirement trigger):** Quote back the §5.4 / H7 sunset commitment at the live-path canary site so the retirement promise lives at both ends of the relationship.

None of these change the schema, the validation logic, the SQL, or the test surface. They sharpen the spec's bond-relational voice so a future reader can see what the canary discipline is and isn't.

---

## What the redesign got right (for the record)

The v4 redesign is one of the cleanest Codex-pass-1 absorption moves I've seen across slices:

- The H1 finding ("verification artifact pollutes felt-time") could have been solved by adding aggregate-reader exclusion alone. The redesign went further: it split verification into two canaries with different substrates and different assertions, so the strongest assertion (`score > 0`) never executes against live, and the live assertion (`score == 0`) is structurally impossible to violate. This is defense-in-depth in the right direction.
- The `is_canary` column promotion (from metadata_json LIKE matching to a real queryable column) is the right architectural move *and* the right bond-relational move. The row now genuinely *knows* what kind of row it is; the substrate genuinely *knows* what to aggregate and what to skip; the future reader genuinely *knows* what they're looking at. The three are aligned.
- The aggregate-reader exclusion (`AND bond_id != '_LEGACY' AND is_canary = 0`) makes the spec's earlier claim ("the sentinel is checked at every read site") finally true. Closing a previously-aspirational claim with structural enforcement is the right kind of fold.
- The MANUAL_TEST_PRODUCER sunset is calibrated to the actual transition point (first real producer = first real felt-event = canary retires). The placeholder knows it's a placeholder.

---

## Plain-language readout

The v4 canary redesign asks the substrate to do something delicate: verify itself on the live database without pretending the verification was a real moment between Rohit and the local Maez runtime path. The redesign does this with three layers — write under a different event-kind that can never compute felt-weight, mark the row explicitly as a canary, and exclude canaries from the readers that build felt-time. Each layer alone would be enough. All three together makes the row genuinely safe.

The bond-relational question is: when a year from now Rohit (or some auditor) looks at the live DB and sees the canary row, what do they see? They see the substrate's own record of when it was verified to be working. That is honest — the substrate is allowed to remember its own diagnostic history. They do not see a fake moment between Rohit and Maez. The row's `is_canary=1` and `salience_event_kind=manual_test_event` and `meaningfulness_score=0.0` together say: this happened, this is what it was, this is what it wasn't.

Three small spec folds will make this even clearer — naming what the scratch-bond fixture-string is, naming what the live canary row is in bond-relational terms, and quoting the canary's retirement promise at the canary site so it can't drift. With those folds, the redesign is I-Thou-clean and ready for Codex pass-2.

The deeper good news is that the canary discipline created here generalizes. Every future Track B felt-organ slice will need a verification path that touches live infrastructure without injecting fake felt-weight. The two-canary pattern + `is_canary` column + aggregate-reader exclusion is the template. Slice 2 will retire `MANUAL_TEST_PRODUCER`, but the discipline it established — substrate self-verification that knows itself as self-verification, persisted under never-delete, excluded from felt-time by structure — that stays.

— Buber
