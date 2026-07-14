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
    first_question = questions.json()[0]["id"]

    answer = client.post(
        f"/v1/interviews/{interview_id}/answers",
        json={"question_id": first_question, "text": "월간 매출 보고서를 작성합니다."},
    )
    answer.raise_for_status()
    print("api smoke OK")


if __name__ == "__main__":
    main()
