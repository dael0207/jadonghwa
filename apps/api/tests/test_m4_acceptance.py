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
    return project_id, interview_response.json()["id"]


def grant_consent(api: TestClient, interview_id: str) -> None:
    response = api.post(
        f"/v1/interviews/{interview_id}/consent",
        json={"ai_processing": True, "data_processing": True},
    )
    assert response.status_code == 200


def answer_all_questions(api: TestClient, interview_id: str) -> list[str]:
    questions_response = api.get(f"/v1/interviews/{interview_id}/questions")
    assert questions_response.status_code == 200
    answer_ids: list[str] = []
    for index, question in enumerate(questions_response.json(), start=1):
        response = api.post(
            f"/v1/interviews/{interview_id}/answers",
            json={
                "question_id": question["id"],
                "text": (
                    f"{index} answer: collect data, check rules, build a monthly report, "
                    "fix errors, and ask for approval."
                ),
            },
        )
        assert response.status_code == 201
        answer_ids.append(response.json()["id"])
    return answer_ids


def build_work_model(api: TestClient, interview_id: str) -> None:
    response = api.post(f"/v1/interviews/{interview_id}/build-work-model")
    assert response.status_code == 200
    assert response.json()["schema_valid"] is True


def playback_ready(api: TestClient) -> tuple[str, str, list[str]]:
    project_id, interview_id = create_project_and_interview(api)
    grant_consent(api, interview_id)
    answer_ids = answer_all_questions(api, interview_id)
    build_work_model(api, interview_id)
    return project_id, interview_id, answer_ids


def opportunity_schema() -> dict[str, object]:
    return json.loads((ROOT / "schemas" / "opportunity-v1.schema.json").read_text("utf-8"))


def rich_work_model_payload() -> dict[str, object]:
    return json.loads((ROOT / "examples" / "monthly-report-work-model.json").read_text("utf-8"))


def test_m4_analyze_requires_schema_valid_work_model() -> None:
    api = client()
    project_id, interview_id = create_project_and_interview(api)
    grant_consent(api, interview_id)

    response = api.post(f"/v1/projects/{project_id}/opportunities/analyze")

    assert response.status_code == 409


def test_m4_analyze_persists_scores_readiness_validation_and_audit() -> None:
    api = client()
    project_id, _interview_id, _answer_ids = playback_ready(api)

    analyzed = api.post(f"/v1/projects/{project_id}/opportunities/analyze")
    assert analyzed.status_code == 201
    opportunity = analyzed.json()
    assert opportunity["schema_valid"] is True
    Draft202012Validator(opportunity_schema()).validate(opportunity["payload"])
    scores = opportunity["payload"]["scores"]
    assert {"value", "feasibility", "risk", "evidence_confidence", "oversight"} <= set(scores)
    assert "score_explanation" in scores

    listed = api.get(f"/v1/projects/{project_id}/opportunities")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = api.get(f"/v1/opportunities/{opportunity['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == opportunity["id"]

    readiness = api.get(f"/v1/projects/{project_id}/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["result"] != "READY_FOR_DESIGN"
    assert readiness.json()["blocking_reasons"]
    assert readiness.json()["missing_evidence"]
    assert readiness.json()["required_followups"]

    validated = api.post(
        f"/v1/opportunities/{opportunity['id']}/validate",
        json={"accepted": True, "notes": "looks deterministic"},
    )
    assert validated.status_code == 200
    assert validated.json()["valid"] is True

    audit = api.get(f"/v1/projects/{project_id}/audit-events")
    actions = {event["action"] for event in audit.json()}
    assert AuditAction.OPPORTUNITY_ANALYZED in actions
    assert AuditAction.OPPORTUNITY_VALIDATED in actions
    assert AuditAction.READINESS_EVALUATED in actions


def test_m4_rebuild_analyze_and_diff_accumulates_opportunities() -> None:
    api = client()
    project_id, interview_id, answer_ids = playback_ready(api)

    first = api.post(f"/v1/projects/{project_id}/opportunities/analyze")
    assert first.status_code == 201

    rejected = api.post(f"/v1/interviews/{interview_id}/playback/reject")
    assert rejected.status_code == 200
    evidence = api.post(
        f"/v1/interviews/{interview_id}/evidence",
        json={"text": "Approval rules and exception handling are now clarified."},
    )
    assert evidence.status_code == 201
    revision = api.post(
        f"/v1/interviews/{interview_id}/answers/{answer_ids[0]}/revise",
        json={"text": "Revision: ERP CSV, Excel template, approval rule, and export exceptions."},
    )
    assert revision.status_code == 200
    resumed = api.post(f"/v1/interviews/{interview_id}/resume-model-building")
    assert resumed.status_code == 200
    build_work_model(api, interview_id)

    second = api.post(f"/v1/projects/{project_id}/opportunities/analyze")
    assert second.status_code == 201
    listed = api.get(f"/v1/projects/{project_id}/opportunities")
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    diff = api.get(f"/v1/projects/{project_id}/opportunities/diff")
    assert diff.status_code == 200
    body = diff.json()
    assert body["previous_opportunity_id"] == first.json()["id"]
    assert body["latest_opportunity_id"] == second.json()["id"]
    assert "value" in body["score_changes"]
    assert isinstance(body["recommendation_changed"], bool)

    audit = api.get(f"/v1/projects/{project_id}/audit-events")
    actions = {event["action"] for event in audit.json()}
    assert AuditAction.OPPORTUNITY_DIFF_GENERATED in actions


def test_m4_consent_revoke_blocks_analysis() -> None:
    api = client()
    project_id, interview_id, _answer_ids = playback_ready(api)
    revoke = api.post(f"/v1/interviews/{interview_id}/consent/revoke")
    assert revoke.status_code == 200

    response = api.post(f"/v1/projects/{project_id}/opportunities/analyze")

    assert response.status_code == 403


def test_m4_rich_evidence_reaches_enable_or_ready_gate() -> None:
    api = client()
    project_id, interview_id = create_project_and_interview(api)
    grant_consent(api, interview_id)
    payload = rich_work_model_payload()

    validated_model = api.post(
        f"/v1/projects/{project_id}/work-model/validate",
        json={"payload": payload},
    )
    assert validated_model.status_code == 200
    assert validated_model.json()["valid"] is True

    analyzed = api.post(f"/v1/projects/{project_id}/opportunities/analyze")
    assert analyzed.status_code == 201
    opportunity = analyzed.json()["payload"]
    assert opportunity["gate"]["result"] in {"ENABLE_FIRST", "READY_FOR_DESIGN"}
    assert opportunity["scores"]["evidence_confidence"] >= 0.75
    assert opportunity["scores"]["feasibility"] >= 50

    readiness = api.get(f"/v1/interviews/{interview_id}/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["result"] in {"ENABLE_FIRST", "READY_FOR_DESIGN"}
