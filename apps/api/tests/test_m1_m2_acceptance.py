from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from work_discovery_api.domain import AuditAction, InterviewStatus
from work_discovery_api.main import create_app
from work_discovery_api.postgres_repository import PostgresRepository
from work_discovery_api.repository_factory import create_repository
from work_discovery_api.store import MemoryStore

if TYPE_CHECKING:
    import pytest


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


def answer_all_questions(api: TestClient, interview_id: str) -> None:
    questions = api.get(f"/v1/interviews/{interview_id}/questions").json()
    for index, question in enumerate(questions, start=1):
        response = api.post(
            f"/v1/interviews/{interview_id}/answers",
            json={
                "question_id": question["id"],
                "text": f"{index}번 답변: 월간 보고 업무를 설명합니다.",
            },
        )
        assert response.status_code == 201


def test_repository_factory_uses_postgres_when_database_url_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a DATABASE_URL setting.
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/work_discovery")

    # When: the repository factory creates the app store.
    repository = create_repository()

    # Then: the PostgreSQL implementation boundary is selected.
    assert isinstance(repository, PostgresRepository)


def test_build_work_model_requires_completed_questions() -> None:
    # Given: a consented interview with only one answer.
    api = client()
    _, interview_id = create_project_and_interview(api)
    grant_consent(api, interview_id)
    question = api.get(f"/v1/interviews/{interview_id}/questions").json()[0]
    api.post(
        f"/v1/interviews/{interview_id}/answers",
        json={"question_id": question["id"], "text": "부분 답변"},
    )

    # When: Work Model build is requested too early.
    response = api.post(f"/v1/interviews/{interview_id}/build-work-model")

    # Then: the API rejects the transition.
    assert response.status_code == 409


def test_build_work_model_succeeds_after_ten_answers_and_validates_schema() -> None:
    # Given: a consented interview with all fixed questions completed.
    api = client()
    _, interview_id = create_project_and_interview(api)
    grant_consent(api, interview_id)
    answer_all_questions(api, interview_id)

    # When: the deterministic mock builder runs.
    response = api.post(f"/v1/interviews/{interview_id}/build-work-model")

    # Then: a schema-valid Work Model is stored and playback is pending.
    assert response.status_code == 200
    body = response.json()
    assert body["schema_valid"] is True
    assert body["payload"]["model_status"] == "PLAYBACK_PENDING"
    root = Path(__file__).resolve().parents[3]
    schema = json.loads(
        (root / "schemas" / "work-model-v1.schema.json").read_text(encoding="utf-8"),
    )
    Draft202012Validator(schema).validate(body["payload"])
    interview = api.get(f"/v1/interviews/{interview_id}")
    assert interview.json()["status"] == InterviewStatus.PLAYBACK_CONFIRMATION


def test_playback_confirm_finalizes_interview_and_records_audit_events() -> None:
    # Given: a playback-ready Work Model.
    api = client()
    project_id, interview_id = create_project_and_interview(api)
    grant_consent(api, interview_id)
    answer_all_questions(api, interview_id)
    api.post(f"/v1/interviews/{interview_id}/build-work-model")

    # When: playback is confirmed.
    response = api.post(f"/v1/interviews/{interview_id}/playback/confirm")

    # Then: the interview is finalized and build/confirm audits are traceable.
    assert response.status_code == 200
    assert response.json()["status"] == InterviewStatus.FINALIZED
    model = api.get(f"/v1/interviews/{interview_id}/work-model")
    assert model.json()["payload"]["model_status"] == "CONFIRMED"
    audit = api.get(f"/v1/projects/{project_id}/audit-events")
    actions = {event["action"] for event in audit.json()}
    assert AuditAction.CONSENT_GRANTED in actions
    assert AuditAction.WORK_MODEL_BUILT in actions
    assert AuditAction.PLAYBACK_CONFIRMED in actions


def test_playback_reject_returns_to_needs_evidence() -> None:
    # Given: a playback-ready Work Model.
    api = client()
    _, interview_id = create_project_and_interview(api)
    grant_consent(api, interview_id)
    answer_all_questions(api, interview_id)
    api.post(f"/v1/interviews/{interview_id}/build-work-model")

    # When: playback is rejected.
    response = api.post(f"/v1/interviews/{interview_id}/playback/reject")

    # Then: the interview returns to NEEDS_EVIDENCE.
    assert response.status_code == 200
    assert response.json()["status"] == InterviewStatus.NEEDS_EVIDENCE
    model = api.get(f"/v1/interviews/{interview_id}/work-model")
    assert model.json()["payload"]["model_status"] == "DISPUTED"


def test_revoked_consent_blocks_answers_and_build() -> None:
    # Given: a consented interview with revoked consent.
    api = client()
    _, interview_id = create_project_and_interview(api)
    grant_consent(api, interview_id)
    revoked = api.post(f"/v1/interviews/{interview_id}/consent/revoke")
    assert revoked.status_code == 200
    question = api.get(f"/v1/interviews/{interview_id}/questions").json()[0]

    # When: the user submits a new answer or requests build after revocation.
    answer = api.post(
        f"/v1/interviews/{interview_id}/answers",
        json={"question_id": question["id"], "text": "철회 후 답변"},
    )
    build = api.post(f"/v1/interviews/{interview_id}/build-work-model")

    # Then: both operations fail closed.
    assert answer.status_code == 403
    assert build.status_code == 403
