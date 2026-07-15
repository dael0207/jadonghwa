from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI, HTTPException, status

from work_discovery_api.contracts import ContractPaths, validate_payload
from work_discovery_api.domain import AuditAction
from work_discovery_api.models import ReleaseReadinessRead, ValidationRead
from work_discovery_api.release_readiness import (
    DeterministicReleaseReadinessEvaluator,
    ReleaseReadinessInput,
)
from work_discovery_api.repository import WorkDiscoveryRepository


def register_m8_routes(
    app: FastAPI,
    app_store: WorkDiscoveryRepository,
    paths: ContractPaths,
    evaluator: DeterministicReleaseReadinessEvaluator,
) -> None:
    @app.post(
        "/v1/projects/{project_id}/release-readiness",
        response_model=ReleaseReadinessRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_release_readiness(project_id: str) -> ReleaseReadinessRead:
        try:
            app_store.require_project(project_id)
            payload = evaluator.evaluate(
                ReleaseReadinessInput(
                    project_id=project_id,
                    design_packages=app_store.list_project_design_packages(project_id),
                    blueprints=app_store.list_project_blueprints(project_id),
                    evaluation_runs=app_store.list_project_evaluation_runs(project_id),
                    previous_reports=app_store.list_project_release_readiness_reports(project_id),
                    audit_events=app_store.list_project_audit_events(project_id),
                ),
            )
            validation_error = validate_payload(paths.release_readiness_schema, payload)
            if validation_error is not None:
                detail = f"generated release readiness failed schema validation: {validation_error}"
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
            report = app_store.save_release_readiness_report(project_id, payload, valid=True)
            app_store.record_audit(
                report.id,
                AuditAction.RELEASE_READINESS_CREATED,
                {
                    "project_id": project_id,
                    "release_readiness_id": report.id,
                    "readiness_status": payload["readiness_status"],
                },
            )
            return report
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get(
        "/v1/projects/{project_id}/release-readiness",
        response_model=list[ReleaseReadinessRead],
    )
    def list_release_readiness(project_id: str) -> Sequence[ReleaseReadinessRead]:
        try:
            return app_store.list_project_release_readiness_reports(project_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.get("/v1/release-readiness/{report_id}", response_model=ReleaseReadinessRead)
    def get_release_readiness(report_id: str) -> ReleaseReadinessRead:
        try:
            return app_store.get_release_readiness_report(report_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    @app.post("/v1/release-readiness/{report_id}/validate", response_model=ValidationRead)
    def validate_release_readiness(report_id: str) -> ValidationRead:
        try:
            report = app_store.get_release_readiness_report(report_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        validation_error = validate_payload(paths.release_readiness_schema, report.payload)
        app_store.record_audit(
            report.id,
            AuditAction.RELEASE_READINESS_VALIDATED,
            {
                "project_id": report.project_id,
                "release_readiness_id": report.id,
                "valid": validation_error is None,
            },
        )
        return ValidationRead(
            valid=validation_error is None,
            schema_name="release-readiness-v1.schema.json",
            error=validation_error,
        )
