"""Committed S7 schema identities.

Generation and verification are SEPARATE PROGRAMS. These constants are
written once by a one-shot generator and thereafter only ever compared
against. The migration imports them; it never derives a target from the
schema it is building, because a schema that computes its own identity is
its own authority and vouches for nothing.

The v1 SOURCE literals are the ones ratified in the design, computed
read-only from the live store. They are reproduced exactly by the DDL in
`s7_v2_migration.py`, which is the evidence that the recipe and the table
definitions in that module are the ones the design meant:

    authorization   b8946c79c8edf9386ce73522aac8b18b6181212a949570cf9c01c01e3ac1af00
    voice (absent)  4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945

The voice source literal is the hash of an EMPTY preimage: the live store
has no voice plane, and "not there" is given a defined identity so the
receipt can bind it rather than describe a gap in prose.

The TARGET literals were withdrawn in v9 after three careful parties
computed three different pairs. These are recomputed from the frozen DDL
with the frozen recipe, and they agree with the pair the review arrived
at independently.
"""

from __future__ import annotations

S7_SOURCE_FINGERPRINT_AUTH = (
    "b8946c79c8edf9386ce73522aac8b18b6181212a949570cf9c01c01e3ac1af00"
)
S7_SOURCE_FINGERPRINT_VOICE = (
    "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
)

S7_TARGET_FINGERPRINT_AUTH = (
    "5bea4677d4d3917afaac4159cda4810484d2c5f381a482291b812de526b73226"
)
S7_TARGET_FINGERPRINT_VOICE = (
    "a4546eb9a57bb91dd9b9d3195b649d17d893e246823a80444df267bd6eb8219e"
)
