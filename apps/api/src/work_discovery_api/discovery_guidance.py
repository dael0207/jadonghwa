from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from work_discovery_api.contracts import ContractPaths, read_json
from work_discovery_api.domain import InterviewStatus
from work_discovery_api.models import (
    DiscoveryDimensionRead,
    DiscoveryGuidanceRead,
    DiscoveryQuestionRead,
    InterviewRead,
    JsonValue,
    OpportunityRead,
    ReadinessRead,
    WorkModelRead,
)

RECOVERY_RESULTS = frozenset({"BLOCKED", "DISCOVERY_NEEDED"})
RECOVERABLE_STATUSES = frozenset(
    {
        InterviewStatus.PLAYBACK_CONFIRMATION,
        InterviewStatus.OPPORTUNITY_ANALYSIS_READY,
        InterviewStatus.FINALIZED,
    },
)

DIMENSIONS: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "INPUT_OUTPUT",
        "입력과 출력",
        ("structured input", "output artifacts", "feasibility"),
        ("Q-CASE-003",),
    ),
    (
        "TOOLS",
        "시스템과 도구",
        ("system access", "stability", "feasibility"),
        ("Q-CASE-004",),
    ),
    (
        "RULE",
        "규칙과 판단 기준",
        ("decision rules", "feasibility"),
        ("Q-DECISION-002", "Q-DECISION-001"),
    ),
    (
        "EXCEPTION",
        "예외와 복구",
        ("exception cases", "risk boundary", "human oversight"),
        ("Q-EXC-003",),
    ),
    (
        "AUTHORITY",
        "승인과 권한",
        ("approval", "authority", "human oversight", "risk"),
        ("Q-AUTH-001",),
    ),
    (
        "METRIC",
        "빈도와 성과 지표",
        ("frequency", "volume", "rework", "metric"),
        ("Q-METRIC-001", "Q-METRIC-002"),
    ),
    (
        "SCOPE",
        "비범위와 업무 경계",
        ("scope", "non-goal", "비범위"),
        ("Q-SCOPE-002",),
    ),
    (
        "EVIDENCE",
        "확인 가능한 근거",
        ("confirmed evidence", "confidence", "coverage"),
        ("Q-EVID-001",),
    ),
)


@dataclass(frozen=True, slots=True)
class DiscoveryGuidanceInput:
    paths: ContractPaths
    project_id: str
    interview: InterviewRead | None
    opportunity: OpportunityRead
    readiness: ReadinessRead
    work_model: WorkModelRead | None


def build_discovery_guidance(source: DiscoveryGuidanceInput) -> DiscoveryGuidanceRead:
    recovery_required = source.readiness.result in RECOVERY_RESULTS
    reasons = (
        *source.readiness.missing_evidence,
        *source.readiness.blocking_reasons,
        *source.readiness.required_followups,
        *work_model_gap_reasons(source.work_model),
    )
    dimensions = selected_dimensions(reasons) if recovery_required else ()
    questions = questions_for_dimensions(source.paths, dimensions) if recovery_required else ()
    latest_version = source.work_model.version if source.work_model else None
    confirmed = (
        source.work_model is not None
        and source.work_model.payload.get("model_status") == "CONFIRMED"
    )
    can_reanalyze = bool(
        recovery_required
        and source.interview is not None
        and source.interview.status == InterviewStatus.FINALIZED
        and source.interview.active_consent
        and confirmed
        and source.work_model is not None
        and source.work_model.schema_valid
        and source.work_model.version > source.opportunity.work_model_version
    )
    return DiscoveryGuidanceRead(
        project_id=source.project_id,
        interview_id=source.interview.id if source.interview else None,
        interview_status=source.interview.status if source.interview else None,
        gate_result=source.readiness.result,
        recovery_required=recovery_required,
        missing_dimensions=dimensions,
        recommended_questions=questions,
        suggested_evidence_prompt=evidence_prompt(dimensions),
        can_reopen=bool(
            recovery_required
            and source.interview is not None
            and source.interview.active_consent
            and source.interview.status in RECOVERABLE_STATUSES
        ),
        can_reanalyze=can_reanalyze,
        latest_work_model_version=latest_version,
        latest_opportunity_id=source.opportunity.id,
        latest_opportunity_work_model_version=source.opportunity.work_model_version,
    )


def selected_dimensions(reasons: Sequence[str]) -> tuple[DiscoveryDimensionRead, ...]:
    haystack = " ".join(reasons).lower()
    selected: list[DiscoveryDimensionRead] = []
    for key, label, markers, _question_ids in DIMENSIONS:
        matched = next(
            (
                reason
                for reason in reasons
                if any(marker in reason.lower() for marker in markers)
            ),
            None,
        )
        if matched is not None or any(marker in haystack for marker in markers):
            selected.append(DiscoveryDimensionRead(key=key, label=label, reason=matched or label))
    if not selected:
        selected.append(
            DiscoveryDimensionRead(
                key="EVIDENCE",
                label="확인 가능한 근거",
                reason="추가 근거가 필요합니다.",
            ),
        )
    return tuple(selected)


def questions_for_dimensions(
    paths: ContractPaths,
    dimensions: Sequence[DiscoveryDimensionRead],
) -> tuple[DiscoveryQuestionRead, ...]:
    bank = read_json(paths.question_bank)
    raw_questions = bank.get("questions")
    question_by_id: dict[str, Mapping[str, JsonValue]] = {}
    if isinstance(raw_questions, list):
        for raw in raw_questions:
            if isinstance(raw, dict) and isinstance(raw.get("id"), str):
                question_by_id[str(raw["id"])] = raw
    selected_keys = {dimension.key for dimension in dimensions}
    result: list[DiscoveryQuestionRead] = []
    for key, _label, _markers, question_ids in DIMENSIONS:
        if key not in selected_keys:
            continue
        for question_id in question_ids:
            raw = question_by_id.get(question_id)
            if raw is None:
                continue
            result.append(
                DiscoveryQuestionRead(
                    id=question_id,
                    dimension=key,
                    text=str(raw.get("text", "")),
                ),
            )
    return tuple(result)


def evidence_prompt(dimensions: Sequence[DiscoveryDimensionRead]) -> str:
    if not dimensions:
        return "현재 추가 발견 작업이 필요하지 않습니다."
    labels = ", ".join(dimension.label for dimension in dimensions)
    return (
        f"다음 항목을 실제 최근 사례 기준으로 보완하세요: {labels}. "
        "'시스템/도구:', '입력:', '출력:', '규칙/판단 기준:', '예외/복구:', "
        "'승인/권한:', '성과지표:', '비범위:', '근거:' 형식의 줄을 사용하세요."
    )


def work_model_gap_reasons(work_model: WorkModelRead | None) -> tuple[str, ...]:
    if work_model is None:
        return tuple(f"Missing {key.lower()} evidence" for key, *_rest in DIMENSIONS)
    payload = work_model.payload
    gaps: list[str] = []
    systems = object_items(payload.get("systems"))
    if not any(
        item.get("access_method") != "UNKNOWN" and item.get("stability") != "UNKNOWN"
        for item in systems
    ):
        gaps.append("System access method and stability")
    artifacts = object_items(payload.get("artifacts"))
    unstructured_formats = {"", "TEXT", "UNKNOWN"}
    if not any(
        str(item.get("format", "")).upper() not in unstructured_formats for item in artifacts
    ):
        gaps.append("Structured input and output artifacts")
    if not object_items(payload.get("rules")):
        gaps.append("Decision rules")
    if not object_items(payload.get("exceptions")):
        gaps.append("Exception cases and recovery")
    constraints = object_items(payload.get("constraints"))
    if not any(item.get("category") == "ORGANIZATIONAL" for item in constraints):
        gaps.append("Human approval and authority boundary")
    if not object_items(payload.get("metrics")):
        gaps.append("Success metric, frequency, volume, and rework")
    non_goals = string_items(payload.get("non_goals"))
    safety_defaults = {"실제 LLM 호출", "STT 처리", "외부 자동화 실행", "G1 명세 생성"}
    if not set(non_goals).difference(safety_defaults):
        gaps.append("User-confirmed non-goals and scope")
    evidence_summary = payload.get("evidence_summary")
    confirmed_rate = (
        evidence_summary.get("confirmed_claim_rate", 0)
        if isinstance(evidence_summary, dict)
        else 0
    )
    if not isinstance(confirmed_rate, int | float) or confirmed_rate < 0.75:
        gaps.append("Confirmed evidence coverage and source refs")
    return tuple(gaps)


def object_items(value: JsonValue | None) -> tuple[Mapping[str, JsonValue], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def string_items(value: JsonValue | None) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))
