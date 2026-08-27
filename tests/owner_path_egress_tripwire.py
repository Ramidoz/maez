# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""A TRIPWIRE over canned owner-facing text on the inbound owner path.

THIS IS NOT A COMPLETENESS PROOF. It does not enumerate Maez's mouths, it
does not tell you what runs, and it must never be cited as evidence that
the owner path is fully covered. It is a tripwire: a frozen inventory of
the sites it CAN see, in the scopes it has been TOLD to look at, which
goes red when that inventory changes in either direction.

Why the weaker claim is the only honest one
-------------------------------------------
The eighteenth council round (2026-08-27, A3 seam closure) put three
seats on the question "what answers the owner before the ledger seam".
Three seats produced three different censuses, and the round recorded
the disagreement itself as the finding: the method does not converge.
The build seat's census had walked reply-producing ``return`` statements
-- and a mouth need not return.

  * ``daemon/inbound_core.py:526`` calls ``pipe.handle_reply``; the
    code's own comment at :541 says the CardRenderer SENT the
    resolution, and the function may then ``return None`` (:577).
  * ``skills/approval_card.py`` ``send_resolution(...) -> None`` sends
    and returns nothing. Codex executed it: the renderer returned None
    while the fake transport received exactly one resolution message.
  * ``core/routing/recall_receipt.py`` holds
    ``"I'm checking my dated memory for that."``, delivered via
    ``send_intermediate`` at ``daemon/maez_daemon.py:8612`` -- inside a
    region an earlier census had called empty.

So: a justification of the form "I enumerated them" is already
falsified, and this module does not offer one. What it offers is
narrower and actually true: IF a new site of a shape this scanner can
see appears inside a scope this scanner was pointed at, the build goes
red and a human has to look.

KNOWN BLIND SPOTS are enumerated in ``KNOWN_BLIND_SPOTS`` below and are
part of the contract, not a TODO list.

Two shapes, deliberately over-broad
-----------------------------------
``canned_return``
    A ``return`` whose value subtree contains ANY non-blank string
    literal or f-string, or which returns a module-level ``str``
    constant of the SAME module. Over-broad on purpose: it catches
    ``return jsonify({"reply": "(internal error)"})``, which a
    literal-only shape misses (measured -- see the design note). The
    price is that it also catches returns that are not owner speech at
    all, e.g. ``return strict_env_flag("MAEZ_INBOUND_CORE_V2")``. Those
    entries are frozen too. Over-capture costs one line in the frozen
    file; under-capture is the failure mode that matters.

``send``
    A call whose callee's terminal name matches ``_SEND_NAME_SHAPE``.
    This is a NAME-SHAPE test, not an egress analysis: it knows nothing
    about whether a transport is reached. It was chosen over a
    hand-maintained whitelist of mouth names because the whitelist was
    MEASURED to fail -- a frozen set built from the three
    council-named mouths saw 0 of the 5 real mouths in
    ``TelegramVoice._process_message`` (``_bot_send_message``,
    ``_reply_text``, ``_bot_send_chat_action``). A whitelist of mouths
    goes stale silently; a name shape at least goes red noisily.

The module-level constant fold is SCOPED: same module, top-level
``NAME = "literal"`` only. It is never followed across a function
boundary and never across a file. Folding across function boundaries
invents call sites.

Identity is a construct anchor, never a line range
--------------------------------------------------
A frozen entry is keyed by ``path::qualname::kind::detail`` with an
occurrence COUNT. Line numbers appear only in failure messages, where
they are machine-derived. A tripwire keyed on line numbers fires on
every unrelated edit above it, and a tripwire that cries wolf gets
deleted -- which would be a worse outcome than not having one.

Consequence worth stating plainly: because the key carries no content
digest, REWORDING an existing canned sentence does NOT trip this. Only
the appearance or disappearance of a site does. That is a blind spot,
and it is listed as one.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


def repo_root() -> Path:
    """The repository this test file actually lives in.

    Resolved RELATIVELY, never pinned to ``/home/rohit/maez``. 53 of the
    repo's test files pin that absolute path, which means their
    source-text assertions grade the LIVE TREE whatever checkout pytest
    is running in -- the hermetic-sandbox scar, and the reason the
    surface-registry slice had to repair its own guard before it could
    be witnessed at all.
    """
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Scope:
    """One watched region: a file, optionally narrowed to one construct.

    ``qualname`` is a dotted construct anchor (``MaezDaemon.handle_message``).
    ``None`` means the whole module. A scope is a DECLARED WATCH-LIST
    ENTRY. It is not a claim that the code inside it runs, and it is not
    a claim that code outside it is safe.
    """

    path: str
    qualname: str | None
    why: str


#: The watched scopes. Every entry carries the reason it is watched.
#:
#: Scope selection is itself a judgement call and is NOT derived from
#: anything -- adding a new owner-facing module to the codebase without
#: adding it here is invisible to this tripwire. That is blind spot #1.
OWNER_PATH_SCOPES: tuple[Scope, ...] = (
    Scope(
        "daemon/inbound_core.py",
        None,
        "The surface-agnostic inbound owner pipeline. MAEZ_INBOUND_CORE_V2=1 "
        "in the live daemon's environ. Holds the S4 return, the card-reply "
        "interceptor (:526 handle_reply -- an eighteenth-round miss), the "
        "proposal and search-commitment returns, and intent_unavailable.",
    ),
    Scope(
        "skills/surface/maez_adapter.py",
        None,
        "The surface-v2 adapter that drives run_inbound_turn, and the "
        "largest population of canned owner sentences in the arc "
        "(_try_search_commitment_intent, _surface_parity_handle_*). Also "
        "holds the adapter.send mouths and its own legacy inline body.",
    ),
    Scope(
        "skills/telegram_voice.py",
        "TelegramVoice._process_message",
        "The legacy Telegram owner path; the daemon runs a telegram-bot "
        "thread alongside surface-v2. This is the function that writes "
        "surface='telegram_text' to the ledger (:3644).",
    ),
    Scope(
        "skills/approval_card.py",
        None,
        "The card mouth. send_resolution sends and returns None -- Codex "
        "EXECUTED that the fake transport received exactly one message "
        "while the renderer returned None. Also the resolution/reminder "
        "text formatters, so a new canned card sentence is visible.",
    ),
    Scope(
        "core/routing/recall_receipt.py",
        None,
        "Holds WORKING_RECEIPT_TEXT, delivered via send_intermediate at "
        "daemon/maez_daemon.py:8612 -- inside the region an earlier "
        "census called empty.",
    ),
    Scope(
        "daemon/maez_daemon.py",
        "MaezDaemon.handle_message",
        "The owner reply function that already writes the model_reply row "
        "(:9786). Watched for the send_intermediate receipt mouth (:8612) "
        "and for any new mouth beside it.",
    ),
    Scope(
        "daemon/maez_daemon.py",
        "MaezDaemon._run_health_server.message",
        "The cockpit/web /message route. Its mouth is the HTTP response, "
        "so its canned text is only reachable through the over-broad "
        "return shape (return jsonify({'reply': '(internal error)'})).",
    ),
)


#: What this tripwire CANNOT see. Part of the contract. Anyone citing
#: this module as coverage must cite this tuple in the same breath.
KNOWN_BLIND_SPOTS: tuple[str, ...] = (
    "SCOPE. A new owner-facing module, or a new function outside the "
    "narrowed qualnames above, is invisible. Nothing derives this list.",
    "LIVENESS. A call is only syntax. This cannot say what RUNS -- "
    "daemon/maez_daemon.py:7385 (S4) is DEAD on the v2 path and a "
    "census reported it live with correct line numbers and correct "
    "arithmetic.",
    "NAME SHAPE. A mouth whose callee name does not match "
    "_SEND_NAME_SHAPE is invisible: dynamic dispatch, getattr by "
    "string, a transport passed as an opaque callable and invoked "
    "under a neutral name, __call__, or a mouth simply named "
    "something else.",
    "INDIRECTION. A canned sentence reached through a helper, a "
    "constant imported from another module, a dict/enum lookup, a "
    "**kwargs splat, or a template rendered at runtime is not a "
    "string literal in a return subtree and is invisible.",
    "WORDING. The key carries no content digest, so rewording an "
    "existing canned sentence does not trip this. Only appearance or "
    "disappearance of a site does.",
    "SEMANTICS. This says nothing about whether a site reaches the "
    "ledger, is recorded, or should be. It is a change detector over "
    "syntax, not an A3 conformance check.",
    "NON-PYTHON MOUTHS. Templates, JS in the cockpit, and anything "
    "outside the scoped .py files are entirely out of view.",
)


#: Deliberately broader than the three mouths the council named, because
#: a whitelist of known mouths was MEASURED to miss every real mouth in
#: the legacy Telegram path. Terminal-name match, word-boundaried on
#: underscores so ``handle_reply`` and ``_bot_send_message`` match while
#: ``responder`` and ``present_day`` do not.
_SEND_NAME_SHAPE = re.compile(
    r"(?:^|_)(send|reply|emit|deliver|present|announce|speak|notify)(?:$|_)",
    re.IGNORECASE,
)

CANNED_RETURN = "canned_return"
SEND = "send"


@dataclass(frozen=True)
class Site:
    path: str
    qualname: str
    kind: str
    detail: str
    lineno: int

    @property
    def key(self) -> str:
        return f"{self.path}::{self.qualname}::{self.kind}::{self.detail}"


def _dotted(node: ast.AST) -> str:
    """Dotted spelling of a callee, or '' when it is not a plain name."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _dotted(node.func)
    return ""


def _enclosing_qualnames(tree: ast.Module) -> dict[int, str]:
    """Map every node's id() to its nearest enclosing construct anchor.

    Class and closure scopes are kept in the name (``A.b.<closure>``
    style, dotted) so that a call inside a nested helper cannot collapse
    onto the outer function's identity -- the exact bypass the S7
    callsite scanner was hardened against.
    """
    out: dict[int, str] = {}

    def walk(node: ast.AST, current: str) -> None:
        for child in ast.iter_child_nodes(node):
            nxt = current
            if isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                nxt = child.name if current == "<module>" else f"{current}.{child.name}"
            out[id(child)] = nxt
            walk(child, nxt)

    walk(tree, "<module>")
    return out


def _module_string_constants(tree: ast.Module) -> set[str]:
    """Top-level ``NAME = "literal"`` bindings of THIS module only.

    Scoped fold. Never followed across a function boundary, never across
    a file. Constant-folding across boundaries invents call sites.
    """
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
    return names


def _return_carries_canned_text(
    value: ast.expr, module_constants: set[str]
) -> bool:
    if isinstance(value, ast.Name) and value.id in module_constants:
        return True
    for node in ast.walk(value):
        if isinstance(node, ast.JoinedStr):
            return True
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.strip():
                return True
    return False


def _in_scope(qualname: str, restrict: str | None) -> bool:
    if restrict is None:
        return True
    return qualname == restrict or qualname.startswith(restrict + ".")


def scan_source(path: str, source: str, qualname: str | None = None) -> list[Site]:
    """Every site of either shape in one source string, one per occurrence.

    Multiplicity is preserved: two canned returns in one function are two
    sites, so a second cannot hide behind the first.
    """
    tree = ast.parse(source)
    enclosing = _enclosing_qualnames(tree)
    module_constants = _module_string_constants(tree)
    sites: list[Site] = []

    for node in ast.walk(tree):
        where = enclosing.get(id(node), "<module>")
        if not _in_scope(where, qualname):
            continue
        if isinstance(node, ast.Return) and node.value is not None:
            if _return_carries_canned_text(node.value, module_constants):
                sites.append(
                    Site(path, where, CANNED_RETURN, "", node.lineno)
                )
        elif isinstance(node, ast.Call):
            dotted = _dotted(node.func)
            terminal = dotted.rsplit(".", 1)[-1]
            if terminal and _SEND_NAME_SHAPE.search(terminal):
                sites.append(Site(path, where, SEND, dotted, node.lineno))

    return sites


def scan_scopes(
    scopes: Iterable[Scope], sources: Mapping[str, str]
) -> list[Site]:
    """Scan a set of scopes against an explicit path->source mapping.

    Taking sources as a mapping is what lets the tripwire's own tests
    exercise it on synthetic code without touching the live tree.
    """
    sites: list[Site] = []
    for scope in scopes:
        sites.extend(
            scan_source(scope.path, sources[scope.path], scope.qualname)
        )
    return sites


def read_sources(root: Path, scopes: Iterable[Scope]) -> dict[str, str]:
    return {scope.path: (root / scope.path).read_text() for scope in scopes}


def inventory(sites: Iterable[Site]) -> dict[str, int]:
    """Construct-anchored counts. No line numbers: see the module docstring."""
    counts: dict[str, int] = {}
    for site in sites:
        counts[site.key] = counts.get(site.key, 0) + 1
    return counts


def scan_repo(root: Path | None = None) -> list[Site]:
    root = repo_root() if root is None else root
    return scan_scopes(OWNER_PATH_SCOPES, read_sources(root, OWNER_PATH_SCOPES))


FROZEN_PATH = "tests/data/owner_path_egress_tripwire.frozen.json"


def load_frozen(root: Path | None = None) -> dict[str, int]:
    root = repo_root() if root is None else root
    payload = json.loads((root / FROZEN_PATH).read_text())
    return dict(payload["inventory"])


def freeze(root: Path | None = None) -> str:
    """Regenerate the frozen inventory from the tree.

    The frozen file is MACHINE-DERIVED and must stay so. Hand-editing a
    count to make the build green is the failure this whole shape exists
    to make visible, so the regeneration path is the only supported way
    to update it -- and updating it is meant to be a deliberate act with
    a human reading the diff.
    """
    root = repo_root() if root is None else root
    counts = inventory(scan_repo(root))
    payload = {
        "_": (
            "MACHINE-DERIVED. Regenerate with "
            "`python -m tests.owner_path_egress_tripwire --freeze`. "
            "This is a TRIPWIRE inventory, NOT a census of Maez's mouths "
            "and NOT a completeness proof -- see the module docstring and "
            "KNOWN_BLIND_SPOTS."
        ),
        "inventory": dict(sorted(counts.items())),
    }
    return json.dumps(payload, indent=2, sort_keys=False) + "\n"


if __name__ == "__main__":  # pragma: no cover - maintenance entry point
    import sys

    if "--freeze" in sys.argv:
        root = repo_root()
        (root / FROZEN_PATH).write_text(freeze(root))
        print(f"froze {len(load_frozen(root))} entries -> {FROZEN_PATH}")
    else:
        for site in sorted(scan_repo(), key=lambda s: (s.path, s.lineno)):
            print(f"{site.path}:{site.lineno}\t{site.kind}\t{site.qualname}\t{site.detail}")
