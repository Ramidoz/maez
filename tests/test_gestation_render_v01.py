import hashlib
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.evolution.gestation_memory import GestationMemory

REPO = Path(__file__).resolve().parents[1]
# Source to an ALREADY-COMMITTED doc (the v0 spec) so `git show HEAD:doc` resolves.
_DOC = "docs/superpowers/specs/2026-06-10-gestation-memory-v0-design.md"


def _src(substr):
    commit = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    content = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{commit}:{_DOC}"], capture_output=True, text=True
    ).stdout
    excerpt = next(line for line in content.splitlines() if substr in line)
    return (
        {"kind": "doc", "ref": _DOC, "commit": commit,
         "excerpt_hash": hashlib.sha256(excerpt.encode("utf-8")).hexdigest()},
        excerpt,
    )


class RenderV01Tests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.gm = GestationMemory(Path(self._tmp.name) / "g.db")
        self.src, self.ex = _src("baby book made from receipts")

    def tearDown(self):
        self._tmp.cleanup()

    def _claim(self, text, kind="fact", typ="milestone", conf="documented", scar=False):
        return self.gm.record_claim(
            claim_text=text, claim_kind=kind, type=typ, confidence=conf,
            sources=[self.src], source_excerpts={0: self.ex}, observed_by="claude", scar=scar,
        )

    def test_milestone_fact_rendered_exactly_once_in_what_changed(self):
        self._claim("A milestone happened.", typ="milestone")
        out = self.gm.render()
        self.assertEqual(out.count("A milestone happened."), 1)
        self.assertIn("## What changed", out)
        self.assertGreater(out.index("A milestone happened."), out.index("## What changed"))

    def test_empty_what_happened_is_omitted(self):
        self._claim("A milestone happened.", typ="milestone")
        self.assertNotIn("## What happened", self.gm.render())

    def test_scar_in_wrong_section_only(self):
        self._claim("It went wrong, then fixed.", typ="no_go", scar=True)
        out = self.gm.render()
        self.assertEqual(out.count("It went wrong, then fixed."), 1)
        self.assertGreater(out.index("It went wrong, then fixed."), out.index("## What went wrong"))
        self.assertNotIn("## What changed", out)

    def test_type_and_confidence_shown_on_line(self):
        self._claim("A milestone happened.", typ="milestone", conf="documented")
        self.assertIn("[milestone/documented]", self.gm.render())

    def test_interpretation_quarantined(self):
        self._claim("A meaning drawn.", kind="interpretation", typ="milestone", conf="inferred")
        out = self.gm.render()
        self.assertIn("## Interpretations", out)
        self.assertGreater(out.index("A meaning drawn."), out.index("## Interpretations"))

    def test_corrections_history_shows_superseded_with_replacement(self):
        old = self._claim("We believed X.")
        new = self._claim("Corrected to Y.")
        self.gm.supersede(old.claim_id, new.claim_id)
        out = self.gm.render()
        self.assertIn("## Corrections history", out)
        self.assertIn("We believed X.", out)
        self.assertIn("Corrected to Y.", out)
        # the superseded claim appears only in the tail (after the header)
        self.assertGreater(out.index("We believed X."), out.index("## Corrections history"))

    def test_no_corrections_history_when_none(self):
        self._claim("A milestone happened.")
        self.assertNotIn("## Corrections history", self.gm.render())

    def test_corrections_history_method(self):
        old = self._claim("old")
        new = self._claim("new")
        self.gm.supersede(old.claim_id, new.claim_id)
        pairs = self.gm.corrections_history()
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0][0].claim_id, old.claim_id)
        self.assertEqual(pairs[0][1].claim_id, new.claim_id)


if __name__ == "__main__":
    unittest.main()
