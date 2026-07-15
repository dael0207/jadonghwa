from __future__ import annotations

from work_discovery_api.design_package_common import (
    first_or_default,
    int_value,
    string_value,
    unique_strings,
)
from work_discovery_api.models import JsonObject, ReadinessRead
from work_discovery_api.work_model_evidence import object_list, string_tuple


def risks_from(opportunity_payload: JsonObject) -> list[JsonObject]:
    risks = [risk_control_from(risk) for risk in object_list(opportunity_payload.get("risks"))]
    return risks or [
        {
            "risk": "Design package may omit edge cases from the discovered work.",
            "control": "Require human review and follow-up evidence before implementation.",
            "level": 2,
        },
    ]


def risk_control_from(risk: JsonObject) -> JsonObject:
    return {
        "risk": string_value(risk.get("description"), "Unspecified workflow risk"),
        "control": string_value(risk.get("control"), "Keep human approval before execution."),
        "level": int_value(risk.get("level"), 2),
    }


def acceptance_tests_for(package_type: str) -> list[JsonObject]:
    tests: list[JsonObject] = [
        {
            "id": "at-design-package-schema",
            "scenario": "Schema-valid design package",
            "given": "A generated M5 design package",
            "when": "The API validates the payload",
            "then": "The payload passes design-package-v1.schema.json",
        },
        {
            "id": "at-no-external-execution",
            "scenario": "No execution in M5",
            "given": "A user reviews the generated package",
            "when": "They inspect scope, non-goals, and backlog",
            "then": "No item asks for credentials, code generation, or external execution",
        },
    ]
    if package_type == "FULL_G1":
        tests.append(
            {
                "id": "at-full-g1-handoff",
                "scenario": "Full G1 handoff readiness",
                "given": "An opportunity is READY_FOR_DESIGN",
                "when": "A package is generated",
                "then": "Scope, flow, data contract, controls, and backlog are present",
            },
        )
    return tests


def backlog_for(package_type: str, opportunity_payload: JsonObject) -> list[JsonObject]:
    questions = list(string_tuple(opportunity_payload.get("open_questions")))
    if package_type == "ENABLEMENT_PREP":
        return [
            {
                "id": "backlog-resolve-readiness-blockers",
                "title": "Resolve readiness blockers",
                "description": first_or_default(
                    questions,
                    "Collect follow-up evidence before full G1 design.",
                ),
                "priority": "MUST",
            },
            {
                "id": "backlog-confirm-human-boundaries",
                "title": "Confirm human oversight boundaries",
                "description": (
                    "Document approval, exception, and override rules before implementation design."
                ),
                "priority": "MUST",
            },
        ]
    return [
        {
            "id": "backlog-finalize-g1-scope",
            "title": "Finalize G1 scope",
            "description": (
                "Review problem, users, flow, data contract, risks, and acceptance tests."
            ),
            "priority": "MUST",
        },
        {
            "id": "backlog-prepare-implementation-plan",
            "title": "Prepare implementation plan",
            "description": (
                "Translate the approved package into a later build plan without executing it in M5."
            ),
            "priority": "SHOULD",
        },
    ]


def open_questions_from(opportunity_payload: JsonObject, readiness: ReadinessRead) -> list[str]:
    return unique_strings(
        [
            *string_tuple(opportunity_payload.get("open_questions")),
            *readiness.required_followups,
        ],
    )
