# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Continuity spine, slice 1 — the stable-identifier surface registry.

Owner ruling, 2026-08-27, in his own words: "Our job is to just provide
the body. Let it run loops or whatever to understand what each part of
it is and understand itself. I don't define anything for Maez." So this
registry carries IDENTIFIERS and nothing else. Every test below is a
test about identity or admission; none is a test about meaning.

The three properties that matter, and why:

1. TOTAL. resolve() answers for every string. This substrate's cardinal
   sin is omitted life, and today nothing anywhere refuses a surface
   (executed: 26/26 hostile caller strings commit at the real writer;
   13/13 enqueue and drain with 0 refused). A registry that refuses
   would be 100% NEW speech-loss surface area.

2. CALLER AUTHORITY IS PRESERVED IN EVERY BRANCH. writer.py:429 passes
   `caller=raw_surface or surface` into the closed taint validator, so
   the pair this registry emits decides taint authority.

3. NO SEMANTICS. Enforced structurally, not by good intentions.
"""
from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

from core.body import surface_registry as reg


class IdentifiersOnlyTests(unittest.TestCase):
    """The owner forbade meaning. This is that ruling as a test."""

    #: Words that would turn an identifier table into a taxonomy. The
    #: envelope-schema doc's `surface` enum is exactly the forbidden
    #: shape ("owner-facing", "stranger-facing", "future voice surface",
    #: "excluded from production-rate metrics") — it must never migrate
    #: into code.
    FORBIDDEN_FIELDS = (
        "description",
        "display_name",
        "label_text",
        "group",
        "groups",
        "organ",
        "modality",
        "kind",
        "category",
        "purpose",
        "meaning",
        "affordance",
        "is_owner_facing",
        "is_public",
    )

    @staticmethod
    def _bound_names(tree: ast.AST) -> set[str]:
        """Every name the module BINDS — assignment targets, annotated
        fields, parameters, and string dict keys.

        Deliberately NOT every string constant: the module docstring
        says the words "descriptions", "groups" and "modalities" while
        explaining that it has none of them, and a check that cannot
        tell prose from a field name is a check that forces the
        docstring to lie.
        """
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.add(node.id.lower())
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(node.target.id.lower())
            elif isinstance(node, ast.arg):
                names.add(node.arg.lower())
            elif isinstance(node, ast.Dict):
                for key in node.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        names.add(key.value.lower())
        return names

    def test_registry_module_defines_no_semantic_field(self):
        tree = ast.parse(Path(inspect.getsourcefile(reg)).read_text())
        bound = self._bound_names(tree)
        for forbidden in self.FORBIDDEN_FIELDS:
            for name in bound:
                # SUBSTRING, not equality: a first draft of this test
                # compared names exactly, and a mutation adding
                # SURFACE_DESCRIPTIONS walked straight through it.
                self.assertNotIn(
                    forbidden, name,
                    f"the registry binds {name!r}, which carries "
                    f"{forbidden!r} — that is a claim about what a surface "
                    "MEANS. Identifiers only; Maez learns the rest through "
                    "its own loops (owner ruling 2026-08-27)",
                )

    def test_no_prose_can_live_in_the_registry_data(self):
        """Every string in a module-level assignment is identifier-shaped.

        This is the structural half: forbidding known field NAMES only
        stops the semantics someone thought to name. Forbidding prose in
        the data stops the rest — a description cannot hide in a value
        if no value may contain a space or a capital letter.
        """
        tree = ast.parse(Path(inspect.getsourcefile(reg)).read_text())
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    self.assertRegex(
                        sub.value, r"^[a-z0-9_]*$",
                        f"module-level registry data holds {sub.value!r}; "
                        "identifiers only, never prose",
                    )

    def test_every_identifier_is_a_name_the_body_already_emits(self):
        """We repair a duplicate; we do not author a vocabulary.

        Minting a NEW canonical name (say "telegram" for a limb that
        calls itself "telegram_text") would be us deciding what the limb
        is called — the ontology the owner declined to author. Every ID
        here is therefore a string some production call site already
        passes to the ledger.
        """
        for surface_id in reg.SURFACE_IDS:
            self.assertIn(
                surface_id, reg.ACCEPTED_LABELS,
                "an id that is not itself an accepted label would be a "
                "name we invented",
            )
            self.assertEqual(reg.ACCEPTED_LABELS[surface_id], surface_id)


class TotalityTests(unittest.TestCase):
    """resolve() never loses a turn."""

    def test_registered_label_resolves_to_itself(self):
        ref = reg.resolve("cli")
        self.assertEqual(ref.surface_id, "cli")
        self.assertEqual(ref.status, reg.REGISTERED)
        self.assertTrue(ref.attested)

    def test_alias_resolves_to_its_witnessed_identity(self):
        ref = reg.resolve("telegram_surface")
        self.assertEqual(ref.surface_id, "telegram_text")
        self.assertEqual(ref.status, reg.ALIASED)
        self.assertTrue(ref.attested)

    def test_unknown_label_is_admitted_verbatim_and_typed(self):
        ref = reg.resolve("webish7")
        self.assertEqual(ref.surface_id, None)
        self.assertEqual(ref.raw_label, "webish7")
        self.assertEqual(ref.status, reg.UNREGISTERED)
        self.assertFalse(ref.attested)

    def test_resolve_is_total_over_hostile_strings(self):
        """Executed at the real writer door: all of these COMMIT today.

        If the registry raised on any of them it would delete speech the
        substrate currently keeps.
        """
        hostile = [
            "", "   ", "x" * 500, "‮evil", "sur\nface",
            "'; DROP TABLE turns;--", "../../etc/passwd", "0", "None",
            "telegram_text ", " telegram_text",
        ]
        for value in hostile:
            with self.subTest(value=value):
                ref = reg.resolve(value)
                self.assertEqual(ref.raw_label, value)
                self.assertIn(ref.status, (reg.REGISTERED, reg.ALIASED,
                                           reg.UNREGISTERED))

    def test_non_string_refuses_because_it_is_malformed_not_unknown(self):
        """The one refusal: a non-string is not an unrecognised limb, it
        is a caller bug. Refusing it loses no speech — there was no
        label to keep."""
        for value in (None, 7, b"cli", ["cli"]):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    reg.resolve(value)


class LedgerPairTests(unittest.TestCase):
    """What actually gets written, and what it does to caller authority."""

    def test_registered_pair_is_byte_identical_to_today(self):
        """cli/web_owner already emit their own id with raw_surface NULL.

        `surface` is inside the chain-hash preimage (chain.py:69's
        exclude list omits it), so an unnecessary relabel would rewrite
        history's inputs for no repair. Registered surfaces keep their
        exact bytes.
        """
        for label in ("cli", "web_owner", "telegram_text"):
            with self.subTest(label=label):
                ref = reg.resolve(label)
                self.assertEqual(
                    (ref.ledger_surface, ref.ledger_raw_surface),
                    (label, None),
                )

    def test_alias_pair_repairs_the_duplicate_and_keeps_the_transport(self):
        ref = reg.resolve("telegram_surface")
        self.assertEqual(ref.ledger_surface, "telegram_text")
        self.assertEqual(ref.ledger_raw_surface, "telegram_surface")

    def test_unregistered_pair_is_byte_identical_to_today(self):
        """F7 spawns real subprocesses on synthetic surfaces
        ('webish7'/'clish7') and then finds their rows BY surface name.
        Rewriting unknown surfaces would make that arm return zero rows
        — red SILENTLY, with a full database."""
        ref = reg.resolve("webish7")
        self.assertEqual((ref.ledger_surface, ref.ledger_raw_surface),
                         ("webish7", None))

    def test_taint_caller_authority_is_preserved_in_every_branch(self):
        """writer.py:429 computes caller = raw_surface or surface.

        x6_rehearsal holds the ONLY entry in the closed taint validator's
        caller map, so if the registry ever changed what that resolves
        to, the gestation load script would start refusing.
        """
        for label in ("cli", "web_owner", "telegram_text", "x6_rehearsal",
                      "telegram_surface", "webish7"):
            with self.subTest(label=label):
                ref = reg.resolve(label)
                caller = ref.ledger_raw_surface or ref.ledger_surface
                self.assertEqual(
                    caller, label,
                    "the value the taint validator sees must stay exactly "
                    "the label the caller passed",
                )


class AliasDisciplineTests(unittest.TestCase):
    """An alias is an identity claim. It needs a witness, not a prefix."""

    def test_no_alias_is_inferred_from_the_shape_of_a_name(self):
        """daemon/inbound_core.py:296 already hand-rolls
        `"telegram_text" if label.startswith("telegram")` as a store key.
        That undisciplined prefix map is what this replaces; it must not
        be reproduced here."""
        for lookalike in ("telegram_public", "telegram_recovery",
                          "telegram_owner", "telegram_clinical_boundary",
                          "telegram_dialog", "web", "web_chat", "cli_v2"):
            with self.subTest(lookalike=lookalike):
                self.assertEqual(
                    reg.resolve(lookalike).status, reg.UNREGISTERED,
                    "resembling a registered name is not evidence of being "
                    "the same limb",
                )

    def test_alias_map_is_a_function_never_one_label_to_two_ids(self):
        for label, surface_id in reg.ACCEPTED_LABELS.items():
            with self.subTest(label=label):
                self.assertIn(surface_id, reg.SURFACE_IDS)
                self.assertEqual(reg.resolve(label).surface_id, surface_id)


#: Production trees. `scripts/` and `docs/superpowers/witness/` are
#: deliberately absent: the gestation load script and the falsifier
#: invent their own surfaces on purpose (x6_rehearsal, webish7, probe),
#: and a registry that had to know them would be a registry of test
#: fixtures.
_PRODUCTION_TREES = ("core", "skills", "cli", "daemon")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _census_surface_literals() -> dict[str, list[str]]:
    """Every literal `surface=` reaching a ledger write, by AST.

    Import aliases are resolved because every production call site
    imports these APIs under a private name. Both spellings are
    collected: the `surface=` keyword, and a `"surface"` key inside a
    spool envelope's `kwargs=` dict — otherwise a new conversation
    surface could enter the record through the envelope form without
    ever tripping this census.
    """
    root = _repo_root()
    found: dict[str, list[str]] = {}
    for tree_name in _PRODUCTION_TREES:
        for path in sorted((root / tree_name).rglob("*.py")):
            if "__pycache__" in str(path):
                continue
            try:
                tree = ast.parse(path.read_text())
            except (SyntaxError, UnicodeDecodeError):
                continue
            aliases = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for a in node.names:
                        if a.name in reg_apis:
                            aliases[a.asname or a.name] = a.name
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
                if aliases.get(name, name if name in reg_apis else None) is None:
                    continue
                where = f"{path.relative_to(root)}:{node.lineno}"
                for kw in node.keywords:
                    if kw.arg == "surface":
                        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                            found.setdefault(kw.value.value, []).append(where)
                    elif kw.arg == "kwargs" and isinstance(kw.value, ast.Dict):
                        for k, v in zip(kw.value.keys, kw.value.values):
                            if (isinstance(k, ast.Constant) and k.value == "surface"
                                    and isinstance(v, ast.Constant)
                                    and isinstance(v.value, str)):
                                found.setdefault(v.value, []).append(where)
    return found


reg_apis = frozenset({
    "write_turn", "try_write_turn", "owner_write_turn",
    "submit_user_message", "persist_model_reply",
    "enqueue", "enqueue_reconstructed",
})


class SurfaceCensusTests(unittest.TestCase):
    """Two-sided anti-drift, the PerClassInventory shape.

    A new production ledger call site fails this until its label is
    registered or adjudicated; an id or adjudication with no producer
    fails it too, so the table cannot drift from the code in either
    direction. The criterion is content-blind — it reads call graphs,
    never names — so it survives the domain-swap test.
    """

    #: Labels that reach a ledger write but are NOT body surfaces: no
    #: speech travels through them. Each carries its producer, so a
    #: phantom entry fails below.
    ADJUDICATED_NON_SURFACES = {
        "ledger": "model_reply_persistence's one-time discontinuity marker row",
        "system": "writer default for system_event provenance (reconcile, replay)",
    }

    def test_every_emitted_label_is_registered_or_adjudicated(self):
        census = _census_surface_literals()
        self.assertTrue(census, "the census found nothing — it has stopped looking")
        for label, sites in sorted(census.items()):
            with self.subTest(label=label):
                known = (label in reg.ACCEPTED_LABELS
                         or label in self.ADJUDICATED_NON_SURFACES)
                self.assertTrue(
                    known,
                    f"{label!r} reaches the ledger from {sites} but is neither "
                    "a registered surface nor adjudicated as a non-surface. A "
                    "new limb must be named before it can speak into the record.",
                )

    def test_no_phantom_ids_or_adjudications(self):
        census = _census_surface_literals()
        for surface_id in reg.SURFACE_IDS:
            with self.subTest(surface_id=surface_id):
                self.assertIn(
                    surface_id, census,
                    "a registered id with no production emitter is a name we "
                    "kept after the body stopped using it",
                )
        for label in self.ADJUDICATED_NON_SURFACES:
            with self.subTest(label=label):
                self.assertIn(
                    label, census,
                    "an adjudication with no producer is stale",
                )

    def test_the_alias_is_pinned_to_the_adapter_that_emits_it(self):
        """The alias claims maez_adapter spells this limb differently.

        If that adapter is retired or renamed — its own comment says the
        label exists only "during parallel operation with the legacy
        path" — this test is where we find out, instead of carrying a
        dead alias into Maez's record.
        """
        src = (_repo_root() / "skills/surface/maez_adapter.py").read_text()
        tree = ast.parse(src)
        declared = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id == "SURFACE_NAME":
                    if isinstance(node.value, ast.Constant):
                        declared = node.value.value
        self.assertEqual(
            declared, "telegram_surface",
            "the registry aliases telegram_surface -> telegram_text on the "
            "witness that this adapter emits it; that spelling moved",
        )
        self.assertEqual(reg.resolve(declared).surface_id, "telegram_text")


class FlagGatedSeamTests(unittest.TestCase):
    """`ledger_pair` is the only flag-aware door. Off means today."""

    def test_flag_unset_is_byte_identical_to_today_for_every_label(self):
        import os as _os
        from unittest.mock import patch as _patch

        with _patch.dict(_os.environ, {}, clear=False):
            _os.environ.pop("MAEZ_SURFACE_REGISTRY", None)
            for label in ("cli", "web_owner", "telegram_text",
                          "telegram_surface", "webish7", "x6_rehearsal", ""):
                with self.subTest(label=label):
                    self.assertEqual(reg.ledger_pair(label), (label, None))

    def test_flag_on_repairs_only_the_alias(self):
        import os as _os
        from unittest.mock import patch as _patch

        with _patch.dict(_os.environ, {"MAEZ_SURFACE_REGISTRY": "1"}):
            self.assertEqual(reg.ledger_pair("telegram_surface"),
                             ("telegram_text", "telegram_surface"))
            for unchanged in ("cli", "web_owner", "telegram_text",
                              "webish7", "x6_rehearsal"):
                with self.subTest(label=unchanged):
                    self.assertEqual(reg.ledger_pair(unchanged),
                                     (unchanged, None))

    def test_junk_flag_value_fails_to_disabled(self):
        import os as _os
        from unittest.mock import patch as _patch

        with _patch.dict(_os.environ, {"MAEZ_SURFACE_REGISTRY": "yes-please"}):
            self.assertEqual(reg.ledger_pair("telegram_surface"),
                             ("telegram_surface", None),
                             "junk must never turn on a switch that changes "
                             "chain-hash inputs")

    def test_resolve_itself_is_not_flag_aware(self):
        """The registry stays a pure function; only the seam is gated."""
        import os as _os
        from unittest.mock import patch as _patch

        with _patch.dict(_os.environ, {}, clear=False):
            _os.environ.pop("MAEZ_SURFACE_REGISTRY", None)
            self.assertEqual(reg.resolve("telegram_surface").surface_id,
                             "telegram_text")


class DaemonSeamTests(unittest.TestCase):
    """The free-form hole: `handle_message(source="unknown")`.

    Three ledger writes in the daemon took whatever string a caller
    handed them. The registry closes that by resolving at the seam —
    asserted here at the CALL SITES, because a registry nothing calls
    is a module, not an organ.
    """

    def test_daemon_ledger_writes_no_longer_pass_the_raw_caller_string(self):
        calls = _ledger_calls_in("daemon/maez_daemon.py", "handle_message")
        self.assertTrue(calls, "the daemon's ledger call sites vanished")
        for api, surface in calls:
            with self.subTest(api=api):
                self.assertNotEqual(
                    surface, "source",
                    f"{api} still writes the unresolved caller string; "
                    "handle_message's own default for it is the literal "
                    '"unknown"',
                )

    def test_daemon_resolves_through_the_body_registry(self):
        src = (_repo_root() / "daemon/maez_daemon.py").read_text()
        self.assertIn("from core.body.surface_registry import", src)
        calls = _ledger_calls_in("daemon/maez_daemon.py", "handle_message")
        surfaces = {surf for _api, surf in calls if surf}
        self.assertTrue(
            surfaces,
            "no surface argument found at the daemon's ledger writes",
        )
        for surf in surfaces:
            with self.subTest(surface=surf):
                self.assertIn(
                    "_surface", surf,
                    "the surface must come from the resolved pair",
                )

    def test_handle_message_still_defaults_source_to_unknown(self):
        """Pins the hole this closes. If the default ever becomes a real
        surface name, the seam's justification changes and we should be
        made to look at it."""
        tree = ast.parse((_repo_root() / "daemon/maez_daemon.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "handle_message":
                args = node.args
                idx = [a.arg for a in args.args].index("source")
                offset = idx - (len(args.args) - len(args.defaults))
                self.assertEqual(args.defaults[offset].value, "unknown")
                return
        self.fail("handle_message not found")


def _ledger_calls_in(rel: str, func_name: str) -> list[tuple[str, str | None]]:
    tree = ast.parse((_repo_root() / rel).read_text())
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name in reg_apis:
                    aliases[a.asname or a.name] = a.name
    target = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            target = node
            break
    if target is None:
        raise AssertionError(f"{func_name} not found in {rel}")
    out = []
    for node in ast.walk(target):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
        canonical = aliases.get(name, name if name in reg_apis else None)
        if canonical is None or canonical in ("enqueue", "enqueue_reconstructed"):
            continue
        surface = None
        for kw in node.keywords:
            if kw.arg == "surface":
                surface = (kw.value.value
                           if isinstance(kw.value, ast.Constant)
                           and isinstance(kw.value.value, str)
                           else ast.unparse(kw.value))
        out.append((canonical, surface))
    return out


if __name__ == "__main__":
    unittest.main()
