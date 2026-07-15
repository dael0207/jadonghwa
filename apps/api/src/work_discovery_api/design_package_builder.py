from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from work_discovery_api.design_package_common import (
    bool_value,
    evidence_refs_for,
    list_with_default,
    string_value,
)
from work_discovery_api.design_package_plan import (
    acceptance_tests_for,
    backlog_for,
    open_questions_from,
    risks_from,
)
from work_discovery_api.design_package_sections import (
    data_contract_from,
    non_goals_from,
    scope_for,
    system_assumptions_from,
    target_users_from,
    user_flow_from,
)
from work_discovery_api.models import (
    JsonObject,
    OpportunityRead,
    ReadinessRead,
    WorkModelRead,
    utc_now,
)
from work_discovery_api.work_model_evidence import object_value, string_tuple


@dataclass(frozen=True, slots=True)
class DesignPackageBuildInput:
    opportunity: OpportunityRead
    work_model: WorkModelRead
    readiness: ReadinessRead


@dataclass(frozen=True, slots=True)
class DesignPackageBlockedError(Exception):
    opportunity_id: str
    readiness_result: str

    def __str__(self) -> str:
        return (
            f"opportunity {self.opportunity_id} cannot create a design package "
            f"from readiness {self.readiness_result}"
        )


class DeterministicDesignPackageBuilder:
    def build(self, source: DesignPackageBuildInput) -> JsonObject:
        package_type = package_type_for(source)
        opportunity_payload = source.opportunity.payload
        work_model_payload = source.work_model.payload
        recommendation = object_value(opportunity_payload.get("recommendation"))
        human_role = object_value(opportunity_payload.get("human_role"))
        evidence_refs = evidence_refs_for(opportunity_payload, work_model_payload)
        return {
            "package_id": stable_package_id(source, package_type),
            "project_id": source.opportunity.project_id,
            "opportunity_id": source.opportunity.id,
            "source_work_model_id": string_value(
                opportunity_payload.get("work_model_id"),
                f"wm-{source.opportunity.project_id}",
            ),
            "source_work_model_version": source.opportunity.work_model_version,
            "readiness_result": source.readiness.result,
            "package_type": package_type,
            "problem": {
                "statement": string_value(
                    opportunity_payload.get("problem_statement"),
                    "Discovered work requires a design package before implementation.",
                ),
                "evidence_refs": evidence_refs[:5],
            },
            "target_users": target_users_from(work_model_payload),
            "scope": scope_for(package_type, recommendation, opportunity_payload),
            "non_goals": non_goals_from(opportunity_payload),
            "user_flow": user_flow_from(work_model_payload, evidence_refs),
            "data_contract": data_contract_from(work_model_payload),
            "system_assumptions": system_assumptions_from(work_model_payload, package_type),
            "human_oversight": {
                "retained_responsibilities": list_with_default(
                    human_role.get("retained_responsibilities"),
                    "Human owner remains accountable for final decisions.",
                ),
                "approval_points": list_with_default(
                    human_role.get("approval_points"),
                    "Human approval is required before pilot or external execution.",
                ),
                "exception_handling": list(string_tuple(human_role.get("exception_handling"))),
                "override_available": bool_value(
                    human_role.get("override_available"),
                    fallback=True,
                ),
            },
            "risks_and_controls": risks_from(opportunity_payload),
            "acceptance_tests": acceptance_tests_for(package_type),
            "implementation_backlog": backlog_for(package_type, opportunity_payload),
            "open_questions": open_questions_from(source.opportunity.payload, source.readiness),
            "evidence_refs": evidence_refs,
            "created_at": utc_now().isoformat(),
        }


def package_type_for(source: DesignPackageBuildInput) -> str:
    if not source.opportunity.schema_valid:
        raise DesignPackageBlockedError(
            opportunity_id=source.opportunity.id,
            readiness_result="INVALID_OPPORTUNITY",
        )
    if source.readiness.result == "READY_FOR_DESIGN":
        return "FULL_G1"
    if source.readiness.result == "ENABLE_FIRST":
        return "ENABLEMENT_PREP"
    raise DesignPackageBlockedError(
        opportunity_id=source.opportunity.id,
        readiness_result=source.readiness.result,
    )


def stable_package_id(source: DesignPackageBuildInput, package_type: str) -> str:
    seed = f"{source.opportunity.id}:{source.opportunity.work_model_version}:{package_type}"
    return f"dp-{uuid5(NAMESPACE_URL, seed)}"
