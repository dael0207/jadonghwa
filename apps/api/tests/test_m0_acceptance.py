from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from work_discovery_api.domain import InterviewStatus
from work_discovery_api.main import create_app
from work_discovery_api.store import MemoryStore


def client() -> TestClient:
    return TestClient(create_app(MemoryStore()))


def create_project_and_interview(api: TestClient) -> tuple[str, str]:
    project_response = api.post("/v1/projects", json={"name": "Monthly report"})
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    interview_response = api.post(f"/v1/projects/{project_id}/interviews")
    assert interview_response.status_code == 201
    return project_id, interview_response.json()["id"]


def test_project_and_interview_creation_when_m0_starts() -> None:
    # Given: a local M0 API.
    api = client()

    # When: a project and interview are created.
    project_id, interview_id = create_project_and_interview(api)

    # Then: both resources are readable and the interview waits for consent.
    project_response = api.get(f"/v1/projects/{project_id}")
    assert project_response.status_code == 200
    interview_response = api.get(f"/v1/interviews/{interview_id}")
    assert interview_response.status_code == 200
    assert interview_response.json()["status"] == InterviewStatus.CONSENT_PENDING


def test_answer_is_blocked_when_consent_is_missing_or_revoked() -> None:
    # Given: an interview without consent.
    api = client()
    _, interview_id = create_project_and_interview(api)
    question_id = api.get(f"/v1/interviews/{interview_id}/questions").json()[0]["id"]

    # When: an answer is submitted before consent.
    blocked_before = api.post(
        f"/v1/interviews/{interview_id}/answers",
        json={"question_id": question_id, "text": "blocked"},
    )

    # Then: the API rejects it.
    assert blocked_before.status_code == 403

    # When: consent is granted and then revoked.
    granted = api.post(
        f"/v1/interviews/{interview_id}/consent",
        json={"ai_processing": True, "data_processing": True},
    )
    assert granted.status_code == 200
    revoked = api.post(f"/v1/interviews/{interview_id}/consent/revoke")
    assert revoked.status_code == 200

    blocked_after = api.post(
        f"/v1/interviews/{interview_id}/answers",
        json={"question_id": question_id, "text": "blocked again"},
    )

    # Then: revoked consent blocks future answers.
    assert blocked_after.status_code == 403


def test_answer_turns_are_immutable_when_revisions_are_submitted() -> None:
    # Given: a consented interview.
    api = client()
    _, interview_id = create_project_and_interview(api)
    consent = api.post(
        f"/v1/interviews/{interview_id}/consent",
        json={"ai_processing": True, "data_processing": True},
    )
    assert consent.status_code == 200
    question_id = api.get(f"/v1/interviews/{interview_id}/questions").json()[0]["id"]

    # When: the same question receives an original answer and a revision.
    first = api.post(
        f"/v1/interviews/{interview_id}/answers",
        json={"question_id": question_id, "text": "첫 답변"},
    )
    assert first.status_code == 201
    second = api.post(
        f"/v1/interviews/{interview_id}/answers",
        json={
            "question_id": question_id,
            "text": "수정 답변",
            "revision_of": first.json()["id"],
        },
    )

    # Then: the revision creates a separate turn instead of overwriting.
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["turn_id"] != second.json()["turn_id"]
    assert second.json()["revision_of"] == first.json()["id"]


def test_initial_question_loader_returns_ten_questions() -> None:
    # Given: a newly created interview.
    api = client()
    _, interview_id = create_project_and_interview(api)

    # When: questions are loaded.
    questions = api.get(f"/v1/interviews/{interview_id}/questions")

    # Then: M0 exposes the fixed ten-question intake set.
    assert questions.status_code == 200
    assert len(questions.json()) == 10


def test_ten_answers_transition_interview_to_model_building() -> None:
    # Given: a consented interview with the fixed question set.
    api = client()
    _, interview_id = create_project_and_interview(api)
    api.post(
        f"/v1/interviews/{interview_id}/consent",
        json={"ai_processing": True, "data_processing": True},
    )
    questions = api.get(f"/v1/interviews/{interview_id}/questions").json()

    # When: every fixed question receives a text answer.
    for item in questions:
        response = api.post(
            f"/v1/interviews/{interview_id}/answers",
            json={"question_id": item["id"], "text": "답변입니다."},
        )
        assert response.status_code == 201

    # Then: the interview reaches MODEL_BUILDING.
    interview = api.get(f"/v1/interviews/{interview_id}")
    assert interview.status_code == 200
    assert interview.json()["status"] == InterviewStatus.MODEL_BUILDING


def test_invalid_state_transition_fails_when_consent_is_repeated() -> None:
    # Given: an already consented interview.
    api = client()
    _, interview_id = create_project_and_interview(api)
    first = api.post(
        f"/v1/interviews/{interview_id}/consent",
        json={"ai_processing": True, "data_processing": True},
    )
    assert first.status_code == 200

    # When: consent is granted again from INTAKE_IN_PROGRESS.
    second = api.post(
        f"/v1/interviews/{interview_id}/consent",
        json={"ai_processing": True, "data_processing": True},
    )

    # Then: the invalid state transition is rejected.
    assert second.status_code == 409


def test_work_model_validation_accepts_monthly_report_example() -> None:
    # Given: a project and the checked-in monthly work model example.
    api = client()
    project_id, _ = create_project_and_interview(api)
    root = Path(__file__).resolve().parents[3]
    payload = json.loads(
        (root / "examples" / "monthly-report-work-model.json").read_text(encoding="utf-8"),
    )

    # When: the work model validation endpoint is called.
    response = api.post(f"/v1/projects/{project_id}/work-model/validate", json={"payload": payload})

    # Then: the schema validation succeeds.
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_checked_in_examples_match_their_schemas() -> None:
    # Given: the repository schemas and example payloads.
    root = Path(__file__).resolve().parents[3]
    pairs = (
        ("schemas/work-model-v1.schema.json", "examples/monthly-report-work-model.json"),
        ("schemas/interview-state-v1.schema.json", "examples/monthly-report-interview-state.json"),
        ("schemas/opportunity-v1.schema.json", "examples/monthly-report-opportunity.json"),
    )

    # When / Then: every example validates against its corresponding schema.
    for schema_path, example_path in pairs:
        schema = json.loads((root / schema_path).read_text(encoding="utf-8"))
        payload = json.loads((root / example_path).read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)
