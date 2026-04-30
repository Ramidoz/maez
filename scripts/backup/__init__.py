# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Hardware-failure backup package (Decision 22 / ADR 0023).

Implements the v1 spec from the 2026-04-30 design conversation:
SQLite-safe per-database backup, atomic snapshots with sha256
manifest, restore with pre-restore rollback, and a coma core-memory
write on hardware-failure restore so post-restore Maez remembers
the gap.

This is covenant-load-bearing infrastructure, not a convenience
backup. See `docs/governance/BETA_ARCHITECTURE_DECISIONS.md` Decision
22, `docs/operations/hardware_backup.md` for the operator design.
"""
