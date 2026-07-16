from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from work_discovery_api.domain import AuditAction
from work_discovery_api.main import create_app
from work_discovery_api.store import MemoryStore

ROOT = Path(__file__).resolve().parents[3]


def client() -> TestClient:
    return TestClient(create_app(MemoryStore()))


def create_project_and_interview(api: TestClient) -> tuple[str, str]:
    project_response = api.post("/v1/projects", json={"name": "Monthly report"})
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    interview_response = api.post(f"/v1/projects/{project_id}/interviews")
    assert interview_response.status_code == 201
    interview_id = interview_response.json()["id"]
    consent = api.post(
        f"/v1/interviews/{interview_id}/consent",
        json={"ai_processing": True, "data_processing": True},
    )
    assert consent.status_code == 200
    return project_id, interview_id


def rich_work_model_payload() -> dict[str, object]:
    return json.loads((ROOT / "examples" / "monthly-report-work-model.json").read_text("utf-8"))


def ready_work_model_payload() -> dict[str, object]:
    payload = rich_work_model_payload()
    exceptions = payload["exceptions"]
    assert isinstance(exceptions, list)
    for item in exceptions:
        assert isinstance(item, dict)
        meta = item["meta"]
        assert isinstance(meta, dict)
        meta["state"] = "CORROBORATED"
        meta["confidence"] = 0.9
    gate = payload["understanding_gate"]
    assert isinstance(gate, dict)
    gate["open_material_gaps"] = []
    gate["result"] = "READY_FOR_ANALYSIS"
    return payload


def design_package_schema() -> dict[str, object]:
    return json.loads((ROOT / "schemas" / "design-package-v1.schema.json").read_text("utf-8"))


def validate_work_model_and_analyze(
    api: TestClient,
    project_id: str,
    payload: dict[str, object],
) -> dict[str, object]:
    validated_model = api.post(
        f"/v1/projects/{project_id}/work-model/validate",
        json={"payload": payload},
    )
    assert validated_model.status_code == 200
    assert validated_model.json()["valid"] is True
    analyzed = api.post(f"/v1/projects/{project_id}/opportunities/analyze")
    assert analyzed.status_code == 201
    return analyzed.json()


def answer_all_questions_and_analyze(api: TestClient, project_id: str, interview_id: str) -> str:
    questions = api.get(f"/v1/interviews/{interview_id}/questions")
    assert questions.status_code == 200
    for index, question in enumerate(questions.json(), start=1):
        answer = api.post(
            f"/v1/interviews/{interview_id}/answers",
            json={
                "question_id": question["id"],
                "text": f"{index} answer with little structured system evidence.",
            },
        )
        assert answer.status_code == 201
    built = api.post(f"/v1/interviews/{interview_id}/build-work-model")
    assert built.status_code == 200
    analyzed = api.post(f"/v1/projects/{project_id}/opportunities/analyze")
    assert analyzed.status_code == 201
    return analyzed.json()["id"]


def test_m5_enable_first_design_package_accumulates_validates_and_audits() -> None:
    api = client()
    project_id, _interview_id = create_project_and_interview(api)
    opportunity = validate_work_model_and_analyze(api, project_id, rich_work_model_payload())
    readiness = api.get(f"/v1/projects/{project_id}/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["result"] == "ENABLE_FIRST"

    first = api.post(f"/v1/opportunities/{opportunity['id']}/design-package")
    assert first.status_code == 201
    package = first.json()
    assert package["schema_valid"] is True
    assert package["payload"]["package_type"] == "ENABLEMENT_PREP"
    assert package["payload"]["readiness_result"] == "ENABLE_FIRST"
    Draft202012Validator(design_package_schema()).validate(package["payload"])

    second = api.post(f"/v1/opportunities/{opportunity['id']}/design-package")
    assert second.status_code == 201
    assert second.json()["id"] != package["id"]

    by_opportunity = api.get(f"/v1/opportunities/{opportunity['id']}/design-packages")
    assert by_opportunity.status_code == 200
    assert len(by_opportunity.json()) == 2

    by_project = api.get(f"/v1/projects/{project_id}/design-packages")
    assert by_project.status_code == 200
    assert len(by_project.json()) == 2

    fetched = api.get(f"/v1/design-packages/{package['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == package["id"]

    validation = api.post(f"/v1/design-packages/{package['id']}/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    audit = api.get(f"/v1/projects/{project_id}/audit-events")
    actions = {event["action"] for event in audit.json()}
    assert AuditAction.DESIGN_PACKAGE_CREATED in actions
    assert AuditAction.DESIGN_PACKAGE_VALIDATED in actions


def test_m5_ready_for_design_generates_full_g1_package() -> None:
    api = client()
    project_id, _interview_id = create_project_and_interview(api)
    opportunity = validate_work_model_and_analyze(api, project_id, ready_work_model_payload())
    readiness = api.get(f"/v1/projects/{project_id}/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["result"] == "READY_FOR_DESIGN"

    response = api.post(f"/v1/opportunities/{opportunity['id']}/design-package")

    assert response.status_code == 201
    body = response.json()
    assert body["payload"]["package_type"] == "FULL_G1"
    Draft202012Validator(design_package_schema()).validate(body["payload"])


def test_m5_discovery_needed_design_package_is_rejected() -> None:
    api = client()
    project_id, interview_id = create_project_and_interview(api)
    opportunity_id = answer_all_questions_and_analyze(api, project_id, interview_id)
    readiness = api.get(f"/v1/projects/{project_id}/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["result"] in {"BLOCKED", "DISCOVERY_NEEDED"}

    response = api.post(f"/v1/opportunities/{opportunity_id}/design-package")

    assert response.status_code == 409
    assert "cannot create a design package" in response.json()["detail"]
