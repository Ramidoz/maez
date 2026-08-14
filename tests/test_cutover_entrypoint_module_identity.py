"""ONE copy of the cutover module per process, or R11 cannot recognise itself.

`python3 -m scripts.cuda_cutover` -- the documented owner invocation -- executes
this file as `__main__` and leaves `scripts.cuda_cutover` UNIMPORTED. The R11
exemption boundary deliberately refuses to accept a caller's envelope and
rebuilds it from durable evidence instead, and it reaches the rebuilder by
`from scripts import cuda_cutover`. Under `-m` that import used to load a
SECOND copy of the module, with its own `ValidatedCutoverSelection` class. The
rebuild then rejected the running ceremony's own selection on type identity,
the rebuilt envelope came back `None`, and the mint refused with

    ExemptionMintRefused: exemption envelope does not match the durable
    selection

which named the wrong cause: the two envelopes never differed field by field,
one of them was never built. Every existing test imports the module under its
dotted name, so a single copy existed and no unit test could see this. It cost
one live ceremony run to find.

These tests emulate the `-m` import condition faithfully -- module body executed
with `__name__ == "__main__"`, registered in `sys.modules` as `__main__`, dotted
name unset -- in a clean subprocess. The `main()` tail is truncated, so no
ceremony runs, no store is opened and no key is tapped.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CUTOVER_SOURCE = REPO_ROOT / "scripts" / "cuda_cutover.py"
ENTRYPOINT_TAIL = '\nif __name__ == "__main__":'

#: Executed in the child before the emulated module body. Loads `scripts.
#: cuda_cutover`'s source, truncates the `main()` tail, and executes it exactly
#: as `runpy` would for `-m`: as `__main__`, absent from `sys.modules` under its
#: dotted name.
_EMULATE_DASH_M = f'''
import importlib.util, sys
sys.path.insert(0, {str(REPO_ROOT)!r})

source = open({str(CUTOVER_SOURCE)!r}).read()
marker = {ENTRYPOINT_TAIL!r}
assert source.count(marker) == 1, "entrypoint tail moved -- emulation would run main()"
body = source.split(marker)[0]

spec = importlib.util.find_spec("scripts.cuda_cutover")
entry = importlib.util.module_from_spec(spec)
entry.__name__ = "__main__"
sys.modules["__main__"] = entry
exec(compile(body, {str(CUTOVER_SOURCE)!r}, "exec"), entry.__dict__)
'''


def _run_under_emulated_dash_m(child_body: str) -> subprocess.CompletedProcess[str]:
    """Run `child_body` in a clean interpreter that believes it is `-m`.

    A subprocess is required, not a convenience: this pytest process has
    already imported `scripts.cuda_cutover` under its dotted name, which is the
    single-copy world the bug hides in.
    """
    return subprocess.run(
        [sys.executable, "-c", _EMULATE_DASH_M + child_body],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(REPO_ROOT),
    )


def test_dash_m_entrypoint_is_the_only_copy_of_the_cutover_module() -> None:
    """`from scripts import cuda_cutover` must reach the RUNNING ceremony."""
    result = _run_under_emulated_dash_m(
        """
from scripts import cuda_cutover as reimported

print("same_module:", reimported is entry)
print("same_selection_class:",
      reimported.ValidatedCutoverSelection is entry.ValidatedCutoverSelection)
print("same_refusal_class:",
      reimported.CutoverRefusal is entry.CutoverRefusal)
"""
    )

    assert result.returncode == 0, result.stderr
    assert "same_module: True" in result.stdout, result.stdout
    assert "same_selection_class: True" in result.stdout, result.stdout
    assert "same_refusal_class: True" in result.stdout, result.stdout


def test_a_second_copy_already_in_the_process_refuses_rather_than_diverges() -> None:
    """An ambiguous process is refused, not silently papered over.

    If something else has already claimed the dotted name, registering cannot
    make the copies one. That is the state this whole file exists to prevent,
    so it raises at import rather than letting the ceremony run toward a
    refusal that names the wrong cause.
    """
    result = _run_under_emulated_dash_m("print('unreachable')")

    # Pre-seed a foreign copy of the dotted name, then re-run the emulation.
    seeded = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, types, importlib.util\n"
            "imposter = types.ModuleType('scripts.cuda_cutover')\n"
            # Carries the real spec, so the emulation still resolves the file;
            # it is a different module OBJECT, which is the whole hazard.
            "imposter.__spec__ = importlib.util.find_spec('scripts.cuda_cutover')\n"
            "sys.modules['scripts.cuda_cutover'] = imposter\n"
            + _EMULATE_DASH_M,
        ],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(REPO_ROOT),
    )

    assert result.returncode == 0, result.stderr
    assert seeded.returncode != 0
    assert "two copies of scripts.cuda_cutover" in seeded.stderr, seeded.stderr


def test_r11_mint_accepts_the_running_ceremonys_own_selection_under_dash_m() -> None:
    """The end-to-end witness: the refusal that blocked the live tap is gone.

    The two grounds that read repository state -- birth and the owner's bench
    receipt -- are stubbed here so this asserts exactly one thing: that the
    envelope the ceremony builds and the envelope R11 rebuilds from durable
    evidence are the SAME envelope. The equality check itself is untouched.
    """
    result = _run_under_emulated_dash_m(
        """
import hashlib
from types import SimpleNamespace

from core.governance import s7_consultation_exemption as exemption_mod

# Grounds that read live repository state, held constant. Not tap evidence.
exemption_mod.born_by_any_signal = lambda: False
exemption_mod._quality_receipt_still_matches = lambda: True


def digest(label):
    return hashlib.sha256(("identity-fixture:" + label).encode()).hexdigest()


# Built by the ENTRY copy, exactly as the running ceremony builds it.
selected = entry.ValidatedCutoverSelection(
    completion_locator="completion-identity-fixture.json",
    completion=None,
    admission=None,
    receipt_ref="receipt-identity-fixture.json",
    receipt=SimpleNamespace(binding_sha256=digest("receipt-binding")),
    receipt_bytes=b"fixture",
    regenerated_receipt_bytes=b"fixture",
    receipt_file_sha256=digest("receipt-file"),
    authorization=SimpleNamespace(
        binding_sha256=digest("authorization-binding"),
        rollback_manifest_sha256=digest("rollback"),
        window_id="cutover-window-identity-fixture",
        issued_at="2026-08-13T12:00:00Z",
        expires_at="2026-08-13T16:00:00Z",
    ),
    authorization_file_sha256=digest("authorization-file"),
    bundle=SimpleNamespace(
        runtime_identity_doc=SimpleNamespace(file_sha256=digest("runtime-identity"))
    ),
    precondition_hash=digest("precondition"),
    operation_affected_refs={},
    affected_refs=("host:local",),
    _selection_token=entry._VALIDATED_CUTOVER_SELECTION_TOKEN,
)

envelope = entry._cutover_envelope_from_durable_selection(selected)
minted = exemption_mod.mint_consultation_exemption(
    envelope=envelope,
    durable_cutover_selection=selected,
    created_at="2026-08-13T12:00:00Z",
)
print("minted_action:", minted.action)
"""
    )

    assert "ExemptionMintRefused" not in result.stderr, result.stderr
    assert result.returncode == 0, result.stderr
    assert "minted_action: model_routing.cutover_cuda" in result.stdout, result.stdout
