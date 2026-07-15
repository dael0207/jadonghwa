from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from work_discovery_api.design_package_common import list_with_default, string_value, unique_strings
from work_discovery_api.models import DesignPackageRead, JsonObject, JsonValue, utc_now
from work_discovery_api.work_model_evidence import object_list, object_value, string_tuple


@dataclass(frozen=True, slots=True)
class BlueprintBuildInput:
    package: DesignPackageRead


@dataclass(frozen=True, slots=True)
class BlueprintBlockedError(Exception):
    package_id: str
    readiness_result: str
    package_type: str

    def __str__(self) -> str:
        return (
            f"design package {self.package_id} cannot create a blueprint "
            f"from readiness {self.readiness_result} and type {self.package_type}"
        )


class DeterministicBlueprintBuilder:
    def build(self, source: BlueprintBuildInput) -> JsonObject:
        payload = source.package.payload
        package_type = string_value(payload.get("package_type"), "UNKNOWN")
        readiness_result = string_value(payload.get("readiness_result"), "BLOCKED")
        mode = blueprint_mode(source.package, readiness_result, package_type)
        evidence_refs = list(string_tuple(payload.get("evidence_refs"))) or [
            "source-design-package",
        ]
        non_goals = list_with_default(payload.get("non_goals"), "No external execution")
        quality_gate = quality_gate_for(mode, evidence_refs, payload, non_goals)
        return {
            "blueprint_id": stable_blueprint_id(source.package, mode.blueprint_type),
            "project_id": source.package.project_id,
            "design_package_id": source.package.id,
            "source_package_type": package_type,
            "readiness_result": readiness_result,
            "blueprint_type": mode.blueprint_type,
            "export_ready": mode.export_ready and bool(quality_gate["passed"]),
            "executive_brief": executive_brief(payload, evidence_refs, mode),
            "as_is_to_be": as_is_to_be(payload, evidence_refs, mode),
            "prd": prd_from(payload, non_goals, mode),
            "ux_spec": ux_spec_from(payload, mode),
            "data_spec": data_spec_from(payload),
            "api_spec": api_spec_from(mode),
            "acceptance_tests": object_list_or_default(
                payload.get("acceptance_tests"),
                fallback_acceptance_test(),
            ),
            "implementation_backlog": object_list_or_default(
                payload.get("implementation_backlog"),
                fallback_backlog(mode),
            ),
            "risks_and_controls": object_list_or_default(
                payload.get("risks_and_controls"),
                fallback_risk(),
            ),
            "quality_gate": quality_gate,
            "open_questions": list(string_tuple(payload.get("open_questions"))),
            "traceability": {
                "source_work_model_id": string_value(
                    payload.get("source_work_model_id"),
                    f"wm-{source.package.project_id}",
                ),
                "source_work_model_version": source.package.work_model_version,
                "opportunity_id": source.package.opportunity_id,
                "design_package_id": source.package.id,
                "evidence_refs": evidence_refs,
            },
            "non_goals": non_goals,
            "created_at": utc_now().isoformat(),
        }


@dataclass(frozen=True, slots=True)
class BlueprintMode:
    blueprint_type: str
    export_ready: bool
    limitation: str


def blueprint_mode(
    package: DesignPackageRead,
    readiness_result: str,
    package_type: str,
) -> BlueprintMode:
    if not package.schema_valid:
        raise BlueprintBlockedError(package.id, "INVALID_PACKAGE", package_type)
    match (readiness_result, package_type):
        case ("READY_FOR_DESIGN", "FULL_G1"):
            return BlueprintMode(
                blueprint_type="FULL_G1_BLUEPRINT",
                export_ready=True,
                limitation="Ready for JSON and Markdown export preview.",
            )
        case ("ENABLE_FIRST", "ENABLEMENT_PREP"):
            return BlueprintMode(
                blueprint_type="ENABLEMENT_FOLLOWUP",
                export_ready=False,
                limitation="Limited to enablement follow-up before full G1 export.",
            )
        case _:
            raise BlueprintBlockedError(package.id, readiness_result, package_type)


def stable_blueprint_id(package: DesignPackageRead, blueprint_type: str) -> str:
    seed = f"{package.id}:{package.work_model_version}:{blueprint_type}"
    return f"bp-{uuid5(NAMESPACE_URL, seed)}"


def executive_brief(
    payload: JsonObject,
    evidence_refs: list[str],
    mode: BlueprintMode,
) -> JsonObject:
    problem = object_value(payload.get("problem"))
    return {
        "summary": string_value(
            problem.get("statement"),
            "Discovered work requires a G1 solution blueprint.",
        ),
        "bullets": unique_strings(
            [
                mode.limitation,
                "Human review remains required before any pilot or implementation.",
                "No credentials, external execution, or production deployment are included.",
            ],
        ),
        "evidence_refs": evidence_refs[:6],
    }


def as_is_to_be(payload: JsonObject, evidence_refs: list[str], mode: BlueprintMode) -> JsonObject:
    flow = object_list(payload.get("user_flow"))
    as_is = [
        string_value(step.get("action"), "Review current workflow step")
        for step in flow[:5]
    ] or ["Current workflow is represented by the source design package."]
    to_be = [
        "Review a structured G1 blueprint before any implementation work.",
        "Keep approval and exception handling with the workflow owner.",
    ]
    if mode.blueprint_type == "ENABLEMENT_FOLLOWUP":
        to_be.append("Resolve blockers before creating an export-ready full G1 blueprint.")
    return {
        "as_is": as_is,
        "to_be": to_be,
        "retained_human_steps": list_with_default(
            object_value(payload.get("human_oversight")).get("approval_points"),
            "Human approval before implementation.",
        ),
        "evidence_refs": evidence_refs[:6],
    }


def prd_from(payload: JsonObject, non_goals: list[str], mode: BlueprintMode) -> JsonObject:
    target_users = [
        string_value(user.get("role"), "Workflow owner")
        for user in object_list(payload.get("target_users"))
    ] or ["Workflow owner"]
    return {
        "purpose": string_value(
            object_value(payload.get("problem")).get("statement"),
            "Prepare an implementation-ready G1 product and technical brief.",
        ),
        "users": target_users,
        "scope": list_with_default(payload.get("scope"), "Review the discovered workflow."),
        "non_goals": non_goals,
        "functional_requirements": [
            "Render the source workflow, evidence, risks, and acceptance tests for review.",
            "Require human approval before any later implementation or external action.",
            mode.limitation,
        ],
        "non_functional_requirements": [
            "Audit every generated, validated, and exported artifact.",
            "Preserve evidence traceability to the source work model and opportunity.",
            "Keep all outputs deterministic in M6.",
        ],
        "success_metrics": [
            "Blueprint passes blueprint-v1.schema.json.",
            "Every acceptance test is readable as Given/When/Then.",
            "No non-goal is contradicted by backlog or API draft content.",
        ],
    }


def ux_spec_from(payload: JsonObject, mode: BlueprintMode) -> JsonObject:
    return {
        "primary_flow": [
            "Open the workbench project.",
            "Generate or inspect the latest design package.",
            "Create a blueprint preview.",
            "Validate and export JSON or Markdown preview.",
        ],
        "screens": ["Workbench blueprint panel", "JSON preview", "Markdown export preview"],
        "states": [
            "No package",
            "Enablement follow-up",
            "Export-ready full G1 blueprint",
            "Schema validation error",
        ],
        "accessibility": [
            "Use structured headings and native buttons.",
            "Keep Korean and English technical labels from clipping on narrow screens.",
            string_value(payload.get("package_type"), mode.blueprint_type),
        ],
    }


def data_spec_from(payload: JsonObject) -> JsonObject:
    contract = object_value(payload.get("data_contract"))
    inputs = object_list_or_default(
        contract.get("inputs"),
        fallback_data_field("Source evidence"),
    )
    outputs = object_list_or_default(
        contract.get("outputs"),
        fallback_data_field("Blueprint preview"),
    )
    return {
        "inputs": inputs,
        "outputs": outputs,
        "entities": ["Project", "DesignPackage", "Blueprint", "AuditEvent"],
        "retention": (
            "M6 stores append-only JSON artifacts; deletion remains a later runbook action."
        ),
        "audit_fields": ["subject_id", "action", "metadata", "created_at"],
    }


def api_spec_from(mode: BlueprintMode) -> JsonObject:
    return {
        "style": "REST_DRAFT",
        "endpoints": [
            {
                "method": "POST",
                "path": "/v1/design-packages/{package_id}/blueprint",
                "purpose": "Create an append-only blueprint preview.",
            },
            {
                "method": "GET",
                "path": "/v1/blueprints/{blueprint_id}/export/markdown",
                "purpose": "Return a Markdown export preview without executing external systems.",
            },
        ],
        "auth": "Local MVP assumes trusted local operator; real auth is out of M6 scope.",
        "errors": ["404 for missing source", "409 for invalid source or schema gate failure"],
        "idempotency": mode.limitation,
    }


def quality_gate_for(
    mode: BlueprintMode,
    evidence_refs: list[str],
    payload: JsonObject,
    non_goals: list[str],
) -> JsonObject:
    acceptance_tests = object_list(payload.get("acceptance_tests"))
    required_non_goals = (
        "External system execution",
        "Credential collection",
        "Actual application code generation",
    )
    criteria = [
        criterion("evidence-traceability", len(evidence_refs) > 0, "Evidence refs are present."),
        criterion(
            "acceptance-tests",
            len(acceptance_tests) > 0,
            "Acceptance tests are present.",
        ),
        criterion(
            "non-goal-enforcement",
            all(item in non_goals for item in required_non_goals),
            "Execution, credential, and code-generation non-goals are explicit.",
        ),
        criterion(
            "full-g1-export",
            mode.blueprint_type == "FULL_G1_BLUEPRINT",
            mode.limitation,
        ),
    ]
    blocking = [item["detail"] for item in criteria if item["passed"] is False]
    return {"passed": len(blocking) == 0, "criteria": criteria, "blocking_items": blocking}


def criterion(key: str, passed: bool, detail: str) -> JsonObject:
    return {"key": key, "passed": passed, "detail": detail}


def object_list_or_default(value: JsonValue | None, fallback: JsonObject) -> list[JsonObject]:
    items = list(object_list(value))
    return items or [fallback]


def fallback_acceptance_test() -> JsonObject:
    return {
        "id": "at-blueprint-schema",
        "scenario": "Blueprint schema validation",
        "given": "A generated blueprint",
        "when": "The API validates the payload",
        "then": "The payload passes blueprint-v1.schema.json",
    }


def fallback_backlog(mode: BlueprintMode) -> JsonObject:
    return {
        "id": "backlog-review-blueprint",
        "title": "Review blueprint gate",
        "description": mode.limitation,
        "priority": "MUST",
    }


def fallback_risk() -> JsonObject:
    return {
        "risk": "Blueprint may be used as if it were executable code.",
        "control": "Label M6 output as a design preview only.",
        "level": 2,
    }


def fallback_data_field(name: str) -> JsonObject:
    return {
        "name": name,
        "kind": "UNKNOWN",
        "format": "JSON",
        "source_refs": ["source-design-package"],
    }
