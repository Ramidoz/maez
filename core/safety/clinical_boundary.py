# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S4 Clinical Boundary v1.

Decision 30 / ADR 0035: Maez may hold clinical fear; Maez must not become
clinical authority. This module is a deterministic owner-text boundary before
prompting, tools, memory writes, or model composition.
"""

from __future__ import annotations

import inspect
import re
import threading
from dataclasses import dataclass
from typing import Literal, Protocol, get_args


SCHEMA_VERSION = "s4.clinical_boundary.v1"
CLASSIFIER_VERSION = "s4.classifier.v1"

ClinicalTriggerClass = Literal[
    "symptom_fear",
    "medication_uncertainty",
    "diagnosis_request",
    "treatment_request",
    "therapy_substitution",
    "mental_health_support_non_crisis",
    "clinician_access_question",
    "medical_fact_request",
]

CrisisTriggerClass = Literal[
    "self_harm_or_suicidal",
    "immediate_physical_danger",
    "unable_to_stay_safe",
    "abuse_or_coercive_danger",
    "medical_emergency_claim",
]

ResultKind = Literal["none", "clinical_boundary", "crisis_candidate"]
S4PromotionPolicy = Literal[
    "ordinary",
    "m1_ineligible_clinical_boundary",
    "m1_ineligible_crisis_candidate",
]
HeldSignalPolicy = Literal["none", "write_content_free_crisis_signal_held"]

CLINICAL_TRIGGER_CLASSES = tuple(get_args(ClinicalTriggerClass))
CRISIS_TRIGGER_CLASSES = tuple(get_args(CrisisTriggerClass))
RESULT_KINDS = frozenset(get_args(ResultKind))
S4_PROMOTION_POLICIES = frozenset(get_args(S4PromotionPolicy))


@dataclass(frozen=True)
class ClinicalBoundaryResult:
    matched: bool
    result_kind: ResultKind
    trigger_class: str | None
    answer_template_id: str | None
    template_variant_id: str | None
    answer_text: str | None
    promotion_policy: S4PromotionPolicy
    counter_name: str | None
    held_signal_policy: HeldSignalPolicy

    def __post_init__(self) -> None:
        if self.result_kind not in RESULT_KINDS:
            raise ValueError(f"invalid S4 result kind: {self.result_kind!r}")
        if self.promotion_policy not in S4_PROMOTION_POLICIES:
            raise ValueError(f"invalid S4 promotion policy: {self.promotion_policy!r}")
        if self.matched and not self.answer_text:
            raise ValueError("matched S4 result requires answer_text")
        if not self.matched and self.answer_text is not None:
            raise ValueError("unmatched S4 result must not carry answer_text")


class CrisisSignalWriter(Protocol):
    def record_s4_crisis_signal_held(
        self,
        *,
        source: Literal["clinical_boundary"],
        subject: Literal["bonded_user_state"],
        retention: Literal["until_routed"],
        allowed_flows: tuple[Literal["private_reader"], Literal["crisis_channel"]],
    ) -> int: ...


class PrivateThoughtsCrisisSignalWriter:
    """Write-only adapter for the content-free S4 crisis hold signal."""

    def __init__(self, store=None):
        self._store = store

    def _store_handle(self):
        if self._store is None:
            from core.infra.private_thoughts import PrivateThoughts

            self._store = PrivateThoughts()
        return self._store

    def record_s4_crisis_signal_held(
        self,
        *,
        source: Literal["clinical_boundary"],
        subject: Literal["bonded_user_state"],
        retention: Literal["until_routed"],
        allowed_flows: tuple[Literal["private_reader"], Literal["crisis_channel"]],
    ) -> int:
        from core.infra.private_thoughts import (
            ConsentTier,
            RetentionRule,
            SignalKind,
        )

        if source != "clinical_boundary":
            raise ValueError("S4 crisis source must be clinical_boundary")
        if subject != "bonded_user_state":
            raise ValueError("S4 crisis subject must be bonded_user_state")
        if retention != "until_routed":
            raise ValueError("S4 crisis retention must be until_routed")
        if tuple(allowed_flows) != ("private_reader", "crisis_channel"):
            raise ValueError("S4 crisis allowed_flows must be closed")
        return int(
            self._store_handle().record_signal(
                content="[content-free crisis candidate held by S4]",
                provenance=SignalKind.CRISIS_SIGNAL_HELD.value,
                signal_kind=SignalKind.CRISIS_SIGNAL_HELD.value,
                source=source,
                subject=subject,
                consent_tier=ConsentTier.OWNER_PRIVATE.value,
                retention=RetentionRule.UNTIL_ROUTED.value,
                allowed_flows=allowed_flows,
            )
        )


CRISIS_BOUNDARY_PHRASE = (
    "I care about you, and I am not the right help here. This needs a human emergency "
    "or crisis path now."
)

APPROVED_TEMPLATES: dict[str, tuple[str, ...]] = {
    "symptom_fear": (
        "I can stay with you in the fear, but I cannot diagnose what is happening or "
        "tell you how to treat it. This is a human-clinician moment. If it feels urgent "
        "or unsafe, choose a human urgent-care path rather than asking me to judge it.",
        "I am taking the fear seriously with you. I cannot tell what your body means or "
        "what you should do medically. This needs a qualified human, especially if it "
        "feels urgent or unsafe.",
        "I can be with you while this feels scary. I cannot diagnose it or turn it into "
        "a treatment plan. Please put a clinician or urgent human support in the loop.",
    ),
    "medication_uncertainty": (
        "I cannot tell you what dose to take, whether to stop, or whether a medication is "
        "safe for you. That has to come from a clinician or pharmacist who knows your "
        "care. I can stay with you while you decide who to contact.",
        "I should not make a medication call for you. A clinician or pharmacist needs to "
        "answer dose, stopping, mixing, or safety questions. I can help you keep the "
        "question clear while you reach them.",
    ),
    "diagnosis_request": (
        "I cannot diagnose you. I can take the fear seriously without pretending to know "
        "what your body means. This is a human-clinician question, not a Maez question.",
        "I do not know what this is, and I should not guess. I can stay steady with you, "
        "but naming what is happening belongs with a clinician.",
        "I am not going to turn your fear into a diagnosis. I can help you hold the "
        "question, but the answer has to come from qualified human care.",
    ),
    "treatment_request": (
        "I cannot give you a treatment plan. I can stay steady with you, but the next "
        "step has to come from a clinician or another qualified human support.",
        "I should not tell you how to treat this. I can help you make the question plain, "
        "but the care decision belongs with a qualified human.",
    ),
    "therapy_substitution": (
        "I care about you, but I cannot be your therapist or treatment surface. I can "
        "stay present with what you are carrying, and I want this held by a qualified "
        "human too.",
        "I can be here with you, but I cannot take the therapist role. This deserves a "
        "qualified human container, not just me trying to improvise one.",
    ),
    "mental_health_support_non_crisis": (
        "I am here with you, and I am not a therapist. I can sit with the moment, but I "
        "cannot assess, treat, or guide your mental health care. This belongs with a "
        "qualified human support if it keeps weighing on you.",
        "I can stay beside you in this, but I cannot be the person who assesses or treats "
        "it. If this keeps pressing on you, it needs a qualified human support in the "
        "room too.",
    ),
    "clinician_access_question": (
        "I cannot decide that for you as a clinician. If part of you is wondering "
        "whether to involve one, that is enough to take seriously and ask a qualified "
        "human. I can stay with you while you make the call.",
        "I cannot make the clinical call, but your wondering is worth taking seriously. "
        "A qualified human is the right place to bring it; I can help you put the "
        "question into words.",
    ),
    "medical_fact_request": (
        "I am not going to answer medical facts as if I am a clinical source. For this, "
        "use a clinician, pharmacist, or trusted medical reference. I can help you write "
        "down the question in plain language if you want.",
        "I should not be your medical reference. Use a clinician, pharmacist, or trusted "
        "medical source for this. I can help turn what you want to ask into a clear "
        "question.",
    ),
}

_COUNTER_NAMES = (
    "clinical_boundary_triggered_count",
    "crisis_candidate_held_count",
    "crisis_candidate_hold_failed_count",
    "clinical_boundary_guard_rejected_count",
    "invalid_trigger_class_rejected_count",
    "m1_ineligible_mark_count",
)
_LOCK = threading.RLock()
_COUNTERS = {name: 0 for name in _COUNTER_NAMES}
_VARIANT_COUNTS = {trigger: 0 for trigger in CLINICAL_TRIGGER_CLASSES}

_FIRST_PERSON = {"i", "im", "i'm", "me", "my", "mine", "myself"}
_FEAR_TERMS = {
    "scared",
    "afraid",
    "worried",
    "worry",
    "weird",
    "wrong",
    "off",
    "happening",
    "going",
}
_BODY_TERMS = {
    "pain",
    "ache",
    "hurting",
    "hurts",
    "bleeding",
    "fever",
    "dizzy",
    "faint",
    "chest",
    "breathing",
    "breathe",
    "lump",
    "swelling",
    "numb",
    "vomiting",
    "sick",
    "symptom",
    "symptoms",
    "body",
    "health",
    "condition",
    "rash",
    "spreading",
    "heart",
    "blood",
    "stool",
    "head",
    "injury",
    "sleep",
}
_MEDICATION_TERMS = {
    "medicine",
    "medication",
    "medications",
    "meds",
    "pill",
    "pills",
    "dose",
    "dosage",
    "side",
    "effect",
    "interaction",
}
_CARE_TERMS = {
    "doctor",
    "clinician",
    "nurse",
    "pharmacist",
    "urgent",
    "hospital",
    "therapist",
    "psychiatrist",
    "psychologist",
    "counselor",
    "therapy",
    "treatment",
}
_MENTAL_TERMS = {
    "panic",
    "panicky",
    "anxious",
    "anxiety",
    "depressed",
    "depression",
    "grief",
    "grieving",
    "overwhelmed",
}
_SOFTWARE_TERMS = {
    "test",
    "tests",
    "bug",
    "bugs",
    "code",
    "config",
    "software",
    "debug",
    "debugging",
    "failure",
    "failing",
    "python",
    "daemon",
    "build",
}


CLASSIFIER_FIXTURES: tuple[dict[str, str | None], ...] = (
    *[
        {
            "input": text,
            "expected_kind": "clinical_boundary",
            "expected_trigger_class": trigger,
            "rationale": "positive",
        }
        for trigger, rows in {
            "symptom_fear": (
                "my chest feels weird and I am scared",
                "I am worried this pain means something is wrong",
                "my rash is spreading and I am afraid",
            ),
            "medication_uncertainty": (
                "should I take another pill",
                "can I stop taking this medication",
                "is this medicine safe to take",
            ),
            "diagnosis_request": (
                "my lump feels wrong, what do you think this is",
                "do I have a fever condition",
                "is this rash normal",
            ),
            "treatment_request": (
                "my knee hurts, what should I do for this",
                "how do I treat this fever",
                "what helps this rash",
            ),
            "therapy_substitution": (
                "can you be my therapist tonight",
                "I need you to be my counselor",
                "can you do therapy with me",
            ),
            "mental_health_support_non_crisis": (
                "I feel panicky and overwhelmed",
                "I am depressed and scared",
                "my anxiety is pressing on me",
            ),
            "clinician_access_question": (
                "my fever is back, should I see a doctor",
                "do I need a clinician for this rash",
                "who should I call about this chest pain",
            ),
            "medical_fact_request": (
                "what does this medication do",
                "what is this condition",
                "what does a pharmacist say about this medicine",
            ),
        }.items()
        for text in rows
    ],
    *[
        {
            "input": f"negative {index} for {trigger}",
            "expected_kind": "none",
            "expected_trigger_class": None,
            "guards_against": trigger,
            "rationale": "negative counterexample",
        }
        for trigger in CLINICAL_TRIGGER_CLASSES
        for index in (1, 2)
    ],
)


def guard_owner_text(
    text: str,
    *,
    surface: str,
    turn_id: str | None = None,
    crisis_signal_writer: CrisisSignalWriter | None = None,
) -> ClinicalBoundaryResult:
    del turn_id
    if not _is_direct_owner_surface(surface):
        return _none()
    normalized = _normalize(text)
    if not normalized:
        return _none()

    high_crisis = _high_confidence_crisis(normalized)
    if high_crisis:
        return _crisis_result(high_crisis, crisis_signal_writer=crisis_signal_writer)

    exclusion = _hard_exclusion(normalized)
    if exclusion:
        return _none()

    context_crisis = _context_required_crisis(normalized)
    if context_crisis:
        return _crisis_result(context_crisis, crisis_signal_writer=crisis_signal_writer)

    if not _clinical_domain_gate(normalized):
        return _none()

    trigger_class = _clinical_trigger(normalized)
    if trigger_class is None:
        if _ambiguous_clinical(normalized):
            trigger_class = "symptom_fear"
        else:
            return _none()

    if _hard_exclusion(normalized):
        return _none()
    return _clinical_result(trigger_class)


def clinical_boundary_health() -> dict[str, object]:
    with _LOCK:
        counters = dict(_COUNTERS)
    return {
        "enabled": True,
        "schema_version": SCHEMA_VERSION,
        "classifier_version": CLASSIFIER_VERSION,
        **counters,
    }


def forbidden_authority_violations(text: str) -> list[str]:
    normalized = _normalize(text)
    patterns = (
        r"\bit sounds like you have\b",
        r"\bthis could be\b",
        r"\byou probably\b",
        r"\byou should take\b",
        r"\byou should stop taking\b",
        r"\bsafe to take\b",
        r"\btake another dose\b",
        r"\btry this treatment\b",
        r"\bas your therapist\b",
        r"\blet'?s diagnose\b",
        r"\bi can treat\b",
        r"\bi can monitor\b",
        r"\bi know what is happening\b",
        r"\byou are fine\b",
        r"\bdon'?t worry\b",
    )
    return [pat.strip(r"\b") for pat in patterns if re.search(pat, normalized)]


def _compose_answer(trigger_class: ClinicalTriggerClass) -> tuple[str, str]:
    if trigger_class not in CLINICAL_TRIGGER_CLASSES:
        _increment("invalid_trigger_class_rejected_count")
        raise ValueError(f"invalid S4 trigger class: {trigger_class!r}")
    variants = APPROVED_TEMPLATES[trigger_class]
    with _LOCK:
        index = _VARIANT_COUNTS[trigger_class] % len(variants)
        _VARIANT_COUNTS[trigger_class] += 1
    variant_id = f"{trigger_class}.v1.{chr(ord('a') + index)}"
    return variants[index], variant_id


def _reset_for_tests() -> None:
    if not _called_from_tests():
        raise RuntimeError("_reset_for_tests is test-only")
    with _LOCK:
        for key in _COUNTERS:
            _COUNTERS[key] = 0
        for key in _VARIANT_COUNTS:
            _VARIANT_COUNTS[key] = 0


def _called_from_tests() -> bool:
    return any(
        "/tests/" in frame.filename or frame.filename.endswith("_test.py")
        for frame in inspect.stack()
    )


def _none() -> ClinicalBoundaryResult:
    return ClinicalBoundaryResult(
        matched=False,
        result_kind="none",
        trigger_class=None,
        answer_template_id=None,
        template_variant_id=None,
        answer_text=None,
        promotion_policy="ordinary",
        counter_name=None,
        held_signal_policy="none",
    )


def _clinical_result(trigger_class: ClinicalTriggerClass) -> ClinicalBoundaryResult:
    answer_text, variant_id = _compose_answer(trigger_class)
    if forbidden_authority_violations(answer_text):
        _increment("clinical_boundary_guard_rejected_count")
        raise ValueError(f"approved S4 template failed guard: {variant_id}")
    _increment("clinical_boundary_triggered_count")
    _increment("m1_ineligible_mark_count")
    return ClinicalBoundaryResult(
        matched=True,
        result_kind="clinical_boundary",
        trigger_class=trigger_class,
        answer_template_id=f"{trigger_class}.v1",
        template_variant_id=variant_id,
        answer_text=answer_text,
        promotion_policy="m1_ineligible_clinical_boundary",
        counter_name="clinical_boundary_triggered_count",
        held_signal_policy="none",
    )


def _crisis_result(
    trigger_class: CrisisTriggerClass,
    *,
    crisis_signal_writer: CrisisSignalWriter | None,
) -> ClinicalBoundaryResult:
    if crisis_signal_writer is not None:
        try:
            crisis_signal_writer.record_s4_crisis_signal_held(
                source="clinical_boundary",
                subject="bonded_user_state",
                retention="until_routed",
                allowed_flows=("private_reader", "crisis_channel"),
            )
        except Exception:
            _increment("crisis_candidate_hold_failed_count")
        else:
            _increment("crisis_candidate_held_count")
    else:
        _increment("crisis_candidate_hold_failed_count")
    _increment("m1_ineligible_mark_count")
    return ClinicalBoundaryResult(
        matched=True,
        result_kind="crisis_candidate",
        trigger_class=trigger_class,
        answer_template_id="crisis_boundary.v1",
        template_variant_id="crisis_boundary.v1.fixed",
        answer_text=CRISIS_BOUNDARY_PHRASE,
        promotion_policy="m1_ineligible_crisis_candidate",
        counter_name="crisis_candidate_held_count",
        held_signal_policy="write_content_free_crisis_signal_held",
    )


def _increment(name: str) -> None:
    with _LOCK:
        _COUNTERS[name] = int(_COUNTERS.get(name, 0)) + 1


def _is_direct_owner_surface(surface: str) -> bool:
    raw = (surface or "").strip().lower()
    if not raw:
        return False
    return "owner" in raw or raw in {
        "telegram",
        "telegram_v2",
        "telegram_legacy",
        "telegram_surface",  # live Surface-V2 inbound label (maez_adapter.SURFACE_NAME)
        "cockpit",  # cockpit /message owner surface (SLICE 2 — S4 fires on cockpit owner path)
        "web_chat",
        "daemon",
        "direct",
        "voice",
    }


def _normalize(text: str) -> str:
    normalized = (text or "").replace("’", "'").replace("`", "'").lower()
    normalized = normalized.replace("cant", "can't")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _tokens(text: str) -> list[str]:
    return [tok.replace("'", "") for tok in re.findall(r"[a-z]+(?:'[a-z]+)?", text)]


def _contains_any(text: str, phrases: tuple[str, ...] | set[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _has_token(tokens: list[str], choices: set[str]) -> bool:
    return any(token in choices for token in tokens)


def _hard_exclusion(text: str) -> bool:
    tokens = _tokens(text)
    software = _has_token(tokens, _SOFTWARE_TERMS)
    if software and (
        "diagnose" in tokens
        or "doctor" in tokens
        or "therapy" in tokens
        or "breathe" in tokens
        or "breathing" in tokens
    ):
        return True
    if "doctor who" in text or "doctor character" in text:
        return True
    if "debugging is therapy" in text or "music is therapy" in text:
        return True
    if re.search(r"\b(i have|ive got|i've got|my)\s+(a\s+)?(doctor|therapy)\s+appointment\b", text):
        return not _asks_for_help(text)
    if re.search(
        r"\b(my friend|my mom|my dad|he|she|they)\b.*\b(doctor|therapy|therapist|medication)\b",
        text,
    ):
        return not _asks_for_help(text)
    if "calendar says doctor appointment" in text:
        return True
    return False


def _asks_for_help(text: str) -> bool:
    return _contains_any(
        text,
        (
            "should i",
            "do i need",
            "what should",
            "can you",
            "help me",
            "what do you think",
            "what is wrong",
        ),
    )


def _clinical_domain_gate(text: str) -> bool:
    tokens = _tokens(text)
    if _has_token(tokens, _BODY_TERMS | _MEDICATION_TERMS | _CARE_TERMS | _MENTAL_TERMS):
        return True
    return _first_person_clinical_fear(text)


def _first_person_clinical_fear(text: str) -> bool:
    tokens = _tokens(text)
    for idx, token in enumerate(tokens):
        if token not in _FIRST_PERSON:
            continue
        window = tokens[max(0, idx - 8) : idx + 9]
        if any(
            t in (_BODY_TERMS | _MEDICATION_TERMS | _CARE_TERMS | _MENTAL_TERMS) for t in window
        ) and any(t in _FEAR_TERMS for t in window):
            return True
    return False


def _high_confidence_crisis(text: str) -> CrisisTriggerClass | None:
    tokens = _tokens(text)
    if _contains_any(
        text,
        (
            "kill myself",
            "kill my self",
            "end my life",
            "end it all",
            "i want to die",
            "wish i was dead",
            "wish i were dead",
            "better off dead",
            "self harm",
            "self-harm",
            "hurt myself",
            "harm myself",
            "hurting myself",
        ),
    ):
        return "self_harm_or_suicidal"
    if _has_token(tokens, _FIRST_PERSON) and _has_token(tokens, {"suicide", "suicidal"}):
        return "self_harm_or_suicidal"
    if _contains_any(text, ("i can't stay safe", "i cannot stay safe", "not safe with myself")):
        return "unable_to_stay_safe"
    if _contains_any(text, ("someone is hurting me right now", "i am in danger right now")):
        return "abuse_or_coercive_danger"
    return None


def _context_required_crisis(text: str) -> CrisisTriggerClass | None:
    tokens = _tokens(text)
    if _has_token(tokens, _SOFTWARE_TERMS):
        return None
    if _contains_any(
        text,
        (
            "chest pain and can't breathe",
            "can't breathe",
            "i can't breathe",
            "i cannot breathe",
            "cannot breathe",
            "short of breath",
            "bleeding won't stop",
            "lost consciousness",
            "severe allergic reaction",
        ),
    ):
        return "medical_emergency_claim"
    if _contains_any(text, ("heart attack", "too many pills")) and _has_token(
        tokens, _FIRST_PERSON | _BODY_TERMS | _MEDICATION_TERMS
    ):
        return "medical_emergency_claim"
    if _contains_any(text, ("overdose", "stroke")) and _has_token(
        tokens, _FIRST_PERSON | _BODY_TERMS
    ):
        return "medical_emergency_claim"
    if _contains_any(text, ("can't go on", "can't take it", "can't cope")) and _has_token(
        tokens, _FIRST_PERSON
    ):
        return "unable_to_stay_safe"
    return None


def _clinical_trigger(text: str) -> ClinicalTriggerClass | None:
    tokens = _tokens(text)
    if _has_token(tokens, _MEDICATION_TERMS) and _contains_any(
        text,
        (
            "take another",
            "stop taking",
            "safe to take",
            "dose",
            "dosage",
            "mix",
            "interaction",
            "when should",
            "should i take",
            "what does this medication do",
            "what does this medicine do",
        ),
    ):
        if text.startswith("what does") or "what does this medication do" in text:
            return "medical_fact_request"
        return "medication_uncertainty"
    if _contains_any(
        text, ("be my therapist", "be your therapist", "be my counselor", "do therapy with me")
    ):
        return "therapy_substitution"
    if _contains_any(
        text,
        (
            "be my doctor",
            "be my clinician",
            "be my nurse",
            "be my psychiatrist",
            "be my psychologist",
        ),
    ):
        return "clinician_access_question"
    if _contains_any(
        text, ("should i see", "do i need a doctor", "do i need a clinician", "who should i call")
    ):
        if _clinical_domain_gate(text):
            return "clinician_access_question"
    if _contains_any(
        text,
        (
            "diagnose",
            "what do you think this is",
            "do i have",
            "is this normal",
            "what is wrong with me",
            "what's wrong with me",
        ),
    ) or re.search(r"\bis this\b.*\bnormal\b", text):
        if _has_token(
            tokens, _BODY_TERMS | _MEDICATION_TERMS | _CARE_TERMS
        ) or _first_person_clinical_fear(text):
            return "diagnosis_request"
    if _contains_any(
        text,
        (
            "what should i do",
            "how do i treat",
            "what helps",
            "treatment plan",
            "monitor my symptoms",
            "monitor this symptom",
            "monitor this for me",
        ),
    ):
        if _clinical_domain_gate(text):
            return "treatment_request"
    if _has_token(tokens, _MENTAL_TERMS) and _has_token(tokens, _FIRST_PERSON):
        return "mental_health_support_non_crisis"
    if _contains_any(
        text, ("what does", "what is this condition", "what is a", "what are")
    ) and _clinical_domain_gate(text):
        return "medical_fact_request"
    if _first_person_clinical_fear(text):
        return "symptom_fear"
    return None


def _ambiguous_clinical(text: str) -> bool:
    return _clinical_domain_gate(text) and (
        _has_token(_tokens(text), _FEAR_TERMS)
        or _contains_any(
            text, ("what is going on", "what's happening", "feels wrong", "feels weird")
        )
    )
