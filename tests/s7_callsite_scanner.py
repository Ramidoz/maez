"""Shared qualified-callsite scanner.

Lifted verbatim from the initializer guard, which was hardened over
several rounds against exactly the bypasses a fresh implementation keeps
reinventing: class and closure scopes collapsing to a bare name, plain
AND annotated assignment aliases, reverse-ordered alias chains, and
getattr-by-string. Writing a second, weaker copy for each new authority
is how those bypasses come back.

Returns one entry PER OCCURRENCE, so multiplicity is preserved: two calls
in one method are two entries, and a second call cannot hide behind the
first.
"""

from __future__ import annotations

def find_callsites(source: str, target: str) -> list[str]:
    """Fully qualified callers of `target` in one source string.

    Three shapes defeated earlier versions:

    * `Hidden.main` and `helper.<locals>.main` both recorded as `::main`,
      so a call inside a class or a nested function satisfied an allowlist
      written for the module-level one;
    * `init: object = s7.initialise_authorization_store` -- an ANNOTATED
      assignment -- aliased the seam invisibly;
    * a call is only syntax. `if False: initialise_authorization_store()`
      appears here and never runs, which is why a behavioural witness
      accompanies this scanner rather than replacing it.

    Returns qualified names, so scope is part of the identity.
    """
    import ast
    import textwrap

    tree = ast.parse(textwrap.dedent(source))
    aliases: set[str] = {
        a.asname
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for a in node.names
        if a.asname and a.name.split(".")[-1] == target
    }

    def alias_tail(value):
        if isinstance(value, ast.Attribute):
            return value.attr
        if isinstance(value, ast.Name):
            return value.id
        return None

    # A TRUE fixed point. Three passes resolved only three links, so a
    # reverse-ordered four-link chain stayed invisible.
    changed = True
    while changed:
        before = set(aliases)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = [node.target], node.value
            else:
                continue
            if value is None:
                continue
            tail = alias_tail(value)
            if tail == target or tail in aliases:
                aliases |= {t.id for t in targets if isinstance(t, ast.Name)}
        changed = aliases != before

    found: list[str] = []

    def walk(node, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, f"{scope}.{child.name}" if scope else child.name)
                continue
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inner = (
                    f"{scope}.<locals>.{child.name}"
                    if scope and not scope[0].isupper()
                    else (f"{scope}.{child.name}" if scope else child.name)
                )
                walk(child, inner)
                continue
            if isinstance(child, ast.Call):
                name = (
                    child.func.attr
                    if isinstance(child.func, ast.Attribute)
                    else getattr(child.func, "id", None)
                )
                if name == target or name in aliases:
                    found.append(scope or "<module>")
                elif (
                    name == "getattr"
                    and len(child.args) > 1
                    and isinstance(child.args[1], ast.Constant)
                    and child.args[1].value == target
                ):
                    found.append(scope or "<module>")
            walk(child, scope)

    walk(tree, "")
    return found
