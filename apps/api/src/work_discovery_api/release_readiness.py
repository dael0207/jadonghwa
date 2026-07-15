from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from work_discovery_api.domain import AuditAction
from work_discovery_api.models import (
    AuditEventRead,
    BlueprintRead,
    DesignPackageRead,
    EvaluationRunRead,
    JsonObject,
    ReleaseReadinessRead,
    utc_now,
)
from work_discovery_api.work_model_evidence import string_tuple


@dataclass(frozen=True, slots=True)
class ReleaseReadinessInput:
    project_id: str
    design_packages: tuple[DesignPackageRead, ...]
    blueprints: tuple[BlueprintRead, ...]
    evaluation_runs: tuple[EvaluationRunRead, ...]
    previous_reports: tuple[ReleaseReadinessRead, ...]
    audit_events: tuple[AuditEventRead, ...]


class DeterministicReleaseReadinessEvaluator:
    def evaluate(self, source: ReleaseReadinessInput) -> JsonObject:
        checklist = checklist_items(source)
        blockers = [str(item["details"]) for item in checklist if item["status"] == "BLOCKED"]
        warns = [str(item["details"]) for item in checklist if item["status"] == "WARN"]
        return {
            "report_id": stable_report_id(source),
            "project_id": source.project_id,
            "readiness_status": readiness_status(blockers, warns),
            "checklist": checklist,
            "blocking_items": blockers,
            "source_blueprint_ids": [item.id for item in source.blueprints],
            "source_design_package_ids": [item.id for item in source.design_packages],
            "metrics_definition": metrics_definition(),
            "runbooks": runbooks(),
            "monitoring_placeholder": {
                "status": "PLACEHOLDER_ONLY",
                "events": [
                    "artifact_created",
                    "artifact_validated",
                    "artifact_exported",
                    "consent_changed",
                ],
            },
            "created_at": utc_now().isoformat(),
        }


def checklist_items(source: ReleaseReadinessInput) -> list[JsonObject]:
    latest_blueprint = latest(source.blueprints)
    latest_package = latest(source.design_packages)
    latest_evaluation = latest(source.evaluation_runs)
    return [
        checklist(
            "consent-audit-deletion-readiness",
            "Consent, audit, and deletion readiness",
            has_audit(source.audit_events, AuditAction.CONSENT_GRANTED)
            and has_audit(source.audit_events, AuditAction.BLUEPRINT_CREATED),
            "Consent and artifact audit events exist; deletion remains runbook-managed.",
        ),
        checklist(
            "schema-validation-coverage",
            "Schema validation coverage",
            bool(
                latest_package
                and latest_package.schema_valid
                and latest_blueprint
                and latest_blueprint.schema_valid
                and latest_evaluation
                and latest_evaluation.schema_valid
            ),
            "Latest package, blueprint, and evaluation run are schema-valid.",
        ),
        checklist(
            "export-readiness",
            "Export readiness",
            bool(latest_blueprint and latest_blueprint.export_ready),
            "A FULL_G1 blueprint is export-ready.",
        ),
        checklist(
            "safety-non-goal-enforcement",
            "Safety non-goal enforcement",
            safety_enforced(source),
            (
                "LLM/STT, credential collection, external execution, and code generation "
                "remain excluded."
            ),
        ),
        checklist(
            "monitoring-placeholder",
            "Monitoring placeholder",
            passed=True,
            details="M8 defines audit event monitoring placeholders without production deployment.",
        ),
        checklist(
            "support-deletion-runbook",
            "Support and deletion runbook",
            passed=True,
            details="M8 provides support, deletion, and incident review runbook text.",
        ),
        checklist(
            "pilot-metrics-definition",
            "Pilot metrics definition",
            latest_evaluation is not None,
            "M7 evaluation run defines deterministic pilot metric placeholders.",
        ),
    ]


def checklist(key: str, label: str, passed: bool, details: str) -> JsonObject:
    return {
        "key": key,
        "label": label,
        "status": "PASS" if passed else "BLOCKED",
        "details": details,
    }


def safety_enforced(source: ReleaseReadinessInput) -> bool:
    texts: list[str] = []
    for package in source.design_packages:
        texts.extend(string_tuple(package.payload.get("non_goals")))
    for blueprint in source.blueprints:
        texts.extend(string_tuple(blueprint.payload.get("non_goals")))
    required = (
        "External system execution",
        "Credential collection",
        "Actual application code generation",
        "Real LLM calls",
        "STT or voice recording",
    )
    return all(item in texts for item in required)


def readiness_status(blockers: list[str], warns: list[str]) -> str:
    if blockers:
        return "NOT_READY"
    if warns:
        return "READY_WITH_BLOCKERS"
    return "READY"


def metrics_definition() -> JsonObject:
    return {
        "pilot_metrics": [
            "User-confirmed blueprint usefulness",
            "Developer blocking-question count",
            "Export review completion rate",
        ],
        "quality_metrics": [
            "Schema validation pass rate",
            "Evidence traceability coverage",
            "Acceptance test completeness",
        ],
        "safety_metrics": [
            "Non-goal violation count",
            "Credential collection attempts",
            "External execution attempts",
        ],
    }


def runbooks() -> JsonObject:
    return {
        "support": "Triage user-reported artifact issues through project audit events.",
        "deletion": "Delete project-scoped artifacts and confirm deletion through an audit event.",
        "incident_review": "Review safety or non-goal violations before enabling any later pilot.",
    }


def stable_report_id(source: ReleaseReadinessInput) -> str:
    seed = (
        f"{source.project_id}:{len(source.blueprints)}:"
        f"{len(source.evaluation_runs)}:{len(source.previous_reports)}"
    )
    return f"rel-{uuid5(NAMESPACE_URL, seed)}"


def has_audit(events: tuple[AuditEventRead, ...], action: AuditAction) -> bool:
    return any(event.action == action for event in events)


def latest[T](items: tuple[T, ...]) -> T | None:
    if not items:
        return None
    return items[-1]
