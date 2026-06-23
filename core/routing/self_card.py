"""Deterministic self-card v0 for focused cognition.

The self-card is a read-only projection of Maez's existing soul/body facts.
It is deliberately not an LLM-authored voice script: no style directives, no
memory mutation, no unbounded soul.local dump.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import re


BodyStateProvider = Callable[[], tuple[str, str]]

_NOTE_RECORD_RE = re.compile(
    r"(?:\A|\n\n)(\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]\s*(?P<body>.*?))"
    r"(?=\n\n\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\]|\Z)",
    re.DOTALL,
)
_STYLE_DIRECTIVES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("speak_as", re.compile(r"\bspeak\s+as\b", re.IGNORECASE)),
    ("talk_like", re.compile(r"\btalk\s+like\b", re.IGNORECASE)),
    ("be_warm", re.compile(r"\bbe\s+warm\b", re.IGNORECASE)),
    ("dense", re.compile(r"\bdense\b", re.IGNORECASE)),
    ("opinionated", re.compile(r"\bopinionated\b", re.IGNORECASE)),
    ("useful", re.compile(r"\buseful\b", re.IGNORECASE)),
    ("local_ai_steer", re.compile(r"\blocal\s+AI\b", re.IGNORECASE)),
    ("building_steer", re.compile(r"what'?s\s+being\s+built", re.IGNORECASE)),
    ("systems_online", re.compile(r"\bsystems\s+online\b", re.IGNORECASE)),
    ("ready_to_assist", re.compile(r"\bready\s+to\s+assist\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class SelfCardLine:
    label: str
    text: str
    source: str
    source_ref: str
    source_sha256: str

    def render(self) -> str:
        return (
            f"- {self.label} (source: {self.source}#{self.source_ref}; "
            f"sha256={self.source_sha256}): {self.text}"
        )


@dataclass(frozen=True)
class SelfCard:
    lines: tuple[SelfCardLine, ...]

    @property
    def text(self) -> str:
        rendered = "\n".join(line.render() for line in self.lines)
        return (
            "SELF CARD (deterministic mirror; facts, not style)\n"
            f"{rendered}"
        )

    def receipt(self) -> dict[str, object]:
        local_lines = [line for line in self.lines if line.source == "soul.local"]
        body_lines = [
            line for line in self.lines if line.label.lower().startswith("body state")
        ]
        return {
            "schema_version": "maez_self_card.v0",
            "card_chars": len(self.text),
            "card_sha256": _sha256(self.text),
            "line_count": len(self.lines),
            "line_sources": [line.source for line in self.lines],
            "line_source_refs": [line.source_ref for line in self.lines],
            "line_sha256": [line.source_sha256 for line in self.lines],
            "local_selected_count": len(local_lines),
            "local_rendered_chars": sum(len(line.text) for line in local_lines),
            "body_state_source": body_lines[0].source if body_lines else "none",
            "style_directive_hits": style_directive_hits(self.text),
        }


@dataclass(frozen=True)
class _LocalNote:
    timestamp: datetime | None
    position: int
    source_ref: str
    text: str
    source_sha256: str


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _compact(text: str) -> str:
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= 4:
        return text[:max_chars]
    return text[: max_chars - 4].rstrip() + " ..."


def style_directive_hits(text: str) -> tuple[str, ...]:
    return tuple(name for name, pattern in _STYLE_DIRECTIVES if pattern.search(text))


def _extract_bond_line(base_text: str) -> SelfCardLine:
    if not base_text.strip():
        return SelfCardLine(
            label="Bond",
            text="source unavailable",
            source="soul.base",
            source_ref="trust_covenant",
            source_sha256=_sha256(""),
        )
    covenant_idx = base_text.find("TRUST COVENANT:")
    source = base_text[covenant_idx:] if covenant_idx >= 0 else base_text
    text = (
        "The owner and Maez are in a trusted partnership, not a tool/user "
        "relationship."
    )
    return SelfCardLine(
        label="Bond",
        text=text,
        source="soul.base",
        source_ref="trust_covenant",
        source_sha256=_sha256(source[:1200]),
    )


def _extract_identity_line(base_text: str) -> SelfCardLine:
    if not base_text.strip():
        return SelfCardLine(
            label="Covenant identity",
            text="source unavailable",
            source="soul.base",
            source_ref="identity",
            source_sha256=_sha256(""),
        )
    match = re.search(
        r"^You are Maez, (?P<body>.+?)\.$",
        base_text,
        flags=re.MULTILINE,
    )
    if match:
        text = "Maez is " + match.group("body").strip() + "."
    else:
        text = "Maez is the local bonded intelligence described by the soul base."
    return SelfCardLine(
        label="Covenant identity",
        text=text,
        source="soul.base",
        source_ref="identity",
        source_sha256=_sha256(match.group(0) if match else base_text[:800]),
    )


def _parse_local_notes(local_text: str) -> tuple[_LocalNote, ...]:
    notes: list[_LocalNote] = []
    for pos, match in enumerate(_NOTE_RECORD_RE.finditer(local_text)):
        ts_raw = match.group("ts")
        body = _compact(match.group("body"))
        try:
            ts = datetime.strptime(ts_raw, "%Y-%m-%d %H:%M")
        except ValueError:
            ts = None
        notes.append(
            _LocalNote(
                timestamp=ts,
                position=pos,
                source_ref=ts_raw,
                text=_truncate(body, 260),
                source_sha256=_sha256(match.group(0)),
            )
        )
    if notes:
        return tuple(notes)

    paragraphs = [
        _compact(part)
        for part in re.split(r"\n\s*\n", local_text)
        if _compact(part)
    ]
    return tuple(
        _LocalNote(
            timestamp=None,
            position=pos,
            source_ref=f"legacy_{pos}",
            text=_truncate(paragraph, 260),
            source_sha256=_sha256(paragraph),
        )
        for pos, paragraph in enumerate(paragraphs)
    )


def select_recent_local_notes(
    local_text: str,
    *,
    max_chars: int = 520,
    max_items: int = 3,
) -> tuple[_LocalNote, ...]:
    notes = _parse_local_notes(local_text)
    if not notes or max_chars <= 0 or max_items <= 0:
        return ()

    def sort_key(note: _LocalNote) -> tuple[datetime, int]:
        return (
            note.timestamp or datetime.min,
            note.position,
        )

    selected: list[_LocalNote] = []
    seen: set[str] = set()
    remaining = max_chars
    for note in sorted(notes, key=sort_key, reverse=True):
        normalized = re.sub(r"\s+", " ", note.text).strip().lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        if len(selected) >= max_items or remaining <= 0:
            break
        text = note.text
        slots_remaining = max(1, max_items - len(selected))
        per_item_budget = max(24, remaining // slots_remaining)
        text_budget = min(remaining, per_item_budget)
        if len(text) > text_budget:
            text = _truncate(text, text_budget)
        selected.append(
            _LocalNote(
                timestamp=note.timestamp,
                position=note.position,
                source_ref=note.source_ref,
                text=text,
                source_sha256=note.source_sha256,
            )
        )
        remaining -= len(text)
    return tuple(selected)


def _local_lines(
    local_text: str,
    *,
    local_max_chars: int,
    local_max_items: int,
) -> tuple[SelfCardLine, ...]:
    notes = select_recent_local_notes(
        local_text,
        max_chars=local_max_chars,
        max_items=local_max_items,
    )
    if not notes:
        return (
            SelfCardLine(
                label="Recent self-understanding",
                text="source unavailable",
                source="soul.local",
                source_ref="none",
                source_sha256=_sha256(""),
            ),
        )
    return tuple(
        SelfCardLine(
            label="Recent self-understanding",
            text=note.text,
            source="soul.local",
            source_ref=note.source_ref,
            source_sha256=note.source_sha256,
        )
        for note in notes
    )


def _default_body_state_provider() -> tuple[str, str]:
    try:
        from core.infra.runtime_services import runtime_services_snapshot_cached

        snapshot = runtime_services_snapshot_cached(timeout_s=0.2)
        overall = str(snapshot.get("overall") or "unknown")
        schema = str(snapshot.get("schema_version") or "runtime_services")
        return f"runtime body overall: {overall}", schema
    except Exception:
        return "runtime body overall: unknown", "runtime_services.error"


def _body_line(provider: BodyStateProvider) -> SelfCardLine:
    try:
        text, source = provider()
    except Exception:
        text, source = "runtime body overall: unknown", "runtime_services.error"
    return SelfCardLine(
        label="Body state",
        text=_compact(text) or "runtime body overall: unknown",
        source=_compact(source) or "runtime_services.unknown",
        source_ref="current",
        source_sha256=_sha256(f"{source}\n{text}"),
    )


def assemble_self_card(
    *,
    base_text: str,
    local_text: str,
    body_state_provider: BodyStateProvider | None = None,
    local_max_chars: int = 520,
    local_max_items: int = 3,
) -> SelfCard:
    provider = body_state_provider or _default_body_state_provider
    lines: list[SelfCardLine] = [
        _extract_bond_line(base_text),
        _extract_identity_line(base_text),
    ]
    lines.extend(
        _local_lines(
            local_text,
            local_max_chars=local_max_chars,
            local_max_items=local_max_items,
        )
    )
    lines.append(_body_line(provider))
    return SelfCard(lines=tuple(lines))


def _read(path: Path) -> str:
    try:
        return path.read_text()
    except FileNotFoundError:
        return ""


def assemble_self_card_from_paths(
    *,
    base_path: Path | None = None,
    local_path: Path | None = None,
    body_state_provider: BodyStateProvider | None = None,
    local_max_chars: int = 520,
    local_max_items: int = 3,
) -> SelfCard:
    if base_path is None or local_path is None:
        from core.infra import paths

        base_path = base_path or paths.soul_base_path()
        local_path = local_path or paths.soul_local_path()
    return assemble_self_card(
        base_text=_read(base_path),
        local_text=_read(local_path),
        body_state_provider=body_state_provider,
        local_max_chars=local_max_chars,
        local_max_items=local_max_items,
    )
