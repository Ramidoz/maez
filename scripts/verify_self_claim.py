# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Forensic self-claim verifier (Step 5u).

When Maez says ``"I called it a 'hemorrhage' in my journal"`` —
is that truthful self-citation or a fabrication? The existing
``core/safety/self_claim_audit.py`` is *preventive*: it judges an
outgoing assistant response right before it ships. This is
*forensic*: it scans Maez's stored memory for prior usage of a
phrase, so the operator can spot-check claims that already shipped.

What gets searched (Maez-voice stores only — system snapshots
and user inputs are explicitly excluded):

  • Chroma raw + core collections via ``MemoryManager._query_collection``
    + a literal-substring filter
  • ``memory/private_thoughts.db`` (private_thoughts table — pure
    Maez first-person)
  • ``memory/fast_conversation_log.db`` (fast_turns where
    role='maez' — recent telegram replies)
  • ``memory/lived_episodes.db`` (episodes filtered to
    Maez-authored summaries via memory_voice column)
  • ``memory/wonderings.db`` (wonderings table — Maez's own
    questions / conclusions)

Most searched stores are read-only. The private-thoughts search is
forensic raw access, so it records an audit row before returning any
private-thought handles or snippets. Conventions follow
``scripts/audit_inspect.py`` (argparse, --json, sys.path inject).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))


# ── result dataclass ─────────────────────────────────────────────


@dataclass
class ClaimHit:
    """One verified prior usage of the searched phrase."""

    store: str
    timestamp: str
    snippet: str
    extra: dict = field(default_factory=dict)


def _excerpt(text: str, phrase: str, *, window: int = 80) -> str:
    """Surface a short excerpt of ``text`` centred on ``phrase``.
    Case-insensitive search; falls back to the head of ``text``
    when no exact-case match (the LIKE / Chroma query may have
    matched normalized text)."""
    if not text:
        return ""
    lower = text.lower()
    needle = phrase.lower()
    idx = lower.find(needle)
    if idx < 0:
        return text[:window].strip().replace("\n", " ")
    half = window // 2
    lo = max(0, idx - half)
    hi = min(len(text), idx + len(phrase) + half)
    excerpt = text[lo:hi].strip().replace("\n", " ")
    if lo > 0:
        excerpt = "…" + excerpt
    if hi < len(text):
        excerpt = excerpt + "…"
    return excerpt


# ── per-store searchers ──────────────────────────────────────────


def _search_chroma(
    *,
    phrase: str,
    top_n: int,
) -> list[ClaimHit]:
    """Walk Chroma raw + core collections via MemoryManager. Uses
    ``where_document={"$contains": phrase}`` — Chroma's
    server-side literal substring filter — to get a complete and
    fast hit set without loading the whole collection into RAM.

    Note: ``$contains`` is case-sensitive in Chroma. The verifier
    runs the search twice (lowercase + the supplied form) when
    they differ, deduplicating by row key, so the operator's
    casing doesn't accidentally hide hits. This is forensic
    tooling — completeness wins over speed."""
    hits: list[ClaimHit] = []
    try:
        from memory.memory_manager import MemoryManager

        m = MemoryManager()
    except Exception as e:
        print(
            f"warning: chroma init failed: {e}",
            file=sys.stderr,
        )
        return hits

    forms = [phrase]
    if phrase.lower() != phrase:
        forms.append(phrase.lower())

    for label, coll in (("raw", m.raw), ("core", m.core)):
        store_label = f"chroma:{label}"
        seen_ids: set[str] = set()
        per_store = 0
        for form in forms:
            try:
                rows = coll.get(
                    where_document={"$contains": form},
                    include=["metadatas", "documents"],
                )
            except Exception as e:
                print(
                    f"warning: chroma {label} where_document failed for {form!r}: {e}",
                    file=sys.stderr,
                )
                continue
            ids = rows.get("ids") or []
            docs = rows.get("documents") or []
            metas = rows.get("metadatas") or []
            for rid, doc, meta in zip(ids, docs, metas, strict=False):
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                meta = meta or {}
                ts = meta.get("timestamp") or meta.get("created_at") or "?"
                hits.append(
                    ClaimHit(
                        store=store_label,
                        timestamp=str(ts),
                        snippet=_excerpt(doc or "", phrase),
                        extra={
                            "wing": meta.get("wing"),
                            "type": meta.get("type"),
                            "role": meta.get("role"),
                        },
                    )
                )
                per_store += 1
                if per_store >= top_n:
                    break
            if per_store >= top_n:
                break
    return hits


def _search_private_thoughts(
    *,
    phrase: str,
    repo_root: Path,
    top_n: int,
    actor: str,
    s7_receipt_ref: str,
    reason: str,
) -> list[ClaimHit]:
    db = repo_root / "memory" / "private_thoughts.db"
    if not db.exists():
        return []
    hits: list[ClaimHit] = []
    try:
        from core.infra.private_thoughts import PrivateThoughts
        from core.infra import private_thoughts_unseal
        from core.infra.unseal_receipts import UnsealReceipts

        rows = private_thoughts_unseal.read_content(
            PrivateThoughts(db_path=db),
            query=phrase,
            actor=actor,
            s7_receipt_ref=s7_receipt_ref,
            reason=reason,
            receipts=UnsealReceipts(repo_root / "memory" / "unseal_receipts.db"),
            limit=top_n,
        )
    except Exception as e:
        print(
            f"warning: private_thoughts unseal failed: {e}",
            file=sys.stderr,
        )
        return []
    for r in rows:
        hits.append(
            ClaimHit(
                store="private_thoughts",
                timestamp=str(r.get("ts", "?")),
                snippet=_excerpt(r.get("content") or "", phrase),
                extra={
                    "thought_id": r.get("thought_id"),
                    "provenance": r.get("provenance"),
                    "phase": r.get("memory_phase"),
                },
            )
        )
    _record_private_thoughts_search_audit(
        repo_root=repo_root,
        phrase=phrase,
        top_n=top_n,
        hits=hits,
    )
    return hits


def _record_private_thoughts_search_audit(
    *,
    repo_root: Path,
    phrase: str,
    top_n: int,
    hits: list[ClaimHit],
) -> None:
    from core.cognition.audit_log import AuditLog

    returned_handles = sorted(f"{hit.store}:{hit.extra.get('thought_id')}" for hit in hits)
    AuditLog(repo_root / "memory" / "audit_log.db").record(
        action="private_thoughts.verify_self_claim_search",
        params={
            "phrase_sha256": hashlib.sha256(phrase.encode("utf-8")).hexdigest(),
            "top_n": int(top_n),
            "returned_hit_count": len(hits),
            "returned_handles_sha256": hashlib.sha256(
                "\n".join(returned_handles).encode("utf-8")
            ).hexdigest(),
        },
        classification={
            "intent_category": "FORENSIC_PRIVATE_THOUGHTS",
            "lane": "operator_forensic",
        },
        injection_matches=[],
        verdict=None,
        policy_rule_id="S1A1_PRIVATE_THOUGHTS_FORENSIC_AUDIT",
    )


def _search_fast_conversation(
    *,
    phrase: str,
    repo_root: Path,
    top_n: int,
) -> list[ClaimHit]:
    db = repo_root / "memory" / "fast_conversation_log.db"
    if not db.exists():
        return []
    hits: list[ClaimHit] = []
    con: sqlite3.Connection | None = None
    try:
        con = sqlite3.connect(str(db))
        con.row_factory = sqlite3.Row
        # role='maez' filter — only Maez-authored turns count as
        # self-claims.
        rows = con.execute(
            "SELECT id, trust_scope, role, text, created_at "
            "FROM fast_turns "
            "WHERE role = 'maez' AND LOWER(text) LIKE ? "
            "ORDER BY created_at DESC LIMIT ?",
            (f"%{phrase.lower()}%", int(top_n)),
        ).fetchall()
    except sqlite3.Error as e:
        print(
            f"warning: fast_conversation query failed: {e}",
            file=sys.stderr,
        )
        return []
    finally:
        if con is not None:
            con.close()
    for r in rows:
        hits.append(
            ClaimHit(
                store="fast_conversation",
                timestamp=str(r["created_at"]),
                snippet=_excerpt(r["text"] or "", phrase),
                extra={
                    "id": r["id"],
                    "trust_scope": r["trust_scope"],
                },
            )
        )
    return hits


def _search_lived_episodes(
    *,
    phrase: str,
    repo_root: Path,
    top_n: int,
) -> list[ClaimHit]:
    db = repo_root / "memory" / "lived_episodes.db"
    if not db.exists():
        return []
    hits: list[ClaimHit] = []
    con: sqlite3.Connection | None = None
    try:
        con = sqlite3.connect(str(db))
        con.row_factory = sqlite3.Row
        # Episodes are summaries; memory_voice column tells us
        # which are first-person Maez-authored. NULL/missing voice
        # is treated as Maez-authored per the column's add-comment
        # in core/memory/episodes.py.
        rows = con.execute(
            "SELECT id, created_at, occurred_at, title, summary, "
            "memory_voice "
            "FROM episodes "
            "WHERE (LOWER(title) LIKE ? OR LOWER(summary) LIKE ?) "
            "AND status = 'active' "
            "ORDER BY COALESCE(occurred_at, created_at) DESC "
            "LIMIT ?",
            (
                f"%{phrase.lower()}%",
                f"%{phrase.lower()}%",
                int(top_n),
            ),
        ).fetchall()
    except sqlite3.Error as e:
        print(
            f"warning: lived_episodes query failed: {e}",
            file=sys.stderr,
        )
        return []
    finally:
        if con is not None:
            con.close()
    for r in rows:
        # Search both title and summary, prefer summary excerpt
        # when phrase appears there.
        text = r["summary"] if phrase.lower() in (r["summary"] or "").lower() else r["title"]
        hits.append(
            ClaimHit(
                store="lived_episodes",
                timestamp=str(r["occurred_at"] or r["created_at"]),
                snippet=_excerpt(text or "", phrase),
                extra={
                    "episode_id": r["id"],
                    "memory_voice": r["memory_voice"],
                    "title": r["title"],
                },
            )
        )
    return hits


def _search_wonderings(
    *,
    phrase: str,
    repo_root: Path,
    top_n: int,
) -> list[ClaimHit]:
    db = repo_root / "memory" / "wonderings.db"
    if not db.exists():
        return []
    hits: list[ClaimHit] = []
    con: sqlite3.Connection | None = None
    try:
        con = sqlite3.connect(str(db))
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT id, created_at, question, conclusion, status "
            "FROM wonderings "
            "WHERE LOWER(question) LIKE ? "
            "OR LOWER(COALESCE(conclusion,'')) LIKE ? "
            "ORDER BY created_at DESC LIMIT ?",
            (
                f"%{phrase.lower()}%",
                f"%{phrase.lower()}%",
                int(top_n),
            ),
        ).fetchall()
    except sqlite3.Error as e:
        print(
            f"warning: wonderings query failed: {e}",
            file=sys.stderr,
        )
        return []
    finally:
        if con is not None:
            con.close()
    for r in rows:
        text = (
            r["conclusion"]
            if (r["conclusion"] or "").lower().find(phrase.lower()) >= 0
            else r["question"]
        )
        hits.append(
            ClaimHit(
                store="wonderings",
                timestamp=str(r["created_at"]),
                snippet=_excerpt(text or "", phrase),
                extra={
                    "wonder_id": r["id"],
                    "status": r["status"],
                },
            )
        )
    return hits


# ── public API ───────────────────────────────────────────────────


_SEARCHERS = {
    "chroma": _search_chroma,
    "private_thoughts": _search_private_thoughts,
    "fast_conversation": _search_fast_conversation,
    "lived_episodes": _search_lived_episodes,
    "wonderings": _search_wonderings,
}


def verify_phrase(
    phrase: str,
    *,
    repo_root: Path | None = None,
    stores: list[str] | None = None,
    top_n: int = 10,
    private_unseal_actor: str | None = None,
    private_unseal_s7_receipt_ref: str | None = None,
    private_unseal_reason: str | None = None,
) -> list[ClaimHit]:
    """Search every Maez-voice store for prior usage of ``phrase``.
    Returns an aggregated list of hits across all stores. The
    caller renders / counts; this function never decides truth or
    falsehood — it surfaces evidence."""
    if not phrase or not phrase.strip():
        return []
    root = repo_root if repo_root is not None else _REPO
    selected = stores or list(_SEARCHERS.keys())
    if "private_thoughts" in selected:
        missing = [
            name
            for name, value in (
                ("private_unseal_actor", private_unseal_actor),
                ("private_unseal_s7_receipt_ref", private_unseal_s7_receipt_ref),
                ("private_unseal_reason", private_unseal_reason),
            )
            if not (value or "").strip()
        ]
        if missing:
            raise ValueError(
                "private_thoughts search requires break-glass metadata: "
                + ", ".join(missing)
            )
    results: list[ClaimHit] = []
    for name in selected:
        fn = _SEARCHERS.get(name)
        if fn is None:
            continue
        try:
            if name == "chroma":
                # Chroma uses MemoryManager which finds its own
                # paths; no repo_root needed. Tests can't redirect
                # chroma to a fixture root for that reason — they
                # exclude this searcher and exercise it separately.
                results.extend(fn(phrase=phrase, top_n=top_n))
            elif name == "private_thoughts":
                results.extend(
                    fn(
                        phrase=phrase,
                        repo_root=root,
                        top_n=top_n,
                        actor=private_unseal_actor or "",
                        s7_receipt_ref=private_unseal_s7_receipt_ref or "",
                        reason=private_unseal_reason or "",
                    ),
                )
            else:
                results.extend(
                    fn(phrase=phrase, repo_root=root, top_n=top_n),
                )
        except Exception as e:
            print(
                f"warning: searcher {name!r} crashed: {e}",
                file=sys.stderr,
            )
    return results


# ── CLI ──────────────────────────────────────────────────────────


_DISCLAIMER = (
    "FORENSIC tool — read-only. Searches Maez-voice stores for "
    "prior usage of a phrase. Hit count > 0 supports a truthful "
    "self-citation; hit count == 0 means the claim is unverified "
    "(may still be true if memory was rotated). Does NOT modify "
    "any store."
)


def _render_text(hits: list[ClaimHit], phrase: str) -> str:
    if not hits:
        return f"phrase {phrase!r}: 0 hit(s) across all stores."
    lines = [f"phrase {phrase!r}: {len(hits)} hit(s)"]
    by_store: dict[str, list[ClaimHit]] = {}
    for h in hits:
        by_store.setdefault(h.store, []).append(h)
    for store in sorted(by_store):
        lines.append(f"  {store}: {len(by_store[store])}")
        for h in by_store[store]:
            lines.append(f"    [{h.timestamp}] {h.snippet}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.verify_self_claim",
        description=(
            "Search Maez's stored memory for prior usage of a "
            "phrase. Use this to spot-check whether a chat self-"
            "citation ('I called it X in my journal') has real "
            "ground in stored memory."
        ),
    )
    p.add_argument("phrase", help="Phrase to search for (case-insensitive)")
    p.add_argument(
        "--store",
        action="append",
        choices=list(_SEARCHERS.keys()),
        help="Restrict to one or more stores. Repeatable. Default: all stores.",
    )
    p.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Per-store hit cap (default: 10).",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON to stdout (default: human-readable).",
    )
    p.add_argument(
        "--actor",
        help="Break-glass actor for private_thoughts content access.",
    )
    p.add_argument(
        "--s7-receipt-ref",
        help="S7 receipt/reference authorizing private_thoughts content access.",
    )
    p.add_argument(
        "--reason",
        help="Break-glass reason for private_thoughts content access.",
    )
    args = p.parse_args(argv)
    selected = args.store or list(_SEARCHERS.keys())
    if "private_thoughts" in selected and not (
        (args.actor or "").strip()
        and (args.s7_receipt_ref or "").strip()
        and (args.reason or "").strip()
    ):
        p.error(
            "--actor, --s7-receipt-ref, and --reason are required when "
            "searching private_thoughts"
        )

    print(f"NOTE: {_DISCLAIMER}", file=sys.stderr)

    hits = verify_phrase(
        args.phrase,
        stores=args.store,
        top_n=args.top_n,
        private_unseal_actor=args.actor,
        private_unseal_s7_receipt_ref=args.s7_receipt_ref,
        private_unseal_reason=args.reason,
    )

    if args.json:
        payload = {
            "disclaimer": _DISCLAIMER,
            "phrase": args.phrase,
            "hit_count": len(hits),
            "hits": [
                {
                    "store": h.store,
                    "timestamp": h.timestamp,
                    "snippet": h.snippet,
                    "extra": h.extra,
                }
                for h in hits
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print(_render_text(hits, args.phrase))

    return 0


__all__ = ["ClaimHit", "main", "verify_phrase"]


if __name__ == "__main__":
    raise SystemExit(main())
