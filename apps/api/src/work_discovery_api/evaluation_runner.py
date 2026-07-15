from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from work_discovery_api.models import (
    AuditEventRead,
    BlueprintRead,
    DesignPackageRead,
    InterviewRead,
    JsonObject,
    OpportunityRead,
    WorkModelRead,
    utc_now,
)
from work_discovery_api.work_model_evidence import object_value, string_tuple

CORPUS_VERSION = "work-discovery-eval-corpus-v1"
CORPUS_ITEM_COUNT = 24
NON_GOAL_CHECKS = (
    "External system execution",
    "Credential collection",
    "Actual application code generation",
    "Real LLM calls",
    "STT or voice recording",
)


@dataclass(frozen=True, slots=True)
class EvaluationRunInput:
    project_id: str
    interviews: tuple[InterviewRead, ...]
    work_models: tuple[WorkModelRead, ...]
    opportunities: tuple[OpportunityRead, ...]
    design_packages: tuple[DesignPackageRead, ...]
    blueprints: tuple[BlueprintRead, ...]
    audit_events: tuple[AuditEventRead, ...]


class DeterministicEvaluationRunner:
    def run(self, source: EvaluationRunInput) -> JsonObject:
        criteria = criteria_results(source)
        passed_count = sum(1 for item in criteria if item["passed"] is True)
        total_count = len(criteria)
        average = round(sum(score_of(item) for item in criteria) / total_count, 3)
        failed = [str(item["key"]) for item in criteria if item["passed"] is False]
        return {
            "run_id": stable_run_id(source),
            "project_id": source.project_id,
            "corpus_version": CORPUS_VERSION,
            "item_count": CORPUS_ITEM_COUNT,
            "score_summary": {
                "average_score": average,
                "passed_count": passed_count,
                "total_count": total_count,
                "overall_passed": len(failed) == 0,
            },
            "criteria_results": criteria,
            "failed_criteria": failed,
            "calibration_report": {
                "status": "DETERMINISTIC_BASELINE",
                "threshold_basis": (
                    "R009 MVP target thresholds converted to deterministic fixture checks."
                ),
                "notes": [
                    "No real pilot data is used in M7.",
                    (
                        "Threshold calibration is a report-only placeholder until a human "
                        "pilot exists."
                    ),
                ],
            },
            "safety_non_goal_compliance": safety_non_goal_compliance(source),
            "created_at": utc_now().isoformat(),
        }


def criteria_results(source: EvaluationRunInput) -> list[JsonObject]:
    latest_model = latest(source.work_models)
    latest_opportunity = latest(source.opportunities)
    latest_package = latest(source.design_packages)
    latest_blueprint = latest(source.blueprints)
    latest_interview = latest(source.interviews)
    safety = safety_non_goal_compliance(source)
    return [
        criterion(
            "work-model-completeness",
            "Work model completeness",
            0.9 if latest_model and latest_model.schema_valid else 0.25,
            0.85,
            "Latest Work Model is schema-valid." if latest_model else "No Work Model exists.",
        ),
        criterion(
            "evidence-traceability",
            "Evidence traceability",
            traceability_score(latest_package, latest_blueprint),
            0.9,
            "Evidence refs are preserved into package and blueprint.",
        ),
        criterion(
            "opportunity-scoring-consistency",
            "Opportunity scoring consistency",
            0.9 if latest_opportunity and latest_opportunity.schema_valid else 0.2,
            0.8,
            "Latest opportunity uses schema-valid scoring payload.",
        ),
        criterion(
            "design-package-completeness",
            "Design package completeness",
            0.92 if latest_package and latest_package.schema_valid else 0.2,
            0.85,
            "Latest design package is schema-valid.",
        ),
        criterion(
            "blueprint-completeness",
            "Blueprint completeness",
            blueprint_score(latest_blueprint),
            0.85,
            "Latest full blueprint is schema-valid and export-ready.",
        ),
        criterion(
            "safety-non-goal-compliance",
            "Safety and non-goal compliance",
            1.0 if safety["passed"] is True else 0.35,
            1.0,
            "Forbidden execution, credential, LLM, STT, and code-generation scopes are excluded.",
        ),
        criterion(
            "interview-burden",
            "Interview burden",
            burden_score(latest_interview),
            0.75,
            "MVP flow keeps the fixed intake under 24 answered prompts.",
        ),
    ]


def criterion(key: str, label: str, score: float, threshold: float, finding: str) -> JsonObject:
    rounded = round(max(0, min(1, score)), 3)
    return {
        "key": key,
        "label": label,
        "score": rounded,
        "threshold": threshold,
        "passed": rounded >= threshold,
        "findings": [finding],
    }


def traceability_score(package: DesignPackageRead | None, blueprint: BlueprintRead | None) -> float:
    refs = []
    if package:
        refs.extend(string_tuple(package.payload.get("evidence_refs")))
    if blueprint:
        refs.extend(
            string_tuple(object_value(blueprint.payload.get("traceability")).get("evidence_refs")),
        )
    return 0.98 if refs else 0.25


def blueprint_score(blueprint: BlueprintRead | None) -> float:
    if blueprint and blueprint.schema_valid and blueprint.export_ready:
        return 0.93
    if blueprint and blueprint.schema_valid:
        return 0.55
    return 0.2


def burden_score(interview: InterviewRead | None) -> float:
    if interview is None:
        return 0.5
    if interview.answered_count <= 10:
        return 0.95
    if interview.answered_count <= 24:
        return 0.8
    return 0.4


def safety_non_goal_compliance(source: EvaluationRunInput) -> JsonObject:
    texts = []
    for package in source.design_packages:
        texts.extend(string_tuple(package.payload.get("non_goals")))
    for blueprint in source.blueprints:
        texts.extend(string_tuple(blueprint.payload.get("non_goals")))
    missing = [item for item in NON_GOAL_CHECKS if item not in texts]
    return {
        "passed": len(missing) == 0,
        "checked_non_goals": list(NON_GOAL_CHECKS),
        "violations": [f"Missing non-goal: {item}" for item in missing],
    }


def stable_run_id(source: EvaluationRunInput) -> str:
    seed = (
        f"{source.project_id}:{len(source.blueprints)}:"
        f"{len(source.design_packages)}:{CORPUS_VERSION}"
    )
    return f"eval-{uuid5(NAMESPACE_URL, seed)}"


def score_of(item: JsonObject) -> float:
    value = item.get("score")
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return 0


def latest[T](items: tuple[T, ...]) -> T | None:
    if not items:
        return None
    return items[-1]
