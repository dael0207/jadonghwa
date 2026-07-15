from __future__ import annotations

from fastapi.testclient import TestClient

from work_discovery_api.main import create_app
from work_discovery_api.store import MemoryStore


def main() -> None:
    client = TestClient(create_app(MemoryStore()))
    project_response = client.post("/v1/projects", json={"name": "Monthly report"})
    project_response.raise_for_status()
    project_id = project_response.json()["id"]

    interview_response = client.post(f"/v1/projects/{project_id}/interviews")
    interview_response.raise_for_status()
    interview_id = interview_response.json()["id"]

    blocked = client.post(
        f"/v1/interviews/{interview_id}/answers",
        json={"question_id": "missing", "text": "blocked"},
    )
    assert blocked.status_code == 403

    consent = client.post(
        f"/v1/interviews/{interview_id}/consent",
        json={"ai_processing": True, "data_processing": True},
    )
    consent.raise_for_status()

    questions = client.get(f"/v1/interviews/{interview_id}/questions")
    questions.raise_for_status()
    question_ids = [item["id"] for item in questions.json()]

    early_build = client.post(f"/v1/interviews/{interview_id}/build-work-model")
    assert early_build.status_code == 409

    answer_ids: list[str] = []
    for index, question_id in enumerate(question_ids, start=1):
        answer = client.post(
            f"/v1/interviews/{interview_id}/answers",
            json={"question_id": question_id, "text": f"{index}번 질문에 답합니다."},
        )
        answer.raise_for_status()
        answer_ids.append(answer.json()["id"])

    model = client.post(f"/v1/interviews/{interview_id}/build-work-model")
    model.raise_for_status()
    assert model.json()["schema_valid"] is True

    rejected = client.post(f"/v1/interviews/{interview_id}/playback/reject")
    rejected.raise_for_status()
    assert rejected.json()["status"] == "NEEDS_EVIDENCE"

    evidence = client.post(
        f"/v1/interviews/{interview_id}/evidence",
        json={"text": "누락된 증거를 추가합니다."},
    )
    evidence.raise_for_status()
    revision = client.post(
        f"/v1/interviews/{interview_id}/answers/{answer_ids[0]}/revise",
        json={"text": "수정 답변을 새 turn으로 추가합니다."},
    )
    revision.raise_for_status()
    resumed = client.post(f"/v1/interviews/{interview_id}/resume-model-building")
    resumed.raise_for_status()
    rebuilt = client.post(f"/v1/interviews/{interview_id}/build-work-model")
    rebuilt.raise_for_status()
    assert rebuilt.json()["schema_valid"] is True
    coverage = client.get(f"/v1/interviews/{interview_id}/coverage")
    coverage.raise_for_status()
    next_question = client.get(f"/v1/interviews/{interview_id}/next-question")
    next_question.raise_for_status()
    opportunity = client.get(f"/v1/interviews/{interview_id}/opportunities/draft")
    opportunity.raise_for_status()
    assert opportunity.json()["schema_valid"] is True
    analyzed = client.post(f"/v1/projects/{project_id}/opportunities/analyze")
    analyzed.raise_for_status()
    assert analyzed.json()["schema_valid"] is True
    readiness = client.get(f"/v1/projects/{project_id}/readiness")
    readiness.raise_for_status()
    assert readiness.json()["result"] in {
        "BLOCKED",
        "DISCOVERY_NEEDED",
        "ENABLE_FIRST",
        "READY_FOR_DESIGN",
    }
    validation = client.post(
        f"/v1/opportunities/{analyzed.json()['id']}/validate",
        json={"accepted": True, "notes": "smoke"},
    )
    validation.raise_for_status()
    assert validation.json()["valid"] is True
    diff = client.get(f"/v1/projects/{project_id}/opportunities/diff")
    diff.raise_for_status()
    assert diff.json()["latest_opportunity_id"] == analyzed.json()["id"]

    confirmed = client.post(f"/v1/interviews/{interview_id}/playback/confirm")
    confirmed.raise_for_status()
    assert confirmed.json()["status"] == "FINALIZED"

    audit = client.get(f"/v1/projects/{project_id}/audit-events")
    audit.raise_for_status()
    actions = {event["action"] for event in audit.json()}
    assert "WORK_MODEL_REBUILT" in actions
    assert "PLAYBACK_CONFIRMED" in actions
    assert "OPPORTUNITY_DRAFT_GENERATED" in actions
    assert "OPPORTUNITY_ANALYZED" in actions
    assert "OPPORTUNITY_VALIDATED" in actions
    assert "READINESS_EVALUATED" in actions
    assert "OPPORTUNITY_DIFF_GENERATED" in actions
    print("api smoke OK")


if __name__ == "__main__":
    main()
