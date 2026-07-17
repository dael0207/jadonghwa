from __future__ import annotations

import json

from jsonschema import Draft202012Validator

from work_discovery_api.contracts import default_contract_paths


def main() -> None:
    paths = default_contract_paths()
    pairs = (
        (paths.work_model_schema, paths.root / "examples" / "monthly-report-work-model.json"),
        (
            paths.interview_state_schema,
            paths.root / "examples" / "monthly-report-interview-state.json",
        ),
        (paths.opportunity_schema, paths.root / "examples" / "monthly-report-opportunity.json"),
        (paths.opportunity_schema, paths.root / "examples" / "monthly-report-opportunity-m4.json"),
        (
            paths.design_package_schema,
            paths.root / "examples" / "monthly-report-design-package.json",
        ),
        (paths.blueprint_schema, paths.root / "examples" / "monthly-report-blueprint.json"),
        (
            paths.evaluation_run_schema,
            paths.root / "examples" / "monthly-report-evaluation-run.json",
        ),
        (
            paths.release_readiness_schema,
            paths.root / "examples" / "monthly-report-release-readiness.json",
        ),
    )
    for schema_path, example_path in pairs:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        example = json.loads(example_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(example)
    m9_requirements = json.loads(
        (
            paths.root / "examples" / "m9" / "monthly-report-implementation-requirements.json"
        ).read_text(encoding="utf-8"),
    )
    Draft202012Validator(
        json.loads(paths.automation_workflow_schema.read_text(encoding="utf-8")),
    ).validate(m9_requirements["workflow"])
    integration_validator = Draft202012Validator(
        json.loads(paths.integration_contract_schema.read_text(encoding="utf-8")),
    )
    for integration in m9_requirements["integrations"]:
        integration_validator.validate(integration)
    fixture_validator = Draft202012Validator(
        json.loads(paths.acceptance_fixture_schema.read_text(encoding="utf-8")),
    )
    for fixture in m9_requirements["acceptance_cases"]:
        fixture_validator.validate(fixture)
    for schema_path in (
        paths.implementation_package_schema,
        paths.codegen_readiness_schema,
        paths.export_manifest_schema,
    ):
        Draft202012Validator.check_schema(
            json.loads(schema_path.read_text(encoding="utf-8")),
        )
    print("schema smoke OK")


if __name__ == "__main__":
    main()
