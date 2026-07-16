from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Final

import pytest
from fastapi.testclient import TestClient

from work_discovery_api.main import create_app
from work_discovery_api.models import JsonObject
from work_discovery_api.store import MemoryStore

ROOT: Final = Path(__file__).resolve().parents[3]


def confirmed_meta(source_ref: str) -> JsonObject:
    return {
        "state": "CORROBORATED",
        "confidence": 0.9,
        "source_refs": [source_ref],
        "validated_by": [],
        "last_validated_at": None,
    }


def base_payload() -> JsonObject:
    payload = json.loads(
        (ROOT / "examples" / "monthly-report-work-model.json").read_text("utf-8"),
    )
    assert isinstance(payload, dict)
    return payload


def ready_fixture() -> JsonObject:
    payload = base_payload()
    evidence = confirmed_meta("answer-001")
    exceptions = payload["exceptions"]
    assert isinstance(exceptions, list)
    for item in exceptions:
        assert isinstance(item, dict)
        item["meta"] = deepcopy(evidence)
    payload["constraints"] = [
        {
            "id": "policy-local-design-only",
            "category": "SECURITY",
            "constraint_kind": "SAFETY_POLICY",
            "statement": "설계 단계에서는 외부 시스템을 실행하거나 자격증명을 수집하지 않는다.",
            "hard": True,
            "meta": deepcopy(evidence),
        },
        {
            "id": "authority-owner-approval",
            "category": "AUTHORITY",
            "constraint_kind": "AUTHORITY_BOUNDARY",
            "statement": "업무 담당자가 예외를 판단하고 팀장이 최종 결과를 승인한다.",
            "hard": True,
            "control": "담당자 판단과 팀장 최종 승인을 자동화 경계 밖에 유지한다.",
            "residual_level": 1,
            "meta": deepcopy(evidence),
        },
    ]
    gate = payload["understanding_gate"]
    assert isinstance(gate, dict)
    gate["open_material_gaps"] = []
    gate["result"] = "READY_FOR_ANALYSIS"
    summary = payload["evidence_summary"]
    assert isinstance(summary, dict)
    summary["source_link_rate"] = 0.97
    summary["confirmed_claim_rate"] = 0.9
    summary["open_contradiction_count"] = 0
    return payload


def enable_fixture() -> JsonObject:
    payload = ready_fixture()
    constraints = payload["constraints"]
    assert isinstance(constraints, list)
    constraints.append(
        {
            "id": "risk-personal-data",
            "category": "PRIVACY",
            "constraint_kind": "INHERENT_RISK",
            "statement": "입력 파일에 개인 식별 정보가 포함될 수 있다.",
            "hard": True,
            "meta": confirmed_meta("answer-002"),
        },
    )
    return payload


def discovery_fixture() -> JsonObject:
    payload = ready_fixture()
    payload["artifacts"] = []
    payload["systems"] = []
    payload["rules"] = []
    payload["exceptions"] = []
    constraints = payload["constraints"]
    assert isinstance(constraints, list)
    payload["constraints"] = constraints[:1]
    gate = payload["understanding_gate"]
    assert isinstance(gate, dict)
    gate["epistemic_coverage"] = 0.25
    gate["operational_readiness"] = 0.2
    gate["risk_clarity"] = 0.3
    gate["open_material_gaps"] = ["입출력, 규칙, 예외와 승인 근거가 부족하다."]
    summary = payload["evidence_summary"]
    assert isinstance(summary, dict)
    summary["source_link_rate"] = 0.3
    summary["confirmed_claim_rate"] = 0.2
    return payload


def blocked_fixture() -> JsonObject:
    payload = ready_fixture()
    constraints = payload["constraints"]
    assert isinstance(constraints, list)
    for identifier, category in (("risk-regulatory", "LEGAL"), ("risk-human-safety", "SAFETY")):
        constraints.append(
            {
                "id": identifier,
                "category": category,
                "constraint_kind": "INHERENT_RISK",
                "statement": f"{category} 영향이 있으나 통제와 책임자가 확인되지 않았다.",
                "hard": True,
                "meta": confirmed_meta("answer-003"),
            },
        )
    summary = payload["evidence_summary"]
    assert isinstance(summary, dict)
    summary["confirmed_claim_rate"] = 0.45
    summary["open_contradiction_count"] = 1
    return payload


def analyze(payload: JsonObject) -> JsonObject:
    api = TestClient(create_app(MemoryStore()))
    project = api.post("/v1/projects", json={"name": "M8.1 gate calibration"})
    assert project.status_code == 201
    project_id = project.json()["id"]
    interview = api.post(f"/v1/projects/{project_id}/interviews")
    assert interview.status_code == 201
    consent = api.post(
        f"/v1/interviews/{interview.json()['id']}/consent",
        json={"ai_processing": True, "data_processing": True},
    )
    assert consent.status_code == 200
    validation = api.post(
        f"/v1/projects/{project_id}/work-model/validate",
        json={"payload": payload},
    )
    assert validation.status_code == 200
    assert validation.json()["valid"] is True
    opportunity = api.post(f"/v1/projects/{project_id}/opportunities/analyze")
    assert opportunity.status_code == 201
    body = opportunity.json()["payload"]
    assert isinstance(body, dict)
    return body


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        (ready_fixture, "READY_FOR_DESIGN"),
        (enable_fixture, "ENABLE_FIRST"),
        (discovery_fixture, "DISCOVERY_NEEDED"),
        (blocked_fixture, "BLOCKED"),
    ],
)
def test_gate_calibration_scenarios(
    fixture: Callable[[], JsonObject],
    expected: str,
) -> None:
    opportunity = analyze(fixture())
    gate = opportunity["gate"]
    assert isinstance(gate, dict)
    assert gate["result"] == expected


def test_ready_profile_excludes_safety_policy_and_reports_controls() -> None:
    opportunity = analyze(ready_fixture())
    profile = opportunity["risk_profile"]
    assert isinstance(profile, dict)
    assert profile["safety_policy_constraints"]
    assert profile["inherent_risk_constraints"] == []
    assert profile["unresolved_risk_constraints"] == []
    assert profile["unresolved_exceptions"] == []
    assert profile["controlled_exceptions"]
    assert profile["authority_boundary_confirmed"] is True
    assert profile["open_contradictions"] == 0
    residual_risk = profile["residual_risk"]
    assert isinstance(residual_risk, int)
    assert residual_risk <= 2
    scores = opportunity["scores"]
    assert isinstance(scores, dict)
    explanations = scores["score_explanation"]
    assert isinstance(explanations, list)
    assert all(isinstance(item, str) for item in explanations)
    assert any("Final gate reason" in item for item in explanations if isinstance(item, str))
