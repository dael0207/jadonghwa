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


def create_project_and_interview(api: TestClient, name: str) -> tuple[str, str]:
    project_response = api.post("/v1/projects", json={"name": name})
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


def validate_work_model_and_analyze(
    api: TestClient,
    project_id: str,
    payload: dict[str, object],
) -> dict[str, object]:
    validated = api.post(
        f"/v1/projects/{project_id}/work-model/validate",
        json={"payload": payload},
    )
    assert validated.status_code == 200
    assert validated.json()["valid"] is True
    analyzed = api.post(f"/v1/projects/{project_id}/opportunities/analyze")
    assert analyzed.status_code == 201
    return analyzed.json()


def create_design_package(api: TestClient, opportunity_id: str) -> dict[str, object]:
    response = api.post(f"/v1/opportunities/{opportunity_id}/design-package")
    assert response.status_code == 201
    return response.json()


def schema(name: str) -> dict[str, object]:
    return json.loads((ROOT / "schemas" / name).read_text("utf-8"))


def test_m6_full_g1_blueprint_accumulates_exports_validates_and_audits() -> None:
    api = client()
    project_id, _interview_id = create_project_and_interview(api, "M6 ready monthly report")
    opportunity = validate_work_model_and_analyze(api, project_id, ready_work_model_payload())
    package = create_design_package(api, str(opportunity["id"]))

    first = api.post(f"/v1/design-packages/{package['id']}/blueprint")
    assert first.status_code == 201
    blueprint = first.json()
    assert blueprint["schema_valid"] is True
    assert blueprint["export_ready"] is True
    assert blueprint["payload"]["blueprint_type"] == "FULL_G1_BLUEPRINT"
    Draft202012Validator(schema("blueprint-v1.schema.json")).validate(blueprint["payload"])

    second = api.post(f"/v1/design-packages/{package['id']}/blueprint")
    assert second.status_code == 201
    assert second.json()["id"] != blueprint["id"]

    by_package = api.get(f"/v1/design-packages/{package['id']}/blueprints")
    assert by_package.status_code == 200
    assert len(by_package.json()) == 2
    by_project = api.get(f"/v1/projects/{project_id}/blueprints")
    assert by_project.status_code == 200
    assert len(by_project.json()) == 2
    fetched = api.get(f"/v1/blueprints/{blueprint['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == blueprint["id"]

    validation = api.post(f"/v1/blueprints/{blueprint['id']}/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True
    json_export = api.get(f"/v1/blueprints/{blueprint['id']}/export/json")
    assert json_export.status_code == 200
    assert json_export.json()["blueprint_id"] == blueprint["payload"]["blueprint_id"]
    markdown = api.get(f"/v1/blueprints/{blueprint['id']}/export/markdown")
    assert markdown.status_code == 200
    assert "G1 Solution Blueprint" in markdown.text

    actions = project_actions(api, project_id)
    assert AuditAction.BLUEPRINT_CREATED in actions
    assert AuditAction.BLUEPRINT_VALIDATED in actions
    assert AuditAction.BLUEPRINT_EXPORTED in actions


def test_m6_enablement_package_creates_limited_non_export_blueprint() -> None:
    api = client()
    project_id, _interview_id = create_project_and_interview(api, "M6 enablement monthly report")
    opportunity = validate_work_model_and_analyze(api, project_id, rich_work_model_payload())
    package = create_design_package(api, str(opportunity["id"]))
    package_payload = package["payload"]
    assert isinstance(package_payload, dict)
    assert package_payload["package_type"] == "ENABLEMENT_PREP"

    response = api.post(f"/v1/design-packages/{package['id']}/blueprint")

    assert response.status_code == 201
    body = response.json()
    assert body["schema_valid"] is True
    assert body["export_ready"] is False
    assert body["payload"]["blueprint_type"] == "ENABLEMENT_FOLLOWUP"
    assert body["payload"]["quality_gate"]["passed"] is False


def test_m7_evaluation_run_scores_validates_and_audits() -> None:
    api = client()
    project_id, blueprint_id = full_blueprint_project(api)

    response = api.post(f"/v1/projects/{project_id}/evaluation-runs")

    assert response.status_code == 201
    body = response.json()
    assert body["schema_valid"] is True
    assert body["payload"]["item_count"] == 24
    assert body["payload"]["score_summary"]["overall_passed"] is True
    Draft202012Validator(schema("evaluation-run-v1.schema.json")).validate(body["payload"])

    listed = api.get(f"/v1/projects/{project_id}/evaluation-runs")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    fetched = api.get(f"/v1/evaluation-runs/{body['id']}")
    assert fetched.status_code == 200
    validation = api.post(f"/v1/evaluation-runs/{body['id']}/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    assert blueprint_id
    actions = project_actions(api, project_id)
    assert AuditAction.EVALUATION_RUN_CREATED in actions
    assert AuditAction.EVALUATION_RUN_VALIDATED in actions


def test_m8_release_readiness_reports_blockers_validates_and_audits() -> None:
    api = client()
    project_id, _blueprint_id = full_blueprint_project(api)
    evaluation = api.post(f"/v1/projects/{project_id}/evaluation-runs")
    assert evaluation.status_code == 201

    response = api.post(f"/v1/projects/{project_id}/release-readiness")

    assert response.status_code == 201
    body = response.json()
    assert body["schema_valid"] is True
    assert body["payload"]["readiness_status"] == "READY"
    Draft202012Validator(schema("release-readiness-v1.schema.json")).validate(body["payload"])

    listed = api.get(f"/v1/projects/{project_id}/release-readiness")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    fetched = api.get(f"/v1/release-readiness/{body['id']}")
    assert fetched.status_code == 200
    validation = api.post(f"/v1/release-readiness/{body['id']}/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    actions = project_actions(api, project_id)
    assert AuditAction.RELEASE_READINESS_CREATED in actions
    assert AuditAction.RELEASE_READINESS_VALIDATED in actions


def test_m8_release_readiness_is_not_ready_without_blueprint() -> None:
    api = client()
    project_id, _interview_id = create_project_and_interview(api, "M8 missing blueprint")

    response = api.post(f"/v1/projects/{project_id}/release-readiness")

    assert response.status_code == 201
    body = response.json()
    assert body["payload"]["readiness_status"] == "NOT_READY"
    assert len(body["payload"]["blocking_items"]) > 0


def full_blueprint_project(api: TestClient) -> tuple[str, str]:
    project_id, _interview_id = create_project_and_interview(api, "M6-M8 full chain")
    opportunity = validate_work_model_and_analyze(api, project_id, ready_work_model_payload())
    package = create_design_package(api, str(opportunity["id"]))
    blueprint = api.post(f"/v1/design-packages/{package['id']}/blueprint")
    assert blueprint.status_code == 201
    return project_id, blueprint.json()["id"]


def project_actions(api: TestClient, project_id: str) -> set[AuditAction]:
    audit = api.get(f"/v1/projects/{project_id}/audit-events")
    assert audit.status_code == 200
    return {AuditAction(event["action"]) for event in audit.json()}
