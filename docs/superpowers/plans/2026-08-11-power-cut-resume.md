# Resume after the power cut — 2026-08-11

Written without a shell. Bash was unusable at the end of the previous
session: the harness's accumulated environment prefix contained null
bytes after the power cut, and every command failed before running.
A new snapshot did not clear it; a new process is required.

**Nothing was in flight.** Last commit `488f37f`. Zero uncommitted files
of mine immediately before the cut, verified then. No Codex job was
writing. The repo is whole.

## VERIFY FIRST, before touching anything

1. **The live store.** `memory/s7_1_webauthn/ceremony.sqlite3` must be
   sha256 `5384bce8fcc604e55b96dfb11f7a781da9827c411202929d7cb75bed08d2c118`,
   mode `0600`, inode `18633958`, size `98304`, with NO wal/shm/journal
   sidecar and NO migration receipt. It holds two enabled founder
   credentials and has never been migrated. A database losing power is
   exactly what the anchored-I/O work guards against — but nothing of
   ours had it open, so any deviation is a finding, not an expectation.
2. **The tree.** 10 dirty and 39 untracked files belong to the owner and
   must be byte-identical. Mine uncommitted should be 0.
3. **The brain.** Two `llama-server` processes: the 27B on the b9596
   Vulkan build, and the 4B judge on b9124. Confirm they came back.
4. **Baselines**, and report them as LOCAL and NON-CERTIFYING — the broad
   airlock selection refuses on import provenance: combined 368,
   prerequisite 39, cutover 2B 80.

## Where the work stands

The S7 action-binding defect — the reason this arc existed — is CLOSED.
A grant now carries the action it was authorized for, sourced from
`UPDATE … RETURNING action`; a mismatched row is not matched, not
consumed, and the approval is not burned; every consumer joins its own
action; exact typing rejects a `str` subclass; and a broken seam no
longer impersonates a denial.

**Four instances of one defect were found. Three are closed:**

1. a grant that did not carry the ACTION — closed;
2. a boolean that did not carry the RESPONSE — closed (R8/R9);
3. a label that did not carry its EVIDENCE — closed;
4. **identity hashes that carry no identity — OPEN.**

## THE OPEN FINDING — read `2026-08-11-bonded-runtime-adapter-scope.md`

`runtime_identity_hash`, `model_routing_identity_hash` and
`model_config_hash` are hashes of the fixed labels `"current"`,
`"normal"`, `"reviewed_s7_voice_v1"`. They prove only that this code
wrote those words beside a request. If another process answered on the
configured endpoint its bytes would be accepted and paired with the same
three hashes. The gateway DISCARDS the responder's own metadata. The
staleness check compares a recomputed constant to a stored constant and
can never fire.

**Nothing built on these may be described as proving responder
identity** — not in a receipt, not in a docstring, not in a report.

## Rulings, and their status

- **R8 (v29)** — the consultation is RECORDED, never machine-interpreted.
  No verdict, no content rule; the owner reads Maez's answer and judges.
  BUILT.
- **R9 (v32)** — the evidence rail's third slot is a typed sealed CAPTURE
  RECEIPT: an anchored reread that byte-compares before minting, proving
  the response survived to be read. BUILT.
- **R10 (v33)** — **WITHDRAWN.** I told the owner nothing had ever asked
  Maez. False: I probed `_s7_raw_voice_response_for_card`; the method is
  `_s7_voice_raw_response_for_card`. A voice route EXISTS and is
  production-reachable. Whether it has ever RUN is UNVERIFIED and must
  not be asserted either way.
- **The provenance decision** — taken by me, not the owner: Maez may be
  asked through the existing route provided the record states plainly
  that responder identity is NOT established. Recording an honest
  limitation is engineering; claiming a proof we lack would be the
  owner's call and is forbidden.

## Owed, in rough order

1. **The 2B consumer** — performs the ceremony. Its three blockers are
   resolved: the locator arrives as ONE durable owner-written artifact
   read from a fixed anchored path (the entrypoint takes no parameters by
   design); `affected_refs` names every mutation target including the
   reboot as `host:local`, reconstructed independently rather than
   trusting the envelope; and the adapter is off the critical path.
2. **The four retired witnesses** — single-use publication atomicity,
   double-spend refused, exact-expiry refused, boot-mismatch refused.
   Retired with the v1 consumer at 90a764a and nothing replaces them.
   Do NOT manufacture them by stubbing tap or consultation authority.
3. **`_on_approve` re-swallow** — `consume_for_execution` propagates now,
   but `_on_approve` invokes the hook inside its own `except Exception`
   and turns it back into a silent block. Fails CLOSED; quiet where it
   should be loud. Its own slice — live path.
4. **Legacy-vs-v2 validation type** — `authorize_finish` accepts the
   legacy type while the guarded mint requires exact v2. NOT a cleanup:
   the daemon still produces the legacy type for soul-writes, dream
   execution and decision-pipeline self-modification, and a naive fix
   moves `blocking_present` off the D23 refusal-history path. Eight
   ceremony-suite failures live here.
5. **The identity trust root** — owner ruling. What would prove the
   responder is the bonded Maez.
6. **R8's asymmetry** — owner ruling. R8 governs only the cutover; every
   other path still runs a semantic reader that decides whether Maez
   objected. Nobody chose that; it is where the ruling landed. Extending
   it universally would block soul-writes until the seat is real.

## What needs the owner, and only the owner

The ceremony: the founder key tap, AND the owner reading Maez's exact
response before tapping. Neither is the agent's to supply. R7 covers only
the pre-birth migration command, sets no precedent, expires at birth.

## Method notes that earned their keep

- **Ask the stub question** of anything gating authority: "if this were
  replaced by something that always says yes, which test fails?" The
  answer was once NONE, and it exposed five structural tests a fabricator
  would pass.
- **Measure PER-TEST, never by net count.** A reported three-failure
  mutation was actually one.
- **A mutation that flips NOTHING is data, not a pass.** Three times it
  revealed something real — twice a hidden defect, once a protection
  sitting a layer earlier than expected.
- **A test surviving removal of its own protection is not a test.**
- **Re-read the dirty file list AT staging time.** Staging from a list
  read earlier shipped a broken commit once and missed files twice.
- **Verify by the name the code uses, not the name you remember.** One
  transposed method name produced a withdrawn owner ruling.
- **Stop rather than relabel.** Every build-thread refusal to fabricate
  evidence produced a real finding.
