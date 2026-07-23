"""Sealed command and terminal boundary for the private CUDA bench."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from types import FrameType
from typing import Literal, Never

from scripts import cuda_bench_driver as driver


PUBLIC_COMMANDS = (
    "static-preflight",
    "rehearse",
    "vulkan-baseline",
    "cuda-candidate",
    "assemble-stage1",
)
_WATCHED_SIGNALS = frozenset({signal.SIGINT, signal.SIGTERM})
_CLI_RESERVED_OUTCOMES = frozenset({"cleanup_incomplete", "interrupted"})
_pthread_sigmask = signal.pthread_sigmask
_terminal_committed = False
_cleanup_incomplete_committing = False


class InvocationRefusal(Exception):
    """A non-echoing argparse refusal."""


@dataclass(frozen=True, slots=True)
class TerminalResult:
    status: Literal["ok", "refused", "failed"]
    outcome: str
    window_id: str | None
    artifact_ref: str | None
    artifact_sha256: str | None

    def __post_init__(self) -> None:
        if self.status not in {"ok", "refused", "failed"}:
            raise ValueError("terminal_status")
        if type(self.outcome) is not str or re.fullmatch(
            r"[a-z][a-z0-9_]{0,63}", self.outcome
        ) is None:
            raise ValueError("terminal_outcome")
        if (self.artifact_ref is None) != (self.artifact_sha256 is None):
            raise ValueError("terminal_artifact_pair")
        if self.window_id is not None and re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.:+-]{0,127}", self.window_id
        ) is None:
            raise ValueError("terminal_window_id")
        if self.artifact_ref is not None:
            parts = self.artifact_ref.split("/")
            if os.path.isabs(self.artifact_ref) or any(
                part in {"", ".", ".."} for part in parts
            ):
                raise ValueError("terminal_artifact_pair")
            if re.fullmatch(r"[0-9a-f]{64}", self.artifact_sha256 or "") is None:
                raise ValueError("terminal_artifact_pair")


class NonEchoingParser(argparse.ArgumentParser):
    def error(self, _message: str) -> Never:
        raise InvocationRefusal


def build_parser() -> NonEchoingParser:
    parser = NonEchoingParser(add_help=False)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in PUBLIC_COMMANDS:
        commands.add_parser(command, add_help=False)
    return parser


def _terminal_bytes(result: TerminalResult) -> bytes:
    return (
        json.dumps(asdict(result), sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _write_stdout(data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(1, view)
        if written <= 0:
            raise OSError("terminal_write")
        view = view[written:]


def _snapshot_pending_signal(explicit: int | None) -> int | None:
    pending = set(signal.sigpending()).intersection(_WATCHED_SIGNALS)
    if explicit in _WATCHED_SIGNALS:
        pending.add(signal.Signals(explicit))
    selected = signal.SIGTERM if signal.SIGTERM in pending else None
    if selected is None and signal.SIGINT in pending:
        selected = signal.SIGINT
    while True:
        current = set(signal.sigpending()).intersection(_WATCHED_SIGNALS)
        if not current:
            break
        signal.sigwait(current)
    return None if selected is None else int(selected)


def _exit_status(result: TerminalResult, signum: int | None = None) -> int:
    if signum is not None:
        return 128 + signum
    if result.outcome == "invocation_invalid":
        return 2
    if result.status == "ok":
        return 0
    if result.status == "refused":
        return 3
    return 4


def _commit_terminal(
    result: TerminalResult,
    *,
    interrupted_signum: int | None = None,
    interruption_fallback: TerminalResult | None = None,
) -> int:
    global _terminal_committed
    _terminal_committed = False
    preblock_signals: set[int] = set()
    if interrupted_signum in _WATCHED_SIGNALS:
        preblock_signals.add(int(interrupted_signum))
    old_mask: set[int] | None = None
    try:
        while True:
            try:
                old_mask = signal.pthread_sigmask(
                    signal.SIG_BLOCK, _WATCHED_SIGNALS
                )
                break
            except driver._CommandInterrupted as interrupted:
                preblock_signals.add(interrupted.signum)
        explicit = None
        if signal.SIGTERM in preblock_signals:
            explicit = int(signal.SIGTERM)
        elif signal.SIGINT in preblock_signals:
            explicit = int(signal.SIGINT)
        selected = _snapshot_pending_signal(explicit)
    except Exception:
        _terminal_committed = True
        if old_mask is not None:
            try:
                signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
            except Exception:
                pass
        return 4
    cleanup_dominates = (
        _cleanup_incomplete_committing or result.outcome == "cleanup_incomplete"
    )
    if cleanup_dominates:
        selected = None
    committed_result = result
    if selected is not None:
        binding = result if interruption_fallback is None else interruption_fallback
        committed_result = TerminalResult(
            "refused",
            "interrupted",
            binding.window_id,
            binding.artifact_ref,
            binding.artifact_sha256,
        )
    code = _exit_status(committed_result, selected)
    try:
        _write_stdout(_terminal_bytes(committed_result))
    except Exception:
        code = 4
    _terminal_committed = True
    try:
        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
    except driver._CommandInterrupted:
        pass
    except Exception:
        pass
    return code


def _on_command_signal(signum: int, _frame: FrameType | None) -> None:
    if _terminal_committed or _cleanup_incomplete_committing:
        return
    raise driver._CommandInterrupted(signum)


def _install_command_signal_scope() -> dict[signal.Signals, object]:
    previous: dict[signal.Signals, object] = {}
    for signum in _WATCHED_SIGNALS:
        previous[signum] = signal.signal(signum, _on_command_signal)
    return previous


def _enter_command_signal_scope() -> tuple[dict[signal.Signals, object], set[int]]:
    """Install both handlers while neither watched signal can be delivered."""

    old_mask = _pthread_sigmask(signal.SIG_BLOCK, _WATCHED_SIGNALS)
    previous: dict[signal.Signals, object] = {}
    try:
        previous = _install_command_signal_scope()
    except BaseException:
        _restore_command_signal_scope(previous)
        _pthread_sigmask(signal.SIG_SETMASK, old_mask)
        raise
    return previous, old_mask


def _restore_command_signal_scope(
    previous: dict[signal.Signals, object], *, restore_mask: bool = True
) -> None:
    try:
        old_mask = _pthread_sigmask(signal.SIG_BLOCK, _WATCHED_SIGNALS)
    except Exception:
        return
    try:
        for signum, handler in previous.items():
            try:
                signal.signal(signum, handler)
            except Exception:
                continue
        if _terminal_committed:
            try:
                _snapshot_pending_signal(None)
            except Exception:
                pass
    finally:
        if restore_mask:
            try:
                _pthread_sigmask(signal.SIG_SETMASK, old_mask)
            except Exception:
                pass


def _admission_result(
    attempt: driver.CommandAttempt,
    *,
    status: Literal["refused", "failed"],
    outcome: str,
) -> TerminalResult:
    return TerminalResult(
        status,
        outcome,
        None,
        attempt.admission_ref,
        attempt.admission_sha256,
    )


def _cleanup_incomplete_result(
    attempt: driver.CommandAttempt | None,
) -> TerminalResult:
    global _cleanup_incomplete_committing
    _cleanup_incomplete_committing = True
    if attempt is None:
        return TerminalResult("failed", "cleanup_incomplete", None, None, None)
    return _admission_result(
        attempt, status="failed", outcome="cleanup_incomplete"
    )


def _expected_terminal_ref(attempt: driver.CommandAttempt) -> str:
    name = driver._command_name(attempt.command, attempt.ordinal, "terminal")
    return driver._command_ref(attempt.namespace, name)


def _binding_is_current(result: TerminalResult, *, root: Path) -> bool:
    if result.artifact_ref is None or result.artifact_sha256 is None:
        return False
    try:
        payload = driver.open_bench_file(result.artifact_ref, root=root)
    except Exception:
        return False
    return hashlib.sha256(payload).hexdigest() == result.artifact_sha256


def _binding_matches_tier(
    attempt: driver.CommandAttempt, result: TerminalResult
) -> bool:
    if result.artifact_ref is None:
        return False
    is_rehearsal = result.artifact_ref.startswith("rehearsal/")
    return is_rehearsal == (attempt.namespace == "rehearsal")


def _is_command_control_ref(relative: str | None) -> bool:
    if relative is None:
        return False
    name = relative.rsplit("/", 1)[-1]
    return driver._COMMAND_ARTIFACT_NAME_RE.fullmatch(name) is not None


def _publish_terminal_result(
    attempt: driver.CommandAttempt,
    result: TerminalResult,
    *,
    root: Path,
) -> TerminalResult:
    policy: driver.ArtifactPolicy
    if attempt.namespace == "rehearsal":
        policy = driver.RehearsalArtifactPolicy()
    else:
        policy = driver.ProductionArtifactPolicy()
    encoded = policy.encode("refusal", {"outcome": result.outcome})
    relative, digest = driver.publish_command_artifact(
        attempt, "terminal", encoded, root=root
    )
    return TerminalResult(
        result.status,
        result.outcome,
        result.window_id,
        relative,
        digest,
    )


def _normalize_handler_result(
    attempt: driver.CommandAttempt,
    value: object,
    *,
    root: Path,
) -> TerminalResult:
    if type(value) is not TerminalResult:
        return _admission_result(attempt, status="failed", outcome="provider_uncertain")
    result = value
    if (
        result.outcome == "invocation_invalid"
        or result.outcome in _CLI_RESERVED_OUTCOMES
        or _is_command_control_ref(result.artifact_ref)
    ):
        return _admission_result(attempt, status="failed", outcome="provider_uncertain")
    if result.status == "ok":
        if (
            result.artifact_ref == attempt.admission_ref
            or not _binding_matches_tier(attempt, result)
            or not _binding_is_current(result, root=root)
        ):
            return _admission_result(
                attempt, status="failed", outcome="provider_uncertain"
            )
        return result
    if result.artifact_ref is None:
        try:
            return _publish_terminal_result(attempt, result, root=root)
        except driver.BenchRefusal as exc:
            if exc.code == "cleanup_incomplete":
                return _cleanup_incomplete_result(attempt)
            return _admission_result(
                attempt, status="failed", outcome="provider_uncertain"
            )
        except Exception:
            return _admission_result(
                attempt, status="failed", outcome="provider_uncertain"
            )
    if (
        not _binding_matches_tier(attempt, result)
        or not _binding_is_current(result, root=root)
    ):
        return _admission_result(attempt, status="failed", outcome="provider_uncertain")
    return result


def _exception_result(
    attempt: driver.CommandAttempt,
    *,
    root: Path,
    status: Literal["refused", "failed"],
    outcome: str,
) -> TerminalResult:
    provisional = TerminalResult(status, outcome, None, None, None)
    try:
        return _publish_terminal_result(attempt, provisional, root=root)
    except driver.BenchRefusal as exc:
        if exc.code == "cleanup_incomplete":
            return _cleanup_incomplete_result(attempt)
        return _admission_result(attempt, status="failed", outcome="provider_uncertain")
    except Exception:
        if _cleanup_incomplete_committing:
            return _cleanup_incomplete_result(attempt)
        return _admission_result(attempt, status="failed", outcome="provider_uncertain")


def _run_command(
    command: str,
    handler: Callable[..., object],
    *,
    root: Path,
    clock: driver.Clock,
) -> int:
    global _cleanup_incomplete_committing, _terminal_committed
    _terminal_committed = False
    _cleanup_incomplete_committing = False
    old_handlers: dict[signal.Signals, object] = {}
    attempt: driver.CommandAttempt | None = None

    def latch_admission(value: driver.CommandAttempt) -> None:
        nonlocal attempt
        attempt = value

    def suppress_cleanup_interruption() -> None:
        global _cleanup_incomplete_committing
        _cleanup_incomplete_committing = True

    try:
        try:
            old_handlers, old_mask = _enter_command_signal_scope()
            _pthread_sigmask(signal.SIG_SETMASK, old_mask)
        except driver._CommandInterrupted as interrupted:
            terminal = TerminalResult(
                "refused", "interrupted", None, None, None
            )
            return _commit_terminal(
                terminal,
                interrupted_signum=interrupted.signum,
                interruption_fallback=terminal,
            )
        except Exception:
            terminal = TerminalResult(
                "failed", "provider_uncertain", None, None, None
            )
            return _commit_terminal(terminal)
        try:
            policy: driver.ArtifactPolicy
            if command == "rehearse":
                policy = driver.RehearsalArtifactPolicy()
            else:
                policy = driver.ProductionArtifactPolicy()
        except Exception:
            terminal = TerminalResult(
                "failed", "provider_uncertain", None, None, None
            )
            return _commit_terminal(terminal)
        try:
            attempt = driver._admit_command(
                command=command,
                window_id=None,
                policy=policy,
                clock=clock,
                root=root,
                _on_latched=latch_admission,
                _on_cleanup_incomplete=suppress_cleanup_interruption,
            )
            value = handler(attempt, root=root)
            terminal = _normalize_handler_result(attempt, value, root=root)
        except driver._CommandInterrupted as interrupted:
            bound = interrupted.attempt if interrupted.attempt is not None else attempt
            terminal = TerminalResult(
                "refused",
                "interrupted",
                None,
                None if bound is None else bound.admission_ref,
                None if bound is None else bound.admission_sha256,
            )
            return _commit_terminal(
                terminal,
                interrupted_signum=interrupted.signum,
                interruption_fallback=terminal,
            )
        except driver.BenchRefusal as exc:
            if exc.code == "cleanup_incomplete":
                _cleanup_incomplete_committing = True
            if exc.code == "interrupted":
                terminal = (
                    TerminalResult(
                        "failed", "provider_uncertain", None, None, None
                    )
                    if attempt is None
                    else _admission_result(
                        attempt,
                        status="failed",
                        outcome="provider_uncertain",
                    )
                )
            elif attempt is None:
                status: Literal["refused", "failed"] = (
                    "failed" if exc.code == "cleanup_incomplete" else "refused"
                )
                terminal = TerminalResult(status, exc.code, None, None, None)
            else:
                terminal = _exception_result(
                    attempt,
                    root=root,
                    status=(
                        "failed" if exc.code == "cleanup_incomplete" else "refused"
                    ),
                    outcome=exc.code,
                )
        except Exception:
            if _cleanup_incomplete_committing:
                terminal = _cleanup_incomplete_result(attempt)
            elif attempt is None:
                terminal = TerminalResult(
                    "failed", "provider_uncertain", None, None, None
                )
            else:
                terminal = _exception_result(
                    attempt,
                    root=root,
                    status="failed",
                    outcome="provider_uncertain",
                )
        fallback = (
            None
            if attempt is None
            else _admission_result(
                attempt, status="refused", outcome="interrupted"
            )
        )
        return _commit_terminal(terminal, interruption_fallback=fallback)
    except driver._CommandInterrupted as interrupted:
        bound = interrupted.attempt if interrupted.attempt is not None else attempt
        terminal = TerminalResult(
            "refused",
            "interrupted",
            None,
            None if bound is None else bound.admission_ref,
            None if bound is None else bound.admission_sha256,
        )
        return _commit_terminal(
            terminal,
            interrupted_signum=interrupted.signum,
            interruption_fallback=terminal,
        )
    finally:
        _restore_command_signal_scope(old_handlers)
        _cleanup_incomplete_committing = False


def _unimplemented_handler(
    _attempt: driver.CommandAttempt, *, root: Path
) -> TerminalResult:
    del root
    return TerminalResult("refused", "assembly_refused", None, None, None)


def main(argv: Sequence[str] | None = None) -> int:
    global _cleanup_incomplete_committing, _terminal_committed
    _terminal_committed = False
    _cleanup_incomplete_committing = False
    old_handlers: dict[signal.Signals, object] = {}
    try:
        try:
            old_handlers, old_mask = _enter_command_signal_scope()
            _pthread_sigmask(signal.SIG_SETMASK, old_mask)
        except driver._CommandInterrupted as interrupted:
            return _commit_terminal(
                TerminalResult("refused", "interrupted", None, None, None),
                interrupted_signum=interrupted.signum,
            )
        except Exception:
            return _commit_terminal(
                TerminalResult(
                    "failed", "provider_uncertain", None, None, None
                )
            )
        try:
            parsed = build_parser().parse_args(argv)
        except InvocationRefusal:
            return _commit_terminal(
                TerminalResult("refused", "invocation_invalid", None, None, None)
            )
        except driver._CommandInterrupted as interrupted:
            return _commit_terminal(
                TerminalResult("refused", "interrupted", None, None, None),
                interrupted_signum=interrupted.signum,
            )
        except Exception:
            return _commit_terminal(
                TerminalResult(
                    "failed", "provider_uncertain", None, None, None
                )
            )
        command = parsed.command
        try:
            clock: driver.Clock = (
                driver.RehearsalClock()
                if command == "rehearse"
                else driver.SystemClock()
            )
        except Exception:
            return _commit_terminal(
                TerminalResult(
                    "failed", "provider_uncertain", None, None, None
                )
            )
        return _run_command(
            command,
            _unimplemented_handler,
            root=driver.BENCH_ROOT,
            clock=clock,
        )
    except driver._CommandInterrupted as interrupted:
        return _commit_terminal(
            TerminalResult("refused", "interrupted", None, None, None),
            interrupted_signum=interrupted.signum,
        )
    finally:
        _restore_command_signal_scope(
            old_handlers, restore_mask=not _terminal_committed
        )
        _cleanup_incomplete_committing = False


if __name__ == "__main__":
    raise SystemExit(main())
