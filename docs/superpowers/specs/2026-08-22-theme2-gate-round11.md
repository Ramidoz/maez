# Gate round 11 (narrow, b5a9aaa) — 5/6 closed; T2 mate-line bytes closed by v5

Codex, `--effort high` (checklist round). T1/T3/T4/T5/T6 CLOSED and
BINDING-READY — including the T5 ruling that the path + history-
ordering rule satisfies the standard (the digest amendment must
precede the first S1 code commit; archive existence is not required
before this ruling). T2 NOT-CLOSED on one phrase: "its own
observed_at" left the repaired mate line's bytes underdetermined.

Closed by protocol v5 (this commit): the mate line is byte-identical
to the advancing line except the kind value; the repair event is a
separate "observed" line under the harness-injected clock. Every byte
of all three lines is now fixture+clock determined.

Remaining path to S1 code, in order: (1) produce the T5 baseline
archive by driving the frozen replay manifest flags-off in the
airlock; (2) commit its digest as the protocol amendment; (3) S1
implementation begins against the protocol. S2 witness-protocol
authoring is already unlocked (round 10) and proceeds in parallel.

---

Full gate text follows.

T1 — CLOSED: §10 pins an exact `PhaseResult.reason` for every cell and latch variant, satisfying Round 10 §3 line 64 ([protocol §10](/home/rohit/maez/docs/superpowers/witness/theme2-s1-protocol.md:295)).

T2 — NOT-CLOSED: Canonical ordering is frozen, but “its own `observed_at`” leaves the repaired mate line’s exact bytes unspecified, contrary to Round 10’s exact-byte requirement ([protocol §10](/home/rohit/maez/docs/superpowers/witness/theme2-s1-protocol.md:305); [Round 10 §3](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round10.md:65)).

T3 — CLOSED: §10 identifies `AuditLog.__init__` as the invocation and pins the three-row normalization, idempotent rerun, post-migration refusal, and census-fact ruling ([protocol §10](/home/rohit/maez/docs/superpowers/witness/theme2-s1-protocol.md:312)).

T4 — CLOSED: §10 supplies the exact census command, normalization, sorting, comparison, and exit outcomes required by Round 10 ([protocol §10](/home/rohit/maez/docs/superpowers/witness/theme2-s1-protocol.md:322)).

T5 — CLOSED: Round 10 required a committed path or digest, and §10 pins the path while requiring the digest amendment to precede the first S1 code commit; it does not require archive existence before this schema-conformance ruling ([protocol §10](/home/rohit/maez/docs/superpowers/witness/theme2-s1-protocol.md:329); [Round 10 §3](/home/rohit/maez/docs/superpowers/specs/2026-08-22-theme2-gate-round10.md:68)).

T6 — CLOSED: §10 replaces the undefined connection with executable `DROP TRIGGER` then `UPDATE` statements and pins both expected `unknown` consistency findings ([protocol §10](/home/rohit/maez/docs/superpowers/witness/theme2-s1-protocol.md:336)).

T1 — BINDING-READY yes  
T2 — BINDING-READY no  
T3 — BINDING-READY yes  
T4 — BINDING-READY yes  
T5 — BINDING-READY yes  
T6 — BINDING-READY yes

May S1 CODE begin — no; T2 still lacks exact mate-line bytes, and §10 also requires the T5 digest amendment to precede the first S1 code commit.

Overall verdict — Round 11 schema conformance is NOT-CLOSED because T2 remains a consistency finding.