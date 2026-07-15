from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from work_discovery_api.models import JsonObject


@dataclass(frozen=True, slots=True)
class ContractPaths:
    root: Path

    @property
    def question_bank(self) -> Path:
        return self.root / "question-bank-v1.json"

    @property
    def work_model_schema(self) -> Path:
        return self.root / "schemas" / "work-model-v1.schema.json"

    @property
    def interview_state_schema(self) -> Path:
        return self.root / "schemas" / "interview-state-v1.schema.json"

    @property
    def opportunity_schema(self) -> Path:
        return self.root / "schemas" / "opportunity-v1.schema.json"

    @property
    def design_package_schema(self) -> Path:
        return self.root / "schemas" / "design-package-v1.schema.json"


def default_contract_paths() -> ContractPaths:
    return ContractPaths(root=Path(__file__).resolve().parents[4])


def read_json(path: Path) -> JsonObject:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data
    message = f"expected JSON object in {path}"
    raise TypeError(message)


def schema_validator(schema_path: Path) -> Draft202012Validator:
    schema = read_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_payload(schema_path: Path, payload: JsonObject) -> str | None:
    validator = schema_validator(schema_path)
    try:
        validator.validate(payload)
    except ValidationError as error:
        return error.message
    return None


def initial_questions(paths: ContractPaths | None = None) -> tuple[JsonObject, ...]:
    contract_paths = paths or default_contract_paths()
    bank = read_json(contract_paths.question_bank)
    questions_value = bank.get("questions")
    if not isinstance(questions_value, list):
        message = "question bank must contain a questions array"
        raise TypeError(message)

    question_objects = [item for item in questions_value if isinstance(item, dict)]
    non_consent = [item for item in question_objects if item.get("stage") != "CONSENT"]
    selected = non_consent[:10] if len(non_consent) >= 10 else question_objects[:10]
    return tuple(selected)
