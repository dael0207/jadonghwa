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
    )
    for schema_path, example_path in pairs:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        example = json.loads(example_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(example)
    print("schema smoke OK")


if __name__ == "__main__":
    main()
