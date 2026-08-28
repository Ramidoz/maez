# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Controlled witness: can an organic event actually create a scar?

OWNER-REQUESTED (2026-08-28), before birth. The census found
`fabrication_log.db` holding 1,144 detections — 101 of them on the real
`telegram_surface` — while `scar_tissue.db` held ZERO organic rows. All
four of its rows are `exhibit:*` backfills written at one July 3
timestamp, so the organ's organic operation had never been witnessed.

THE QUESTION IS BINARY:
  * a qualifying rewritten claim produces a properly receipted scar
    through the REAL path -> the organ works, and zero organic scars so
    far may simply be correct history;
  * the qualifying path cannot produce one -> Category A.

WHAT IS REAL HERE AND WHAT IS NOT. The machinery is real end to end:
the shipped `_rewrite_detailed`, the shipped `_emit` (which mints the
fabrication receipts), the shipped `AuditResult`, the daemon's own
`_record_fabrication_scars_from_audit_result` and `_record_scar_event`
called as the real functions, and the shipped `record_scar` with its
pinned A1 ordering. Only the STORES are sandboxed and the flag is armed
in-process.

WHAT IS SYNTHETIC IS ONLY THE CLAIM. A false factual sentence is
machinery input, not a feeling: no personality event is manufactured,
nothing is written to any live store, and nothing pretends Maez felt
anything. That line was set by the owner and is load-bearing — a scar
fabricated from a staged emotional event would corrupt the very record
this organ exists to keep honest.

The judge (the DETECTOR) is not exercised here; flags are constructed
as the judge emits them, so the witness is deterministic and tests
detection->rewrite->receipt->scar->surfacing rather than the LLM.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

_PROBE_ROOT = "/var/tmp"

#: A synthetic FALSE FACTUAL claim. Deliberately impersonal.
_FALSE_CLAIM = "The backup completed successfully at 04:00 this morning."
_JUDGE_REASON = "Claims a completed backup with no backup receipt in evidence."


class _StubDaemon:
    """Carries only what the real daemon methods reach for.

    ``_record_scar_event`` is BOUND FROM THE REAL DAEMON CLASS, not
    re-implemented — the hook calls ``self._record_scar_event(...)`` and
    swallows any AttributeError at DEBUG. The first version of this
    witness omitted it and reported a false CATEGORY A: the organ was
    fine and the harness was broken. Anything this stub does not carry
    fails silently, so it must carry the real thing.
    """

    from daemon.maez_daemon import MaezDaemon as _D
    _record_scar_event = _D._record_scar_event
    del _D

    def __init__(self, sidecar, episodes):
        self._scar_sidecar = sidecar
        self.lived_episodes = episodes


class OrganicScarWitness(unittest.TestCase):
    def test_a_rewritten_fabrication_produces_a_receipted_scar(self):
        from core.learning.scar_tissue import ScarSidecar
        from core.memory.episodes import EpisodeStore
        from core.safety import self_claim_audit as sca
        from daemon.maez_daemon import MaezDaemon

        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            root = Path(tmp)
            env = {
                "MAEZ_SCAR_TISSUE": "1",                       # armed in-process only
                "MAEZ_CONSEQUENCE_MEMORY_DB": str(root / "consequence.db"),
                "MAEZ_DATA": str(root / "data"),
                "MAEZ_PRIVATE_THOUGHTS_PATH": str(root / "pt.db"),
                "MAEZ_FABRICATION_LOG_DB": str(root / "fabrication.db"),
            }
            sidecar = ScarSidecar(root / "scar_tissue.db")
            episodes = EpisodeStore(str(root / "lived_episodes.db"))

            # HAZARD: consequence_memory.DB_PATH is evaluated at MODULE
            # IMPORT (`DB_PATH = _default_db_path()`), so setting
            # MAEZ_CONSEQUENCE_MEMORY_DB after the first import has NO
            # effect — a later test silently inherits the first one's
            # path, or worse, the LIVE store if nothing overrode it
            # before import. Pin the attribute directly.
            from core.learning import consequence_memory as _cm

            with mock.patch.dict(os.environ, env, clear=False), \
                    mock.patch.object(_cm, "DB_PATH", root / "consequence.db"):
                # --- REAL flag, exactly as the judge emits one ---
                flag = sca.Flag(
                    kind="judge",
                    span=(0, len(_FALSE_CLAIM)),
                    text=_FALSE_CLAIM,
                    reason=_JUDGE_REASON,
                )

                # --- REAL rewrite + REAL receipt minting ---
                outcome = sca._rewrite_detailed(_FALSE_CLAIM, [flag])
                receipt_ids = sca._emit(
                    surface="telegram_surface",
                    flags=[flag],
                    mode=outcome.mode,
                    signals_absent=["backup receipt"],
                    signals_present=["system stats"],
                )
                self.assertTrue(
                    receipt_ids,
                    "STOP — the audit rewrote a flagged claim but minted NO "
                    "fabrication receipt. The scar hook keys on exactly "
                    "this list, so no scar could ever form. Category A.",
                )
                self.assertNotEqual(
                    outcome.text, _FALSE_CLAIM,
                    "the rewrite left the unsupported claim unchanged",
                )

                result = sca.AuditResult(
                    text=outcome.text,
                    rewritten=True,
                    mode=outcome.mode,
                    flags=[flag],
                    fabrication_receipt_ids=receipt_ids,
                )

                # --- THE REAL DAEMON HOOK, called as the real function ---
                stub = _StubDaemon(sidecar, episodes)
                MaezDaemon._record_fabrication_scars_from_audit_result(
                    stub, result, surface="telegram_surface"
                )

                # Owner's SECOND condition, on the SAME event: a scar
                # must be USABLE afterwards, not merely stored. Read
                # inside the armed env, as the daemon would.
                rows = ScarSidecar.list_all_at(root / "scar_tissue.db")
                coverage = ScarSidecar.coverage_at(root / "scar_tissue.db")
                episodes_after = episodes.list_active() or []

        self.assertTrue(
            rows,
            "STOP — CATEGORY A. The full qualifying path ran (claim "
            "flagged, claim rewritten, fabrication receipt minted, real "
            "daemon hook invoked with the flag armed) and produced NO "
            "scar. Maez cannot learn from a caught fabrication.",
        )
        scar = rows[0]
        self.assertIn(
            "fabrication", str(scar.get("dedup_key", "")),
            "the scar is not keyed to the fabrication that caused it",
        )
        # list_all_at() returns receipt_refs already PARSED into a list;
        # the raw column name is receipt_refs_json and asserting on that
        # here silently matched the empty string.
        refs = str(scar.get("receipt_refs", scar.get("receipt_refs_json", "")))
        self.assertIn(
            "fabrication:", refs,
            "the scar carries no fabrication receipt — an unreceipted "
            "scar is an assertion without evidence",
        )
        self.assertIn(
            "consequence:", refs,
            "the scar carries no consequence receipt; record_scar's "
            "pinned A1 order mints one before writing",
        )

        self.assertTrue(
            coverage,
            "the scar exists but the surfacing reader returns nothing — "
            "a scar nothing can read is not learning",
        )
        self.assertTrue(
            episodes_after,
            "record_scar's contract writes a lived episode on FIRST "
            "occurrence; without it the scar never reaches recall",
        )

if __name__ == "__main__":
    unittest.main()
