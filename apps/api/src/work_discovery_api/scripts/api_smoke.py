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

    for index, question_id in enumerate(question_ids, start=1):
        answer = client.post(
            f"/v1/interviews/{interview_id}/answers",
            json={"question_id": question_id, "text": f"{index}번 질문에 답합니다."},
        )
        answer.raise_for_status()

    model = client.post(f"/v1/interviews/{interview_id}/build-work-model")
    model.raise_for_status()
    assert model.json()["schema_valid"] is True

    confirmed = client.post(f"/v1/interviews/{interview_id}/playback/confirm")
    confirmed.raise_for_status()
    assert confirmed.json()["status"] == "FINALIZED"

    audit = client.get(f"/v1/projects/{project_id}/audit-events")
    audit.raise_for_status()
    actions = {event["action"] for event in audit.json()}
    assert "WORK_MODEL_BUILT" in actions
    assert "PLAYBACK_CONFIRMED" in actions
    print("api smoke OK")


if __name__ == "__main__":
    main()
