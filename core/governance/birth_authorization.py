# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The birth-ceremony receipt rail (blocker A1/B2, thirteenth council round).

Before this module, `scripts/birth_ceremony.py` accepted ANY non-empty
string as its "S7 receipt" and stored it permanently in the one
irreversible row. This module makes the ceremony prove what it claims:

- `mint_and_consume_birth_authorization()` hosts the EXISTING S7 guarded
  ceremony in-process (the live-proven cutover recipe): the production
  verifier checks a real WebAuthn assertion produced by the owner's
  physical key in the cockpit-origin browser tab, the artifact lands in
  the durable v2 plane, and `consume_for_execution_with_committed_row`
  spends it atomically (single-use by `consumed_at IS NULL`).
- `held_birth_authorization_proof()` is the IN-TRANSACTION rail: it
  re-opens the store read-only through held O_NOFOLLOW descriptors, pins
  ONE snapshot, and verifies the consumed artifact BY FACTS — every
  binding recomputed from reality (canonical paths, manifest bytes),
  never taken from the mint's in-memory objects. `run_transaction` holds
  the snapshot across the birth write.

PROOF BOUNDARY, stated per the thirteenth round: the re-read proves
durable relational consistency of a founder-verified verdict row under an
honest repository-owned path. The raw WebAuthn assertion is persisted
NOWHERE (schema fact), so offline cryptographic re-verification of the
tap is impossible by construction, and a hostile same-UID writer is
outside what S7 has ever claimed to stop. The physical key, the 0600
store, the interactive TTY and the uid are the gates; this rail makes
their product durable, single-use, and recomputable — it does not turn a
process into its own witness.

Inline mint shipped 2-1 (Codex dissent recorded in the rulings doc): the
daemon's routed mint would require flipping S7_LIVE_WEBAUTHN_CEREMONY (an
owner human-gate that turns the dormancy gate red) and building a birth
card producer; a script-hosted owner-TTY ceremony has no HTTP surface for
the route token to protect.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.governance import operator_user_boundary as s7

BIRTH_ACTION = "ledger.birth_ceremony"
BIRTH_WORK_CLASS = "birth_activation"

#: Ruled freshness (thirteenth round: Grok 300 / Claude 1800 -> 600).
#: Service stop between consume and the birth write takes seconds; a
#: ceremony that stalls past this window refuses and the owner re-taps.
BIRTH_CONSUME_FRESHNESS_S = 600

#: The env-override CLASS (Codex amendment — sweep the class, not the two
#: instances the author happened to execute). Any of these set during a
#: for-real ceremony can redirect an authority-bearing path: the ledger,
#: the data root, the config root (creation manifest), or the S7 store.
FORBIDDEN_ENV_OVERRIDES = (
    "MAEZ_LEDGER_DB_PATH",
    "MAEZ_DATA",
    "MAEZ_HOME",
    "MAEZ_CONFIG",
    "S7_WEBAUTHN_STORE_ROOT",
)

_V2_TABLE = "s7_authorization_artifacts_v2"
_CRED_TABLE = "s7_founder_webauthn_credentials"
_CHALLENGE_TABLE = "s7_ceremony_challenges"


class BirthAuthorizationRefusal(RuntimeError):
    """A named refusal. `reason` is closed vocabulary; `detail` is prose."""

    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason
        super().__init__(f"{reason}: {detail}" if detail else reason)


def _now_z() -> str:
    return (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )


def refuse_env_overrides(env: dict | None = None) -> None:
    """For-real only: any path-redirecting override refuses the ceremony.

    Executed finding (this arc): MAEZ_LEDGER_DB_PATH in the operator's
    shell made a decoy path pass the 'canonical ledger only' check while
    the daemon's unit env read the real one.
    """
    source = os.environ if env is None else env
    present = [name for name in FORBIDDEN_ENV_OVERRIDES if source.get(name)]
    if present:
        raise BirthAuthorizationRefusal(
            "env_override_in_for_real",
            f"unset {', '.join(sorted(present))} — a for-real ceremony binds "
            "to the unoverridden canonical paths only",
        )


def _unoverridden_root() -> Path:
    # The paths layer's own computed root, deliberately BYPASSING the env
    # overrides (which refuse_env_overrides has already rejected for
    # for-real). paths._SELF_ROOT is the directory the code actually
    # lives in — the same value home() returns with no env set.
    from core.infra import paths as _paths

    return _paths._SELF_ROOT


def canonical_ledger_realpath() -> str:
    return str((_unoverridden_root() / "memory" / "ledger.db").resolve())


def canonical_s7_store_path() -> Path:
    return (
        _unoverridden_root() / "memory" / "s7_1_webauthn" / "ceremony.sqlite3"
    )


def canonical_manifest_path() -> Path:
    return _unoverridden_root() / "config" / "creation_manifest.md"


def read_manifest_sha256(manifest_path: Path) -> str:
    """Hash the owner's creation manifest through a held descriptor.

    Structural O1 enforcement: the rail REQUIRES the file and hashes its
    bytes; it never writes, templates, or shape-validates the owner's
    letter (shape rules are an owner open question). Held O_NOFOLLOW read
    per the thirteenth round: a resolved pathname is not an inode
    guarantee.
    """
    manifest_path = Path(manifest_path)
    dir_fd = None
    fd = None
    try:
        try:
            dir_fd = s7._open_directory_by_components(manifest_path.parent)
        except OSError as exc:
            raise BirthAuthorizationRefusal(
                "manifest_missing", f"cannot open {manifest_path.parent}: {exc}"
            ) from exc
        try:
            fd = os.open(
                manifest_path.name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=dir_fd,
            )
        except FileNotFoundError as exc:
            raise BirthAuthorizationRefusal(
                "manifest_missing",
                f"{manifest_path} does not exist — the creation manifest is "
                "owner-authored and must exist before any ceremony (O1); no "
                "agent may write it",
            ) from exc
        except OSError as exc:
            raise BirthAuthorizationRefusal(
                "manifest_unreadable", str(exc)
            ) from exc
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise BirthAuthorizationRefusal(
                "manifest_not_regular", "the manifest must be a regular file"
            )
        if st.st_uid != os.getuid():
            raise BirthAuthorizationRefusal(
                "manifest_wrong_owner",
                f"owned by uid {st.st_uid}, ceremony runs as {os.getuid()}",
            )
        hasher = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                break
            hasher.update(chunk)
            total += len(chunk)
        if total == 0:
            raise BirthAuthorizationRefusal(
                "manifest_empty", "the creation manifest has no bytes"
            )
        return hasher.hexdigest()
    finally:
        if fd is not None:
            os.close(fd)
        if dir_fd is not None:
            os.close(dir_fd)


def birth_action_params(
    *,
    ledger_db_realpath: str,
    creation_manifest_sha256: str,
    owner_witness: str,
    mode: str,
) -> dict[str, str]:
    """The preimage the owner's tap covers. Mode is INSIDE it, so a
    rehearsal artifact can never authorize a real birth."""
    if mode not in ("for_real", "dry_run"):
        raise BirthAuthorizationRefusal("mode_invalid", repr(mode))
    if not owner_witness.strip():
        raise BirthAuthorizationRefusal("owner_witness_missing")
    return {
        "ledger_db_realpath": str(ledger_db_realpath),
        "creation_manifest_sha256": creation_manifest_sha256,
        "owner_witness": owner_witness,
        "mode": mode,
    }


def build_birth_envelope(
    *,
    run_id: str,
    params: dict[str, str],
    now: str,
    expires_at: str,
) -> Any:
    """The one honest envelope. Closed-vocabulary literals as ruled:
    birth_requested (widened — every prior symptom code is repair-shaped),
    covenant_organ_change / not_self_fix / behavior_change /
    no_safe_rollback (existing, honest). The manifest hash rides
    free_text_ref_hash so the owner's letter is bound into the envelope
    hash as well as the params hash."""
    return s7.build_work_request_envelope(
        request_id=run_id,
        action=BIRTH_ACTION,
        params=dict(params),
        claimed_work_class=BIRTH_WORK_CLASS,
        requesting_subsystem="birth_ceremony",
        closed_symptom_code="birth_requested",
        proposed_change_class="covenant_organ_change",
        why_self_fix_failed_class="not_self_fix",
        affected_refs=(),
        # The envelope carries free_text_ref_hash (the manifest binding),
        # and the validator REQUIRES bonded_content_ref with it — executed
        # during build; the design's "content_free" did not survive the
        # validator, and bonded_content_ref is the honest name for a hash
        # of the owner's letter.
        content_exposure_risk="bonded_content_ref",
        precondition_hash=s7.canonical_hash(
            {"preflight_classification": "NOT_COMMITTED", **params}
        ),
        created_at=now,
        expires_at=expires_at,
        predicted_effect_class="behavior_change",
        rollback_path_class="no_safe_rollback",
        maez_voice_consultation_id=None,
        free_text_ref_hash=params["creation_manifest_sha256"],
    )


def _parse_ts(value: object, *, field: str) -> datetime:
    if type(value) is not str:
        raise BirthAuthorizationRefusal("clock_incoherent", f"{field} not text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise BirthAuthorizationRefusal(
            "clock_incoherent", f"{field}={value!r}"
        ) from exc
    if parsed.tzinfo is None:
        raise BirthAuthorizationRefusal(
            "clock_incoherent", f"{field} is timezone-naive"
        )
    return parsed


@contextmanager
def held_birth_authorization_proof(
    *,
    store_path: Path,
    run_id: str,
    expected_params: dict[str, str],
    now: str | None = None,
):
    """Open the S7 store read-only via held descriptors, pin ONE snapshot,
    verify the consumed birth authorization BY FACTS, and yield them.

    The caller (run_transaction) holds the snapshot across the birth write
    so the verified facts cannot change under it unseen. Every check is a
    named refusal; any failure aborts before the irreversible row.
    """
    store_path = Path(store_path)
    dir_fd = None
    store_fd = None
    conn = None
    try:
        try:
            dir_fd = s7._open_directory_by_components(store_path.parent)
            store_fd = os.open(
                store_path.name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=dir_fd,
            )
        except OSError as exc:
            raise BirthAuthorizationRefusal(
                "receipt_store_unavailable", f"{store_path}: {exc}"
            ) from exc
        st = os.fstat(store_fd)
        if not stat.S_ISREG(st.st_mode):
            raise BirthAuthorizationRefusal(
                "receipt_store_unavailable", "store is not a regular file"
            )
        if st.st_uid != os.getuid():
            raise BirthAuthorizationRefusal(
                "receipt_store_unavailable",
                f"store owned by uid {st.st_uid}, ceremony runs as {os.getuid()}",
            )
        try:
            conn = sqlite3.connect(
                f"file:/proc/self/fd/{store_fd}?mode=ro", uri=True
            )
            conn.row_factory = sqlite3.Row
            # Pin one snapshot: BEGIN + first read. Later re-reads inside
            # this context see exactly this state.
            conn.execute("BEGIN")
            table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (_V2_TABLE,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise BirthAuthorizationRefusal(
                "receipt_store_unavailable", str(exc)
            ) from exc
        if table is None:
            raise BirthAuthorizationRefusal(
                "receipt_store_unavailable",
                "v2 authorization plane is absent; absent is not permission",
            )

        row = conn.execute(
            f"SELECT * FROM {_V2_TABLE} WHERE request_id = ?", (run_id,)
        ).fetchall()
        if len(row) != 1:
            raise BirthAuthorizationRefusal(
                "receipt_unresolved",
                f"{len(row)} artifacts carry request_id {run_id!r}; exactly "
                "one consumed birth authorization must exist for this run",
            )
        art = row[0]

        if art["action"] != BIRTH_ACTION:
            raise BirthAuthorizationRefusal("wrong_action", art["action"])
        if art["derived_work_class"] != BIRTH_WORK_CLASS:
            raise BirthAuthorizationRefusal(
                "wrong_work_class", art["derived_work_class"]
            )
        if art["schema_version"] != "s7.authorization_artifact.v2":
            raise BirthAuthorizationRefusal(
                "wrong_schema", str(art["schema_version"])
            )
        if (
            art["auth_method"] != "founder_webauthn"
            or art["grant_source"] != "founder_webauthn"
            or art["ceremony_kind"] != "founder_local_webauthn"
        ):
            raise BirthAuthorizationRefusal(
                "owner_proof_missing",
                f"auth_method={art['auth_method']!r} "
                f"grant_source={art['grant_source']!r} "
                f"ceremony_kind={art['ceremony_kind']!r}",
            )
        if art["user_presence"] != 1 or art["user_verification"] != 1:
            raise BirthAuthorizationRefusal(
                "owner_proof_missing",
                f"user_presence={art['user_presence']} "
                f"user_verification={art['user_verification']}",
            )
        expected_hash = s7.canonical_hash(dict(expected_params))
        if art["action_params_hash"] != expected_hash:
            raise BirthAuthorizationRefusal(
                "binding_mismatch",
                "the tapped params hash does not match the recomputed "
                "preimage (db path / manifest bytes / witness / mode)",
            )
        if art["consumed_at"] is None:
            raise BirthAuthorizationRefusal(
                "not_consumed",
                "the artifact exists but was never spent — the ceremony "
                "consumes at mint; an unconsumed artifact did not come "
                "from this ceremony's path",
            )
        if art["consumed_by_request_id"] != run_id:
            raise BirthAuthorizationRefusal(
                "run_identity_mismatch",
                f"consumed by {art['consumed_by_request_id']!r}, "
                f"this run is {run_id!r} — a crashed ceremony's artifact "
                "never authorizes a re-run; re-tap",
            )
        created = _parse_ts(art["created_at"], field="created_at")
        consumed = _parse_ts(art["consumed_at"], field="consumed_at")
        expires = _parse_ts(art["expires_at"], field="expires_at")
        if not (created <= consumed < expires):
            raise BirthAuthorizationRefusal(
                "clock_incoherent",
                f"created={art['created_at']} consumed={art['consumed_at']} "
                f"expires={art['expires_at']}",
            )
        now_ts = _parse_ts(now if now is not None else _now_z(), field="now")
        age = (now_ts - consumed).total_seconds()
        if age < 0 or age > BIRTH_CONSUME_FRESHNESS_S:
            raise BirthAuthorizationRefusal(
                "consume_stale",
                f"consumed {age:.0f}s from now (window "
                f"{BIRTH_CONSUME_FRESHNESS_S}s) — re-tap",
            )

        cred = conn.execute(
            f"SELECT enabled, role_names_json FROM {_CRED_TABLE} "
            "WHERE credential_ref = ?",
            (art["credential_ref"],),
        ).fetchone()
        if cred is None or cred["enabled"] != 1:
            raise BirthAuthorizationRefusal(
                "credential_unknown_or_disabled", str(art["credential_ref"])
            )
        try:
            roles = json.loads(cred["role_names_json"])
        except (TypeError, ValueError):
            roles = []
        if "bonded_user" not in roles:
            raise BirthAuthorizationRefusal(
                "credential_unknown_or_disabled",
                "credential lacks the bonded_user role",
            )

        challenge = conn.execute(
            f"SELECT challenge_kind, consumed_at, action_params_hash, "
            f"request_id FROM {_CHALLENGE_TABLE} WHERE nonce = ?",
            (art["nonce"],),
        ).fetchall()
        if len(challenge) != 1:
            raise BirthAuthorizationRefusal(
                "challenge_join_failed",
                f"{len(challenge)} challenge rows carry the artifact nonce",
            )
        ch = challenge[0]
        if (
            ch["challenge_kind"] != "authorize_guarded_request"
            or ch["consumed_at"] is None
            or ch["action_params_hash"] != art["action_params_hash"]
            or ch["request_id"] != run_id
        ):
            raise BirthAuthorizationRefusal(
                "challenge_join_failed",
                "the challenge row does not D12-match the artifact",
            )

        yield {
            "ceremony_run_id": run_id,
            "s7_artifact_id": art["artifact_id"],
            "s7_request_envelope_hash": art["request_envelope_hash"],
            "s7_rendered_text_hash": art["rendered_text_hash"],
            "s7_action_params_hash": art["action_params_hash"],
            "s7_precondition_hash": art["precondition_hash"],
            "s7_nonce": art["nonce"],
            "s7_credential_ref": art["credential_ref"],
            "s7_work_class": art["derived_work_class"],
            "s7_schema_version": art["schema_version"],
            "s7_consumed_at": art["consumed_at"],
            "creation_manifest_sha256": expected_params[
                "creation_manifest_sha256"
            ],
            "ledger_db_realpath": expected_params["ledger_db_realpath"],
        }
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        if store_fd is not None:
            os.close(store_fd)
        if dir_fd is not None:
            os.close(dir_fd)


def birth_receipt_projection_sha256(facts: dict[str, str]) -> str:
    """Canonical hash of the resolved receipt facts — the 'hash of the
    ceremony receipts' the 2026-07-05 design puts in the birth row."""
    return s7.canonical_hash(dict(facts))


def committed_grant_row_proves_birth_activation(row: Any, grant: Any) -> bool:
    """The birth-pinned analogue of
    committed_grant_row_proves_founder_self_modification: field-exact
    row-to-grant equality, founder methods, UV=1, class birth_activation,
    consumed_by == request_id, exact-canonical clocks."""
    if not isinstance(row, s7.CommittedGrantRow) or not isinstance(
        grant, s7.S7ExecutionGrant
    ):
        return False
    for field in s7._COMMITTED_ROW_GRANT_FIELDS:
        row_value = getattr(row, field)
        grant_value = getattr(grant, field)
        if type(row_value) is not type(grant_value) or row_value != grant_value:
            return False
    if (
        type(grant.schema_version) is not str
        or grant.schema_version != "s7.execution_grant.v2"
        or type(row.schema_version) is not str
        or row.schema_version != s7.S7_AUTHORIZATION_ARTIFACT_V2_SCHEMA
        or type(row.user_presence) is not int
        or row.user_presence != 1
        or type(row.user_verification) is not int
        or row.user_verification != 1
        or type(row.consumed_by_request_id) is not str
        or row.consumed_by_request_id != row.request_id
        or row.derived_work_class != BIRTH_WORK_CLASS
        or row.action != BIRTH_ACTION
        or row.ceremony_kind != "founder_local_webauthn"
        or row.auth_method != "founder_webauthn"
        or row.grant_source != "founder_webauthn"
    ):
        return False
    created = s7._parse_exact_canonical_row_timestamp(row.created_at)
    consumed = s7._parse_exact_canonical_row_timestamp(row.consumed_at)
    expires = s7._parse_exact_canonical_row_timestamp(row.expires_at)
    if created is None or consumed is None or expires is None:
        return False
    return created <= consumed < expires


def fresh_birth_run_id() -> str:
    """Unpredictable (Codex amendment): the run id is the envelope
    request_id is the consumed_by_request_id, and it must not be
    guessable by an importer replaying within the freshness window."""
    return f"birth-{secrets.token_hex(16)}"


def mint_and_consume_birth_authorization(
    *,
    store_root: Path,
    run_id: str,
    params: dict[str, str],
    verifier: Any = None,
    printer: Callable[[str], None] = print,
    prompt: Callable[[str], str] = input,
    now: str | None = None,
) -> dict[str, str]:
    """Host the existing S7 guarded ceremony for the birth action and
    atomically consume the minted artifact. Returns the resolved facts.

    The owner's assertion comes from navigator.credentials.get in the
    cockpit-origin browser tab (maez-web must be UP), pasted at the TTY —
    the cutover recipe, six real taps of precedent. The paste must echo
    the params hash printed at the gate, so the tap provably covers what
    the owner saw.
    """
    from core.governance.s7_consultation_exemption import born_by_any_signal
    from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore
    from core.governance.s7_webauthn_ceremony import (
        S7LocalWebAuthnCeremonyService,
    )

    if born_by_any_signal():
        raise BirthAuthorizationRefusal(
            "already_born", "birth authorization cannot be minted after birth"
        )

    store_root = Path(store_root)
    store = S7WebAuthnBootstrapStore(store_root)
    if verifier is None:
        from core.governance.s7_webauthn_verifier import (
            S7ProductionWebAuthnVerifier,
        )

        verifier = S7ProductionWebAuthnVerifier()
    service = S7LocalWebAuthnCeremonyService(
        verifier=verifier, store_factory=lambda: store
    )

    mint_now = now if now is not None else _now_z()
    expires_at = s7_add_minutes(mint_now, 5)
    envelope = build_birth_envelope(
        run_id=run_id, params=params, now=mint_now, expires_at=expires_at
    )
    if envelope.derived_work_class != BIRTH_WORK_CLASS:
        raise BirthAuthorizationRefusal(
            "wrong_work_class",
            f"envelope derived {envelope.derived_work_class!r}",
        )
    credentials = store.list_credentials()
    enabled = [c for c in credentials if getattr(c, "enabled", False)]
    if not enabled:
        raise BirthAuthorizationRefusal(
            "credential_unknown_or_disabled", "no enabled founder credential"
        )
    # Primary key first; the backup authorizes only when the primary is
    # gone (the same preference the recovery-state degraded flags encode).
    primary = [
        c for c in enabled if getattr(c, "credential_kind", "") == "primary"
    ]
    credential = (primary or enabled)[0]
    action_params_hash = s7.canonical_hash(dict(params))
    if "bonded_user" not in credential.role_names:
        raise BirthAuthorizationRefusal(
            "credential_unknown_or_disabled",
            "the founder credential lacks the bonded_user role",
        )
    # The same context shape the cutover's real taps used —
    # _authority_context_active_for_artifact requires every field below.
    authority_context = s7.AuthorityContext(
        actor_id="founder",
        actor_handle_hmac=credential.actor_handle_hmac,
        role_names=tuple(credential.role_names),
        grant_source="founder_webauthn",
        allowed_scopes=("operator_health",),
        auth_method="founder_webauthn",
        surface="birth_ceremony_tty",
        credential_ref=credential.credential_ref,
        created_at=mint_now,
        expires_at=expires_at,
        verified=True,
        verification_reason="founder_local_webauthn_challenge_pending",
    )
    rendered = s7.render_request_statement(
        envelope=envelope,
        surface="birth_ceremony_tty",
        origin="http://localhost:11437",
        action_params_hash=action_params_hash,
        authority_context=authority_context,
        maez_voice_consultation=None,
        nonce=secrets.token_hex(32),
        expires_at=expires_at,
        rendered_at=mint_now,
    )

    recovery = store.credential_recovery_state()
    session_binding = "birth-session-" + secrets.token_hex(32)
    internal_channel_binding = "birth-internal-" + secrets.token_hex(32)
    begin = service.authorize_begin(
        now=mint_now,
        rendered_statement=rendered,
        precondition_hash=envelope.precondition_hash,
        session_binding=session_binding,
        internal_channel_binding=internal_channel_binding,
        allow_degraded_primary_only=(
            recovery.get("primary_credential_state") == "enabled"
            and recovery.get("backup_credential_state") != "enabled"
        ),
        allow_degraded_backup_only=(
            recovery.get("primary_credential_state") == "missing"
            and recovery.get("backup_credential_state") == "enabled"
        ),
    )
    if begin.status_code != 200:
        raise BirthAuthorizationRefusal(
            "mint_begin_refused", json.dumps(begin.body, sort_keys=True)
        )
    challenge_id = begin.body.get("challenge_id")
    if type(challenge_id) is not str or not challenge_id:
        raise BirthAuthorizationRefusal("mint_begin_refused", "no challenge id")

    # The WYSIWYS gate (Codex amendment: the generic renderer shows only
    # hashes; the owner must SEE the parameters the tap covers). Everything
    # the owner's paste must echo is printed here as a template with one
    # hole — the browser assertion.
    printer(
        json.dumps(
            {
                "birth_action": BIRTH_ACTION,
                "birth_action_params": dict(params),
                "birth_action_params_sha256": action_params_hash,
                "rendered_authorization": rendered.rendered_text,
                "public_key_options": begin.body.get("public_key_options"),
                "webauthn_finish_template": {
                    "challenge_id": challenge_id,
                    "credential_ref": credential.credential_ref,
                    "birth_action_params_sha256": action_params_hash,
                    "authentication_response": (
                        "<the assertion from navigator.credentials.get at"
                        " http://localhost:11437, base64url-encoded fields>"
                    ),
                },
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    try:
        raw = prompt("webauthn_finish_json> ")
        request_json = json.loads(raw)
    except (EOFError, KeyboardInterrupt, json.JSONDecodeError) as exc:
        raise BirthAuthorizationRefusal("owner_presence_unattested") from exc
    if (
        type(request_json) is not dict
        or request_json.get("challenge_id") != challenge_id
        or request_json.get("credential_ref") != credential.credential_ref
        or request_json.get("birth_action_params_sha256") != action_params_hash
        or type(request_json.get("authentication_response")) is not dict
    ):
        raise BirthAuthorizationRefusal(
            "owner_presence_unattested",
            "the paste must echo challenge_id, credential_ref and the "
            "params hash printed at the gate",
        )
    request_json = {
        "challenge_id": request_json["challenge_id"],
        "credential_ref": request_json["credential_ref"],
        "authentication_response": request_json["authentication_response"],
    }

    finish_now = now if now is not None else _now_z()
    finish = service.authorize_finish(
        now=finish_now,
        envelope=envelope,
        rendered_statement=rendered,
        precondition_hash=envelope.precondition_hash,
        maez_voice_consultation=None,
        session_binding=session_binding,
        internal_channel_binding=internal_channel_binding,
        request_json=request_json,
    )
    if finish.status_code != 200:
        raise BirthAuthorizationRefusal(
            "mint_finish_refused", json.dumps(finish.body, sort_keys=True)
        )
    artifact_id = finish.body.get("artifact_id")
    if type(artifact_id) is not str or not artifact_id:
        raise BirthAuthorizationRefusal("mint_finish_refused", "no artifact id")

    # Atomic durable consume through the core held-descriptor machinery —
    # the same consume_for_execution_on_connection every other guarded
    # execution uses (no new _verify_held_store_activation caller).
    consume_now = now if now is not None else _now_z()
    store_path = store_root / "ceremony.sqlite3"
    dir_fd = None
    store_fd = None
    conn = None
    try:
        dir_fd = s7._open_directory_by_components(store_path.parent)
        store_fd = os.open(
            store_path.name,
            os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=dir_fd,
        )
        conn = s7._open_s7_connection_from_held_store(
            dir_fd=dir_fd, store_fd=store_fd
        )
        grant, _cb, committed = s7.consume_for_execution_with_committed_row(
            conn,
            artifact_id,
            rendered=rendered,
            action_params_hash=action_params_hash,
            authority_context=authority_context,
            precondition_hash=envelope.precondition_hash,
            derived_work_class=BIRTH_WORK_CLASS,
            derived_aggregation_group=rendered.derived_aggregation_group,
            now=consume_now,
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        if store_fd is not None:
            os.close(store_fd)
        if dir_fd is not None:
            os.close(dir_fd)
    if grant is None or committed is None:
        raise BirthAuthorizationRefusal(
            "consume_refused",
            "the atomic consume matched no row — bindings or expiry failed "
            "at the store",
        )
    if not committed_grant_row_proves_birth_activation(committed, grant):
        raise BirthAuthorizationRefusal(
            "committed_row_proof_failed",
            "the post-commit row does not prove a founder birth_activation",
        )
    return {
        "ceremony_run_id": run_id,
        "s7_artifact_id": artifact_id,
        "s7_request_envelope_hash": committed.request_envelope_hash,
        "s7_rendered_text_hash": committed.rendered_text_hash,
        "s7_action_params_hash": committed.action_params_hash,
        "s7_nonce": committed.nonce,
        "s7_credential_ref": committed.credential_ref,
        "s7_consumed_at": committed.consumed_at,
        "rendered_statement_text": rendered.rendered_text,
    }


def s7_add_minutes(value: str, minutes: int) -> str:
    from core.governance.s7_webauthn_ceremony import _add_minutes

    return _add_minutes(value, minutes)
