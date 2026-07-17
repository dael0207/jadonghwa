from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from work_discovery_api.domain import AuditAction
from work_discovery_api.main import create_app
from work_discovery_api.scripts.blind_build_smoke import run_blind_build
from work_discovery_api.store import MemoryStore

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class EvidenceFixture:
    role: str
    filename: str
    content_type: str
    content: bytes


def client() -> TestClient:
    return TestClient(create_app(MemoryStore()))


def schema(name: str) -> dict[str, object]:
    return json.loads((ROOT / "schemas" / name).read_text("utf-8"))


def ready_work_model_payload() -> dict[str, object]:
    payload = json.loads(
        (ROOT / "examples" / "monthly-report-work-model.json").read_text("utf-8"),
    )
    exceptions = payload["exceptions"]
    assert isinstance(exceptions, list)
    for item in exceptions:
        assert isinstance(item, dict)
        meta = item["meta"]
        assert isinstance(meta, dict)
        meta["state"] = "CORROBORATED"
        meta["confidence"] = 0.9
    gate = payload["understanding_gate"]
    assert isinstance(gate, dict)
    gate["open_material_gaps"] = []
    gate["result"] = "READY_FOR_ANALYSIS"
    return payload


def full_blueprint_project(api: TestClient) -> str:
    project = api.post("/v1/projects", json={"name": "M9 monthly report"})
    assert project.status_code == 201
    project_id = project.json()["id"]
    validated = api.post(
        f"/v1/projects/{project_id}/work-model/validate",
        json={"payload": ready_work_model_payload()},
    )
    assert validated.status_code == 200
    opportunity = api.post(f"/v1/projects/{project_id}/opportunities/analyze")
    assert opportunity.status_code == 201
    package = api.post(
        f"/v1/opportunities/{opportunity.json()['id']}/design-package",
    )
    assert package.status_code == 201
    blueprint = api.post(f"/v1/design-packages/{package.json()['id']}/blueprint")
    assert blueprint.status_code == 201
    assert blueprint.json()["export_ready"] is True
    return project_id


def upload_and_confirm(
    api: TestClient,
    project_id: str,
    fixture: EvidenceFixture,
) -> dict[str, object]:
    uploaded = api.post(
        f"/v1/projects/{project_id}/evidence-files",
        json={
            "role": fixture.role,
            "filename": fixture.filename,
            "content_type": fixture.content_type,
            "content_base64": base64.b64encode(fixture.content).decode("ascii"),
        },
    )
    assert uploaded.status_code == 201
    confirmed = api.post(
        f"/v1/evidence-files/{uploaded.json()['id']}/confirm",
        json={"confirmed": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["confirmed"] is True
    return confirmed.json()


def monthly_acceptance_evidence(
    api: TestClient,
    project_id: str,
) -> dict[str, tuple[dict[str, object], dict[str, object]]]:
    fixture_names = {
        "NORMAL": ("monthly-report-input.csv", "monthly-report-expected.json"),
        "ERROR": (
            "monthly-report-missing-column.csv",
            "monthly-report-missing-column-expected.json",
        ),
        "EXCEPTION": (
            "monthly-report-invalid-amount.csv",
            "monthly-report-invalid-amount-expected.json",
        ),
        "APPROVAL_REQUIRED": (
            "monthly-report-approval.csv",
            "monthly-report-approval-expected.json",
        ),
    }
    result: dict[str, tuple[dict[str, object], dict[str, object]]] = {}
    for kind, (input_name, expected_name) in fixture_names.items():
        input_file = upload_and_confirm(
            api,
            project_id,
            EvidenceFixture(
                role="INPUT",
                filename=input_name,
                content_type="text/csv",
                content=(ROOT / "examples" / "m9" / input_name).read_bytes(),
            ),
        )
        expected_file = upload_and_confirm(
            api,
            project_id,
            EvidenceFixture(
                role="EXPECTED_OUTPUT",
                filename=expected_name,
                content_type="application/json",
                content=(ROOT / "examples" / "m9" / expected_name).read_bytes(),
            ),
        )
        result[kind] = input_file, expected_file
    return result


def minimal_xlsx_bytes() -> bytes:
    worksheet = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row>
      <c t="inlineStr"><is><t>customer</t></is></c>
      <c t="inlineStr"><is><t>amount</t></is></c>
    </row>
    <row>
      <c t="inlineStr"><is><t>Acme</t></is></c>
      <c><v>100</v></c>
    </row>
  </sheetData>
</worksheet>
"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    return buffer.getvalue()


def test_m9_codegen_gate_blocks_then_allows_complete_contract(tmp_path: Path) -> None:
    api = client()
    project_id = full_blueprint_project(api)

    draft = api.post(f"/v1/projects/{project_id}/implementation-packages")

    assert draft.status_code == 201
    assert draft.json()["readiness_status"] == "DESIGN_READY"
    readiness = api.get(
        f"/v1/implementation-packages/{draft.json()['id']}/codegen-readiness",
    )
    assert readiness.status_code == 200
    assert readiness.json()["codegen_ready"] is False
    assert readiness.json()["blockers"]
    assert readiness.json()["follow_up_questions"]
    blocked_export = api.get(
        f"/v1/implementation-packages/{draft.json()['id']}/export.zip",
    )
    assert blocked_export.status_code == 409
    draft_export = api.get(
        f"/v1/implementation-packages/{draft.json()['id']}/export.zip?mode=draft",
    )
    assert draft_export.status_code == 200

    evidence_by_kind = monthly_acceptance_evidence(api, project_id)
    requirements = json.loads(
        (ROOT / "examples" / "m9" / "monthly-report-implementation-requirements.json").read_text(
            "utf-8",
        ),
    )
    for case in requirements["acceptance_cases"]:
        input_file, expected_file = evidence_by_kind[case["kind"]]
        case["input_file_refs"] = [input_file["id"]]
        case["expected_file_refs"] = [expected_file["id"]]
    recorded = api.post(
        f"/v1/projects/{project_id}/implementation-requirements",
        json={"payload": requirements, "confirmed": True},
    )
    assert recorded.status_code == 201

    created = api.post(f"/v1/projects/{project_id}/implementation-packages")

    assert created.status_code == 201
    package = created.json()
    assert package["readiness_status"] == "CODEGEN_READY"
    assert package["schema_valid"] is True
    Draft202012Validator(schema("implementation-package-v1.schema.json")).validate(
        package["payload"],
    )
    validation = api.post(f"/v1/implementation-packages/{package['id']}/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True
    readiness = api.get(
        f"/v1/implementation-packages/{package['id']}/codegen-readiness",
    )
    assert readiness.status_code == 200
    assert readiness.json()["codegen_ready"] is True
    Draft202012Validator(schema("codegen-readiness-v1.schema.json")).validate(
        readiness.json(),
    )

    exported = api.get(f"/v1/implementation-packages/{package['id']}/export.zip")

    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        names = set(archive.namelist())
        required_files = {
            "manifest.json",
            "README.md",
            "source/work-model.json",
            "source/opportunity.json",
            "source/design-package.json",
            "source/blueprint.json",
            "contracts/workflow.json",
            "contracts/integrations.json",
            "contracts/input.schema.json",
            "contracts/output.schema.json",
            "contracts/mappings.json",
            "contracts/decisions.json",
            "contracts/exceptions.json",
            "contracts/approvals.json",
            "implementation/stack.json",
            "implementation/architecture.md",
            "implementation/modules.json",
            "implementation/env.example",
            "implementation/deployment.md",
            "tests/acceptance-tests.json",
            "traceability/evidence-map.json",
        }
        assert required_files <= names
        manifest = json.loads(archive.read("manifest.json"))
        Draft202012Validator(schema("export-manifest-v1.schema.json")).validate(manifest)
        Draft202012Validator(schema("work-model-v1.schema.json")).validate(
            json.loads(archive.read("source/work-model.json")),
        )
        Draft202012Validator(schema("opportunity-v1.schema.json")).validate(
            json.loads(archive.read("source/opportunity.json")),
        )
        Draft202012Validator(schema("design-package-v1.schema.json")).validate(
            json.loads(archive.read("source/design-package.json")),
        )
        Draft202012Validator(schema("blueprint-v1.schema.json")).validate(
            json.loads(archive.read("source/blueprint.json")),
        )
        Draft202012Validator(schema("automation-workflow-v1.schema.json")).validate(
            json.loads(archive.read("contracts/workflow.json")),
        )
        integration_validator = Draft202012Validator(
            schema("integration-contract-v1.schema.json"),
        )
        for integration in json.loads(archive.read("contracts/integrations.json")):
            integration_validator.validate(integration)
        fixture_validator = Draft202012Validator(schema("acceptance-fixture-v1.schema.json"))
        for fixture in json.loads(archive.read("tests/acceptance-tests.json")):
            fixture_validator.validate(fixture)
        manifest_paths = {item["path"] for item in manifest["files"]}
        assert manifest_paths == names - {"manifest.json"}
        for item in manifest["files"]:
            content = archive.read(item["path"])
            assert hashlib.sha256(content).hexdigest() == item["sha256"]
            assert len(content) == item["size_bytes"]
        assert len([name for name in names if name.startswith("tests/fixtures/input/")]) == 4
        assert len([name for name in names if name.startswith("tests/fixtures/expected/")]) == 4
        evidence_map = json.loads(archive.read("traceability/evidence-map.json"))
        assert all(item["target_path"] in names for item in evidence_map["entries"])
        for name in names:
            assert not name.startswith("/")
            assert ".." not in Path(name).parts
            if name.endswith((".json", ".md", ".example")):
                text = archive.read(name).decode("utf-8")
                assert "C:\\" not in text
                assert "/Users/" not in text

    archive_path = tmp_path / "implementation-package.zip"
    archive_path.write_bytes(exported.content)
    blind_build = run_blind_build(archive_path)
    assert blind_build.passed is True
    assert blind_build.cases_executed == 4
    assert blind_build.actual == {
        "approval_required": False,
        "record_count": 2,
        "total_amount": 300.0,
    }

    packages = api.get(f"/v1/projects/{project_id}/implementation-packages")
    assert packages.status_code == 200
    assert len(packages.json()) == 2
    actions = {
        AuditAction(event["action"])
        for event in api.get(f"/v1/projects/{project_id}/audit-events").json()
    }
    assert AuditAction.EVIDENCE_FILE_UPLOADED in actions
    assert AuditAction.EVIDENCE_FILE_CONFIRMED in actions
    assert AuditAction.IMPLEMENTATION_PACKAGE_CREATED in actions
    assert AuditAction.IMPLEMENTATION_PACKAGE_VALIDATED in actions
    assert AuditAction.IMPLEMENTATION_PACKAGE_EXPORTED in actions


def test_m9_rejects_unknown_critical_values_and_unsafe_files() -> None:
    api = client()
    project_id = full_blueprint_project(api)
    requirements = {
        "target_runtime": "UNKNOWN",
        "framework": "UNKNOWN",
        "package_manager": "UNKNOWN",
    }
    recorded = api.post(
        f"/v1/projects/{project_id}/implementation-requirements",
        json={"payload": requirements, "confirmed": True},
    )
    assert recorded.status_code == 201
    package = api.post(f"/v1/projects/{project_id}/implementation-packages")
    assert package.status_code == 201
    assert package.json()["readiness_status"] != "CODEGEN_READY"
    assert any(
        "UNKNOWN" in blocker
        for blocker in package.json()["payload"]["codegen_readiness"]["blockers"]
    )

    executable = api.post(
        f"/v1/projects/{project_id}/evidence-files",
        json={
            "role": "INPUT",
            "filename": "run.exe",
            "content_type": "application/octet-stream",
            "content_base64": base64.b64encode(b"MZ").decode("ascii"),
        },
    )
    assert executable.status_code == 415

    absolute_path = api.post(
        f"/v1/projects/{project_id}/evidence-files",
        json={
            "role": "INPUT",
            "filename": "absolute-path.json",
            "content_type": "application/json",
            "content_base64": base64.b64encode(
                b'{"source": "/Users/operator/private.csv"}',
            ).decode("ascii"),
        },
    )
    assert absolute_path.status_code == 415

    nested_secret = api.post(
        f"/v1/projects/{project_id}/evidence-files",
        json={
            "role": "INPUT",
            "filename": "secret-field.json",
            "content_type": "application/json",
            "content_base64": base64.b64encode(
                b'{"connection": {"api_key": "not-allowed"}}',
            ).decode("ascii"),
        },
    )
    assert nested_secret.status_code == 415

    xlsx = api.post(
        f"/v1/projects/{project_id}/evidence-files",
        json={
            "role": "INPUT",
            "filename": "monthly-report.xlsx",
            "content_type": (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            "content_base64": base64.b64encode(minimal_xlsx_bytes()).decode("ascii"),
        },
    )
    assert xlsx.status_code == 201
    assert xlsx.json()["sample_values"]["format"] == "XLSX"
    assert set(xlsx.json()["extracted_schema"]["items"]["properties"]) == {
        "customer",
        "amount",
    }


def test_m9_codegen_gate_rejects_workflow_cycle() -> None:
    api = client()
    project_id = full_blueprint_project(api)
    requirements = json.loads(
        (ROOT / "examples" / "m9" / "monthly-report-implementation-requirements.json").read_text(
            "utf-8",
        ),
    )
    requirements["workflow"]["steps"][0]["depends_on"] = ["write-output"]
    recorded = api.post(
        f"/v1/projects/{project_id}/implementation-requirements",
        json={"payload": requirements, "confirmed": True},
    )
    assert recorded.status_code == 201

    package = api.post(f"/v1/projects/{project_id}/implementation-packages")

    assert package.status_code == 201
    readiness = package.json()["payload"]["codegen_readiness"]
    assert readiness["codegen_ready"] is False
    assert any("acyclic DAG" in blocker for blocker in readiness["blockers"])
