from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import NoReturn

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from work_discovery_api.contracts import ContractPaths, validate_payload
from work_discovery_api.models import (
    BlueprintRead,
    DesignPackageRead,
    EvidenceFileRead,
    ImplementationPackageRead,
    JsonObject,
    JsonValue,
    OpportunityRead,
    WorkModelRead,
    utc_now,
)

SECRET_VALUE_PATTERN = re.compile(
    r"(?im)^[A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY)[A-Z0-9_]*"
    r"\s*=\s*[^\s#][^\r\n]*$",
)
ABSOLUTE_WINDOWS_PATH = re.compile(r"(?i)\b[A-Z]:[\\/]")
ABSOLUTE_UNIX_PATH = re.compile(r"(?<![\w.])/(?:Users|home|root|tmp|var|etc|opt)/")


class ExportValidationError(ValueError):
    pass


def _fail(message: str, cause: Exception | None = None) -> NoReturn:
    if cause is None:
        raise ExportValidationError(message)
    raise ExportValidationError(message) from cause


@dataclass(frozen=True, slots=True)
class ImplementationExportSources:
    work_model: WorkModelRead
    opportunity: OpportunityRead
    design_package: DesignPackageRead
    blueprint: BlueprintRead
    evidence_files: tuple[EvidenceFileRead, ...]


def build_implementation_export(
    package: ImplementationPackageRead,
    sources: ImplementationExportSources,
    paths: ContractPaths,
    *,
    draft: bool,
) -> bytes:
    if not draft and package.readiness_status != "CODEGEN_READY":
        _fail(
            "CODEGEN_READY export is blocked; use mode=draft to inspect an incomplete package",
        )
    files = _artifact_files(package, sources)
    if not draft:
        _validate_codegen_payload(package, sources, paths, files)
    _validate_archive_entries(files)
    manifest = _manifest(package, files)
    manifest_error = validate_payload(paths.export_manifest_schema, manifest)
    if manifest_error is not None:
        _fail(f"export manifest is invalid: {manifest_error}")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _json_bytes(manifest))
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return buffer.getvalue()


def _artifact_files(
    package: ImplementationPackageRead,
    sources: ImplementationExportSources,
) -> dict[str, bytes]:
    payload = package.payload
    data_contract = _object(payload.get("data_contract"))
    rules = _object(payload.get("rules"))
    files: dict[str, bytes] = {
        "README.md": _readme(package).encode(),
        "source/work-model.json": _json_bytes(sources.work_model.payload),
        "source/opportunity.json": _json_bytes(sources.opportunity.payload),
        "source/design-package.json": _json_bytes(sources.design_package.payload),
        "source/blueprint.json": _json_bytes(sources.blueprint.payload),
        "contracts/workflow.json": _json_bytes(_object(payload.get("workflow"))),
        "contracts/integrations.json": _json_bytes(_json_list(payload.get("integrations"))),
        "contracts/input.schema.json": _json_bytes(_object(data_contract.get("input_schema"))),
        "contracts/output.schema.json": _json_bytes(_object(data_contract.get("output_schema"))),
        "contracts/mappings.json": _json_bytes(
            _json_list(data_contract.get("field_mappings")),
        ),
        "contracts/decisions.json": _json_bytes(rules),
        "contracts/exceptions.json": _json_bytes(_json_list(payload.get("exceptions"))),
        "contracts/approvals.json": _json_bytes(_object(payload.get("human_oversight"))),
        "implementation/stack.json": _json_bytes(
            {
                "target_runtime": payload.get("target_runtime"),
                "framework": payload.get("framework"),
                "package_manager": payload.get("package_manager"),
                "execution_interface": payload.get("execution_interface"),
            },
        ),
        "implementation/architecture.md": _architecture_markdown(package).encode(),
        "implementation/modules.json": _json_bytes(
            _json_list(payload.get("module_responsibilities")),
        ),
        "implementation/env.example": _env_example(payload).encode(),
        "implementation/deployment.md": _deployment_markdown(payload).encode(),
        "tests/acceptance-tests.json": _json_bytes(
            _json_list(payload.get("acceptance_cases")),
        ),
    }
    fixture_paths: dict[str, str] = {}
    for evidence in sources.evidence_files:
        if not evidence.confirmed:
            continue
        folder = "input" if evidence.role == "INPUT" else "expected"
        archive_path = f"tests/fixtures/{folder}/{evidence.id[:8]}-{evidence.filename}"
        files[archive_path] = evidence.content
        fixture_paths[evidence.id] = archive_path
        generic_ref = "fixture:input" if evidence.role == "INPUT" else "fixture:expected"
        fixture_paths.setdefault(generic_ref, archive_path)
    evidence_map = _evidence_map(package, fixture_paths)
    files["traceability/evidence-map.json"] = _json_bytes(evidence_map)
    return files


def _validate_codegen_payload(
    package: ImplementationPackageRead,
    sources: ImplementationExportSources,
    paths: ContractPaths,
    files: dict[str, bytes],
) -> None:
    package_error = validate_payload(paths.implementation_package_schema, package.payload)
    if package_error is not None:
        _fail(f"implementation package is invalid: {package_error}")
    readiness = _object(package.payload.get("codegen_readiness"))
    readiness_error = validate_payload(paths.codegen_readiness_schema, readiness)
    if readiness_error is not None or readiness.get("codegen_ready") is not True:
        _fail(
            f"codegen readiness is invalid: {readiness_error or 'gate is not ready'}",
        )
    workflow = _object(package.payload.get("workflow"))
    workflow_error = validate_payload(paths.automation_workflow_schema, workflow)
    if workflow_error is not None:
        _fail(f"workflow is invalid: {workflow_error}")
    _validate_workflow_refs(workflow, package.payload)
    cases = _validate_integrations_and_cases(package, sources, paths)
    _validate_data_contract(package)
    _validate_evidence_map(package, files)
    _validate_acceptance_assertions(cases)


def _validate_integrations_and_cases(
    package: ImplementationPackageRead,
    sources: ImplementationExportSources,
    paths: ContractPaths,
) -> list[JsonObject]:
    for integration in _json_object_list(package.payload.get("integrations")):
        error = validate_payload(paths.integration_contract_schema, integration)
        if error is not None:
            _fail(f"integration is invalid: {error}")
    cases = _json_object_list(package.payload.get("acceptance_cases"))
    for case in cases:
        error = validate_payload(paths.acceptance_fixture_schema, case)
        if error is not None:
            _fail(f"acceptance fixture is invalid: {error}")
    kinds = {str(case.get("kind", "")) for case in cases}
    required_kinds = {"NORMAL", "ERROR", "EXCEPTION", "APPROVAL_REQUIRED"}
    if not required_kinds <= kinds:
        _fail("acceptance fixtures must cover all four required kinds")
    confirmed_files = {item.id: item for item in sources.evidence_files if item.confirmed}
    input_refs: set[str] = set()
    expected_refs: set[str] = set()
    output_schema = _object(_object(package.payload.get("data_contract")).get("output_schema"))
    output_validator = Draft202012Validator(output_schema)
    for case in cases:
        case_input_refs = _json_string_list(case.get("input_file_refs"))
        case_expected_refs = _json_string_list(case.get("expected_file_refs"))
        refs = (*case_input_refs, *case_expected_refs)
        if (
            not case_input_refs
            or not case_expected_refs
            or any(ref not in confirmed_files for ref in refs)
            or any(confirmed_files[ref].role != "INPUT" for ref in case_input_refs)
            or any(confirmed_files[ref].role != "EXPECTED_OUTPUT" for ref in case_expected_refs)
        ):
            _fail("acceptance fixture contains an unresolved file ref")
        input_refs.update(case_input_refs)
        expected_refs.update(case_expected_refs)
        for ref in case_expected_refs:
            try:
                expected_value = json.loads(confirmed_files[ref].content.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                _fail(f"expected fixture {ref} must contain UTF-8 JSON", error)
            validation_errors = tuple(output_validator.iter_errors(expected_value))
            if validation_errors:
                _fail(
                    f"expected fixture {ref} does not match the output schema: "
                    f"{validation_errors[0].message}",
                )
    if len(input_refs) < len(required_kinds) or len(expected_refs) < len(required_kinds):
        _fail("each acceptance kind must use distinct input and expected fixtures")
    return cases


def _validate_data_contract(
    package: ImplementationPackageRead,
) -> None:
    data_contract = _object(package.payload.get("data_contract"))
    for key in ("input_schema", "output_schema"):
        schema = _object(data_contract.get(key))
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            _fail(f"{key} is not a valid JSON Schema: {error}", error)


def _validate_evidence_map(
    package: ImplementationPackageRead,
    files: dict[str, bytes],
) -> None:
    evidence_map = json.loads(files["traceability/evidence-map.json"])
    mapped_refs = {
        str(item["ref"])
        for item in evidence_map["entries"]
        if isinstance(item, dict) and "ref" in item
    }
    required_refs = _collect_evidence_refs(package.payload)
    if not required_refs <= mapped_refs:
        missing = sorted(required_refs - mapped_refs)
        _fail(f"unresolved evidence refs: {missing}")
    archive_paths = set(files)
    unresolved_targets = {
        str(item.get("target_path", ""))
        for item in evidence_map["entries"]
        if isinstance(item, dict)
        and str(item.get("target_path", "")) not in archive_paths
    }
    if unresolved_targets:
        _fail(f"evidence refs point outside the archive: {sorted(unresolved_targets)}")


def _validate_workflow_refs(workflow: JsonObject, package: JsonObject) -> None:
    steps = _json_object_list(workflow.get("steps"))
    step_ids = {str(step.get("step_id", "")) for step in steps}
    dependencies = {
        str(step.get("step_id", "")): set(_json_string_list(step.get("depends_on")))
        for step in steps
    }
    if any(not step_id for step_id in step_ids) or any(
        dependency not in step_ids for values in dependencies.values() for dependency in values
    ):
        _fail("workflow contains an unresolved step dependency")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str) -> None:
        if step_id in visiting:
            _fail("workflow DAG contains a cycle")
        if step_id in visited:
            return
        visiting.add(step_id)
        for dependency in dependencies[step_id]:
            visit(dependency)
        visiting.remove(step_id)
        visited.add(step_id)

    for step_id in step_ids:
        visit(step_id)
    rules = _object(package.get("rules"))
    rule_ids = {
        str(rule.get("rule_id", ""))
        for key in ("calculations", "decisions", "validations")
        for rule in _json_object_list(rules.get(key))
    }
    referenced_rules = {ref for step in steps for ref in _json_string_list(step.get("rule_refs"))}
    if not referenced_rules <= rule_ids:
        _fail(
            f"workflow rule refs are unresolved: {sorted(referenced_rules - rule_ids)}",
        )
    available = {"fixture:input", "dataset:input"}
    for step in steps:
        inputs = set(_json_string_list(step.get("input_refs")))
        if inputs and not inputs <= available:
            _fail(
                f"workflow inputs are not connected: {sorted(inputs - available)}",
            )
        outputs = set(_json_string_list(step.get("output_refs")))
        if not outputs:
            _fail("every workflow step must produce an output")
        available.update(outputs)


def _validate_acceptance_assertions(cases: list[JsonObject]) -> None:
    for case in cases:
        assertions = _json_object_list(case.get("assertions"))
        if not assertions:
            _fail("acceptance cases must assert semantic output values")
        if all(str(item.get("operator", "")) in {"EXISTS", "TYPE_IS"} for item in assertions):
            _fail(
                "each acceptance case needs at least one value or approval assertion",
            )


def _validate_archive_entries(files: dict[str, bytes]) -> None:
    for name, content in files.items():
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or ABSOLUTE_WINDOWS_PATH.search(
                name,
            )
        ):
            _fail(f"unsafe archive path: {name}")
        if name.endswith((".json", ".md", ".example", ".csv", ".txt", ".yaml", ".yml")):
            text = content.decode("utf-8")
            if ABSOLUTE_WINDOWS_PATH.search(text) or ABSOLUTE_UNIX_PATH.search(text):
                _fail(f"absolute path found in {name}")
            if SECRET_VALUE_PATTERN.search(text):
                _fail(f"secret-like value found in {name}")


def _manifest(package: ImplementationPackageRead, files: dict[str, bytes]) -> JsonObject:
    entries = [
        {
            "path": name,
            "media_type": _media_type(name),
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
        for name, content in sorted(files.items())
    ]
    return {
        "manifest_version": "export-manifest-v1",
        "package_id": package.id,
        "readiness_status": package.readiness_status.value,
        "generated_at": utc_now().isoformat(),
        "files": entries,
    }


def _evidence_map(
    package: ImplementationPackageRead,
    fixture_paths: dict[str, str],
) -> JsonObject:
    entries: list[JsonObject] = []
    all_refs = _collect_evidence_refs(package.payload)
    for ref in sorted(all_refs):
        target_path = "source/work-model.json"
        if ref.startswith("opportunity:"):
            target_path = "source/opportunity.json"
        elif ref.startswith("design-package:"):
            target_path = "source/design-package.json"
        elif ref.startswith("blueprint:"):
            target_path = "source/blueprint.json"
        elif ref.startswith("evidence-file:"):
            file_id = ref.removeprefix("evidence-file:")
            target_path = fixture_paths.get(file_id, "UNRESOLVED")
        elif ref in fixture_paths:
            target_path = fixture_paths[ref]
        elif ref.startswith("rule:"):
            target_path = "contracts/decisions.json"
        entries.append({"ref": ref, "target_path": target_path})
    for file_id, target_path in fixture_paths.items():
        if file_id not in all_refs:
            entries.append({"ref": file_id, "target_path": target_path})
    return {"package_id": package.id, "entries": entries}


def _collect_evidence_refs(payload: JsonObject) -> set[str]:
    refs: set[str] = set()

    def walk(value: JsonValue, key: str = "") -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                walk(child, str(child_key))
        elif isinstance(value, list | tuple):
            if key in {"evidence_refs", "input_file_refs", "expected_file_refs"}:
                refs.update(str(item) for item in value if isinstance(item, str))
            else:
                for child in value:
                    walk(child, key)
        elif isinstance(value, str) and key in {"evidence_ref", "source_ref"}:
            refs.add(value)

    walk(payload)
    return refs


def _readme(package: ImplementationPackageRead) -> str:
    return (
        "# Implementation Package\n\n"
        f"Package: `{package.id}`\n\n"
        f"Gate: `{package.readiness_status.value}`\n\n"
        "This archive is an implementation contract, not generated production code. "
        "It must not execute external systems or contain credential values.\n"
    )


def _architecture_markdown(package: ImplementationPackageRead) -> str:
    payload = package.payload
    workflow = _object(payload.get("workflow"))
    return (
        "# Architecture\n\n"
        f"Runtime: {payload.get('target_runtime')}\n\n"
        f"Framework: {payload.get('framework')}\n\n"
        f"Workflow: {workflow.get('name')}\n\n"
        "Implement adapters behind the integration contracts. Keep transformation rules "
        "pure and validate every input and output against the exported schemas.\n"
    )


def _deployment_markdown(payload: JsonObject) -> str:
    operations = _object(payload.get("operations"))
    return (
        "# Deployment\n\n"
        f"{operations.get('deployment', 'No deployment contract supplied.')}\n\n"
        "Production deployment, external-system execution, and credential provisioning "
        "remain explicit operator responsibilities outside this package.\n"
    )


def _env_example(payload: JsonObject) -> str:
    integrations = _json_object_list(payload.get("integrations"))
    variables: dict[str, str] = {}
    for integration in integrations:
        for variable in _json_object_list(integration.get("environment_variables")):
            name = str(variable.get("name", ""))
            description = str(variable.get("description", ""))
            if name:
                variables[name] = description
    lines: list[str] = []
    for name, description in sorted(variables.items()):
        lines.extend((f"# {description}", f"{name}=", ""))
    return "\n".join(lines)


def _json_bytes(value: JsonValue) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def _object(value: JsonValue | None) -> JsonObject:
    return dict(value) if isinstance(value, dict) else {}


def _json_list(value: JsonValue | None) -> list[JsonValue]:
    return list(value) if isinstance(value, list | tuple) else []


def _json_object_list(value: JsonValue | None) -> list[JsonObject]:
    return [dict(item) for item in _json_list(value) if isinstance(item, dict)]


def _json_string_list(value: JsonValue | None) -> tuple[str, ...]:
    return tuple(str(item) for item in _json_list(value) if isinstance(item, str))


def _media_type(name: str) -> str:
    if name.endswith(".json"):
        return "application/json"
    if name.endswith(".md"):
        return "text/markdown"
    if name.endswith(".csv"):
        return "text/csv"
    if name.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "text/plain"
