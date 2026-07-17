from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from work_discovery_api.domain import ImplementationReadinessStatus
from work_discovery_api.models import (
    BlueprintRead,
    DesignPackageRead,
    EvidenceFileRead,
    ImplementationRequirementsRead,
    JsonObject,
    JsonValue,
    OpportunityRead,
    ProjectRead,
    WorkModelRead,
    utc_now,
)

REQUIRED_REQUIREMENT_KEYS: tuple[str, ...] = (
    "target_runtime",
    "framework",
    "package_manager",
    "execution_interface",
    "workflow",
    "input_schema",
    "output_schema",
    "field_mappings",
    "calculation_rules",
    "decision_rules",
    "validation_rules",
    "exceptions",
    "reliability",
    "human_oversight",
    "integrations",
    "module_responsibilities",
    "operations",
    "acceptance_cases",
)
ACCEPTANCE_KINDS = frozenset({"NORMAL", "ERROR", "EXCEPTION", "APPROVAL_REQUIRED"})
UNRESOLVED_MARKERS = ("UNKNOWN", "UNRESOLVED", "REPLACED_BY_API")


@dataclass(frozen=True, slots=True)
class ImplementationPackageInput:
    package_id: str
    project: ProjectRead
    work_model: WorkModelRead
    opportunity: OpportunityRead
    design_package: DesignPackageRead
    blueprint: BlueprintRead
    requirements: ImplementationRequirementsRead | None
    evidence_files: tuple[EvidenceFileRead, ...]


@dataclass(frozen=True, slots=True)
class ImplementationPackageBuild:
    payload: JsonObject
    readiness_status: ImplementationReadinessStatus


class DeterministicImplementationPackageBuilder:
    def build(self, build_input: ImplementationPackageInput) -> ImplementationPackageBuild:
        requirements = (
            deepcopy(build_input.requirements.payload)
            if build_input.requirements is not None
            else {}
        )
        normalized = self._normalized_requirements(requirements, build_input.evidence_files)
        checks = self._checks(build_input, requirements, normalized)
        blockers = tuple(str(check["detail"]) for check in checks if check["passed"] is False)
        follow_ups = self._follow_up_questions(checks)
        core_keys = {
            "requirements-confirmed",
            "critical-fields",
            "workflow-dag",
            "workflow-io",
            "data-contract",
            "implementation-controls",
        }
        core_passed = all(
            bool(check["passed"]) for check in checks if str(check["key"]) in core_keys
        )
        all_passed = all(bool(check["passed"]) for check in checks)
        if all_passed:
            readiness_status = ImplementationReadinessStatus.CODEGEN_READY
        elif core_passed:
            readiness_status = ImplementationReadinessStatus.IMPLEMENTATION_READY
        else:
            readiness_status = ImplementationReadinessStatus.DESIGN_READY
        now = utc_now()
        readiness: JsonObject = {
            "package_id": build_input.package_id,
            "project_id": build_input.project.id,
            "status": readiness_status.value,
            "codegen_ready": readiness_status is ImplementationReadinessStatus.CODEGEN_READY,
            "blockers": list(blockers),
            "follow_up_questions": list(follow_ups),
            "checks": list(checks),
            "evaluated_at": now.isoformat(),
        }
        source_refs = self._source_evidence_refs(build_input)
        payload: JsonObject = {
            "package_id": build_input.package_id,
            "project_id": build_input.project.id,
            "source_work_model_id": (
                f"work-model:{build_input.work_model.project_id}:v{build_input.work_model.version}"
            ),
            "source_work_model_version": build_input.work_model.version,
            "source_opportunity_id": build_input.opportunity.id,
            "source_design_package_id": build_input.design_package.id,
            "source_blueprint_id": build_input.blueprint.id,
            "readiness_status": readiness_status.value,
            "target_runtime": normalized["target_runtime"],
            "framework": normalized["framework"],
            "package_manager": normalized["package_manager"],
            "execution_interface": normalized["execution_interface"],
            "workflow": normalized["workflow"],
            "integrations": normalized["integrations"],
            "data_contract": {
                "input_schema": normalized["input_schema"],
                "output_schema": normalized["output_schema"],
                "field_mappings": normalized["field_mappings"],
            },
            "rules": {
                "calculations": normalized["calculation_rules"],
                "decisions": normalized["decision_rules"],
                "validations": normalized["validation_rules"],
            },
            "exceptions": normalized["exceptions"],
            "reliability": normalized["reliability"],
            "human_oversight": normalized["human_oversight"],
            "module_responsibilities": normalized["module_responsibilities"],
            "operations": normalized["operations"],
            "acceptance_cases": normalized["acceptance_cases"],
            "evidence_refs": list(source_refs),
            "codegen_readiness": readiness,
            "created_at": now.isoformat(),
        }
        return ImplementationPackageBuild(payload=payload, readiness_status=readiness_status)

    def _checks(
        self,
        build_input: ImplementationPackageInput,
        requirements: JsonObject,
        normalized: JsonObject,
    ) -> tuple[JsonObject, ...]:
        requirements_confirmed = (
            build_input.requirements is not None and build_input.requirements.confirmed
        )
        missing = [key for key in REQUIRED_REQUIREMENT_KEYS if not requirements.get(key)]
        critical_values = dict(normalized)
        critical_values.pop("acceptance_cases", None)
        unknown = sorted(_find_markers(critical_values))
        workflow = _object(normalized.get("workflow"))
        workflow_ok = _workflow_is_acyclic(workflow)
        workflow_io_ok = _workflow_io_connected(workflow)
        data_contract_ok = (
            bool(_object(normalized.get("input_schema")))
            and bool(_object(normalized.get("output_schema")))
            and bool(_object_list(normalized.get("field_mappings")))
        )
        controls_ok = all(
            (
                _object_list(normalized.get("calculation_rules")),
                _object_list(normalized.get("decision_rules")),
                _object_list(normalized.get("validation_rules")),
                _object(normalized.get("reliability")),
                _object(normalized.get("human_oversight")),
                _object_list(normalized.get("integrations")),
                _object_list(normalized.get("module_responsibilities")),
                _object(normalized.get("operations")),
            ),
        )
        confirmed_inputs = tuple(
            file for file in build_input.evidence_files if file.confirmed and file.role == "INPUT"
        )
        confirmed_outputs = tuple(
            file
            for file in build_input.evidence_files
            if file.confirmed and file.role == "EXPECTED_OUTPUT"
        )
        evidence_ok = bool(confirmed_inputs and confirmed_outputs)
        acceptance_cases = _object_list(normalized.get("acceptance_cases"))
        acceptance_kinds = {str(case.get("kind", "")) for case in acceptance_cases}
        acceptance_ok = (
            acceptance_kinds >= ACCEPTANCE_KINDS
            and not _find_markers(acceptance_cases)
            and _acceptance_refs_resolve(acceptance_cases, build_input.evidence_files)
            and _acceptance_refs_are_distinct(acceptance_cases)
        )
        normal_pair = _acceptance_pair(
            acceptance_cases,
            build_input.evidence_files,
            "NORMAL",
        )
        schema_match = normal_pair is not None and _evidence_schemas_match(
            _object(normalized.get("input_schema")),
            _object(normalized.get("output_schema")),
            normal_pair[0],
            normal_pair[1],
        )
        source_gate_ok = (
            build_input.opportunity.schema_valid
            and build_input.design_package.schema_valid
            and build_input.blueprint.schema_valid
            and build_input.blueprint.export_ready
            and _nested_string(build_input.opportunity.payload, "gate", "result")
            == "READY_FOR_DESIGN"
        )
        return (
            _check(
                "source-design-gate",
                source_gate_ok,
                "Source artifacts must be schema-valid READY_FOR_DESIGN and export-ready.",
            ),
            _check(
                "requirements-confirmed",
                requirements_confirmed,
                "Confirm the implementation requirements before CODEGEN_READY.",
            ),
            _check(
                "critical-fields",
                not missing and not unknown,
                (
                    f"Critical fields are missing or unresolved: missing={missing}, "
                    f"markers={unknown}"
                ),
            ),
            _check(
                "workflow-dag",
                workflow_ok,
                "Workflow step IDs and dependencies must form an acyclic DAG.",
            ),
            _check(
                "workflow-io",
                workflow_io_ok,
                "Every workflow step input must be supplied by evidence or an earlier step output.",
            ),
            _check(
                "data-contract",
                data_contract_ok,
                "Exact input/output schemas and source-to-target field mappings are required.",
            ),
            _check(
                "implementation-controls",
                controls_ok,
                (
                    "Rules, reliability, oversight, integrations, modules, "
                    "and operations are required."
                ),
            ),
            _check(
                "confirmed-fixtures",
                evidence_ok,
                "Confirm input and expected-output evidence files for the acceptance cases.",
            ),
            _check(
                "fixture-schema-match",
                schema_match,
                "Confirmed fixture fields must match the declared input and output schemas.",
            ),
            _check(
                "acceptance-coverage",
                acceptance_ok,
                (
                    "Normal, error, exception, and approval acceptance cases "
                    "need distinct, resolvable fixture refs and executable assertions."
                ),
            ),
        )

    def _normalized_requirements(
        self,
        requirements: JsonObject,
        evidence_files: tuple[EvidenceFileRead, ...],
    ) -> JsonObject:
        input_files = tuple(
            item for item in evidence_files if item.confirmed and item.role == "INPUT"
        )
        output_files = tuple(
            item for item in evidence_files if item.confirmed and item.role == "EXPECTED_OUTPUT"
        )
        input_ref = input_files[0].id if input_files else "UNRESOLVED_INPUT_EVIDENCE"
        output_ref = output_files[0].id if output_files else "UNRESOLVED_EXPECTED_EVIDENCE"
        acceptance_cases = _object_list(requirements.get("acceptance_cases"))
        if not acceptance_cases:
            acceptance_cases = _default_acceptance_cases(input_ref, output_ref)
        else:
            acceptance_cases = [deepcopy(case) for case in acceptance_cases]
        source_evidence = "work-model:source"
        return {
            "target_runtime": _string(requirements.get("target_runtime"), "UNKNOWN"),
            "framework": _string(requirements.get("framework"), "UNKNOWN"),
            "package_manager": _string(requirements.get("package_manager"), "UNKNOWN"),
            "execution_interface": _object_or_default(
                requirements.get("execution_interface"),
                {
                    "type": "CLI",
                    "command": "UNKNOWN",
                    "input_path_argument": "--input",
                    "output_path_argument": "--output",
                },
            ),
            "workflow": _object_or_default(
                requirements.get("workflow"),
                _default_workflow(input_ref),
            ),
            "input_schema": _object_or_default(
                requirements.get("input_schema"),
                {"type": "object"},
            ),
            "output_schema": _object_or_default(
                requirements.get("output_schema"),
                {"type": "object"},
            ),
            "field_mappings": _object_list(requirements.get("field_mappings")),
            "calculation_rules": _rule_list(
                requirements.get("calculation_rules"),
                "calculation-unknown",
                source_evidence,
            ),
            "decision_rules": _rule_list(
                requirements.get("decision_rules"),
                "decision-unknown",
                source_evidence,
            ),
            "validation_rules": _rule_list(
                requirements.get("validation_rules"),
                "validation-unknown",
                source_evidence,
            ),
            "exceptions": _object_list(requirements.get("exceptions")),
            "reliability": _object_or_default(
                requirements.get("reliability"),
                {"retry": "UNKNOWN", "idempotency": "UNKNOWN", "rollback": "UNKNOWN"},
            ),
            "human_oversight": _object_or_default(
                requirements.get("human_oversight"),
                {"approval_points": ["UNKNOWN"], "override_policy": "UNKNOWN"},
            ),
            "integrations": _object_list(requirements.get("integrations"))
            or [_default_integration(source_evidence)],
            "module_responsibilities": _object_list(
                requirements.get("module_responsibilities"),
            )
            or [{"path": "src/UNKNOWN", "responsibility": "UNKNOWN"}],
            "operations": _object_or_default(
                requirements.get("operations"),
                {
                    "logging": "UNKNOWN",
                    "audit": "UNKNOWN",
                    "security": "UNKNOWN",
                    "deployment": "UNKNOWN",
                },
            ),
            "acceptance_cases": acceptance_cases,
        }

    def _source_evidence_refs(
        self,
        build_input: ImplementationPackageInput,
    ) -> tuple[str, ...]:
        refs = {
            f"work-model:{build_input.work_model.project_id}:v{build_input.work_model.version}",
            f"opportunity:{build_input.opportunity.id}",
            f"design-package:{build_input.design_package.id}",
            f"blueprint:{build_input.blueprint.id}",
        }
        refs.update(
            f"evidence-file:{evidence.id}"
            for evidence in build_input.evidence_files
            if evidence.confirmed
        )
        refs.update(_collect_source_refs(build_input.work_model.payload))
        refs.update(_collect_source_refs(build_input.opportunity.payload))
        refs.update(_collect_source_refs(build_input.design_package.payload))
        return tuple(sorted(refs))

    def _follow_up_questions(self, checks: tuple[JsonObject, ...]) -> tuple[str, ...]:
        questions = {
            "requirements-confirmed": "구현 런타임·실행 명령·계약을 이 내용으로 확정할까요?",
            "critical-fields": "UNKNOWN으로 남은 구현 필드의 정확한 값을 무엇으로 정할까요?",
            "workflow-dag": "각 단계의 선행 단계와 실행 순서를 정확히 어떻게 연결해야 하나요?",
            "workflow-io": "각 단계가 읽는 입력과 생성하는 출력 이름을 무엇으로 확정할까요?",
            "data-contract": "입력/출력 필드, 자료형, 필수 여부와 변환식을 확인해 주세요.",
            "implementation-controls": "재시도·멱등성·롤백·승인·보안·배포 정책을 확정해 주세요.",
            "confirmed-fixtures": (
                "정상 입력과 기대 출력 샘플 파일을 각각 업로드하고 확인해 주세요."
            ),
            "fixture-schema-match": (
                "샘플에서 추출한 필드와 선언한 JSON Schema 중 어느 쪽이 정확한가요?"
            ),
            "acceptance-coverage": "정상·오류·예외·승인 필요 사례별 기대 결과를 확정해 주세요.",
            "source-design-gate": "M8까지 READY인 FULL_G1 blueprint를 먼저 생성해 주세요.",
        }
        return tuple(questions[str(check["key"])] for check in checks if check["passed"] is False)


def _check(key: str, passed: bool, failure_detail: str) -> JsonObject:
    detail = f"{key} passed." if passed else failure_detail
    return {"key": key, "passed": passed, "detail": detail}


def _object(value: JsonValue | None) -> JsonObject:
    return dict(value) if isinstance(value, dict) else {}


def _object_or_default(value: JsonValue | None, default: JsonObject) -> JsonObject:
    result = _object(value)
    return result or default


def _object_list(value: JsonValue | None) -> list[JsonObject]:
    if not isinstance(value, list | tuple):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _string(value: JsonValue | None, default: str) -> str:
    return value if isinstance(value, str) and value.strip() else default


def _rule_list(value: JsonValue | None, rule_id: str, evidence_ref: str) -> list[JsonObject]:
    rules = _object_list(value)
    return rules or [
        {
            "rule_id": rule_id,
            "expression": "UNKNOWN",
            "evidence_refs": [evidence_ref],
        },
    ]


def _default_workflow(input_ref: str) -> JsonObject:
    return {
        "workflow_id": "implementation-workflow",
        "name": "UNKNOWN",
        "trigger": {"type": "MANUAL", "description": "UNKNOWN"},
        "schedule": None,
        "completion_condition": "UNKNOWN",
        "steps": [
            {
                "step_id": "unresolved-step",
                "name": "UNKNOWN",
                "action": "UNKNOWN",
                "depends_on": [],
                "input_refs": [input_ref],
                "output_refs": ["UNRESOLVED_OUTPUT"],
                "rule_refs": [],
                "human_gate": None,
                "retry_policy": {"max_attempts": 1, "backoff_seconds": 0},
            },
        ],
    }


def _default_integration(evidence_ref: str) -> JsonObject:
    return {
        "integration_id": "unresolved-integration",
        "system_name": "UNKNOWN",
        "adapter_type": "FILE",
        "operation": "UNKNOWN",
        "access_mode": "READ",
        "auth_mode": "NONE",
        "environment_variables": [],
        "timeout_seconds": 30,
        "retry_policy": "UNKNOWN",
        "idempotency_key": None,
        "evidence_refs": [evidence_ref],
    }


def _default_acceptance_cases(input_ref: str, output_ref: str) -> list[JsonObject]:
    labels = (
        ("normal", "NORMAL"),
        ("error", "ERROR"),
        ("exception", "EXCEPTION"),
        ("approval", "APPROVAL_REQUIRED"),
    )
    return [
        {
            "fixture_id": f"{label}-fixture",
            "kind": kind,
            "scenario": "UNKNOWN",
            "input_file_refs": [input_ref],
            "expected_file_refs": [output_ref],
            "execution_command": "UNKNOWN",
            "assertions": [{"path": "$", "operator": "EXISTS", "expected": True}],
        }
        for label, kind in labels
    ]


def _find_markers(value: JsonValue) -> set[str]:
    markers: set[str] = set()
    if isinstance(value, str):
        if _has_marker(value):
            markers.add(value)
    elif isinstance(value, dict):
        for item in value.values():
            markers.update(_find_markers(item))
    elif isinstance(value, list | tuple):
        for item in value:
            markers.update(_find_markers(item))
    return markers


def _has_marker(value: str) -> bool:
    upper = value.upper()
    return any(marker in upper for marker in UNRESOLVED_MARKERS)


def _workflow_is_acyclic(workflow: JsonObject) -> bool:
    steps = _object_list(workflow.get("steps"))
    identifiers = [str(step.get("step_id", "")) for step in steps]
    if not identifiers or any(not identifier for identifier in identifiers):
        return False
    if len(set(identifiers)) != len(identifiers):
        return False
    dependencies = {
        str(step["step_id"]): {
            str(item) for item in cast("list[JsonValue]", step.get("depends_on", []))
        }
        for step in steps
    }
    if any(dep not in dependencies for values in dependencies.values() for dep in values):
        return False
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str) -> bool:
        if step_id in visiting:
            return False
        if step_id in visited:
            return True
        visiting.add(step_id)
        if not all(visit(dependency) for dependency in dependencies[step_id]):
            return False
        visiting.remove(step_id)
        visited.add(step_id)
        return True

    return all(visit(step_id) for step_id in dependencies)


def _workflow_io_connected(workflow: JsonObject) -> bool:
    steps = _object_list(workflow.get("steps"))
    available = {"fixture:input", "dataset:input"}
    for step in steps:
        inputs = {str(item) for item in _sequence(step.get("input_refs"))}
        if any(_has_marker(item) for item in inputs):
            return False
        if inputs and not inputs <= available:
            return False
        outputs = {str(item) for item in _sequence(step.get("output_refs"))}
        if not outputs or any(_has_marker(item) for item in outputs):
            return False
        available.update(outputs)
    return bool(steps)


def _sequence(value: JsonValue | None) -> tuple[JsonValue, ...]:
    return tuple(value) if isinstance(value, list | tuple) else ()


def _evidence_schemas_match(
    input_schema: JsonObject,
    output_schema: JsonObject,
    input_file: EvidenceFileRead,
    output_file: EvidenceFileRead,
) -> bool:
    input_matches = _schema_types_compatible(
        _schema_properties(input_schema),
        _schema_properties(input_file.extracted_schema),
    )
    try:
        Draft202012Validator.check_schema(output_schema)
        expected_value = json.loads(output_file.content.decode("utf-8-sig"))
    except (SchemaError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return input_matches and Draft202012Validator(output_schema).is_valid(expected_value)


def _schema_types_compatible(
    declared: dict[str, str],
    observed: dict[str, str],
) -> bool:
    if declared.keys() != observed.keys():
        return False
    return all(
        declared[name] == observed[name]
        or (declared[name] == "number" and observed[name] == "integer")
        for name in declared
    )


def _schema_properties(schema: JsonObject) -> dict[str, str]:
    target = schema
    items = schema.get("items")
    if isinstance(items, dict):
        target = dict(items)
    properties = target.get("properties")
    if not isinstance(properties, dict):
        return {}
    result: dict[str, str] = {}
    for name, spec in properties.items():
        if isinstance(spec, dict):
            result[str(name)] = str(spec.get("type", ""))
    return result


def _acceptance_refs_resolve(
    cases: list[JsonObject],
    evidence_files: tuple[EvidenceFileRead, ...],
) -> bool:
    confirmed_files = {item.id: item for item in evidence_files if item.confirmed}
    for case in cases:
        input_refs = tuple(str(ref) for ref in _sequence(case.get("input_file_refs")))
        output_refs = tuple(str(ref) for ref in _sequence(case.get("expected_file_refs")))
        if (
            not input_refs
            or not output_refs
            or any(ref not in confirmed_files for ref in (*input_refs, *output_refs))
            or any(confirmed_files[ref].role != "INPUT" for ref in input_refs)
            or any(confirmed_files[ref].role != "EXPECTED_OUTPUT" for ref in output_refs)
        ):
            return False
    return True


def _acceptance_refs_are_distinct(cases: list[JsonObject]) -> bool:
    cases_by_kind = {str(case.get("kind", "")): case for case in cases}
    if cases_by_kind.keys() < ACCEPTANCE_KINDS:
        return False
    input_refs = {
        str(ref)
        for kind in ACCEPTANCE_KINDS
        for ref in _sequence(cases_by_kind[kind].get("input_file_refs"))
    }
    output_refs = {
        str(ref)
        for kind in ACCEPTANCE_KINDS
        for ref in _sequence(cases_by_kind[kind].get("expected_file_refs"))
    }
    return len(input_refs) >= len(ACCEPTANCE_KINDS) and len(output_refs) >= len(
        ACCEPTANCE_KINDS,
    )


def _acceptance_pair(
    cases: list[JsonObject],
    evidence_files: tuple[EvidenceFileRead, ...],
    kind: str,
) -> tuple[EvidenceFileRead, EvidenceFileRead] | None:
    case = next((item for item in cases if item.get("kind") == kind), None)
    if case is None:
        return None
    inputs = tuple(str(ref) for ref in _sequence(case.get("input_file_refs")))
    outputs = tuple(str(ref) for ref in _sequence(case.get("expected_file_refs")))
    files_by_id = {item.id: item for item in evidence_files if item.confirmed}
    if not inputs or not outputs:
        return None
    input_file = files_by_id.get(inputs[0])
    output_file = files_by_id.get(outputs[0])
    if (
        input_file is None
        or output_file is None
        or input_file.role != "INPUT"
        or output_file.role != "EXPECTED_OUTPUT"
    ):
        return None
    return input_file, output_file


def _nested_string(payload: JsonObject, *path: str) -> str:
    current: JsonValue = payload
    for key in path:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return current if isinstance(current, str) else ""


def _collect_source_refs(payload: JsonObject) -> set[str]:
    refs: set[str] = set()

    def walk(value: JsonValue, key: str = "") -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                walk(child, str(child_key))
        elif isinstance(value, list | tuple):
            for child in value:
                walk(child, key)
        elif (isinstance(value, str) and key in {"source_ref", "evidence_ref"}) or (
            isinstance(value, str) and key in {"source_refs", "evidence_refs"}
        ):
            refs.add(value)

    walk(payload)
    return refs
