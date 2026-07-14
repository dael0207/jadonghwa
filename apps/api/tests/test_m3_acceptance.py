from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from work_discovery_api.domain import AuditAction, InterviewStatus
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


def grant_consent(api: TestClient, interview_id: str) -> None:
    response = api.post(
        f"/v1/interviews/{interview_id}/consent",
        json={"ai_processing": True, "data_processing": True},
    )
    assert response.status_code == 200


def answer_all_questions(api: TestClient, interview_id: str) -> list[str]:
    questions = api.get(f"/v1/interviews/{interview_id}/questions").json()
    answer_ids: list[str] = []
    for index, question in enumerate(questions, start=1):
        response = api.post(
            f"/v1/interviews/{interview_id}/answers",
            json={
                "question_id": question["id"],
                "text": f"{index}번 답변: 월간 보고 업무의 실제 사례와 조건입니다.",
            },
        )
        assert response.status_code == 201
        answer_ids.append(response.json()["id"])
    return answer_ids


def playback_ready_interview(api: TestClient) -> tuple[str, str, list[str]]:
    project_id, interview_id = create_project_and_interview(api)
    grant_consent(api, interview_id)
    answer_ids = answer_all_questions(api, interview_id)
    built = api.post(f"/v1/interviews/{interview_id}/build-work-model")
    assert built.status_code == 200
    return project_id, interview_id, answer_ids


def test_m3_reject_evidence_revision_rebuild_and_opportunity_draft() -> None:
    api = client()
    project_id, interview_id, answer_ids = playback_ready_interview(api)
    first_model = api.get(f"/v1/interviews/{interview_id}/work-model").json()

    rejected = api.post(f"/v1/interviews/{interview_id}/playback/reject")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == InterviewStatus.NEEDS_EVIDENCE

    evidence = api.post(
        f"/v1/interviews/{interview_id}/evidence",
        json={"text": "최근 월간 보고에서는 승인자 확인 단계가 누락되었습니다."},
    )
    assert evidence.status_code == 201
    revision = api.post(
        f"/v1/interviews/{interview_id}/answers/{answer_ids[0]}/revise",
        json={"text": "수정 답변: 첫 단계는 원본 데이터 수집이 아니라 승인자 확인입니다."},
    )
    assert revision.status_code == 200
    assert revision.json()["revision_of"] == answer_ids[0]

    answers = api.get(f"/v1/interviews/{interview_id}/answers")
    assert answers.status_code == 200
    assert len(answers.json()) == 12
    assert answers.json()[0]["text"].startswith("1번 답변")

    resumed = api.post(f"/v1/interviews/{interview_id}/resume-model-building")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == InterviewStatus.MODEL_BUILDING
    rebuilt = api.post(f"/v1/interviews/{interview_id}/build-work-model")
    assert rebuilt.status_code == 200
    assert rebuilt.json()["version"] > first_model["version"]

    history = api.get(f"/v1/projects/{project_id}/work-models")
    assert history.status_code == 200
    assert len(history.json()) >= 3

    coverage = api.get(f"/v1/interviews/{interview_id}/coverage")
    assert coverage.status_code == 200
    assert coverage.json()["covered_count"] >= 7
    next_question = api.get(f"/v1/interviews/{interview_id}/next-question")
    assert next_question.status_code == 200
    assert next_question.json()["complete"] is False
    assert next_question.json()["coverage_key"] == "tools"

    opportunity = api.get(f"/v1/interviews/{interview_id}/opportunities/draft")
    assert opportunity.status_code == 200
    assert opportunity.json()["schema_valid"] is True
    root = Path(__file__).resolve().parents[3]
    schema = json.loads(
        (root / "schemas" / "opportunity-v1.schema.json").read_text(encoding="utf-8"),
    )
    Draft202012Validator(schema).validate(opportunity.json()["payload"])

    audit = api.get(f"/v1/projects/{project_id}/audit-events")
    actions = {event["action"] for event in audit.json()}
    assert AuditAction.PLAYBACK_REJECTED in actions
    assert AuditAction.EVIDENCE_ADDED in actions
    assert AuditAction.ANSWER_REVISED in actions
    assert AuditAction.WORK_MODEL_REBUILD_REQUESTED in actions
    assert AuditAction.WORK_MODEL_REBUILT in actions
    assert AuditAction.OPPORTUNITY_DRAFT_GENERATED in actions


def test_m3_write_operations_fail_after_finalized_or_revoked_consent() -> None:
    api = client()
    _, interview_id, answer_ids = playback_ready_interview(api)
    confirmed = api.post(f"/v1/interviews/{interview_id}/playback/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == InterviewStatus.FINALIZED

    evidence_after_final = api.post(
        f"/v1/interviews/{interview_id}/evidence",
        json={"text": "finalized afterthought"},
    )
    revision_after_final = api.post(
        f"/v1/interviews/{interview_id}/answers/{answer_ids[0]}/revise",
        json={"text": "finalized revision"},
    )
    assert evidence_after_final.status_code == 409
    assert revision_after_final.status_code == 409

    _, revoked_interview_id, revoked_answer_ids = playback_ready_interview(api)
    revoke = api.post(f"/v1/interviews/{revoked_interview_id}/consent/revoke")
    assert revoke.status_code == 200
    evidence_after_revoke = api.post(
        f"/v1/interviews/{revoked_interview_id}/evidence",
        json={"text": "revoked evidence"},
    )
    revision_after_revoke = api.post(
        f"/v1/interviews/{revoked_interview_id}/answers/{revoked_answer_ids[0]}/revise",
        json={"text": "revoked revision"},
    )
    build_after_revoke = api.post(f"/v1/interviews/{revoked_interview_id}/build-work-model")
    assert evidence_after_revoke.status_code == 403
    assert revision_after_revoke.status_code == 403
    assert build_after_revoke.status_code == 403
