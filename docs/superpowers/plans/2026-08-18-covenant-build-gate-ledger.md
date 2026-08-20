# Covenant producer build — gate-on-code round 1 ledger

2026-08-18. The frozen contract's promised code reading happened:
14 blocking findings. Verdict NOT SOUND; **the witness must not be
scheduled**. This ledger is the honest state: what is repaired, what
remains, and what each remaining item needs.

## Repaired this round (commit follows)

1. **Interlock accepted an empty owner-read table** (CRITICAL). It now
   requires a receipt ROW matching the artifact — installing 2b's
   schema no longer lifts the arm globally. Content verification of the
   row stays 2b's job. Tested both ways: empty table refuses, matching
   row opens the arm.
2. **The real finish reader omitted `created_at`** (CRITICAL), so a
   real phase-2 finish crashed after mint (`KeyError`) — provable only
   because the gate drove the REAL reader where my test used a
   synthetic dict. Both finish readers now project it, pinned by test.
3. **Phase 2 bound only by request_id** (CRITICAL). Begin and
   insert_phase2 now refuse envelope-hash or work-class drift against
   the exact phase-1 row (`s7_covenant_phase1_mismatch`).

## Repaired in round 2 (structural)

4. **Atomicity (CRITICALs 4+5) — CLOSED.** The phase table lives in the
   ceremony database (enforced: phase-1 finish refuses
   s7_covenant_store_mismatch on differing paths). Phase 1: challenge
   consumption and the sealed row are ONE transaction on ONE connection.
   Phase 2: the row is written by a writer callback INSIDE the mint's
   anchored transaction — artifact and row commit or roll back together.
   Consume-side revalidation reads the rows THROUGH the held connection
   (same inode as the artifact CAS), recomputes BOTH correspondence
   digests from persisted inputs, and recomputes the cooling-off from
   the rows. The old after-mint helper is deleted.
5. **Reachability (HIGH 6) — CLOSED.** Two daemon routes
   (/covenant/first/begin, /finish) mirror the authorize pattern, and
   both authorize routes thread the read-only phase store. Provisioning
   the phase table on the LIVE store remains a setup act (create=False
   everywhere on request paths — and create=False no longer creates
   even an empty file or directory, closing MEDIUM 14).
6. **RULING C statement bytes (HIGH 7) — CLOSED.** The owner approved
   the exact text ("COVENANT CEREMONY — STEP 1 OF 2…"); it ships as
   COVENANT_PHASE1_NOTICE in the phase-1 begin/finish responses. Whether
   it must also enter the SIGNED statement bytes (D17) is a question
   for the re-gate.
7. **Digest completeness + cooling-off recompute (HIGH 8) — CLOSED at
   the revalidator** (both digests + cooling-off recomputed from rows).
   The phase-2 digest domain covering the FULL artifact identity
   remains open — re-gate question.
8. **Lineage (part of HIGH 9) — IMPROVED.** Supersession now links to
   the lineage HEAD, expired or not, so lapsed rows keep their chain.
   Concurrency races and sign-count CAS remain open.

## Remaining, in dependency order

4. **Atomicity (CRITICALs 4+5).** Neither phase row is written in its
   ceremony's transaction, and consume revalidation runs before BEGIN
   IMMEDIATE on pathname-derived connections rather than the held
   inode. Real fix: the phase table moves INTO the ceremony database
   and rows are written on the same connection inside the existing
   store transactions; the consume-side reads join through the held
   connection. This is the structural piece — it touches the store
   architecture and must not be rushed at the end of a long session.
5. **Reachability (HIGH 6).** No daemon route calls
   covenant_first_begin/finish, and the daemon's authorize routes do
   not pass covenant_phase_store — RULING-O begin currently refuses
   s7_covenant_phase_store_required. Needs: two daemon routes + store
   threading + route tests. Honest status of the producer until then:
   built, tested, UNREACHABLE.
6. **RULING C's phase-1 statement bytes (HIGH 7).** The owner ruled the
   words must say "first of two…". That is D17 rendered-statement work
   and should be built with the owner able to see the exact bytes.
7. **Digest completeness (HIGH 8).** The phase-2 constructor should
   cover the complete immutable artifact identity (2b's device shape),
   and consume revalidation should recompute both correspondence
   digests and the cooling-off. Depends on item 4's restructure.
8. **Concurrency & lineage (HIGH 9).** Expired-phase-1 supersession
   linkage, one-begin-per-request, sign-count CAS. Design decisions,
   then code.
9. **Findings 10-14** (MEDIUMs): refusal-shape conventions at the
   consume seat, daemon refusal classification (corruption vs absence),
   create=False still creating an empty db file, retention-test token
   quality, R11 test docstring accuracy. Each small; none witness-
   blocking on its own.

## What this round proves about the process

The 420-green floor missed all fourteen. The gate found them by driving
the REAL readers and REAL call paths where my tests substituted
synthetic inputs — the same synthetic-input failure the full-body audit
named in S7's own validator, reproduced by me, caught by the process
built to catch it. The witness stays unscheduled until this ledger is
empty and the gate reads SOUND.
