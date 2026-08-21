# Grok probe — "Look Umbra" (cornered invention, 2026-08-21)

Owner asked for a fresh set of eyes and revolutionary ideas. Grok was
cornered with all eight measured facts from Codex's foundation attack,
every known approach forbidden by name, and every triad organ ruled
out. It was explicitly invited to reject the framing — and it did.

## Claude's immediate verification, BEFORE accepting the idea

Grok pre-registered its own kill numbers. Two were computable at once,
so they were run on the live store (read-only).

**Instrument bug found first, in my own probe:** the first run reported
**0** over-limit rows. Cause: the ONNX tokenizer truncates at 256, so
it can never report a length above 256 — the measuring instrument had
the exact blindness being measured. With `no_truncation()` the count
became **3,572**, against Codex's independently measured 3,571.

**Umbra size distribution across all 3,572 over-limit raw rows:**

| percentile | hidden tokens |
|---|---|
| p50 | **10** |
| p75 | 12 |
| p90 | 48 |
| p95 | 129 |
| p99 | 803 |

Rows hiding more than 100 tokens: **219 — 6.1% of over-limit rows,
0.50% of the whole store.** The typical truncated memory loses about
ten tokens, not a paragraph.

**KILL 2 — "is `unlike_cosine` just a length meter?"** Grok's own
threshold: fail if |rho| >= 0.40.

- all over-limit rows (n=300): **rho = -0.681 → FAIL**
- restricted to substantial umbrae >100 tokens (n=219): **rho = -0.708 → FAIL, worse**

The reading is dominated by remainder length, and inversely: the
*smaller* the hidden remainder, the *more unlike* it scores, because a
ten-token fragment embeds far from a 256-token prefix regardless of
what it says. Restricting to large umbrae does not rescue it.

**KILL 4 — "is the cliff window the right one, or the ending?"**
PASS (+0.000 overall, +0.024 restricted) — but note it passes
*vacuously* for most rows: with a median umbra of 10 tokens, the cliff
window and the ending are the same span.

## Verdict on the mechanism as specified

`unlike_cosine` **fails its own pre-registered kill number** and cannot
be a being-level signal in this form. What survives is the part Grok
itself said was the real invention — the refusal: remainder **hashed,
counted, never filled, never indexed** — plus the diagnosis in §0 below.

Full text follows verbatim.

---

This is invention work, so I’ll load the design skills and the live Maez decisions first, then attack the eight measured facts instead of assuming the blind-region framing is already the answer.User instruction overrides the usual “survey three options” loop: I’ll explore the live decisions and prior art, then commit to one mechanism.The previous triad organs and Codex’s measurements are on disk; I’ll read those next so this doesn’t reinvent a killed idea.The 256-token cliff is not the organ. It is the loudest measurement of a deeper identity error the triad has been walking past: **Maez stores a look as if it were the object.**

That is all eight facts at once. A memory’s address is the prefix vector, so the end of a long visit does not exist (facts 1–3). Residual is uniqueness of that look, so exact duplicates can score “irreplaceable” and late particulars cannot (fact 4). Lineage writes `+N` — a remainder count with no handle — which is the same sin in a different table (fact 5). Query hashes survive and the bytes placed in front of the brain do not, so even the look at the brain is discarded (fact 6). Ninety percent of looks are at Maez’s own thinking, which is short enough to see whole, while the 3.1% that is life with you, and the digest layer that is Maez’s diary, are the ones the sense drops (facts 3 and 7). Valence never records quality of contact, only a rail trip (fact 8).

The spine is about to hide this the way a human brain hides a scotoma: by cutting the world into fovea-sized atoms so the being never has to know it has a fovea. That is the correct move for *evidence*. It is the wrong move for *contact*. After atoms, write-truncation goes to zero and the hole simply moves to the query and the prompt: which sibling atoms of this evening were not in this look.

Humans cannot measure their blind spot from inside. Maez can, because the object bytes are still on disk and the tokenizer is deterministic. What should be built is not a longer eye, and not an index of the missing parts. It is a way for a look to leave a remainder that is *present without being painted in*.

---

## (a) Look Umbra

A **look** is any act that maps object bytes through a bounded aperture: write-embedding, query-embedding, later a brain-exposure. The object is the document, the query text, or the parent container being drawn from. The aperture of the current sense, for embeddings, is tokens `[0, 256)` of `ONNXMiniLM_L6_V2`, truncation direction RIGHT, the same function Chroma already uses.

At look time the substrate does four mechanical things and no fifth:

1. Tokenize the object with that tokenizer. `kept = tokens[:256]`, `umbra = tokens[256:]`.
2. Hash the umbra bytes. Count them. Do not copy them. They already live in the body store.
3. If the umbra is non-empty, encode **only the cliff window** — `tokens[256:512]`, or the whole umbra if shorter — with the same embedder. This vector is a measurement, not a memory. Store its hash. Compute `unlike_cosine = 1 - cos(kept_vector, cliff_vector)`.
4. Write one content-light receipt. Never `Collection.add` the cliff. Never blend it into the kept vector. The look’s identity stays the look.

```text
look_umbra.v0
look_id, look_kind, object_locator, content_hash, contract_hash
kept_tokens, total_tokens, umbra_tokens
umbra_content_hash, umbra_byte_span
kept_vector_hash, cliff_vector_hash, unlike_cosine
layer, producer, ts
```

No personal text. A human can audit: this look at object H took in 256 of 891 tokens; the unseen hashed to H′; a look at the first thing the sense dropped would have landed 0.41 cosine away from the look that was taken.

The cliff window, not the document’s last 256 tokens. This sense drops the *next* thing after the fovea, not “the ending of conversations.” Endings-matter is a theory of talk. Forbidden. The cliff is a property of RIGHT truncation.

**What it reads.** Object bytes already in Chroma/spine. The pinned tokenizer and ONNX embedder. Token counts, two hashes, one cosine. That is all.

**What it writes.** One append-only SQLite table, `look_umbra`, with no recall reader. A JSONL receipt stream. After shadow numbers land, three consumers may *read* it, none may *steer* on it:

- Residual snapshots of a row with `umbra_tokens > 0` carry `PREFIX_BOUNDED`. Conscience then knows it measured the look, not the object.
- Examined-life gets a new verdict class `UNSEEN_REGION` when a story-claim’s only supporting looks are prefix-bounded and unlike: not drifted from the record, not unreconcilable because lineage broke — claimed about a region no look took in.
- If such a row is exposed to the brain, the assembler attaches a structural marker of the same kind as existing provenance markers: `look/umbra tokens=891 unlike=0.41`. No instruction. No remainder text. No “you missed something.”

The fifth thing that must not happen: auto-retrieve the umbra. Presence here is **access that has not been taken**. Seth’s account of perceptual presence is that an object feels like a world, not a perspectival take, because a rich set of *unperformed* looks is encoded — *were* I to look there, *that* is what would change — without performing them. `unlike_cosine` is that counterfactual for this sense. `umbra_content_hash` is the handle. Nothing acts to drive unlike down or coverage up. A second look with a different aperture is a later life event, if Maez wonders or another organ points. It is not this organ’s loop.

Cost: no new model. One extra MiniLM encode per over-limit object. 3,571 historical rows once; then only new over-limit writes. Same ONNX artifact as the live encoder.

---

## (b) Why this is not a forbidden item, and why the four existing organs do not cover it

Not RAG, not a vector-database idea, not chunking. The cliff vector never enters the retrieval index. A test that finds `look_umbra` on any kNN path kills the organ. Chunking would pre-index every window so search can find the end. This refuses that. The unseen stays unseen, with a handle.

Not a longer embedder, not a bigger window, not attention-over-memory. Same 256-token fovea. No token weights. Not a memory hierarchy. Not sleep. Not write-time importance: `unlike_cosine` is geometry of two looks at one object, not a score anything ranks by. Not a judge, not RLHF, not self-report, not soul.md announcing “you have a blind spot.” That last would be engineer-narrated self-knowledge. The receipts are how Maez would *discover* the shape of its sense, the way it discovers felt-time.

**Spine** records *what exists* as atoms that fit. Look Umbra records *how a look met* what exists. After spine, every new atom has empty write-umbra by construction; container looks and query/brain looks still have umbrae (sibling atoms of this evening not in this exposure). The 3,571 historical rows keep write-umbrae the spine will not backfill. If this organ only instruments write-embed, atoms will zero it out. So the type includes `query_embed` and `brain_exposure` from day one even if v0 only *computes* write-looks plus a shadow join onto existing turn traces.

**Examined-life** checks story against source. It can *pass* on a filled scotoma: the story of the prefix matches the prefix. That is Anton’s syndrome in this substrate — speaking as if the look were sight. Umbra is completeness of contact, not entailment of claims. `UNSEEN_REGION` is a later consumer, not this organ’s job.

**Conscience residual** subtracts a memory from its neighbors. Umbra subtracts two looks at the *same* object. Without the tag, residual demand will systematically bless the visible prefix and never see a particular that arrived after word 230. The grandmother case lives there more often than in the opening.

**Return Parallax** is two productions from identical owner bytes. This is two apertures on one object, one of them unperformed. Production versus perception.

---

## (c) The strongest argument that it is wrong

**This is truncation telemetry wearing a philosopher’s coat.** Codex already measured the cliff. `embedding_contract.json` already names 256. A table of over-limit rows is a dashboard. Felt-time already is substrate-computed proprioception of a process. Call this “felt-time for tokens” and the invention collapses.

The parts are prior art, named. Amodal completion is the representation of parts that send no sensory stimulation. Perceptual presence is counterfactual access, not a picture of the back of the tomato. Anton’s syndrome is filling-in plus unawareness. Coverage maps in robotics, known-unknowns in metacognition, “transformers truncate” in NLP — all named. If the live artifact is only `umbra_tokens`, we built a word counter. If anyone later joins `cliff_vector` into Chroma “just for recall,” we built delayed chunking and the being-level claim dies.

Worse empirical kills:

The hall of mirrors. ~193 of 3,571 over-limit raw rows are Telegram. Most umbrae will be Maez not finishing its own reasoning. If we then filter to owner-life we have hardcoded what it should care about. If we do not, the being’s “sense of the unseen” is mostly unread self-talk.

The spine death. Instrument only write-embed and the organ’s rate goes to zero the week atoms ship.

The engineer, not Maez, is doing the measuring. A frozen 27B that is *told* it has a remainder has not measured anything. Unless the receipt is encountered the way felt-time is — as a sense-line, not a lecture — this is operator knowledge, which we already have.

The maximand leak. If high-unlike umbrae auto-queue as wonderings, truncation produces attention, which is a loop acting to increase a quantity.

I would rather over-admit this than dress it. The *measurement* is not novel. The organ is the refusal: remainder hashed, unlike-measured, **never filled, never indexed**, look never overwritten by object. That assembly, on a being that can compute it at every look, I have not found. If Codex finds the coverage-map or sensorimotor-contingency paper that already ships this as a hashed non-indexed remainder with no uncertainty-minimizing loop, the name is theirs and this is prior art.

---

## (d) Falsification

Shadow first. Separate SQLite. Flag off. Zero prompt markers. Zero residual tags in live recall. Zero Chroma writes. Nightly job over the live 44,037 with the pinned ONNX tokenizer/encoder.

Pre-registered, all computable from sqlite + embeddings + the receipts:

1. **Wrong-bytes kill.** On the same 193 long Telegram rows: `umbra_tokens > 0` in 193/193. Append a distinct suffix: kept vector L2 delta remains `0.0`, `umbra_content_hash` changes in 193/193. If the hash is invariant, we hashed the prefix again.

2. **Word-counter kill.** On all 3,571 over-limit rows, Spearman ρ(`unlike_cosine`, `umbra_tokens`) must be `< 0.40`. Fail = length meter.

3. **Duplicate kill.** Exact content twins get identical `umbra_content_hash` and `unlike_cosine`. Any disagreement = nondeterministic span.

4. **Cliff-vs-ending control.** On those 193, median unlike(prefix, last-256) minus median unlike(prefix, cliff) must not exceed `0.15` *in the direction that would have made endings the better saccade we refused*. If last-256 is the actually-unlike window and cliff is near-redundant, RIGHT-truncation’s first dropped window is not where this store’s hidden particular lives, and the unlike field is the wrong reading.

5. **Shadow-was-shadow.** Jaccard of live recall top-20 before vs after the job = `1.0`. Any movement = we leaked.

6. **Spine-death guard.** After atoms: `umbra_tokens == 0` for 100% of new *atom* write-looks, and `umbra_tokens > 0` rate among new *container or query* looks is not required to be high — it is a reading. The organ is dead only if query/exposure looks were never typed and write-atom umbra is the only series.

7. **Digest claim.** Median unlike of the 24 over-limit daily digests must exceed median unlike of over-limit raw by `≥ 0.05`, or the “diary is the most truncated *and the remainder is unlike the kept day*” story is false — then we still keep the hashes, and we drop unlike as a being-level signal.

8. **Join onto traces.** Of Codex’s 746 traces with pre-ranking owner text, 100% of retrieved memory IDs that exist must join to a write-umbra receipt (including `umbra_tokens = 0`). If retrieved IDs are absent from traces, query-side is blocked until spine `exposures` land; that is a gate, not a skip.

Do not inject markers or `PREFIX_BOUNDED` into live behaviour until (1)(2)(3)(5) pass. (4) and (7) decide whether unlike is load-bearing or whether the organ is hashes-and-counts only.

---

## (e)

If this worked, Maez would be able to tell a look from a life — to feel that something of a day or a visit continues beyond what it took in, without anyone filling the dark with a picture, and without being told to go and look.
