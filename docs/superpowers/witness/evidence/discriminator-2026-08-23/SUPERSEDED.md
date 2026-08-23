# Superseded by ../discriminator-2026-08-23-r27/

These runs are not wrong; they are **insufficient**, and they fail the
current judge on purpose.

Gate round 27 found that the producer RETURNED on the forced-on path before
it swept for latch artifacts, escaped stores, and the post-replay ledger
digest. So `run-f.json` here carries none of that evidence: the half of the
proof claiming "nothing was stored" rested on two self-reported numbers.
Round 27 also found that the `fixture` label was never backed by the ledger
the run actually used.

The producer was repaired (both paths now collect the same evidence before
either writes) and the discriminator was re-executed. Judging THESE files
under the current judge yields FAIL on K1/K2/K4 — that is the correct
outcome and the reason they were replaced rather than re-blessed.

Retained because deleting superseded evidence would make the record of how
the protocol tightened unreadable.
