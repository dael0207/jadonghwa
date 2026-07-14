from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from work_discovery_api.models import JsonObject, JsonValue, WorkModelRead, utc_now


@dataclass(frozen=True, slots=True)
class OpportunityAnalysisInput:
    work_model: WorkModelRead


class DeterministicOpportunityAnalyzer:
    def draft(self, source: OpportunityAnalysisInput) -> JsonObject:
        payload = source.work_model.payload
        model_id = string_value(payload.get("model_id"), f"wm-{source.work_model.project_id}")
        process_id = first_process_id(payload)
        title = string_value(payload.get("title"), "발견된 업무")
        summary = string_value(payload.get("summary"), title)
        opportunity_id = f"opp-{uuid5(NAMESPACE_URL, model_id)}"
        created_at = utc_now().isoformat()
        return {
            "opportunity_id": opportunity_id,
            "project_id": source.work_model.project_id,
            "work_model_id": model_id,
            "target_refs": [process_id],
            "problem_statement": (
                f"{title} 업무는 M3 deterministic analyzer가 식별한 반복 업무 후보입니다. "
                f"근거 요약: {summary[:1200]}"
            ),
            "recommendation": {
                "solution_mode": "KNOWLEDGE_ASSIST",
                "title": "검증용 업무 정리 보조 초안",
                "rationale": (
                    "M3는 실제 자동화 후보 분석이 아니라 schema와 경계 검증을 위한 "
                    "deterministic mock analyzer를 사용합니다."
                ),
                "scope": ["인터뷰 답변 요약", "playback 확인 후 개선 후보 초안 표시"],
                "autonomy_level": 1,
            },
            "alternative_options": [
                {
                    "solution_mode": "SIMPLIFY_STANDARDIZE",
                    "title": "업무 흐름 표준화",
                    "rationale": "자동화 전에 시작 조건, 결과물, 예외를 더 명확히 표준화합니다.",
                    "scope": ["업무 체크리스트", "입력·출력 명세 정리"],
                    "autonomy_level": 0,
                },
            ],
            "scores": {
                "value": 45,
                "feasibility": 55,
                "risk": 2,
                "evidence_confidence": 0.55,
                "oversight": 3,
                "portfolio_class": "ENABLE_FIRST",
                "score_explanation": [
                    "M3는 답변 기반 mock 점수만 산출합니다.",
                    "실제 ROI와 위험 평가는 M4 이후 별도 analyzer가 필요합니다.",
                ],
            },
            "gate": {
                "result": "DISCOVERY_NEEDED",
                "blocked_reasons": ["실제 자동화 설계 전 추가 증거와 사용자 확인이 필요합니다."],
            },
            "human_role": {
                "retained_responsibilities": ["업무 사실 확인", "예외와 책임 경계 승인"],
                "approval_points": ["Work Model playback", "자동화 후보 채택 전"],
                "exception_handling": ["모호한 입력과 예외 사례는 사람이 판단합니다."],
                "override_available": True,
            },
            "benefit_estimate": {
                "basis": "UNKNOWN",
                "annual_manual_hours": {"min": 0, "max": 0, "typical": 0},
                "annual_rework_hours": {"min": 0, "max": 0, "typical": 0},
                "recoverable_hours": {"min": 0, "max": 0, "typical": 0},
                "annual_total_benefit": {"currency": "KRW", "min": 0, "max": 0, "typical": 0},
                "build_cost": {"currency": "KRW", "min": 0, "max": 0, "typical": 0},
                "annual_run_cost": {"currency": "KRW", "min": 0, "max": 0, "typical": 0},
                "assumptions": ["M3에서는 수치 ROI를 추정하지 않습니다."],
            },
            "risks": [
                {
                    "category": "OPERATIONS",
                    "level": 2,
                    "description": (
                        "충분히 검증되지 않은 업무 이해를 자동화 설계로 오인할 수 있습니다."
                    ),
                    "control": "사용자 playback 승인과 추가 증거 수집 후 다음 단계로 진행합니다.",
                    "residual_level": 1,
                },
            ],
            "prerequisites": ["schema-valid Work Model", "사용자 playback 확인 또는 추가 증거"],
            "evidence_refs": [process_id],
            "open_questions": [
                "빈도, 처리 시간, 예외, 권한 경계를 실제 사례로 더 확인해야 합니다.",
            ],
            "validation_experiment": {
                "hypothesis": "사용자가 확인한 Work Model은 후보 분석의 충분한 입력이 된다.",
                "method": "한 업무에 대해 추가 증거를 수집하고 playback 재빌드 결과를 비교합니다.",
                "sample": "M3 로컬 인터뷰 한 건",
                "success_criteria": ["재빌드 후 사용자가 누락이 줄었다고 확인합니다."],
            },
            "mvp_scope": ["업무 이해 결과에서 1개 mock opportunity draft 생성"],
            "non_goals": ["실제 외부 시스템 실행", "실제 G1 명세 생성", "LLM 기반 후보 분석"],
            "created_at": created_at,
        }


def first_process_id(payload: JsonObject) -> str:
    processes = payload.get("processes")
    if isinstance(processes, list):
        for item in processes:
            if isinstance(item, dict):
                candidate = item.get("id")
                if isinstance(candidate, str) and candidate:
                    return candidate
    return "process-discovered-work"


def string_value(value: JsonValue | None, fallback: str) -> str:
    if isinstance(value, str) and value:
        return value
    return fallback
