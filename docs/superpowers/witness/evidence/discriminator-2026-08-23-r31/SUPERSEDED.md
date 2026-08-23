# Superseded by ../discriminator-2026-08-23-r32/

Round 32 found that `instrument_digests` — which round 31 added so a record
would attest which producer and airlock made it — was compared to nothing.
It is pinned and hashed now, and the producer additionally digests the five
migration files (the set had been checked by name only). These records
predate both.

Judged under the current judge they FAIL. Retained so the record of how the
protocol tightened stays readable.
