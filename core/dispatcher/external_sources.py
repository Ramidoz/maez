"""External-source fan-out for the recall-axis dispatcher.

This module consumes `CompositionSpec.external_sources` and returns typed fresh
source results. It does not choose sources, merge with substrate recall, render
prompt text, modify repair specs, or wire into brain-loop routing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
import json
from pathlib import Path
import re
import time
from typing import Any

from core.dispatcher.spec import (
    AvailabilityLimitation,
    CompositionSpec,
    DeadlineKind,
    DispatcherRefusalReason,
    ExternalBranchStatus,
    ExternalEmptyReason,
    ExternalErrorClass,
    ExternalSource,
    FreshnessClass,
)
from core.egress import external_fetch


DEFAULT_BRANCH_TIMEOUT_S = 5.0
DEFAULT_GLOBAL_DEADLINE_S = 6.0
DEFAULT_CLEANUP_GRACE_S = 0.025
DEFAULT_MAX_PARALLEL_BRANCHES = 5
# Hard prompt cap for each fresh evidence source; text beyond this is omitted
# before rendering and the egress diagnostic remains the source-of-truth witness.
MAX_FRESH_CHARS_PER_SOURCE = 2000
URL_RE = re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE)
SUBREDDIT_RE = re.compile(r"\br/([A-Za-z0-9_][A-Za-z0-9_]{1,20})\b")
SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "api_token",
    "auth",
    "authorization",
    "key",
    "password",
    "secret",
    "token",
}
SOURCE_PRIORITY = (
    ExternalSource.WEB_SEARCH,
    ExternalSource.LIVE_REDDIT,
    ExternalSource.FETCH_URL,
    ExternalSource.ARXIV_OR_PAPERCLIP,
    ExternalSource.FRONTIER_CONSULT,
)
_EXPLICIT_WEB_SEARCH_RE = re.compile(
    r"^\s*(?:search(?: the internet| the web| web)?(?: for)?|google|look up|fetch|"
    r"check the internet(?: for)?|go check(?: for)?)\b[\s:,-]*(?P<object>.*)$",
    re.IGNORECASE,
)
_META_SEARCH_INSTRUCTION_RE = re.compile(
    r"\b(?:if you (?:do not|don't) have|if (?:you )?(?:need|want)|latest information|"
    r"current information|up[- ]to[- ]date|internet if|web if)\b",
    re.IGNORECASE,
)
_OWNER_LINE_RE = re.compile(r"^\s*(?:rohit|owner|user)\s*:\s*(?P<text>.+?)\s*$", re.IGNORECASE)
_QUESTION_START_RE = re.compile(
    r"^\s*(?:what|who|when|where|why|how|is|are|do|does|did|can|could|should|has|have)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FreshBlock:
    source: ExternalSource
    text: str
    retrieval_timestamp: str
    freshness: FreshnessClass
    prompt_cost: int
    egress_diagnostic_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "text": self.text,
            "retrieval_timestamp": self.retrieval_timestamp,
            "freshness": self.freshness.value,
            "prompt_cost": self.prompt_cost,
            "egress_diagnostic_id": self.egress_diagnostic_id,
        }


@dataclass(frozen=True)
class ExternalBranchResult:
    branch_id: str
    fanout_generation_id: str
    source: ExternalSource
    status: ExternalBranchStatus
    blocks: tuple[FreshBlock, ...] = ()
    empty_reason: ExternalEmptyReason | None = None
    error_class: ExternalErrorClass | None = None
    elapsed_ms: float = 0.0
    deadline_kind: DeadlineKind | None = None
    completed_at: float | None = None
    late_result_ignored: bool = False
    refusal_reason: DispatcherRefusalReason | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "fanout_generation_id": self.fanout_generation_id,
            "source": self.source.value,
            "status": self.status.value,
            "blocks": [block.to_dict() for block in self.blocks],
            "empty_reason": self.empty_reason.value if self.empty_reason else None,
            "error_class": self.error_class.value if self.error_class else None,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "deadline_kind": self.deadline_kind.value if self.deadline_kind else None,
            "completed_at": self.completed_at,
            "late_result_ignored": self.late_result_ignored,
            "refusal_reason": self.refusal_reason.value if self.refusal_reason else None,
        }


@dataclass(frozen=True)
class ExternalFanoutResult:
    fanout_generation_id: str
    sealed_at: float
    branch_results: tuple[ExternalBranchResult, ...]
    fresh_blocks: tuple[FreshBlock, ...]
    availability_limitations: tuple[AvailabilityLimitation, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fanout_generation_id": self.fanout_generation_id,
            "sealed_at": self.sealed_at,
            "branch_results": [branch.to_dict() for branch in self.branch_results],
            "fresh_blocks": [block.to_dict() for block in self.fresh_blocks],
            "availability_limitations": [
                limitation.value for limitation in self.availability_limitations
            ],
        }


@dataclass(frozen=True)
class ExternalAdapterRequest:
    source: ExternalSource
    utterance: str
    conversation_state: Mapping[str, Any]
    retrieval_timestamp: str


@dataclass(frozen=True)
class ExternalAdapterPayload:
    text: str
    egress_diagnostic_id: str
    freshness: FreshnessClass = FreshnessClass.LIVE_FETCH
    prompt_cost: int | None = None
    retrieval_timestamp: str | None = None


ExternalAdapter = Callable[[ExternalSource, ExternalAdapterRequest], ExternalAdapterPayload]
SubjectBoundaryPredicate = Callable[[ExternalSource, str, Mapping[str, Any]], bool]


class _MappedExternalFailure(Exception):
    def __init__(
        self,
        *,
        status: ExternalBranchStatus,
        error_class: ExternalErrorClass | None = None,
        empty_reason: ExternalEmptyReason | None = None,
        limitation: AvailabilityLimitation,
        deadline_kind: DeadlineKind | None = None,
        refusal_reason: DispatcherRefusalReason | None = None,
    ) -> None:
        super().__init__(status.value)
        self.status = status
        self.error_class = error_class
        self.empty_reason = empty_reason
        self.limitation = limitation
        self.deadline_kind = deadline_kind
        self.refusal_reason = refusal_reason


class ExternalFanout:
    def __init__(
        self,
        *,
        adapters: Mapping[ExternalSource, ExternalAdapter] | None = None,
        subject_boundary_predicate: SubjectBoundaryPredicate | None = None,
        branch_timeout_s: float = DEFAULT_BRANCH_TIMEOUT_S,
        global_deadline_s: float = DEFAULT_GLOBAL_DEADLINE_S,
        cleanup_grace_s: float = DEFAULT_CLEANUP_GRACE_S,
        max_parallel_branches: int = DEFAULT_MAX_PARALLEL_BRANCHES,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.adapters = dict(adapters or {})
        self.subject_boundary_predicate = (
            subject_boundary_predicate or _default_subject_boundary_refused
        )
        self.branch_timeout_s = branch_timeout_s
        self.global_deadline_s = global_deadline_s
        self.cleanup_grace_s = cleanup_grace_s
        self.max_parallel_branches = max_parallel_branches
        self.clock = clock or time.monotonic

    def run(
        self,
        spec: CompositionSpec,
        *,
        utterance: str,
        conversation_state: Mapping[str, Any],
        fanout_generation_id: str,
    ) -> ExternalFanoutResult:
        started_at = self.clock()
        deadline_at = started_at + self.global_deadline_s
        ordered_sources = _stable_sources(spec.external_sources)
        if not ordered_sources:
            return ExternalFanoutResult(
                fanout_generation_id=fanout_generation_id,
                sealed_at=started_at,
                branch_results=(),
                fresh_blocks=(),
                availability_limitations=(),
            )

        results: dict[ExternalSource, ExternalBranchResult] = {}
        limitations: list[AvailabilityLimitation] = []
        fresh_blocks: list[FreshBlock] = []
        executor = ThreadPoolExecutor(
            max_workers=max(1, min(self.max_parallel_branches, len(ordered_sources)))
        )
        futures: dict[Future[ExternalAdapterPayload], tuple[ExternalSource, str, float]] = {}

        try:
            for source in ordered_sources:
                branch_id = _branch_id(fanout_generation_id, source)
                preflight = self._preflight_result(
                    source=source,
                    branch_id=branch_id,
                    generation_id=fanout_generation_id,
                    utterance=utterance,
                    conversation_state=conversation_state,
                )
                if preflight is not None:
                    results[source] = preflight
                    _append_limitation(limitations, _limitation_for(preflight))
                    continue

                adapter = self.adapters.get(source) or _DEFAULT_ADAPTERS.get(source)
                if adapter is None:
                    results[source] = _failure_result(
                        generation_id=fanout_generation_id,
                        branch_id=branch_id,
                        source=source,
                        status=ExternalBranchStatus.ERROR,
                        error_class=ExternalErrorClass.ADAPTER_MISSING,
                        elapsed_ms=0.0,
                    )
                    _append_limitation(limitations, AvailabilityLimitation.FRESH_ATTEMPT_FAILED)
                    continue

                request = ExternalAdapterRequest(
                    source=source,
                    utterance=utterance,
                    conversation_state=conversation_state,
                    retrieval_timestamp=_utc_now_iso(),
                )
                futures[executor.submit(adapter, source, request)] = (
                    source,
                    branch_id,
                    self.clock(),
                )

            pending = set(futures)
            while pending:
                now = self.clock()
                if now >= deadline_at:
                    for future in list(pending):
                        source, branch_id, submitted_at = futures[future]
                        results[source] = _timeout_result(
                            generation_id=fanout_generation_id,
                            branch_id=branch_id,
                            source=source,
                            elapsed_ms=(now - submitted_at) * 1000,
                            deadline_kind=DeadlineKind.GLOBAL,
                        )
                        _append_limitation(limitations, AvailabilityLimitation.SOURCE_TIMEOUT)
                    pending.clear()
                    break

                for future in list(pending):
                    source, branch_id, submitted_at = futures[future]
                    if now - submitted_at >= self.branch_timeout_s:
                        results[source] = _timeout_result(
                            generation_id=fanout_generation_id,
                            branch_id=branch_id,
                            source=source,
                            elapsed_ms=(now - submitted_at) * 1000,
                            deadline_kind=DeadlineKind.BRANCH,
                        )
                        _append_limitation(limitations, AvailabilityLimitation.SOURCE_TIMEOUT)
                        pending.remove(future)

                if not pending:
                    break

                done, _ = wait(pending, timeout=min(0.002, max(0.0, deadline_at - now)))
                for future in done:
                    source, branch_id, submitted_at = futures[future]
                    pending.remove(future)
                    elapsed_ms = (self.clock() - submitted_at) * 1000
                    result = self._result_from_future(
                        future,
                        source=source,
                        branch_id=branch_id,
                        generation_id=fanout_generation_id,
                        elapsed_ms=elapsed_ms,
                    )
                    results[source] = result
                    _append_limitation(limitations, _limitation_for(result))
        finally:
            if self.cleanup_grace_s > 0:
                wait(
                    set(futures) - {future for future in futures if future.done()},
                    timeout=self.cleanup_grace_s,
                )
            executor.shutdown(wait=False, cancel_futures=True)

        sealed_at = self.clock()
        for source in ordered_sources:
            result = results[source]
            if result.status is ExternalBranchStatus.SUCCESS:
                fresh_blocks.extend(result.blocks)

        return ExternalFanoutResult(
            fanout_generation_id=fanout_generation_id,
            sealed_at=sealed_at,
            branch_results=tuple(results[source] for source in ordered_sources),
            fresh_blocks=tuple(fresh_blocks),
            availability_limitations=tuple(limitations),
        )

    def _preflight_result(
        self,
        *,
        source: ExternalSource,
        branch_id: str,
        generation_id: str,
        utterance: str,
        conversation_state: Mapping[str, Any],
    ) -> ExternalBranchResult | None:
        if source is ExternalSource.FRONTIER_CONSULT:
            return _reserved_result(generation_id, branch_id, source)
        # The v1 arxiv route is audited; explicit paperclip asks stay
        # reserved until the paperclip substrate has its own egress contract.
        if source is ExternalSource.ARXIV_OR_PAPERCLIP and "paperclip" in utterance.lower():
            return _reserved_result(generation_id, branch_id, source)
        if self.subject_boundary_predicate(source, utterance, conversation_state):
            return _failure_result(
                generation_id=generation_id,
                branch_id=branch_id,
                source=source,
                status=ExternalBranchStatus.PREFLIGHT_BLOCKED,
                error_class=ExternalErrorClass.SUBJECT_BOUNDARY_REFUSED,
                elapsed_ms=0.0,
            )
        if source is ExternalSource.FETCH_URL:
            urls = _extract_urls(utterance)
            if not urls and conversation_state.get("model_suggested_url"):
                return _failure_result(
                    generation_id=generation_id,
                    branch_id=branch_id,
                    source=source,
                    status=ExternalBranchStatus.PREFLIGHT_BLOCKED,
                    error_class=ExternalErrorClass.PREFLIGHT_REFUSED,
                    elapsed_ms=0.0,
                    refusal_reason=DispatcherRefusalReason.MODEL_INVENTED_URL,
                )
            if not urls:
                return _failure_result(
                    generation_id=generation_id,
                    branch_id=branch_id,
                    source=source,
                    status=ExternalBranchStatus.EMPTY,
                    empty_reason=ExternalEmptyReason.NO_RESULTS,
                    elapsed_ms=0.0,
                )
            if any(_has_sensitive_query(url) for url in urls):
                return _failure_result(
                    generation_id=generation_id,
                    branch_id=branch_id,
                    source=source,
                    status=ExternalBranchStatus.PREFLIGHT_BLOCKED,
                    error_class=ExternalErrorClass.PREFLIGHT_REFUSED,
                    elapsed_ms=0.0,
                )
        return None

    def _result_from_future(
        self,
        future: Future[ExternalAdapterPayload],
        *,
        source: ExternalSource,
        branch_id: str,
        generation_id: str,
        elapsed_ms: float,
    ) -> ExternalBranchResult:
        try:
            payload = future.result()
        except _MappedExternalFailure as exc:
            return _failure_result(
                generation_id=generation_id,
                branch_id=branch_id,
                source=source,
                status=exc.status,
                error_class=exc.error_class,
                empty_reason=exc.empty_reason,
                deadline_kind=exc.deadline_kind,
                elapsed_ms=elapsed_ms,
                refusal_reason=exc.refusal_reason,
            )
        except TimeoutError:
            return _timeout_result(
                generation_id=generation_id,
                branch_id=branch_id,
                source=source,
                elapsed_ms=elapsed_ms,
                deadline_kind=DeadlineKind.BRANCH,
            )
        except Exception:
            return _failure_result(
                generation_id=generation_id,
                branch_id=branch_id,
                source=source,
                status=ExternalBranchStatus.ERROR,
                error_class=ExternalErrorClass.UNCLASSIFIED,
                elapsed_ms=elapsed_ms,
            )

        if not payload.text:
            return _failure_result(
                generation_id=generation_id,
                branch_id=branch_id,
                source=source,
                status=ExternalBranchStatus.EMPTY,
                empty_reason=ExternalEmptyReason.NO_RESULTS,
                elapsed_ms=elapsed_ms,
            )
        block = FreshBlock(
            source=source,
            text=payload.text[:MAX_FRESH_CHARS_PER_SOURCE],
            retrieval_timestamp=payload.retrieval_timestamp or _utc_now_iso(),
            freshness=payload.freshness,
            prompt_cost=payload.prompt_cost
            if payload.prompt_cost is not None
            else len(payload.text),
            egress_diagnostic_id=payload.egress_diagnostic_id,
        )
        return ExternalBranchResult(
            branch_id=branch_id,
            fanout_generation_id=generation_id,
            source=source,
            status=ExternalBranchStatus.SUCCESS,
            blocks=(block,),
            elapsed_ms=elapsed_ms,
            completed_at=self.clock(),
        )


def diagnostics_match_fresh_block(block: FreshBlock, *, log_path: Path) -> bool:
    if not block.egress_diagnostic_id:
        return False
    try:
        rows = [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except FileNotFoundError:
        return False
    return any(
        row.get("schema_version") == external_fetch.SCHEMA_VERSION
        and row.get("request_id") == block.egress_diagnostic_id
        for row in rows
    )


def _web_search_adapter(
    _source: ExternalSource,
    request: ExternalAdapterRequest,
) -> ExternalAdapterPayload:
    from skills import web_search

    log_path = external_fetch._diagnostic_path()
    start_offset = log_path.stat().st_size if log_path.exists() else 0
    query = _derive_web_search_query(request.utterance, request.conversation_state)
    result = web_search.search(query, max_results=3)
    if not result.get("success") or not result.get("results"):
        raise _MappedExternalFailure(
            status=ExternalBranchStatus.EMPTY,
            empty_reason=ExternalEmptyReason.NO_RESULTS,
            limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
        )
    text = web_search.format_for_context(result)
    if not text.strip():
        raise _MappedExternalFailure(
            status=ExternalBranchStatus.EMPTY,
            empty_reason=ExternalEmptyReason.NO_RESULTS,
            limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
        )
    diagnostic_id = _latest_diagnostic_id_after(
        log_path=log_path,
        start_offset=start_offset,
        caller_prefix="skills.web_search.",
    )
    if not diagnostic_id:
        raise _MappedExternalFailure(
            status=ExternalBranchStatus.ERROR,
            error_class=ExternalErrorClass.UNCLASSIFIED,
            limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
        )
    return ExternalAdapterPayload(
        text=text,
        egress_diagnostic_id=diagnostic_id,
        retrieval_timestamp=request.retrieval_timestamp,
    )


def _derive_web_search_query(utterance: str, conversation_state: Mapping[str, Any]) -> str:
    text = (utterance or "").strip()
    match = _EXPLICIT_WEB_SEARCH_RE.match(text)
    if not match:
        return text
    requested_object = _clean_query_text(match.group("object"))
    if requested_object and not _META_SEARCH_INSTRUCTION_RE.search(requested_object):
        return requested_object
    history_query = _latest_substantive_owner_question(conversation_state.get("chat_history"))
    return history_query or text


def _latest_substantive_owner_question(chat_history: Any) -> str:
    if not chat_history:
        return ""
    try:
        entries = list(chat_history)
    except TypeError:
        entries = [chat_history]
    for entry in reversed(entries):
        for candidate in reversed(_owner_texts_from_history_entry(entry)):
            query = _clean_query_text(candidate)
            if query and _looks_like_substantive_question(query):
                return query
    return ""


def _owner_texts_from_history_entry(entry: Any) -> list[str]:
    if isinstance(entry, Mapping):
        for key in ("user_text", "owner_text", "text", "content"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                if key in {"user_text", "owner_text", "text"}:
                    return [value]
                return _owner_lines(value)
        return []
    if isinstance(entry, str):
        return _owner_lines(entry)
    content = getattr(entry, "content", None)
    if isinstance(content, str):
        return _owner_lines(content)
    return []


def _owner_lines(content: str) -> list[str]:
    lines: list[str] = []
    for raw_line in content.splitlines():
        match = _OWNER_LINE_RE.match(raw_line)
        if match:
            lines.append(match.group("text"))
    return lines


def _looks_like_substantive_question(text: str) -> bool:
    if _META_SEARCH_INSTRUCTION_RE.search(text):
        return False
    return "?" in text or bool(_QUESTION_START_RE.search(text))


def _clean_query_text(text: str) -> str:
    return (text or "").strip().strip(" \t\r\n\"'`.,;:!-")


def _latest_diagnostic_id_after(
    *,
    log_path: Path,
    start_offset: int,
    caller_prefix: str,
) -> str:
    try:
        with log_path.open("r", encoding="utf-8") as fh:
            fh.seek(start_offset)
            rows = [json.loads(line) for line in fh if line.strip()]
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return ""
    for row in reversed(rows):
        if (
            row.get("schema_version") == external_fetch.SCHEMA_VERSION
            and str(row.get("caller", "")).startswith(caller_prefix)
            and row.get("request_id")
        ):
            return str(row["request_id"])
    return ""


def _require_reddit_listing(text: str) -> None:
    """Fail closed unless text is a parsed Reddit listing."""
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        raise _MappedExternalFailure(
            status=ExternalBranchStatus.EMPTY,
            empty_reason=ExternalEmptyReason.PARSED_BUT_NO_USABLE_FIELDS,
            limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
        )

    children = None
    if isinstance(parsed, dict):
        data = parsed.get("data")
        if isinstance(data, dict):
            children = data.get("children")

    if not isinstance(children, list):
        raise _MappedExternalFailure(
            status=ExternalBranchStatus.EMPTY,
            empty_reason=ExternalEmptyReason.PARSED_BUT_NO_USABLE_FIELDS,
            limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
        )
    if not children:
        raise _MappedExternalFailure(
            status=ExternalBranchStatus.EMPTY,
            empty_reason=ExternalEmptyReason.NO_RESULTS,
            limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
        )


def _live_reddit_adapter(
    _source: ExternalSource,
    request: ExternalAdapterRequest,
) -> ExternalAdapterPayload:
    match = SUBREDDIT_RE.search(request.utterance)
    if not match:
        raise _MappedExternalFailure(
            status=ExternalBranchStatus.EMPTY,
            empty_reason=ExternalEmptyReason.NO_RESULTS,
            limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
        )
    subreddit = match.group(1)
    fetched = external_fetch.fetch_text(
        fetch_type="live_reddit",
        url=f"https://www.reddit.com/r/{subreddit}/hot.json?limit=5",
        caller="core.dispatcher.external_sources.live_reddit",
        timeout_s=5.0,
    )
    text = str(getattr(fetched, "text", ""))
    if getattr(fetched, "ok", False) and text.strip():
        _require_reddit_listing(text)
    return _payload_from_fetch_result(
        fetched,
        retrieval_timestamp=request.retrieval_timestamp,
    )


def _fetch_url_adapter(
    _source: ExternalSource,
    request: ExternalAdapterRequest,
) -> ExternalAdapterPayload:
    from core.search.page_extract import extract_readable

    url = _extract_urls(request.utterance)[0]
    fetched = external_fetch.fetch_text(
        fetch_type="fetch_url",
        url=url,
        caller="core.dispatcher.external_sources.fetch_url",
        timeout_s=5.0,
    )
    if getattr(fetched, "ok", False):
        base_type = (getattr(fetched, "content_type", "") or "").split(";", 1)[0].strip().lower()
        if base_type not in {"text/html", "text/plain", ""}:
            raise _MappedExternalFailure(
                status=ExternalBranchStatus.EMPTY,
                empty_reason=ExternalEmptyReason.NO_RESULTS,
                limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
            )
        title, text = extract_readable(
            str(getattr(fetched, "text", "")),
            content_type=base_type or "text/html",
        )
        if not text.strip():
            raise _MappedExternalFailure(
                status=ExternalBranchStatus.EMPTY,
                empty_reason=ExternalEmptyReason.NO_RESULTS,
                limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
            )
        return ExternalAdapterPayload(
            text=(title + "\n" + text) if title else text,
            egress_diagnostic_id=str(getattr(fetched, "request_id", "")),
            retrieval_timestamp=request.retrieval_timestamp,
        )
    return _payload_from_fetch_result(
        fetched,
        retrieval_timestamp=request.retrieval_timestamp,
    )


def _arxiv_adapter(
    _source: ExternalSource,
    request: ExternalAdapterRequest,
) -> ExternalAdapterPayload:
    query = re.sub(r"\s+", "+", request.utterance.strip())[:200]
    fetched = external_fetch.fetch_text(
        fetch_type="arxiv",
        url=f"https://export.arxiv.org/api/query?search_query=all:{query}&max_results=3",
        caller="core.dispatcher.external_sources.arxiv",
        timeout_s=3.0,
    )
    return _payload_from_fetch_result(
        fetched,
        retrieval_timestamp=request.retrieval_timestamp,
    )


_DEFAULT_ADAPTERS: dict[ExternalSource, ExternalAdapter] = {
    ExternalSource.WEB_SEARCH: _web_search_adapter,
    ExternalSource.LIVE_REDDIT: _live_reddit_adapter,
    ExternalSource.FETCH_URL: _fetch_url_adapter,
    ExternalSource.ARXIV_OR_PAPERCLIP: _arxiv_adapter,
}


def _payload_from_fetch_result(
    result: Any,
    *,
    retrieval_timestamp: str | None = None,
) -> ExternalAdapterPayload:
    if getattr(result, "ok", False):
        text = str(getattr(result, "text", ""))
        if not text.strip():
            raise _MappedExternalFailure(
                status=ExternalBranchStatus.EMPTY,
                empty_reason=ExternalEmptyReason.NO_RESULTS,
                limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
            )
        return ExternalAdapterPayload(
            text=text,
            egress_diagnostic_id=str(getattr(result, "request_id", "")),
            retrieval_timestamp=retrieval_timestamp,
        )

    status_code = getattr(result, "status_code", None)
    reason_codes = tuple(getattr(result, "reason_codes", ()) or ())
    if status_code in {401, 403}:
        error_class = ExternalErrorClass.AUTH_DENIED
    elif status_code == 429:
        error_class = ExternalErrorClass.RATE_LIMITED
    elif any("parse" in str(reason).lower() for reason in reason_codes):
        error_class = ExternalErrorClass.PARSE_FAILURE
    elif any("timeout" in str(reason).lower() for reason in reason_codes):
        raise _MappedExternalFailure(
            status=ExternalBranchStatus.TIMEOUT,
            error_class=ExternalErrorClass.TIMEOUT,
            limitation=AvailabilityLimitation.SOURCE_TIMEOUT,
            deadline_kind=DeadlineKind.BRANCH,
        )
    elif status_code and int(status_code) >= 400:
        error_class = ExternalErrorClass.HTTP_NON_2XX
    else:
        error_class = ExternalErrorClass.NETWORK_ERROR
    raise _MappedExternalFailure(
        status=ExternalBranchStatus.ERROR,
        error_class=error_class,
        limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
    )


def _failure_result(
    *,
    generation_id: str,
    branch_id: str,
    source: ExternalSource,
    status: ExternalBranchStatus,
    elapsed_ms: float,
    error_class: ExternalErrorClass | None = None,
    empty_reason: ExternalEmptyReason | None = None,
    deadline_kind: DeadlineKind | None = None,
    refusal_reason: DispatcherRefusalReason | None = None,
) -> ExternalBranchResult:
    return ExternalBranchResult(
        branch_id=branch_id,
        fanout_generation_id=generation_id,
        source=source,
        status=status,
        error_class=error_class,
        empty_reason=empty_reason,
        elapsed_ms=elapsed_ms,
        deadline_kind=deadline_kind,
        refusal_reason=refusal_reason,
    )


def _reserved_result(
    generation_id: str,
    branch_id: str,
    source: ExternalSource,
) -> ExternalBranchResult:
    return _failure_result(
        generation_id=generation_id,
        branch_id=branch_id,
        source=source,
        status=ExternalBranchStatus.RESERVED_UNAVAILABLE,
        empty_reason=ExternalEmptyReason.RESERVED_SOURCE_UNAVAILABLE,
        elapsed_ms=0.0,
    )


def _timeout_result(
    *,
    generation_id: str,
    branch_id: str,
    source: ExternalSource,
    elapsed_ms: float,
    deadline_kind: DeadlineKind,
) -> ExternalBranchResult:
    return ExternalBranchResult(
        branch_id=branch_id,
        fanout_generation_id=generation_id,
        source=source,
        status=ExternalBranchStatus.TIMEOUT,
        empty_reason=ExternalEmptyReason.DEADLINE_REACHED,
        error_class=ExternalErrorClass.TIMEOUT,
        elapsed_ms=elapsed_ms,
        deadline_kind=deadline_kind,
        late_result_ignored=True,
    )


def _limitation_for(result: ExternalBranchResult) -> AvailabilityLimitation | None:
    if result.status is ExternalBranchStatus.SUCCESS:
        return None
    if result.status is ExternalBranchStatus.TIMEOUT:
        return AvailabilityLimitation.SOURCE_TIMEOUT
    if result.status is ExternalBranchStatus.RESERVED_UNAVAILABLE:
        return AvailabilityLimitation.RESERVED_SOURCE_UNAVAILABLE
    if result.error_class is ExternalErrorClass.SUBJECT_BOUNDARY_REFUSED:
        return AvailabilityLimitation.THIRD_PARTY_SUBJECT_BOUNDARY
    return AvailabilityLimitation.FRESH_ATTEMPT_FAILED


def _append_limitation(
    limitations: list[AvailabilityLimitation],
    limitation: AvailabilityLimitation | None,
) -> None:
    if limitation is not None and limitation not in limitations:
        limitations.append(limitation)


def _stable_sources(sources: Sequence[ExternalSource]) -> list[ExternalSource]:
    return sorted(sources, key=lambda source: (_source_priority(source), source.value))


def _source_priority(source: ExternalSource) -> int:
    try:
        return SOURCE_PRIORITY.index(source)
    except ValueError:
        return len(SOURCE_PRIORITY)


def _branch_id(generation_id: str, source: ExternalSource) -> str:
    return f"{generation_id}:{source.value}"


def _extract_urls(text: str) -> list[str]:
    return [match.group(0).rstrip(".,;!?") for match in URL_RE.finditer(text)]


def _has_sensitive_query(url: str) -> bool:
    if "?" not in url:
        return False
    query = url.split("?", 1)[1].split("#", 1)[0]
    keys = {part.split("=", 1)[0].lower() for part in query.split("&") if part}
    return bool(keys & SENSITIVE_QUERY_KEYS)


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _default_subject_boundary_refused(
    _source: ExternalSource,
    utterance: str,
    _conversation_state: Mapping[str, Any],
) -> bool:
    lowered = utterance.lower()
    if not any(verb in lowered for verb in ("research", "look up", "search for")):
        return False
    return bool(re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", utterance))
