from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from work_discovery_api.domain import AuditAction, InterviewStatus, InvalidTransitionError
from work_discovery_api.main import create_app
from work_discovery_api.store import MemoryStore

ROOT = Path(__file__).resolve().parents[3]


def create_flow(api: TestClient) -> tuple[str, str]:
    project = api.post("/v1/projects", json={"name": "Monthly report"})
    assert project.status_code == 201
    project_id = project.json()["id"]
    interview = api.post(f"/v1/projects/{project_id}/interviews")
    assert interview.status_code == 201
    interview_id = interview.json()["id"]
    consent = api.post(
        f"/v1/interviews/{interview_id}/consent",
        json={"ai_processing": True, "data_processing": True},
    )
    assert consent.status_code == 200
    return project_id, interview_id


def complete_initial_playback(api: TestClient, interview_id: str) -> None:
    questions = api.get(f"/v1/interviews/{interview_id}/questions")
    assert questions.status_code == 200
    for index, question in enumerate(questions.json(), start=1):
        answer = api.post(
            f"/v1/interviews/{interview_id}/answers",
            json={
                "question_id": question["id"],
                "text": f"{index}번 월간 보고 업무 답변입니다.",
            },
        )
        assert answer.status_code == 201
    built = api.post(f"/v1/interviews/{interview_id}/build-work-model")
    assert built.status_code == 200
    confirmed = api.post(f"/v1/interviews/{interview_id}/playback/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == InterviewStatus.FINALIZED


def recovery_evidence() -> str:
    return (
        "시스템/도구: ERP, CRM, Excel, PowerPoint\n"
        "입력: ERP 매출 CSV, CRM 활동 Excel\n"
        "출력: 월간 실적 보고서 PPT, 검증 완료 Excel\n"
        "규칙/판단 기준: 고객별 합계가 ERP 총액과 일치해야 하고 10% 이상 차이는 확인한다\n"
        "예외/복구: 파일 누락이나 값 오류는 담당자 확인 후 수동으로 다시 반영한다\n"
        "승인/권한: 팀장이 최종 보고서를 승인하고 담당자가 예외를 판단한다\n"
        "성과지표: 월 1회, 작성 4시간, 오류율 5% 이하\n"
        "비범위: ERP 원본 수정, 결재 승인, 이메일 발송\n"
        "근거: 실제 월간 보고서 샘플과 검증 체크리스트"
    )


def test_recovery_loop_appends_opportunity_after_confirmed_rebuild() -> None:
    # Given: a finalized interview whose first opportunity needs more discovery.
    store = MemoryStore()
    api = TestClient(create_app(store))
    project_id, interview_id = create_flow(api)
    complete_initial_playback(api, interview_id)
    first = api.post(f"/v1/projects/{project_id}/opportunities/analyze")
    assert first.status_code == 201
    first_opportunity = first.json()
    readiness = api.get(f"/v1/projects/{project_id}/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["result"] in {"BLOCKED", "DISCOVERY_NEEDED"}
    blocked_package = api.post(
        f"/v1/opportunities/{first_opportunity['id']}/design-package",
    )
    assert blocked_package.status_code == 409
    with pytest.raises(InvalidTransitionError):
        store.transition_interview(interview_id, InterviewStatus.NEEDS_EVIDENCE)

    # When: recovery guidance is followed through evidence, rebuild, playback, and reanalysis.
    guidance = api.get(f"/v1/projects/{project_id}/discovery-guidance")
    assert guidance.status_code == 200
    guidance_body = guidance.json()
    assert guidance_body["recovery_required"] is True
    assert guidance_body["missing_dimensions"]
    assert guidance_body["recommended_questions"]
    assert {item["key"] for item in guidance_body["missing_dimensions"]} == {
        "INPUT_OUTPUT",
        "TOOLS",
        "RULE",
        "EXCEPTION",
        "AUTHORITY",
        "METRIC",
        "SCOPE",
        "EVIDENCE",
    }
    assert guidance_body["can_reopen"] is True

    reopened = api.post(f"/v1/projects/{project_id}/discovery/reopen")
    assert reopened.status_code == 200
    assert reopened.json()["status"] == InterviewStatus.NEEDS_EVIDENCE
    evidence = api.post(
        f"/v1/interviews/{interview_id}/evidence",
        json={"text": recovery_evidence()},
    )
    assert evidence.status_code == 201
    resumed = api.post(f"/v1/interviews/{interview_id}/resume-model-building")
    assert resumed.status_code == 200
    rebuilt = api.post(f"/v1/interviews/{interview_id}/build-work-model")
    assert rebuilt.status_code == 200
    assert rebuilt.json()["payload"]["rules"]
    assert rebuilt.json()["payload"]["exceptions"]
    reconfirmed = api.post(f"/v1/interviews/{interview_id}/playback/confirm")
    assert reconfirmed.status_code == 200

    second = api.post(f"/v1/projects/{project_id}/discovery/reanalyze")

    # Then: a newer opportunity is appended and the audit trail preserves both recovery events.
    assert second.status_code == 201
    second_opportunity = second.json()
    assert second_opportunity["id"] != first_opportunity["id"]
    assert second_opportunity["work_model_version"] > first_opportunity["work_model_version"]
    opportunities = api.get(f"/v1/projects/{project_id}/opportunities")
    assert opportunities.status_code == 200
    assert len(opportunities.json()) == 2
    next_readiness = api.get(f"/v1/projects/{project_id}/readiness")
    assert next_readiness.json()["result"] == "READY_FOR_DESIGN"

    design_package = api.post(
        f"/v1/opportunities/{second_opportunity['id']}/design-package",
    )
    assert design_package.status_code == 201
    package_body = design_package.json()
    assert package_body["payload"]["package_type"] == "FULL_G1"
    blueprint = api.post(f"/v1/design-packages/{package_body['id']}/blueprint")
    assert blueprint.status_code == 201
    blueprint_body = blueprint.json()
    assert blueprint_body["payload"]["blueprint_type"] == "FULL_G1_BLUEPRINT"
    assert blueprint_body["export_ready"] is True
    assert api.get(f"/v1/blueprints/{blueprint_body['id']}/export/json").status_code == 200
    markdown = api.get(f"/v1/blueprints/{blueprint_body['id']}/export/markdown")
    assert markdown.status_code == 200
    assert "G1 Solution Blueprint" in markdown.text

    evaluation = api.post(f"/v1/projects/{project_id}/evaluation-runs")
    assert evaluation.status_code == 201
    criteria = evaluation.json()["payload"]["criteria_results"]
    blueprint_criterion = next(item for item in criteria if item["key"] == "blueprint-completeness")
    assert blueprint_criterion["passed"] is True
    release = api.post(f"/v1/projects/{project_id}/release-readiness")
    assert release.status_code == 201
    release_body = release.json()["payload"]
    assert release_body["readiness_status"] == "READY"
    export_check = next(
        item for item in release_body["checklist"] if item["key"] == "export-readiness"
    )
    assert export_check["status"] == "PASS"
    audit = api.get(f"/v1/projects/{project_id}/audit-events")
    actions = {event["action"] for event in audit.json()}
    assert AuditAction.DISCOVERY_REOPENED in actions
    assert AuditAction.DISCOVERY_REANALYZED in actions


def test_guidance_is_not_required_when_ready_for_design() -> None:
    # Given: a schema-valid rich model that reaches READY_FOR_DESIGN.
    api = TestClient(create_app(MemoryStore()))
    project_id, _interview_id = create_flow(api)
    payload = json.loads((ROOT / "examples" / "monthly-report-work-model.json").read_text("utf-8"))
    for item in payload["exceptions"]:
        item["meta"]["state"] = "CORROBORATED"
        item["meta"]["confidence"] = 0.9
    payload["understanding_gate"]["open_material_gaps"] = []
    payload["understanding_gate"]["result"] = "READY_FOR_ANALYSIS"
    validated = api.post(
        f"/v1/projects/{project_id}/work-model/validate",
        json={"payload": payload},
    )
    assert validated.status_code == 200
    analyzed = api.post(f"/v1/projects/{project_id}/opportunities/analyze")
    assert analyzed.status_code == 201
    readiness = api.get(f"/v1/projects/{project_id}/readiness")
    assert readiness.json()["result"] == "READY_FOR_DESIGN"

    # When: discovery guidance is requested.
    guidance = api.get(f"/v1/projects/{project_id}/discovery-guidance")

    # Then: it explicitly reports that no recovery is required.
    assert guidance.status_code == 200
    assert guidance.json()["recovery_required"] is False
    assert guidance.json()["missing_dimensions"] == []
    assert guidance.json()["recommended_questions"] == []


def test_blocked_gate_uses_the_same_recovery_contract() -> None:
    # Given: a valid opportunity whose latest gate is explicitly BLOCKED.
    store = MemoryStore()
    api = TestClient(create_app(store))
    project_id, interview_id = create_flow(api)
    complete_initial_playback(api, interview_id)
    analyzed = api.post(f"/v1/projects/{project_id}/opportunities/analyze")
    assert analyzed.status_code == 201
    blocked_payload = analyzed.json()["payload"]
    blocked_payload["gate"] = {
        "result": "BLOCKED",
        "blocked_reasons": ["Authority boundary must be resolved"],
    }
    store.save_opportunity(
        project_id,
        analyzed.json()["work_model_version"],
        blocked_payload,
        valid=True,
    )

    # When: guidance and recovery reopen are requested.
    guidance = api.get(f"/v1/projects/{project_id}/discovery-guidance")
    reopened = api.post(f"/v1/projects/{project_id}/discovery/reopen")

    # Then: BLOCKED follows the same evidence recovery gate as DISCOVERY_NEEDED.
    assert guidance.status_code == 200
    assert guidance.json()["gate_result"] == "BLOCKED"
    assert guidance.json()["recovery_required"] is True
    assert guidance.json()["can_reopen"] is True
    assert reopened.status_code == 200
    assert reopened.json()["status"] == InterviewStatus.NEEDS_EVIDENCE


def test_reopen_rejects_revoked_and_deletion_pending_interviews() -> None:
    # Given: a project whose latest interview has revoked consent.
    store = MemoryStore()
    api = TestClient(create_app(store))
    project_id, interview_id = create_flow(api)
    revoked = api.post(f"/v1/interviews/{interview_id}/consent/revoke")
    assert revoked.status_code == 200

    # When/Then: recovery cannot reopen a consent-revoked interview.
    blocked_revoked = api.post(f"/v1/projects/{project_id}/discovery/reopen")
    assert blocked_revoked.status_code == 409

    # Given: the same interview advances to deletion pending.
    store.transition_interview(interview_id, InterviewStatus.DELETION_PENDING)

    # When/Then: recovery remains blocked while deletion is pending.
    blocked_deletion = api.post(f"/v1/projects/{project_id}/discovery/reopen")
    assert blocked_deletion.status_code == 409

    # Given: a separate interview is aborted before consent.
    aborted_store = MemoryStore()
    aborted_api = TestClient(create_app(aborted_store))
    aborted_project = aborted_api.post("/v1/projects", json={"name": "Aborted recovery"})
    aborted_project_id = aborted_project.json()["id"]
    aborted_interview = aborted_api.post(
        f"/v1/projects/{aborted_project_id}/interviews",
    )
    aborted_interview_id = aborted_interview.json()["id"]
    aborted_store.transition_interview(aborted_interview_id, InterviewStatus.ABORTED)

    # When/Then: recovery cannot reopen an aborted interview.
    blocked_aborted = aborted_api.post(
        f"/v1/projects/{aborted_project_id}/discovery/reopen",
    )
    assert blocked_aborted.status_code == 409
