from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBJECTIVE = ROOT / "core" / "evolution" / "subjective_duration.py"
DAEMON = ROOT / "daemon" / "maez_daemon.py"
TELEGRAM = ROOT / "skills" / "telegram_voice.py"
WEB = ROOT / "skills" / "web_interface.py"
SURFACE_ADAPTER = ROOT / "skills" / "surface" / "maez_adapter.py"
SELF_CARD_TIME = ROOT / "core" / "routing" / "self_card_time.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _production_python_paths() -> list[Path]:
    skipped_parts = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "docs",
        "scripts",
        "tests",
    }
    return sorted(
        path
        for path in ROOT.rglob("*.py")
        if not (set(path.relative_to(ROOT).parts) & skipped_parts)
    )


def _imports_subjective_duration(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "core.evolution.subjective_duration" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "core.evolution.subjective_duration":
                return True
            if node.module == "core.evolution" and any(
                alias.name == "subjective_duration" for alias in node.names
            ):
                return True
    return False


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _temperament_write_violations(source: str, *, filename: str) -> list[str]:
    tree = ast.parse(source, filename=filename)
    forbidden_helpers = {"record_event", "write_temperament_event"}
    temperament_names: set[str] = {"self.temperament"}
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == "Temperament"
                ):
                    temperament_names.add(target.id)
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        attr = node.func.attr
        if attr not in forbidden_helpers:
            continue
        receiver = ast.unparse(node.func.value)
        if (
            receiver == "Temperament"
            or receiver in temperament_names
            or attr == "write_temperament_event"
        ):
            violations.append(f"{filename}:{node.lineno}:{ast.unparse(node)}")
    return violations


class SubjectiveDurationStaticBoundaryTests(unittest.TestCase):
    def test_subjective_duration_is_not_a_temperament_parameter(self):
        from core.evolution.temperament import PARAMETER_NAMES, PARAMETER_SET

        self.assertNotIn("subjective_duration", PARAMETER_NAMES)
        self.assertNotIn("subjective_duration", PARAMETER_SET)

    def test_subjective_duration_module_does_not_write_temperament(self):
        scan_roots = [SUBJECTIVE, DAEMON, TELEGRAM, WEB, Path(__file__)]
        violations: list[str] = []

        for path in scan_roots:
            if not path.exists():
                violations.append(f"{path}:missing")
                continue
            violations.extend(_temperament_write_violations(_source(path), filename=str(path)))

        self.assertEqual([], violations)

    def test_temperament_write_detector_catches_class_call_shape(self):
        violations = _temperament_write_violations(
            "from core.evolution.temperament import Temperament\n"
            "def bad():\n"
            "    Temperament.record_event('curiosity', 1.0)\n",
            filename="synthetic.py",
        )

        self.assertEqual(
            ["synthetic.py:3:Temperament.record_event('curiosity', 1.0)"],
            violations,
        )

    def test_anti_coercion_same_function_ast_boundary(self):
        forbidden_read_names = {
            "SubjectiveDuration",
            "subjective_duration_prompt_line",
            "perception_line",
        }
        outbound_markers = {
            "_reply_text",
            "_public_reply_text",
            "_public_owner_alert",
            "send_envelope",
            "send_telegram",
            "send_telegram_async",
            "send_exec_approval",
            "send_model_picker",
            "create_approval_card",
            "approval_card",
            "crisis_signal_writer",
            "_alert_rohit",
            "_maybe_tell_owner_unprompted",
            "_send_telegram_notice",
            "send_dev",
        }
        violations: list[str] = []

        def reads_subjective_duration(node: ast.AST, aliases: set[str]) -> bool:
            for child in ast.walk(node):
                if isinstance(child, ast.Name) and child.id in (forbidden_read_names | aliases):
                    return True
                if isinstance(child, ast.Attribute) and child.attr in forbidden_read_names:
                    return True
            return False

        def calls_outbound(node: ast.AST) -> bool:
            return any(
                isinstance(child, ast.Call) and (_call_name(child) in outbound_markers)
                for child in ast.walk(node)
            )

        for path in [DAEMON, TELEGRAM, WEB, SURFACE_ADAPTER]:
            tree = ast.parse(_source(path), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                aliases: set[str] = set()
                changed = True
                while changed:
                    changed = False
                    for assign in ast.walk(node):
                        if isinstance(assign, ast.Assign) and reads_subjective_duration(assign.value, aliases):
                            for target in assign.targets:
                                if isinstance(target, ast.Name) and target.id not in aliases:
                                    aliases.add(target.id)
                                    changed = True
                        elif (
                            isinstance(assign, ast.AnnAssign)
                            and assign.value is not None
                            and reads_subjective_duration(assign.value, aliases)
                            and isinstance(assign.target, ast.Name)
                            and assign.target.id not in aliases
                        ):
                            aliases.add(assign.target.id)
                            changed = True
                        elif (
                            isinstance(assign, ast.AugAssign)
                            and isinstance(assign.target, ast.Name)
                            and assign.target.id in aliases
                        ):
                            changed = changed or False

                for call in ast.walk(node):
                    if not isinstance(call, ast.Call) or _call_name(call) not in outbound_markers:
                        continue
                    call_inputs = list(call.args) + [kw.value for kw in call.keywords]
                    if any(reads_subjective_duration(arg, aliases) for arg in call_inputs):
                        violations.append(
                            f"{path}:{call.lineno}:{node.name}:subjective-duration outbound argument"
                        )

                for branch in ast.walk(node):
                    if isinstance(branch, (ast.If, ast.While)):
                        if reads_subjective_duration(branch.test, aliases) and (
                            any(calls_outbound(stmt) for stmt in branch.body)
                            or any(calls_outbound(stmt) for stmt in branch.orelse)
                        ):
                            violations.append(
                                f"{path}:{branch.lineno}:{node.name}:subjective-duration contact branch"
                            )
                    elif isinstance(branch, ast.IfExp):
                        if reads_subjective_duration(branch.test, aliases) and (
                            calls_outbound(branch.body) or calls_outbound(branch.orelse)
                        ):
                            violations.append(
                                f"{path}:{branch.lineno}:{node.name}:subjective-duration contact expression"
                            )

        self.assertEqual([], violations)

    def test_reviewed_prompt_surfaces_do_not_import_subjective_duration_at_module_scope(self):
        violations: list[str] = []
        # self_card_time is the Slice A reviewed read-only prompt adapter. It may
        # lazily import subjective_duration helpers, but never at module scope.
        for path in [DAEMON, TELEGRAM, WEB, SURFACE_ADAPTER, SELF_CARD_TIME]:
            tree = ast.parse(_source(path), filename=str(path))
            module_level = ast.Module(body=list(tree.body), type_ignores=[])
            for node in module_level.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)) and _imports_subjective_duration(
                    ast.Module(body=[node], type_ignores=[])
                ):
                    violations.append(f"{path.relative_to(ROOT)}:{node.lineno}:module-level")

        self.assertEqual([], violations)

    def test_subjective_duration_imports_stay_on_reviewed_prompt_surfaces(self):
        allowed_importers = {
            SUBJECTIVE.relative_to(ROOT),
            DAEMON.relative_to(ROOT),
            TELEGRAM.relative_to(ROOT),
            WEB.relative_to(ROOT),
            # Slice A reviewed read-only prompt adapter. It reads rhythm facts
            # for a deterministic self-card candidate; it is not an outbound
            # sender or owner-contact surface.
            SELF_CARD_TIME.relative_to(ROOT),
        }
        violations: list[str] = []

        for path in _production_python_paths():
            rel = path.relative_to(ROOT)
            tree = ast.parse(_source(path), filename=str(path))
            if _imports_subjective_duration(tree) and rel not in allowed_importers:
                violations.append(str(rel))

        self.assertEqual([], violations)

    def test_self_card_time_adapter_has_no_outbound_send_markers(self):
        outbound_markers = {
            "send_envelope",
            "send_telegram",
            "send_telegram_async",
            "send_exec_approval",
            "send_model_picker",
            "create_approval_card",
            "approval_card",
            "crisis_signal_writer",
            "_alert_rohit",
            "_maybe_tell_owner_unprompted",
            "_send_telegram_notice",
            "send_dev",
        }
        tree = ast.parse(_source(SELF_CARD_TIME), filename=str(SELF_CARD_TIME))
        violations = [
            f"{SELF_CARD_TIME.relative_to(ROOT)}:{node.lineno}:{_call_name(node)}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _call_name(node) in outbound_markers
        ]

        self.assertEqual([], violations)

    def test_surface_adapter_defaults_to_no_subjective_duration_owner_auth(self):
        text = _source(SURFACE_ADAPTER)
        tree = ast.parse(text, filename=str(SURFACE_ADAPTER))
        violations: list[str] = []

        self.assertNotIn("SubjectiveDurationOwnerAuth", text)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _call_name(node) != "handle_message":
                continue
            for keyword in node.keywords:
                if keyword.arg != "subjective_duration_owner_auth":
                    continue
                if not (isinstance(keyword.value, ast.Constant) and keyword.value.value is None):
                    violations.append(f"{SURFACE_ADAPTER}:{node.lineno}:non-None owner auth")

        self.assertEqual([], violations)

    def test_owner_auth_contract_and_prompt_insertion_sources_are_wired(self):
        daemon = _source(DAEMON)
        telegram = _source(TELEGRAM)
        web = _source(WEB)
        violations: list[str] = []

        for label, text, fragment in [
            ("daemon", daemon, "SubjectiveDurationOwnerAuth"),
            ("daemon", daemon, "subjective_duration_owner_auth"),
            ("daemon", daemon, "subjective_duration_prompt_line"),
            ("telegram", telegram, "subjective_duration_prompt_line"),
            ("web", web, "subjective_duration_prompt_line"),
        ]:
            if fragment not in text:
                violations.append(f"{label}:missing:{fragment}")

        if violations:
            self.fail(f"Missing subjective-duration wiring: {violations}")

        ui_route = daemon[daemon.index('@app.route("/message"') : daemon.index('@app.route("/internal/brain_loop"')]
        self.assertNotIn("SubjectiveDurationOwnerAuth", ui_route)
        self.assertNotIn("subjective_duration_owner_auth=", ui_route)

        handle = daemon[daemon.index("def handle_message(") :]
        self.assertLess(handle.index("system_state = format_snapshot"), handle.index("subjective_duration_prompt_line"))
        self.assertLess(handle.index("subjective_duration_prompt_line"), handle.index("public_ctx = self._get_public_context"))

        telegram_auth = telegram.index("if not self._is_authorized(user_id):")
        telegram_prompt = telegram.index("subjective_duration_prompt_line")
        telegram_memory = telegram.index("if memory_block:", telegram_prompt)
        self.assertLess(telegram_auth, telegram_prompt)
        self.assertLess(telegram_prompt, telegram_memory)

        web_owner = web.index("if owner_bridge:")
        web_line = web.index("subjective_duration_prompt_line")
        web_memory = web.index("owner_memory = memory.format_for_prompt", web_line)
        self.assertLess(web_owner, web_line)
        self.assertLess(web_line, web_memory)

    def test_prompt_phrase_constants_are_not_contact_pressure(self):
        if not SUBJECTIVE.exists():
            self.fail(f"{SUBJECTIVE}:missing")
        text = _source(SUBJECTIVE)
        forbidden = [
            "come back",
            "check in",
            "neglected",
            "abandoned",
            "you should",
            "please return",
        ]
        for fragment in forbidden:
            self.assertNotIn(fragment, text.lower())


if __name__ == "__main__":
    unittest.main()
