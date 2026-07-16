from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from work_discovery_api.models import (
    AnswerRead,
    InterviewRead,
    JsonObject,
    ProjectRead,
    QuestionRead,
    utc_now,
)
from work_discovery_api.recovery_evidence import (
    build_authority_constraints,
    build_decisions,
    build_exceptions,
    build_metrics,
    build_rules,
    build_structured_artifacts,
    build_systems,
    parse_recovery_evidence,
)


@dataclass(frozen=True, slots=True)
class WorkModelBuildInput:
    project: ProjectRead
    interview: InterviewRead
    questions: tuple[QuestionRead, ...]
    answers: tuple[AnswerRead, ...]


@dataclass(frozen=True, slots=True)
class InsufficientAnswersError(Exception):
    answered_count: int
    required_count: int

    def __str__(self) -> str:
        return f"need {self.required_count} completed questions, got {self.answered_count}"


class DeterministicWorkModelBuilder:
    def build(self, source: WorkModelBuildInput) -> JsonObject:
        latest_answers = latest_answer_by_question(source.answers)
        if len(latest_answers) < len(source.questions):
            raise InsufficientAnswersError(
                answered_count=len(latest_answers),
                required_count=len(source.questions),
            )

        answer_refs = tuple(answer.id for answer in latest_answers)
        recovery = parse_recovery_evidence(source.answers)
        now = utc_now().isoformat()
        meta = assertion_meta(answer_refs)
        recovery_meta = assertion_meta(recovery.source_refs, confirmed=True)
        title = source.project.name
        summary = summarize_answers(latest_answers)
        step_answers = meaningful_answers(latest_answers)[:3] or latest_answers[:1]

        return {
            "model_id": stable_id("wm", source.interview.id),
            "project_id": source.project.id,
            "version": 1,
            "lifecycle_stage": "AS_IS",
            "title": title,
            "summary": summary,
            "model_status": "PLAYBACK_PENDING",
            "participants": [
                {
                    "id": "role-user",
                    "kind": "ROLE",
                    "name": "업무 설명자",
                    "roles": ["수행자"],
                    "responsibilities": ["인터뷰에서 설명한 업무 수행"],
                    "meta": meta,
                },
            ],
            "goals": [
                {
                    "id": "goal-understand-work",
                    "statement": goal_statement(latest_answers),
                    "beneficiary_refs": ["role-user"],
                    "success_measures": ["업무 흐름과 근거가 사용자에게 확인된다."],
                    "meta": meta,
                },
            ],
            "processes": [
                {
                    "id": "process-discovered-work",
                    "name": title,
                    "description": summary,
                    "owner_refs": ["role-user"],
                    "performer_refs": ["role-user"],
                    "goal_refs": ["goal-understand-work"],
                    "trigger": {
                        "description": first_text(latest_answers, "업무가 필요해지는 시점"),
                        "event_type": "MANUAL",
                        "meta": meta,
                    },
                    "completion_condition": {
                        "description": "사용자가 기대하는 결과물이 준비된 상태",
                        "event_type": "OTHER",
                        "meta": meta,
                    },
                    "steps": build_steps(step_answers, meta),
                    "variants": [],
                    "frequency": {
                        "count": {"min": 1, "max": 1, "typical": 1},
                        "period": "UNKNOWN",
                        "meta": meta,
                    },
                    "volume": {
                        "count": {"min": 1, "max": 1, "typical": 1},
                        "period": "UNKNOWN",
                        "scope": "PERSON",
                        "meta": meta,
                    },
                    "meta": meta,
                },
            ],
            "artifacts": [
                {
                    "id": "artifact-interview-notes",
                    "kind": "DOCUMENT",
                    "name": "인터뷰 답변",
                    "direction": "IN",
                    "format": "TEXT",
                    "data_fields": [],
                    "data_classification": "UNKNOWN",
                    "retention": "프로젝트 보존 정책에 따름",
                    "meta": meta,
                },
                *build_structured_artifacts(recovery, recovery_meta),
            ],
            "systems": [
                {
                    "id": "system-user-described",
                    "name": "사용자가 언급한 업무 도구",
                    "kind": "OTHER",
                    "access_method": "UNKNOWN",
                    "stability": "UNKNOWN",
                    "permission_notes": "M2 mock builder는 실제 시스템 자격증명을 수집하지 않는다.",
                    "meta": meta,
                },
                *build_systems(recovery, recovery_meta),
            ],
            "decisions": build_decisions(recovery, recovery_meta),
            "rules": build_rules(recovery, recovery_meta),
            "exceptions": build_exceptions(recovery, recovery_meta),
            "pain_points": pain_points(latest_answers, meta),
            "metrics": build_metrics(recovery, recovery_meta),
            "constraints": [
                {
                    "id": "constraint-no-external-execution",
                    "category": "SECURITY",
                    "constraint_kind": "SAFETY_POLICY",
                    "statement": "M2는 외부 시스템 실행과 실제 자격증명 수집을 하지 않는다.",
                    "hard": True,
                    "meta": meta,
                },
                *build_authority_constraints(recovery, recovery_meta),
            ],
            "non_goals": [
                "실제 LLM 호출",
                "STT 처리",
                "외부 자동화 실행",
                "G1 명세 생성",
                *recovery.values.get("non_goals", ()),
            ],
            "understanding_gate": {
                "epistemic_coverage": 0.9 if recovery.present else 0.65,
                "operational_readiness": 0.85 if recovery.present else 0.55,
                "risk_clarity": 0.85 if recovery.present else 0.5,
                "recent_case_present": True,
                "playback_confirmed": False,
                "open_material_gaps": [],
                "result": "READY_WITH_ASSUMPTIONS",
            },
            "evidence_summary": {
                "claim_count": len(latest_answers),
                "source_link_rate": 1,
                "confirmed_claim_rate": round(recovery.coverage, 2) if recovery.present else 0,
                "open_contradiction_count": 0,
            },
            "created_at": now,
            "updated_at": now,
        }


def latest_answer_by_question(answers: tuple[AnswerRead, ...]) -> tuple[AnswerRead, ...]:
    latest: dict[str, AnswerRead] = {}
    for answer in answers:
        latest[answer.question_id] = answer
    return tuple(latest[key] for key in sorted(latest))


def meaningful_answers(answers: tuple[AnswerRead, ...]) -> tuple[AnswerRead, ...]:
    return tuple(answer for answer in answers if answer.text.strip())


def first_text(answers: tuple[AnswerRead, ...], fallback: str) -> str:
    for answer in answers:
        text = answer.text.strip()
        if text:
            return text[:1000]
    return fallback


def summarize_answers(answers: tuple[AnswerRead, ...]) -> str:
    texts = [answer.text.strip() for answer in answers if answer.text.strip()]
    if not texts:
        return "사용자가 10문항 질문지에 모름 또는 건너뛰기로 응답한 업무 모델 초안"
    return " / ".join(texts[:3])[:4000]


def goal_statement(answers: tuple[AnswerRead, ...]) -> str:
    text = first_text(answers, "업무 결과를 명확히 하고 개선 가능성을 판단한다.")
    return f"'{text[:180]}' 업무를 이해하고 개선 가능성을 판단한다."


def assertion_meta(source_refs: tuple[str, ...], *, confirmed: bool = False) -> JsonObject:
    return {
        "state": "CORROBORATED" if confirmed else "CLAIMED",
        "confidence": 0.9 if confirmed else 0.65,
        "source_refs": list(source_refs),
        "validated_by": [],
        "last_validated_at": None,
    }


def build_steps(answers: tuple[AnswerRead, ...], meta: JsonObject) -> list[JsonObject]:
    steps: list[JsonObject] = []
    for index, answer in enumerate(answers, start=1):
        step_id = f"step-{index:03d}"
        next_step_refs = [f"step-{index + 1:03d}"] if index < len(answers) else []
        steps.append(
            {
                "id": step_id,
                "sequence": index,
                "name": f"인터뷰 기반 단계 {index}",
                "action": answer.text.strip()
                or f"{answer.question_id}에 대한 상태 응답을 기록한다.",
                "performer_refs": ["role-user"],
                "input_refs": ["artifact-interview-notes"],
                "output_refs": ["artifact-interview-notes"],
                "system_refs": ["system-user-described"],
                "decision_refs": [],
                "exception_refs": [],
                "next_step_refs": next_step_refs,
                "manual_touch": True,
                "reversible": True,
                "meta": meta,
            },
        )
    return steps


def pain_points(answers: tuple[AnswerRead, ...], meta: JsonObject) -> list[JsonObject]:
    text = first_text(answers, "아직 명확한 불편 요소가 확인되지 않았다.")
    return [
        {
            "id": "pain-interview-reported",
            "statement": text[:2000],
            "category": "OTHER",
            "severity": 3,
            "target_refs": ["process-discovered-work"],
            "meta": meta,
        },
    ]


def stable_id(prefix: str, seed: str) -> str:
    return f"{prefix}-{uuid5(NAMESPACE_URL, seed)}"
