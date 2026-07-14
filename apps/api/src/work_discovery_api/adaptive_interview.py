from __future__ import annotations

from dataclasses import dataclass

from work_discovery_api.domain import AnswerStatus
from work_discovery_api.models import (
    AnswerRead,
    CoverageItemRead,
    CoverageRead,
    NextQuestionRead,
    QuestionRead,
)


@dataclass(frozen=True, slots=True)
class CoverageRule:
    key: str
    label: str
    question_ids: tuple[str, ...]
    fallback_question_id: str
    fallback_text: str


COVERAGE_RULES = (
    CoverageRule(
        "role",
        "역할과 책임",
        ("Q-ROLE-001",),
        "Q-ROLE-001",
        "현재 역할과 결과 책임을 다시 구체화해주세요.",
    ),
    CoverageRule(
        "target_work",
        "분석 대상 업무",
        ("Q-ROLE-003",),
        "Q-ROLE-003",
        "이번에 분석할 업무 하나를 더 정확히 골라주세요.",
    ),
    CoverageRule(
        "frequency",
        "반복 빈도",
        ("Q-ROLE-002", "Q-METRIC-001"),
        "Q-METRIC-001",
        "이 업무는 하루, 주, 월에 몇 번 정도 발생하나요?",
    ),
    CoverageRule(
        "value",
        "업무 가치",
        ("Q-GOAL-001", "Q-GOAL-002"),
        "Q-GOAL-001",
        "이 결과를 누가 왜 사용하는지 설명해주세요.",
    ),
    CoverageRule(
        "boundary",
        "시작과 완료 조건",
        ("Q-SCOPE-001",),
        "Q-SCOPE-001",
        "어디서 시작되고 어떤 상태면 끝났다고 보나요?",
    ),
    CoverageRule(
        "recent_case",
        "최근 실제 사례",
        ("Q-CASE-001", "Q-CASE-002"),
        "Q-CASE-001",
        "가장 최근 한 건을 처음부터 실제 순서대로 설명해주세요.",
    ),
    CoverageRule(
        "input_output",
        "입력과 결과물",
        ("Q-CASE-003", "Q-DATA-001"),
        "Q-CASE-003",
        "처음 받은 정보와 마지막 결과물을 구체적으로 말해주세요.",
    ),
    CoverageRule(
        "tools",
        "도구와 시스템",
        ("Q-CASE-004", "Q-SYS-001"),
        "Q-CASE-004",
        "사용한 프로그램, 사이트, 파일, 메일과 메신저를 순서대로 알려주세요.",
    ),
    CoverageRule(
        "decision_rules",
        "판단과 규칙",
        ("Q-DECISION-001", "Q-DECISION-002"),
        "Q-DECISION-001",
        "가장 판단이 어려운 순간과 그때 보는 단서를 설명해주세요.",
    ),
    CoverageRule(
        "exceptions",
        "예외와 복구",
        ("Q-EXC-001", "Q-EXC-003"),
        "Q-EXC-001",
        "평소 방식대로 처리할 수 없었던 최근 사례가 있나요?",
    ),
)


class DeterministicAdaptiveQuestionSelector:
    def coverage(
        self,
        interview_id: str,
        answers: tuple[AnswerRead, ...],
    ) -> CoverageRead:
        items = tuple(item for item in (coverage_item(rule, answers) for rule in COVERAGE_RULES))
        covered = sum(1 for item in items if item.status == "COVERED")
        return CoverageRead(
            interview_id=interview_id,
            covered_count=covered,
            total_count=len(items),
            items=items,
        )

    def next_question(
        self,
        interview_id: str,
        questions: tuple[QuestionRead, ...],
        answers: tuple[AnswerRead, ...],
    ) -> NextQuestionRead:
        question_by_id = {question.id: question for question in questions}
        for rule in COVERAGE_RULES:
            item = coverage_item(rule, answers)
            if item.status == "COVERED":
                continue
            selected = question_by_id.get(rule.fallback_question_id)
            text = selected.text if selected is not None else rule.fallback_text
            return NextQuestionRead(
                interview_id=interview_id,
                complete=False,
                coverage_key=rule.key,
                question_id=rule.fallback_question_id,
                text=text,
                reason=f"{rule.label} coverage is {item.status}.",
            )
        return NextQuestionRead(
            interview_id=interview_id,
            complete=True,
            coverage_key=None,
            question_id=None,
            text=None,
            reason="모든 M3 coverage 항목이 최소 한 개 이상의 답변 근거를 갖고 있습니다.",
        )


def coverage_item(rule: CoverageRule, answers: tuple[AnswerRead, ...]) -> CoverageItemRead:
    evidence_count = 0
    attempted = False
    for answer in answers:
        if answer.question_id not in rule.question_ids:
            continue
        attempted = True
        if answer.status == AnswerStatus.ANSWERED and answer.text.strip():
            evidence_count += 1
    status = "COVERED" if evidence_count > 0 else "NEEDS_EVIDENCE" if attempted else "OPEN"
    return CoverageItemRead(
        key=rule.key,
        label=rule.label,
        status=status,
        evidence_count=evidence_count,
        question_ids=rule.question_ids,
    )
