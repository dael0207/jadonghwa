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

    guidance = client.get(f"/v1/projects/{project_id}/discovery-guidance")
    guidance.raise_for_status()
    assert guidance.json()["recovery_required"] is True
    assert guidance.json()["missing_dimensions"]
    assert guidance.json()["recommended_questions"]
    reopened = client.post(f"/v1/projects/{project_id}/discovery/reopen")
    reopened.raise_for_status()
    assert reopened.json()["status"] == "NEEDS_EVIDENCE"
    recovery_evidence = client.post(
        f"/v1/interviews/{interview_id}/evidence",
        json={
            "text": (
                "시스템/도구: ERP, CRM, Excel, PowerPoint\n"
                "입력: ERP 매출 CSV, CRM 활동 Excel\n"
                "출력: 월간 실적 보고서 PPT, 검증 완료 Excel\n"
                "규칙/판단 기준: ERP 총액과 일치해야 하고 10% 이상 차이는 확인한다\n"
                "예외/복구: 파일 누락은 담당자 확인 후 수동으로 다시 반영한다\n"
                "승인/권한: 팀장이 최종 보고서를 승인한다\n"
                "성과지표: 월 1회, 작성 4시간, 오류율 5% 이하\n"
                "비범위: ERP 원본 수정, 결재 승인, 이메일 발송\n"
                "근거: 실제 보고서 샘플과 검증 체크리스트"
            ),
        },
    )
    recovery_evidence.raise_for_status()
    recovery_resume = client.post(f"/v1/interviews/{interview_id}/resume-model-building")
    recovery_resume.raise_for_status()
    recovery_model = client.post(f"/v1/interviews/{interview_id}/build-work-model")
    recovery_model.raise_for_status()
    recovery_confirm = client.post(f"/v1/interviews/{interview_id}/playback/confirm")
    recovery_confirm.raise_for_status()
    reanalyzed = client.post(f"/v1/projects/{project_id}/discovery/reanalyze")
    reanalyzed.raise_for_status()
    assert reanalyzed.json()["work_model_version"] > analyzed.json()["work_model_version"]
    recovered_readiness = client.get(f"/v1/projects/{project_id}/readiness")
    recovered_readiness.raise_for_status()
    assert recovered_readiness.json()["result"] == "READY_FOR_DESIGN"

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
    assert "DISCOVERY_REOPENED" in actions
    assert "DISCOVERY_REANALYZED" in actions

    design_package = client.post(
        f"/v1/opportunities/{reanalyzed.json()['id']}/design-package",
    )
    design_package.raise_for_status()
    assert design_package.json()["schema_valid"] is True
    assert design_package.json()["payload"]["package_type"] == "FULL_G1"
    package_validation = client.post(
        f"/v1/design-packages/{design_package.json()['id']}/validate",
    )
    package_validation.raise_for_status()
    assert package_validation.json()["valid"] is True
    packages = client.get(f"/v1/projects/{project_id}/design-packages")
    packages.raise_for_status()
    assert len(packages.json()) == 1
    blueprint = client.post(f"/v1/design-packages/{design_package.json()['id']}/blueprint")
    blueprint.raise_for_status()
    assert blueprint.json()["schema_valid"] is True
    assert blueprint.json()["export_ready"] is True
    assert blueprint.json()["payload"]["blueprint_type"] == "FULL_G1_BLUEPRINT"
    blueprint_validation = client.post(
        f"/v1/blueprints/{blueprint.json()['id']}/validate",
    )
    blueprint_validation.raise_for_status()
    assert blueprint_validation.json()["valid"] is True
    blueprint_json = client.get(f"/v1/blueprints/{blueprint.json()['id']}/export/json")
    blueprint_json.raise_for_status()
    blueprint_markdown = client.get(f"/v1/blueprints/{blueprint.json()['id']}/export/markdown")
    blueprint_markdown.raise_for_status()
    assert "G1 Solution Blueprint" in blueprint_markdown.text
    evaluation = client.post(f"/v1/projects/{project_id}/evaluation-runs")
    evaluation.raise_for_status()
    assert evaluation.json()["schema_valid"] is True
    assert evaluation.json()["payload"]["item_count"] == 24
    assert evaluation.json()["payload"]["score_summary"]["overall_passed"] is True
    evaluation_validation = client.post(
        f"/v1/evaluation-runs/{evaluation.json()['id']}/validate",
    )
    evaluation_validation.raise_for_status()
    release = client.post(f"/v1/projects/{project_id}/release-readiness")
    release.raise_for_status()
    assert release.json()["schema_valid"] is True
    assert release.json()["payload"]["readiness_status"] == "READY"
    release_validation = client.post(
        f"/v1/release-readiness/{release.json()['id']}/validate",
    )
    release_validation.raise_for_status()
    assert release_validation.json()["valid"] is True

    print("api smoke OK")


if __name__ == "__main__":
    main()
