"""One-shot S7 founder WebAuthn transport backfill.

This is intentionally narrow: it refuses ambiguous stores and updates only the
single founder credential's transport metadata plus the record hash that covers
that metadata.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from core.governance.s7_webauthn_bootstrap import (
    _credential_record_from_row,
    _credential_record_hash,
)


DEFAULT_DB = Path("memory/s7_1_webauthn/ceremony.sqlite3")
FOUNDER_TRANSPORTS = ("usb", "nfc")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help="S7 ceremony sqlite database path",
    )
    args = parser.parse_args()

    db_path = args.db
    if not db_path.exists():
        raise SystemExit(f"refusing: db not found: {db_path}")

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN IMMEDIATE")
        try:
            rows = conn.execute(
                """
                SELECT credential_ref, actor_handle_hmac, role_names_json,
                       public_key, sign_count, rp_id, origin, credential_kind,
                       backup_credential, enabled, ceremony_kind, label, created_at,
                       last_used_at, disabled_at, disabled_by_authorization_id,
                       reenabled_by_authorization_id, registration_challenge_id,
                       attestation_format, aaguid, authenticator_attachment,
                       backup_eligible, backed_up, transports_json, library_name,
                       library_version, sign_count_mode, uv_capable,
                       uv_required_for_guarded, distinct_device_confidence, record_hash
                FROM s7_founder_webauthn_credentials
                """
            ).fetchall()
            if len(rows) != 1:
                conn.execute("ROLLBACK")
                raise SystemExit(
                    f"refusing: expected exactly one credential row, found {len(rows)}"
                )

            row = rows[0]
            current_transports = json.loads(row["transports_json"])
            if current_transports:
                conn.execute("ROLLBACK")
                raise SystemExit(
                    f"refusing: credential already has transports {current_transports!r}"
                )

            record = _credential_record_from_row(row)
            updated_record = record.__class__(
                **{
                    **record.__dict__,
                    "transports": FOUNDER_TRANSPORTS,
                    "record_hash": "",
                }
            )
            record_hash = _credential_record_hash(updated_record)
            conn.execute(
                """
                UPDATE s7_founder_webauthn_credentials
                SET transports_json = ?, record_hash = ?
                WHERE credential_ref = ?
                """,
                (
                    json.dumps(list(FOUNDER_TRANSPORTS), separators=(",", ":")),
                    record_hash,
                    row["credential_ref"],
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    print(
        "updated one founder credential transports_json to "
        f"{list(FOUNDER_TRANSPORTS)!r} and refreshed record_hash"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
