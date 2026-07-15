from __future__ import annotations

from work_discovery_api.design_package_common import (
    list_with_default,
    string_value,
    unique_strings,
)
from work_discovery_api.models import JsonObject
from work_discovery_api.work_model_evidence import object_list, string_tuple


def target_users_from(work_model_payload: JsonObject) -> list[JsonObject]:
    users: list[JsonObject] = []
    for participant in object_list(work_model_payload.get("participants"))[:4]:
        role = string_value(participant.get("role"), string_value(participant.get("name"), "User"))
        users.append(
            {
                "role": role,
                "responsibilities": list_with_default(
                    participant.get("responsibilities"),
                    "Review and approve discovered workflow outputs.",
                ),
            },
        )
    return users or [
        {
            "role": "Workflow owner",
            "responsibilities": ["Review package scope and approve next design step."],
        },
    ]


def scope_for(
    package_type: str,
    recommendation: JsonObject,
    opportunity_payload: JsonObject,
) -> list[str]:
    scope = list_with_default(
        recommendation.get("scope"),
        "Review the discovered workflow package.",
    )
    mvp_scope = list(string_tuple(opportunity_payload.get("mvp_scope")))
    if package_type == "ENABLEMENT_PREP":
        return unique_strings(
            ["Resolve readiness blockers before full G1 design.", *scope, *mvp_scope],
        )
    return unique_strings([*scope, *mvp_scope, "Prepare a full G1 design handoff draft."])


def non_goals_from(opportunity_payload: JsonObject) -> list[str]:
    return unique_strings(
        [
            *string_tuple(opportunity_payload.get("non_goals")),
            "Actual application code generation",
            "External system execution",
            "Credential collection",
            "STT or voice recording",
            "Real LLM calls",
        ],
    )


def user_flow_from(work_model_payload: JsonObject, evidence_refs: list[str]) -> list[JsonObject]:
    steps: list[JsonObject] = []
    for process in object_list(work_model_payload.get("processes")):
        steps.extend(object_list(process.get("steps")))
    flow = [
        user_flow_step_from(step, index, evidence_refs)
        for index, step in enumerate(steps[:6], 1)
    ]
    return flow or [
        {
            "step_id": "flow-review-package",
            "actor": "Workflow owner",
            "action": "Review design package scope and blockers",
            "output": "Approval or follow-up decision",
            "evidence_refs": evidence_refs[:3],
        },
    ]


def user_flow_step_from(step: JsonObject, index: int, evidence_refs: list[str]) -> JsonObject:
    return {
        "step_id": string_value(step.get("id"), f"flow-step-{index}"),
        "actor": string_value(step.get("actor"), "Workflow owner"),
        "action": string_value(step.get("action"), f"Review workflow step {index}"),
        "output": string_value(step.get("output"), "Reviewed work output"),
        "evidence_refs": list(string_tuple(step.get("source_refs"))) or evidence_refs[:3],
    }


def data_contract_from(work_model_payload: JsonObject) -> JsonObject:
    inputs: list[JsonObject] = []
    outputs: list[JsonObject] = []
    for artifact in object_list(work_model_payload.get("artifacts"))[:8]:
        field = data_field_from(artifact)
        direction = string_value(artifact.get("direction"), "INPUT").upper()
        if direction in {"OUTPUT", "OUT"}:
            outputs.append(field)
        elif direction in {"INPUT_OUTPUT", "INOUT"}:
            inputs.append(field)
            outputs.append(field)
        else:
            inputs.append(field)
    return {
        "inputs": inputs or [fallback_data_field("Captured interview evidence")],
        "outputs": outputs or [fallback_data_field("Design package review result")],
        "assumptions": [
            "M5 stores design data as JSON and does not execute external workflows.",
            "Source system access is deferred to a later approved implementation phase.",
        ],
    }


def data_field_from(artifact: JsonObject) -> JsonObject:
    return {
        "name": string_value(artifact.get("name"), string_value(artifact.get("id"), "Artifact")),
        "kind": "ARTIFACT",
        "format": string_value(artifact.get("format"), "UNKNOWN"),
        "source_refs": list(string_tuple(artifact.get("source_refs"))) or ["source-work-model"],
    }


def fallback_data_field(name: str) -> JsonObject:
    return {
        "name": name,
        "kind": "UNKNOWN",
        "format": "UNKNOWN",
        "source_refs": ["source-work-model"],
    }


def system_assumptions_from(work_model_payload: JsonObject, package_type: str) -> list[str]:
    assumptions = [
        "No external business system is executed by the M5 design package.",
        "No credentials are collected or stored by M5.",
    ]
    if package_type == "ENABLEMENT_PREP":
        assumptions.append("Readiness blockers must be resolved before full G1 design.")
    for system_item in object_list(work_model_payload.get("systems"))[:5]:
        name = string_value(system_item.get("name"), "System")
        access = string_value(system_item.get("access_method"), "unknown access")
        stability = string_value(system_item.get("stability"), "unknown stability")
        assumptions.append(f"{name} access is {access}; stability is {stability}.")
    return unique_strings(assumptions)
